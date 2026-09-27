"""Native Entity와 Participant ROLE 근거를 exact source mention으로 통합한다.

활성 unified 경로는 ASSERTOR를 후속 attribution query로만 보존한다. 아래
legacy candidate builder는 과거 진단용이며 활성 identity 결정에 쓰지 않는다.
runtime carrier에는 tensor나 Gold ID를 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
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
    source_windows: tuple[tuple[str, str], ...] = ()
    type_evidence: tuple[float, ...] = ()  # Native five-type source logits only.

    def validate(self, article: RawArticle) -> None:
        if not self.evidence_id or self.origin not in ("NER", "ROLE", "ASSERTOR"):
            raise ValueError("Entity evidence origin/ID invalid")
        if not 0 <= self.start < self.end <= len(article.content) or article.content[self.start:self.end] != self.text:
            raise ValueError("Entity evidence does not match exact source span")
        if self.entity_type is not None and self.entity_type not in ENTITY_TYPES:
            raise ValueError("Entity type outside r05.3 taxonomy")
        if not math.isfinite(self.score):
            raise ValueError("Entity evidence score must be finite")
        if self.type_evidence and (self.origin != "NER" or
                                   len(self.type_evidence) != len(ENTITY_TYPES) or
                                   not all(math.isfinite(value) for value in self.type_evidence)):
            raise ValueError("only Native Entity evidence may carry five finite type logits")
        if any(len(pair) != 2 or not all(isinstance(value, str) and value for value in pair)
               for pair in self.source_windows):
            raise ValueError("Entity source window provenance must contain nonempty ID pairs")
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
    source_windows: tuple[tuple[str, str], ...] = ()
    source_score: float | None = None  # Raw model score, not calibrated probability.


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
    identity_contract: str = "LEGACY_RESOLUTION"

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
        type_evidence = tuple(value for _, value in span.subtype_scores)
        output.append(EntitySourceEvidence(evidence_id, "NER", span.start, span.end,
                                           span.text, span.label, span.score,
                                           type_evidence=type_evidence))
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
                                role=span.label, referential_state=referential_state,
                                source_windows=(span.provenance_windows or
                                                ((span.start_window_id,
                                                  span.end_window_id),)))


def evidence_from_assertor_decode(statement_id: str, span: DecodedSourceSpan, *,
                                 referential_state: str = "PROPOSED") -> EntitySourceEvidence:
    """Statement-conditioned source를 post-closure attribution binding으로 보낸다."""
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
    mandatory_ids = {candidate.candidate_id for candidate in mandatory}
    optional = [candidate for candidate in candidates
                if candidate.candidate_id not in mandatory_ids]
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
                                    item.referential_state, status, item.source_windows))
    status = "BOUNDED_PARTIAL" if dropped_ner or dropped_role else "READY_WITH_CONFLICTS" if conflicts else "READY"
    return EntityCandidateUniverse(article.article_version_id, article.content_sha256,
                                   tuple(sorted(selected, key=lambda row: (row.start, row.end, row.entity_type or "",
                                                                           row.candidate_id))),
                                   tuple(bindings), status, dropped_ner, dropped_role,
                                   conflicts, source_mode)


def build_unified_entity_mentions(
        article: RawArticle, evidence: Sequence[EntitySourceEvidence]
) -> EntityCandidateUniverse:
    """Join accepted ROLE uses to exact Native mentions before one Entity closure.

    A ROLE with no unique exact Native match remains an UNKNOWN mention. Its
    Event/role use is retained independently of mention identity. ASSERTOR is a
    later attribution query and never creates a coreference mention here.
    """
    if len({row.evidence_id for row in evidence}) != len(evidence):
        raise ValueError("duplicate Entity/ROLE/ASSERTOR evidence ID")
    for row in evidence:
        row.validate(article)
    native = [row for row in evidence if row.origin == "NER"]
    roles = [row for row in evidence if row.origin == "ROLE"]
    assertors = [row for row in evidence if row.origin == "ASSERTOR"]
    by_span: dict[tuple[int, int], list[str]] = {}
    candidates: dict[str, EntityCandidate] = {}
    for row in native:
        candidate_id = _candidate_id(article, row.start, row.end, row.entity_type, None)
        if candidate_id in candidates:
            raise ValueError("duplicate Native Entity mention identity")
        candidates[candidate_id] = EntityCandidate(
            candidate_id, row.start, row.end, row.text, row.entity_type,
            ("NER",), (row.evidence_id,), row.score, "CONFIRMED", None,
            row.type_evidence)
        by_span.setdefault((row.start, row.end), []).append(candidate_id)

    role_uses_by_mention: dict[str, list[EntitySourceEvidence]] = {}
    role_bindings: list[RoleBinding] = []
    for row in roles:
        exact_native = by_span.get((row.start, row.end), ())
        if len(exact_native) == 1:
            candidate_id = exact_native[0]
            status = "CANDIDATE"
        else:
            # No Gold ID exists in predicted execution. Ambiguous same-span
            # Native types must be decided by coreference, not by this join.
            candidate_id = _candidate_id(article, row.start, row.end, None, "ROLE_UNKNOWN")
            status = "SPAN_ONLY"
            if candidate_id not in candidates:
                candidates[candidate_id] = EntityCandidate(
                    candidate_id, row.start, row.end, row.text, None,
                    ("ROLE",), (), row.score, "SPAN_ONLY", None)
        role_uses_by_mention.setdefault(candidate_id, []).append(row)
        role_bindings.append(RoleBinding(
            row.evidence_id, row.owner_id, row.role, row.start, row.end,
            row.text, (candidate_id,), row.referential_state, status,
            row.source_windows, row.score))

    for candidate_id, uses in role_uses_by_mention.items():
        candidate = candidates[candidate_id]
        candidates[candidate_id] = replace(
            candidate,
            origins=tuple(sorted(set(candidate.origins) | {"ROLE"})),
            evidence_ids=tuple(sorted((*candidate.evidence_ids,
                                       *(row.evidence_id for row in uses)))),
            score=(candidate.score if "NER" in candidate.origins
                   else max(row.score for row in uses)))

    assertor_bindings = [RoleBinding(
        row.evidence_id, row.owner_id, "ASSERTOR", row.start, row.end,
        row.text, tuple(by_span.get((row.start, row.end), ())),
        row.referential_state, "CANDIDATE", row.source_windows, row.score)
        for row in assertors]
    ordered = tuple(sorted(candidates.values(), key=lambda row: (
        row.start, row.end, row.entity_type or "", row.candidate_id)))
    return EntityCandidateUniverse(
        article.article_version_id, article.content_sha256, ordered,
        tuple((*role_bindings, *assertor_bindings)), "READY", 0, 0,
        sum(len(ids) > 1 for ids in by_span.values()), "PREDICTED",
        "UNIFIED_MENTION_COREF_V1")


def cap_unified_entity_mentions(
        universe: EntityCandidateUniverse, *, limit: int = 128
) -> EntityCandidateUniverse:
    """Apply the existing ROLE-first, score/coordinate Entity priority before coref.

    Unselected mentions never enter pair routing. Their role uses stay visible
    as PARTIAL_BUDGET bindings in the diagnostic/closure path.
    """
    if universe.identity_contract != "UNIFIED_MENTION_COREF_V1" or limit <= 0:
        raise ValueError("unified Entity safety cap requires a positive limit")
    if len(universe.candidates) <= limit:
        return universe
    rank = lambda row: (-row.score, row.start, row.end,
                        row.entity_type or "", row.candidate_id)
    role = [row for row in universe.candidates if "ROLE" in row.origins]
    native = [row for row in universe.candidates if "ROLE" not in row.origins]
    selected = (sorted(role, key=rank) + sorted(native, key=rank))[:limit]
    selected_ids = {row.candidate_id for row in selected}
    bindings = tuple(replace(binding,
                             candidate_ids=tuple(cid for cid in binding.candidate_ids
                                                 if cid in selected_ids),
                             status=("PARTIAL_BUDGET" if binding.candidate_ids and
                                     not any(cid in selected_ids
                                             for cid in binding.candidate_ids)
                                     else binding.status))
                     for binding in universe.bindings)
    return replace(
        universe,
        candidates=tuple(sorted(selected, key=lambda row: (
            row.start, row.end, row.entity_type or "", row.candidate_id))),
        bindings=bindings, status="BOUNDED_PARTIAL",
        dropped_ner=sum(row.candidate_id not in selected_ids and
                        "NER" in row.origins and "ROLE" not in row.origins
                        for row in universe.candidates),
        dropped_role=sum(row.candidate_id not in selected_ids and
                         "ROLE" in row.origins for row in universe.candidates))


def build_role_resolution_primary_universe(
        article: RawArticle, base_evidence: Sequence[EntitySourceEvidence],
        role_evidence: Sequence[EntitySourceEvidence]) -> EntityCandidateUniverse:
    """Keep B2 fillers as resolution queries outside the initial Entity inventory.

    The caller must provide endpoint-accepted ROLE evidence. Every query remains
    present, but only NER/ASSERTOR evidence can create a PRIMARY candidate.
    """
    if any(row.origin == "ROLE" for row in base_evidence) or any(
            row.origin != "ROLE" for row in role_evidence):
        raise ValueError("resolution-first evidence origins differ")
    primary = build_entity_candidates(article, base_evidence, budget=None)
    seen = {row.evidence_id for row in base_evidence}
    bindings = list(primary.bindings)
    for row in role_evidence:
        row.validate(article)
        if row.evidence_id in seen:
            raise ValueError("duplicate role resolution query")
        seen.add(row.evidence_id)
        bindings.append(RoleBinding(
            row.evidence_id, row.owner_id, row.role, row.start, row.end,
            row.text, (), row.referential_state, "CANDIDATE", row.source_windows))
    return replace(primary, bindings=tuple(bindings))


def build_role_resolution_fallback_universe(
        article: RawArticle, base_evidence: Sequence[EntitySourceEvidence],
        role_evidence: Sequence[EntitySourceEvidence],
        primary_choices: dict[str, str | None], *,
        preserve_unresolved_evidence_ids: frozenset[str]) -> EntityCandidateUniverse:
    """Promote only explicitly preserved unresolved fillers after resolution.

    A preserved failed filler keeps exact ROLE evidence as a local candidate
    and SPAN_ONLY endpoint. Other failed fillers keep only a scalar binding.
    The decision map covers every ROLE ID; resolved targets belong to PRIMARY.
    """
    expected = {row.evidence_id for row in role_evidence}
    if set(primary_choices) != expected:
        raise ValueError("resolution decisions must cover every B2 filler")
    if not preserve_unresolved_evidence_ids <= expected or any(
            primary_choices[evidence_id] is not None
            for evidence_id in preserve_unresolved_evidence_ids):
        raise ValueError("only unresolved B2 evidence can enter SPAN_ONLY rescue")
    primary = build_role_resolution_primary_universe(
        article, base_evidence, role_evidence)
    primary_ids = {row.candidate_id for row in primary.candidates}
    if any(choice is not None and choice not in primary_ids
           for choice in primary_choices.values()):
        raise ValueError("resolved filler targets must come from PRIMARY Entity")
    unresolved = [row for row in role_evidence
                  if row.evidence_id in preserve_unresolved_evidence_ids]
    final = build_entity_candidates(article, (*base_evidence, *unresolved), budget=None)
    bindings = {row.evidence_id: row for row in final.bindings}
    for row in unresolved:
        binding = bindings[row.evidence_id]
        if not binding.candidate_ids:
            raise ValueError("unresolved filler lost its local Entity candidate")
        bindings[row.evidence_id] = replace(binding, status="SPAN_ONLY",
                                            referential_state="SPAN_ONLY")
    for row in role_evidence:
        choice = primary_choices[row.evidence_id]
        if choice is not None:
            bindings[row.evidence_id] = RoleBinding(
                row.evidence_id, row.owner_id, row.role, row.start, row.end,
                row.text, (choice,), row.referential_state, "CANDIDATE",
                row.source_windows)
        elif row.evidence_id not in preserve_unresolved_evidence_ids:
            bindings[row.evidence_id] = RoleBinding(
                row.evidence_id, row.owner_id, row.role, row.start, row.end,
                row.text, (), "SPAN_ONLY", "SPAN_ONLY", row.source_windows)
    # Preserve source binding order. Sorting evidence IDs would reorder Event
    # fillers after resolution even though neither the source nor route did.
    return replace(final, bindings=tuple(bindings[row.evidence_id]
                                         for row in primary.bindings))
