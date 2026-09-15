"""Offline postprocess for Neo4j JSONL bundles (cold-start / server load).

Steps:
  1. Drop noise Entity nodes (quotes, pronouns)
  2. Merge Entity by normalized canonicalName
  3. Merge Event by embedding cosine similarity (+ hard conflict guards)
  4. Dedupe edges, normalize COVERS isPrimary
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from starlight_ai.entity_filter import is_noise_entity_name, normalize_entity_name

ENTITY_INBOUND = ("MENTIONS", "ACTOR", "TARGET", "PLACE", "PUBLISHED_BY")
EVENT_OUTBOUND = ("ACTOR", "TARGET", "PLACE", "OCCURRED_ON", "CLASSIFIED_AS")
EVENT_INBOUND = ("COVERS",)


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: str) -> str:
        self.add(x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def remap(self, node_id: str) -> str:
        return self.find(node_id)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _is_entity(node: dict[str, Any]) -> bool:
    return "Entity" in node.get("labels", [])


def _is_event(node: dict[str, Any]) -> bool:
    return "Event" in node.get("labels", [])


def _node_id(node: dict[str, Any]) -> str:
    return str(node["properties"]["nodeId"])


def _degree(edges: list[dict[str, Any]], nid: str) -> int:
    return sum(
        1
        for e in edges
        if e.get("startNodeId") == nid or e.get("endNodeId") == nid
    )


def drop_noise_entities(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    drop: set[str] = set()
    for n in nodes:
        if not _is_entity(n):
            continue
        name = n["properties"].get("canonicalName")
        if is_noise_entity_name(name):
            drop.add(_node_id(n))
    if not drop:
        return nodes, edges, 0
    nodes = [n for n in nodes if _node_id(n) not in drop]
    edges = [
        e
        for e in edges
        if e.get("startNodeId") not in drop and e.get("endNodeId") not in drop
    ]
    return nodes, edges, len(drop)


def merge_entities_by_name(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        if not _is_entity(n):
            continue
        raw = n["properties"].get("canonicalName") or ""
        key = normalize_entity_name(raw).lower()
        if key:
            by_key[key].append(n)

    id_map: dict[str, str] = {}
    merged_groups = 0
    merged_away = 0

    for _key, group in by_key.items():
        if len(group) < 2:
            continue
        merged_groups += 1

        def keep_score(n: dict[str, Any]) -> tuple:
            labels = set(n.get("labels") or [])
            typed = 1 if labels & {"Person", "Location", "NewsOrganization"} else 0
            nid = _node_id(n)
            name = n["properties"].get("canonicalName") or ""
            return (typed, _degree(edges, nid), len(name), nid)

        keep = max(group, key=keep_score)
        keep_id = _node_id(keep)
        keep_labels = set(keep.get("labels") or [])
        for n in group:
            nid = _node_id(n)
            if nid == keep_id:
                continue
            id_map[nid] = keep_id
            merged_away += 1
            keep_labels.update(n.get("labels") or [])
            if not keep["properties"].get("entityType") and n["properties"].get(
                "entityType"
            ):
                keep["properties"]["entityType"] = n["properties"]["entityType"]
        keep["labels"] = sorted(set(keep.get("labels", [])) | keep_labels)

    nodes = [n for n in nodes if _node_id(n) not in id_map]
    edges = _rewire_edges(edges, id_map)
    stats = {
        "entity_groups_merged": merged_groups,
        "entities_merged_away": merged_away,
    }
    return nodes, edges, id_map, stats


def _event_meta(
    event_id: str, edges: list[dict[str, Any]], nodes_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    times: set[str] = set()
    actors: set[str] = set()
    places: set[str] = set()
    covers = 0
    for e in edges:
        if e.get("startNodeId") == event_id:
            et = e.get("type")
            tgt = e.get("endNodeId")
            if et == "OCCURRED_ON" and tgt:
                tn = nodes_by_id.get(tgt)
                if tn:
                    tk = tn["properties"].get("timeKey") or tn["properties"].get("value")
                    if tk:
                        times.add(str(tk))
            elif et == "ACTOR" and tgt:
                en = nodes_by_id.get(tgt)
                if en and _is_entity(en):
                    nm = en["properties"].get("canonicalName")
                    if nm:
                        actors.add(str(nm))
            elif et == "PLACE" and tgt:
                en = nodes_by_id.get(tgt)
                if en and _is_entity(en):
                    nm = en["properties"].get("canonicalName")
                    if nm:
                        places.add(str(nm))
        if e.get("type") == "COVERS" and e.get("endNodeId") == event_id:
            covers += 1
    return {"times": times, "actors": actors, "places": places, "covers": covers}


def _hard_conflict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ta, tb = a.get("times") or set(), b.get("times") or set()
    if ta and tb and ta.isdisjoint(tb):

        def parts(keys: set[str]) -> set[str]:
            out = set(keys)
            for k in keys:
                bits = k.split("-")
                if len(bits) >= 1:
                    out.add(bits[0])
                if len(bits) >= 2:
                    out.add("-".join(bits[:2]))
            return out

        if parts(ta).isdisjoint(parts(tb)):
            return True
    aa, ab = a.get("actors") or set(), b.get("actors") or set()
    if len(aa) >= 2 and len(ab) >= 2 and aa.isdisjoint(ab):
        return True
    pa, pb = a.get("places") or set(), b.get("places") or set()
    if pa and pb and pa.isdisjoint(pb):
        return True
    return False


def merge_events_by_embedding(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    threshold: float = 0.92,
    top_k: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    events = [n for n in nodes if _is_event(n)]
    nodes_by_id = {_node_id(n): n for n in nodes}
    with_emb = [
        n
        for n in events
        if n["properties"].get("embedding") is not None
    ]
    if len(with_emb) < 2:
        return nodes, edges, {}, {"events_merged_away": 0, "event_clusters": 0}

    ids = [_node_id(n) for n in with_emb]
    mat = np.asarray(
        [n["properties"]["embedding"] for n in with_emb], dtype=np.float32
    )
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms

    meta = {eid: _event_meta(eid, edges, nodes_by_id) for eid in ids}
    uf = UnionFind()
    conflict_skips = 0
    pair_count = 0

    # Top-k neighbors per row (excluding self)
    sims = mat @ mat.T
    for i, eid in enumerate(ids):
        scores = sims[i].copy()
        scores[i] = -1.0
        if top_k < len(scores):
            idx = np.argpartition(-scores, top_k)[:top_k]
        else:
            idx = np.arange(len(scores))
        for j in idx:
            if scores[j] < threshold:
                continue
            other = ids[j]
            if _hard_conflict(meta[eid], meta[other]):
                conflict_skips += 1
                continue
            uf.union(eid, other)
            pair_count += 1

    clusters: dict[str, list[str]] = defaultdict(list)
    for eid in ids:
        clusters[uf.find(eid)].append(eid)
    multi = {k: v for k, v in clusters.items() if len(v) > 1}

    id_map: dict[str, str] = {}
    merged_away = 0
    for members in multi.values():

        def keep_score(nid: str) -> tuple:
            m = meta[nid]
            title = nodes_by_id[nid]["properties"].get("title") or ""
            return (m["covers"], len(title), nid)

        keep = max(members, key=keep_score)
        for nid in members:
            if nid != keep:
                id_map[nid] = keep
                merged_away += 1

    nodes = [n for n in nodes if _node_id(n) not in id_map]
    edges = _rewire_edges(edges, id_map)
    stats = {
        "events_with_embedding": len(with_emb),
        "event_clusters": len(multi),
        "events_merged_away": merged_away,
        "event_pair_links": pair_count,
        "event_conflict_skips": conflict_skips,
        "threshold": threshold,
    }
    return nodes, edges, id_map, stats


def _rewire_edges(
    edges: list[dict[str, Any]], id_map: dict[str, str]
) -> list[dict[str, Any]]:
    if not id_map:
        return edges

    def remap(nid: str | None) -> str | None:
        if nid is None:
            return None
        while nid in id_map:
            nid = id_map[nid]
        return nid

    out: list[dict[str, Any]] = []
    for e in edges:
        s = remap(e.get("startNodeId"))
        t = remap(e.get("endNodeId"))
        if not s or not t or s == t:
            continue
        out.append({**e, "startNodeId": s, "endNodeId": t})
    return out


def dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in edges:
        key = (e.get("type", ""), e.get("startNodeId", ""), e.get("endNodeId", ""))
        if key not in seen:
            seen[key] = e
            continue
        prev = seen[key]
        props = dict(prev.get("properties") or {})
        newp = dict(e.get("properties") or {})
        if "confidence" in props or "confidence" in newp:
            c1 = props.get("confidence")
            c2 = newp.get("confidence")
            if c1 is None:
                props["confidence"] = c2
            elif c2 is not None:
                props["confidence"] = max(float(c1), float(c2))
        if newp.get("isPrimary"):
            props["isPrimary"] = True
        prev["properties"] = props
    return list(seen.values())


def normalize_covers_primary(edges: list[dict[str, Any]]) -> int:
    by_article: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edges:
        if e.get("type") == "COVERS":
            by_article[e.get("startNodeId", "")].append(e)
    fixed = 0
    for rels in by_article.values():
        primaries = [r for r in rels if (r.get("properties") or {}).get("isPrimary")]
        if len(primaries) == 1:
            continue
        fixed += 1
        chosen = primaries[0] if primaries else rels[0]
        for r in rels:
            props = dict(r.get("properties") or {})
            props["isPrimary"] = r is chosen
            r["properties"] = props
    return fixed


def count_labels(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for n in nodes:
        for lb in n.get("labels") or []:
            counts[lb] += 1
    return dict(counts)


def postprocess_bundle(
    bundle_dir: Path,
    *,
    event_threshold: float = 0.92,
    event_top_k: int = 8,
    in_nodes: str = "nodes.jsonl",
    in_edges: str = "edges.jsonl",
    out_nodes: str = "nodes.jsonl",
    out_edges: str = "edges.jsonl",
    backup: bool = True,
) -> dict[str, Any]:
    bundle_dir = bundle_dir.expanduser().resolve()
    nodes_path = bundle_dir / in_nodes
    edges_path = bundle_dir / in_edges
    if not nodes_path.exists() or not edges_path.exists():
        raise FileNotFoundError(f"missing {in_nodes}/{in_edges} in {bundle_dir}")

    nodes = load_jsonl(nodes_path)
    edges = load_jsonl(edges_path)
    before = {
        "nodes": len(nodes),
        "edges": len(edges),
        "labels": count_labels(nodes),
    }

    if backup and out_nodes == "nodes.jsonl":
        raw_nodes = bundle_dir / "nodes.raw.jsonl"
        raw_edges = bundle_dir / "edges.raw.jsonl"
        if not raw_nodes.exists():
            write_jsonl(raw_nodes, nodes)
            write_jsonl(raw_edges, edges)

    nodes, edges, noise_dropped = drop_noise_entities(nodes, edges)
    nodes, edges, _ent_map, ent_stats = merge_entities_by_name(nodes, edges)
    nodes, edges, _evt_map, evt_stats = merge_events_by_embedding(
        nodes, edges, threshold=event_threshold, top_k=event_top_k
    )
    edges = dedupe_edges(edges)
    primary_fixed = normalize_covers_primary(edges)

    # Drop edges pointing to missing nodes
    live = {_node_id(n) for n in nodes}
    edges = [
        e
        for e in edges
        if e.get("startNodeId") in live and e.get("endNodeId") in live
    ]

    out_nodes_path = bundle_dir / out_nodes
    out_edges_path = bundle_dir / out_edges
    write_jsonl(out_nodes_path, nodes)
    write_jsonl(out_edges_path, edges)

    after = {
        "nodes": len(nodes),
        "edges": len(edges),
        "labels": count_labels(nodes),
    }
    report = {
        "bundle_dir": str(bundle_dir),
        "before": before,
        "after": after,
        "noise_entities_dropped": noise_dropped,
        "entity_merge": ent_stats,
        "event_merge": evt_stats,
        "covers_primary_fixed": primary_fixed,
        "files": {
            "nodes": str(out_nodes_path),
            "edges": str(out_edges_path),
        },
    }
    report_path = bundle_dir / "postprocess_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report["report_path"] = str(report_path)
    return report
