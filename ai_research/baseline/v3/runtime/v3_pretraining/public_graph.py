"""v3 scalar construction에서 선택된 article-local PUBLIC graph로의 순수 투영.

원문은 request owner가 유지한다. 이 모듈은 선택 후 필요한 source evidence만 직렬화하며
Identity를 재판정하거나 tensor/DB identity를 PUBLIC에 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import TYPE_CHECKING, Any, Mapping

from runtime.v3_pretraining.canonical_text import GroundedStatement, canonicalize_event, canonicalize_statement
from runtime.v3_pretraining.entity_identity import EntityClosure
from runtime.v3_pretraining.event_identity import EventClosure
from runtime.v3_pretraining.source_layout import RawArticle
from runtime.v3_pretraining.temporal import TemporalOccurrence, calendar_eligible, parse_canonical_time

if TYPE_CHECKING:
    from runtime.v3_pretraining.attribution_scoring import AssertedByFact, RelationFact
    from runtime.v3_pretraining.primary_scoring import PrimaryScore


SCHEMA_VERSION = "articlelocal-kg-public-v3"
PROJECTION_VERSION = "v3-public-projection-r1"
ENTITY_TYPES = frozenset({"PERSON", "ORGANIZATION", "LOCATION", "PRODUCT", "GENERIC"})
NODE_KINDS = frozenset({"ARTICLE", "EVENT", "STATEMENT", "ENTITY", "TIME"})
EDGE_ENDPOINTS = {
    "COVERS": ("ARTICLE", "EVENT"),
    "CONTAINS_STATEMENT": ("ARTICLE", "STATEMENT"),
    "MENTIONS": ("ARTICLE", "ENTITY"),
    "ACTOR": ("EVENT", "ENTITY"), "TARGET": ("EVENT", "ENTITY"),
    "PLACE": ("EVENT", "ENTITY"), "ASSERTED_BY": ("STATEMENT", "ENTITY"),
    "OCCURRED_ON": ("EVENT", "TIME"), "ABOUT": ("STATEMENT", "EVENT"),
    "CAUSES": ("EVENT", "EVENT"),
}
NODE_PROPERTIES = {
    "ARTICLE": frozenset({"article_id", "article_version_id", "title", "published_at"}),
    "EVENT": frozenset({"canonical_text", "canonical_status", "canonical_rule_version", "primary_score", "primary_score_status", "primary_score_producer", "local_id"}),
    "STATEMENT": frozenset({"canonical_text", "canonical_status", "canonical_rule_version", "statement_type", "primary_score", "primary_score_status", "primary_score_producer", "local_id"}),
    "ENTITY": frozenset({"canonical_name", "entity_type", "local_id"}),
    "TIME": frozenset({"normalized_value", "granularity", "local_id"}),
}
EDGE_PROPERTIES = {
    "COVERS": frozenset({"isPrimary"}),
    "CONTAINS_STATEMENT": frozenset(), "MENTIONS": frozenset(),
    "ACTOR": frozenset({"endpoint_status", "evidence_ids"}),
    "TARGET": frozenset({"endpoint_status", "evidence_ids"}),
    "PLACE": frozenset({"endpoint_status", "evidence_ids"}),
    "ASSERTED_BY": frozenset({"endpoint_status", "evidence_id"}),
    "OCCURRED_ON": frozenset({"member_ids"}),
    "ABOUT": frozenset({"relation_logit"}), "CAUSES": frozenset({"relation_logit"}),
}
ROOT_KEYS = frozenset({"schema_version", "projection_version", "article", "status", "persistence_ready", "nodes", "edges", "diagnostics"})
EVIDENCE_KEYS = frozenset({"article_id", "start", "end", "text", "evidence_ids"})


@dataclass(frozen=True, slots=True)
class V3ConstructionResult:
    """모델과 closure가 만든 scalar 결과. 원문은 PUBLIC 출력 전까지만 소유한다."""

    article: RawArticle
    title: str
    events: EventClosure
    entities: EntityClosure
    statements: tuple[GroundedStatement, ...]
    times: tuple[TemporalOccurrence, ...]
    asserted_by: tuple[AssertedByFact, ...]
    relations: tuple[RelationFact, ...]
    primary_scores: tuple[PrimaryScore, ...]
    producer_version: str


def _unique(rows: tuple[Any, ...], attr: str) -> dict[str, Any]:
    result = {getattr(row, attr): row for row in rows}
    if len(result) != len(rows) or "" in result:
        raise ValueError(f"duplicate/empty {attr}")
    return result


def _evidence(article: RawArticle, start: int, end: int, text: str,
              evidence_ids: tuple[str, ...]) -> dict[str, Any]:
    if not 0 <= start < end <= len(article.content) or article.content[start:end] != text:
        raise ValueError("PUBLIC evidence differs from exact source")
    return {"article_id": article.article_id, "start": start, "end": end,
            "text": text, "evidence_ids": list(evidence_ids)}


def _score_map(source: V3ConstructionResult, event_ids: set[str],
               statement_ids: set[str]) -> dict[tuple[str, str], PrimaryScore]:
    scores: dict[tuple[str, str], PrimaryScore] = {}
    for row in source.primary_scores:
        if row.kind not in ("EVENT_CLUSTER", "STATEMENT") or not math.isfinite(row.primary_score):
            raise ValueError("invalid Primary score")
        key = (row.kind, row.local_id)
        if key in scores or row.local_id not in (event_ids if row.kind == "EVENT_CLUSTER" else statement_ids):
            raise ValueError("duplicate/unknown Primary score")
        scores[key] = row
    return scores


def _trained(status: str) -> bool:
    return status not in ("UNTRAINED_FRESH_WEIGHT_DIAGNOSTIC", "UNAVAILABLE") and not status.startswith("UNTRAINED")


def _validate_construction(source: V3ConstructionResult) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[tuple[str, str], PrimaryScore]]:
    if (not source.producer_version or source.events.source_mode != "PREDICTED" or
            source.entities.source_mode != "PREDICTED" or
            source.events.article_version_id != source.article.article_version_id or
            source.events.content_sha256 != source.article.content_sha256):
        raise ValueError("construction article version/hash mismatch")
    events = _unique(source.events.events, "local_id")
    entities = _unique(source.entities.entities, "local_id")
    statements = _unique(source.statements, "local_id")
    times = _unique(source.times, "local_id")
    if len(set(events) | set(entities) | set(statements) | set(times)) != sum(map(len, (events, entities, statements, times))):
        raise ValueError("local graph IDs collide")
    scores = _score_map(source, set(events), set(statements))
    for row in source.statements:
        row.validate(source.article)
    for row in source.events.events:
        _evidence(source.article, row.start, row.end, row.text, (row.representative_member_id,))
        for start, end, text, _ in row.triggers:
            _evidence(source.article, start, end, text, ())
        for role in row.roles:
            _evidence(source.article, role.start, role.end, role.text, role.evidence_ids)
            if role.role not in ("ACTOR", "TARGET", "PLACE") or role.entity_id is not None and role.entity_id not in entities:
                raise ValueError("Event role endpoint is invalid")
        for attached in row.times:
            if attached.time_id not in times:
                raise ValueError("Event Time endpoint is unknown")
            if not attached.member_ids or not set(attached.member_ids) <= set(times[attached.time_id].attached_event_ids):
                raise ValueError("Event Time fact lacks learned member attachment")
    for row in source.entities.entities:
        _evidence(source.article, row.start, row.end, row.text, row.evidence_ids)
    for row in source.times:
        _evidence(source.article, row.start, row.end, row.text, row.evidence_ids)
        if row.normalized_value is not None:
            parsed = parse_canonical_time(row.normalized_value)
            if parsed.granularity != row.granularity:
                raise ValueError("Time granularity differs from normalized value")
        if row.calendar_eligible != calendar_eligible(row.normalized_value):
            raise ValueError("Time calendar eligibility mismatch")
    for row in source.asserted_by:
        _evidence(source.article, row.start, row.end, row.text, (row.evidence_id,))
        if row.statement_id not in statements or row.entity_id is not None and row.entity_id not in entities:
            raise ValueError("Assertor endpoint is unknown")
    seen_relations: set[tuple[str, str, str]] = set()
    for row in source.relations:
        if not math.isfinite(row.logit):
            raise ValueError("non-finite relation logit")
        if row.relation == "ABOUT":
            valid = row.source_id in statements and row.target_id in events
        elif row.relation == "CAUSES":
            valid = row.source_id in events and row.target_id in events and row.source_id != row.target_id
        else:
            valid = False
        if not valid:
            raise ValueError("relation has invalid ordered final local endpoint")
        relation_key = (row.relation, row.source_id, row.target_id)
        if relation_key in seen_relations:
            raise ValueError("duplicate final local relation pair")
        seen_relations.add(relation_key)
    return events, entities, statements, times, scores


def project_public(source: V3ConstructionResult, *, selected_event_ids: frozenset[str] | None = None,
                   selected_statement_ids: frozenset[str] | None = None,
                   score_threshold: float | None = None,
                   diagnostic_unfiltered: bool = False) -> dict[str, Any]:
    """선택 집합 또는 외부 threshold로 PUBLIC을 만든다. 기본은 score 있는 전 proposition."""
    events, entities, statements, times, scores = _validate_construction(source)
    if score_threshold is not None and (selected_event_ids is not None or selected_statement_ids is not None):
        raise ValueError("explicit selection and threshold are mutually exclusive")
    if score_threshold is not None and not math.isfinite(score_threshold):
        raise ValueError("score threshold must be finite")
    all_keys = {("EVENT_CLUSTER", key) for key in events} | {("STATEMENT", key) for key in statements}
    missing = all_keys - set(scores)
    if score_threshold is not None and (missing or any(not _trained(score.status) for score in scores.values())):
        raise ValueError("threshold requires all trained Primary scores")
    if score_threshold is not None:
        selected_events = {key for key in events if scores[("EVENT_CLUSTER", key)].primary_score >= score_threshold}
        selected_statements = {key for key in statements if scores[("STATEMENT", key)].primary_score >= score_threshold}
    else:
        selected_events = set(events) if selected_event_ids is None else set(selected_event_ids)
        selected_statements = set(statements) if selected_statement_ids is None else set(selected_statement_ids)
    if selected_events - set(events) or selected_statements - set(statements):
        raise ValueError("selection includes unknown final local ID")
    selected_keys = {("EVENT_CLUSTER", key) for key in selected_events} | {
        ("STATEMENT", key) for key in selected_statements}
    if selected_keys - set(scores) and not diagnostic_unfiltered:
        raise ValueError("Primary score missing; explicit diagnostic_unfiltered required")
    article = source.article
    article_node_id = "ARTICLE:" + article.article_version_id
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    def node(kind: str, local_id: str, properties: dict[str, Any], evidence: list[dict[str, Any]]) -> None:
        nodes.append({"node_id": local_id, "kind": kind, "properties": properties, "evidence": evidence})
    def edge(kind: str, left: str, right: str, properties: dict[str, Any] | None = None,
             evidence: list[dict[str, Any]] | None = None) -> None:
        edges.append({"edge_id": f"{kind}:{left}:{right}:{len(edges)}", "edge_type": kind,
                      "source_id": left, "target_id": right,
                      "properties": properties or {}, "evidence": evidence or []})
    node("ARTICLE", article_node_id, {"article_id": article.article_id,
         "article_version_id": article.article_version_id, "title": source.title,
         "published_at": article.published_at}, [])
    primary = None
    selected_scored = [events[key] for key in selected_events if ("EVENT_CLUSTER", key) in scores]
    if len(selected_scored) == len(selected_events) and selected_scored and all(
            _trained(scores[("EVENT_CLUSTER", row.local_id)].status) for row in selected_scored):
        primary = min(selected_scored, key=lambda row: (-scores[("EVENT_CLUSTER", row.local_id)].primary_score,
                                                        row.start, row.end, row.local_id)).local_id
    semantic_entities: set[str] = set()
    semantic_times: set[str] = set()
    omitted = {"unresolved_role": 0, "unresolved_assertor": 0,
               "noncalendar_time_attachment": 0, "filtered_relation": 0}
    for key in sorted(selected_events, key=lambda value: (events[value].start, events[value].end, value)):
        row = events[key]
        canonical = canonicalize_event(article, row)
        score = scores.get(("EVENT_CLUSTER", key))
        node("EVENT", key, {"local_id": key, "canonical_text": canonical.text,
             "canonical_status": canonical.status, "canonical_rule_version": canonical.rule_version,
             "primary_score": score.primary_score if score else None,
             "primary_score_status": score.status if score else "UNAVAILABLE",
             "primary_score_producer": source.producer_version if score else None},
             [_evidence(article, row.start, row.end, row.text, (row.representative_member_id,))])
        edge("COVERS", article_node_id, key, {"isPrimary": key == primary if primary else None})
        for role in row.roles:
            if role.entity_id is None:
                omitted["unresolved_role"] += 1
                continue
            semantic_entities.add(role.entity_id)
            edge(role.role, key, role.entity_id, {"endpoint_status": role.endpoint_status,
                 "evidence_ids": list(role.evidence_ids)},
                 [_evidence(article, role.start, role.end, role.text, role.evidence_ids)])
        for attached in row.times:
            time = times[attached.time_id]
            if not calendar_eligible(time.normalized_value):
                omitted["noncalendar_time_attachment"] += 1
                continue
            semantic_times.add(time.local_id)
            edge("OCCURRED_ON", key, time.local_id, {"member_ids": list(attached.member_ids)},
                 [_evidence(article, time.start, time.end, time.text, time.evidence_ids)])
    for key in sorted(selected_statements, key=lambda value: (statements[value].grounding.start, value)):
        row = statements[key]
        canonical = canonicalize_statement(article, row)
        score = scores.get(("STATEMENT", key))
        node("STATEMENT", key, {"local_id": key, "canonical_text": canonical.text,
             "canonical_status": canonical.status, "canonical_rule_version": canonical.rule_version,
             "statement_type": row.statement_type,
             "primary_score": score.primary_score if score else None,
             "primary_score_status": score.status if score else "UNAVAILABLE",
             "primary_score_producer": source.producer_version if score else None},
             [_evidence(article, row.grounding.start, row.grounding.end,
                        row.grounding.text, (row.grounding.evidence_id,))])
        edge("CONTAINS_STATEMENT", article_node_id, key)
    for row in source.asserted_by:
        if row.statement_id not in selected_statements:
            continue
        if row.entity_id is None:
            omitted["unresolved_assertor"] += 1
            continue
        semantic_entities.add(row.entity_id)
        edge("ASSERTED_BY", row.statement_id, row.entity_id,
             {"endpoint_status": row.status, "evidence_id": row.evidence_id},
             [_evidence(article, row.start, row.end, row.text, (row.evidence_id,))])
    for key in sorted(semantic_entities, key=lambda value: (entities[value].start, value)):
        row = entities[key]
        if row.entity_type not in ENTITY_TYPES:
            raise ValueError(f"selected semantic Entity type requires backend resolution: {key}")
        node("ENTITY", key, {"local_id": key, "canonical_name": row.text,
             "entity_type": row.entity_type},
             [_evidence(article, row.start, row.end, row.text, row.evidence_ids)])
        edge("MENTIONS", article_node_id, key)
    for key in sorted(semantic_times, key=lambda value: (times[value].start, value)):
        row = times[key]
        node("TIME", key, {"local_id": key, "normalized_value": row.normalized_value,
             "granularity": row.granularity},
             [_evidence(article, row.start, row.end, row.text, row.evidence_ids)])
    for row in source.relations:
        if row.relation == "ABOUT" and row.source_id in selected_statements and row.target_id in selected_events or (
                row.relation == "CAUSES" and row.source_id in selected_events and row.target_id in selected_events):
            edge(row.relation, row.source_id, row.target_id, {"relation_logit": row.logit})
        else:
            omitted["filtered_relation"] += 1
    ready = primary is not None and all(key in scores and _trained(scores[key].status) for key in selected_keys)
    result = {"schema_version": SCHEMA_VERSION, "projection_version": PROJECTION_VERSION,
              "article": {"article_id": article.article_id, "article_version_id": article.article_version_id,
                          "title": source.title, "published_at": article.published_at,
                          "content_sha256": article.content_sha256},
              "status": "PERSISTENCE_READY" if ready else "PERSISTENCE_NOT_READY",
              "persistence_ready": ready, "nodes": nodes, "edges": edges,
              "diagnostics": {"omitted": omitted, "selected_event_count": len(selected_events),
                              "selected_statement_count": len(selected_statements),
                              "unavailable_score_count": len(selected_keys - set(scores)),
                              "untrained_score_count": sum(key in scores and not _trained(scores[key].status)
                                                           for key in selected_keys)}}
    validate_public(result, article)
    return result


def validate_public(payload: Mapping[str, Any], source: RawArticle | None = None) -> None:
    """v3 allowlist와 endpoint, source grounding, N1 저장 전제 조건을 검증한다."""
    if set(payload) != ROOT_KEYS or payload["schema_version"] != SCHEMA_VERSION or payload["projection_version"] != PROJECTION_VERSION:
        raise ValueError("v3 PUBLIC root schema mismatch")
    if set(payload["article"]) != {"article_id", "article_version_id", "title", "published_at", "content_sha256"}:
        raise ValueError("v3 PUBLIC article schema mismatch")
    diagnostics = payload["diagnostics"]
    if (set(diagnostics) != {"omitted", "selected_event_count", "selected_statement_count",
                             "unavailable_score_count", "untrained_score_count"} or
            set(diagnostics["omitted"]) != {"unresolved_role", "unresolved_assertor",
                                            "noncalendar_time_attachment", "filtered_relation"}):
        raise ValueError("v3 PUBLIC diagnostics allowlist mismatch")
    if source is not None and (payload["article"]["article_id"] != source.article_id or
                               payload["article"]["article_version_id"] != source.article_version_id or
                               payload["article"]["content_sha256"] != source.content_sha256):
        raise ValueError("PUBLIC article provenance mismatch")
    ids: dict[str, str] = {}
    for row in payload["nodes"]:
        if set(row) != {"node_id", "kind", "properties", "evidence"} or row["kind"] not in NODE_KINDS:
            raise ValueError("unknown PUBLIC node field/kind")
        if row["node_id"] in ids or set(row["properties"]) != NODE_PROPERTIES[row["kind"]]:
            raise ValueError("duplicate node or invalid node property allowlist")
        ids[row["node_id"]] = row["kind"]
        if row["kind"] == "ENTITY" and row["properties"]["entity_type"] not in ENTITY_TYPES:
            raise ValueError("PUBLIC Entity type outside internal taxonomy")
        if row["kind"] == "TIME" and (not calendar_eligible(row["properties"]["normalized_value"]) or
                                       parse_canonical_time(row["properties"]["normalized_value"]).granularity != row["properties"]["granularity"]):
            raise ValueError("PUBLIC Time must be actual point calendar value")
        if row["kind"] in ("EVENT", "STATEMENT"):
            score = row["properties"]["primary_score"]
            if score is not None and (not isinstance(score, (float, int)) or not math.isfinite(score)):
                raise ValueError("nonfinite PUBLIC Primary score")
        for evidence in row["evidence"]:
            _validate_evidence(evidence, payload["article"]["article_id"], source)
    covers: list[bool | None] = []
    covered_ids: set[str] = set()
    contained_ids: set[str] = set()
    seen_edge_ids: set[str] = set()
    semantic_entity_ids: set[str] = set()
    attached_time_ids: set[str] = set()
    for row in payload["edges"]:
        if set(row) != {"edge_id", "edge_type", "source_id", "target_id", "properties", "evidence"}:
            raise ValueError("unknown PUBLIC edge field")
        kind = row["edge_type"]
        if row["edge_id"] in seen_edge_ids:
            raise ValueError("duplicate PUBLIC edge ID")
        seen_edge_ids.add(row["edge_id"])
        if kind not in EDGE_ENDPOINTS or set(row["properties"]) != EDGE_PROPERTIES[kind]:
            raise ValueError("unknown PUBLIC edge/property")
        if kind in ("ABOUT", "CAUSES") and (
                not isinstance(row["properties"]["relation_logit"], (int, float)) or
                not math.isfinite(row["properties"]["relation_logit"])):
            raise ValueError("PUBLIC relation logit invalid")
        expected = EDGE_ENDPOINTS[kind]
        if (ids.get(row["source_id"]), ids.get(row["target_id"])) != expected:
            raise ValueError("dangling or invalid PUBLIC edge endpoint")
        if kind == "CAUSES" and row["source_id"] == row["target_id"]:
            raise ValueError("CAUSES needs ordered distinct Event endpoints")
        if kind == "COVERS":
            if row["target_id"] in covered_ids:
                raise ValueError("duplicate COVERS Event")
            covers.append(row["properties"]["isPrimary"])
            covered_ids.add(row["target_id"])
        if kind == "CONTAINS_STATEMENT":
            if row["target_id"] in contained_ids:
                raise ValueError("duplicate Statement containment")
            contained_ids.add(row["target_id"])
        if kind in ("ACTOR", "TARGET", "PLACE", "ASSERTED_BY"):
            semantic_entity_ids.add(row["target_id"])
        if kind == "OCCURRED_ON":
            attached_time_ids.add(row["target_id"])
        for evidence in row["evidence"]:
            _validate_evidence(evidence, payload["article"]["article_id"], source)
    if sum(kind == "ARTICLE" for kind in ids.values()) != 1:
        raise ValueError("PUBLIC needs exactly one Article")
    if {key for key, kind in ids.items() if kind == "EVENT"} != covered_ids or {
            key for key, kind in ids.items() if kind == "STATEMENT"} != contained_ids:
        raise ValueError("PUBLIC proposition lacks Article containment")
    if {key for key, kind in ids.items() if kind == "ENTITY"} != semantic_entity_ids:
        raise ValueError("PUBLIC Entity lacks semantic proposition relation")
    if {key for key, kind in ids.items() if kind == "TIME"} != attached_time_ids:
        raise ValueError("PUBLIC Time lacks selected Event attachment")
    if payload["persistence_ready"]:
        if payload["status"] != "PERSISTENCE_READY" or not covers or covers.count(True) != 1 or any(value not in (True, False) for value in covers):
            raise ValueError("N1 persisted Article requires COVERS and one isPrimary")
        if any(row["properties"]["primary_score"] is None or
               not _trained(row["properties"]["primary_score_status"])
               for row in payload["nodes"] if row["kind"] in ("EVENT", "STATEMENT")):
            raise ValueError("persistence-ready graph requires trained proposition score")
    elif payload["status"] != "PERSISTENCE_NOT_READY":
        raise ValueError("PUBLIC readiness status mismatch")
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def _validate_evidence(evidence: Mapping[str, Any], article_id: str, source: RawArticle | None) -> None:
    if set(evidence) != EVIDENCE_KEYS or evidence["article_id"] != article_id or not isinstance(evidence["evidence_ids"], list):
        raise ValueError("PUBLIC evidence schema/article mismatch")
    if not isinstance(evidence["start"], int) or not isinstance(evidence["end"], int) or evidence["start"] >= evidence["end"] or not isinstance(evidence["text"], str):
        raise ValueError("PUBLIC evidence span invalid")
    if source is not None:
        _evidence(source, evidence["start"], evidence["end"], evidence["text"], tuple(evidence["evidence_ids"]))


def serialize_public(payload: Mapping[str, Any], *, source: RawArticle | None = None,
                     pretty: bool = False) -> str:
    validate_public(payload, source)
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2 if pretty else None,
                      sort_keys=pretty)
