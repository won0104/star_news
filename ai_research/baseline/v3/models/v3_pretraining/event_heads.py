"""P5 Event identity: v2.3 Event encoder and symmetric pair branches adapted to v3.

The Event encoder runs for every retained member before routing. Selected pairs
alone enter the symmetric baseline and explicit channel interaction. Confidence
from a different source decision is never substituted for missing confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

import torch
from torch import nn

from models.contracts import PairConfig, PairIndexBatch
from models.pairs.symmetric import SymmetricPairEncoder
from models.v3_pretraining.architecture import V3Core


EVENT_CHANNELS = ("semantic", "trigger", "actor", "target", "place",
                  "entity", "time", "document")
PAIR_CHANNELS = EVENT_CHANNELS[:-1]
OPTIONAL_CHANNEL_INDICES = (1, 2, 3, 4, 5, 6)
PAIR_INTERACTION_WIDTH = 32
EVENT_PAIR_POLICY_VERSION = "V3_EVENT_PAIR_SOURCE_POLICY_15_V2"
# Historical v2.3 ROLE scalars depend on the removed resolver, and its Event
# verifier score has no same-decision v3 producer. Time is an explicit r06
# soft-evidence input; none of these values gates pairs or adds a fixed score.
EVENT_PAIR_POLICY_FEATURES = (
    "event_text_bigram_jaccard", "event_text_normalized_containment",
    "trigger_text_bigram_jaccard", "time_compatible", "time_incompatible",
    "time_incomparable", "time_unknown", "time_distance_365d_normalized",
    "time_interval_compatible", "time_interval_incompatible",
    "time_semantic_type_match", "time_shared_raw_evidence",
    "sentence_distance_capped_32",
    "both_triggers_present", "both_time_attachments_present",
)


@dataclass(frozen=True, slots=True)
class EventPairFeatureBundle:
    """Request-scoped Event input; confidence is meaningful only where known."""

    channel_means: torch.Tensor  # [N,8,H], including document channel
    channel_counts: torch.Tensor  # [N,8], raw source counts
    sentence_context: torch.Tensor  # [N,H]
    document_state: torch.Tensor  # [H]
    optional_counts: torch.Tensor  # [N,6], min(raw count,8)/8
    optional_confidence: torch.Tensor  # [N,6], probability where known
    confidence_known: torch.Tensor  # bool [N,6]
    _validated_versions: tuple[int, ...] | None = field(
        default=None, init=False, repr=False, compare=False)

    def validate(self) -> None:
        means = self.channel_means
        all_tensors = (means, self.channel_counts, self.sentence_context,
                       self.document_state, self.optional_counts,
                       self.optional_confidence, self.confidence_known)
        try:
            versions = tuple(value._version for value in all_tensors)
        except RuntimeError:
            # inference_mode tensors have no version counter: validate fully.
            versions = None
        if versions is not None and versions == self._validated_versions:
            return
        if means.ndim != 3 or means.shape[1] != len(EVENT_CHANNELS):
            raise ValueError("Event bundle needs [N,8,H] channel states")
        n, _, hidden = means.shape
        if (self.channel_counts.shape != (n, len(EVENT_CHANNELS)) or
                self.sentence_context.shape != (n, hidden) or
                self.document_state.shape != (hidden,) or
                self.optional_counts.shape != (n, len(OPTIONAL_CHANNEL_INDICES)) or
                self.optional_confidence.shape != self.optional_counts.shape or
                self.confidence_known.shape != self.optional_counts.shape or
                self.confidence_known.dtype is not torch.bool):
            raise ValueError("Event bundle source/count/confidence shapes differ")
        tensors = (means, self.channel_counts, self.sentence_context,
                   self.document_state, self.optional_counts,
                   self.optional_confidence)
        if (any(value.device != means.device or value.dtype != means.dtype or
                not bool(torch.isfinite(value).all()) for value in tensors) or
                bool((self.channel_counts < 0).any()) or
                bool(((self.optional_counts < 0) | (self.optional_counts > 1)).any()) or
                bool(((self.optional_confidence < 0) |
                      (self.optional_confidence > 1)).any())):
            raise ValueError("Event bundle needs finite, same-device source values")
        available = self.channel_counts[:, OPTIONAL_CHANNEL_INDICES] > 0
        if (bool((self.confidence_known & ~available).any()) or
                bool((self.optional_confidence[~self.confidence_known] != 0).any())):
            raise ValueError("unknown Event confidence must remain masked")
        if versions is not None:
            object.__setattr__(self, "_validated_versions", versions)


class EventFeatureEncoderV3(nn.Module):
    """v2.3's two-layer EventFeatureEncoder with explicit score availability."""

    def __init__(self, hidden: int, dropout: float) -> None:
        super().__init__()
        # v2.3: 9 hidden channels, 4 role presence, 8 availability, 6 counts,
        # 6 confidences. v3 adds 6 confidence-known bits for extension paths.
        input_size = hidden * 9 + 4 + len(EVENT_CHANNELS) + 3 * len(OPTIONAL_CHANNEL_INDICES)
        self.output = nn.Sequential(
            nn.Linear(input_size, hidden), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(hidden, hidden), nn.LayerNorm(hidden),
        )

    def forward(self, bundle: EventPairFeatureBundle) -> torch.Tensor:
        bundle.validate()
        means = bundle.channel_means
        available = bundle.channel_counts > 0
        document = bundle.document_state.unsqueeze(0).expand(len(means), -1)
        return self.output(torch.cat((
            means[:, 0], means[:, 1], means[:, 2], means[:, 3], means[:, 4],
            means[:, 6], bundle.sentence_context, document,
            available[:, (2, 3, 4, 6)].to(means.dtype), means[:, 5],
            available.to(means.dtype), bundle.optional_counts,
            bundle.optional_confidence, bundle.confidence_known.to(means.dtype),
        ), dim=-1))


class EventChannelPairInteractionV3(nn.Module):
    """v2.3's seven-channel interaction with masked confidence comparison."""

    def __init__(self, hidden: int, dropout: float) -> None:
        super().__init__()
        self.channel_projections = nn.ModuleDict({
            channel: nn.Sequential(
                nn.Linear(hidden * 3 + (3 if index == 0 else 12),
                          PAIR_INTERACTION_WIDTH),
                nn.GELU(), nn.LayerNorm(PAIR_INTERACTION_WIDTH),
            ) for index, channel in enumerate(PAIR_CHANNELS)
        })
        self.output = nn.Sequential(
            nn.Linear(len(PAIR_CHANNELS) * PAIR_INTERACTION_WIDTH, hidden),
            nn.GELU(), nn.Dropout(dropout), nn.LayerNorm(hidden),
        )

    def forward(self, bundle: EventPairFeatureBundle,
                pair_indices: torch.LongTensor) -> torch.Tensor:
        bundle.validate()
        n = len(bundle.channel_means)
        if (pair_indices.ndim != 2 or pair_indices.shape[1] != 2 or
                pair_indices.dtype != torch.long or
                (pair_indices.numel() and
                 (bool((pair_indices < 0).any()) or bool((pair_indices >= n).any())))):
            raise ValueError("Event interaction needs valid [P,2] member indices")
        if not len(pair_indices):
            return bundle.channel_means.new_empty((0, bundle.document_state.numel()))
        left_index, right_index = pair_indices[:, 0], pair_indices[:, 1]
        available = bundle.channel_counts > 0
        projected = []
        for index, channel in enumerate(PAIR_CHANNELS):
            left = bundle.channel_means[left_index, index]
            right = bundle.channel_means[right_index, index]
            left_available = available[left_index, index]
            right_available = available[right_index, index]
            both = left_available & right_available
            presence = torch.stack((both, left_available ^ right_available,
                                    ~(left_available | right_available)), dim=-1).to(left.dtype)
            semantic = torch.cat((left + right, left * right,
                                  (left - right).abs()), dim=-1) * both.unsqueeze(-1)
            metadata = [presence]
            if index:
                optional = index - 1
                a = bundle.optional_counts[left_index, optional:optional + 1]
                b = bundle.optional_counts[right_index, optional:optional + 1]
                metadata.extend((torch.minimum(a, b), torch.maximum(a, b), (a - b).abs()))
                known_a = bundle.confidence_known[left_index, optional]
                known_b = bundle.confidence_known[right_index, optional]
                both_known = known_a & known_b
                ca = bundle.optional_confidence[left_index, optional:optional + 1]
                cb = bundle.optional_confidence[right_index, optional:optional + 1]
                confidence = torch.cat((torch.minimum(ca, cb),
                                        torch.maximum(ca, cb), (ca - cb).abs()), dim=-1)
                metadata.append(confidence * both_known.unsqueeze(-1))
                metadata.append(torch.stack((both_known, known_a ^ known_b,
                                             ~(known_a | known_b)), dim=-1).to(left.dtype))
            projected.append(self.channel_projections[channel](
                torch.cat((semantic, *metadata), dim=-1)))
        return self.output(torch.cat(projected, dim=-1))


class EventIdentityHead(nn.Module):
    """Encode all members once, then classify only routed unordered Event pairs."""

    def __init__(self, hidden: int = 256, *, dropout: float = 0.1) -> None:
        super().__init__()
        self.feature_encoder = EventFeatureEncoderV3(hidden, dropout)
        pair_config = PairConfig(hidden_size=hidden, projection_size=hidden,
                                 policy_feature_size=len(EVENT_PAIR_POLICY_FEATURES),
                                 dropout=dropout)
        self.baseline_pair_encoder = SymmetricPairEncoder(pair_config)
        self.interaction_encoder = EventChannelPairInteractionV3(hidden, dropout)
        self.fusion = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(hidden, hidden), nn.LayerNorm(hidden),
        )
        self.classifier = nn.Linear(hidden, 2)

    def encode_events(self, bundle: EventPairFeatureBundle) -> torch.Tensor:
        """Includes singleton Events that no pair router ever selects."""
        bundle.validate()
        if len(bundle.channel_means) == 0:
            return bundle.channel_means.new_empty((0, bundle.document_state.numel()))
        return self.feature_encoder(bundle)

    def forward(self, bundle: EventPairFeatureBundle, encoded_events: torch.Tensor,
                sentence_indices: torch.LongTensor,
                pair_indices: torch.LongTensor,
                policy_features: torch.Tensor) -> torch.Tensor:
        bundle.validate()
        n, _, hidden = bundle.channel_means.shape
        if (encoded_events.shape != (n, hidden) or sentence_indices.shape != (n,) or
                sentence_indices.dtype != torch.long or
                pair_indices.ndim != 2 or pair_indices.shape[1] != 2 or
                pair_indices.dtype != torch.long or
                policy_features.shape !=
                (len(pair_indices), len(EVENT_PAIR_POLICY_FEATURES))):
            raise ValueError("Event states/sentence/pair/policy inputs differ")
        if not len(pair_indices):
            return encoded_events.new_empty((0, 2))
        device = encoded_events.device
        rows = PairIndexBatch(
            pair_indices[:, 0].unsqueeze(0), pair_indices[:, 1].unsqueeze(0),
            torch.ones((1, len(pair_indices)), dtype=torch.bool, device=device),
            policy_features.unsqueeze(0),
        )
        spans = torch.stack((sentence_indices, torch.zeros_like(sentence_indices),
                             torch.ones_like(sentence_indices)), dim=-1).unsqueeze(0)
        baseline, _ = self.baseline_pair_encoder(
            encoded_events.unsqueeze(0), spans,
            torch.ones((1, n), dtype=torch.bool, device=device), rows,
            bundle.document_state.unsqueeze(0))
        interaction = self.interaction_encoder(bundle, pair_indices)
        return self.classifier(self.fusion(torch.cat((baseline[0], interaction), dim=-1)))


def register_event_heads(core: V3Core) -> None:
    name = "event_coreference"
    seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(core.config.seed + seed_offset)
        module = EventIdentityHead(core.config.context.hidden_size,
                                   dropout=core.config.context.dropout)
    core.register_task(name, module, source_run_id=core.config.run_id)
