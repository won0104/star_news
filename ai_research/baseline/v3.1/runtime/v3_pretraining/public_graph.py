"""v3 scalar construction에서 선택된 article-local PUBLIC graph로의 순수 투영.

원문은 request owner가 유지한다. 이 모듈은 선택 후 필요한 source evidence만 직렬화하며
Identity를 재판정하거나 tensor/DB identity를 PUBLIC에 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
from typing import TYPE_CHECKING, Any, Mapping

from runtime.v3_pretraining.canonical_text import (
    CanonicalSourceView,
    CanonicalTextResult,
    GroundedStatement,
    canonicalize_event,
    canonicalize_statement,
    source_only_event,
    source_only_statement,
)
from runtime.v3_pretraining.entity_identity import EntityClosure, canonical_entity_name
from runtime.v3_pretraining.event_identity import EventClosure, LocalEventState, LocalRoleFact, ROLES
from runtime.v3_pretraining.public_confidence import EdgeScore, PublicEdgeScores
from runtime.v3_pretraining.source_layout import RawArticle
from runtime.v3_pretraining.temporal import (
    TIME_PROJECTION_POLICY_VERSION,
    TemporalOccurrence,
    calendar_eligible,
    classify_time_projection_semantics,
    parse_canonical_time,
    time_public_projection_decision,
)

if TYPE_CHECKING:
    from runtime.v3_pretraining.attribution_scoring import AssertedByFact, RelationFact
    from runtime.v3_pretraining.primary_scoring import PrimaryScore


SCHEMA_VERSION = "articlelocal-kg-public-v3"
PROJECTION_VERSION = "v3-public-projection-r9-participant-accepted-role-only"
PUBLIC_ROLE_CAPS = {"ACTOR": 2, "TARGET": 2, "PLACE": 1}
PUBLIC_ROLE_ENDPOINT_STATUSES = frozenset({
    "RESOLVED", "RESOLVED_TYPE_CONFLICT", "SPAN_ONLY"})
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
    "EVENT": frozenset({"canonical_text", "canonical_status", "canonical_rule_version", "canonical_provenance", "primary_score", "primary_score_status", "primary_score_producer", "local_id"}),
    "STATEMENT": frozenset({"canonical_text", "canonical_status", "canonical_rule_version", "canonical_provenance", "statement_type", "primary_score", "primary_score_status", "primary_score_producer", "local_id"}),
    "ENTITY": frozenset({"canonical_name", "entity_type", "local_id", "merged_mentions"}),
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
    "ABOUT": frozenset(), "CAUSES": frozenset(),
}
EDGE_KEYS = frozenset({"edge_id", "edge_type", "source_id", "target_id", "confidence",
                       "properties", "evidence"})
ROOT_KEYS = frozenset({"schema_version", "projection_version", "article", "status", "persistence_ready", "nodes", "edges", "diagnostics"})
EVIDENCE_KEYS = frozenset({"article_id", "start", "end", "text", "evidence_ids"})
PROVENANCE_KEYS = frozenset({"article_version_id", "used_grounding_ids", "source_groundings",
                             "edits", "audit", "fact_invariants"})
GROUNDING_KEYS = frozenset({"evidence_id", "start", "end", "text"})
EDIT_KEYS = frozenset({"rule_id", "change_type", "source_start", "source_end", "source_text",
                       "display_start", "display_end", "replacement"})
CANONICAL_TEXT_MODES = frozenset({"GROUNDED_R2", "SOURCE_ONLY"})


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
    # Carrier 밖의 edge 판단 score. primary_scores처럼 semantic carrier와 분리한다.
    edge_scores: PublicEdgeScores


def compact_event_closure_for_public(
        closure: EventClosure, selected_event_ids: frozenset[str]) -> EventClosure:
    """Drop unselected Event source facts after their last model consumer.

    This projection-only carrier retains each Event ID and source anchor so
    relation endpoint validation and omission counts remain unchanged. Selected
    Events retain all member facts for canonical text and role evidence.
    """
    if selected_event_ids - {row.local_id for row in closure.events}:
        raise ValueError("PUBLIC compaction includes unknown Event ID")
    return replace(closure, events=tuple(
        row if row.local_id in selected_event_ids else replace(
            row, triggers=(), roles=(), times=(), member_groundings=())
        for row in closure.events))


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


def _canonical_provenance(article: RawArticle, result: CanonicalTextResult) -> dict[str, Any]:
    return {
        "article_version_id": article.article_version_id,
        "used_grounding_ids": list(result.used_grounding_ids),
        "source_groundings": [
            {"evidence_id": row.evidence_id, "start": row.start, "end": row.end, "text": row.text}
            for row in result.source_groundings
        ],
        "edits": [
            {"rule_id": row.rule_id, "change_type": row.change_type,
             "source_start": row.source_start, "source_end": row.source_end,
             "source_text": row.source_text, "display_start": row.display_start,
             "display_end": row.display_end, "replacement": row.replacement}
            for row in result.edits
        ],
        "audit": list(result.audit),
        "fact_invariants": list(result.fact_invariants),
    }


def _canonical_evidence(article: RawArticle, result: CanonicalTextResult,
                        base: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [base]
    rows.extend(_evidence(article, row.start, row.end, row.text, (row.evidence_id,))
                for row in result.source_groundings)
    unique: dict[tuple[int, int, str, tuple[str, ...]], dict[str, Any]] = {}
    for row in rows:
        key = (row["start"], row["end"], row["text"], tuple(row["evidence_ids"]))
        unique.setdefault(key, row)
    return list(unique.values())


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


def _public_role_rank(role: LocalRoleFact, representative_member_id: str) -> tuple[Any, ...]:
    """Use existing Participant source scores to choose one displayed endpoint."""
    scores = [score for _, score, _ in role.source_provenance if score is not None]
    if any(not math.isfinite(score) for score in scores):
        raise ValueError("Event role source score is nonfinite")
    return (0 if scores else 1, -max(scores) if scores else 0.0,
            0 if representative_member_id in role.member_ids else 1,
            role.start, role.end, role.entity_id, role.evidence_ids)


def _role_edge_score(role: LocalRoleFact) -> EdgeScore:
    """Endpoint를 고른 winning fact의 최고 source score가 곧 role edge 판단이다."""
    scores = [score for _, score, _ in role.source_provenance if score is not None]
    if not scores:
        raise ValueError(f"{role.role} confidence provenance missing")
    return EdgeScore(max(scores), "PARTICIPANT_ROLE_SOURCE")


def _public_role_eligible(role: LocalRoleFact, entities: EntityClosure) -> bool:
    if role.entity_id is None or role.endpoint_status not in PUBLIC_ROLE_ENDPOINT_STATUSES:
        return False
    return (role.endpoint_status != "SPAN_ONLY" or
            any(entities.evidence_to_entity.get(evidence_id) == role.entity_id
                for evidence_id in role.evidence_ids))


def _selected_public_roles(event: LocalEventState,
                           entities: EntityClosure) -> tuple[LocalRoleFact, ...]:
    """Select confidence-ranked final Entity endpoints without changing closure facts."""
    by_endpoint: dict[tuple[str, str], LocalRoleFact] = {}
    for role in event.roles:
        if not _public_role_eligible(role, entities):
            continue
        endpoint = (role.role, role.entity_id)
        current = by_endpoint.get(endpoint)
        if current is None or _public_role_rank(role, event.representative_member_id) < \
                _public_role_rank(current, event.representative_member_id):
            by_endpoint[endpoint] = role
    selected = []
    for role_name in ROLES:
        ranked = sorted(
            (fact for (kind, _), fact in by_endpoint.items() if kind == role_name),
            key=lambda fact: (-_role_edge_score(fact).confidence,
                              _public_role_rank(fact, event.representative_member_id)),
        )
        selected.extend(ranked[:PUBLIC_ROLE_CAPS[role_name]])
    return tuple(selected)


def _validate_construction(source: V3ConstructionResult) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[tuple[str, str], PrimaryScore]]:
    if (not source.producer_version or source.events.source_mode != "PREDICTED" or
            source.entities.source_mode != "PREDICTED" or
            source.events.article_version_id != source.article.article_version_id or
            source.events.content_sha256 != source.article.content_sha256):
        raise ValueError("construction article version/hash mismatch")
    if not isinstance(source.edge_scores, PublicEdgeScores):
        raise ValueError("construction lacks PUBLIC edge score provenance")
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
        if len(row.merged_mentions) > 3 or len({(mention.start, mention.end)
                                                 for mention in row.merged_mentions}) != len(row.merged_mentions):
            raise ValueError("Entity merged mentions exceed display bound or duplicate coordinates")
        for mention in row.merged_mentions:
            if (mention.start, mention.end) == (row.start, row.end):
                raise ValueError("representative Entity mention repeated as merged mention")
            _evidence(source.article, mention.start, mention.end, mention.text, ())
    for row in source.times:
        _evidence(source.article, row.start, row.end, row.text, row.evidence_ids)
        if row.normalized_value is not None:
            parsed = parse_canonical_time(row.normalized_value)
            if parsed.granularity != row.granularity:
                raise ValueError("Time granularity differs from normalized value")
        if row.calendar_eligible != calendar_eligible(row.normalized_value):
            raise ValueError("Time calendar eligibility mismatch")
        semantics = classify_time_projection_semantics(row.text)
        if (row.projection_safe, row.projection_reason) != (semantics.eligible, semantics.reason):
            raise ValueError("Time projection semantics differ from raw evidence")
        attached = bool(row.attached_event_ids)
        if row.attachment_status != ("ATTACHED" if attached else "UNATTACHED"):
            raise ValueError("Time attachment status differs from learned attachment evidence")
        decision = time_public_projection_decision(row, attached_to_event=attached)
        if row.public_calendar_candidate != decision.eligible:
            raise ValueError("Time PUBLIC candidate flag differs from r06 projection contract")
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


def compact_public_construction(
        source: V3ConstructionResult,
        selected_event_ids: frozenset[str]) -> V3ConstructionResult:
    """Validate complete scalar results, then release unselected Event facts.

    Serving calls this only after Relation and Primary have consumed the full
    closure. Direct projection still validates and accepts the complete carrier.
    """
    _validate_construction(source)
    return replace(source, events=compact_event_closure_for_public(
        source.events, selected_event_ids))


def project_public(source: V3ConstructionResult, *, selected_event_ids: frozenset[str] | None = None,
                   selected_statement_ids: frozenset[str] | None = None,
                   score_threshold: float | None = None,
                   diagnostic_unfiltered: bool = False,
                   canonical_text_mode: str = "GROUNDED_R2") -> dict[str, Any]:
    """선택 집합 또는 외부 threshold로 PUBLIC을 만든다. 기본은 score 있는 전 proposition."""
    events, entities, statements, times, scores = _validate_construction(source)
    if score_threshold is not None and (selected_event_ids is not None or selected_statement_ids is not None):
        raise ValueError("explicit selection and threshold are mutually exclusive")
    if score_threshold is not None and not math.isfinite(score_threshold):
        raise ValueError("score threshold must be finite")
    if canonical_text_mode not in CANONICAL_TEXT_MODES:
        raise ValueError("unknown canonical text mode")
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
    edge_scores = source.edge_scores
    def edge(kind: str, left: str, right: str, score: EdgeScore,
             properties: dict[str, Any] | None = None,
             evidence: list[dict[str, Any]] | None = None) -> None:
        # Confidence는 validation을 통과해 실제로 출력되는 edge에만 붙는 metadata다.
        edges.append({"edge_id": f"{kind}:{left}:{right}:{len(edges)}", "edge_type": kind,
                      "source_id": left, "target_id": right,
                      "confidence": score.confidence,
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
               "noncalendar_time_attachment": 0, "unsafe_time_attachment": 0,
               "filtered_relation": 0}
    time_projection_reasons: dict[str, int] = {}
    source_view = CanonicalSourceView.build(article) if selected_events or selected_statements else None
    for key in sorted(selected_events, key=lambda value: (events[value].start, events[value].end, value)):
        row = events[key]
        canonical = (canonicalize_event(article, row, view=source_view)
                     if canonical_text_mode == "GROUNDED_R2" else source_only_event(article, row))
        score = scores.get(("EVENT_CLUSTER", key))
        node("EVENT", key, {"local_id": key, "canonical_text": canonical.text,
             "canonical_status": canonical.status, "canonical_rule_version": canonical.rule_version,
             "canonical_provenance": _canonical_provenance(article, canonical),
             "primary_score": score.primary_score if score else None,
             "primary_score_status": score.status if score else "UNAVAILABLE",
             "primary_score_producer": source.producer_version if score else None},
             _canonical_evidence(article, canonical,
                                 _evidence(article, row.start, row.end, row.text,
                                           (row.representative_member_id,))))
        edge("COVERS", article_node_id, key, edge_scores.covers(row.member_ids),
             {"isPrimary": key == primary if primary else None})
        omitted["unresolved_role"] += sum(
            not _public_role_eligible(role, source.entities)
            for role in row.roles)
        for role in _selected_public_roles(row, source.entities):
            # Closure retains every role fact; duplicate sources for the selected
            # endpoint contribute their exact evidence before PUBLIC emission.
            same_endpoint = (fact for fact in row.roles
                             if fact.role == role.role and fact.entity_id == role.entity_id
                             and _public_role_eligible(fact, source.entities))
            evidence_by_span: dict[tuple[int, int, str], set[str]] = {}
            for fact in same_endpoint:
                evidence_by_span.setdefault((fact.start, fact.end, fact.text), set()).update(
                    fact.evidence_ids)
            evidence = [_evidence(article, start, end, text, tuple(sorted(ids)))
                        for (start, end, text), ids in sorted(evidence_by_span.items())]
            semantic_entities.add(role.entity_id)
            edge(role.role, key, role.entity_id, _role_edge_score(role),
                 {"endpoint_status": role.endpoint_status,
                 "evidence_ids": sorted({evidence_id for ids in evidence_by_span.values()
                                         for evidence_id in ids})}, evidence)
        for attached in row.times:
            time = times[attached.time_id]
            projection = time_public_projection_decision(time, attached_to_event=True)
            if not projection.eligible:
                if projection.reason == "UNSUPPORTED_CALENDAR_VALUE":
                    omitted["noncalendar_time_attachment"] += 1
                else:
                    omitted["unsafe_time_attachment"] += 1
                time_projection_reasons[projection.reason] = (
                    time_projection_reasons.get(projection.reason, 0) + 1)
                continue
            semantic_times.add(time.local_id)
            edge("OCCURRED_ON", key, time.local_id,
                 edge_scores.occurred_on(attached.member_ids, attached.time_id),
                 {"member_ids": list(attached.member_ids)},
                 [_evidence(article, time.start, time.end, time.text, time.evidence_ids)])
    for key in sorted(selected_statements, key=lambda value: (statements[value].grounding.start, value)):
        row = statements[key]
        canonical = (canonicalize_statement(article, row, view=source_view)
                     if canonical_text_mode == "GROUNDED_R2" else source_only_statement(article, row))
        score = scores.get(("STATEMENT", key))
        node("STATEMENT", key, {"local_id": key, "canonical_text": canonical.text,
             "canonical_status": canonical.status, "canonical_rule_version": canonical.rule_version,
             "canonical_provenance": _canonical_provenance(article, canonical),
             "statement_type": row.statement_type,
             "primary_score": score.primary_score if score else None,
             "primary_score_status": score.status if score else "UNAVAILABLE",
             "primary_score_producer": source.producer_version if score else None},
             _canonical_evidence(article, canonical,
                                 _evidence(article, row.grounding.start, row.grounding.end,
                                           row.grounding.text, (row.grounding.evidence_id,))))
        edge("CONTAINS_STATEMENT", article_node_id, key, edge_scores.contains_statement(key))
    for row in source.asserted_by:
        if row.statement_id not in selected_statements:
            continue
        if row.entity_id is None:
            omitted["unresolved_assertor"] += 1
            continue
        semantic_entities.add(row.entity_id)
        edge("ASSERTED_BY", row.statement_id, row.entity_id,
             edge_scores.asserted_by(row.evidence_id),
             {"endpoint_status": row.status, "evidence_id": row.evidence_id},
             [_evidence(article, row.start, row.end, row.text, (row.evidence_id,))])
    for key in sorted(semantic_entities, key=lambda value: (entities[value].start, value)):
        row = entities[key]
        if row.entity_type not in ENTITY_TYPES:
            raise ValueError(f"selected semantic Entity type requires backend resolution: {key}")
        node("ENTITY", key, {"local_id": key, "canonical_name": canonical_entity_name(row),
             "entity_type": row.entity_type,
             "merged_mentions": [{"text": mention.text, "start": mention.start,
                                  "end": mention.end} for mention in row.merged_mentions]},
             [_evidence(article, row.start, row.end, row.text, row.evidence_ids)])
        edge("MENTIONS", article_node_id, key, edge_scores.mentions(row.candidate_ids))
    for key in sorted(semantic_times, key=lambda value: (times[value].start, value)):
        row = times[key]
        node("TIME", key, {"local_id": key, "normalized_value": row.normalized_value,
             "granularity": row.granularity},
             [_evidence(article, row.start, row.end, row.text, row.evidence_ids)])
    for row in source.relations:
        if row.relation == "ABOUT" and row.source_id in selected_statements and row.target_id in selected_events or (
                row.relation == "CAUSES" and row.source_id in selected_events and row.target_id in selected_events):
            edge(row.relation, row.source_id, row.target_id,
                 EdgeScore(row.logit, row.relation + "_PAIR"))
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
                                                           for key in selected_keys),
                              "time_projection_policy_version": TIME_PROJECTION_POLICY_VERSION,
                              "time_projection_rejection_reasons": time_projection_reasons}}
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
                             "unavailable_score_count", "untrained_score_count",
                             "time_projection_policy_version", "time_projection_rejection_reasons"} or
            set(diagnostics["omitted"]) != {"unresolved_role", "unresolved_assertor",
                                            "noncalendar_time_attachment", "unsafe_time_attachment",
                                            "filtered_relation"} or
            diagnostics["time_projection_policy_version"] != TIME_PROJECTION_POLICY_VERSION or
            not isinstance(diagnostics["time_projection_rejection_reasons"], Mapping) or
            any(not isinstance(key, str) or not key or not isinstance(value, int) or value < 0
                for key, value in diagnostics["time_projection_rejection_reasons"].items())):
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
        if row["kind"] == "ENTITY":
            if row["properties"]["entity_type"] not in ENTITY_TYPES:
                raise ValueError("PUBLIC Entity type outside internal taxonomy")
            mentions = row["properties"]["merged_mentions"]
            if not isinstance(mentions, list) or len(mentions) > 3:
                raise ValueError("PUBLIC merged mentions exceed display bound")
            seen_spans: set[tuple[int, int]] = set()
            for mention in mentions:
                if not isinstance(mention, Mapping) or set(mention) != {"text", "start", "end"}:
                    raise ValueError("PUBLIC merged mention fields invalid")
                start, end, text = mention["start"], mention["end"], mention["text"]
                if (type(start) is not int or type(end) is not int or
                        not isinstance(text, str) or not text or not 0 <= start < end or
                        (start, end) in seen_spans or
                        source is not None and (end > len(source.content) or
                                                source.content[start:end] != text)):
                    raise ValueError("PUBLIC merged mention is not a unique exact source span")
                seen_spans.add((start, end))
            if (len(row["evidence"]) != 1 or
                    not isinstance(row["evidence"][0], Mapping) or
                    (row["evidence"][0].get("start"), row["evidence"][0].get("end")) in seen_spans):
                raise ValueError("PUBLIC merged mention repeats representative")
        if row["kind"] == "TIME":
            if (not calendar_eligible(row["properties"]["normalized_value"]) or
                    parse_canonical_time(row["properties"]["normalized_value"]).granularity !=
                    row["properties"]["granularity"]):
                raise ValueError("PUBLIC Time must be actual point calendar value")
            if (len(row["evidence"]) != 1 or
                    not isinstance(row["evidence"][0], Mapping) or
                    not classify_time_projection_semantics(
                        row["evidence"][0].get("text", "")).eligible):
                raise ValueError("PUBLIC Time raw evidence is not projection-safe")
        if row["kind"] in ("EVENT", "STATEMENT"):
            score = row["properties"]["primary_score"]
            if score is not None and (not isinstance(score, (float, int)) or not math.isfinite(score)):
                raise ValueError("nonfinite PUBLIC Primary score")
            _validate_canonical_provenance(row["properties"]["canonical_provenance"],
                                           payload["article"]["article_version_id"],
                                           row["properties"]["canonical_text"], source)
        for evidence in row["evidence"]:
            _validate_evidence(evidence, payload["article"]["article_id"], source)
    covers: list[bool | None] = []
    covered_ids: set[str] = set()
    contained_ids: set[str] = set()
    seen_edge_ids: set[str] = set()
    seen_event_roles: dict[tuple[str, str], set[str]] = {}
    semantic_entity_ids: set[str] = set()
    attached_time_ids: set[str] = set()
    time_evidence = {row["node_id"]: row["evidence"] for row in payload["nodes"]
                     if row["kind"] == "TIME"}
    for row in payload["edges"]:
        if set(row) != EDGE_KEYS:
            raise ValueError("unknown PUBLIC edge field")
        kind = row["edge_type"]
        if row["edge_id"] in seen_edge_ids:
            raise ValueError("duplicate PUBLIC edge ID")
        seen_edge_ids.add(row["edge_id"])
        if kind not in EDGE_ENDPOINTS or set(row["properties"]) != EDGE_PROPERTIES[kind]:
            raise ValueError("unknown PUBLIC edge/property")
        confidence = row["confidence"]
        if (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or
                not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0):
            raise ValueError("PUBLIC edge confidence must be a finite [0,1] number")
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
        if kind in ROLES:
            slot = (row["source_id"], kind)
            endpoints = seen_event_roles.setdefault(slot, set())
            if row["target_id"] in endpoints:
                raise ValueError("PUBLIC Event has duplicate Entity endpoint for one role")
            endpoints.add(row["target_id"])
            if len(endpoints) > PUBLIC_ROLE_CAPS[kind]:
                raise ValueError("PUBLIC Event role cardinality cap exceeded")
        if kind == "OCCURRED_ON":
            attached_time_ids.add(row["target_id"])
            if (not isinstance(row["properties"]["member_ids"], list) or
                    not row["properties"]["member_ids"] or
                    row["evidence"] != time_evidence.get(row["target_id"])):
                raise ValueError("PUBLIC Event-Time edge lacks matching occurrence evidence")
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


def _validate_canonical_provenance(provenance: Mapping[str, Any], article_version_id: str,
                                   canonical_text: str, source: RawArticle | None) -> None:
    """Validate source exactness and edit coordinates against the final display string.

    Literal edits point at their replacement in the final string. CLAUSE_SELECTION
    instead marks the descendant display region of a wider source clause, so later
    overlapping replacements may make that region differ from its historical value.
    """
    if (set(provenance) != PROVENANCE_KEYS or
            provenance["article_version_id"] != article_version_id or
            not isinstance(canonical_text, str) or
            not all(isinstance(value, str) for value in provenance["used_grounding_ids"] +
                    provenance["audit"] + provenance["fact_invariants"])):
        raise ValueError("canonical provenance schema/version mismatch")
    grounding_ids = []
    for row in provenance["source_groundings"]:
        if set(row) != GROUNDING_KEYS or not row["evidence_id"]:
            raise ValueError("canonical source grounding schema mismatch")
        grounding_ids.append(row["evidence_id"])
        if source is not None:
            _evidence(source, row["start"], row["end"], row["text"], (row["evidence_id"],))
    if grounding_ids != provenance["used_grounding_ids"]:
        raise ValueError("canonical grounding ID order differs from provenance")
    for row in provenance["edits"]:
        if (set(row) != EDIT_KEYS or not row["rule_id"] or not row["change_type"] or
                not isinstance(row["display_start"], int) or not isinstance(row["display_end"], int) or
                row["display_start"] < 0 or row["display_start"] > row["display_end"] or
                row["display_end"] > len(canonical_text) or
                not isinstance(row["replacement"], str)):
            raise ValueError("canonical edit schema invalid")
        if row["change_type"] == "CLAUSE_SELECTION":
            if row["display_start"] == row["display_end"] or not row["replacement"]:
                raise ValueError("canonical clause selection display range invalid")
        elif row["change_type"] in {
                "ENDING_REPLACEMENT", "GROUNDED_ROLE_REPLACEMENT",
                "GROUNDED_ROLE_INSERTION", "GROUNDED_FRAME_COMPOSITION"}:
            if canonical_text[row["display_start"]:row["display_end"]] != row["replacement"]:
                raise ValueError("canonical edit replacement differs from final display")
        else:
            raise ValueError("canonical edit change type invalid")
        if source is not None and (not 0 <= row["source_start"] <= row["source_end"] <= len(source.content)
                                   or source.content[row["source_start"]:row["source_end"]] != row["source_text"]):
            raise ValueError("canonical edit source differs from exact article")


def serialize_public(payload: Mapping[str, Any], *, source: RawArticle | None = None,
                     pretty: bool = False) -> str:
    validate_public(payload, source)
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2 if pretty else None,
                      sort_keys=pretty)
