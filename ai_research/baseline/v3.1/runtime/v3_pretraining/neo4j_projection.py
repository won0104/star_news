"""v3 PUBLIC에서 backend 저장 의도만 내보내는 순수 dry-run adapter.

UUID, DB identity, global matching과 DB write를 생성하지 않는다. 호출자가 별도 backend
매핑/불변식 판단을 끝내야 저장 가능하다.
"""

from __future__ import annotations

from typing import Any, Mapping

from runtime.v3_pretraining.public_graph import validate_public
from runtime.v3_pretraining.temporal import parse_canonical_time


def project_neo4j_dry_run(public: Mapping[str, Any]) -> dict[str, Any]:
    """local ID와 미확정 backend identity/type을 명시적으로 분리한다."""
    validate_public(public)
    nodes = []
    unmapped = []
    for row in public["nodes"]:
        kind = row["kind"]
        properties = dict(row["properties"])
        if kind == "EVENT":
            properties = {"title": properties["canonical_text"],
                          "canonicalProvenance": properties["canonical_provenance"]}
            unmapped.append({"local_id": row["node_id"], "field": "primary_score",
                             "reason": "BACKEND_PROPERTY_NOT_CONFIRMED"})
        elif kind == "STATEMENT":
            properties = {"text": properties["canonical_text"],
                          "statementType": properties["statement_type"],
                          "canonicalProvenance": properties["canonical_provenance"]}
            unmapped.append({"local_id": row["node_id"], "field": "primary_score",
                             "reason": "BACKEND_PROPERTY_NOT_CONFIRMED"})
        elif kind == "ENTITY":
            properties = {"canonicalName": properties["canonical_name"],
                          "internalEntityType": properties["entity_type"],
                          "entityType": None}
            unmapped.append({"local_id": row["node_id"], "field": "entityType",
                             "reason": "BACKEND_ENTITY_TYPE_MAPPING_UNCONFIRMED"})
            unmapped.append({"local_id": row["node_id"], "field": "merged_mentions",
                             "reason": "BACKEND_PROPERTY_NOT_CONFIRMED"})
        elif kind == "TIME":
            value = properties["normalized_value"]
            parsed = parse_canonical_time(value)
            parts = value.split("-")
            properties = {"timeKey": value, "value": value, "granularity": parsed.granularity,
                          "year": int(parts[0]),
                          "month": int(parts[1]) if len(parts) > 1 else None,
                          "day": int(parts[2]) if len(parts) > 2 else None}
        else:
            properties = {"articleId": properties["article_id"],
                          "articleVersionId": properties["article_version_id"],
                          "title": properties["title"]}
        nodes.append({"local_id": row["node_id"], "kind": kind,
                      "backend_uuid": None, "backend_identity_status": "UNMAPPED",
                      "public_primary_score": (row["properties"]["primary_score"]
                                               if kind in ("EVENT", "STATEMENT") else None),
                      "proposed_properties": properties, "evidence": row["evidence"]})
        unmapped.append({"local_id": row["node_id"], "field": "backend_uuid",
                         "reason": "BACKEND_IDENTITY_NOT_PROVIDED"})
    edges = [{"local_edge_id": row["edge_id"], "type": row["edge_type"],
              "source_local_id": row["source_id"], "target_local_id": row["target_id"],
              "source_backend_uuid": None, "target_backend_uuid": None,
              "proposed_properties": {**row["properties"], "confidence": row["confidence"]},
              "evidence": row["evidence"]}
             for row in public["edges"]]
    return {"mode": "PURE_DRY_RUN", "source_schema_version": public["schema_version"],
            "public_persistence_ready": public["persistence_ready"],
            "backend_persistence_ready": False,
            "db_write_count": 0, "nodes": nodes, "edges": edges, "unmapped": unmapped}
