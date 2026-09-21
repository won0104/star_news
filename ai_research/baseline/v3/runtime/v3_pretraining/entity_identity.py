"""article-local Entity 후보의 명시적 동일성 결정과 role endpoint remap.

학습된 pair/role decision만 받는다. surface 일치만으로 alias를 만들지 않고,
미해결 예측을 fake Entity로 보정하지 않는다. 결과는 scalar/evidence 전용이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Mapping

from runtime.v3_pretraining.entity_union import ENTITY_TYPES, EntityCandidateUniverse


@dataclass(frozen=True, slots=True)
class LocalEntity:
    local_id: str
    representative_candidate_id: str
    start: int
    end: int
    text: str
    entity_type: str | None
    observed_types: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    status: str  # RESOLVED or TYPE_CONFLICT
    member_type_evidence: tuple[tuple[str, str | None, tuple[float, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class RoleEndpoint:
    evidence_id: str
    owner_id: str
    role: str
    start: int
    end: int
    text: str
    local_entity_id: str | None
    status: str  # RESOLVED, RESOLVED_TYPE_CONFLICT, SPAN_ONLY, UNRESOLVED_REFERENTIAL, PARTIAL_BUDGET


@dataclass(frozen=True, slots=True)
class EntityClosure:
    entities: tuple[LocalEntity, ...]
    candidate_to_entity: Mapping[str, str]
    evidence_to_entity: Mapping[str, str]
    endpoints: tuple[RoleEndpoint, ...]
    status: str
    source_mode: str


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def close_entity_identity(universe: EntityCandidateUniverse, *,
                          merge_decisions: Mapping[tuple[str, str], bool],
                          resolution_decisions: Mapping[str, str | None],
                          accepted_evidence_ids: frozenset[str] = frozenset(),
                          strict_gold_endpoints: bool = False) -> EntityClosure:
    """complete-link positive pair만 합치고 각 source role 사실은 별도 보존한다."""
    by_id = universe.candidate_by_id()
    if len(by_id) != len(universe.candidates):
        raise ValueError("duplicate Entity candidate ID")
    binding_ids = {binding.evidence_id for binding in universe.bindings}
    if not accepted_evidence_ids <= binding_ids:
        raise ValueError("accepted evidence references unknown role")
    active = {candidate_id for candidate_id, candidate in by_id.items()
              if "NER" in candidate.origins or candidate.referential_state == "CONFIRMED"
              or any(evidence_id in accepted_evidence_ids for evidence_id in candidate.evidence_ids)}
    normalized: dict[tuple[str, str], bool] = {}
    for a, b in merge_decisions:
        if a not in by_id or b not in by_id or a == b:
            raise ValueError("Entity coreference decision references unknown/self candidate")
        key = _pair_key(a, b)
        value = bool(merge_decisions[(a, b)])
        if key in normalized and normalized[key] != value:
            raise ValueError("conflicting directed copies of symmetric coreference decision")
        normalized[key] = value
    groups: list[set[str]] = [{candidate_id} for candidate_id in sorted(active)]
    for a, b in sorted(key for key, value in normalized.items() if value):
        if a not in active or b not in active:
            continue
        left = next(group for group in groups if a in group)
        right = next(group for group in groups if b in group)
        if left is right:
            continue
        if all(normalized.get(_pair_key(x, y), False) for x in left for y in right):
            left.update(right)
            groups.remove(right)
    entities = []
    candidate_to_entity = {}
    evidence_to_entity: dict[str, str] = {}
    for members in groups:
        candidates = [by_id[candidate_id] for candidate_id in sorted(members)]
        observed = {candidate.entity_type for candidate in candidates if candidate.entity_type is not None}
        if universe.source_mode == "PREDICTED":
            scored = [candidate.type_evidence for candidate in candidates if candidate.type_evidence]
            if scored and any(len(values) != len(ENTITY_TYPES) or
                              not all(math.isfinite(value) for value in values) for values in scored):
                raise ValueError("predicted Entity type evidence needs five finite model values")
            if scored:
                totals = [sum(values[index] for values in scored) for index in range(len(ENTITY_TYPES))]
                entity_type = ENTITY_TYPES[max(range(len(totals)), key=lambda index: (totals[index], -index))]
            elif observed:
                # Direct closure fixtures may supply only member labels. Serving always supplies model vectors.
                entity_type = next(kind for kind in ENTITY_TYPES if kind in observed)
            else:
                raise ValueError("predicted Entity cluster lacks five-type evidence")
        else:
            entity_type = next(iter(observed)) if len(observed) == 1 else None
        status = "TYPE_CONFLICT" if len(observed) > 1 else "RESOLVED" if entity_type else "UNTYPED"
        representative = min(candidates, key=lambda candidate: (candidate.start, candidate.end,
                                                                   -candidate.score, candidate.candidate_id))
        payload = f"{universe.article_version_id}:{universe.content_sha256}:{','.join(sorted(members))}"
        local_id = "ENT:" + sha256(payload.encode()).hexdigest()[:16]
        entity = LocalEntity(local_id, representative.candidate_id, representative.start,
                             representative.end, representative.text, entity_type,
                             tuple(sorted(observed)),
                             tuple(sorted(members)),
                             tuple(sorted({evidence_id for candidate in candidates
                                           for evidence_id in candidate.evidence_ids})), status,
                             tuple((candidate.candidate_id, candidate.entity_type,
                                    candidate.type_evidence) for candidate in candidates))
        entities.append(entity)
        for candidate_id in members:
            candidate_to_entity[candidate_id] = local_id
        for evidence_id in entity.evidence_ids:
            if evidence_id in evidence_to_entity and evidence_to_entity[evidence_id] != local_id:
                raise ValueError("one source evidence maps to conflicting Entity identities")
            evidence_to_entity[evidence_id] = local_id
    entities.sort(key=lambda entity: (entity.start, entity.end, entity.local_id))
    entity_by_id = {entity.local_id: entity for entity in entities}
    endpoints = []
    bindings_by_id = {binding.evidence_id: binding for binding in universe.bindings}
    if set(resolution_decisions) - set(bindings_by_id):
        raise ValueError("resolution decision has unknown role evidence")
    for binding in universe.bindings:
        choice = resolution_decisions.get(binding.evidence_id)
        endpoint_id = None
        if binding.status == "PARTIAL_BUDGET":
            status = "PARTIAL_BUDGET"
        elif binding.status == "SPAN_ONLY":
            if choice is not None:
                raise ValueError("SPAN_ONLY source cannot acquire a fake Entity endpoint")
            status = "SPAN_ONLY"
        elif choice is None:
            status = "UNRESOLVED_REFERENTIAL" if binding.role in ("ACTOR", "TARGET") else "SPAN_ONLY"
        elif choice not in candidate_to_entity:
            raise ValueError("resolution endpoint references unknown Entity candidate")
        else:
            entity = entity_by_id[candidate_to_entity[choice]]
            status = ("RESOLVED" if entity.status == "RESOLVED" else
                      "RESOLVED_TYPE_CONFLICT" if entity.status == "TYPE_CONFLICT" else
                      "UNRESOLVED_REFERENTIAL" if binding.role in ("ACTOR", "TARGET") else "SPAN_ONLY")
            endpoint_id = entity.local_id if status.startswith("RESOLVED") else None
        if strict_gold_endpoints and binding.role in ("ACTOR", "TARGET") and status not in (
                "RESOLVED", "RESOLVED_TYPE_CONFLICT"):
            raise ValueError(f"Gold {binding.role} endpoint was lost: {binding.evidence_id}")
        endpoints.append(RoleEndpoint(binding.evidence_id, binding.owner_id, binding.role,
                                      binding.start, binding.end, binding.text, endpoint_id, status))
    overall = ("BOUNDED_PARTIAL" if universe.status == "BOUNDED_PARTIAL" or
               any(row.status == "PARTIAL_BUDGET" for row in endpoints)
               else "PARTIAL_ENDPOINT" if any(row.status == "UNRESOLVED_REFERENTIAL"
                                              for row in endpoints)
               else "READY_WITH_TYPE_CONFLICTS" if any(row.status == "RESOLVED_TYPE_CONFLICT"
                                                       for row in endpoints)
               else "READY")
    return EntityClosure(tuple(entities), candidate_to_entity, evidence_to_entity,
                         tuple(endpoints),
                         overall, universe.source_mode)
