"""Merge per-article analyze results into Neo4j-ready node/edge files."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

TOPIC_NAME_TO_CODE: dict[str, str] = {
    "정치": "POLITICS",
    "경제": "ECONOMY",
    "사회": "SOCIETY",
    "문화": "CULTURE",
    "국제": "INTERNATIONAL",
    "스포츠": "SPORTS",
    "IT·과학": "IT_SCIENCE",
}

TOPIC_SEED: list[dict[str, Any]] = [
    {"topicCode": "POLITICS", "nameKo": "정치", "displayOrder": 1},
    {"topicCode": "ECONOMY", "nameKo": "경제", "displayOrder": 2},
    {"topicCode": "SOCIETY", "nameKo": "사회", "displayOrder": 3},
    {"topicCode": "CULTURE", "nameKo": "문화", "displayOrder": 4},
    {"topicCode": "INTERNATIONAL", "nameKo": "국제", "displayOrder": 5},
    {"topicCode": "SPORTS", "nameKo": "스포츠", "displayOrder": 6},
    {"topicCode": "IT_SCIENCE", "nameKo": "IT·과학", "displayOrder": 7},
]


def _topic_node_id(code: str) -> str:
    return f"topic-{code}"


def _time_node_id(time_key: str) -> str:
    return f"time-{time_key}"


def _org_node_id(name: str) -> str:
    safe = re.sub(r"[^\w\-]+", "_", name.strip())[:48] or "unknown"
    return f"norg-{safe}"


def _parse_published_at(raw: str | None) -> str | None:
    """Normalize to ISO-8601 with Asia/Seoul offset when possible."""
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return f"{text}T00:00:00+09:00"
    if re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$", text):
        return text.replace(" ", "T") + "+09:00"
    if "+" in text or text.endswith("Z"):
        return text
    return text


class Neo4jBundleBuilder:
    """Accumulate analyze JSON into deduped nodes/edges for empty-DB import."""

    def __init__(self, *, with_publisher: bool = True) -> None:
        self.with_publisher = with_publisher
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self._edge_keys: set[str] = set()
        self.stats: dict[str, int] = {
            "articles": 0,
            "events": 0,
            "entities": 0,
            "statements": 0,
            "times": 0,
            "edges": 0,
            "skipped_results": 0,
        }
        self._seed_topics()
        self._org_mysql_id = 1

    def _seed_topics(self) -> None:
        for row in TOPIC_SEED:
            nid = _topic_node_id(row["topicCode"])
            self.nodes[nid] = {
                "labels": ["Topic"],
                "properties": {
                    "nodeId": nid,
                    "topicCode": row["topicCode"],
                    "nameKo": row["nameKo"],
                    "displayOrder": row["displayOrder"],
                    "isActive": True,
                },
            }

    def _add_node(self, labels: list[str], props: dict[str, Any]) -> str:
        nid = str(props["nodeId"])
        if nid in self.nodes:
            # Prefer richer properties on collide (e.g. Time shared).
            existing = self.nodes[nid]["properties"]
            for k, v in props.items():
                if v is not None and (existing.get(k) in (None, "", []) or k == "embedding"):
                    existing[k] = v
            return nid
        self.nodes[nid] = {"labels": list(labels), "properties": dict(props)}
        return nid

    def _add_edge(
        self,
        etype: str,
        start: str,
        end: str,
        properties: dict[str, Any] | None = None,
        *,
        edge_id: str | None = None,
    ) -> None:
        key = f"{etype}|{start}|{end}"
        if key in self._edge_keys:
            return
        if start not in self.nodes or end not in self.nodes:
            return
        self._edge_keys.add(key)
        self.edges.append(
            {
                "edgeId": edge_id or f"edge-{uuid.uuid4().hex[:16]}",
                "type": etype,
                "startNodeId": start,
                "endNodeId": end,
                "properties": dict(properties or {}),
            }
        )
        self.stats["edges"] += 1

    def add_result(self, result: dict[str, Any]) -> None:
        if not result or result.get("status") not in {"OK", "PARTIAL"}:
            self.stats["skipped_results"] += 1
            return

        time_remap: dict[str, str] = {}
        article_node_id: str | None = None
        event_ids: list[str] = []

        for node in result.get("nodes") or []:
            labels = list(node.get("labels") or [])
            props = dict(node.get("properties") or {})
            if not props.get("nodeId"):
                continue

            if "Article" in labels:
                if props.get("publishedAt"):
                    props["publishedAt"] = _parse_published_at(str(props["publishedAt"]))
                article_node_id = self._add_node(["Article"], props)
                self.stats["articles"] += 1
                continue

            if "Event" in labels:
                eid = self._add_node(["Event"], props)
                event_ids.append(eid)
                self.stats["events"] += 1
                continue

            if "Statement" in labels:
                self._add_node(["Statement"], props)
                self.stats["statements"] += 1
                continue

            if "Entity" in labels:
                self._add_node(labels, props)
                self.stats["entities"] += 1
                continue

            if "Time" in labels:
                old_id = str(props["nodeId"])
                time_key = props.get("timeKey") or props.get("value")
                if not time_key:
                    continue
                time_key = str(time_key)
                new_id = _time_node_id(time_key)
                time_remap[old_id] = new_id
                tprops = {
                    "nodeId": new_id,
                    "timeKey": time_key,
                    "value": props.get("value") or time_key,
                    "granularity": props.get("granularity"),
                }
                # Keep Year/Month/Day secondary labels when present.
                self._add_node(labels if labels != ["Time"] else ["Time"], tprops)
                if new_id not in self.nodes or "Time" in self.nodes[new_id]["labels"]:
                    pass
                self.stats["times"] += 1
                continue

        # Publisher (offline seed; Spring may also own this later)
        if self.with_publisher and article_node_id:
            source = (result.get("article") or {}).get("source")
            if source:
                oid = _org_node_id(str(source))
                if oid not in self.nodes:
                    self._add_node(
                        ["Entity", "NewsOrganization"],
                        {
                            "nodeId": oid,
                            "canonicalName": str(source),
                            "entityType": "NEWS_ORGANIZATION",
                            "mysqlOrganizationId": self._org_mysql_id,
                        },
                    )
                    self._org_mysql_id += 1
                self._add_edge("PUBLISHED_BY", article_node_id, oid)

        # Topic CLASSIFIED_AS
        topic_name = (result.get("classification") or {}).get("topic")
        if article_node_id and topic_name:
            code = TOPIC_NAME_TO_CODE.get(str(topic_name))
            if code:
                tid = _topic_node_id(code)
                self._add_edge(
                    "CLASSIFIED_AS",
                    article_node_id,
                    tid,
                    {"isPrimary": True, "source": "KPF-bert-cls2", "topic": topic_name},
                )

        # Edges with Time remap + COVERS isPrimary
        covers: list[dict[str, Any]] = []
        for edge in result.get("edges") or []:
            etype = edge.get("type")
            if etype == "CLASSIFIED_AS":
                continue  # handled above with real Topic ids
            start = str(edge.get("startNodeId") or "")
            end = str(edge.get("endNodeId") or "")
            end = time_remap.get(end, end)
            start = time_remap.get(start, start)
            props = dict(edge.get("properties") or {})
            if etype == "COVERS":
                covers.append(
                    {
                        "start": start,
                        "end": end,
                        "properties": props,
                        "edgeId": edge.get("edgeId"),
                    }
                )
                continue
            self._add_edge(str(etype), start, end, props, edge_id=edge.get("edgeId"))

        if covers and article_node_id:
            # Exactly one isPrimary=true per article.
            covers.sort(key=lambda c: c["end"])
            for i, c in enumerate(covers):
                props = dict(c["properties"])
                props["isPrimary"] = i == 0
                self._add_edge(
                    "COVERS",
                    c["start"],
                    c["end"],
                    props,
                    edge_id=c.get("edgeId"),
                )

    def write(self, out_dir: Path | str) -> dict[str, Any]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        nodes_path = out / "nodes.jsonl"
        edges_path = out / "edges.jsonl"
        with nodes_path.open("w", encoding="utf-8") as f:
            for node in self.nodes.values():
                f.write(json.dumps(node, ensure_ascii=False) + "\n")
        with edges_path.open("w", encoding="utf-8") as f:
            for edge in self.edges:
                f.write(json.dumps(edge, ensure_ascii=False) + "\n")

        summary = {
            **self.stats,
            "unique_nodes": len(self.nodes),
            "unique_edges": len(self.edges),
            "files": {
                "nodes": str(nodes_path),
                "edges": str(edges_path),
            },
        }
        (out / "bundle_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_load_readme(out)
        return summary


def _write_load_readme(out: Path) -> None:
    text = """# Neo4j offline bundle

배치 후 **반드시** 후처리:

```powershell
python -m starlight_ai.cli_postprocess --bundle <this_dir>
```

서버(빈 DB) 적재 전에:

1. `V1__initial_graph_schema.cypher` 적용
2. `V2__event_vector_index.cypher` 적용 (**1024-d**, KURE-v1)

서버 업로드: `nodes.jsonl`, `edges.jsonl`, `manifest.json`, `postprocess_report.json`

FastAPI/적재 담당이 UNWIND MERGE 하거나 `neo4j-admin` 변환하면 된다.
"""
    (out / "README_LOAD.md").write_text(text, encoding="utf-8")
