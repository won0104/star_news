"""Dependency-free preparation of canonical graph data for Neo4j import.

This module does not open a database connection.  It turns the already validated
canonical graph contract into scalar Neo4j properties and deterministic Cypher.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .contracts import ArticleLocalKnowledgeGraphResult, GRAPH_SCHEMA_VERSION
from .compact_assembly import CompactKnowledgeGraphResult, PUBLIC_SCHEMA_VERSION


PROJECTION_SCHEMA_VERSION = "articlelocal-kg-neo4j-projection-v1"
V22_PROJECTION_SCHEMA_VERSION = "articlelocal-kg-neo4j-projection-v22-v1"
_NODE_LABELS = {
    "ARTICLE": "Article",
    "EVENT": "Event",
    "STATEMENT": "Statement",
}
_EDGE_TYPES = {"COVERS", "CONTAINS_STATEMENT"}
_V22_NODE_LABELS = {
    **_NODE_LABELS, "ENTITY": "Entity", "TIME": "Time",
}
_V22_EDGE_TYPES = {
    *_EDGE_TYPES, "MENTIONS", "ACTOR", "TARGET", "PLACE", "OCCURRED_ON",
}


def _scalar_properties(value: Mapping[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key, item in value.items():
        if item is None or isinstance(item, (bool, int, float, str)):
            properties[str(key)] = item
        elif isinstance(item, list) and all(
            row is None or isinstance(row, (bool, int, float, str)) for row in item
        ):
            properties[str(key)] = item
        else:
            properties[str(key) + "_json"] = json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
    return properties


def project_graph_for_neo4j(
    graph: ArticleLocalKnowledgeGraphResult | CompactKnowledgeGraphResult | Mapping[str, Any],
) -> dict[str, Any]:
    """검증된 PUBLIC graph만 offline projection하며 identity를 재계산하지 않는다."""

    payload = (
        graph.to_dict() if isinstance(
            graph, (ArticleLocalKnowledgeGraphResult, CompactKnowledgeGraphResult)
        ) else dict(graph)
    )
    if payload.get("schema_version") not in (GRAPH_SCHEMA_VERSION,
                                              PUBLIC_SCHEMA_VERSION):
        raise ValueError("unsupported Neo4j source graph schema")
    is_v22 = payload.get("schema_version") == PUBLIC_SCHEMA_VERSION
    node_labels = _V22_NODE_LABELS if is_v22 else _NODE_LABELS
    edge_types = _V22_EDGE_TYPES if is_v22 else _EDGE_TYPES
    node_ids = {str(row["node_id"]) for row in payload["nodes"]}
    nodes = []
    for row in payload["nodes"]:
        kind = str(row["kind"])
        if kind not in node_labels:
            raise ValueError(f"unsupported Neo4j node kind: {kind}")
        nodes.append(
            {
                "id": str(row["node_id"]),
                "labels": ["ArticleLocalKGNode", node_labels[kind]],
                "properties": {
                    "id": str(row["node_id"]),
                    "kind": kind,
                    "runtime_config_id": payload["runtime_config_id"],
                    "assembly_config_id": payload["assembly_config_id"],
                    **_scalar_properties(row.get("properties", {})),
                    "evidence_json": json.dumps(
                        row.get("evidence", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "provenance_json": json.dumps(
                        row.get("provenance", {}),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            }
        )
    relationships = []
    for row in payload["edges"]:
        edge_type = str(row["edge_type"])
        if edge_type not in edge_types:
            raise ValueError(f"unsupported Neo4j relationship type: {edge_type}")
        source = str(row["source_id"])
        target = str(row["target_id"])
        if source not in node_ids or target not in node_ids:
            raise ValueError("Neo4j projection contains a dangling endpoint")
        relationships.append(
            {
                "id": str(row["edge_id"]),
                "type": edge_type,
                "source_id": source,
                "target_id": target,
                "properties": {
                    "id": str(row["edge_id"]),
                    "confidence": (
                        None if is_v22 and row["confidence"] is None
                        else float(row["confidence"])
                    ),
                    **({"status": str(row["status"])} if is_v22 else {}),
                    "evidence_json": json.dumps(
                        row.get("evidence", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "provenance_json": json.dumps(
                        row.get("provenance", {}),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            }
        )
    coverage = payload.get("coverage", {}) if is_v22 else {}
    return {
        "schema_version": (
            V22_PROJECTION_SCHEMA_VERSION if is_v22 else PROJECTION_SCHEMA_VERSION
        ),
        "source_graph_schema_version": payload["schema_version"],
        "article_id": payload["article"]["article_id"],
        "nodes": nodes,
        "relationships": relationships,
        "unmaterialized_evidence": (
            {"unresolved_fact_count": coverage.get("unresolved_fact_count", 0)}
            if is_v22 else payload["unmaterialized_evidence"]
        ),
        "lane_statuses": (
            coverage.get("lane_statuses", {}) if is_v22 else payload["lane_statuses"]
        ),
    }


def _cypher_literal(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_cypher_literal(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def _cypher_map(properties: Mapping[str, Any]) -> str:
    return "{" + ", ".join(
        f"`{key}`: {_cypher_literal(value)}" for key, value in sorted(properties.items())
    ) + "}"


def projections_to_cypher(projections: Iterable[Mapping[str, Any]]) -> str:
    """Build idempotent Cypher that can be reviewed before database execution."""

    lines = [
        "// Generated from canonical Article-local KG projections; no credentials included.",
        "CREATE CONSTRAINT articlelocal_kg_node_id IF NOT EXISTS FOR (n:ArticleLocalKGNode) REQUIRE n.id IS UNIQUE;",
        "",
    ]
    for projection in projections:
        for node in projection["nodes"]:
            labels = ":".join(node["labels"])
            lines.append(f"MERGE (n:{labels} {{id: {_cypher_literal(node['id'])}}})")
            lines.append(f"SET n += {_cypher_map(node['properties'])};")
        for edge in projection["relationships"]:
            edge_type = str(edge["type"])
            allowed = (
                _V22_EDGE_TYPES if projection.get("source_graph_schema_version") ==
                PUBLIC_SCHEMA_VERSION else _EDGE_TYPES
            )
            if edge_type not in allowed:
                raise ValueError(f"unsupported Cypher relationship type: {edge_type}")
            lines.append(
                "MATCH (s:ArticleLocalKGNode {id: "
                + _cypher_literal(edge["source_id"])
                + "}), (t:ArticleLocalKGNode {id: "
                + _cypher_literal(edge["target_id"])
                + "})"
            )
            lines.append(
                f"MERGE (s)-[r:{edge_type} {{id: {_cypher_literal(edge['id'])}}}]->(t)"
            )
            lines.append(f"SET r += {_cypher_map(edge['properties'])};")
        lines.append("")
    return "\n".join(lines)
