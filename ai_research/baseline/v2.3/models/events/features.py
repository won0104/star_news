"""Gold/predicted upstream을 동일하게 표현하는 공개 Event feature 계약.

Argument role의 출처(oracle one-hot 또는 predicted probability)는 이 모듈 밖에서
결정한다. 조립기는 어느 출처든 같은 ``[B,P,4]`` weight 계약으로 받아 역할별로
pooling한다. Event coreference와 Relation은 Gold record를 보지 않고 이 결과만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from ..contracts import CandidateBatch, EVENT_ARGUMENT_ROLES, gather_candidates


CURRENT_EVENT_FEATURE_CHANNELS = (
    "proposition",
    "trigger",
    "raw_actor",
    "raw_target",
    "raw_place",
    "resolved_entity",
    "time",
    "document_context",
)
CURRENT_EVENT_OPTIONAL_CHANNELS = (
    "trigger",
    "raw_actor",
    "raw_target",
    "raw_place",
    "resolved_entity",
    "time",
)


@dataclass(slots=True)
class EventFeatureBundle:
    """Event별 public upstream feature.

    모든 representation은 ``[B,E,H]``이며 ``role_presence_mask``는
    ``[B,E,4]`` (ACTOR/TARGET/PLACE/TIME), ``event_mask``는 ``[B,E]``다.
    ``feature_source``는 ``oracle_teacher_forced`` 또는 ``predicted_cascaded``다.
    """

    semantic_span_rep: torch.Tensor
    trigger_rep: torch.Tensor
    actor_rep: torch.Tensor
    target_rep: torch.Tensor
    place_rep: torch.Tensor
    time_rep: torch.Tensor
    role_presence_mask: torch.BoolTensor
    sentence_context: torch.Tensor
    document_context: torch.Tensor
    event_mask: torch.BoolTensor
    feature_source: str
    # Current canonical EventFrame migration fields. They are optional so the
    # historical multi-task bundle and checkpoints keep their exact shape.
    resolved_entity_rep: torch.Tensor | None = None
    channel_availability_mask: torch.BoolTensor | None = None
    channel_counts: torch.Tensor | None = None
    channel_confidence: torch.Tensor | None = None

    def validate(self) -> None:
        base = self.semantic_span_rep.shape
        if len(base) != 3:
            raise ValueError("event representations must have shape [B,E,H]")
        for name in (
            "trigger_rep",
            "actor_rep",
            "target_rep",
            "place_rep",
            "time_rep",
            "sentence_context",
            "document_context",
        ):
            if getattr(self, name).shape != base:
                raise ValueError(f"{name} must match semantic_span_rep [B,E,H]")
        if self.role_presence_mask.shape != (*base[:2], len(EVENT_ARGUMENT_ROLES)):
            raise ValueError("role_presence_mask must have shape [B,E,4]")
        if self.role_presence_mask.dtype is not torch.bool:
            raise ValueError("role_presence_mask must be boolean")
        if self.event_mask.shape != base[:2] or self.event_mask.dtype is not torch.bool:
            raise ValueError("event_mask must be bool [B,E]")
        if self.feature_source not in {"oracle_teacher_forced", "predicted_cascaded"}:
            raise ValueError("unknown EventFeatureBundle feature_source")
        current = (
            self.resolved_entity_rep,
            self.channel_availability_mask,
            self.channel_counts,
            self.channel_confidence,
        )
        if any(value is not None for value in current):
            if any(value is None for value in current):
                raise ValueError("current EventFeatureBundle fields must be supplied together")
            if self.resolved_entity_rep.shape != base:
                raise ValueError("resolved_entity_rep must match semantic_span_rep [B,E,H]")
            if self.channel_availability_mask.shape != (
                *base[:2], len(CURRENT_EVENT_FEATURE_CHANNELS)
            ) or self.channel_availability_mask.dtype is not torch.bool:
                raise ValueError("channel_availability_mask must be bool [B,E,8]")
            expected_optional = (*base[:2], len(CURRENT_EVENT_OPTIONAL_CHANNELS))
            if self.channel_counts.shape != expected_optional:
                raise ValueError("channel_counts must have shape [B,E,6]")
            if self.channel_confidence.shape != expected_optional:
                raise ValueError("channel_confidence must have shape [B,E,6]")

    @property
    def role_representations(self) -> tuple[torch.Tensor, ...]:
        return self.actor_rep, self.target_rep, self.place_rep, self.time_rep


class EventFeatureAssembler:
    """Candidate state와 role weight를 역할별 EventFeatureBundle로 조립한다.

    이 클래스에는 parameter가 없다. ``argument_role_weights``는 Argument pair 순서와
    같은 ``[B,P_argument,4]``이고 NONE mass는 포함하지 않는다. Event proxy(현재 Gold의
    LocalEvent relation endpoint)는 ``event_source_indices``로 대응 mention의 Argument
    prediction을 재사용한다. 이 proxy는 P1에서 cluster representation으로 교체할 경계다.
    """

    def __init__(self, *, role_presence_threshold: float = 0.5) -> None:
        if not 0.0 <= role_presence_threshold <= 1.0:
            raise ValueError("role_presence_threshold must be in [0,1]")
        self.role_presence_threshold = role_presence_threshold

    def __call__(
        self,
        *,
        candidate_states: torch.Tensor,
        candidates: CandidateBatch,
        sentence_states: torch.Tensor,
        document_state: torch.Tensor,
        argument_role_weights: torch.Tensor,
        feature_source: str,
    ) -> EventFeatureBundle:
        event_count = candidates.event_indices.shape[1]
        hidden = candidate_states.shape[-1]
        expected = (*candidates.pairs["argument"].mask.shape, len(EVENT_ARGUMENT_ROLES))
        if argument_role_weights.shape != expected:
            raise ValueError(
                f"argument_role_weights must have shape {expected}, got {tuple(argument_role_weights.shape)}"
            )
        if event_count == 0:
            empty = candidate_states.new_zeros(candidate_states.shape[0], 0, hidden)
            bundle = EventFeatureBundle(
                empty,
                empty.clone(),
                empty.clone(),
                empty.clone(),
                empty.clone(),
                empty.clone(),
                torch.zeros(
                    candidate_states.shape[0],
                    0,
                    len(EVENT_ARGUMENT_ROLES),
                    dtype=torch.bool,
                    device=candidate_states.device,
                ),
                empty.clone(),
                empty.clone(),
                candidates.event_mask,
                feature_source,
            )
            bundle.validate()
            return bundle

        semantic = gather_candidates(candidate_states, candidates.event_indices)
        trigger = gather_candidates(candidate_states, candidates.event_trigger_indices)
        trigger = trigger * candidates.event_trigger_mask.unsqueeze(-1)

        argument_pairs = candidates.pairs["argument"]
        argument_targets = gather_candidates(candidate_states, argument_pairs.target_indices)
        same_source = (
            candidates.event_source_indices.unsqueeze(-1)
            == argument_pairs.source_indices.unsqueeze(1)
        )
        pair_mask = (
            same_source
            & candidates.event_mask.unsqueeze(-1)
            & argument_pairs.mask.unsqueeze(1)
        )
        weights = argument_role_weights.to(candidate_states.dtype).clamp_min(0)
        weights = weights.unsqueeze(1) * pair_mask.unsqueeze(-1)
        # [B,E,P,R] x [B,P,H] -> [B,E,R,H]
        numerator = torch.einsum("bepr,bph->berh", weights, argument_targets)
        mass = weights.sum(dim=2)
        role_states = numerator / mass.unsqueeze(-1).clamp_min(1e-8)
        role_states = role_states * candidates.event_mask.unsqueeze(-1).unsqueeze(-1)
        role_presence = (mass >= self.role_presence_threshold) & candidates.event_mask.unsqueeze(-1)

        event_spans = gather_candidates(candidates.span_indices, candidates.event_indices)
        sentence_indices = event_spans[..., 0].long().clamp(0, sentence_states.shape[1] - 1)
        sentence_context = sentence_states.gather(
            1,
            sentence_indices.unsqueeze(-1).expand(-1, -1, sentence_states.shape[-1]),
        )
        document_context = document_state.unsqueeze(1).expand(-1, event_count, -1)
        event_float_mask = candidates.event_mask.unsqueeze(-1)
        bundle = EventFeatureBundle(
            semantic_span_rep=semantic * event_float_mask,
            trigger_rep=trigger * event_float_mask,
            actor_rep=role_states[:, :, 0],
            target_rep=role_states[:, :, 1],
            place_rep=role_states[:, :, 2],
            time_rep=role_states[:, :, 3],
            role_presence_mask=role_presence,
            sentence_context=sentence_context * event_float_mask,
            document_context=document_context * event_float_mask,
            event_mask=candidates.event_mask,
            feature_source=feature_source,
        )
        bundle.validate()
        return bundle


class EventFeatureEncoder(nn.Module):
    """공개 bundle을 Event pair/relation용 ``[B,E,H]`` state로 투영한다."""

    def __init__(
        self,
        hidden_size: int,
        dropout: float,
        *,
        current_contract: bool = False,
    ) -> None:
        super().__init__()
        self.current_contract = current_contract
        input_size = hidden_size * 8 + len(EVENT_ARGUMENT_ROLES)
        if current_contract:
            input_size += (
                hidden_size
                + len(CURRENT_EVENT_FEATURE_CHANNELS)
                + 2 * len(CURRENT_EVENT_OPTIONAL_CHANNELS)
            )
        self.output = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size),
            nn.LayerNorm(hidden_size),
        )

    def forward(self, bundle: EventFeatureBundle) -> torch.Tensor:
        bundle.validate()
        parts = [
            bundle.semantic_span_rep,
            bundle.trigger_rep,
            *bundle.role_representations,
            bundle.sentence_context,
            bundle.document_context,
            bundle.role_presence_mask.to(bundle.semantic_span_rep.dtype),
        ]
        if self.current_contract:
            if bundle.resolved_entity_rep is None:
                raise ValueError("current EventFeatureEncoder requires migrated EventFrame fields")
            parts.extend(
                (
                    bundle.resolved_entity_rep,
                    bundle.channel_availability_mask.to(bundle.semantic_span_rep.dtype),
                    bundle.channel_counts.to(bundle.semantic_span_rep.dtype),
                    bundle.channel_confidence.to(bundle.semantic_span_rep.dtype),
                )
            )
        features = torch.cat(parts, dim=-1)
        return self.output(features) * bundle.event_mask.unsqueeze(-1)
