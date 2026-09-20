"""Generic TimeExpression discovery, Event attachment, and safe normalization.

The neural lanes consume article text only.  ``published_at`` is intentionally
visible only to :class:`ArticleRelativeTimeNormalizer`, the deterministic stage-⑧
derivation.  Raw evidence survives every unresolved normalization or attachment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import calendar
import re
import time
from types import SimpleNamespace

import torch

from models.contracts import PairIndexBatch, SPAN_KINDS
from ..candidate_routing.temporal import TemporalBoundedContract, TemporalBoundedSession
from ..candidate_routing.span_budget import Lane, selected_boundaries, token_pairs
from ..candidate_routing.time_span_budget import (
    TimeChunkProjectionReuse, TimeProjectionIdentity, TimeSpanBoundedContract,
)
from .candidate_iteration import (
    iter_bounded_span_candidates, iter_candidate_chunks, iter_span_candidates,
)
from ..lifecycle import StageScope


def enumerate_time_candidates(
    prepared,
    *,
    max_token_width: int,
    max_character_width: int,
    character_boundaries: bool,
):
    """Enumerate a deterministic sentence-local contiguous span universe."""

    return [
        {**row, "text": prepared.article.content[row["char_start"]:row["char_end"]]}
        for row in iter_span_candidates(
            prepared, max_token_width=max_token_width,
            max_character_width=max_character_width,
            character_boundaries=character_boundaries,
        )
    ]


def pack_time_candidates(rows, device):
    indices = [
        [row["sentence_index"], row["token_start"], row["token_end"]]
        for row in rows
    ]
    return (
        SimpleNamespace(
            span_indices=torch.tensor(indices, dtype=torch.long, device=device).reshape(1, -1, 3),
            span_kind_ids=torch.full(
                (1, len(rows)), SPAN_KINDS.index("TIME"), dtype=torch.long, device=device
            ),
            span_mask=torch.ones(1, len(rows), dtype=torch.bool, device=device),
        ),
        torch.tensor(
            [[row["boundary_features"] for row in rows]],
            dtype=torch.float32,
            device=device,
        ).reshape(1, len(rows), 4),
    )


def time_prediction_id(article_id: str, char_start: int, char_end: int) -> str:
    material = f"{article_id}|{char_start}|{char_end}|TIME_EXPRESSION".encode("utf-8")
    return "TIM-" + sha256(material).hexdigest()[:20]


def event_time_attachment_id(event_prediction_id: str, time_prediction_id_: str) -> str:
    material = f"{event_prediction_id}|{time_prediction_id_}|EVENT_TIME".encode("utf-8")
    return "ETA-" + sha256(material).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    status: str
    value: str | None
    granularity: str | None
    reference_published_at: str | None
    timezone: str | None
    rule: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "value": self.value,
            "granularity": self.granularity,
            "reference_published_at": self.reference_published_at,
            "timezone": self.timezone,
            "rule": self.rule,
            "responsibility": "⑧ 그래프 조립부",
        }


class ArticleRelativeTimeNormalizer:
    """Resolve only rule-clear calendar expressions from text and publishedAt."""

    _DAY_OFFSETS = {"그제": -2, "어제": -1, "오늘": 0, "내일": 1, "모레": 2, "이날": 0}
    _YEAR_OFFSETS = {"작년": -1, "지난해": -1, "올해": 0, "내년": 1}
    _DURATION = re.compile(r"(?:동안|간|주기|째|이내|이상|이하)$")
    _SET = re.compile(r"(?:매일|매주|매월|매년|마다|정기적으로)")

    def normalize(self, text: str, published_at: str | None) -> NormalizationResult:
        raw = text.strip()
        if self._DURATION.search(raw) or self._SET.search(raw):
            return NormalizationResult("UNRESOLVED", None, None, None, None, "DURATION_OR_SET_NOT_MATERIALIZED")
        absolute = re.fullmatch(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", raw)
        if absolute:
            try:
                value = datetime(*map(int, absolute.groups())).date().isoformat()
            except ValueError:
                return NormalizationResult("UNRESOLVED", None, None, None, None, "INVALID_ABSOLUTE_DATE")
            return NormalizationResult("NORMALIZED", value, "DAY", None, None, "ABSOLUTE_YMD")
        year_month = re.fullmatch(r"(\d{4})년\s*(\d{1,2})월(?:\s*당시)?", raw)
        if year_month:
            year_value, month_value = map(int, year_month.groups())
            if not 1 <= month_value <= 12:
                return NormalizationResult(
                    "UNRESOLVED", None, None, None, None, "INVALID_ABSOLUTE_YEAR_MONTH"
                )
            return NormalizationResult(
                "NORMALIZED",
                f"{year_value:04d}-{month_value:02d}",
                "MONTH",
                None,
                None,
                "ABSOLUTE_YEAR_MONTH",
            )
        year = re.fullmatch(r"(\d{4})년", raw)
        if year:
            return NormalizationResult("NORMALIZED", year.group(1), "YEAR", None, None, "ABSOLUTE_YEAR")
        if published_at is None:
            return NormalizationResult("UNRESOLVED", None, None, None, None, "REFERENCE_REQUIRED_OR_UNSUPPORTED")
        try:
            anchor = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return NormalizationResult("UNRESOLVED", None, None, published_at, None, "INVALID_PUBLISHED_AT")
        timezone = anchor.tzname()
        for word, offset in self._DAY_OFFSETS.items():
            if raw == word or raw.startswith(word + " "):
                return NormalizationResult(
                    "NORMALIZED",
                    (anchor + timedelta(days=offset)).date().isoformat(),
                    "DAY",
                    published_at,
                    timezone,
                    "ARTICLE_RELATIVE_DAY",
                )
        for word, offset in self._YEAR_OFFSETS.items():
            if raw == word or raw.startswith(word + " "):
                return NormalizationResult(
                    "NORMALIZED",
                    f"{anchor.year + offset:04d}",
                    "YEAR",
                    published_at,
                    timezone,
                    "ARTICLE_RELATIVE_YEAR",
                )
        next_year_month = re.fullmatch(r"이듬해\s*(\d{1,2})월", raw)
        if next_year_month:
            month_value = int(next_year_month.group(1))
            if 1 <= month_value <= 12:
                return NormalizationResult(
                    "NORMALIZED",
                    f"{anchor.year + 1:04d}-{month_value:02d}",
                    "MONTH",
                    published_at,
                    timezone,
                    "ARTICLE_RELATIVE_NEXT_YEAR_MONTH",
                )
        upcoming = re.fullmatch(r"오는\s*(\d{1,2})일", raw)
        if upcoming:
            day = int(upcoming.group(1))
            year, month = anchor.year, anchor.month
            if day <= anchor.day:
                month += 1
                if month == 13:
                    year, month = year + 1, 1
            if day <= calendar.monthrange(year, month)[1]:
                return NormalizationResult(
                    "NORMALIZED",
                    f"{year:04d}-{month:02d}-{day:02d}",
                    "DAY",
                    published_at,
                    timezone,
                    "ARTICLE_RELATIVE_UPCOMING_DAY",
                )
        return NormalizationResult("UNRESOLVED", None, None, None, None, "UNSUPPORTED_OR_CONTEXT_DEPENDENT")


class FixedTimeExpressionRuntime:
    """Inference-only stage ③ generic TimeExpression extractor."""

    def __init__(self, model, config, checkpoint_sha):
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha

    def _score_chunk(self, prepared, backbone, batch, context, chunk, threshold,
                     device, diagnostic_sink=None,
                     projection_identity: TimeProjectionIdentity | None = None):
        """문장 순서의 batch tensor를 scorer 종료 때 닫고 승인 근거만 반환한다."""

        accepted = []
        hits = misses = 0
        with StageScope() as stage:
            packed, boundary = pack_time_candidates(chunk, device)
            stage.own(packed)
            stage.own(boundary)
            if projection_identity is None:
                logits = stage.own(self.model.forward_candidates(
                    batch, backbone, context, packed, boundary
                )[0, :, 0])
            else:
                cache = TimeChunkProjectionReuse(projection_identity)
                try:
                    unique, row_indices, hits, misses = cache.select_rows(
                        chunk, projection_identity
                    )
                    unique_packed, _ = pack_time_candidates(unique, device)
                    stage.own(unique_packed)
                    projected = stage.own(
                        self.model.candidate_span_encoder.forward_runtime_direct(
                            backbone, context, unique_packed, batch.source_token_mask
                        )[0]
                    )
                    lookup = stage.own(torch.tensor(row_indices, dtype=torch.long,
                                                    device=device))
                    states = stage.own(projected.index_select(0, lookup))
                    logits = stage.own(self.model.head(
                        states.unsqueeze(0), boundary, packed.span_mask
                    )[0, :, 0])
                finally:
                    cache.close()
            scores = torch.sigmoid(logits).detach().cpu().tolist()
            for row, score in zip(chunk, scores):
                if diagnostic_sink is not None and diagnostic_sink.level.value == "FULL":
                    diagnostic_sink.record("candidate", {
                        "component": "time_expressions",
                        "article_version_id": prepared.article.article_version_id,
                        "sentence_index": row["sentence_index"],
                        "char_start": row["char_start"],
                        "char_end": row["char_end"],
                        "score": float(score),
                    })
                if score < threshold:
                    continue
                accepted.append({
                    "prediction_id": time_prediction_id(
                        prepared.article.article_id, row["char_start"], row["char_end"],
                    ),
                    "article_id": prepared.article.article_id,
                    "sentence_id": row["sentence_id"],
                    "sentence_index": row["sentence_index"],
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "token_start": row["token_start"],
                    "token_end": row["token_end"],
                    "text": prepared.grounding_text(
                        row["char_start"], row["char_end"], row["sentence_index"],
                    ),
                    "score": float(score),
                    "source": "PREDICTED_GENERIC_TIME_EXPRESSION",
                    "checkpoint_sha": self.checkpoint_sha,
                    "runtime_config_id": self.config["runtime_config_id"],
                    "representation_layer": 10,
                    "responsibility": "③ 구간 추출부",
                    "provenance": {
                        "architecture": "SPAN_NATIVE_BINARY_TIME_EXPRESSION",
                        "neural_subtype": None,
                        "published_at_used_for_extraction": False,
                    },
                })
        return accepted, hits, misses

    @torch.inference_mode()
    def run(self, prepared, backbone, *, diagnostic_sink=None,
            routing_observer=None,
            bounded_policy: TimeSpanBoundedContract | None = None):
        started = time.perf_counter()
        if bounded_policy is not None:
            if not isinstance(bounded_policy, TimeSpanBoundedContract):
                raise TypeError("Time span bounded path needs pinned T16/C8 contract")
            bounded_policy.validate()
            if (self.checkpoint_sha != bounded_policy.fine_checkpoint_sha256
                or int(self.config["max_span_width_tokens"]) != 21
                or int(self.config["max_span_width_characters"]) != 44
                or int(self.config["candidate_chunk_size"]) != 1024
                or float(self.config["threshold"]) != 0.9
                or self.config["character_boundaries"] is not True):
                raise ValueError("Time bounded extraction needs frozen fine contract")
        device = next(self.model.parameters()).device
        batch = prepared.batch.to(device)
        context = self.model.encode_context(batch, backbone)
        context_seconds = time.perf_counter() - started
        budget_census = None
        projection_identity = None
        if bounded_policy is None:
            candidates = iter_span_candidates(
                prepared,
                max_token_width=int(self.config["max_span_width_tokens"]),
                max_character_width=int(self.config["max_span_width_characters"]),
                character_boundaries=bool(self.config["character_boundaries"]),
            )
        else:
            cheap_started = time.perf_counter()
            lane = Lane("TIME", 21, 44, 1024, 1)
            pairs, broad = token_pairs(prepared, lane)
            boundaries, cheap = selected_boundaries(
                prepared, pairs, lane, bounded_policy.budget,
            )
            retained = cheap.get("fine_candidate_rows", 0)
            if broad["candidate_count"] and not retained:
                raise RuntimeError("Time bounded selector returned empty nonempty article")
            candidates = iter_bounded_span_candidates(
                prepared, boundaries, max_token_width=lane.max_tokens,
                max_character_width=lane.max_chars,
            )
            budget_census = {**cheap,
                "policy_id": bounded_policy.policy_id,
                "policy_config_sha256": bounded_policy.config_sha256,
                "selector_source_sha256": bounded_policy.selector_sha256,
                "broad_structural_candidate_count": broad["candidate_count"],
                "cheap_visited_count": (cheap["token_span_cheaply_ranked"]
                    + cheap["cheap_boundary_position_visited"]
                    + cheap["cheap_character_cross_pair_visited"]),
                "boundary_candidate_retained_count": retained,
                "cheap_selection_seconds": time.perf_counter() - cheap_started,
                "time_context_encoding_seconds": context_seconds,
            }
            pairs.clear()
            boundaries = {}
            projection_identity = TimeProjectionIdentity(
                str(prepared.article.article_version_id),
                sha256(prepared.article.content.encode("utf-8")).hexdigest(),
                bounded_policy.policy_id, bounded_policy.config_sha256,
                id(backbone), id(context), id(self.model.candidate_span_encoder),
                self.checkpoint_sha, str(device),
                str(next(self.model.parameters()).dtype),
            )
        scorer_started = time.perf_counter() if bounded_policy is not None else None
        accepted = []
        candidate_count = 0
        hits = misses = 0
        width_census = Counter() if routing_observer is not None else None
        sentence_census = Counter() if routing_observer is not None else None
        character_variant_count = 0
        chunk_size = int(self.config.get("candidate_chunk_size", 1024))
        threshold = float(self.config["threshold"])
        for chunk in iter_candidate_chunks(candidates, chunk_size):
            candidate_count += len(chunk)
            if routing_observer is not None:
                for row in chunk:
                    width_census[int(row["token_end"]) - int(row["token_start"])] += 1
                    sentence_census[int(row["sentence_index"])] += 1
                    character_variant_count += int(
                        row["boundary_features"][0] != 0.0
                        or row["boundary_features"][1] != 1.0
                    )
            selected, chunk_hits, chunk_misses = self._score_chunk(
                prepared, backbone, batch, context, chunk, threshold,
                device, diagnostic_sink, projection_identity,
            )
            accepted.extend(selected)
            hits += chunk_hits
            misses += chunk_misses
        if budget_census is not None:
            if candidate_count != budget_census["boundary_candidate_retained_count"]:
                raise RuntimeError("Time selector rows differ from fine head input")
            budget_census.update({
                "fine_scored_candidate_count": candidate_count,
                "accepted_time_candidate_count": len(accepted),
                "budget_exhaustion_count": (
                    budget_census["broad_structural_candidate_count"] - candidate_count),
                "projection_reuse_hit_count": hits,
                "projection_reuse_miss_count": misses,
                "unique_expensive_token_span_projection_count":
                    budget_census.get("unique_expensive_token_projection_keys", 0),
                "projection_cache_scope": "SELECTED_CHUNK_ONLY",
                "expensive_time_representation_scoring_seconds":
                    time.perf_counter() - scorer_started,
            })
            del candidates, context, batch, projection_identity
        accepted.sort(key=lambda row: (row["sentence_index"], row["char_start"], row["char_end"]))
        if routing_observer is not None:
            record = {
                "lane": "TIME",
                "article_version_id": prepared.article.article_version_id,
                "candidate_count": candidate_count,
                "character_variant_count": character_variant_count,
                "token_width_counts": dict(sorted(width_census.items())),
                "sentence_count": len(sentence_census),
                "max_candidates_per_sentence": max(sentence_census.values(), default=0),
                "accepted_pre_occurrence_count": len(accepted),
            }
            if bounded_policy is None:
                routing_observer.observe_reference_scalar("phase_b_census", record)
            else:
                routing_observer.observe_bounded_scalar("phase_b_bounded_census",
                                                        {**record, **budget_census})
        trace = {
            "stage": "③ 구간 추출부",
            "component": "Generic TimeExpression span classifier",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": len(prepared.article.content),
            "candidate_count": candidate_count,
            "output_count": len(accepted),
            "representation_layer": 10,
            "published_at_feature": False,
            "warnings": [],
            "elapsed_seconds": time.perf_counter() - started,
        }
        if budget_census is not None:
            trace["time_span_budget_census"] = budget_census
        return tuple(accepted), trace


def pack_event_time_candidates(events, times, device):
    rows = []
    kinds = []
    for item in events:
        aligned = item.get("aligned") or (
            item["sentence_index"],
            item["token_start"],
            item["token_end"],
        )
        rows.append([int(value) for value in aligned])
        kinds.append(SPAN_KINDS.index("EVENT"))
    for item in times:
        rows.append([item["sentence_index"], item["token_start"], item["token_end"]])
        kinds.append(SPAN_KINDS.index("TIME"))
    candidates = SimpleNamespace(
        span_indices=torch.tensor([rows], dtype=torch.long, device=device).reshape(1, -1, 3),
        span_kind_ids=torch.tensor([kinds], dtype=torch.long, device=device),
        span_mask=torch.ones(1, len(rows), dtype=torch.bool, device=device),
    )
    pair_rows = []
    features = []
    for event_index, event in enumerate(events):
        for time_index, temporal in enumerate(times):
            distance = int(temporal["sentence_index"]) - int(event["sentence_index"])
            event_span = (int(event["char_start"]), int(event["char_end"]))
            time_span = (int(temporal["char_start"]), int(temporal["char_end"]))
            pair_rows.append((event_index, len(events) + time_index))
            features.append(
                (
                    float(distance == 0),
                    float(event_span[0] <= time_span[0] and time_span[1] <= event_span[1]),
                    float(time_span[1] <= event_span[0]),
                    max(-1.0, min(1.0, distance / 32.0)),
                )
            )
    pairs = PairIndexBatch(
        source_indices=torch.tensor([[row[0] for row in pair_rows]], dtype=torch.long, device=device),
        target_indices=torch.tensor([[row[1] for row in pair_rows]], dtype=torch.long, device=device),
        mask=torch.ones(1, len(pair_rows), dtype=torch.bool, device=device),
        policy_features=torch.tensor([features], dtype=torch.float32, device=device).reshape(1, len(pair_rows), 4),
    )
    return candidates, pairs, pair_rows


def _pack_event_time_spans(events, times, device):
    """Pair universe와 분리해 canonical occurrence의 span state만 준비한다."""
    rows = []
    kinds = []
    for event in events:
        aligned = event.get("aligned") or (
            event["sentence_index"], event["token_start"], event["token_end"]
        )
        rows.append([int(value) for value in aligned])
        kinds.append(SPAN_KINDS.index("EVENT"))
    for temporal in times:
        rows.append([
            int(temporal["sentence_index"]), int(temporal["token_start"]),
            int(temporal["token_end"]),
        ])
        kinds.append(SPAN_KINDS.index("TIME"))
    return SimpleNamespace(
        span_indices=torch.tensor([rows], dtype=torch.long, device=device).reshape(1, -1, 3),
        span_kind_ids=torch.tensor([kinds], dtype=torch.long, device=device),
        span_mask=torch.ones(1, len(rows), dtype=torch.bool, device=device),
    )


def _iter_event_time_pair_chunks(events, times, device, batch_size):
    """기존 ALL Event×Time 방향·feature 순서를 보존하며 pair tensor만 제한한다."""
    if batch_size <= 0:
        raise ValueError("Event-Time pair batch_size must be positive")
    source, target, features, indices = [], [], [], []
    event_count = len(events)
    for event_index, event in enumerate(events):
        event_span = (int(event["char_start"]), int(event["char_end"]))
        for time_index, temporal in enumerate(times):
            distance = int(temporal["sentence_index"]) - int(event["sentence_index"])
            time_span = (int(temporal["char_start"]), int(temporal["char_end"]))
            source.append(event_index)
            target.append(event_count + time_index)
            indices.append((event_index, time_index))
            features.append((
                float(distance == 0),
                float(event_span[0] <= time_span[0] and time_span[1] <= event_span[1]),
                float(time_span[1] <= event_span[0]),
                max(-1.0, min(1.0, distance / 32.0)),
            ))
            if len(indices) == batch_size:
                yield _pair_chunk(source, target, features, device), tuple(indices)
                source, target, features, indices = [], [], [], []
    if indices:
        yield _pair_chunk(source, target, features, device), tuple(indices)


def _iter_selected_event_time_pair_chunks(events, times, selected_by_event,
                                          device, batch_size):
    """Routing ID union만 4개 frozen feature/pair scorer에 전달한다."""
    if batch_size <= 0:
        raise ValueError("Event-Time pair batch_size must be positive")
    source, target, features, indices = [], [], [], []
    event_count = len(events)
    for event_index, event in enumerate(events):
        event_span = (int(event["char_start"]), int(event["char_end"]))
        for time_index in selected_by_event[event_index]:
            temporal = times[time_index]
            distance = int(temporal["sentence_index"]) - int(event["sentence_index"])
            time_span = (int(temporal["char_start"]), int(temporal["char_end"]))
            source.append(event_index)
            target.append(event_count + time_index)
            indices.append((event_index, time_index))
            features.append((
                float(distance == 0),
                float(event_span[0] <= time_span[0] and time_span[1] <= event_span[1]),
                float(time_span[1] <= event_span[0]),
                max(-1.0, min(1.0, distance / 32.0)),
            ))
            if len(indices) == batch_size:
                yield _pair_chunk(source, target, features, device), tuple(indices)
                source, target, features, indices = [], [], [], []
    if indices:
        yield _pair_chunk(source, target, features, device), tuple(indices)


def _pair_chunk(source, target, features, device):
    count = len(source)
    return PairIndexBatch(
        source_indices=torch.tensor([source], dtype=torch.long, device=device).reshape(1, count),
        target_indices=torch.tensor([target], dtype=torch.long, device=device).reshape(1, count),
        mask=torch.ones(1, count, dtype=torch.bool, device=device),
        policy_features=torch.tensor([features], dtype=torch.float32, device=device).reshape(1, count, 4),
    )


class FixedEventTimeAttachmentRuntime:
    """Inference-only stage ⑤ directed Event→TimeExpression attachment."""

    def __init__(self, model, config, checkpoint_sha):
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha

    @torch.inference_mode()
    def run(self, prepared, backbone, events, times, *, bounded_policy=None):
        started = time.perf_counter()
        if bounded_policy is not None and not isinstance(
            bounded_policy, TemporalBoundedContract
        ):
            raise TypeError("bounded Time policy must be fixed Step 5 r1 K80")
        if not events or not times:
            return {}, (), {
                "stage": "⑤ 방향 관계 판정부",
                "component": "Event→TimeExpression attachment",
                "checkpoint_sha": self.checkpoint_sha,
                "input_count": len(events) + len(times),
                "candidate_count": 0,
                "output_count": 0,
                "published_at_feature": False,
                "warnings": [],
                "elapsed_seconds": time.perf_counter() - started,
            }
        device = next(self.model.parameters()).device
        batch = prepared.batch.to(device)
        threshold = float(self.config["threshold"])
        by_event = {event["prediction_id"]: [] for event in events}
        attachments = []
        pair_batch_size = int(self.config.get("pair_batch_size", 2048))
        pair_batch_count = 0
        inactive_pair_count = 0
        bounded_session = None
        routing_rows = []
        selected_by_event = None
        if bounded_policy is not None:
            bounded_session = TemporalBoundedSession(
                bounded_policy, prepared, events, times
            )
            selected_by_event = []
            for event in events:
                decision = bounded_session.route(event)
                selected_by_event.append(bounded_session.selected_indices(decision))
                routing_rows.append(decision)
            if len(selected_by_event) != len(events):
                raise RuntimeError("Time bounded route omitted a canonical EventMention")
        with StageScope() as stage:
            candidates = stage.own(_pack_event_time_spans(events, times, device))
            context, states = self.model.encode(batch, backbone, candidates)
            stage.own(context)
            stage.own(states)
            pair_stream = (
                _iter_event_time_pair_chunks(events, times, device, pair_batch_size)
                if bounded_session is None else
                _iter_selected_event_time_pair_chunks(
                    events, times, selected_by_event, device, pair_batch_size
                )
            )
            fine_count_by_event = [0] * len(events)
            for pairs, pair_indices in pair_stream:
                pair_batch_count += 1
                logits, mask = self.model.forward_pairs(
                    states, candidates, pairs, context.document_state,
                )
                scores = torch.sigmoid(logits[0]).detach().cpu().tolist()
                for (event_index, time_index), score, active in zip(
                    pair_indices, scores, mask[0].tolist(),
                ):
                    fine_count_by_event[event_index] += 1
                    if not active:
                        inactive_pair_count += 1
                        continue
                    if score < threshold:
                        continue
                    event = events[event_index]
                    temporal = times[time_index]
                    row = {
                        "attachment_id": event_time_attachment_id(event["prediction_id"], temporal["prediction_id"]),
                        "source_event_prediction_id": event["prediction_id"],
                        "target_time_prediction_id": temporal["prediction_id"],
                        "score": float(score),
                        "checkpoint_sha": self.checkpoint_sha,
                        "runtime_config_id": self.config["runtime_config_id"],
                        "source": "PREDICTED_EVENT_TIME_ATTACHMENT",
                        "responsibility": "⑤ 방향 관계 판정부",
                        "provenance": {"direction": "EVENT_TO_TIME_EXPRESSION", "published_at_feature": False},
                    }
                    attachments.append(row)
                    by_event[event["prediction_id"]].append(row)
        bounded_trace = None
        if bounded_session is not None:
            summaries = [
                bounded_session.record_and_release(
                    event["prediction_id"], fine_count_by_event[index]
                ) for index, event in enumerate(events)
            ]
            bounded_trace = {
                "policy_id": bounded_policy.policy_id,
                "revision": bounded_policy.revision,
                "manifest_sha256": bounded_policy.manifest_sha256,
                "tier_quota": {"LOCAL": 8, "NEAR": 8, "GLOBAL": 64},
                "query_count": len(events),
                "visited": sum(row.visited for row in summaries),
                "cheaply_ranked": sum(row.cheaply_ranked for row in summaries),
                "retained": sum(row.retained for row in summaries),
                "fine_scored": sum(row.fine_scored for row in summaries),
                "skipped_by_budget": sum(row.skipped_by_budget for row in summaries),
                "budget_exhausted_query_count": sum(
                    row.budget_exhausted for row in summaries
                ),
                "global_top64_unindexed_occurrence_count": (
                    bounded_session.unindexed_global_count
                ),
                "request_used": bounded_session.router.request.used_units,
                "request_budget": bounded_session.router.request.total_units,
                "reference_fallback_active": False,
                "coarse_score_is_final_confidence": False,
                "multiple_positive_attachments_allowed": True,
                "published_at_used_for_routing": False,
            }
            bounded_session.close()
            bounded_trace["index_released_after_scoring"] = (
                bounded_session.index.owner_census()["released"]
            )
        attachments.sort(key=lambda row: (row["source_event_prediction_id"], row["target_time_prediction_id"]))
        trace = {
            "stage": "⑤ 방향 관계 판정부",
            "component": "Event→TimeExpression attachment",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": len(events) + len(times),
            "candidate_count": (
                len(events) * len(times) if bounded_session is None
                else sum(fine_count_by_event)
            ),
            "broad_possible_pair_count": len(events) * len(times),
            "output_count": len(attachments),
            "pair_batch_size": pair_batch_size,
            "pair_batch_count": pair_batch_count,
            "inactive_pair_count": inactive_pair_count,
            "published_at_feature": False,
            "warnings": [],
            "elapsed_seconds": time.perf_counter() - started,
        }
        if bounded_trace is not None:
            trace["time_bounded_routing"] = bounded_trace
        return by_event, tuple(attachments), trace
