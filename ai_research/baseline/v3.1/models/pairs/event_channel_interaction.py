"""Event channel correspondence를 보존하는 대칭 pair interaction scorer.

기존 Event-level pair 경로는 그대로 사용한다. 이 모듈은 EventFeatureBundle의
identity-critical hidden channel을 각각 비교하고, 그 결과를 기존 pair state에
추가한다. Optional channel이 한쪽에만 있을 때 hidden-vector 차이를 mismatch로
해석하지 않도록 양쪽이 모두 available인 경우에만 semantic interaction을 연다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection

import torch
from torch import nn

from ..contracts import PairConfig, PairIndexBatch, PairOutput
from ..events import EventFeatureBundle
from .directed import _gather
from .symmetric import SymmetricPairEncoder


EVENT_INTERACTION_CHANNELS = (
    "proposition",
    "trigger",
    "actor",
    "target",
    "place",
    "resolved_entity",
    "time",
)

_CHANNEL_SPECS = {
    "proposition": ("semantic_span_rep", 0, None),
    "trigger": ("trigger_rep", 1, 0),
    "actor": ("actor_rep", 2, 1),
    "target": ("target_rep", 3, 2),
    "place": ("place_rep", 4, 3),
    "resolved_entity": ("resolved_entity_rep", 5, 4),
    "time": ("time_rep", 6, 5),
}


@dataclass(slots=True)
class EventChannelPairInteractionOutput:
    """Fused state와 channel별 진단 tensor를 함께 반환한다."""

    state: torch.Tensor
    mask: torch.BoolTensor
    channel_states: dict[str, torch.Tensor]
    raw_interactions: dict[str, torch.Tensor]
    availability_states: dict[str, torch.Tensor]


class EventChannelPairInteractionEncoder(nn.Module):
    """각 EventFeatureBundle channel을 섞기 전에 대칭적으로 직접 비교한다.

    Semantic input은 ``sum/product/absdiff``이며 optional channel은 BOTH_AVAILABLE일
    때만 이 input을 사용한다. Availability와 기존 count/confidence는 unordered
    ``min/max/absdiff`` metadata로 별도 전달한다.
    """

    def __init__(
        self,
        hidden_size: int,
        *,
        interaction_size: int | None = None,
        output_size: int | None = None,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.interaction_size = interaction_size or max(hidden_size // 8, 1)
        self.output_size = output_size or hidden_size
        projections = {}
        for channel in EVENT_INTERACTION_CHANNELS:
            optional_index = _CHANNEL_SPECS[channel][2]
            metadata_size = 3 if optional_index is None else 9
            projections[channel] = nn.Sequential(
                nn.Linear(hidden_size * 3 + metadata_size, self.interaction_size),
                nn.GELU(),
                nn.LayerNorm(self.interaction_size),
            )
        self.channel_projections = nn.ModuleDict(projections)
        self.output = nn.Sequential(
            nn.Linear(len(EVENT_INTERACTION_CHANNELS) * self.interaction_size, self.output_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.LayerNorm(self.output_size),
        )

    def forward(
        self,
        bundle: EventFeatureBundle,
        pairs: PairIndexBatch,
        *,
        disabled_channels: Collection[str] = (),
    ) -> EventChannelPairInteractionOutput:
        bundle.validate()
        if bundle.channel_availability_mask is None:
            raise ValueError("Event channel interaction requires current EventFeatureBundle fields")
        pairs.validate(bundle.event_mask.shape[1])
        unknown = set(disabled_channels) - set(EVENT_INTERACTION_CHANNELS)
        if unknown:
            raise ValueError(f"unknown disabled Event interaction channels: {sorted(unknown)}")

        disabled = set(disabled_channels)
        _, left_mask = _gather(bundle.event_mask, bundle.event_mask, pairs.source_indices)
        _, right_mask = _gather(bundle.event_mask, bundle.event_mask, pairs.target_indices)
        pair_mask = pairs.mask & left_mask & right_mask
        channel_states: dict[str, torch.Tensor] = {}
        raw_interactions: dict[str, torch.Tensor] = {}
        availability_states: dict[str, torch.Tensor] = {}

        for channel in EVENT_INTERACTION_CHANNELS:
            tensor_name, availability_index, optional_index = _CHANNEL_SPECS[channel]
            representation = getattr(bundle, tensor_name)
            left, _ = _gather(representation, bundle.event_mask, pairs.source_indices)
            right, _ = _gather(representation, bundle.event_mask, pairs.target_indices)
            left_available, _ = _gather(
                bundle.channel_availability_mask[..., availability_index],
                bundle.event_mask,
                pairs.source_indices,
            )
            right_available, _ = _gather(
                bundle.channel_availability_mask[..., availability_index],
                bundle.event_mask,
                pairs.target_indices,
            )
            both = left_available & right_available & pair_mask
            one = (left_available ^ right_available) & pair_mask
            neither = (~left_available & ~right_available) & pair_mask
            availability = torch.stack((both, one, neither), dim=-1).to(left.dtype)
            semantic = torch.cat((left + right, left * right, (left - right).abs()), dim=-1)
            semantic = semantic * both.unsqueeze(-1)
            raw_interactions[channel] = semantic
            availability_states[channel] = availability

            metadata = [availability]
            if optional_index is not None:
                left_count, _ = _gather(
                    bundle.channel_counts[..., optional_index : optional_index + 1],
                    bundle.event_mask,
                    pairs.source_indices,
                )
                right_count, _ = _gather(
                    bundle.channel_counts[..., optional_index : optional_index + 1],
                    bundle.event_mask,
                    pairs.target_indices,
                )
                left_confidence, _ = _gather(
                    bundle.channel_confidence[..., optional_index : optional_index + 1],
                    bundle.event_mask,
                    pairs.source_indices,
                )
                right_confidence, _ = _gather(
                    bundle.channel_confidence[..., optional_index : optional_index + 1],
                    bundle.event_mask,
                    pairs.target_indices,
                )
                metadata.extend(
                    (
                        torch.minimum(left_count, right_count),
                        torch.maximum(left_count, right_count),
                        (left_count - right_count).abs(),
                        torch.minimum(left_confidence, right_confidence),
                        torch.maximum(left_confidence, right_confidence),
                        (left_confidence - right_confidence).abs(),
                    )
                )
            channel_input = torch.cat((semantic, *metadata), dim=-1)
            projected = self.channel_projections[channel](channel_input)
            if channel in disabled:
                projected = torch.zeros_like(projected)
            channel_states[channel] = projected * pair_mask.unsqueeze(-1)

        fused = self.output(
            torch.cat([channel_states[channel] for channel in EVENT_INTERACTION_CHANNELS], dim=-1)
        )
        fused = fused * pair_mask.unsqueeze(-1)
        return EventChannelPairInteractionOutput(
            state=fused,
            mask=pair_mask,
            channel_states=channel_states,
            raw_interactions=raw_interactions,
            availability_states=availability_states,
        )


class EventCoreferenceInteractionHead(nn.Module):
    """기존 Event-level pair state와 explicit channel interaction을 함께 분류한다."""

    def __init__(
        self,
        config: PairConfig,
        *,
        interaction_size: int | None = None,
        labels: int = 2,
    ) -> None:
        super().__init__()
        self.baseline_pair_encoder = SymmetricPairEncoder(config)
        self.interaction_encoder = EventChannelPairInteractionEncoder(
            config.hidden_size,
            interaction_size=interaction_size,
            output_size=config.hidden_size,
            dropout=config.dropout,
        )
        self.fusion = nn.Sequential(
            nn.Linear(config.hidden_size * 2, config.hidden_size),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size, config.hidden_size),
            nn.LayerNorm(config.hidden_size),
        )
        self.classifier = nn.Linear(config.hidden_size, labels)

    def forward(
        self,
        candidate_states: torch.Tensor,
        candidate_spans: torch.LongTensor,
        candidate_mask: torch.BoolTensor,
        pairs: PairIndexBatch,
        document_state: torch.Tensor,
        bundle: EventFeatureBundle,
        *,
        disabled_channels: Collection[str] = (),
        mode: str = "full",
    ) -> PairOutput:
        if mode not in {"full", "no_explicit_interaction", "interaction_only"}:
            raise ValueError(f"unknown Event coreference interaction mode: {mode}")
        baseline, baseline_mask = self.baseline_pair_encoder(
            candidate_states,
            candidate_spans,
            candidate_mask,
            pairs,
            document_state,
        )
        interaction = self.interaction_encoder(
            bundle,
            pairs,
            disabled_channels=disabled_channels,
        )
        pair_mask = baseline_mask & interaction.mask
        if mode == "no_explicit_interaction":
            explicit_state = torch.zeros_like(interaction.state)
        else:
            explicit_state = interaction.state
        if mode == "interaction_only":
            baseline = torch.zeros_like(baseline)
        fused = self.fusion(torch.cat((baseline, explicit_state), dim=-1))
        fused = fused * pair_mask.unsqueeze(-1)
        return PairOutput(self.classifier(fused), pair_mask)
