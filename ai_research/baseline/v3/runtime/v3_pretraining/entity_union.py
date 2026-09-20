"""NER·referential role·Assertor source의 article-local scalar 후보 통합.

후보는 원문 근거와 출처만 보유한다. tensor/Gold ID는 runtime carrier에 넣지 않는다.
coreference와 endpoint 선택은 이 union 뒤 별도의 learned decision이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import TYPE_CHECKING, Sequence

from runtime.v3_pretraining.source_layout import RawArticle

if TYPE_CHECKING:
    from runtime.v3_pretraining.extraction_decode import DecodedSourceSpan


ENTITY_TYPES = ("PERSON", "ORGANIZATION", "LOCATION", "PRODUCT", "GENERIC")
ROLES = ("ACTOR", "TARGET", "PLACE", "ASSERTOR")
REFERENTIAL_STATES = ("CONFIRMED", "PROPOSED", "SPAN_ONLY")


@dataclass(frozen=True, slots=True)
class EntitySourceEvidence:
    evidence_id: str
    origin: str  # NER, ROLE, ASSERTOR
    start: int
    end: int
    text: str
    entity_type: str | None
    score: float
    owner_id: str | None = None  # Event/Statement ID for role/Assertor
    role: str | None = None
    referential_state: str = "CONFIRMED"
    referent_hint: str | None = None  # explicit model context, never copied Gold ID at runtime

    def validate(self, article: RawArticle) -> None:
        if not self.evidence_id or self.origin not in ("NER", "ROLE", "ASSERTOR"):
            raise ValueError("Entity evidence origin/ID invalid")
        if not 0 <= self.start < self.end <= len(article.content) or article.content[self.start:self.end] != self.text:
            raise ValueError("Entity evidence does not match exact source span")
        if self.entity_type is not None and self.entity_type not in ENTITY_TYPES:
            raise ValueError("Entity type outside r05.3 taxonomy")
        if not math.isfinite(self.score):
            raise ValueError("Entity evidence score must be finite")
        if self.origin == "NER":
            if self.entity_type is None or self.role is not None or self.owner_id is not None:
                raise ValueError("NER evidence needs type but no role owner")
        else:
            allowed_roles = ("ASSERTOR",) if self.origin == "ASSERTOR" else ROLES[:3]
            if not self.owner_id or self.role not in allowed_roles:
                raise ValueError("role/Assertor evidence needs owner and declared role")
            if self.referential_state not in REFERENTIAL_STATES:
                raise ValueError("unknown referential evidence state")


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    candidate_id: str
    start: int
    end: int
    text: str
    entity_type: str | None
    origins: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    score: float
    referential_state: str
    referent_hint: str | None
    type_evidence: tuple[float, ...] = ()  # predicted five-type log probabilities; request scalar only


@dataclass(frozen=True, slots=True)
class RoleBinding:
    evidence_id: str
    owner_id: str
    role: str
    start: int
    end: int
    text: str
    candidate_ids: tuple[str, ...]
    referential_state: str
    status: str  # CANDIDATE, SPAN_ONLY, UNRESOLVED_REFERENTIAL, PARTIAL_BUDGET


@dataclass(frozen=True, slots=True)
class EntityCandidateUniverse:
    article_version_id: str
    content_sha256: str
    candidates: tuple[EntityCandidate, ...]
    bindings: tuple[RoleBinding, ...]
    status: str  # READY, READY_WITH_CONFLICTS, BOUNDED_PARTIAL
    dropped_ner: int
    dropped_role: int
    type_conflicts: int
    source_mode: str  # PREDICTED or GOLD_ORACLE_STRUCTURE

    def candidate_by_id(self) -> dict[str, EntityCandidate]:
        return {candidate.candidate_id: candidate for candidate in self.candidates}


@dataclass(frozen=True, slots=True)
class EntityCandidateBudget:
    max_candidates: int = 128
    status: str = "PROVISIONAL_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        if self.max_candidates <= 0:
            raise ValueError("Entity candidate budget must be positive")


def evidence_from_entity_decode(spans: Sequence[DecodedSourceSpan]) -> tuple[EntitySourceEvidence, ...]:
    """5번 Entity decode scalar 결과를 Gold 없이 NER origin으로 변환한다."""
    output = []
    for span in spans:
        if span.kind != "ENTITY" or span.label not in ENTITY_TYPES:
            raise ValueError("decoded Entity needs a valid five-type label")
        evidence_id = f"NER-PRED:{span.start}:{span.end}:{span.label}"
        output.append(EntitySourceEvidence(evidence_id, "NER", span.start, span.end,
                                           span.text, span.label, span.score))
    return tuple(output)


def evidence_from_role_decode(owner_id: str, span: DecodedSourceSpan, *,
                              referential_state: str = "PROPOSED",
                              entity_type_hint: str | None = None) -> EntitySourceEvidence:
    """Event-conditioned role 결과를 source-first 후보로 넘긴다."""
    if not owner_id or span.kind != "PARTICIPANT" or span.label not in ROLES[:3]:
        raise ValueError("decoded role needs Event owner and ACTOR/TARGET/PLACE")
    evidence_id = f"ROLE-PRED:{owner_id}:{span.label}:{span.start}:{span.end}"
    return EntitySourceEvidence(evidence_id, "ROLE", span.start, span.end, span.text,
                                entity_type_hint, span.score, owner_id=owner_id,
                                role=span.label, referential_state=referential_state)


def evidence_from_assertor_decode(statement_id: str, span: DecodedSourceSpan, *,
                                 referential_state: str = "PROPOSED") -> EntitySourceEvidence:
    """Statement-conditioned textual source를 동일 Entity 후보 universe로 보낸다."""
    if not statement_id or span.kind != "ASSERTOR" or span.label is not None:
        raise ValueError("Assertor source needs its owning Statement and exact span")
    return EntitySourceEvidence(f"ASSERTOR-PRED:{statement_id}:{span.start}:{span.end}",
                                "ASSERTOR", span.start, span.end, span.text, None,
                                span.score, owner_id=statement_id, role="ASSERTOR",
                                referential_state=referential_state)


def _candidate_id(article: RawArticle, start: int, end: int,
                  entity_type: str | None, hint: str | None) -> str:
    payload = f"{article.article_version_id}:{article.content_sha256}:{start}:{end}:{entity_type}:{hint}"
    return "ECAND:" + sha256(payload.encode()).hexdigest()[:16]


def build_entity_candidates(article: RawArticle, evidence: Sequence[EntitySourceEvidence], *,
                            budget: EntityCandidateBudget | None = EntityCandidateBudget(),
                            source_mode: str = "PREDICTED") -> EntityCandidateUniverse:
    """exact span/type가 호환될 때만 합치고 role origin을 budget 앞에 예약한다."""
    if source_mode not in ("PREDICTED", "GOLD_ORACLE_STRUCTURE"):
        raise ValueError("unknown Entity candidate provenance mode")
    if source_mode == "PREDICTED" and any(item.referent_hint is not None and
                                          not item.referent_hint.startswith("CTX:") for item in evidence):
        raise ValueError("predicted referent hints need a local CTX: ID, never a Gold ID")
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise ValueError("duplicate Entity evidence ID")
    for item in evidence:
        item.validate(article)
    ner_by_span: dict[tuple[int, int], set[str]] = {}
    for item in evidence:
        if item.origin == "NER":
            ner_by_span.setdefault((item.start, item.end), set()).add(item.entity_type)
    prepared: list[tuple[EntitySourceEvidence, str | None]] = []
    for item in evidence:
        if item.origin == "NER":
            prepared.append((item, item.entity_type))
            continue
        if item.referential_state == "SPAN_ONLY":
            continue
        inferred = item.entity_type
        nearby_types = ner_by_span.get((item.start, item.end), set())
        if inferred is None and len(nearby_types) == 1:
            inferred = next(iter(nearby_types))
        if inferred is None and item.referential_state == "CONFIRMED" and item.role in ("ACTOR", "TARGET"):
            inferred = "GENERIC"
        prepared.append((item, inferred))
    # 같은 coordinate/type의 문맥 hint가 충돌하면 hint 없는 NER도 임의 한쪽에 붙이지 않는다.
    groups: dict[tuple[int, int, str | None], list[tuple[EntitySourceEvidence, str | None]]] = {}
    for item, entity_type in prepared:
        groups.setdefault((item.start, item.end, entity_type), []).append((item, entity_type))
    candidates: list[EntityCandidate] = []
    evidence_to_candidates: dict[str, list[str]] = {item.evidence_id: [] for item in evidence}
    conflicts = 0
    for (start, end, entity_type), members in sorted(groups.items(), key=lambda row: (row[0][0], row[0][1], row[0][2] or "")):
        hints = {item.referent_hint for item, _ in members if item.referent_hint is not None}
        has_unhinted = any(item.referent_hint is None for item, _ in members)
        separated = bool(hints) and (len(hints) > 1 or has_unhinted)
        selected_hints = tuple(sorted(hints)) + ((None,) if has_unhinted else ()) if separated else (None,)
        if separated:
            conflicts += 1
        for hint in selected_hints:
            if not separated:
                selected = [item for item, _ in members]
                canonical_hint = next(iter(hints)) if hints else None
            else:
                selected = [item for item, _ in members if item.referent_hint == hint]
                canonical_hint = hint
            if not selected:
                continue
            candidate_id = _candidate_id(article, start, end, entity_type, canonical_hint)
            state = ("CONFIRMED" if any(item.referential_state == "CONFIRMED" for item in selected)
                     else "PROPOSED")
            candidate = EntityCandidate(candidate_id, start, end, article.content[start:end], entity_type,
                                        tuple(sorted({item.origin for item in selected})),
                                        tuple(sorted(item.evidence_id for item in selected)),
                                        max(item.score for item in selected), state, canonical_hint)
            candidates.append(candidate)
            for item in selected:
                evidence_to_candidates[item.evidence_id].append(candidate_id)
    # 서로 다른 type의 같은 경계는 학습된 판정 전까지 별도 후보로 둔다.
    types_by_span: dict[tuple[int, int], set[str | None]] = {}
    for candidate in candidates:
        types_by_span.setdefault((candidate.start, candidate.end), set()).add(candidate.entity_type)
    conflicts += sum(len(types) > 1 for types in types_by_span.values())
    mandatory = [candidate for candidate in candidates if "ROLE" in candidate.origins or "ASSERTOR" in candidate.origins]
    optional = [candidate for candidate in candidates if candidate not in mandatory]
    ranking = lambda candidate: (-candidate.score, candidate.start, candidate.end,
                                 candidate.entity_type or "", candidate.candidate_id)
    ordered = sorted(mandatory, key=ranking) + sorted(optional, key=ranking)
    selected = ordered if budget is None else ordered[:budget.max_candidates]
    selected_ids = {candidate.candidate_id for candidate in selected}
    dropped_ner = sum(candidate.candidate_id not in selected_ids for candidate in candidates
                      if "NER" in candidate.origins and "ROLE" not in candidate.origins and "ASSERTOR" not in candidate.origins)
    dropped_role = sum(candidate.candidate_id not in selected_ids for candidate in mandatory)
    bindings = []
    for item in evidence:
        if item.origin == "NER":
            continue
        linked = tuple(candidate_id for candidate_id in evidence_to_candidates[item.evidence_id]
                       if candidate_id in selected_ids)
        if item.referential_state == "SPAN_ONLY":
            status = "SPAN_ONLY"
        elif linked:
            status = "CANDIDATE"
        elif evidence_to_candidates[item.evidence_id]:
            status = "PARTIAL_BUDGET"
        else:
            status = "UNRESOLVED_REFERENTIAL"
        bindings.append(RoleBinding(item.evidence_id, item.owner_id, item.role,
                                    item.start, item.end, item.text, linked,
                                    item.referential_state, status))
    status = "BOUNDED_PARTIAL" if dropped_ner or dropped_role else "READY_WITH_CONFLICTS" if conflicts else "READY"
    return EntityCandidateUniverse(article.article_version_id, article.content_sha256,
                                   tuple(sorted(selected, key=lambda row: (row.start, row.end, row.entity_type or "",
                                                                           row.candidate_id))),
                                   tuple(bindings), status, dropped_ner, dropped_role,
                                   conflicts, source_mode)
