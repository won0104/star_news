"""v3 Event/Statement의 원문 근거 deterministic 표시문 생성.

학습 target/head가 아니다. 단일 원문 clause 밖의 role·시점·서술을 조합하지
않으며 canonical 결과를 identity 판정에 쓰지 않는다. evidence offset은 입력에 남는다.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from runtime.v3_pretraining.event_identity import LocalEventState
from runtime.v3_pretraining.source_layout import RawArticle


RULE_VERSION = "v3-extractive-canonical-r1"
STATEMENT_TYPES = frozenset({"FORECAST", "CLAIM", "EVALUATION"})
_FINITE = re.compile(r"(?:다|요|니다|했다|된다|한다|됐다|였다|이다|있다|없다|라고 밝혔다|라고 말했다)[.!?…]*$", re.UNICODE)
_EVENT_UNSAFE = re.compile(r"(?:전망|예상|추정|가능|것으로|것이라|라고|이라고|했다며)")
_MULTI_CLAUSE = re.compile(r"(?:그러나|하지만|반면|한편|그리고|반대로|이어서)")
_DELIMITERS = frozenset({".", "!", "?", ";", "\n", ",", "。", "！", "？"})
_OPEN_QUOTES = {"“": "”", "‘": "’", "\"": "\"", "'": "'"}
_CLOSE_QUOTES = {value: key for key, value in _OPEN_QUOTES.items() if key != value}


@dataclass(frozen=True, slots=True)
class SourceGrounding:
    evidence_id: str
    start: int
    end: int
    text: str

    def validate(self, raw: RawArticle) -> None:
        if (not self.evidence_id or not 0 <= self.start < self.end <= len(raw.content)
                or raw.content[self.start:self.end] != self.text):
            raise ValueError("canonical grounding lost exact source offset/text")


@dataclass(frozen=True, slots=True)
class GroundedStatement:
    local_id: str
    statement_type: str
    grounding: SourceGrounding
    assertor: SourceGrounding | None = None

    def validate(self, raw: RawArticle) -> None:
        if not self.local_id or self.statement_type not in STATEMENT_TYPES:
            raise ValueError("Statement identity/type outside r05.3 contract")
        self.grounding.validate(raw)
        if self.assertor is not None:
            self.assertor.validate(raw)


@dataclass(frozen=True, slots=True)
class CanonicalTextResult:
    text: str
    status: str  # SOURCE_COMPLETE, SOURCE_CLAUSE_EXPANDED, FALLBACK_SOURCE_SPAN, INSUFFICIENT_CONTEXT
    rule_version: str
    used_grounding_ids: tuple[str, ...]
    audit: tuple[str, ...]


def _complete(text: str) -> bool:
    return bool(_FINITE.search(text.strip().rstrip("\"'”’ ").strip()))


def _clause_bounds(content: str, start: int, end: int) -> tuple[int, int] | None:
    """quote 내부 구두점과 소수점은 분리하지 않는 단일 contiguous clause."""
    boundaries = [0]
    quote_stack: list[str] = []
    for index, char in enumerate(content):
        if char in _CLOSE_QUOTES and quote_stack and quote_stack[-1] == char:
            quote_stack.pop()
            continue
        if char in _OPEN_QUOTES:
            closing = _OPEN_QUOTES[char]
            if quote_stack and quote_stack[-1] == closing:
                quote_stack.pop()
            else:
                quote_stack.append(closing)
            continue
        if char in _DELIMITERS and not quote_stack:
            if char == "." and 0 < index < len(content) - 1 and (
                    content[index - 1].isdigit() and content[index + 1].isdigit()):
                continue
            boundaries.append(index + 1)
    boundaries.append(len(content))
    if quote_stack:
        return None
    for left, right in zip(boundaries, boundaries[1:]):
        if left <= start < end <= right:
            while left < right and content[left].isspace():
                left += 1
            while right > left and content[right - 1].isspace():
                right -= 1
            return (left, right) if left <= start < end <= right else None
    return None


def _result(text: str, status: str, used: tuple[str, ...],
            audit: tuple[str, ...] = ()) -> CanonicalTextResult:
    return CanonicalTextResult(text, status, RULE_VERSION, used, audit)


def canonicalize_event(raw: RawArticle, event: LocalEventState) -> CanonicalTextResult:
    """대표 member의 원문만 사용한다; 다른 member의 role을 섞지 않는다."""
    if (not event.local_id or not 0 <= event.start < event.end <= len(raw.content)
            or raw.content[event.start:event.end] != event.text):
        raise ValueError("Event canonicalization needs exact representative source")
    for start, end, text, _member_id in event.triggers:
        if not 0 <= start < end <= len(raw.content) or raw.content[start:end] != text:
            raise ValueError("Event trigger source changed")
    for role in event.roles:
        if not 0 <= role.start < role.end <= len(raw.content) or raw.content[role.start:role.end] != role.text:
            raise ValueError("Event role source changed")
    source = event.text.strip()
    used = (event.representative_member_id,)
    representative_roles = tuple(role for role in event.roles
                                 if event.representative_member_id in role.member_ids)
    needs_context = (" " not in source and len(source) <= 20) or any(
        not event.start <= role.start < role.end <= event.end
        for role in representative_roles)
    if not source:
        return _result(event.text, "INSUFFICIENT_CONTEXT", used, ("EMPTY_SOURCE_SPAN",))
    if _complete(source) and not needs_context:
        return _result(source, "SOURCE_COMPLETE", used,
                       ("CLUSTER_CONFLICT_REPRESENTATIVE_ONLY",) if event.conflict_flags else ())
    if event.conflict_flags:
        return _result(source, "FALLBACK_SOURCE_SPAN", used,
                       ("CLUSTER_CONFLICT_NO_FRAME_COMPOSITION",))
    bounds = _clause_bounds(raw.content, event.start, event.end)
    if bounds is None:
        return _result(source, "INSUFFICIENT_CONTEXT", used, ("QUOTE_OR_CLAUSE_BOUNDARY",))
    left, right = bounds
    clause = raw.content[left:right].strip()
    if (len(clause) > 160 or not _complete(clause) or _MULTI_CLAUSE.search(clause)
            or _EVENT_UNSAFE.search(clause)):
        return _result(source, "FALLBACK_SOURCE_SPAN", used,
                       ("UNSAFE_OR_INCOMPLETE_CLAUSE",))
    if any(not left <= role.start < role.end <= right for role in representative_roles):
        return _result(source, "INSUFFICIENT_CONTEXT", used,
                       ("ROLE_OUTSIDE_SINGLE_CLAUSE",))
    if event.triggers and not any(left <= start < end <= right and member_id ==
                                  event.representative_member_id
                                  for start, end, _text, member_id in event.triggers):
        return _result(source, "INSUFFICIENT_CONTEXT", used,
                       ("TRIGGER_OUTSIDE_SINGLE_CLAUSE",))
    if clause == source:
        return _result(source, "FALLBACK_SOURCE_SPAN", used, ("NO_SAFE_EXPANSION",))
    evidence_ids = tuple(sorted({eid for role in representative_roles for eid in role.evidence_ids}))
    return _result(clause, "SOURCE_CLAUSE_EXPANDED", used + evidence_ids,
                   (f"SOURCE_RANGE:{left}:{right}",))


def canonicalize_statement(raw: RawArticle,
                           statement: GroundedStatement) -> CanonicalTextResult:
    """FORECAST/CLAIM/EVALUATION의 원문 modality·부정·인용을 바꾸지 않는다."""
    statement.validate(raw)
    source = statement.grounding.text.strip()
    used = (statement.grounding.evidence_id,)
    if not source:
        return _result(statement.grounding.text, "INSUFFICIENT_CONTEXT", used,
                       ("EMPTY_SOURCE_SPAN",))
    if _complete(source):
        return _result(source, "SOURCE_COMPLETE", used)
    bounds = _clause_bounds(raw.content, statement.grounding.start,
                            statement.grounding.end)
    if bounds is None:
        return _result(source, "INSUFFICIENT_CONTEXT", used,
                       ("QUOTE_OR_CLAUSE_BOUNDARY",))
    left, right = bounds
    clause = raw.content[left:right].strip()
    if (len(clause) > 160 or not _complete(clause) or _MULTI_CLAUSE.search(clause)):
        return _result(source, "FALLBACK_SOURCE_SPAN", used,
                       ("UNSAFE_OR_INCOMPLETE_CLAUSE",))
    if statement.assertor is not None and left <= statement.assertor.start < statement.assertor.end <= right:
        used += (statement.assertor.evidence_id,)
    if clause == source:
        return _result(source, "FALLBACK_SOURCE_SPAN", used, ("NO_SAFE_EXPANSION",))
    return _result(clause, "SOURCE_CLAUSE_EXPANDED", used,
                   (f"SOURCE_RANGE:{left}:{right}",))
