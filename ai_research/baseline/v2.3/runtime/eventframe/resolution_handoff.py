"""Entity identity feature와 resolved role fact의 compact handoff.

모델 tensor sum/count는 실행 scope 안에서만 존재한다. role fact의 evidence는
version+offset/text의 JSON-safe 값이며 raw EntityMention/rescue owner를 참조하지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

import torch


@dataclass(slots=True)
class EntityRepresentationAggregate:
    member_sum: torch.Tensor | None
    member_count: int
    max_member_score: float

    def release(self) -> None:
        self.member_sum = None


@dataclass(slots=True)
class IdentityResolutionHandoff:
    entity_by_local_id: dict[str, EntityRepresentationAggregate]
    resolved_role_facts: tuple[dict[str, Any], ...]
    role_feature_sets: dict[str, dict[str, frozenset[tuple[str, str]]]]
    entity_identity_remap: dict[str, str] = field(default_factory=dict)

    def release(self) -> None:
        for aggregate in self.entity_by_local_id.values():
            aggregate.release()
        self.entity_by_local_id.clear()
        self.role_feature_sets.clear()
        self.entity_identity_remap.clear()


def _grounding(article_version_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "article_version_id": article_version_id,
        "char_start": int(row["char_start"]),
        "char_end": int(row["char_end"]),
        "sentence_index": int(row["sentence_index"]),
        "text": str(row["text"]),
    }


def _fact_id(event_id: str, role: str, local_id: str) -> str:
    material = "\u241f".join((event_id, role, local_id)).encode("utf-8")
    return "RFACT-" + sha256(material).hexdigest()[:24]


def build_resolved_role_facts(
    article_version_id: str,
    resolution_rows: tuple[Mapping[str, Any], ...],
    filler_by_evidence_id: Mapping[str, Mapping[str, Any]],
    canonical_entity_by_id: Mapping[str, Mapping[str, Any]],
    local_entities: tuple[Mapping[str, Any], ...],
    coreference_rows: tuple[Mapping[str, Any], ...] = (),
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, frozenset[tuple[str, str]]]]]:
    """Event/role/LocalEntity별 max score와 각 실제 grounding을 집계한다."""
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    feature_sets: dict[str, dict[str, set[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    local_by_id = {row["local_entity_id"]: row for row in local_entities}
    coreference_by_pair = {
        frozenset((str(row["left_entity_prediction_id"]),
                   str(row["right_entity_prediction_id"]))): row
        for row in coreference_rows
    }
    for row in resolution_rows:
        if row.get("resolution_status") != "ENTITY_RESOLVED":
            continue
        event_id = str(row["source_event_prediction_id"])
        role = str(row["role"])
        local_id = str(row["target_local_entity_id"])
        entity_id = str(row["target_entity_prediction_id"])
        if local_id not in local_by_id or entity_id not in canonical_entity_by_id:
            raise ValueError("resolved role fact has absent canonical Entity target")
        grouped[(event_id, role, local_id)].append(row)
        feature_sets[event_id][role].add((local_id, entity_id))

    facts = []
    for (event_id, role, local_id), rows in sorted(grouped.items()):
        winner = min(rows, key=lambda row: (
            -float(row["resolution_score"]), str(row["participant_evidence_id"]),
        ))
        filler_groundings = {}
        entity_groundings = {}
        rescue_groundings = {}
        for row in rows:
            filler = filler_by_evidence_id[str(row["participant_evidence_id"])]
            filler_key = (int(filler["char_start"]), int(filler["char_end"]))
            filler_groundings[filler_key] = _grounding(article_version_id, filler)
            entity_id = str(row["target_entity_prediction_id"])
            entity_groundings[entity_id] = _grounding(
                article_version_id, canonical_entity_by_id[entity_id],
            )
            if row.get("rescue_grounding"):
                rescue = row["rescue_grounding"]
                rescue_groundings[str(row["scored_entity_prediction_id"])] = dict(rescue)
        representative_id = str(local_by_id[local_id]["representative_entity_prediction_id"])
        representative = _grounding(
            article_version_id, canonical_entity_by_id[representative_id],
        )
        coreference_witnesses = []
        for entity_id in sorted(entity_groundings):
            if entity_id == representative_id:
                continue
            witness = coreference_by_pair.get(frozenset((entity_id, representative_id)))
            if witness is None:
                raise ValueError("resolved Entity member lacks coreference grounding witness")
            coreference_witnesses.append({
                "left_entity_prediction_id": entity_id,
                "right_entity_prediction_id": representative_id,
                "score": float(witness["score"]),
                "left_grounding": entity_groundings[entity_id],
                "right_grounding": representative,
            })
        facts.append({
            "fact_id": _fact_id(event_id, role, local_id),
            "canonical_event_mention_id": event_id,
            "role": role,
            "local_entity_id": local_id,
            "confidence": float(winner["resolution_score"]),
            "representative_participant_evidence_id": winner["participant_evidence_id"],
            "representative_entity_prediction_id": representative_id,
            "representative_entity_grounding": representative,
            "filler_groundings": tuple(filler_groundings[key]
                                       for key in sorted(filler_groundings)),
            "entity_groundings": tuple(entity_groundings[key]
                                       for key in sorted(entity_groundings)),
            "coreference_witnesses": tuple(coreference_witnesses),
            "rescue_groundings": tuple(rescue_groundings[key]
                                       for key in sorted(rescue_groundings)),
            "independent_filler_count": len(filler_groundings),
        })
    frozen_sets = {
        event_id: {role: frozenset(values) for role, values in roles.items()}
        for event_id, roles in feature_sets.items()
    }
    return tuple(facts), frozen_sets
