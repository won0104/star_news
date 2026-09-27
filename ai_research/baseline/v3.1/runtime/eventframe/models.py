"""Canonical compositions of the already-selected Semantic and B2 topologies.

These classes deliberately preserve checkpoint key names. They contain no Gold
adapter, training target, matching helper, or new model feature.
"""

from __future__ import annotations

from types import SimpleNamespace

import torch
from torch import nn
from torch.nn import functional as F

from models.attributes.statement_type import StatementTypeHead
from models.context import CandidateSpanEncoder, DocumentContextEncoder
from models.contracts import ModelConfig, PairConfig, PairIndexBatch, SPAN_KINDS
from models.events import EventFeatureEncoder
from models.pairs.directed import DirectedPairEncoder
from models.pairs.entity_coreference import EntityCoreferenceHead
from models.pairs.event_coreference import EventCoreferenceHead
from models.pairs.event_channel_interaction import EventCoreferenceInteractionHead
from models.pairs.participant_resolution import ParticipantEntityResolutionHead
from models.spans.canonical_v3 import CanonicalSpanRepresentationV3, JointSpanProposalHead
from models.spans.semantic import SemanticSpanHead
from models.spans.entity import EntitySpanNativeHead
from models.spans.time import TimeExpressionSpanNativeHead
from models.spans.trigger import TriggerBoundaryHead


SEMANTIC_LABELS = ("EVENT", "STATEMENT")
CANONICAL_V3_LABELS = SEMANTIC_LABELS
PARTICIPANT_ROLES = ("ACTOR", "TARGET", "PLACE")
ENTITY_TYPES = ("PERSON", "ORGANIZATION", "LOCATION", "PRODUCT")


def _span_batch(
    rows: list[list[int]], kinds: list[int], *, device: torch.device
) -> SimpleNamespace:
    return SimpleNamespace(
        span_indices=torch.tensor([rows], dtype=torch.long, device=device).reshape(1, -1, 3),
        span_kind_ids=torch.tensor([kinds], dtype=torch.long, device=device),
        span_mask=torch.ones(1, len(rows), dtype=torch.bool, device=device),
    )


class CanonicalV3SemanticRuntimeModel(nn.Module):
    """기존 same-seed DCE/TOP32 proposer와 frozen Canonical V3를 그대로 연결한다."""

    def __init__(self) -> None:
        super().__init__()
        config = ModelConfig()
        self.document_context = DocumentContextEncoder(config.context)
        self.joint_proposer = JointSpanProposalHead(
            hidden_size=config.context.hidden_size,
            labels=len(CANONICAL_V3_LABELS),
            projection_size=config.semantic_biaffine_size,
            dropout=config.dropout,
        )
        self.canonical_v3 = CanonicalSpanRepresentationV3()
        self.representation_layer = config.layers.semantic

    def load_upstream_state(self, state: dict[str, torch.Tensor]) -> None:
        dce = {
            key.removeprefix("document_context."): value
            for key, value in state.items() if key.startswith("document_context.")
        }
        proposer = {
            key.removeprefix("joint_proposer."): value
            for key, value in state.items() if key.startswith("joint_proposer.")
        }
        self.document_context.load_state_dict(dce, strict=True)
        self.joint_proposer.load_state_dict(proposer, strict=True)

    def encode_and_propose(self, batch, backbone):
        raw_states = backbone.layer(self.representation_layer)
        context = self.document_context(
            raw_states, batch.source_token_mask, batch.sentence_mask,
            batch.sentence_positions,
        )
        return raw_states, context.token_states, self.joint_proposer(context.token_states)


class SemanticRuntimeModel(nn.Module):
    """Exact selected Semantic topology with stable state-dict names."""

    def __init__(self) -> None:
        super().__init__()
        config = ModelConfig()
        self.document_context = DocumentContextEncoder(config.context)
        self.semantic = _SemanticRuntimeAdapter(
            SemanticSpanHead(
                hidden_size=config.context.hidden_size,
                labels=2,
                biaffine_size=config.semantic_biaffine_size,
                max_span_width=config.context.max_span_width,
                width_size=config.context.width_embedding_size,
                dropout=config.dropout,
            ),
            config.layers.semantic,
        )

    def forward(self, batch, backbone):
        context = self.document_context(
            backbone.layer(self.semantic.representation_layer),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )
        output = self.semantic(
            token_states=context.token_states,
            sentence_states=context.sentence_states,
            token_mask=batch.source_token_mask,
        )
        return context, output


class TriggerRuntimeModel(nn.Module):
    """Historical Trigger boundary topology, isolated from the joint checkpoint."""

    def __init__(self) -> None:
        super().__init__()
        config = ModelConfig()
        self.representation_layer = config.layers.trigger
        self.head = TriggerBoundaryHead(
            config.context.input_hidden_size,
            config.head_hidden_size,
            config.dropout,
        )

    def forward(self, batch, backbone):
        return self.head(
            backbone.layer(self.representation_layer), batch.source_token_mask
        )


class StatementTypeRuntimeModel(nn.Module):
    """Curated-compatible existing Statement span classifier topology."""

    def __init__(self) -> None:
        super().__init__()
        self.config = ModelConfig()
        self.document_context = DocumentContextEncoder(self.config.context)
        self.candidate_span_encoder = CandidateSpanEncoder(
            self.config.context, self.config.layers
        )
        self.head = StatementTypeHead(
            self.config.context.hidden_size,
            len(self.config.taxonomy.statement_types),
            self.config.dropout,
        )

    def forward_statements(self, batch, backbone, statements):
        context = self.document_context(
            backbone.layer(self.config.layers.sentence_presence),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )
        rows = [statement["aligned"] for statement in statements]
        candidates = _span_batch(
            rows,
            [SPAN_KINDS.index("STATEMENT")] * len(rows),
            device=batch.input_ids.device,
        )
        states = self.candidate_span_encoder.forward_runtime_direct(
            backbone, context, candidates, batch.source_token_mask
        )
        return self.head(states, candidates.span_mask)


class EntityMentionRuntimeModel(nn.Module):
    """Nested-capable L12 span-native Entity Mention extractor."""

    def __init__(self) -> None:
        super().__init__()
        self.config = ModelConfig()
        self.document_context = DocumentContextEncoder(self.config.context)
        self.candidate_span_encoder = CandidateSpanEncoder(
            self.config.context, self.config.layers
        )
        self.head = EntitySpanNativeHead(
            self.config.context.hidden_size,
            self.config.head_hidden_size,
            len(ENTITY_TYPES),
            self.config.dropout,
        )

    def encode_context(self, batch, backbone):
        return self.document_context(
            backbone.layer(self.config.layers.sentence_presence),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )

    def forward_candidates(self, batch, backbone, context, candidates, boundary_features):
        states = self.candidate_span_encoder.forward_runtime_direct(
            backbone, context, candidates, batch.source_token_mask
        )
        return self.head(states, boundary_features, candidates.span_mask)


class EntityCandidatePriorityRuntimeModel(nn.Module):
    """Fixed v2 binary MLP used only for non-destructive priority metadata."""

    def __init__(
        self, input_size: int = 1806, hidden_size: int = 128, dropout: float = 0.1
    ) -> None:
        super().__init__()
        self.classifier = nn.Sequential(
            nn.LayerNorm(input_size),
            nn.Linear(input_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if features.ndim != 2:
            raise ValueError("Entity priority verifier expects [candidate, feature]")
        return self.classifier(features).squeeze(-1)


class EntityCoreferenceRuntimeModel(nn.Module):
    """Symmetric stage-⑥ EntityMention identity scorer."""

    def __init__(self, policy_feature_size: int = 16) -> None:
        super().__init__()
        self.config = PairConfig(policy_feature_size=policy_feature_size)
        self.head = EntityCoreferenceHead(self.config)

    def forward(self, states, spans, mask, pairs, document_state):
        return self.head(states, spans, mask, pairs, document_state)


class ParticipantEntityResolutionRuntimeModel(nn.Module):
    """Directed stage-⑥ raw Participant→EntityMention resolver."""

    def __init__(self, policy_feature_size: int = 21) -> None:
        super().__init__()
        self.config = PairConfig(policy_feature_size=policy_feature_size)
        self.head = ParticipantEntityResolutionHead(self.config)

    def forward(self, states, spans, kinds, mask, pairs, document_state):
        return self.head(states, spans, kinds, mask, pairs, document_state)


class TimeExpressionRuntimeModel(nn.Module):
    """Subtype-free, nested-capable L10 generic TimeExpression extractor."""

    def __init__(self) -> None:
        super().__init__()
        self.config = ModelConfig()
        self.document_context = DocumentContextEncoder(self.config.context)
        self.candidate_span_encoder = CandidateSpanEncoder(
            self.config.context, self.config.layers
        )
        self.head = TimeExpressionSpanNativeHead(
            self.config.context.hidden_size,
            self.config.head_hidden_size,
            self.config.dropout,
        )

    def encode_context(self, batch, backbone):
        return self.document_context(
            backbone.layer(self.config.layers.sentence_presence),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )

    def forward_candidates(self, batch, backbone, context, candidates, boundary_features):
        states = self.candidate_span_encoder.forward_runtime_direct(
            backbone, context, candidates, batch.source_token_mask
        )
        return self.head(states, boundary_features, candidates.span_mask)


class EventTimeAttachmentRuntimeModel(nn.Module):
    """Small directed Event→TimeExpression binary attachment model."""

    def __init__(self) -> None:
        super().__init__()
        self.config = ModelConfig()
        self.document_context = DocumentContextEncoder(self.config.context)
        self.candidate_span_encoder = CandidateSpanEncoder(
            self.config.context, self.config.layers
        )
        self.pair_encoder = DirectedPairEncoder(
            self.config.pairs, task_names=("event_time",)
        )
        self.head = nn.Linear(self.config.pairs.hidden_size, 1)

    def encode(self, batch, backbone, candidates):
        context = self.document_context(
            backbone.layer(self.config.layers.sentence_presence),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )
        states = self.candidate_span_encoder.forward_runtime_direct(
            backbone, context, candidates, batch.source_token_mask
        )
        return context, states

    def forward_pairs(
        self,
        states,
        candidates,
        pairs: PairIndexBatch,
        document_state,
    ):
        pair_states, pair_mask = self.pair_encoder(
            states,
            candidates.span_indices,
            candidates.span_kind_ids,
            candidates.span_mask,
            pairs,
            document_state,
            task_name="event_time",
        )
        return self.head(pair_states).squeeze(-1).masked_fill(~pair_mask, 0.0), pair_mask


class _SemanticRuntimeAdapter(nn.Module):
    """Inference-only adapter retaining the selected checkpoint's ``semantic.head`` keys."""

    def __init__(self, head: SemanticSpanHead, representation_layer: int) -> None:
        super().__init__()
        self.head = head
        self.representation_layer = representation_layer

    def forward(self, *, token_states, sentence_states, token_mask):
        return self.head(token_states, sentence_states, token_mask)


class ParticipantBoundaryHead(nn.Module):
    """Selected B2 additive Event-conditioned independent boundary topology."""

    def __init__(self, hidden: int = 256, dropout: float = 0.1) -> None:
        super().__init__()
        self.event_projection = nn.Linear(hidden, hidden)
        self.token_projection = nn.Linear(hidden, hidden)
        self.position_projection = nn.Linear(3, hidden, bias=False)
        self.norm = nn.LayerNorm(hidden)
        self.dropout = nn.Dropout(dropout)
        self.branches = nn.ModuleList([nn.Linear(hidden, 2) for _ in PARTICIPANT_ROLES])

    def forward(self, event_states, token_states, event_spans, token_mask):
        positions = torch.arange(token_states.shape[1], device=token_states.device)[None]
        start, end = event_spans[:, 1:2], event_spans[:, 2:3]
        scale = token_mask.sum(-1, keepdim=True).clamp_min(1)
        position = torch.stack(
            (
                (positions - start) / scale,
                (positions - (end - 1)) / scale,
                ((positions >= start) & (positions < end)).float(),
            ),
            dim=-1,
        )
        fused = self.norm(
            self.token_projection(token_states)
            + self.event_projection(event_states)[:, None]
            + self.position_projection(position)
        )
        fused = self.dropout(F.gelu(fused))
        return torch.stack([branch(fused) for branch in self.branches], dim=2)


class ParticipantB2RuntimeModel(nn.Module):
    """Exact selected Fair Comparison B2 topology with no supervision dependency."""

    def __init__(self, seed: int = 1008) -> None:
        super().__init__()
        self.config = ModelConfig()
        torch.manual_seed(seed)
        self.document_context = DocumentContextEncoder(self.config.context)
        self.candidate_span_encoder = CandidateSpanEncoder(
            self.config.context, self.config.layers
        )
        self.boundary_head = ParticipantBoundaryHead(
            self.config.context.hidden_size, self.config.context.dropout
        )

    def context_and_events(self, batch, backbone, events):
        context = self.document_context(
            backbone.layer(8),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )
        rows = [event["aligned"] for event in events]
        candidates = _span_batch(
            rows,
            [SPAN_KINDS.index("EVENT")] * len(rows),
            device=batch.input_ids.device,
        )
        states = self.candidate_span_encoder.forward_runtime_direct(
            backbone, context, candidates, batch.source_token_mask
        )
        return context, states

    def forward_events(self, batch, backbone, events):
        context, event_states = self.context_and_events(batch, backbone, events)
        spans = torch.tensor(
            [event["aligned"] for event in events],
            dtype=torch.long,
            device=context.token_states.device,
        )
        sentence_tokens = context.token_states[0, spans[:, 0]]
        token_mask = batch.source_token_mask[0, spans[:, 0]]
        return self.boundary_head(event_states[0], sentence_tokens, spans, token_mask), token_mask


class EventIdentityRuntimeModel(nn.Module):
    """Current EventFeatureBundle projection plus symmetric Event MERGE scorer."""

    def __init__(self, policy_feature_size: int = 12) -> None:
        super().__init__()
        config = ModelConfig()
        pair_config = PairConfig(
            hidden_size=config.pairs.hidden_size,
            projection_size=config.pairs.projection_size,
            kind_embedding_size=config.pairs.kind_embedding_size,
            distance_embedding_size=config.pairs.distance_embedding_size,
            order_embedding_size=config.pairs.order_embedding_size,
            task_embedding_size=config.pairs.task_embedding_size,
            max_sentence_distance=config.pairs.max_sentence_distance,
            policy_feature_size=policy_feature_size,
            dropout=config.pairs.dropout,
        )
        self.feature_encoder = EventFeatureEncoder(
            config.context.hidden_size,
            config.dropout,
            current_contract=True,
        )
        self.head = EventCoreferenceHead(pair_config, labels=2)

    def forward(self, bundle, event_spans, pairs):
        states = self.feature_encoder(bundle)
        return self.head(
            states,
            event_spans,
            bundle.event_mask,
            pairs,
            bundle.document_context[:, 0],
        )


class EventIdentityInteractionRuntimeModel(nn.Module):
    """Selected EventFeatureBundle encoder plus the fixed explicit interaction head."""

    def __init__(
        self,
        policy_feature_size: int = 12,
        interaction_size: int = 32,
    ) -> None:
        super().__init__()
        config = ModelConfig()
        pair_config = PairConfig(
            hidden_size=config.pairs.hidden_size,
            projection_size=config.pairs.projection_size,
            kind_embedding_size=config.pairs.kind_embedding_size,
            distance_embedding_size=config.pairs.distance_embedding_size,
            order_embedding_size=config.pairs.order_embedding_size,
            task_embedding_size=config.pairs.task_embedding_size,
            max_sentence_distance=config.pairs.max_sentence_distance,
            policy_feature_size=policy_feature_size,
            dropout=config.pairs.dropout,
        )
        self.feature_encoder = EventFeatureEncoder(
            config.context.hidden_size,
            config.dropout,
            current_contract=True,
        )
        self.head = EventCoreferenceInteractionHead(
            pair_config,
            interaction_size=interaction_size,
            labels=2,
        )

    def forward(self, bundle, event_spans, pairs):
        states = self.feature_encoder(bundle)
        return self.head(
            states,
            event_spans,
            bundle.event_mask,
            pairs,
            bundle.document_context[:, 0],
            bundle,
        )
