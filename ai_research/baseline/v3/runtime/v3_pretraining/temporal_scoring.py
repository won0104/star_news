"""Event/Time exact feature의 요청 범위 lease와 Gold 없는 attachment 점수화."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Sequence

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from runtime.v3_pretraining.source_layout import SourceLayout, SpanAlignment


class EventTimeFeatureLease:
    """동일 요청의 Event/Time 표현; 마지막 consumer가 닫아 참조를 해제한다."""

    def __init__(self, *, article_version_id: str, content_sha256: str,
                 event_ids: tuple[str, ...],
                 time_ids: tuple[str, ...], event_spans: tuple[tuple[int, int], ...],
                 time_spans: tuple[tuple[int, int], ...], event_states: torch.Tensor,
                 time_states: torch.Tensor, document_state: torch.Tensor,
                 source_mode: str, extra_states: dict[str, torch.Tensor] | None = None) -> None:
        if source_mode not in ("GOLD_ORACLE", "PREDICTED"):
            raise ValueError("unknown Event-Time feature provenance")
        if len(set(event_ids)) != len(event_ids) or len(set(time_ids)) != len(time_ids):
            raise ValueError("duplicate Event/Time feature ID")
        if event_states.shape[0] != len(event_ids) or time_states.shape[0] != len(time_ids):
            raise ValueError("Event/Time feature rows differ from IDs")
        self.article_version_id = article_version_id
        self.content_sha256 = content_sha256
        self.event_ids = event_ids
        self.time_ids = time_ids
        self.event_spans = event_spans
        self.time_spans = time_spans
        self.event_states: torch.Tensor | None = event_states
        self.time_states: torch.Tensor | None = time_states
        self.document_state: torch.Tensor | None = document_state
        self.extra_states: dict[str, torch.Tensor] | None = extra_states or {}
        self.extra_residuals: dict[str, torch.Tensor] | None = None
        self.extra_link_logits: dict[str, torch.Tensor] | None = None
        self.source_mode = source_mode
        self.closed = False

    def close(self) -> None:
        self.event_states = None
        self.time_states = None
        self.document_state = None
        self.extra_states = None
        self.extra_residuals = None
        self.extra_link_logits = None
        self.closed = True

    def __enter__(self) -> "EventTimeFeatureLease":
        if self.closed:
            raise RuntimeError("Event-Time feature lease already closed")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def encode_event_time_features(*, layout: SourceLayout, batch: ArticleBatch,
                               backbone: BackboneOutput, shared: SharedForwardLease,
                               core: V3Core,
                               events: Sequence[tuple[str, SpanAlignment]],
                               times: Sequence[tuple[str, SpanAlignment]],
                               extra_rows: Sequence[tuple[str, SpanAlignment, str]] = (),
                               source_mode: str) -> EventTimeFeatureLease:
    if shared.closed or shared.token_states is None or shared.sentence_states is None or shared.document_state is None:
        raise RuntimeError("Event-Time encoding needs a live shared DCE lease")
    if layout.article.content != batch.contents[0] or len(layout.windows) != batch.input_ids.shape[1]:
        raise ValueError("Event-Time feature source differs from backbone input")
    if len({name for name, _, _ in extra_rows}) != len(extra_rows):
        raise ValueError("duplicate transient Event feature ID")
    rows = ([(alignment, "EVENT") for _, alignment in events] +
            [(alignment, "TIME") for _, alignment in times] +
            [(alignment, kind) for _, alignment, kind in extra_rows])
    for alignment, _ in rows:
        if layout.reconstruct(alignment) != (alignment.start, alignment.end, alignment.text):
            raise ValueError("Event-Time feature source span changed")
    if rows:
        features = core.exact_source_span(
            layout=layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state, candidate_encoder=core.candidate_span,
            rows=rows)
        encoded = features.states
    else:
        encoded = shared.document_state.new_empty((0, shared.document_state.shape[-1]))
        features = None
    lease = EventTimeFeatureLease(
        article_version_id=layout.article.article_version_id,
        content_sha256=layout.article.content_sha256,
        event_ids=tuple(eid for eid, _ in events), time_ids=tuple(tid for tid, _ in times),
        event_spans=tuple((alignment.start, alignment.end) for _, alignment in events),
        time_spans=tuple((alignment.start, alignment.end) for _, alignment in times),
        event_states=encoded[:len(events)],
        time_states=encoded[len(events):len(events) + len(times)],
        document_state=shared.document_state[0], source_mode=source_mode,
        extra_states={name: encoded[len(events) + len(times) + index]
                      for index, (name, _, _) in enumerate(extra_rows)})
    offset = len(events) + len(times)
    lease.extra_residuals = {name: features.residuals[offset + index]
                             for index, (name, _, _) in enumerate(extra_rows)} if features is not None else {}
    lease.extra_link_logits = {name: features.link_logits[offset + index]
                               for index, (name, _, _) in enumerate(extra_rows)} if features is not None else {}
    return lease


def event_time_geometry(lease: EventTimeFeatureLease,
                        pairs: Sequence[tuple[int, int]], *, content_length: int) -> torch.Tensor:
    if lease.closed or lease.event_states is None or content_length <= 0:
        raise RuntimeError("Event-Time geometry needs a live feature lease")
    return lease.event_states.new_tensor([
        (min(abs(lease.event_spans[a][0] - lease.time_spans[b][0]) / content_length, 1.0),
         float(lease.time_spans[b][0] >= lease.event_spans[a][1]),
         float(lease.time_spans[b][1] <= lease.event_spans[a][0]),
         float(lease.event_spans[a][0] <= lease.time_spans[b][0] and
               lease.time_spans[b][1] <= lease.event_spans[a][1]))
        for a, b in pairs])


@dataclass(frozen=True, slots=True)
class EventTimeDecodeConfig:
    max_pairs: int = 4096
    chunk_size: int = 128
    score_threshold: float = 0.0
    status: str = "PROVISIONAL_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        if self.max_pairs <= 0 or self.chunk_size <= 0:
            raise ValueError("Event-Time decoder budget must be positive")


@dataclass(frozen=True, slots=True)
class EventTimeDecodeResult:
    attached_pairs: tuple[tuple[str, str], ...]
    scored_pairs: int
    eligible_pairs: int
    partial: bool
    policy_status: str


@torch.no_grad()
def score_event_time(lease: EventTimeFeatureLease, *, core: V3Core,
                     content_length: int,
                     config: EventTimeDecodeConfig = EventTimeDecodeConfig()) -> EventTimeDecodeResult:
    """co-occurrence를 edge로 간주하지 않고 directed learned logit만 소비한다."""
    if lease.closed or lease.event_states is None or lease.time_states is None or lease.document_state is None:
        raise RuntimeError("Event-Time scorer needs live features")
    if lease.source_mode != "PREDICTED":
        raise ValueError("runtime attachment scorer cannot consume Gold oracle features")
    pairs = tuple(product(range(len(lease.event_ids)), range(len(lease.time_ids))))
    selected = pairs[:config.max_pairs]
    accepted = []
    for start in range(0, len(selected), config.chunk_size):
        chunk = selected[start:start + config.chunk_size]
        indices = torch.tensor(chunk, dtype=torch.long, device=lease.event_states.device)
        logits = core.task_modules["event_time"](
            lease.event_states, lease.time_states, indices, lease.document_state,
            event_time_geometry(lease, chunk, content_length=content_length))
        if not torch.isfinite(logits).all():
            raise ValueError("Event-Time scorer returned non-finite logits")
        accepted.extend((lease.event_ids[a], lease.time_ids[b]) for (a, b), logit in zip(chunk, logits)
                        if float(logit) >= config.score_threshold)
    return EventTimeDecodeResult(tuple(accepted), len(selected), len(pairs),
                                 len(selected) < len(pairs), config.status)
