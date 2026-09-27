"""final scalar grounding만 사용하는 deterministic 표시문 정규화.

canonical text는 identity나 학습 target이 아니다. 원문 evidence는 exact span으로
유지하고, 표시문에서 수행한 절 선택·어미 정리·grounded role 삽입은 별도 edit
provenance로 기록한다. neural representation이나 외부 API를 사용하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from runtime.v3_pretraining.event_identity import (EventMemberGrounding, LocalEventState,
                                                   LocalRoleFact)
from runtime.v3_pretraining.source_layout import RawArticle


RULE_VERSION = "v3-span-first-minimal-edit-r06-v4"
STATEMENT_TYPES = frozenset({"FORECAST", "CLAIM", "EVALUATION"})
_FINITE = re.compile(
    r"(?:다|요|니다|습니다|했다|됐다|되었다|한다|된다|였다|이다|있다|없다)[.!?…]*$",
    re.UNICODE,
)
_NOMINAL_EVENT = re.compile(
    r"(?:발표|공개|체결|임명|선출|교체|출범|착공|완공|폐쇄|합병|인수|매각|출시|"
    r"승인|결정|사망|우승|개최|증가|감소|확대|축소)$"
)
_PRONOUN_SUBJECT = re.compile(r"^(?:그는|그녀는|그들은|이들은|그것은|이는)\s*")
_PRONOUN_TARGET = re.compile(r"(?:^|(?<=\s))(?:이를|그것을)(?=\s|$)")
_PRONOUN_ROLE_TEXT = {
    "그는": frozenset({"그", "그는"}),
    "그녀는": frozenset({"그녀", "그녀는"}),
    "그들은": frozenset({"그들", "그들은"}),
    "이들은": frozenset({"이들", "이들은"}),
    "그것은": frozenset({"그것", "그것은"}),
    "이는": frozenset({"이", "이는"}),
    "이를": frozenset({"이", "이를"}),
    "그것을": frozenset({"그것", "그것을"}),
}
_CONDITION = re.compile(r"(?:지\s*않으면|[가-힣]+면|더라도|경우|때에는|때는)")
_MODAL = re.compile(r"(?:전망|예상|추정|가능|수\s*있|것으로|것이라|계획|방침|주장|밝혔|말했)")
_NEGATION = re.compile(r"(?:지\s*않|않았|아니|없(?:다|었)|못(?:했|하|할))")
_SAFE_ACTIVE = re.compile(r"(?:공개|발표|완성|진행|착수|체결|개발|제작|확대|축소|늘렸|줄였|즐거워|들어갔)")
_PASSIVE = re.compile(r"(?:됐|되었|된|임명|대체|선출|체결됐|공개됐)")
_CONNECTIVE = re.compile(
    r"(?:하지\s*않았으며|하지\s*않았고|했으며|했고|됐으며|됐고|되었으며|되었고|"
    r"있었으며|있었고|없었으며|없었고|이었으며|이었고|였으며|였고)(?=\s|$)"
)
_DISCOURSE = re.compile(r"\s+(?=(?:그러나|하지만|반면|한편|반대로|이어서|이후)\s)")
_ENDING_MAP = (
    ("하지 않았으며", "하지 않았다"), ("하지 않았고", "하지 않았다"),
    ("되었으며", "되었다"), ("되었고", "되었다"),
    ("있었으며", "있었다"), ("있었고", "있었다"),
    ("없었으며", "없었다"), ("없었고", "없었다"),
    ("이었으며", "이었다"), ("이었고", "이었다"),
    ("였으며", "였다"), ("였고", "였다"),
    ("됐으며", "됐다"), ("됐고", "됐다"),
    ("했으며", "했다"), ("했고", "했다"),
)
_SAFE_HA_STEMS = (
    "완성", "발표", "공개", "체결", "확인", "결정", "승인", "교체", "임명",
    "선출", "개최", "출시", "증가", "감소", "확대", "축소", "진행", "대체",
)
_OPEN_QUOTES = {"“": "”", "‘": "’", '"': '"', "'": "'"}
_OPEN_BRACKETS = {"(": ")", "[": "]", "{": "}"}
_CLOSE_QUOTES = {value for value in _OPEN_QUOTES.values()}
_CLOSE_BRACKETS = {value for value in _OPEN_BRACKETS.values()}
_SENTENCE_END = frozenset({".", "!", "?", ";", "\n", "。", "！", "？"})
_CONTRAST = re.compile(r"(?:지만|으나|그러나|하지만|반면|반대로|불구)")
_QUANTITY = re.compile(r"(?:\d|%|각각|일부|전부|절반|이상|이하)")
_TEMPORAL_DETAIL = re.compile(r"(?:오늘|어제|내년|작년|\d{4}년|부터|이후|이전|동안)")
_NOMINAL_FRAGMENT_END = re.compile(r"(?:은|는|이|가|을|를|의|에|에서|으로|와|과|며|고)$")
_EVENT_PAST_CONNECTIVE = re.compile(
    r"(?P<tense>았|었|였|했|됐)(?P<link>으며|지만|는데|으나|고)$"
)
_CONTEXT_HA_ENDINGS = ("하여서", "하는데", "하지만", "하여", "해서", "하고", "하며", "해")
_CONTEXT_DOE_ENDINGS = ("되어서", "되지만", "되는데", "되어", "돼서", "되고", "되며", "돼")
_CONTEXT_VERB_STEMS = frozenset((*_SAFE_HA_STEMS, "구매"))
_FOLLOWING_PAST = re.compile(r"[가-힣]+(?:았|었|였|했|됐)다$")
_FOLLOWING_PRESENT = re.compile(r"[가-힣]+(?:한다|된다|는다|난다)$")
_CASE_PARTICLES = frozenset("은는이가을를의에와과도만")
_SCOPE_DELIMITERS = frozenset((*_OPEN_QUOTES, *_CLOSE_QUOTES,
                               *_OPEN_BRACKETS, *_CLOSE_BRACKETS))


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
class CanonicalEdit:
    rule_id: str
    change_type: str
    source_start: int
    source_end: int
    source_text: str
    display_start: int
    display_end: int
    replacement: str


@dataclass(frozen=True, slots=True)
class CanonicalTextResult:
    text: str
    status: str
    rule_version: str
    used_grounding_ids: tuple[str, ...]
    audit: tuple[str, ...]
    source_groundings: tuple[SourceGrounding, ...] = ()
    edits: tuple[CanonicalEdit, ...] = ()
    fact_invariants: tuple[str, ...] = (
        "SOURCE_EVIDENCE_EXACT", "NO_NEW_FACT", "IDENTITY_UNCHANGED",
        "NEGATION_MODALITY_SCOPE_PRESERVED",
    )


@dataclass(frozen=True, slots=True)
class CanonicalSourceView:
    """요청당 한 번 계산하는 sentence/clause와 quote/parenthesis scope index."""

    article_version_id: str
    content_sha256: str
    sentence_ranges: tuple[tuple[int, int], ...]
    clause_ranges: tuple[tuple[int, int], ...]
    scope_depths: tuple[int, ...]

    @classmethod
    def build(cls, raw: RawArticle) -> "CanonicalSourceView":
        content = raw.content
        quote_stack: list[str] = []
        bracket_stack: list[str] = []
        depths: list[int] = []
        boundaries = [0]
        for index, char in enumerate(content):
            depths.append(len(quote_stack) + len(bracket_stack))
            if char in _CLOSE_QUOTES and quote_stack and quote_stack[-1] == char:
                quote_stack.pop()
            elif char in _OPEN_QUOTES:
                closing = _OPEN_QUOTES[char]
                if quote_stack and quote_stack[-1] == closing:
                    quote_stack.pop()
                else:
                    quote_stack.append(closing)
            elif char in _CLOSE_BRACKETS and bracket_stack and bracket_stack[-1] == char:
                bracket_stack.pop()
            elif char in _OPEN_BRACKETS:
                bracket_stack.append(_OPEN_BRACKETS[char])
            if char in _SENTENCE_END and not quote_stack and not bracket_stack:
                if char == "." and 0 < index < len(content) - 1 and (
                        content[index - 1].isdigit() and content[index + 1].isdigit()):
                    continue
                boundaries.append(index + 1)
        if boundaries[-1] != len(content):
            boundaries.append(len(content))
        sentences_list = []
        for left, right in zip(boundaries, boundaries[1:]):
            trimmed = _trim_range(content, left, right)
            if trimmed[0] < trimmed[1]:
                sentences_list.append(trimmed)
        sentences = tuple(sentences_list)
        clauses: list[tuple[int, int]] = []
        for left, right in sentences:
            cuts = {left, right}
            segment = content[left:right]
            for match in _CONNECTIVE.finditer(segment):
                absolute = left + match.end()
                if _scope_depth(depths, absolute - 1) == 0:
                    cuts.add(absolute)
            for match in _DISCOURSE.finditer(segment):
                absolute = left + match.end()
                if _scope_depth(depths, absolute) == 0:
                    cuts.add(absolute)
            ordered = sorted(cuts)
            for first, last in zip(ordered, ordered[1:]):
                trimmed = _trim_range(content, first, last)
                if trimmed[0] < trimmed[1]:
                    clauses.append(trimmed)
        return cls(raw.article_version_id, raw.content_sha256, sentences,
                   tuple(clauses), tuple(depths))

    def require(self, raw: RawArticle) -> None:
        if (self.article_version_id != raw.article_version_id or
                self.content_sha256 != raw.content_sha256):
            raise ValueError("canonical source view belongs to a different article")

    def containing(self, start: int, end: int) -> tuple[int, int] | None:
        for left, right in self.clause_ranges:
            if left <= start < end <= right:
                return left, right
        for left, right in self.sentence_ranges:
            if left <= start < end <= right:
                return left, right
        return None

    def scope_depth(self, position: int) -> int:
        return _scope_depth(self.scope_depths, position)


def _scope_depth(depths: tuple[int, ...] | list[int], position: int) -> int:
    return depths[position] if 0 <= position < len(depths) else 0


def _trim_range(content: str, start: int, end: int) -> tuple[int, int]:
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return start, end


def _grounding(raw: RawArticle, evidence_id: str, start: int, end: int) -> SourceGrounding:
    row = SourceGrounding(evidence_id, start, end, raw.content[start:end])
    row.validate(raw)
    return row


def _deduplicate_groundings(rows: tuple[SourceGrounding, ...]) -> tuple[SourceGrounding, ...]:
    retained: dict[tuple[str, int, int], SourceGrounding] = {}
    for row in rows:
        retained.setdefault((row.evidence_id, row.start, row.end), row)
    return tuple(retained.values())


def _rebase_edits_for_insertion(edits: tuple[CanonicalEdit, ...] | list[CanonicalEdit],
                                position: int, inserted_length: int) -> list[CanonicalEdit]:
    """Map prior display spans through one insertion into the final display string."""
    if position < 0 or inserted_length < 0:
        raise ValueError("canonical display insertion coordinates invalid")
    rebased = []
    for row in edits:
        if row.display_end <= position:
            rebased.append(row)
        elif row.display_start >= position:
            rebased.append(replace(row, display_start=row.display_start + inserted_length,
                                   display_end=row.display_end + inserted_length))
        else:
            rebased.append(replace(row, display_end=row.display_end + inserted_length))
    return rebased


def _rebase_edits_for_replacement(edits: tuple[CanonicalEdit, ...] | list[CanonicalEdit],
                                  start: int, end: int,
                                  replacement_length: int) -> list[CanonicalEdit]:
    """Map prior display spans through a length-changing replacement."""
    if start < 0 or end < start or replacement_length < 0:
        raise ValueError("canonical display replacement coordinates invalid")
    delta = replacement_length - (end - start)
    rebased = []
    for row in edits:
        left, right = row.display_start, row.display_end
        if right <= start:
            rebased.append(row)
        elif left >= end:
            rebased.append(replace(row, display_start=left + delta,
                                   display_end=right + delta))
        elif left <= start and right >= end:
            rebased.append(replace(row, display_end=right + delta))
        else:
            mapped_left = left if left <= start else start
            mapped_right = right + delta if right >= end else start + replacement_length
            rebased.append(replace(row, display_start=mapped_left,
                                   display_end=max(mapped_left, mapped_right)))
    return rebased


def _result(text: str, status: str, groundings: tuple[SourceGrounding, ...],
            audit: tuple[str, ...] = (), edits: tuple[CanonicalEdit, ...] = ()) -> CanonicalTextResult:
    groundings = _deduplicate_groundings(groundings)
    return CanonicalTextResult(text, status, RULE_VERSION,
                               tuple(row.evidence_id for row in groundings), audit,
                               groundings, edits)


def _complete(text: str) -> bool:
    return bool(_FINITE.search(text.strip().rstrip("\"'”’ ").strip()))


def _nominal_complete(text: str) -> bool:
    clean = text.strip().rstrip(".!?…")
    if len(clean) < 3:
        return False
    if _NOMINAL_EVENT.search(clean):
        return True
    # Upstream has already accepted this span as an Event.  Preserve a grounded
    # multi-token nominal situation without restricting it to a hand-written noun
    # inventory, while leaving particle/connective-ended fragments unresolved.
    return bool(re.search(r"\s", clean)) and not _NOMINAL_FRAGMENT_END.search(clean)


def _semantic_signature(text: str) -> tuple[bool, bool, bool, bool]:
    return (bool(_NEGATION.search(text)), bool(_CONDITION.search(text)),
            bool(_MODAL.search(text)), any(char in text for char in _OPEN_QUOTES))


def _event_information_markers(text: str) -> tuple[str, ...]:
    """Return deterministic source-detail markers, not a semantic-quality score."""
    markers = []
    for name, pattern in (("NEGATION", _NEGATION), ("CONDITION", _CONDITION),
                          ("MODALITY", _MODAL), ("CONTRAST", _CONTRAST),
                          ("QUANTITY", _QUANTITY), ("TIME", _TEMPORAL_DETAIL)):
        if pattern.search(text):
            markers.append(name)
    return tuple(markers)


def _punctuate(text: str) -> str:
    return text if text.endswith((".", "!", "?", "…")) else text + "."


def _normalize_ending(text: str, source_start: int) -> tuple[str, CanonicalEdit] | None:
    """명시한 과거 연결/관형 패턴만 완결한다; 조건·미래·가능성은 보류한다."""
    clean = text.strip().rstrip(".!?…")
    if _CONDITION.search(clean) or re.search(r"(?:할|될|일)\s*$", clean):
        return None
    for suffix, replacement in _ENDING_MAP:
        if clean.endswith(suffix):
            stem = clean[:-len(suffix)]
            normalized = _punctuate(stem + replacement)
            source_offset = source_start + len(clean) - len(suffix)
            display_offset = len(stem)
            return normalized, CanonicalEdit(
                "KOREAN_CONNECTIVE_TO_FINITE", "ENDING_REPLACEMENT",
                source_offset, source_offset + len(suffix), suffix,
                display_offset, display_offset + len(replacement), replacement)
    if clean.endswith("된") and any(clean[:-1].endswith(stem) for stem in _SAFE_HA_STEMS):
        normalized = _punctuate(clean[:-1] + "됐다")
        return normalized, CanonicalEdit(
            "KOREAN_RELATIVE_PASSIVE_TO_FINITE", "ENDING_REPLACEMENT",
            source_start + len(clean) - 1, source_start + len(clean), "된",
            len(clean) - 1, len(clean) + 1, "됐다")
    if clean.endswith("한") and any(clean[:-1].endswith(stem) for stem in _SAFE_HA_STEMS):
        normalized = _punctuate(clean[:-1] + "했다")
        return normalized, CanonicalEdit(
            "KOREAN_RELATIVE_HA_TO_FINITE", "ENDING_REPLACEMENT",
            source_start + len(clean) - 1, source_start + len(clean), "한",
            len(clean) - 1, len(clean) + 1, "했다")
    return None


def _event_connective_candidate(source: str) -> tuple[str, str, str] | None:
    """Recognize only enumerated terminal forms, before nominal completion."""
    clean = source.rstrip(".!?…")
    past = _EVENT_PAST_CONNECTIVE.search(clean)
    if past is not None:
        replacement = {"았": "았다", "었": "었다", "였": "였다",
                       "했": "했다", "됐": "됐다"}[past.group("tense")]
        return past.group(0), replacement, "EXPLICIT_PAST"
    token = re.search(r"[가-힣]+$", clean)
    if token is None:
        return None
    for family, endings in (("HA", _CONTEXT_HA_ENDINGS),
                            ("DOE", _CONTEXT_DOE_ENDINGS)):
        for suffix in endings:
            if token.group(0).endswith(suffix) and token.group(0)[:-len(suffix)] in _CONTEXT_VERB_STEMS:
                return suffix, family, "CONTEXT_REQUIRED"
    return None


def _terminal_trigger_matches(raw: RawArticle, event: LocalEventState,
                              member: EventMemberGrounding, suffix: str) -> bool:
    terminal = member.text.rstrip().rstrip(".!?…")
    token = re.search(r"[가-힣]+$", terminal)
    if token is None or not terminal.endswith(suffix):
        return False
    token_start = member.start + token.start()
    terminal_end = member.start + len(terminal)
    suffix_start = terminal_end - len(suffix)
    return any(
        mid == member.member_id and token_start <= start < suffix_start <= end <= terminal_end
        and raw.content[start:end] == text
        for start, end, text, mid in event.triggers
    )


def _following_finite_tense(raw: RawArticle, member: EventMemberGrounding,
                            view: CanonicalSourceView) -> tuple[str, int, int] | None:
    clause = next(((left, right) for left, right in view.clause_ranges
                   if left <= member.start < member.end <= right), None)
    if clause is None or member.end >= clause[1]:
        return None
    following = raw.content[member.end:clause[1]]
    if not following or following[0] in _CASE_PARTICLES or _MODAL.search(following):
        return None
    clean = following.strip().rstrip(".!?…").rstrip()
    if not clean or any(char in _SCOPE_DELIMITERS for char in following):
        return None
    predicate = re.search(r"[가-힣]+$", clean)
    if predicate is None:
        return None
    word = predicate.group(0)
    tense = ("PAST" if _FOLLOWING_PAST.fullmatch(word) else
             "PRESENT" if _FOLLOWING_PRESENT.fullmatch(word) else None)
    if tense is None:
        return None
    predicate_end = member.end + following.rfind(word) + len(word)
    predicate_start = predicate_end - len(word)
    if view.scope_depth(member.end - 1) != view.scope_depth(predicate_start):
        return None
    return tense, predicate_start, predicate_end


def _event_connective_edit(source: str, source_start: int, suffix: str,
                           replacement: str, rule_id: str
                           ) -> tuple[str, CanonicalEdit]:
    clean = source.rstrip(".!?…")
    offset = len(clean) - len(suffix)
    return _punctuate(clean[:offset] + replacement), CanonicalEdit(
        rule_id, "ENDING_REPLACEMENT", source_start + offset,
        source_start + len(clean), suffix, offset, offset + len(replacement),
        replacement)


def _normalize_statement_ending(text: str, source_start: int) -> tuple[str, CanonicalEdit] | None:
    """Finish only enumerated connective forms and an explicit ``-다고`` quote ending."""
    normalized = _normalize_ending(text, source_start)
    if normalized is not None:
        return normalized
    clean = text.strip().rstrip(".!?…")
    if clean.endswith("다고"):
        candidate = clean[:-1]
        if _complete(candidate):
            display_start = len(clean) - len("다고")
            return _punctuate(candidate), CanonicalEdit(
                "KOREAN_QUOTATIVE_DAGO_TO_FINITE", "ENDING_REPLACEMENT",
                source_start + display_start, source_start + len(clean), "다고",
                display_start, display_start + len("다"), "다")
    return None


def _member_groundings(raw: RawArticle, event: LocalEventState) -> tuple[EventMemberGrounding, ...]:
    rows = event.member_groundings or (
        EventMemberGrounding(event.representative_member_id, event.start, event.end, event.text),)
    if {row.member_id for row in rows} != set(event.member_ids):
        raise ValueError("Event canonical member grounding inventory differs from final cluster")
    for row in rows:
        if not 0 <= row.start < row.end <= len(raw.content) or raw.content[row.start:row.end] != row.text:
            raise ValueError("Event canonical member grounding lost exact source")
    return rows


def _validate_event(raw: RawArticle, event: LocalEventState) -> None:
    if (not event.local_id or not 0 <= event.start < event.end <= len(raw.content)
            or raw.content[event.start:event.end] != event.text):
        raise ValueError("Event canonicalization needs exact representative source")
    _member_groundings(raw, event)
    for start, end, text, member_id in event.triggers:
        if (member_id not in event.member_ids or not 0 <= start < end <= len(raw.content)
                or raw.content[start:end] != text):
            raise ValueError("Event trigger source changed")
    for role in event.roles:
        if (not set(role.member_ids) <= set(event.member_ids) or
                not 0 <= role.start < role.end <= len(raw.content) or
                raw.content[role.start:role.end] != role.text):
            raise ValueError("Event role source changed")


def _range_groundings(raw: RawArticle, event: LocalEventState, member_id: str,
                      left: int, right: int) -> tuple[SourceGrounding, ...]:
    rows = [_grounding(raw, f"CLAUSE:{left}:{right}", left, right)]
    rows.extend(_grounding(raw, evidence_id, role.start, role.end)
                for role in event.roles if member_id in role.member_ids and
                left <= role.start < role.end <= right for evidence_id in role.evidence_ids)
    rows.extend(_grounding(raw, f"TRIGGER:{mid}", start, end)
                for start, end, _text, mid in event.triggers
                if mid == member_id and left <= start < end <= right)
    return _deduplicate_groundings(tuple(rows))


def _event_anchor(raw: RawArticle, event: LocalEventState, member: EventMemberGrounding,
                  view: CanonicalSourceView) -> CanonicalTextResult:
    source = member.text.strip()
    base = (_grounding(raw, member.member_id, member.start, member.end),)
    markers = _event_information_markers(source)
    trigger_only = any(member.start == start and member.end == end and member.member_id == mid
                       for start, end, _text, mid in event.triggers)
    bare_predicate = trigger_only and " " not in source and not _nominal_complete(source)
    audit = ("SPAN_FIRST_SOURCE_MEMBER", f"SOURCE_DETAIL_MARKERS:{','.join(markers) or 'NONE'}")
    if source and _complete(source) and not bare_predicate:
        return _result(source, "SOURCE_COMPLETE", base,
                       audit)
    connective = _event_connective_candidate(source) if source else None
    if connective is not None:
        suffix, replacement, kind = connective
        if not _terminal_trigger_matches(raw, event, member, suffix):
            return _result(source, "FALLBACK_SOURCE_SPAN", base,
                           audit + ("CONNECTIVE_TERMINAL_TRIGGER_UNSUPPORTED",))
        if kind == "CONTEXT_REQUIRED":
            following = _following_finite_tense(raw, member, view)
            if following is None:
                return _result(source, "FALLBACK_SOURCE_SPAN", base,
                               audit + ("CONNECTIVE_FOLLOWING_TENSE_UNAVAILABLE",))
            tense, predicate_start, predicate_end = following
            replacement = ("했다" if replacement == "HA" else "됐다") if tense == "PAST" else (
                "한다" if replacement == "HA" else "된다")
            rule_id = "KOREAN_CONTEXTUAL_CONNECTIVE_TO_FINITE"
            context_audit = (f"FOLLOWING_FINITE_PREDICATE:{predicate_start}:{predicate_end}:{tense}",)
        else:
            rule_id = "KOREAN_CONNECTIVE_TO_FINITE"
            context_audit = ()
        text, edit = _event_connective_edit(
            source, member.start + len(member.text) - len(member.text.lstrip()),
            suffix, replacement, rule_id)
        return _result(text, "ENDING_NORMALIZED", base,
                       audit + context_audit + (edit.rule_id,), (edit,))
    normalized = _normalize_ending(source, member.start) if source else None
    if normalized is not None:
        text, edit = normalized
        return _result(text, "ENDING_NORMALIZED", base,
                       audit + (edit.rule_id,), (edit,))
    if source and _nominal_complete(source) and not bare_predicate:
        return _result(source, "SOURCE_COMPLETE", base,
                       audit + ("NOMINAL_EVENT_PRESERVED",))
    if not bare_predicate:
        return _result(source, "FALLBACK_SOURCE_SPAN", base,
                       audit + ("UNSAFE_ENDING_OR_INCOMPLETE_EVENT_SPAN",))
    bounds = view.containing(member.start, member.end)
    if bounds is None:
        return _result(member.text, "INSUFFICIENT_CONTEXT", base,
                       audit + ("CLAUSE_BOUNDARY_UNAVAILABLE",))
    left, right = bounds
    clause_raw = raw.content[left:right]
    clause = clause_raw.strip()
    clause_start = left + len(clause_raw) - len(clause_raw.lstrip())
    clause_end = clause_start + len(clause)
    if (clause_start, clause_end) == (member.start, member.end):
        return _result(source, "INSUFFICIENT_CONTEXT", base,
                       audit + ("BARE_PREDICATE_WITHOUT_SOURCE_CLAUSE",))
    if _MODAL.search(clause) and not _MODAL.search(source):
        return _result(source, "FALLBACK_SOURCE_SPAN", base,
                       audit + ("REPORTING_OR_MODAL_SCOPE_NOT_EVENT_FACT",))
    normalized = _normalize_ending(clause, clause_start)
    grounds = _range_groundings(raw, event, member.member_id, left, right)
    selection = CanonicalEdit("MINIMAL_SOURCE_CLAUSE", "CLAUSE_SELECTION",
                              left, right, raw.content[left:right], 0, len(clause), clause)
    if normalized is not None:
        text, edit = normalized
        # CLAUSE_SELECTION owns the whole transformed clause, including punctuation
        # added by ending normalization, rather than only the suffix replacement.
        selection = replace(selection, display_end=len(text))
        return _result(text, "ENDING_NORMALIZED", grounds,
                       audit + ("BARE_PREDICATE_MINIMAL_CLAUSE", edit.rule_id),
                       (selection, edit))
    if _complete(clause) or _nominal_complete(clause):
        return _result(clause, "SOURCE_CLAUSE_EXPANDED", grounds,
                       audit + ("BARE_PREDICATE_MINIMAL_CLAUSE",), (selection,))
    return _result(source, "INSUFFICIENT_CONTEXT", base,
                   audit + ("BARE_PREDICATE_CLAUSE_UNSUPPORTED",))


def _anchor_rank(result: CanonicalTextResult, member: EventMemberGrounding,
                 representative_id: str) -> tuple[int, int, int, int, int]:
    direct_span = int(result.status in ("SOURCE_COMPLETE", "ENDING_NORMALIZED"))
    readable = int(_complete(result.text) or _nominal_complete(result.text))
    information = len(_event_information_markers(member.text))
    source_usable = int(bool(direct_span and readable))
    # A complete/explicitly normalized source outranks an unsupported fragment.
    # Among usable source members, detail markers can outrank representative
    # status; length is never used as a quality proxy.
    return (source_usable, information, direct_span,
            int(member.member_id == representative_id), -member.start)


def _strip_particle(text: str) -> str:
    clean = text.strip()
    # 단일 음절 조사처럼 보이는 이름 끝 글자는 제거하지 않는다. role endpoint span은
    # 보통 Entity mention 자체이며, 명시적인 복합 격표지만 안전하게 정리한다.
    return re.sub(r"(?:에서는|으로는|에게는|부터는|까지는|에서|에게|으로|로)$", "", clean)


def _has_batchim(text: str) -> bool:
    if not text:
        return False
    code = ord(text[-1]) - 0xAC00
    return 0 <= code <= 11171 and code % 28 != 0


def _unique_resolved_roles(roles: tuple[LocalRoleFact, ...]) -> tuple[LocalRoleFact, ...]:
    retained: dict[str, LocalRoleFact] = {}
    for row in roles:
        if row.entity_id is not None:
            retained.setdefault(row.entity_id, row)
    return tuple(retained.values())


def _subject_phrase(raw: RawArticle, roles: tuple[LocalRoleFact, ...]) -> str:
    roles = _unique_resolved_roles(roles)
    # ACTOR Entity mention은 exact surface 자체를 이름으로 취급한다. 이름 끝 글자를
    # 조사라고 추정해 제거하지 않고, source에서 span 뒤의 실제 조사를 따로 본다.
    names = tuple(row.text.strip() for row in roles if row.text.strip())
    if not names:
        return ""
    if len(names) == 1:
        name = names[0]
        following = raw.content[roles[0].end:roles[0].end + 1]
        if name.endswith(("은", "는", "이", "가", "께서")) and following not in ("은", "는", "이", "가"):
            return name
        return name + ("이" if _has_batchim(name) else "가")
    joined = ("과" if _has_batchim(names[0]) else "와").join(names)
    return joined + ("이" if _has_batchim(names[-1]) else "가")


def _trigger_root(text: str) -> str:
    clean = text.strip().rstrip(".!?…")
    return re.sub(r"(?:하지\s*않았다|했습니다|했다|됐다|되었다|한다|된다|하였다|했다며|했고|했으며)$", "", clean)


def _compatible_role(event: LocalEventState, anchor: EventMemberGrounding,
                     role: LocalRoleFact, members: dict[str, EventMemberGrounding],
                     view: CanonicalSourceView) -> bool:
    if role.entity_id is None or role.endpoint_status != "RESOLVED" or not role.member_ids:
        return False
    anchor_trigger = next((text for _start, _end, text, mid in event.triggers
                           if mid == anchor.member_id), anchor.text)
    root = _trigger_root(anchor_trigger)
    anchor_times = {row.time_id for row in event.times if anchor.member_id in row.member_ids}
    for member_id in role.member_ids:
        member = members.get(member_id)
        if member is None:
            return False
        member_times = {row.time_id for row in event.times if member_id in row.member_ids}
        if anchor_times and member_times and anchor_times != member_times:
            return False
        if _semantic_signature(anchor.text) != _semantic_signature(member.text):
            if any(_semantic_signature(member.text)[:3]):
                return False
        if view.scope_depth(anchor.start) != view.scope_depth(role.start):
            return False
        if member_id != anchor.member_id and root and root not in member.text:
            other_trigger = next((text for _s, _e, text, mid in event.triggers if mid == member_id), "")
            if _trigger_root(other_trigger) != root:
                return False
    return True


def _pronoun_source_occurrence(raw: RawArticle, anchor: EventMemberGrounding,
                               match: re.Match[str]) -> tuple[int, int, str] | None:
    """Map one display pronoun back to the same exact anchor occurrence."""
    surface = match.group(0).strip()
    if surface not in _PRONOUN_ROLE_TEXT:
        return None
    start = anchor.start + match.start()
    end = start + len(surface)
    if end > anchor.end or raw.content[start:end] != surface:
        return None
    return start, end, surface


def _role_is_pronoun_occurrence(raw: RawArticle, role: LocalRoleFact,
                                occurrence: tuple[int, int, str]) -> bool:
    start, end, surface = occurrence
    return (role.start == start and role.end <= end and
            role.text in _PRONOUN_ROLE_TEXT[surface] and
            raw.content[role.start:role.end] == role.text)


def _role_is_any_pronoun(raw: RawArticle, role: LocalRoleFact) -> bool:
    for surface, allowed in _PRONOUN_ROLE_TEXT.items():
        if (role.text in allowed and role.start + len(surface) <= len(raw.content) and
                raw.content[role.start:role.start + len(surface)] == surface):
            return True
    return False


def _resolved_pronoun_alias(raw: RawArticle, event: LocalEventState,
                            anchor: EventMemberGrounding, compatible: tuple[LocalRoleFact, ...],
                            role_name: str, match: re.Match[str], display_text: str
                            ) -> tuple[LocalRoleFact, tuple[LocalRoleFact, ...]] | None:
    """Resolve a pronoun only through its own role endpoint, then choose that Entity's alias."""
    occurrence = _pronoun_source_occurrence(raw, anchor, match)
    if occurrence is None:
        return None
    endpoint_rows = tuple(
        row for row in event.roles
        if row.role == role_name and anchor.member_id in row.member_ids and
        _role_is_pronoun_occurrence(raw, row, occurrence)
    )
    if (not endpoint_rows or any(row.endpoint_status != "RESOLVED" or row.entity_id is None
                                 for row in endpoint_rows)):
        return None
    entity_ids = {row.entity_id for row in endpoint_rows}
    if len(entity_ids) != 1:
        return None
    entity_id = next(iter(entity_ids))
    same_entity_roles = tuple(
        row for row in compatible
        if row.entity_id == entity_id and row.endpoint_status == "RESOLVED"
    )
    # If the resolved Entity already has an explicit source alias in the display,
    # keep the original span instead of adding a second alias for one participant.
    if any(not _role_is_any_pronoun(raw, row) and row.text.strip() and
           row.text.strip() in display_text for row in same_entity_roles):
        return None
    aliases = {
        (row.start, row.end, row.text): row
        for row in same_entity_roles
        if row.role == role_name and not _role_is_any_pronoun(raw, row) and row.text.strip()
    }
    if not aliases:
        return None
    alias = aliases[min(aliases)]
    return alias, endpoint_rows


def _compose_frame(raw: RawArticle, event: LocalEventState, anchor: EventMemberGrounding,
                   result: CanonicalTextResult, view: CanonicalSourceView) -> CanonicalTextResult:
    if (event.conflict_flags or result.status in ("FALLBACK_SOURCE_SPAN", "INSUFFICIENT_CONTEXT")
            or not (_complete(result.text) or _nominal_complete(result.text))):
        return result
    members = {row.member_id: row for row in _member_groundings(raw, event)}
    compatible = tuple(row for row in event.roles
                       if _compatible_role(event, anchor, row, members, view))
    text = result.text
    edits = list(result.edits)
    grounds = list(result.source_groundings)
    changed = False
    source_display = text
    actor_pronoun = _PRONOUN_SUBJECT.search(source_display)
    frame_actors = _unique_resolved_roles(tuple(
        row for row in compatible if row.role == "ACTOR" and row.text not in source_display))
    actor_resolution = (_resolved_pronoun_alias(
        raw, event, anchor, compatible, "ACTOR", actor_pronoun, source_display)
                        if actor_pronoun else None)
    target_plans = []
    for target_pronoun in _PRONOUN_TARGET.finditer(source_display):
        target_resolution = _resolved_pronoun_alias(
            raw, event, anchor, compatible, "TARGET", target_pronoun, source_display)
        if target_resolution is not None:
            target_plans.append((target_pronoun, target_resolution))

    # All source occurrences and endpoints above belong to the unmodified anchor.
    # Apply display replacements from right to left so earlier length deltas rebase
    # later pronoun and ending edit coordinates without changing source lookup.
    for target_pronoun, (target, endpoint_rows) in reversed(target_plans):
        name = target.text.strip()
        following = raw.content[target.end:target.end + 1]
        phrase = (name if name.endswith(("을", "를")) and following not in ("을", "를")
                  else name + ("을" if _has_batchim(name) else "를"))
        edits = _rebase_edits_for_replacement(
            edits, target_pronoun.start(), target_pronoun.end(), len(phrase))
        text = text[:target_pronoun.start()] + phrase + text[target_pronoun.end():]
        edits.append(CanonicalEdit(
            "RESOLVED_PRONOUN_TARGET", "GROUNDED_ROLE_REPLACEMENT",
            target.start, target.end, target.text,
            target_pronoun.start(), target_pronoun.start() + len(phrase), phrase))
        grounds.extend(_grounding(raw, eid, row.start, row.end)
                       for row in (*endpoint_rows, target) for eid in row.evidence_ids)
        changed = True
    if actor_pronoun and actor_resolution is not None:
        actor, endpoint_rows = actor_resolution
        phrase = _subject_phrase(raw, (actor,))
        if phrase:
            edits = _rebase_edits_for_replacement(
                edits, actor_pronoun.start(), actor_pronoun.end(), len(phrase) + 1)
            text = phrase + " " + text[actor_pronoun.end():]
            edits.append(CanonicalEdit("RESOLVED_PRONOUN_ACTOR", "GROUNDED_ROLE_REPLACEMENT",
                                       actor.start, actor.end, actor.text,
                                       0, len(phrase), phrase))
            grounds.extend(_grounding(raw, eid, row.start, row.end)
                           for row in (*endpoint_rows, actor) for eid in row.evidence_ids)
            changed = True
    if not changed and " " not in text.strip() and _SAFE_ACTIVE.search(text) and not _PASSIVE.search(text):
        targets = tuple(row for row in compatible if row.role == "TARGET")
        subject = _subject_phrase(raw, frame_actors)
        targets = _unique_resolved_roles(targets)
        target_names = tuple(_strip_particle(row.text) for row in targets)
        if subject and target_names:
            target = target_names[0]
            object_phrase = target + ("을" if _has_batchim(target) else "를")
            predicate = _punctuate(text.strip().rstrip(".!?…"))
            composed = f"{subject} {object_phrase} {predicate}"
            prefix_length = len(subject) + 1 + len(object_phrase) + 1
            edits = _rebase_edits_for_insertion(edits, 0, prefix_length)
            edits.append(CanonicalEdit("RESOLVED_ACTIVE_FRAME", "GROUNDED_FRAME_COMPOSITION",
                                       anchor.start, anchor.end, anchor.text, 0, len(composed), composed))
            grounds.extend(_grounding(raw, eid, row.start, row.end)
                           for row in (*frame_actors, *targets) for eid in row.evidence_ids)
            text, changed = composed, True
    if not changed:
        return result
    return _result(text, "GROUNDED_FRAME_COMPOSED", tuple(grounds),
                   result.audit + ("SAME_EVENT_COMPATIBILITY_CHECKED",), tuple(edits))


def canonicalize_event(raw: RawArticle, event: LocalEventState, *,
                       view: CanonicalSourceView | None = None) -> CanonicalTextResult:
    """좋은 member anchor를 고른 뒤 안전한 clause/ending/frame 표시 규칙을 적용한다."""
    _validate_event(raw, event)
    view = view or CanonicalSourceView.build(raw)
    view.require(raw)
    members = _member_groundings(raw, event)
    candidates = [(row, _event_anchor(raw, event, row, view)) for row in members]
    anchor, result = max(candidates,
                         key=lambda pair: _anchor_rank(pair[1], pair[0],
                                                      event.representative_member_id))
    if anchor.member_id != event.representative_member_id:
        result = _result(result.text, result.status, result.source_groundings,
                         result.audit + (f"DISPLAY_ANCHOR:{anchor.member_id}",
                                         "DISPLAY_ANCHOR_SOURCE_DETAIL_HEURISTIC"),
                         result.edits)
    return _compose_frame(raw, event, anchor, result, view)


def canonicalize_statement(raw: RawArticle, statement: GroundedStatement, *,
                           view: CanonicalSourceView | None = None) -> CanonicalTextResult:
    """Preserve the proposition span; only finish an explicitly safe ending."""
    statement.validate(raw)
    view = view or CanonicalSourceView.build(raw)
    view.require(raw)
    source = statement.grounding.text.strip()
    base = (statement.grounding,)
    audit = (f"STATEMENT_TYPE:{statement.statement_type}", "SPAN_FIRST_PROPOSITION")
    if statement.assertor is not None:
        audit += ("ASSERTOR_DISPLAYED_SEPARATELY",)
    if not source:
        return _result(statement.grounding.text, "INSUFFICIENT_CONTEXT", base,
                       audit + ("EMPTY_SOURCE_SPAN",))
    if _complete(source):
        return _result(source, "SOURCE_COMPLETE", base, audit)
    normalized = _normalize_statement_ending(source, statement.grounding.start)
    if normalized is not None:
        text, edit = normalized
        return _result(text, "ENDING_NORMALIZED", base,
                       audit + (edit.rule_id,), (edit,))
    return _result(source, "FALLBACK_SOURCE_SPAN", base,
                   audit + ("UNSAFE_ENDING_OR_INCOMPLETE_PROPOSITION",))


def source_only_event(raw: RawArticle, event: LocalEventState) -> CanonicalTextResult:
    """표시 on/off invariant 검사용 exact representative source 경로."""
    _validate_event(raw, event)
    return _result(event.text, "SOURCE_ONLY_DIAGNOSTIC",
                   (_grounding(raw, event.representative_member_id, event.start, event.end),),
                   ("CANONICALIZER_DISABLED",))


def source_only_statement(raw: RawArticle, statement: GroundedStatement) -> CanonicalTextResult:
    statement.validate(raw)
    return _result(statement.grounding.text, "SOURCE_ONLY_DIAGNOSTIC",
                   (statement.grounding,), ("CANONICALIZER_DISABLED",))
