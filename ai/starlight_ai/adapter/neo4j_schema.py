"""Project KG bundle output + embeddings into Neo4j-oriented JSON."""

from __future__ import annotations

import uuid
from typing import Any

from starlight_ai.entity_filter import is_noise_entity_name, normalize_entity_name

ENTITY_TYPE_LABEL: dict[str, str] = {
    "PERSON": "Person",
    "LOCATION": "Location",
    "COMPANY": "Company",
    "GOVERNMENT_AGENCY": "GovernmentAgency",
    "NEWS_ORGANIZATION": "NewsOrganization",
    # ORGANIZATION / PRODUCT: Entity only + entityType; loader may refine.
}

PUBLIC_EDGE_TYPES = {
    "COVERS",
    "CONTAINS_STATEMENT",
    "MENTIONS",
    "ACTOR",
    "TARGET",
    "PLACE",
    "OCCURRED_ON",
    # 백엔드 _SIMPLE_EDGE_QUERIES가 이미 MERGE를 지원하는 명제·발언 관계
    "ASSERTED_BY",
    "ABOUT",
    "CAUSES",
}

# V1 leftovers still seen in some local bundles — drop for service schema.
DROP_EDGE_TYPES = {"MEMBER_OF_EVENT", "SAME_EVENT"}
# EventMention layer — not a Neo4j Event (V2 public kind is EVENT only).
DROP_NODE_KINDS = {"LOCAL_EVENT"}


def _prop(node: dict[str, Any]) -> dict[str, Any]:
    return dict(node.get("properties") or {})


def _display_text(props: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = props.get(key)
        if val:
            return str(val)
    return ""


def _entity_labels(entity_type: str | None) -> list[str]:
    labels = ["Entity"]
    if not entity_type:
        return labels
    secondary = ENTITY_TYPE_LABEL.get(entity_type.upper())
    if secondary and secondary not in labels:
        labels.append(secondary)
    return labels


def _time_labels(granularity: str | None) -> list[str]:
    labels = ["Time"]
    mapping = {"YEAR": "Year", "MONTH": "Month", "DAY": "Day"}
    secondary = mapping.get((granularity or "").upper())
    if secondary:
        labels.append(secondary)
    return labels


def _time_key(value: str | None, granularity: str | None, existing: Any) -> str | None:
    if existing:
        return str(existing)
    if not value:
        return None
    text = str(value).strip()
    # Prefer ISO-like normalized values as timeKey (matches UNIQUE constraint usage).
    return text or None


def _article_node_id(article: dict[str, Any], kg_nodes: list[dict[str, Any]]) -> str:
    for node in kg_nodes:
        kind = str(node.get("kind") or "").upper()
        if kind == "ARTICLE":
            return str(node.get("node_id") or node.get("id"))
    return str(article.get("article_id") or f"art_{uuid.uuid4().hex[:16]}")


def adapt_to_schema(
    *,
    article: dict[str, Any],
    kg: dict[str, Any],
    classification: dict[str, Any] | None,
    event_embeddings: dict[str, list[float]],
    embedding_model: str,
    embedding_dim: int,
    include_classified_as_edge: bool = False,
) -> dict[str, Any]:
    """Build starlight-article-analyze-v1 payload."""
    raw_nodes = list(kg.get("nodes") or [])
    raw_edges = list(kg.get("edges") or [])
    warnings: list[str] = []

    article_node_id = _article_node_id(article, raw_nodes)
    nodes_out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Prefer KG ARTICLE; else synthesize from input.
    has_article = False
    for node in raw_nodes:
        kind = str(node.get("kind") or "").upper()
        nid = str(node.get("node_id") or node.get("id") or "")
        props = _prop(node)
        if not nid:
            continue

        if kind in DROP_NODE_KINDS:
            warnings.append(f"dropped_local_event:{nid}")
            continue

        if kind == "ARTICLE":
            has_article = True
            out_props: dict[str, Any] = {
                "nodeId": nid,
                "title": props.get("title") or article.get("title") or "",
                "publishedAt": props.get("published_at")
                or props.get("publishedAt")
                or article.get("published_at")
                or "",
            }
            mysql_id = article.get("mysql_article_id") or article.get("mysqlArticleId")
            if mysql_id is not None:
                out_props["mysqlArticleId"] = mysql_id
            nodes_out.append({"labels": ["Article"], "properties": out_props})
            seen_ids.add(nid)
            continue

        if kind == "EVENT":
            title = _display_text(props, "canonical_text", "text", "name", "title")
            out_props = {
                "nodeId": nid,
                "title": title,
            }
            if nid in event_embeddings:
                out_props["embedding"] = event_embeddings[nid]
                out_props["embeddingModel"] = embedding_model
                out_props["embeddingDim"] = embedding_dim
            nodes_out.append({"labels": ["Event"], "properties": out_props})
            seen_ids.add(nid)
            continue

        if kind == "STATEMENT":
            # 2.1 public-v2: text / statement_type
            # 2.3 compact public-v2.2: canonical_text / statement_type_value
            nodes_out.append(
                {
                    "labels": ["Statement"],
                    "properties": {
                        "nodeId": nid,
                        "text": _display_text(props, "text", "canonical_text", "name"),
                        "statementType": (
                            props.get("statement_type")
                            or props.get("statementType")
                            or props.get("statement_type_value")
                        ),
                    },
                }
            )
            seen_ids.add(nid)
            continue

        if kind in {"ENTITY", "LOCAL_ENTITY"}:
            et = props.get("entity_type") or props.get("entityType")
            et_str = str(et) if et else None
            cname = _display_text(props, "canonical_name", "name", "text")
            if is_noise_entity_name(cname):
                warnings.append(f"dropped_noise_entity:{nid}:{cname!r}")
                continue
            cname = normalize_entity_name(cname) or cname
            if et_str and et_str.upper() == "ORGANIZATION":
                warnings.append(f"entity_type_ORGANIZATION_unrefined:{nid}")
            nodes_out.append(
                {
                    "labels": _entity_labels(et_str),
                    "properties": {
                        "nodeId": nid,
                        "canonicalName": cname,
                        "entityType": et,
                    },
                }
            )
            seen_ids.add(nid)
            continue

        label = node.get("label")
        if label in {"Person", "Organization", "Location", "Entity"} and kind not in {
            "TIME",
            "ARTICLE",
            "EVENT",
            "STATEMENT",
        }:
            et = props.get("entity_type") or props.get("type") or (
                label.upper() if label != "Entity" else None
            )
            et_str = str(et) if et else None
            cname = _display_text(props, "canonical_name", "name", "text")
            if is_noise_entity_name(cname):
                warnings.append(f"dropped_noise_entity:{nid}:{cname!r}")
                continue
            cname = normalize_entity_name(cname) or cname
            if label == "Organization" and (not et_str or et_str.upper() == "ORGANIZATION"):
                et_str = "ORGANIZATION"
                warnings.append(f"entity_type_ORGANIZATION_unrefined:{nid}")
            nodes_out.append(
                {
                    "labels": _entity_labels(et_str),
                    "properties": {
                        "nodeId": nid,
                        "canonicalName": cname,
                        "entityType": et_str or et,
                    },
                }
            )
            seen_ids.add(nid)
            continue

        if kind == "TIME":
            gran = props.get("granularity")
            value = (
                props.get("normalized_value")
                or props.get("value")
                or _display_text(props, "text", "name")
            )
            time_key = _time_key(
                str(value) if value else None,
                str(gran) if gran else None,
                props.get("timeKey") or props.get("time_key"),
            )
            out_props = {
                "nodeId": nid,
                "value": value,
                "granularity": gran,
            }
            if time_key:
                out_props["timeKey"] = time_key
            nodes_out.append(
                {
                    "labels": _time_labels(str(gran) if gran else None),
                    "properties": out_props,
                }
            )
            seen_ids.add(nid)
            continue

        warnings.append(f"skipped_node_kind:{kind}:{nid}")

    if not has_article:
        out_props = {
            "nodeId": article_node_id,
            "title": article.get("title") or "",
            "publishedAt": article.get("published_at") or "",
        }
        mysql_id = article.get("mysql_article_id") or article.get("mysqlArticleId")
        if mysql_id is not None:
            out_props["mysqlArticleId"] = mysql_id
        nodes_out.insert(0, {"labels": ["Article"], "properties": out_props})
        seen_ids.add(article_node_id)

    edges_out: list[dict[str, Any]] = []
    for edge in raw_edges:
        etype = str(edge.get("edge_type") or edge.get("type") or "")
        if etype in DROP_EDGE_TYPES:
            continue
        if etype not in PUBLIC_EDGE_TYPES:
            warnings.append(f"skipped_edge_type:{etype}")
            continue
        src = str(edge.get("source_id") or edge.get("startNodeId") or "")
        tgt = str(edge.get("target_id") or edge.get("endNodeId") or "")
        if src not in seen_ids or tgt not in seen_ids:
            warnings.append(f"dangling_edge:{etype}:{src}->{tgt}")
            continue
        eprops = dict(edge.get("properties") or {})
        conf = edge.get("confidence", eprops.get("confidence"))
        out_eprops: dict[str, Any] = {}
        if conf is not None:
            out_eprops["confidence"] = conf
        # v3는 COVERS에 학습된 Primary 판정을 싣는다. null(판정 불가)은 넘기지 않아
        # 백엔드가 기존 방식으로 primary를 정하게 한다.
        if etype == "COVERS" and isinstance(eprops.get("isPrimary"), bool):
            out_eprops["isPrimary"] = eprops["isPrimary"]
        edges_out.append(
            {
                "edgeId": edge.get("edge_id") or edge.get("edgeId") or f"edge_{uuid.uuid4().hex[:12]}",
                "type": etype,
                "startNodeId": src,
                "endNodeId": tgt,
                "properties": out_eprops,
            }
        )

    classification_out = None
    if classification:
        classification_out = {
            "big_cls": classification.get("big_cls"),
            "small_cls": classification.get("small_cls"),
            "region_cls": classification.get("region_cls"),
            "topic": classification.get("topic"),
        }
        if include_classified_as_edge and classification.get("topic"):
            # Topic node is not created here; edge carries nameKo for loader.
            edges_out.append(
                {
                    "edgeId": f"edge_cls_{uuid.uuid4().hex[:12]}",
                    "type": "CLASSIFIED_AS",
                    "startNodeId": article_node_id,
                    "endNodeId": f"topic:{classification['topic']}",
                    "properties": {
                        "topic": classification["topic"],
                        "isPrimary": True,
                        "source": "KPF-bert-cls2",
                    },
                }
            )
            warnings.append(
                "CLASSIFIED_AS endNodeId is topic:<nameKo>; loader must resolve Topic node"
            )

    events_missing_emb = [
        n["properties"]["nodeId"]
        for n in nodes_out
        if "Event" in n["labels"] and "embedding" not in n["properties"]
    ]
    if events_missing_emb:
        warnings.append(f"events_without_embedding:{len(events_missing_emb)}")

    status = "OK"
    kg_status = kg.get("status")
    validation = (kg.get("validation") or {}).get("status")
    if kg.get("source_failures"):
        status = "PARTIAL"
        warnings.append("kg_source_failures")
    if validation and validation != "PASS":
        status = "PARTIAL"
        warnings.append(f"kg_validation:{validation}")

    return {
        "schema_version": "starlight-article-analyze-v1",
        "status": status,
        "article": {
            "article_id": article.get("article_id"),
            "title": article.get("title"),
            "published_at": article.get("published_at"),
            "mysql_article_id": article.get("mysql_article_id")
            or article.get("mysqlArticleId"),
            "source": article.get("source"),
        },
        "classification": classification_out,
        "nodes": nodes_out,
        "edges": edges_out,
        "warnings": warnings,
        "meta": {
            "kg_status": kg_status,
            "kg_schema_version": kg.get("schema_version"),
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
            "kg_validation": validation,
        },
    }
