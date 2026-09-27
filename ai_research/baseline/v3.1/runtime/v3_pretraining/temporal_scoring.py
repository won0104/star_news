"""Event/Time exact feature의 요청 범위 lease와 Gold 없는 attachment 점수화."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice, product
import math
from typing import Mapping, Sequence, TYPE_CHECKING

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.exact_span import ExactSpanFeatures
from models.v3_pretraining.pair_context import original_sentence_states
from runtime.v3_pretraining.exact_feature_cache import (DirectExactFeatureHandoff,
                                                        RequestExactFeatureCache,
                                                        exact_source_features)
from runtime.v3_pretraining.source_layout import SourceLayout, SpanAlignment

if TYPE_CHECKING:
    from runtime.v3_pretraining.pair_routing import RoutedPairs


class EventTimeFeatureLease:
    """동일 요청의 Event/Time 표현; 마지막 consumer가 닫아 참조를 해제한다."""

    def __init__(self, *, article_version_id: str, content_sha256: str,
                 event_ids: tuple[str, ...],
                 time_ids: tuple[str, ...], event_spans: tuple[tuple[int, int], ...],
                 time_spans: tuple[tuple[int, int], ...], event_states: torch.Tensor,
                 time_states: torch.Tensor, document_state: torch.Tensor,
                 original_sentence_states: torch.Tensor,
                 original_sentence_spans: tuple[tuple[int, int], ...],
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
        self.original_sentence_states: torch.Tensor | None = original_sentence_states
        self.original_sentence_spans = original_sentence_spans
        self.extra_states: dict[str, torch.Tensor] | None = extra_states or {}
        self.extra_residuals: dict[str, torch.Tensor] | None = None
        self.extra_link_logits: dict[str, torch.Tensor] | None = None
        self.source_mode = source_mode
        self.closed = False

    def close(self) -> None:
        self.event_states = None
        self.time_states = None
        self.document_state = None
        self.original_sentence_states = None
        self.original_sentence_spans = ()
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
                               source_mode: str,
                               exact_feature_cache: RequestExactFeatureCache | None = None,
                               direct_features: Mapping[tuple[str, int, int],
                                                        DirectExactFeatureHandoff] | None = None,
                               ) -> EventTimeFeatureLease:
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
    if direct_features and exact_feature_cache is None:
        raise ValueError("direct Event-Time features need their request cache owner")
    if rows:
        direct = {}
        missing = []
        missing_positions = []
        for index, (alignment, kind) in enumerate(rows):
            handoff = (direct_features or {}).get((kind, alignment.start, alignment.end))
            if handoff is None:
                missing.append((alignment, kind))
                missing_positions.append(index)
                continue
            if (exact_feature_cache.closed or
                    handoff.request_token is not exact_feature_cache.request_token or
                    handoff.kind != kind or handoff.alignment != alignment):
                raise ValueError("Event-Time direct feature lineage differs")
            feature = handoff.feature
            direct[index] = (feature.state, feature.residual,
                             feature.link_logit, feature.local)
        if not direct:
            features = exact_source_features(
                layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
                rows=rows, cache=exact_feature_cache)
        else:
            fresh = (exact_source_features(
                layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
                rows=missing, cache=exact_feature_cache) if missing else None)
            for position, index in enumerate(missing_positions):
                direct[index] = (fresh.states[position], fresh.residuals[position],
                                 fresh.link_logits[position], fresh.local_mask[position])
            ordered = [direct[index] for index in range(len(rows))]
            features = ExactSpanFeatures(
                torch.stack([row[0] for row in ordered]),
                torch.stack([row[1] for row in ordered]),
                torch.stack([row[2] for row in ordered]),
                tuple(row[3] for row in ordered))
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
        original_sentence_states=original_sentence_states(layout, shared.sentence_states[0]),
        original_sentence_spans=layout.sentence_spans,
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
    attached_pair_logits: tuple[tuple[str, str, float], ...] = ()


@torch.no_grad()
def score_event_time(lease: EventTimeFeatureLease, *, core: V3Core,
                     content_length: int,
                     config: EventTimeDecodeConfig = EventTimeDecodeConfig(),
                     routed_pairs: RoutedPairs | None = None) -> EventTimeDecodeResult:
    """co-occurrence를 edge로 간주하지 않고 directed learned logit만 소비한다."""
    if lease.closed or lease.event_states is None or lease.time_states is None or lease.document_state is None:
        raise RuntimeError("Event-Time scorer needs live features")
    if lease.source_mode != "PREDICTED":
        raise ValueError("runtime attachment scorer cannot consume Gold oracle features")
    eligible_count = len(lease.event_ids) * len(lease.time_ids)
    selected = (tuple(islice(product(range(len(lease.event_ids)),
                                    range(len(lease.time_ids))), config.max_pairs))
                if routed_pairs is None else routed_pairs.pairs)
    if routed_pairs is not None:
        from runtime.v3_pretraining.pair_routing import inventory_lineage_values
        lineage = inventory_lineage_values(
            lease.article_version_id, lease.content_sha256,
            tuple((key, *span) for key, span in zip(lease.event_ids, lease.event_spans)) +
            tuple((key, *span) for key, span in zip(lease.time_ids, lease.time_spans)))
        if (routed_pairs.policy_id != "BCR_A_TIME_OCCURRENCE_R1_K80" or
                routed_pairs.source_inventory_lineage != lineage or
                any(not 0 <= a < len(lease.event_ids) or
                    not 0 <= b < len(lease.time_ids) or
                    record["query_id"] != lease.event_ids[a] or
                    record["candidate_id"] != lease.time_ids[b]
                    for (a, b), record in zip(selected, routed_pairs.records))):
            raise ValueError("Event-Time routed fine input differs from source lease")
    accepted = []
    accepted_logits = []
    for start in range(0, len(selected), config.chunk_size):
        chunk = selected[start:start + config.chunk_size]
        indices = torch.tensor(chunk, dtype=torch.long, device=lease.event_states.device)
        logits = core.task_modules["event_time"](
            lease.event_states, lease.time_states, indices, lease.document_state,
            event_time_geometry(lease, chunk, content_length=content_length))
        score_rows = logits.detach().cpu().tolist()
        if any(not math.isfinite(logit) for logit in score_rows):
            raise ValueError("Event-Time scorer returned non-finite logits")
        for (a, b), logit in zip(chunk, score_rows):
            if logit >= config.score_threshold:
                pair = lease.event_ids[a], lease.time_ids[b]
                accepted.append(pair)
                accepted_logits.append((*pair, float(logit)))
    return EventTimeDecodeResult(tuple(accepted), len(selected), eligible_count,
                                 len(selected) < eligible_count, config.status,
                                 tuple(accepted_logits))
