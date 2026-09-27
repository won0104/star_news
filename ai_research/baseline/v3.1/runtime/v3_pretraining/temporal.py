"""r06.0 textual Time의 anchor 정규화와 PUBLIC 투영 경계.

정규화는 raw operator를 떼어 내지 않고 안정적인 calendar anchor만 만든다.
Event attachment, calendar value 형식 지원, raw 표현의 projection safety는 서로
다른 판단이다. 이 모듈은 세 판단을 scalar occurrence에 보존하고 PUBLIC과
같은 결정 규칙을 사용하게 한다.
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
_KO_DATE_BOUNDARY = re.compile(
    r"(\d{4})년(?:\s*(\d{1,2})월(?:\s*(\d{1,2})일)?)?\s*(부터|이전|이후)\Z"
)
_LAST_DAY = re.compile(r"지난\s*(\d{1,2})일(부터)?\Z")
_CONTEXTUAL_LAST_DAY_FROM = re.compile(
    r"휴전\s*발효\s*\d+일\s*만인\s*지난\s*(\d{1,2})일부터\Z"
)
_KO_MONTH_REFERENCE = re.compile(r"(?<!\d)(\d{4})년\s*(\d{1,2})월(?!\s*\d)")
_ZONE = re.compile(r"\b(KST|UTC|GMT)\b", re.IGNORECASE)

TIME_PROJECTION_POLICY_VERSION = "r06-time-public-projection-v1"
RELATIVE_MONTH_CONTEXT_PROVENANCE = frozenset({
    "PUBLISHED_AT_MONTH_CONFIRMED",
    "SOURCE_EXPLICIT_MONTH",
})
_CLEAR_RELATIVE_CALENDAR = re.compile(
    r"(?:오늘|어제|지난달|작년|새해|지난\s*\d{1,2}월|지난\s*\d{1,2}일|"
    r"\d{1,2}월(?:\s*\d{1,2}일)?|\d{1,2}일(?:\s*\(현지시간\))?)\Z"
)
_AMBIGUOUS_TEMPORAL = re.compile(
    r"(?:경|약|정도|무렵|전후|여간|동안|대비|보다|처음|그다음|머지|오래|이내)"
)


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
    raise ValueError("unsupported r06.0 Time value")


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
class RelativeMonthContext:
    """`지난 N일`의 기준 연·월을 확정한 외부 근거.

    `PUBLISHED_AT_MONTH_CONFIRMED`는 발행 연·월이 해당 표현의 기준임을
    caller가 문맥으로 확인했음을 뜻한다. `SOURCE_EXPLICIT_MONTH`는 기사 내
    exact span을 근거로 삼는다. 단순 발행일 존재는 전자를 자동 생성하지
    않는다.
    """

    year: int
    month: int
    provenance: str
    evidence_id: str
    evidence_start: int | None = None
    evidence_end: int | None = None
    evidence_text: str | None = None


@dataclass(frozen=True, slots=True)
class RelativeMonthContextBinding:
    """Bind one confirmed month context to one exact Time span and article snapshot.

    The binding is deliberately occurrence-local.  A caller cannot provide one
    article-level default that is then broadcast to every relative-day mention.
    """

    article_id: str
    content_sha256: str
    time_start: int
    time_end: int
    time_text: str
    context: RelativeMonthContext


@dataclass(frozen=True, slots=True)
class TimeMentionEvidence:
    time_id: str
    start: int
    end: int
    text: str
    normalized_value: str | None
    normalization_status: str  # GOLD, SOURCE_RULE, UNRESOLVED
    relative_month_context: RelativeMonthContext | None = None
    normalization_reason: str | None = None


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
    projection_safe: bool
    projection_reason: str
    normalization_contexts: tuple[RelativeMonthContext, ...] = ()
    normalization_reason: str | None = None

    @property
    def normalization_context_ids(self) -> tuple[str, ...]:
        return tuple(row.evidence_id for row in self.normalization_contexts)

    @property
    def normalization_context_provenance(self) -> tuple[str, ...]:
        return tuple(row.provenance for row in self.normalization_contexts)


@dataclass(frozen=True, slots=True)
class TimeProjectionDecision:
    eligible: bool
    reason: str


def _ko_anchor(groups: tuple[str | None, str | None, str | None]) -> tuple[str | None, str]:
    year, month, day = groups
    candidate = year + ("-" + month.zfill(2) if month else "") + (
        "-" + day.zfill(2) if day else "")
    try:
        return parse_canonical_time(candidate).value, "SOURCE_EXPLICIT"
    except ValueError:
        return None, "INVALID_SOURCE_DATE"


def _published_anchor(published_at: str | None, marker: re.Match[str] | None) -> tuple[datetime | None, str | None]:
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
    return anchor, None


def _relative_month_context_error(context: RelativeMonthContext | None, *,
                                  published_at: str | None,
                                  article: RawArticle | None = None) -> str | None:
    if context is None:
        return "MISSING_CONFIRMED_RELATIVE_MONTH"
    if (not 1 <= context.year <= 9999 or not 1 <= context.month <= 12 or
            context.provenance not in RELATIVE_MONTH_CONTEXT_PROVENANCE or
            not context.evidence_id):
        return "INVALID_RELATIVE_MONTH_CONTEXT"
    if context.provenance == "PUBLISHED_AT_MONTH_CONFIRMED":
        anchor, error = _published_anchor(published_at, None)
        if (anchor is None or error is not None or
                (context.year, context.month) != (anchor.year, anchor.month) or
                context.evidence_text != published_at or
                context.evidence_start is not None or context.evidence_end is not None):
            return "INVALID_RELATIVE_MONTH_CONTEXT"
        return None
    if (context.evidence_text is None or
            not isinstance(context.evidence_start, int) or
            not isinstance(context.evidence_end, int) or
            context.evidence_start < 0 or
            context.evidence_end != context.evidence_start + len(context.evidence_text)):
        return "INVALID_RELATIVE_MONTH_CONTEXT"
    references = _KO_MONTH_REFERENCE.findall(context.evidence_text)
    if (len(references) != 1 or
            tuple(map(int, references[0])) != (context.year, context.month)):
        return "INVALID_RELATIVE_MONTH_CONTEXT"
    if article is not None and (
            context.evidence_end > len(article.content) or
            article.content[context.evidence_start:context.evidence_end] != context.evidence_text):
        return "INVALID_RELATIVE_MONTH_CONTEXT"
    return None


def index_relative_month_context_bindings(
        article: RawArticle,
        bindings: Sequence[RelativeMonthContextBinding],
) -> dict[tuple[int, int, str], RelativeMonthContext]:
    """Validate caller evidence and index it by one exact relative-day span.

    Article identity and content digest prevent reuse across source snapshots.
    Both the target Time span and the context's own source/published-at evidence
    are checked before any model work consumes the binding.
    """
    indexed: dict[tuple[int, int, str], RelativeMonthContext] = {}
    for binding in bindings:
        if (binding.article_id != article.article_id or
                binding.content_sha256 != article.content_sha256):
            raise ValueError("relative-month binding belongs to a different article snapshot")
        if (not 0 <= binding.time_start < binding.time_end <= len(article.content) or
                binding.time_end != binding.time_start + len(binding.time_text) or
                article.content[binding.time_start:binding.time_end] != binding.time_text):
            raise ValueError("relative-month binding lost exact Time source grounding")
        relative = _ZONE.sub("", binding.time_text.strip()).strip()
        if not (_LAST_DAY.fullmatch(relative) or
                _CONTEXTUAL_LAST_DAY_FROM.fullmatch(relative)):
            raise ValueError("relative-month binding targets a Time span that needs no month context")
        if _relative_month_context_error(
                binding.context, published_at=article.published_at, article=article) is not None:
            raise ValueError("relative-month binding lacks exact confirmed context evidence")
        key = (binding.time_start, binding.time_end, binding.time_text)
        if key in indexed:
            raise ValueError("duplicate relative-month binding for one Time occurrence")
        indexed[key] = binding.context
    return indexed


def classify_time_projection_semantics(text: str) -> TimeProjectionDecision:
    """raw TimeMention이 단일 service calendar anchor로 안전한지 판정한다.

    이 판정은 attachment나 normalized value 형식을 대신하지 않는다. 명시적
    calendar literal과 r06.0이 승인한 명확한 ``~부터`` 시작 anchor만
    allowlist하며 기타 boundary/operator는 보수적으로 거절한다.
    """
    source = text.strip()
    if not source:
        return TimeProjectionDecision(False, "EMPTY_RAW_TIME")
    if _YEAR.fullmatch(source) or _MONTH.fullmatch(source) or _DAY.fullmatch(source):
        try:
            parse_canonical_time(source)
        except ValueError:
            return TimeProjectionDecision(False, "INVALID_RAW_CALENDAR_DATE")
        return TimeProjectionDecision(True, "SAFE_CALENDAR_LITERAL")
    ko = _KO_DATE.fullmatch(source)
    if ko:
        value, _reason = _ko_anchor(ko.groups())
        return (TimeProjectionDecision(True, "SAFE_CALENDAR_LITERAL") if value is not None
                else TimeProjectionDecision(False, "INVALID_RAW_CALENDAR_DATE"))
    relative_source = _ZONE.sub("", source).strip()
    if _CLEAR_RELATIVE_CALENDAR.fullmatch(relative_source):
        return TimeProjectionDecision(True, "SAFE_RELATIVE_CALENDAR_ANCHOR")
    boundary = _KO_DATE_BOUNDARY.fullmatch(source)
    if boundary and boundary.group(4) == "부터":
        value, _reason = _ko_anchor(boundary.groups()[:3])
        return (TimeProjectionDecision(True, "SAFE_EXPLICIT_START_ANCHOR") if value is not None
                else TimeProjectionDecision(False, "INVALID_RAW_CALENDAR_DATE"))
    if _LAST_DAY.fullmatch(source) and source.endswith("부터"):
        return TimeProjectionDecision(True, "SAFE_RELATIVE_START_ANCHOR")
    if _CONTEXTUAL_LAST_DAY_FROM.fullmatch(source):
        return TimeProjectionDecision(True, "SAFE_CONTEXTUAL_START_ANCHOR")
    if "이전" in source or "이후" in source:
        return TimeProjectionDecision(False, "UNAPPROVED_BOUNDARY_OPERATOR")
    if "부터" in source:
        return TimeProjectionDecision(False, "AMBIGUOUS_START_BOUNDARY")
    if _AMBIGUOUS_TEMPORAL.search(source):
        return TimeProjectionDecision(False, "AMBIGUOUS_OR_NONPOINT_SEMANTICS")
    return TimeProjectionDecision(False, "UNRECOGNIZED_PROJECTION_SEMANTICS")


def time_public_projection_decision(occurrence: TemporalOccurrence, *,
                                    attached_to_event: bool) -> TimeProjectionDecision:
    """Attachment, 지원 calendar value, raw semantics의 AND 계약을 적용한다."""
    if not attached_to_event:
        return TimeProjectionDecision(False, "NO_EVENT_ATTACHMENT")
    if not occurrence.calendar_eligible:
        return TimeProjectionDecision(False, "UNSUPPORTED_CALENDAR_VALUE")
    if not occurrence.projection_safe:
        return TimeProjectionDecision(False, occurrence.projection_reason)
    return TimeProjectionDecision(True, "PROJECTABLE")


def infer_source_time(text: str, published_at: str | None, *,
                      relative_month_context: RelativeMonthContext | None = None
                      ) -> tuple[str | None, str]:
    """raw span을 보존하며 명시적 precision/calendar anchor만 반환한다."""
    source = text.strip()
    try:
        return parse_canonical_time(source).value, "SOURCE_EXPLICIT"
    except ValueError:
        pass
    ko = _KO_DATE.fullmatch(source)
    if ko:
        return _ko_anchor(ko.groups())
    boundary = _KO_DATE_BOUNDARY.fullmatch(source)
    if boundary:
        return _ko_anchor(boundary.groups()[:3])
    marker = _ZONE.search(source)
    relative = _ZONE.sub("", source).strip()
    last_day = _LAST_DAY.fullmatch(relative) or _CONTEXTUAL_LAST_DAY_FROM.fullmatch(relative)
    if relative not in ("오늘", "어제", "지난달") and not last_day:
        return None, "INSUFFICIENT_SOURCE_OR_UNSUPPORTED_PRECISION"
    if last_day:
        context_error = _relative_month_context_error(
            relative_month_context, published_at=published_at)
        if context_error is not None:
            return None, context_error
        if relative_month_context is None:  # defensive; validator above is fail-closed
            return None, "MISSING_CONFIRMED_RELATIVE_MONTH"
        requested_day = int(last_day.group(1))
        try:
            return date(relative_month_context.year, relative_month_context.month,
                        requested_day).isoformat(), "SOURCE_RELATIVE_ANCHORED"
        except ValueError:
            return None, "INVALID_SOURCE_DATE"
    anchor, error = _published_anchor(published_at, marker)
    if anchor is None:
        return None, error or "MISSING_PUBLISHED_AT"
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
        context_error = (_relative_month_context_error(
            row.relative_month_context, published_at=article.published_at, article=article)
            if row.relative_month_context is not None else None)
        if context_error is not None:
            raise ValueError("Time relative-month context lacks exact confirmed evidence")
        inferred_value, inferred_reason = infer_source_time(
            row.text, article.published_at,
            relative_month_context=row.relative_month_context)
        if row.normalization_status == "SOURCE_RULE" and (
                row.normalized_value is None or inferred_value != row.normalized_value or
                (row.normalization_reason is not None and
                 row.normalization_reason != inferred_reason)):
            raise ValueError("source-derived Time value exceeds exact textual/anchor evidence")
        if row.normalization_status == "UNRESOLVED" and row.normalization_reason is not None and (
                inferred_value is not None or row.normalization_reason != inferred_reason):
            raise ValueError("unresolved Time reason differs from source/context evidence")
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
        reasons = {row.normalization_reason for row in members
                   if row.normalization_reason is not None}
        if len(reasons) > 1:
            raise ValueError("same Time occurrence has conflicting normalization reason")
        eligible = calendar_eligible(value)
        semantics = classify_time_projection_semantics(article.content[start:end])
        context_by_id: dict[str, RelativeMonthContext] = {}
        for member in members:
            context = member.relative_month_context
            if context is None:
                continue
            if context.evidence_id in context_by_id and context_by_id[context.evidence_id] != context:
                raise ValueError("same Time occurrence has conflicting relative-month evidence")
            context_by_id[context.evidence_id] = context
        contexts = tuple(sorted(context_by_id.values(),
                                key=lambda row: (row.evidence_id, row.provenance)))
        occurrence = TemporalOccurrence(
            local_id, member_ids, start, end, article.content[start:end], value,
            parsed.granularity if parsed else None, next(iter(statuses)), event_ids,
            "ATTACHED" if event_ids else "UNATTACHED", eligible, False,
            semantics.eligible, semantics.reason, contexts,
            next(iter(reasons)) if reasons else None)
        decision = time_public_projection_decision(occurrence, attached_to_event=bool(event_ids))
        output.append(TemporalOccurrence(
            occurrence.local_id, occurrence.evidence_ids, occurrence.start, occurrence.end,
            occurrence.text, occurrence.normalized_value, occurrence.granularity,
            occurrence.normalization_status, occurrence.attached_event_ids,
            occurrence.attachment_status, occurrence.calendar_eligible, decision.eligible,
            occurrence.projection_safe, occurrence.projection_reason,
            occurrence.normalization_contexts, occurrence.normalization_reason))
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
