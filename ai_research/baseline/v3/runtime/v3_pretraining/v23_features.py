"""Shared v2.3 local-span scorer coordinates for v3 training and serving.

The sentence-window Canonical V3 and native span heads reuse the request's
backbone and DCE lease. Cross-window spans have no v2.3 sentence-window cell;
their v3 exact-source extension is handled by the caller.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Sequence

import torch

from models.contracts import SPAN_KINDS
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from runtime.v3_pretraining.source_layout import SourceLayout


def sentence_cell(layout: SourceLayout, start: int, end: int,
                  preferred_window_id: str | None = None) -> tuple[int, int, int, object, object] | None:
    """Find the source sentence token pair covering an exact character span."""
    if not 0 <= start < end <= len(layout.article.content):
        raise ValueError("source span is outside the article")
    # Sentence windows are already in source order. Restrict the scan to the
    # containing sentence without changing the first-valid-window tie break.
    sentence_index = bisect_right(
        layout.sentence_spans, (start, len(layout.article.content))) - 1
    if (sentence_index < 0 or
            not (layout.sentence_spans[sentence_index][0] <= start < end <=
                 layout.sentence_spans[sentence_index][1])):
        return None
    choices = ((index, window)
               for index, window in layout.sentence_windows_by_index[sentence_index]
               if preferred_window_id is None or
               window.window_id == preferred_window_id)
    for index, window in choices:
        first = next((token for token in window.tokens
                      if token.start <= start < token.end), None)
        last = next((token for token in window.tokens
                     if token.start < end <= token.end), None)
        if (first is not None and last is not None and
                0 < last.position - first.position + 1 <= 96):
            return index, first.position, last.position + 1, first, last
    return None


def event_candidate_state(*, layout: SourceLayout, batch, backbone,
                          shared: SharedForwardLease, core: V3Core,
                          start: int, end: int) -> torch.Tensor | None:
    """Encode an Event with the release CandidateSpanEncoder when locally representable."""
    cell = sentence_cell(layout, start, end)
    if cell is None:
        return None
    window, first, last, _first_token, _last_token = cell
    device = shared.token_states.device
    candidates = SimpleNamespace(
        span_indices=torch.tensor([[[window, first, last]]], dtype=torch.long, device=device),
        span_kind_ids=torch.full((1, 1), SPAN_KINDS.index("EVENT"),
                                 dtype=torch.long, device=device),
        span_mask=torch.ones((1, 1), dtype=torch.bool, device=device))
    return core.candidate_span.forward_runtime_direct_states(
        backbone, shared.sentence_states, candidates, batch.source_token_mask)[0, 0]


def local_source_states(*, kind: str, layout: SourceLayout, batch, backbone,
                        shared: SharedForwardLease, core: V3Core,
                        rows: Sequence[tuple[int, int]]) -> torch.Tensor:
    """Encode v2.3-representable source cells without the v3 exact bridge."""
    if kind not in ("EVENT", "STATEMENT") or not rows:
        raise ValueError("local source states require semantic source cells")
    cells = [sentence_cell(layout, start, end) for start, end in rows]
    if any(cell is None for cell in cells):
        raise ValueError("local source row has no sentence cell")
    device = shared.token_states.device
    candidates = SimpleNamespace(
        span_indices=torch.tensor([[(cell[0], cell[1], cell[2]) for cell in cells]],
                                  dtype=torch.long, device=device),
        span_kind_ids=torch.full((1, len(cells)), SPAN_KINDS.index(kind),
                                 dtype=torch.long, device=device),
        span_mask=torch.ones((1, len(cells)), dtype=torch.bool, device=device))
    return core.candidate_span.forward_runtime_direct_states(
        backbone, shared.sentence_states, candidates, batch.source_token_mask)[0]


def canonical_scores(*, layout: SourceLayout, batch, backbone, shared: SharedForwardLease,
                     core: V3Core, rows: Sequence[tuple[int, int, str | None]]
                     ) -> tuple[tuple[torch.Tensor, torch.Tensor] | None, ...]:
    """Apply v2.3 Canonical V3 to sentence cells, preserving caller row order."""
    grouped: dict[int, list[tuple[int, int, int, str]]] = {}
    output: list[tuple[torch.Tensor, torch.Tensor] | None] = [None] * len(rows)
    for index, (start, end, preferred) in enumerate(rows):
        cell = sentence_cell(layout, start, end, preferred)
        if cell is not None:
            grouped.setdefault(cell[0], []).append((index, cell[1], cell[2], preferred or ""))
    for window, group in grouped.items():
        proposals = torch.tensor([[(window, start, end) for _, start, end, _ in group]],
                                 dtype=torch.long, device=shared.token_states.device)
        mask = torch.ones((1, len(group)), dtype=torch.bool, device=proposals.device)
        scored = core.canonical_span(backbone.layer(8), shared.token_states,
                                     proposals, mask, batch.source_token_mask)
        for position, (index, _start, _end, _preferred) in enumerate(group):
            output[index] = (scored.semantic_logits[0, position],
                             scored.boundary_logits[0, position])
    return tuple(output)


@dataclass(frozen=True, slots=True)
class NativeCellGeometry:
    """One source-only native cell, bound to the exact query that produced it."""

    kind: str
    layout_id: int
    start: int
    end: int
    preferred_window_id: str | None
    cell: tuple[int, int, int, object, object] | None
    geometry: tuple[float, float, float, float] | None


def native_cell_geometry(kind: str, layout: SourceLayout, start: int, end: int,
                         preferred_window_id: str | None) -> NativeCellGeometry:
    if kind not in ("ENTITY", "TIME"):
        raise ValueError("native geometry belongs to Entity or Time")
    token_limit, char_limit = (20, 56) if kind == "ENTITY" else (21, 44)
    cell = sentence_cell(layout, start, end, preferred_window_id)
    if cell is None or cell[2] - cell[1] > token_limit or end - start > char_limit:
        return NativeCellGeometry(kind, id(layout), start, end,
                                  preferred_window_id, None, None)
    _, first_position, last_exclusive, first, last = cell
    geometry = ((start - first.start) / max(first.end - first.start, 1),
                (end - last.start) / max(last.end - last.start, 1),
                (end - start) / char_limit,
                (last_exclusive - first_position) / token_limit)
    return NativeCellGeometry(kind, id(layout), start, end,
                              preferred_window_id, cell, geometry)


def native_states(*, kind: str, layout: SourceLayout, batch, backbone,
                  shared: SharedForwardLease, core: V3Core,
                  rows: Sequence[tuple[int, int, str | None]],
                  fallback_states: torch.Tensor,
                  fallback_geometry: torch.Tensor,
                  sentence_cache=None,
                  prepared: Sequence[NativeCellGeometry] | None = None,
                  ) -> tuple[torch.Tensor, torch.Tensor, tuple[bool, ...]]:
    """Use the v2.3 direct candidate encoder and 4-scalar boundary features locally."""
    if kind not in ("ENTITY", "TIME") or fallback_states.shape[0] != len(rows):
        raise ValueError("native span rows differ")
    if prepared is not None and len(prepared) != len(rows):
        raise ValueError("native geometry carrier row count differs")
    local = []
    cells = []
    geometry = []
    for index, (start, end, preferred) in enumerate(rows):
        carrier = (native_cell_geometry(kind, layout, start, end, preferred)
                   if prepared is None else prepared[index])
        if (carrier.kind, carrier.layout_id, carrier.start, carrier.end,
                carrier.preferred_window_id) != (kind, id(layout), start, end, preferred):
            raise ValueError("native geometry carrier source lineage differs")
        cell = carrier.cell
        if cell is None:
            continue
        window, first_position, last_exclusive, _first, _last = cell
        local.append(index)
        cells.append((window, first_position, last_exclusive))
        geometry.append(carrier.geometry)
    if not local:
        return fallback_states, fallback_geometry, tuple(False for _ in rows)
    device = fallback_states.device
    candidates = SimpleNamespace(
        span_indices=torch.tensor([cells], dtype=torch.long, device=device),
        span_kind_ids=torch.full((1, len(cells)), SPAN_KINDS.index(kind),
                                 dtype=torch.long, device=device),
        span_mask=torch.ones((1, len(cells)), dtype=torch.bool, device=device))
    scored = core.candidate_span.forward_runtime_direct_states(
        backbone, shared.sentence_states, candidates, batch.source_token_mask,
        sentence_cache=sentence_cache)[0]
    native_geometry = torch.tensor(geometry, dtype=fallback_geometry.dtype, device=device)
    if device.type == "mps":
        # MPS does not implement index_copy.out; indexed assignment copies the
        # identical selected rows without changing their values or ordering.
        states = fallback_states.clone()
        features = fallback_geometry.clone()
        states[local] = scored
        features[local] = native_geometry
    else:
        index = torch.tensor(local, device=device)
        states = fallback_states.index_copy(0, index, scored)
        features = fallback_geometry.index_copy(0, index, native_geometry)
    local_indices = set(local)
    used = tuple(index in local_indices for index in range(len(rows)))
    return states, features, used
