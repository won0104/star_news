"""r05.3 textual Time의 정밀도 보존·보수적 source 정규화·PUBLIC 적격성 경계.

정규화는 source 또는 timezone이 명확한 상대 표현에서만 만든다. Event attachment는
별도 learned decision이며 calendar eligibility는 12번 선택/직렬화의 입력 신호다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Mapping, Sequence

from runtime.v3_pretraining.source_layout import RawArticle


_YEAR = re.compile(r"\d{4}\Z")
_MONTH = re.compile(r"(\d{4})-(\d{2})\Z")
_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})\Z")
_FY = re.compile(r"FY\d{4}\Z")
_KO_DATE = re.compile(r"(\d{4})년(?:\s*(\d{1,2})월(?:\s*(\d{1,2})일)?)?\Z")
_ZONE = re.compile(r"\b(KST|UTC|GMT)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CanonicalTimeValue:
    value: str
    kind: str  # POINT, INTERVAL, FISCAL_YEAR
    granularity: str  # YEAR, MONTH, DAY, FISCAL_YEAR


def parse_canonical_time(value: str) -> CanonicalTimeValue:
    """Gold 표기의 유효 날짜와 같은 granularity interval만 받아 손실 없이 반환한다."""
    if not isinstance(value, str) or not value:
        raise ValueError("canonical Time value must be nonempty")
    if "/" in value:
        parts = value.split("/")
        if len(parts) != 2:
            raise ValueError("Time interval needs exactly two endpoints")
        first, last = (parse_canonical_time(part) for part in parts)
        if (first.kind != "POINT" or last.kind != "POINT" or
                first.granularity != last.granularity or first.value > last.value):
            raise ValueError("Time interval endpoints need ordered equal calendar granularity")
        return CanonicalTimeValue(value, "INTERVAL", first.granularity)
    if _FY.fullmatch(value):
        if int(value[2:]) == 0:
            raise ValueError("fiscal year zero is invalid")
        return CanonicalTimeValue(value, "FISCAL_YEAR", "FISCAL_YEAR")
    if _YEAR.fullmatch(value):
        if int(value) == 0:
            raise ValueError("calendar year zero is invalid")
        return CanonicalTimeValue(value, "POINT", "YEAR")
    match = _MONTH.fullmatch(value)
    if match:
        year, month = map(int, match.groups())
        if not 1 <= year <= 9999 or not 1 <= month <= 12:
            raise ValueError("invalid calendar month")
        return CanonicalTimeValue(value, "POINT", "MONTH")
    match = _DAY.fullmatch(value)
    if match:
        date(*map(int, match.groups()))
        return CanonicalTimeValue(value, "POINT", "DAY")
    raise ValueError("unsupported r05.3 Time value")


def calendar_eligible(value: str | None) -> bool:
    """12번 calendar adapter가 받을 수 있는 실제 단일 YEAR/MONTH/DAY 값."""
    if value is None:
        return False
    try:
        parsed = parse_canonical_time(value)
    except ValueError:
        return False
    return parsed.kind == "POINT"


@dataclass(frozen=True, slots=True)
class TimeMentionEvidence:
    time_id: str
    start: int
    end: int
    text: str
    normalized_value: str | None
    normalization_status: str  # GOLD, SOURCE_RULE, UNRESOLVED


@dataclass(frozen=True, slots=True)
class TemporalOccurrence:
    local_id: str
    evidence_ids: tuple[str, ...]
    start: int
    end: int
    text: str
    normalized_value: str | None
    granularity: str | None
    normalization_status: str
    attached_event_ids: tuple[str, ...]
    attachment_status: str  # ATTACHED or UNATTACHED
    calendar_eligible: bool
    public_calendar_candidate: bool


def infer_source_time(text: str, published_at: str | None) -> tuple[str | None, str]:
    """명시적 precision만 복사한다; anchor 없는 상대시간과 시각/day 투영은 거절한다."""
    source = text.strip()
    try:
        return parse_canonical_time(source).value, "SOURCE_EXPLICIT"
    except ValueError:
        pass
    ko = _KO_DATE.fullmatch(source)
    if ko:
        year, month, day = ko.groups()
        candidate = year + ("-" + month.zfill(2) if month else "") + (
            "-" + day.zfill(2) if day else "")
        try:
            return parse_canonical_time(candidate).value, "SOURCE_EXPLICIT"
        except ValueError:
            return None, "INVALID_SOURCE_DATE"
    marker = _ZONE.search(source)
    relative = _ZONE.sub("", source).strip()
    if relative not in ("오늘", "어제", "지난달"):
        return None, "INSUFFICIENT_SOURCE_OR_UNSUPPORTED_PRECISION"
    if not published_at:
        return None, "MISSING_PUBLISHED_AT"
    try:
        anchor = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return None, "INVALID_PUBLISHED_AT"
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        return None, "MISSING_TIMEZONE"
    if marker:
        zone = marker.group().upper()
        anchor = anchor.astimezone(timezone(timedelta(hours=9)) if zone == "KST" else timezone.utc)
    day = anchor.date()
    if relative == "오늘":
        return day.isoformat(), "SOURCE_RELATIVE_ANCHORED"
    if relative == "어제":
        return (day - timedelta(days=1)).isoformat(), "SOURCE_RELATIVE_ANCHORED"
    year, month = day.year, day.month - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}", "SOURCE_RELATIVE_ANCHORED"


def close_time_occurrences(article: RawArticle, mentions: Sequence[TimeMentionEvidence],
                           attachments: Sequence[tuple[str, str]]) -> tuple[TemporalOccurrence, ...]:
    """동일 source occurrence만 합치고 미연결·미정규화 사유를 별도로 보존한다."""
    if len({row.time_id for row in mentions}) != len(mentions):
        raise ValueError("duplicate Time evidence ID")
    by_id = {row.time_id: row for row in mentions}
    if any(tid not in by_id or not event_id for event_id, tid in attachments):
        raise ValueError("attachment references missing Event/Time")
    groups: dict[tuple[int, int, str | None], list[TimeMentionEvidence]] = {}
    for row in mentions:
        if not 0 <= row.start < row.end <= len(article.content) or article.content[row.start:row.end] != row.text:
            raise ValueError("Time evidence lost exact source grounding")
        if row.normalization_status not in ("GOLD", "SOURCE_RULE", "UNRESOLVED"):
            raise ValueError("unknown Time normalization provenance")
        if row.normalized_value is not None:
            parse_canonical_time(row.normalized_value)
        if row.normalization_status == "UNRESOLVED" and row.normalized_value is not None:
            raise ValueError("unresolved Time cannot claim a value")
        if row.normalization_status == "SOURCE_RULE" and (
                row.normalized_value is None or
                infer_source_time(row.text, article.published_at)[0] != row.normalized_value):
            raise ValueError("source-derived Time value exceeds exact textual/anchor evidence")
        groups.setdefault((row.start, row.end, row.normalized_value), []).append(row)
    output = []
    for (start, end, value), members in sorted(groups.items(), key=lambda item: item[0]):
        member_ids = tuple(sorted(row.time_id for row in members))
        event_ids = tuple(sorted({eid for eid, tid in attachments if tid in member_ids}))
        parsed = parse_canonical_time(value) if value is not None else None
        local_id = "TOCC:" + sha256(f"{article.article_version_id}:{article.content_sha256}:{start}:{end}:{value}".encode()).hexdigest()[:16]
        statuses = {row.normalization_status for row in members}
        if len(statuses) > 1:
            raise ValueError("same Time occurrence has conflicting normalization provenance")
        eligible = calendar_eligible(value)
        output.append(TemporalOccurrence(local_id, member_ids, start, end, article.content[start:end],
                                         value, parsed.granularity if parsed else None,
                                         next(iter(statuses)), event_ids,
                                         "ATTACHED" if event_ids else "UNATTACHED", eligible,
                                         eligible and bool(event_ids)))
    return tuple(output)


def remap_time_attachments(occurrences: Sequence[TemporalOccurrence],
                           event_member_to_cluster: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """8번 final Event ID 확정 후 모든 member의 Time evidence를 cluster에 합친다."""
    result: dict[str, set[str]] = {}
    for row in occurrences:
        for event_id in row.attached_event_ids:
            cluster_id = event_member_to_cluster.get(event_id)
            if cluster_id is None:
                raise ValueError("attached Event lacks final cluster identity")
            result.setdefault(cluster_id, set()).add(row.local_id)
    return {cluster_id: tuple(sorted(ids)) for cluster_id, ids in sorted(result.items())}
