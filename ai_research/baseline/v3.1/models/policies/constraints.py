"""endpoint/role/schema 제약. 모든 함수는 학습 parameter를 갖지 않는다."""

from __future__ import annotations

from typing import Mapping

from models.contracts import LEGACY_RELATION_ONTOLOGY, PRODUCTION_RELATION_ONTOLOGY


PRODUCTION_HARD_RELATION_ENDPOINTS = {
    "CAUSES": frozenset({("EVENT", "EVENT")}),
    "SUBEVENT_OF": frozenset({("EVENT", "EVENT")}),
    "ASSERTED_BY": frozenset({("STATEMENT", "ENTITY")}),
    "ABOUT": frozenset({("STATEMENT", "EVENT"), ("STATEMENT", "ENTITY")}),
    "PART_OF": frozenset({("EVENT", "STORY")}),
}
STORY_SOFT_RELATIONS = frozenset(
    {
        "response-like",
        "precondition",
        "consequence",
        "temporal continuity",
        "semantic continuity",
        "participant continuity",
        "co-participation",
    }
)
LEGACY_HARD_RELATION_ENDPOINTS = {
    "CAUSES": frozenset({("EVENT", "EVENT")}),
    "RESPONDS_TO": frozenset({("EVENT", "EVENT")}),
    "ABOUT": frozenset({("STATEMENT", "EVENT"), ("STATEMENT", "ENTITY")}),
}


def allowed_argument_labels(target_kind: str, target_entity_type: str | None = None) -> frozenset[str]:
    if target_kind == "TIME":
        return frozenset(("NONE", "TIME"))
    if target_kind in {"EVIDENCE", "TYPED_LITERAL"}:
        return frozenset(("NONE", "TARGET"))
    if target_kind == "ENTITY":
        # Entity type는 noisy Gold/runtime prediction일 수 있어 hard exclusion에 쓰지 않는다.
        return frozenset(("NONE", "ACTOR", "TARGET", "PLACE"))
    return frozenset(("NONE",))


def allowed_legacy_relation_labels(
    source_kind: str, target_kind: str
) -> frozenset[str]:
    if source_kind == "EVENT" and target_kind == "EVENT":
        return frozenset(("NONE", "CAUSES", "RESPONDS_TO"))
    if source_kind == "STATEMENT" and target_kind in {"EVENT", "ENTITY"}:
        return frozenset(("NONE", "ABOUT"))
    return frozenset(("NONE",))


# Historical import alias.
allowed_relation_labels = allowed_legacy_relation_labels


def allowed_production_relation_labels(
    task: str,
    source_kind: str,
    target_kind: str,
) -> frozenset[str]:
    labels = {
        "causal": "CAUSES",
        "subevent": "SUBEVENT_OF",
        "statement_about": "ABOUT",
    }
    try:
        positive = labels[task]
    except KeyError as error:
        raise ValueError(f"unknown production relation task: {task}") from error
    if (source_kind, target_kind) in PRODUCTION_HARD_RELATION_ENDPOINTS[positive]:
        return frozenset(("NONE", positive))
    return frozenset(("NONE",))


def validate_cardinality(edge_type: str, source_id: str, target_id: str) -> None:
    if not source_id or not target_id:
        raise ValueError("graph edge endpoints must be non-empty")
    if edge_type in {"CAUSES", "RESPONDS_TO", "SUBEVENT_OF"} and source_id == target_id:
        raise ValueError("Event self-edge is forbidden")


def validate_hard_relation_endpoint(
    edge_type: str,
    source_kind: str,
    target_kind: str,
    *,
    ontology_mode: str,
) -> None:
    """ontology mode별 hard KG edge endpoint를 fail-loud 검증한다."""

    if edge_type in STORY_SOFT_RELATIONS:
        raise ValueError(f"story soft relation cannot be a hard KG edge: {edge_type}")
    endpoints = (
        PRODUCTION_HARD_RELATION_ENDPOINTS
        if ontology_mode == PRODUCTION_RELATION_ONTOLOGY
        else LEGACY_HARD_RELATION_ENDPOINTS
        if ontology_mode == LEGACY_RELATION_ONTOLOGY
        else None
    )
    if endpoints is None:
        raise ValueError(f"unknown relation ontology mode: {ontology_mode}")
    if (
        ontology_mode == PRODUCTION_RELATION_ONTOLOGY
        and edge_type == "RESPONDS_TO"
    ):
        raise ValueError("RESPONDS_TO is legacy-only and cannot be a production hard edge")
    if edge_type not in endpoints:
        return
    actual = (source_kind, target_kind)
    if actual not in endpoints[edge_type]:
        raise ValueError(f"{edge_type} endpoint is invalid: {actual}")


def validate_subevent_semantics(
    parent_properties: Mapping[str, object],
    edge_properties: Mapping[str, object],
) -> None:
    """SUBEVENT_OF parent grounding과 compatibility evidence를 검증한다."""

    if parent_properties.get("synthetic") is True:
        raise ValueError("SUBEVENT_OF synthetic parent Event is forbidden")
    if parent_properties.get("grounded") is not True:
        raise ValueError("SUBEVENT_OF parent must be a grounded Event")
    if parent_properties.get("bounded_episode") is not True:
        raise ValueError("SUBEVENT_OF parent must be a bounded episode")
    if edge_properties.get("temporal_compatible") is not True:
        raise ValueError("SUBEVENT_OF requires temporal compatibility")
    if edge_properties.get("situational_compatible") is not True:
        raise ValueError("SUBEVENT_OF requires situational compatibility")
