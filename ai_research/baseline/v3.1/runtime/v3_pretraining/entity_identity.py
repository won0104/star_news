"""article-local Entity 후보의 명시적 동일성 결정과 role endpoint remap.

학습된 pair/role decision만 받는다. surface 일치만으로 alias를 만들지 않고,
미해결 예측을 fake Entity로 보정하지 않는다. cluster 확정 뒤 대표 source mention은
보수적인 대명사 allowlist와 type/surface/source 순서로 고르며 identity에는 관여하지 않는다.
결과는 scalar/evidence 전용이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Mapping

from runtime.v3_pretraining.entity_union import (ENTITY_TYPES, EntityCandidate,
                                                EntityCandidateUniverse)


_PRONOMINAL_ENTITY_SURFACES = frozenset({
    "그", "그녀", "그들", "이들", "그것", "이것", "저것",
    "그는", "그가", "그를", "그의", "그에게",
    "그녀는", "그녀가", "그녀를", "그녀의", "그녀에게",
    "그들은", "그들이", "그들을", "그들의", "그들에게",
    "이들은", "이들이", "이들을", "이들의", "이들에게",
    "그것은", "그것이", "그것을",
    "이것은", "이것이", "이것을",
    "저것은", "저것이", "저것을",
    "이는", "이를",
})
_ENTITY_BOUNDARY_SEPARATORS = frozenset(",，、;；:：")
_ENTITY_BOUNDARY_PAIRS = {"(": ")", "[": "]", "{": "}", "“": "”", "‘": "’"}
_ENTITY_CLOSING_TO_OPENING = {closer: opener for opener, closer in _ENTITY_BOUNDARY_PAIRS.items()}
_ENTITY_QUOTES = frozenset({'"', "'"})
_ENTITY_PARTICLE_SUFFIXES = (
    "에게서는", "으로부터", "로부터", "에게서", "에서는", "에게는",
    "으로는", "부터는", "까지는", "에서", "에게", "으로", "부터", "까지",
    "한테", "하고", "로", "은", "는", "이", "가", "을", "를",
    "의", "에", "와", "과", "도", "만",
)


@dataclass(frozen=True, slots=True)
class MergedMention:
    """PUBLIC 표시용으로 closure 시점에 보존한 비대표 exact source span."""

    text: str
    start: int
    end: int


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
    status: str  # RESOLVED, TYPE_CONFLICT, SPAN_ONLY, or UNTYPED
    member_type_evidence: tuple[tuple[str, str | None, tuple[float, ...]], ...] = ()
    merged_mentions: tuple[MergedMention, ...] = ()


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
    source_score: float | None = None
    source_windows: tuple[tuple[str, str], ...] = ()


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


def _is_pronominal_surface(text: str) -> bool:
    """확실한 순수 대명사 표면만 exact allowlist로 판정한다."""
    return text.strip() in _PRONOMINAL_ENTITY_SURFACES


def _trim_entity_boundary(text: str) -> str:
    """Remove only visible edge whitespace and unmatched boundary punctuation."""
    clean = text.strip()
    while clean:
        previous = clean
        if clean[0] in _ENTITY_BOUNDARY_SEPARATORS:
            clean = clean[1:].lstrip()
        elif clean[-1] in _ENTITY_BOUNDARY_SEPARATORS:
            clean = clean[:-1].rstrip()
        elif clean[0] in _ENTITY_BOUNDARY_PAIRS and (
                clean.count(clean[0]) > clean.count(_ENTITY_BOUNDARY_PAIRS[clean[0]])):
            clean = clean[1:].lstrip()
        elif clean[-1] in _ENTITY_BOUNDARY_PAIRS and (
                clean.count(clean[-1]) > clean.count(_ENTITY_BOUNDARY_PAIRS[clean[-1]])):
            clean = clean[:-1].rstrip()
        elif clean[0] in _ENTITY_CLOSING_TO_OPENING and (
                clean.count(clean[0]) > clean.count(_ENTITY_CLOSING_TO_OPENING[clean[0]])):
            clean = clean[1:].lstrip()
        elif clean[-1] in _ENTITY_CLOSING_TO_OPENING and (
                clean.count(clean[-1]) > clean.count(_ENTITY_CLOSING_TO_OPENING[clean[-1]])):
            clean = clean[:-1].rstrip()
        elif clean[0] in _ENTITY_QUOTES and clean.count(clean[0]) % 2:
            clean = clean[1:].lstrip()
        elif clean[-1] in _ENTITY_QUOTES and clean.count(clean[-1]) % 2:
            clean = clean[:-1].rstrip()
        if clean == previous:
            break
    return clean or text.strip() or text


def _particle_variant(text: str, clean_variants: frozenset[str]) -> str | None:
    """A suffix is removable only when its bare exact surface is in this cluster."""
    for suffix in _ENTITY_PARTICLE_SUFFIXES:
        if text.endswith(suffix):
            stem = text[:-len(suffix)]
            if stem and stem in clean_variants:
                return stem
    return None


def _clean_variant_surfaces(texts: tuple[str, ...]) -> frozenset[str]:
    return frozenset(text for text in texts if text and text == _trim_entity_boundary(text))


def canonical_entity_name(entity: LocalEntity) -> str:
    """PUBLIC display only; representative coordinates and identity remain exact."""
    clean = _trim_entity_boundary(entity.text)
    variants = _clean_variant_surfaces(tuple(row.text for row in entity.merged_mentions))
    return _particle_variant(clean, variants) or clean


def _surface_cleanliness(text: str, clean_variants: frozenset[str]) -> int:
    clean = _trim_entity_boundary(text)
    return (int(text != text.strip()) + int(clean != text.strip()) +
            int(_particle_variant(clean, clean_variants) is not None))


def _entity_representative_key(
        candidate: EntityCandidate,
        final_entity_type: str | None,
        clean_variants: frozenset[str],
) -> tuple[bool, bool, int, int, int, str]:
    """Pronoun, final type, surface boundary, then source order determine display."""
    type_matches = (final_entity_type is not None and
                    candidate.entity_type == final_entity_type)
    return (_is_pronominal_surface(candidate.text), not type_matches,
            _surface_cleanliness(candidate.text, clean_variants),
            candidate.start, candidate.end, candidate.candidate_id)


def close_entity_identity(universe: EntityCandidateUniverse, *,
                          merge_decisions: Mapping[tuple[str, str], bool],
                          resolution_decisions: Mapping[str, str | None],
                          accepted_evidence_ids: frozenset[str] = frozenset(),
                          retained_candidate_ids: frozenset[str] = frozenset(),
                          strict_gold_endpoints: bool = False) -> EntityClosure:
    """Close complete-link identity while preserving each source role fact.

    Accepted ROLE_ONLY mentions share the bounded identity universe with Native
    mentions. A cluster without Native evidence remains SPAN_ONLY even when
    several ROLE_ONLY mentions merge.
    """
    by_id = universe.candidate_by_id()
    if len(by_id) != len(universe.candidates):
        raise ValueError("duplicate Entity candidate ID")
    binding_ids = {binding.evidence_id for binding in universe.bindings}
    if not accepted_evidence_ids <= binding_ids:
        raise ValueError("accepted evidence references unknown role")
    if not retained_candidate_ids <= by_id.keys():
        raise ValueError("retained resolution target references unknown candidate")
    unified = universe.identity_contract == "UNIFIED_MENTION_COREF_V1"
    if unified and any(binding.role != "ASSERTOR" for binding in universe.bindings
                       if binding.evidence_id in resolution_decisions):
        raise ValueError("unified ROLE endpoint cannot use a second resolution decision")
    active = (set(by_id) if unified else
              {candidate_id for candidate_id, candidate in by_id.items()
               if "NER" in candidate.origins or candidate.referential_state == "CONFIRMED"
               or candidate_id in retained_candidate_ids
               or any(evidence_id in accepted_evidence_ids for evidence_id in candidate.evidence_ids)})
    normalized: dict[tuple[str, str], bool] = {}
    for a, b in merge_decisions:
        if a not in by_id or b not in by_id or a == b:
            raise ValueError("Entity coreference decision references unknown/self candidate")
        key = _pair_key(a, b)
        value = bool(merge_decisions[(a, b)])
        if key in normalized and normalized[key] != value:
            raise ValueError("conflicting directed copies of symmetric coreference decision")
        normalized[key] = value
    groups: dict[str, set[str]] = {
        candidate_id: {candidate_id} for candidate_id in sorted(active)}
    group_owner = {candidate_id: candidate_id for candidate_id in active}
    for a, b in sorted(key for key, value in normalized.items() if value):
        if a not in active or b not in active:
            continue
        left_id, right_id = group_owner[a], group_owner[b]
        if left_id == right_id:
            continue
        left, right = groups[left_id], groups[right_id]
        if all(normalized.get(_pair_key(x, y), False) for x in left for y in right):
            left.update(right)
            for member_id in right:
                group_owner[member_id] = left_id
            del groups[right_id]
    entities = []
    candidate_to_entity = {}
    evidence_to_entity: dict[str, str] = {}
    for members in groups.values():
        candidates = [by_id[candidate_id] for candidate_id in sorted(members)]
        has_native = any("NER" in candidate.origins for candidate in candidates)
        observed = {candidate.entity_type for candidate in candidates if candidate.entity_type is not None}
        if universe.source_mode == "PREDICTED":
            scored = [candidate.type_evidence for candidate in candidates
                      if "NER" in candidate.origins and candidate.type_evidence]
            if scored and any(len(values) != len(ENTITY_TYPES) or
                              not all(math.isfinite(value) for value in values) for values in scored):
                raise ValueError("predicted Entity type evidence needs five finite model values")
            if len(observed) == 1:
                # The Native lane already made its five-type source decision.
                # A full logit vector is evidence, not authority to retype a
                # surviving typed mention before or after identity closure.
                entity_type = next(iter(observed))
            elif scored:
                totals = [sum(values[index] for values in scored) for index in range(len(ENTITY_TYPES))]
                entity_type = max(
                    (kind for kind in ENTITY_TYPES if kind in observed),
                    key=lambda kind: (totals[ENTITY_TYPES.index(kind)],
                                      -ENTITY_TYPES.index(kind)))
            elif observed:
                # Direct closure fixtures may supply only member labels. Serving always supplies model vectors.
                entity_type = next(kind for kind in ENTITY_TYPES if kind in observed)
            elif unified:
                # UNKNOWN is an internal mention type. A Native-free completed
                # cluster receives GENERIC only at final Entity projection.
                entity_type = "GENERIC"
            else:
                raise ValueError("predicted Entity cluster lacks five-type evidence")
        else:
            entity_type = (next(iter(observed)) if len(observed) == 1 else
                           "GENERIC" if unified and not observed else None)
        status = ("TYPE_CONFLICT" if len(observed) > 1 else
                  "SPAN_ONLY" if unified and not has_native else
                  "RESOLVED" if entity_type else "UNTYPED")
        clean_variants = _clean_variant_surfaces(tuple(row.text for row in candidates))
        representative = min(
            candidates,
            key=lambda candidate: _entity_representative_key(
                candidate, entity_type, clean_variants))
        # 전체 후보 객체를 PUBLIC까지 보유하지 않고, 서로 다른 비대표 좌표
        # 최대 세 개만 source order로 복사한다.
        merged_mentions = []
        seen_spans = {(representative.start, representative.end)}
        for candidate in sorted(candidates, key=lambda row: (row.start, row.end, row.candidate_id)):
            coordinate = (candidate.start, candidate.end)
            if coordinate in seen_spans:
                continue
            seen_spans.add(coordinate)
            merged_mentions.append(MergedMention(candidate.text, *coordinate))
            if len(merged_mentions) == 3:
                break
        payload = f"{universe.article_version_id}:{universe.content_sha256}:{','.join(sorted(members))}"
        local_id = "ENT:" + sha256(payload.encode()).hexdigest()[:16]
        entity = LocalEntity(local_id, representative.candidate_id, representative.start,
                             representative.end, representative.text, entity_type,
                             tuple(sorted(observed)),
                             tuple(sorted(members)),
                             tuple(sorted({evidence_id for candidate in candidates
                                           for evidence_id in candidate.evidence_ids})), status,
                             tuple((candidate.candidate_id, candidate.entity_type,
                                    candidate.type_evidence) for candidate in candidates),
                             tuple(merged_mentions))
        entities.append(entity)
        for candidate_id in members:
            candidate_to_entity[candidate_id] = local_id
        for evidence_id in entity.evidence_ids:
            if evidence_id in evidence_to_entity and evidence_to_entity[evidence_id] != local_id:
                raise ValueError("one source evidence maps to conflicting Entity identities")
            evidence_to_entity[evidence_id] = local_id
    # Closure ordering remains tied to the member inventory's earliest source span,
    # not to the independently selected display/feature representative.
    entities.sort(key=lambda entity: (
        *min((by_id[candidate_id].start, by_id[candidate_id].end)
             for candidate_id in entity.candidate_ids),
        entity.local_id))
    entity_by_id = {entity.local_id: entity for entity in entities}
    endpoints = []
    bindings_by_id = {binding.evidence_id: binding for binding in universe.bindings}
    if set(resolution_decisions) - set(bindings_by_id):
        raise ValueError("resolution decision has unknown role evidence")
    for binding in universe.bindings:
        if unified and binding.role != "ASSERTOR":
            if binding.status == "PARTIAL_BUDGET" and not binding.candidate_ids:
                endpoints.append(RoleEndpoint(
                    binding.evidence_id, binding.owner_id, binding.role,
                    binding.start, binding.end, binding.text, None,
                    "PARTIAL_BUDGET", binding.source_score, binding.source_windows))
                continue
            if len(binding.candidate_ids) != 1:
                raise ValueError("unified ROLE use must name one retained mention")
            if binding.candidate_ids[0] not in candidate_to_entity:
                endpoints.append(RoleEndpoint(
                    binding.evidence_id, binding.owner_id, binding.role,
                    binding.start, binding.end, binding.text, None,
                    "UNRESOLVED_REFERENTIAL", binding.source_score,
                    binding.source_windows))
                continue
            entity = entity_by_id[candidate_to_entity[binding.candidate_ids[0]]]
            status = ("RESOLVED_TYPE_CONFLICT" if entity.status == "TYPE_CONFLICT" else
                      "SPAN_ONLY" if entity.status == "SPAN_ONLY" else
                      "RESOLVED")
            endpoints.append(RoleEndpoint(
                binding.evidence_id, binding.owner_id, binding.role,
                binding.start, binding.end, binding.text, entity.local_id, status,
                binding.source_score, binding.source_windows))
            continue
        choice = resolution_decisions.get(binding.evidence_id)
        endpoint_id = None
        if binding.status == "PARTIAL_BUDGET":
            status = "PARTIAL_BUDGET"
        elif binding.status == "SPAN_ONLY":
            if choice is not None:
                raise ValueError("SPAN_ONLY source cannot acquire a fake Entity endpoint")
            status = "SPAN_ONLY"
        elif choice is None:
            status = ("UNRESOLVED_REFERENTIAL" if binding.role in ("ACTOR", "TARGET", "PLACE")
                      else "SPAN_ONLY")
        elif choice not in candidate_to_entity:
            raise ValueError("resolution endpoint references unknown Entity candidate")
        else:
            entity = entity_by_id[candidate_to_entity[choice]]
            status = ("RESOLVED" if entity.status == "RESOLVED" else
                      "RESOLVED_TYPE_CONFLICT" if entity.status == "TYPE_CONFLICT" else
                      "UNRESOLVED_REFERENTIAL" if binding.role in ("ACTOR", "TARGET", "PLACE")
                      else "SPAN_ONLY")
            endpoint_id = entity.local_id if status.startswith("RESOLVED") else None
        if strict_gold_endpoints and binding.role in ("ACTOR", "TARGET") and status not in (
                "RESOLVED", "RESOLVED_TYPE_CONFLICT"):
            raise ValueError(f"Gold {binding.role} endpoint was lost: {binding.evidence_id}")
        endpoints.append(RoleEndpoint(binding.evidence_id, binding.owner_id, binding.role,
                                      binding.start, binding.end, binding.text, endpoint_id, status,
                                      binding.source_score, binding.source_windows))
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
