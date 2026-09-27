"""Source-only Event pair evidence for the versioned v3 P5 adaptation.

The v2.3 resolver-dependent ROLE scalars and its separate Event verifier score
are absent. The three text comparisons, sentence distance, and presence cues
retain their historical formulas. Current r06 Time values become *soft evidence*:
compatible, incompatible, incomparable, and unknown are separate indicators.
Multiple attachments may set more than one indicator. Time distance is a
source-derived calendar gap in days divided by ``gap + 365``; zero distance is
distinguished from unavailable distance by the four indicators. Interval and
semantic-type cues are also kept separate. None is a hard gate or routing score.

Gold pair labels, learned pair logits, and acceptance thresholds are not inputs.
Gold-only normalized values are ignored unless independently source-rederived.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
import re
from typing import Sequence

import torch

from runtime.v3_pretraining.event_identity import EventMember
from runtime.v3_pretraining.source_layout import RawArticle
from runtime.v3_pretraining.temporal import (TemporalOccurrence, infer_source_time,
                                            parse_canonical_time)


EVENT_PAIR_POLICY_VERSION = "V3_EVENT_PAIR_SOURCE_POLICY_15_V2"
EVENT_PAIR_POLICY_FEATURES = (
    "event_text_bigram_jaccard",
    "event_text_normalized_containment",
    "trigger_text_bigram_jaccard",
    "time_compatible",
    "time_incompatible",
    "time_incomparable",
    "time_unknown",
    "time_distance_365d_normalized",
    "time_interval_compatible",
    "time_interval_incompatible",
    "time_semantic_type_match",
    "time_shared_raw_evidence",
    "sentence_distance_capped_32",
    "both_triggers_present",
    "both_time_attachments_present",
)

_ROLES = ("ACTOR", "TARGET", "PLACE")
_SET = re.compile(r"매일|매주|매월|매년|마다|정기적으로")
_DURATION = re.compile(r"(?:동안|간|주기|째|이내|이상|이하)$")
_ZONE = re.compile(r"\b(?:UTC|GMT|KST|[+-]\d{2}:?\d{2})\b", re.IGNORECASE)


@lru_cache(maxsize=16384)
def _norm(text: str) -> str:
    return "".join(text.casefold().split())


@lru_cache(maxsize=16384)
def _grams(text: str) -> frozenset[str]:
    value = _norm(text)
    if len(value) < 2:
        return frozenset((value,)) if value else frozenset()
    return frozenset(value[index:index + 2] for index in range(len(value) - 1))


def _jaccard(left: str, right: str) -> float:
    a, b = _grams(left), _grams(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def _sentence_index(member: EventMember,
                    sentence_spans: Sequence[tuple[int, int]]) -> int:
    indices = [index for index, (start, end) in enumerate(sentence_spans)
               if max(start, member.start) < min(end, member.end)]
    if not indices:
        raise ValueError("Event pair policy needs a source-grounded sentence per Event")
    # Match the first-overlap anchor used by Event member sentence summaries.
    return indices[0]


def _source_timezone(occurrence: TemporalOccurrence,
                     article: RawArticle, source_reason: str | None) -> str | None:
    marker = _ZONE.search(occurrence.text)
    if marker is not None:
        return marker.group().upper()
    if source_reason != "SOURCE_RELATIVE_ANCHORED":
        return None
    contexts = occurrence.normalization_contexts
    if len(contexts) > 1:
        raise ValueError("Time source has ambiguous normalization contexts")
    if contexts and contexts[0].provenance == "SOURCE_EXPLICIT_MONTH":
        return None
    if article.published_at is None:
        raise ValueError("relative Time has no published-at timezone source")
    try:
        anchor = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("relative Time has invalid published-at timezone source") from exc
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise ValueError("relative Time has no published-at timezone source")
    return anchor.tzname()


@dataclass(frozen=True, slots=True)
class _SourceTime:
    semantic_type: str | None
    bounds: tuple[date, date] | None
    is_interval: bool
    timezone: str | None


def _calendar_bounds(value: str) -> tuple[date, date] | None:
    parsed = parse_canonical_time(value)
    if parsed.kind == "FISCAL_YEAR":
        # The source does not state where the fiscal year begins.
        return None
    first, last = (value.split("/") if parsed.kind == "INTERVAL"
                   else (value, value))

    def point_bounds(part: str) -> tuple[date, date]:
        components = tuple(map(int, part.split("-")))
        if len(components) == 1:
            return date(components[0], 1, 1), date(components[0], 12, 31)
        if len(components) == 2:
            year, month = components
            return date(year, month, 1), date(year, month, monthrange(year, month)[1])
        return date(*components), date(*components)

    return point_bounds(first)[0], point_bounds(last)[1]


def _source_time(occurrence: TemporalOccurrence, article: RawArticle) -> _SourceTime:
    """Use r06 source derivation, never Gold-only normalized values."""
    contexts = occurrence.normalization_contexts
    if len(contexts) > 1:
        raise ValueError("Time source has ambiguous normalization contexts")
    inferred, source_reason = infer_source_time(
        occurrence.text, article.published_at,
        relative_month_context=contexts[0] if contexts else None)
    if occurrence.normalization_status == "SOURCE_RULE":
        if inferred != occurrence.normalized_value or inferred is None:
            raise ValueError("source-rule Time normalization differs from source")
        if parse_canonical_time(inferred).granularity != occurrence.granularity:
            raise ValueError("source-rule Time granularity differs from source")
    elif occurrence.normalization_status not in ("UNRESOLVED", "GOLD"):
        raise ValueError("Time has unknown normalization status")
    parsed = parse_canonical_time(inferred) if inferred is not None else None
    semantic_type = ("SET" if _SET.search(occurrence.text) else
                     "DURATION" if _DURATION.search(occurrence.text) else
                     parsed.kind if parsed is not None else None)
    return _SourceTime(semantic_type,
                       _calendar_bounds(inferred) if parsed is not None and
                       semantic_type in ("POINT", "INTERVAL") else None,
                       parsed is not None and parsed.kind == "INTERVAL",
                       _source_timezone(occurrence, article, source_reason) if inferred else None)


def _time_evidence(left: Sequence[TemporalOccurrence], right: Sequence[TemporalOccurrence],
                   source_times: dict[str, _SourceTime]) -> tuple[float, ...]:
    compatible = incompatible = incomparable = unknown = False
    interval_compatible = interval_incompatible = semantic_match = False
    shared_raw = bool({eid for row in left for eid in row.evidence_ids} &
                      {eid for row in right for eid in row.evidence_ids})
    minimum_gap: int | None = None
    if not left or not right:
        unknown = True
    for a in left:
        for b in right:
            aa, bb = source_times[a.local_id], source_times[b.local_id]
            if aa.semantic_type is not None and bb.semantic_type is not None:
                semantic_match |= aa.semantic_type == bb.semantic_type
            if aa.semantic_type is None or bb.semantic_type is None:
                unknown = True
                continue
            if aa.bounds is None or bb.bounds is None or (
                    aa.timezone and bb.timezone and aa.timezone != bb.timezone):
                incomparable = True
                continue
            gap = max((aa.bounds[0] - bb.bounds[1]).days,
                      (bb.bounds[0] - aa.bounds[1]).days, 0)
            minimum_gap = gap if minimum_gap is None else min(minimum_gap, gap)
            compatible |= gap == 0
            incompatible |= gap > 0
            if aa.is_interval or bb.is_interval:
                interval_compatible |= gap == 0
                interval_incompatible |= gap > 0
    distance = (minimum_gap / (minimum_gap + 365.0)
                if minimum_gap is not None else 0.0)
    return tuple(map(float, (compatible, incompatible, incomparable, unknown))) + (
        distance, float(interval_compatible), float(interval_incompatible),
        float(semantic_match), float(shared_raw))


def event_pair_policy_features(*, article: RawArticle,
                               members: Sequence[EventMember],
                               occurrences: Sequence[TemporalOccurrence],
                               sentence_spans: Sequence[tuple[int, int]],
                               pairs: Sequence[tuple[int, int]],
                               reference: torch.Tensor) -> torch.Tensor:
    """Return `[P,15]` source features in canonical `(left < right)` pair order.

    `pairs` must be unique and lexicographically sorted. The function fails
    closed on missing source coordinates or Time attachments. Gold-only
    normalization is ignored if it cannot be source-rederived.
    """
    if not reference.dtype.is_floating_point:
        raise TypeError("Event policy reference tensor must be floating point")
    if len({member.member_id for member in members}) != len(members):
        raise ValueError("duplicate Event member ID")
    if len({row.local_id for row in occurrences}) != len(occurrences):
        raise ValueError("duplicate Time occurrence ID")
    if tuple(pairs) != tuple(sorted(set(pairs))) or any(
            len(pair) != 2 or not 0 <= pair[0] < pair[1] < len(members)
            for pair in pairs):
        raise ValueError("Event policy pairs must be unique canonical ordered indices")
    if tuple(sentence_spans) != tuple(sorted(sentence_spans)) or any(
            not 0 <= start < end <= len(article.content)
            for start, end in sentence_spans):
        raise ValueError("Event policy sentence spans are invalid or unordered")
    if not pairs:
        return reference.new_empty((0, len(EVENT_PAIR_POLICY_FEATURES)))

    by_time = {row.local_id: row for row in occurrences}
    all_raw_ids: set[str] = set()
    source_times: dict[str, _SourceTime] = {}
    for row in occurrences:
        if (not 0 <= row.start < row.end <= len(article.content) or
                article.content[row.start:row.end] != row.text or
                not row.evidence_ids or len(set(row.evidence_ids)) != len(row.evidence_ids) or
                any(eid in all_raw_ids for eid in row.evidence_ids)):
            raise ValueError("Time occurrence lost unique exact source evidence")
        all_raw_ids.update(row.evidence_ids)

    indices = []
    member_times: list[list[TemporalOccurrence]] = []
    for member in members:
        if (not 0 <= member.start < member.end <= len(article.content) or
                article.content[member.start:member.end] != member.text):
            raise ValueError("Event member lost exact source span")
        trigger = (member.trigger_start, member.trigger_end, member.trigger_text)
        if any(value is None for value in trigger) and any(value is not None for value in trigger):
            raise ValueError("Event trigger has incomplete source span")
        if member.trigger_text is not None and (not 0 <= member.trigger_start <
                member.trigger_end <= len(article.content) or
                article.content[member.trigger_start:member.trigger_end] != member.trigger_text):
            raise ValueError("Event trigger lost exact source span")
        for role in member.roles:
            if (role.role not in _ROLES or
                    not 0 <= role.start < role.end <= len(article.content) or
                    article.content[role.start:role.end] != role.text):
                raise ValueError("Event role lost exact source span")
        indices.append(_sentence_index(member, sentence_spans))
        attached = []
        for time_id in member.time_ids:
            occurrence = by_time.get(time_id)
            if occurrence is None or member.member_id not in occurrence.attached_event_ids:
                raise ValueError("Event Time attachment is absent or inconsistent")
            attached.append(occurrence)
            if time_id not in source_times:
                source_times[time_id] = _source_time(occurrence, article)
        member_times.append(attached)

    rows = []
    for left_index, right_index in pairs:
        left, right = members[left_index], members[right_index]
        rows.append((
            _jaccard(left.text, right.text),
            float(_norm(left.text) in _norm(right.text) or
                  _norm(right.text) in _norm(left.text)),
            _jaccard(left.trigger_text or "", right.trigger_text or ""),
            *_time_evidence(member_times[left_index], member_times[right_index], source_times),
            min(abs(indices[left_index] - indices[right_index]), 32) / 32.0,
            float(left.trigger_text is not None and right.trigger_text is not None),
            float(bool(member_times[left_index] and member_times[right_index])),
        ))
    return reference.new_tensor(rows).reshape(len(pairs), len(EVENT_PAIR_POLICY_FEATURES))
