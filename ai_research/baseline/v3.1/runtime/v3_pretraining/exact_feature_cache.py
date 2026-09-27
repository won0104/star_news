"""Request-local reuse of identical exact-source span features.

Exact bridge outputs and accepted native Entity/Time states have separate keys. A
native state enters the bridge only when producer, kind, routed layer, window,
token cell and exact source coordinate all agree. Rows are released after the
Event-Time feature handoff.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Sequence

import torch

from models.v3_pretraining.exact_span import ExactSpanFeatures
from runtime.v3_pretraining.source_layout import SpanAlignment


@dataclass(frozen=True, slots=True)
class _FeatureRow:
    state: torch.Tensor
    residual: torch.Tensor
    link_logit: torch.Tensor
    local: bool


@dataclass(frozen=True, slots=True)
class DirectExactFeatureHandoff:
    """A complete exact producer row scoped to one live request and kind."""

    request_token: object
    kind: str
    alignment: SpanAlignment
    feature: _FeatureRow


@dataclass(frozen=True, slots=True)
class NativeEntityStateRow:
    window_row: int
    token_start: int
    token_end: int
    start: int
    end: int
    score: float
    state_position: int


class RequestExactFeatureCache:
    """Reuse bridge rows within one live request, with a per-kind memory bound."""

    def __init__(self, *, layout, batch, backbone, shared, core,
                 max_rows_per_kind: int = 256,
                 max_native_rows: int = 16384) -> None:
        if (max_rows_per_kind <= 0 or max_native_rows <= 0 or shared.closed or
                getattr(core, "training", False)):
            raise ValueError("exact feature cache needs eval mode, a live request and positive bound")
        self._identity = (id(layout), id(batch), id(backbone),
                          id(shared.token_states), id(shared.sentence_states),
                          id(shared.document_state), id(core.exact_source_span),
                          id(core.candidate_span))
        self.request_token = object()
        self.max_rows_per_kind = max_rows_per_kind
        self.max_native_rows = max_native_rows
        self._rows: dict[str, OrderedDict[tuple[object, ...], _FeatureRow]] = {}
        self._native_rows: OrderedDict[tuple[object, ...], tuple[float, torch.Tensor]] = OrderedDict()
        self._sentence_cache = None
        self.closed = False

    def _check_request(self, *, layout, batch, backbone, shared, core) -> None:
        if self.closed or shared.closed or self._identity != (
                id(layout), id(batch), id(backbone), id(shared.token_states),
                id(shared.sentence_states), id(shared.document_state),
                id(core.exact_source_span), id(core.candidate_span)):
            raise ValueError("exact feature cache belongs to another request or producer")

    def sentence_cache(self, *, layout, batch, backbone, shared, core):
        """Share candidate-independent attention logits within the live request."""
        self._check_request(layout=layout, batch=batch, backbone=backbone,
                            shared=shared, core=core)
        factory = getattr(core.candidate_span, "new_runtime_sentence_cache", None)
        if factory is not None and self._sentence_cache is None:
            self._sentence_cache = factory(backbone, shared.sentence_states,
                                           batch.source_token_mask)
        return self._sentence_cache

    @staticmethod
    def _native_key(kind: str, layer: int, window_row: int,
                    token_start: int, token_end: int,
                    start: int, end: int) -> tuple[object, ...]:
        return ("CANDIDATE_SPAN_RUNTIME_DIRECT_V1", kind, layer, window_row,
                token_start, token_end, start, end)

    def remember_native_states(self, *, kind: str, layout, batch, backbone,
                               shared, core, rows: Sequence[NativeEntityStateRow],
                               states: torch.Tensor) -> None:
        """Retain accepted native Entity/Time states with their producer lineage."""
        self._check_request(layout=layout, batch=batch, backbone=backbone,
                            shared=shared, core=core)
        if kind not in ("ENTITY", "TIME"):
            raise ValueError("only native Entity/Time states can enter the exact bridge")
        if not rows:
            return
        if states.ndim != 2 or any(not 0 <= row.state_position < len(states) for row in rows):
            raise ValueError("native state rows differ from the scored chunk")
        layer = core.candidate_span.layer_policy.for_span_kind(kind)
        positions = torch.tensor([row.state_position for row in rows],
                                 dtype=torch.long, device=states.device)
        packed = states.index_select(0, positions).detach().to("cpu").clone()
        for position, row in enumerate(rows):
            key = self._native_key(kind, layer, row.window_row,
                                   row.token_start, row.token_end, row.start, row.end)
            old = self._native_rows.get(key)
            if old is None or row.score > old[0]:
                self._native_rows[key] = (row.score, packed[position])
            self._native_rows.move_to_end(key)
            if len(self._native_rows) > self.max_native_rows:
                self._native_rows.popitem(last=False)

    def remember_native_entities(self, *, layout, batch, backbone, shared, core,
                                 rows: Sequence[NativeEntityStateRow],
                                 states: torch.Tensor) -> None:
        self.remember_native_states(
            kind="ENTITY", layout=layout, batch=batch, backbone=backbone,
            shared=shared, core=core, rows=rows, states=states)

    def retain_native_coordinates(self, kind: str,
                                  coordinates: set[tuple[int, int]]) -> None:
        """Drop threshold-surviving rows that did not survive source acceptance."""
        if self.closed or kind not in ("ENTITY", "TIME"):
            raise ValueError("native state cache is closed")
        for key in tuple(self._native_rows):
            if key[1] == kind and (key[6], key[7]) not in coordinates:
                del self._native_rows[key]

    def retain_native_entity_coordinates(self, coordinates: set[tuple[int, int]]) -> None:
        self.retain_native_coordinates("ENTITY", coordinates)

    def _lookup_native(self, kind: str, window_row: int, token_start: int,
                       token_end: int, alignment: SpanAlignment, *, core, shared):
        if kind not in ("ENTITY", "TIME") or alignment.canonical_window_id is None:
            return None
        if (alignment.start_ref.window_id != alignment.canonical_window_id or
                alignment.end_ref.window_id != alignment.canonical_window_id):
            return None
        layer = core.candidate_span.layer_policy.for_span_kind(kind)
        key = self._native_key(kind, layer, window_row, token_start, token_end,
                               alignment.start, alignment.end)
        hit = self._native_rows.get(key)
        return None if hit is None else hit[1].to(shared.sentence_states.device)

    @staticmethod
    def _key(alignment: SpanAlignment, kind: str) -> tuple[object, ...]:
        return (kind, alignment.start, alignment.end,
                alignment.start_ref, alignment.end_ref,
                alignment.canonical_window_id)

    def direct_handoff(self, *, layout, batch, backbone, shared, core,
                       alignment: SpanAlignment, kind: str
                       ) -> DirectExactFeatureHandoff | None:
        """Export an already produced complete exact row without recomputing it."""
        self._check_request(layout=layout, batch=batch, backbone=backbone,
                            shared=shared, core=core)
        row = self._rows.get(kind, {}).get(self._key(alignment, kind))
        return (None if row is None else
                DirectExactFeatureHandoff(self.request_token, kind, alignment, row))

    def encode(self, *, layout, batch, backbone, shared, core,
               rows: Sequence[tuple[SpanAlignment, str]]) -> ExactSpanFeatures:
        self._check_request(layout=layout, batch=batch, backbone=backbone,
                            shared=shared, core=core)
        keys = [self._key(alignment, kind) for alignment, kind in rows]
        for alignment, _kind in rows:
            if layout.reconstruct(alignment) != (alignment.start, alignment.end,
                                                  alignment.text):
                raise ValueError("cached exact source coordinate changed")
        cached: dict[tuple[object, ...], _FeatureRow] = {}
        missing: dict[tuple[object, ...], tuple[SpanAlignment, str]] = {}
        for key, row in zip(keys, rows):
            bucket = self._rows.setdefault(row[1], OrderedDict())
            hit = bucket.get(key)
            if hit is None:
                missing.setdefault(key, row)
            else:
                cached[key] = hit
                bucket.move_to_end(key)
        fresh = None
        if missing:
            fresh = core.exact_source_span(
                layout=layout, batch=batch, backbone=backbone,
                token_states=shared.token_states,
                sentence_states=shared.sentence_states,
                document_state=shared.document_state,
                candidate_encoder=core.candidate_span,
                rows=tuple(missing.values()),
                runtime_sentence_cache=self.sentence_cache(
                    layout=layout, batch=batch, backbone=backbone, shared=shared, core=core),
                native_state_lookup=lambda kind, window, first, last, alignment:
                    self._lookup_native(kind, window, first, last, alignment,
                                        core=core, shared=shared))
            for index, key in enumerate(missing):
                row = _FeatureRow(fresh.states[index], fresh.residuals[index],
                                  fresh.link_logits[index], fresh.local_mask[index])
                cached[key] = row
                bucket = self._rows[key[0]]
                # Clone each retained row so one entry cannot pin a large
                # producer chunk until the request's Event-Time boundary.
                bucket[key] = _FeatureRow(row.state.detach().clone(),
                                          row.residual.detach().clone(),
                                          row.link_logit.detach().clone(), row.local)
                bucket.move_to_end(key)
                if len(bucket) > self.max_rows_per_kind:
                    bucket.popitem(last=False)
        if fresh is not None and len(missing) == len(rows) and len(set(keys)) == len(rows):
            return fresh
        if not rows:
            return core.exact_source_span(
                layout=layout, batch=batch, backbone=backbone,
                token_states=shared.token_states,
                sentence_states=shared.sentence_states,
                document_state=shared.document_state,
                candidate_encoder=core.candidate_span, rows=())
        ordered = [cached[key] for key in keys]
        return ExactSpanFeatures(
            torch.stack([row.state for row in ordered]),
            torch.stack([row.residual for row in ordered]),
            torch.stack([row.link_logit for row in ordered]),
            tuple(row.local for row in ordered))

    def close(self) -> None:
        self._rows.clear()
        self._native_rows.clear()
        if self._sentence_cache is not None:
            self._sentence_cache.close()
            self._sentence_cache = None
        self.closed = True


def exact_source_features(*, layout, batch, backbone, shared, core, rows,
                          cache: RequestExactFeatureCache | None = None
                          ) -> ExactSpanFeatures:
    """Use the bridge's exact producer, reusing only request-identical rows."""
    if cache is not None:
        return cache.encode(layout=layout, batch=batch, backbone=backbone,
                            shared=shared, core=core, rows=rows)
    return core.exact_source_span(
        layout=layout, batch=batch, backbone=backbone,
        token_states=shared.token_states, sentence_states=shared.sentence_states,
        document_state=shared.document_state,
        candidate_encoder=core.candidate_span, rows=rows)
