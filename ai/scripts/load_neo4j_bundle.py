"""Load offline neo4j_bundle_* JSONL into a local Neo4j (demo / smoke)."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

# Primary label used for MERGE identity (nodeId).
PRIMARY = {
    "Topic": "Topic",
    "Article": "Article",
    "Event": "Event",
    "Statement": "Statement",
    "Time": "Time",
    "Entity": "Entity",
    "NewsOrganization": "NewsOrganization",
    "Story": "Story",
    "User": "User",
}

SCHEMA_STATEMENTS = [
    # Unique constraints (V1 subset + safe IF NOT EXISTS)
    "CREATE CONSTRAINT article_node_id_unique IF NOT EXISTS FOR (n:Article) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT article_mysql_id_unique IF NOT EXISTS FOR (n:Article) REQUIRE n.mysqlArticleId IS UNIQUE",
    "CREATE CONSTRAINT event_node_id_unique IF NOT EXISTS FOR (n:Event) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT story_node_id_unique IF NOT EXISTS FOR (n:Story) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT topic_node_id_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT topic_code_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.topicCode IS UNIQUE",
    "CREATE CONSTRAINT entity_node_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT news_organization_mysql_id_unique IF NOT EXISTS FOR (n:NewsOrganization) REQUIRE n.mysqlOrganizationId IS UNIQUE",
    "CREATE CONSTRAINT time_node_id_unique IF NOT EXISTS FOR (n:Time) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT time_key_unique IF NOT EXISTS FOR (n:Time) REQUIRE n.timeKey IS UNIQUE",
    "CREATE CONSTRAINT statement_node_id_unique IF NOT EXISTS FOR (n:Statement) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (n:User) REQUIRE n.userId IS UNIQUE",
    "CREATE RANGE INDEX article_published_at IF NOT EXISTS FOR (n:Article) ON (n.publishedAt)",
    "CREATE RANGE INDEX event_occurred_at IF NOT EXISTS FOR (n:Event) ON (n.occurredAt)",
    "CREATE FULLTEXT INDEX article_title_fulltext IF NOT EXISTS FOR (n:Article) ON EACH [n.title]",
    "CREATE FULLTEXT INDEX event_fulltext IF NOT EXISTS FOR (n:Event) ON EACH [n.title, n.aliases]",
    "CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS FOR (n:Entity) ON EACH [n.canonicalName, n.aliases]",
    "CREATE FULLTEXT INDEX statement_text_fulltext IF NOT EXISTS FOR (n:Statement) ON EACH [n.text]",
    """
    CREATE VECTOR INDEX event_embedding_index IF NOT EXISTS
    FOR (e:Event) ON (e.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 1024,
      `vector.similarity_function`: 'cosine'
    }}
    """,
]

EDGE_TYPES = [
    "PUBLISHED_BY",
    "CLASSIFIED_AS",
    "COVERS",
    "CONTAINS_STATEMENT",
    "MENTIONS",
    "ACTOR",
    "TARGET",
    "PLACE",
    "OCCURRED_ON",
]


def _chunks(items: list[Any], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _primary_label(labels: list[str]) -> str:
    for cand in ("Article", "Event", "Statement", "Topic", "Time", "NewsOrganization", "Entity", "Story", "User"):
        if cand in labels:
            return cand
    return labels[0]


def wait_ready(driver, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with driver.session() as s:
                s.run("RETURN 1").consume()
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2)
    raise RuntimeError(f"Neo4j not ready: {last}")


def apply_schema(session) -> None:
    for stmt in SCHEMA_STATEMENTS:
        session.run(stmt).consume()


def clear_graph(session) -> None:
    # Batch delete to avoid huge tx
    while True:
        result = session.run(
            "MATCH (n) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS c"
        )
        c = result.single()["c"]
        if not c:
            break


def load_nodes(session, nodes_path: Path, batch_size: int) -> int:
    by_key: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    total = 0
    with nodes_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            labels = tuple(obj["labels"])
            props = dict(obj["properties"])
            by_key[labels].append(props)
            total += 1

    for labels, rows in by_key.items():
        primary = _primary_label(list(labels))
        extras = [lb for lb in labels if lb != primary]
        # SET extra labels via Cypher fragment
        extra_set = "".join(f" SET n:`{lb}`" for lb in extras)
        cypher = (
            f"UNWIND $rows AS row "
            f"MERGE (n:`{primary}` {{nodeId: row.nodeId}}) "
            f"SET n += row{extra_set}"
        )
        for chunk in _chunks(rows, batch_size):
            session.run(cypher, rows=chunk).consume()
        print(f"  nodes {list(labels)}: {len(rows)}")
    return total


def load_edges(session, edges_path: Path, batch_size: int) -> int:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total = 0
    with edges_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            by_type[obj["type"]].append(
                {
                    "edgeId": obj.get("edgeId"),
                    "start": obj["startNodeId"],
                    "end": obj["endNodeId"],
                    "props": obj.get("properties") or {},
                }
            )
            total += 1

    for etype, rows in by_type.items():
        if not re.fullmatch(r"[A-Z_]+", etype):
            raise ValueError(f"unsafe edge type: {etype}")
        cypher = (
            f"UNWIND $rows AS row "
            f"MATCH (a {{nodeId: row.start}}) "
            f"MATCH (b {{nodeId: row.end}}) "
            f"MERGE (a)-[r:`{etype}`]->(b) "
            f"SET r += row.props "
            f"SET r.edgeId = coalesce(r.edgeId, row.edgeId)"
        )
        for chunk in _chunks(rows, batch_size):
            session.run(cypher, rows=chunk).consume()
        print(f"  edges {etype}: {len(rows)}")
    return total


def summarize(session) -> dict[str, Any]:
    counts = {}
    for label in ("Article", "Event", "Entity", "Statement", "Time", "Topic", "NewsOrganization"):
        counts[label] = session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
    counts["relationships"] = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    sample_articles = session.run(
        """
        MATCH (a:Article)-[:COVERS]->(e:Event)
        OPTIONAL MATCH (a)-[:CLASSIFIED_AS]->(t:Topic)
        RETURN a.title AS title, t.nameKo AS topic, count(e) AS events
        ORDER BY events DESC
        LIMIT 5
        """
    ).data()

    sample_path = session.run(
        """
        MATCH (a:Article)-[:COVERS]->(e:Event)
        OPTIONAL MATCH (e)-[:ACTOR]->(p:Entity)
        OPTIONAL MATCH (e)-[:OCCURRED_ON]->(tm:Time)
        RETURN a.title AS article, e.title AS event,
               collect(DISTINCT p.canonicalName)[0..5] AS actors,
               tm.timeKey AS when
        LIMIT 3
        """
    ).data()

    emb_count = session.run(
        "MATCH (e:Event) WHERE e.embedding IS NOT NULL RETURN count(e) AS c"
    ).single()["c"]
    emb_dim = session.run(
        "MATCH (e:Event) WHERE e.embedding IS NOT NULL RETURN size(e.embedding) AS d LIMIT 1"
    ).single()
    return {
        "counts": counts,
        "top_articles_by_events": sample_articles,
        "sample_paths": sample_path,
        "embedding": {
            "events_with_emb": emb_count,
            "dim": emb_dim["d"] if emb_dim else None,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--uri", default="bolt://127.0.0.1:17687")
    p.add_argument("--user", default="neo4j")
    p.add_argument("--password", default="ssafy206")
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--clear", action="store_true", help="DETACH DELETE all nodes first")
    args = p.parse_args()

    nodes = args.bundle / "nodes.jsonl"
    edges = args.bundle / "edges.jsonl"
    if not nodes.exists() or not edges.exists():
        raise SystemExit(f"missing nodes/edges under {args.bundle}")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    wait_ready(driver)
    t0 = time.time()
    with driver.session() as session:
        print("schema…")
        apply_schema(session)
        if args.clear:
            print("clear…")
            clear_graph(session)
        print("nodes…")
        n = load_nodes(session, nodes, args.batch_size)
        print("edges…")
        e = load_edges(session, edges, args.batch_size)
        summary = summarize(session)
    driver.close()
    summary["loaded_nodes"] = n
    summary["loaded_edges"] = e
    summary["wall_seconds"] = round(time.time() - t0, 1)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
