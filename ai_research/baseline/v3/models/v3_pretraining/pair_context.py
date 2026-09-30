"""ABOUT/CAUSES가 공유하는 원문 문장 기반 PairContextV1 계약.

원문 문장 state는 DCE window 출력을 ``sentence_index``별로 한 번만 평균한다.
endpoint summary는 node/cluster마다 한 번 만들고, pair별 작업은 최대 여덟 문장의
bounded bridge gather와 고정 순서 feature 조립으로 제한한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import torch

from runtime.v3_pretraining.source_layout import SourceLayout


PAIR_CONTEXT_VERSION = "pair-context-v1-2057"
PAIR_CONTEXT_VECTOR_ORDER = (
    "left", "right", "left_minus_right", "left_times_right",
    "left_sentence_context", "right_sentence_context", "bridge_context",
    "document_state",
)
PAIR_CONTEXT_SCALAR_ORDER = (
    "signed_distance_clipped_div_8", "abs_distance_clipped_div_8",
    "same", "adjacent", "non_adjacent", "bridge_available",
    "bridge_truncated", "left_multi_member", "right_multi_member",
)
PAIR_CONTEXT_HIDDEN = 256
PAIR_CONTEXT_DIM = len(PAIR_CONTEXT_VECTOR_ORDER) * PAIR_CONTEXT_HIDDEN + len(
    PAIR_CONTEXT_SCALAR_ORDER)
MAX_BRIDGE_SENTENCES = 8


@dataclass(frozen=True, slots=True)
class EndpointSentenceSummary:
    """한 endpoint의 label-independent 원문 문장 summary와 anchor provenance."""

    context: torch.Tensor
    sentence_indices: tuple[int, ...]
    anchor_index: int
    multi_member: bool


@dataclass(frozen=True, slots=True)
class PairContextProvenance:
    left_anchor: int
    right_anchor: int
    actual_distance: int
    left_sentence_indices: tuple[int, ...]
    right_sentence_indices: tuple[int, ...]
    bridge_sentence_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PairContextBatch:
    features: torch.Tensor
    provenance: tuple[PairContextProvenance, ...]
    max_bridge_gather: int


def original_sentence_states(layout: SourceLayout,
                             window_states: torch.Tensor) -> torch.Tensor:
    """DCE window rows를 원문 sentence index별 한 행으로 축약한다.

    Bridge view는 제외한다. 긴 한 문장의 겹치는 sentence window는 같은 원문
    문장으로 평균되므로 endpoint/bridge pooling에서 중복 가중되지 않는다.
    """
    if window_states.ndim != 2 or window_states.shape[0] != len(layout.windows):
        raise ValueError("DCE sentence rows differ from SourceLayout windows")
    rows: list[torch.Tensor] = []
    for sentence_index in range(len(layout.sentence_spans)):
        indices = [index for index, window in enumerate(layout.windows)
                   if window.view == "sentence" and window.sentence_index == sentence_index]
        if not indices:
            raise ValueError("original sentence has no DCE sentence window")
        gather = torch.tensor(indices, dtype=torch.long, device=window_states.device)
        rows.append(window_states.index_select(0, gather).mean(dim=0))
    return torch.stack(rows) if rows else window_states.new_empty((0, window_states.shape[-1]))


def _overlapping_sentences(sentence_spans: Sequence[tuple[int, int]],
                           start: int, end: int) -> tuple[int, ...]:
    if not 0 <= start < end:
        raise ValueError("endpoint span must be nonempty")
    indices = tuple(index for index, (sentence_start, sentence_end) in enumerate(sentence_spans)
                    if max(start, sentence_start) < min(end, sentence_end))
    if not indices:
        raise ValueError("endpoint span overlaps no original sentence")
    return indices


def summarize_statement(sentence_states: torch.Tensor,
                        sentence_spans: Sequence[tuple[int, int]], *,
                        start: int, end: int) -> EndpointSentenceSummary:
    indices = _overlapping_sentences(sentence_spans, start, end)
    gather = torch.tensor(indices, dtype=torch.long, device=sentence_states.device)
    return EndpointSentenceSummary(
        sentence_states.index_select(0, gather).mean(dim=0), indices, indices[0], False)


def summarize_event_members(sentence_states: torch.Tensor,
                            sentence_spans: Sequence[tuple[int, int]],
                            members: Sequence[tuple[str, int, int]]) -> EndpointSentenceSummary:
    """Event member 순서나 relation label/score와 무관한 cluster summary."""
    if not members:
        raise ValueError("EventCluster sentence summary needs at least one member")
    ordered = sorted(members, key=lambda row: (row[1], row[2], row[0]))
    by_member = [(member_id, _overlapping_sentences(sentence_spans, start, end))
                 for member_id, start, end in ordered]
    unique = tuple(sorted({index for _, indices in by_member for index in indices}))
    gather = torch.tensor(unique, dtype=torch.long, device=sentence_states.device)
    return EndpointSentenceSummary(
        sentence_states.index_select(0, gather).mean(dim=0), unique,
        by_member[0][1][0], len(members) >= 2)


def summarize_statements(sentence_states: torch.Tensor,
                         sentence_spans: Sequence[tuple[int, int]],
                         spans: Mapping[str, tuple[int, int]]) -> dict[str, EndpointSentenceSummary]:
    return {statement_id: summarize_statement(
        sentence_states, sentence_spans, start=start, end=end)
            for statement_id, (start, end) in spans.items()}


def _bridge_indices(left_anchor: int, right_anchor: int) -> tuple[tuple[int, ...], bool]:
    low, high = sorted((left_anchor, right_anchor))
    interior = tuple(range(low + 1, high))
    if len(interior) <= MAX_BRIDGE_SENTENCES:
        return interior, False
    selected = tuple(sorted(interior[:4] + interior[-4:]))
    return selected, True


def build_pair_context(*, left: torch.Tensor, right: torch.Tensor,
                       left_summaries: Sequence[EndpointSentenceSummary],
                       right_summaries: Sequence[EndpointSentenceSummary],
                       sentence_states: torch.Tensor,
                       document_state: torch.Tensor,
                       include_provenance: bool = True) -> PairContextBatch:
    """한 chunk의 2,057차원 relation 입력을 고정 순서로 조립한다."""
    count = left.shape[0]
    if (left.shape != right.shape or left.ndim != 2 or left.shape[1] != PAIR_CONTEXT_HIDDEN
            or len(left_summaries) != count or len(right_summaries) != count
            or sentence_states.ndim != 2 or sentence_states.shape[1] != PAIR_CONTEXT_HIDDEN
            or document_state.shape != (PAIR_CONTEXT_HIDDEN,)):
        raise ValueError("PairContextV1 input shape differs")
    if count == 0:
        return PairContextBatch(left.new_empty((0, PAIR_CONTEXT_DIM)), (), 0)
    bridge_rows = []
    scalar_rows = []
    provenance = []
    max_gather = 0
    zero = sentence_states.new_zeros((PAIR_CONTEXT_HIDDEN,))
    for left_summary, right_summary in zip(left_summaries, right_summaries):
        distance = right_summary.anchor_index - left_summary.anchor_index
        bridge, truncated = _bridge_indices(
            left_summary.anchor_index, right_summary.anchor_index)
        max_gather = max(max_gather, len(bridge))
        if bridge:
            gather = torch.tensor(bridge, dtype=torch.long, device=sentence_states.device)
            bridge_rows.append(sentence_states.index_select(0, gather).mean(dim=0))
        else:
            bridge_rows.append(zero)
        absolute = abs(distance)
        scalar_rows.append((
            max(-8, min(8, distance)) / 8.0,
            min(absolute, 8) / 8.0,
            float(absolute == 0), float(absolute == 1), float(absolute >= 2),
            float(bool(bridge)), float(truncated),
            float(left_summary.multi_member), float(right_summary.multi_member),
        ))
        if include_provenance:
            provenance.append(PairContextProvenance(
                left_summary.anchor_index, right_summary.anchor_index, distance,
                left_summary.sentence_indices, right_summary.sentence_indices, bridge))
    left_context = torch.stack([row.context for row in left_summaries])
    right_context = torch.stack([row.context for row in right_summaries])
    bridge_context = torch.stack(bridge_rows)
    document = document_state.unsqueeze(0).expand_as(left)
    scalars = left.new_tensor(scalar_rows)
    features = torch.cat((left, right, left - right, left * right,
                          left_context, right_context, bridge_context, document,
                          scalars), dim=-1)
    if features.shape != (count, PAIR_CONTEXT_DIM):
        raise AssertionError("PairContextV1 feature dimension changed")
    return PairContextBatch(features, tuple(provenance), max_gather)
