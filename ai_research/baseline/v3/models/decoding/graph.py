"""mention prediction을 final article-local graph contract로 조립하는 deterministic 책임.

EventMention/EvidenceSpan은 final node가 아니며 evidence는 source offset property로 남긴다.
Neo4j 저장은 이 모듈의 책임이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Iterable, Mapping, Sequence

from ..contracts import LEGACY_RELATION_ONTOLOGY
from ..policies.constraints import (
    validate_cardinality,
    validate_hard_relation_endpoint,
    validate_subevent_semantics,
)
from .coreference import UnionFindClusterer


@dataclass(frozen=True, slots=True)
class EvidenceProperty:
    article_id: str
    start: int
    end: int
    text: str
    sentence_index: int

    def validate(self, content: str) -> None:
        if not 0 <= self.start < self.end <= len(content):
            raise ValueError("evidence offset is outside source text")
        if content[self.start : self.end] != self.text:
            raise ValueError("evidence text does not round-trip to immutable source")


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    kind: str
    properties: Mapping[str, object]
    evidence: tuple[EvidenceProperty, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_type: str
    source_id: str
    target_id: str
    confidence: float
    evidence: tuple[EvidenceProperty, ...] = ()
    properties: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArticleGraph:
    article_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


class RelativeTimeNormalizer:
    """상대 표현만 publishedAt을 anchor로 정규화한다; 무조건 Event 날짜 fallback은 없다."""

    _DAY_OFFSETS = {"그제": -2, "어제": -1, "오늘": 0, "내일": 1, "모레": 2}
    _YEAR_OFFSETS = {"작년": -1, "지난해": -1, "올해": 0, "내년": 1}

    def normalize(self, text: str, published_at: str | None) -> str | None:
        if published_at is None:
            return None
        anchor = _parse_datetime(published_at)
        for word, offset in self._DAY_OFFSETS.items():
            if word in text:
                return (anchor + timedelta(days=offset)).date().isoformat()
        for word, offset in self._YEAR_OFFSETS.items():
            if word in text:
                return f"{anchor.year + offset:04d}"
        match = re.fullmatch(r"(\d{4})년", text.strip())
        return match.group(1) if match else None


class DeterministicGraphAssembler:
    """clustering, edge 승격, OCCURRED_ON, dedupe/self-edge/schema validation을 수행한다."""

    def __init__(self, relation_ontology_mode: str = LEGACY_RELATION_ONTOLOGY) -> None:
        self.clusterer = UnionFindClusterer()
        self.time_normalizer = RelativeTimeNormalizer()
        self.relation_ontology_mode = relation_ontology_mode

    def assemble(
        self,
        *,
        article_id: str,
        content: str,
        published_at: str | None,
        entity_mentions: Sequence[GraphNode],
        event_mentions: Sequence[GraphNode],
        statements: Sequence[GraphNode],
        time_expressions: Sequence[GraphNode],
        story_nodes: Sequence[GraphNode] = (),
        entity_merge_edges: Iterable[tuple[str, str, float]] = (),
        event_merge_edges: Iterable[tuple[str, str, float]] = (),
        mention_edges: Iterable[GraphEdge] = (),
        merge_threshold: float = 0.5,
    ) -> ArticleGraph:
        all_evidence = [
            evidence
            for node in (
                *entity_mentions,
                *event_mentions,
                *statements,
                *time_expressions,
                *story_nodes,
            )
            for evidence in node.evidence
        ]
        for evidence in all_evidence:
            if evidence.article_id != article_id:
                raise ValueError("cross-article evidence is forbidden")
            evidence.validate(content)
        entity_clusters = self.clusterer.cluster(
            (node.node_id for node in entity_mentions), entity_merge_edges, threshold=merge_threshold
        )
        event_clusters = self.clusterer.cluster(
            (node.node_id for node in event_mentions), event_merge_edges, threshold=merge_threshold
        )
        entity_map, entity_nodes = _materialize_clusters("ENTITY", entity_clusters, entity_mentions)
        event_map, event_nodes = _materialize_clusters("EVENT", event_clusters, event_mentions)
        time_nodes = tuple(
            GraphNode(
                node.node_id,
                "TIME",
                {
                    **dict(node.properties),
                    "normalized": node.properties.get("normalized")
                    or self.time_normalizer.normalize(
                        str(node.properties.get("text", node.evidence[0].text if node.evidence else "")),
                        published_at,
                    ),
                },
                node.evidence,
            )
            for node in time_expressions
        )
        final_nodes = tuple(
            (*entity_nodes, *event_nodes, *statements, *time_nodes, *story_nodes)
        )
        node_by_id = {node.node_id: node for node in final_nodes}
        node_ids = set(node_by_id)
        lifted = []
        for edge in mention_edges:
            source = entity_map.get(edge.source_id, event_map.get(edge.source_id, edge.source_id))
            target = entity_map.get(edge.target_id, event_map.get(edge.target_id, edge.target_id))
            if edge.edge_type in {"CAUSES", "RESPONDS_TO", "SUBEVENT_OF"} and source == target:
                continue
            if source not in node_ids or target not in node_ids:
                raise ValueError("edge references an unknown final node")
            validate_cardinality(edge.edge_type, source, target)
            validate_hard_relation_endpoint(
                edge.edge_type,
                node_by_id[source].kind,
                node_by_id[target].kind,
                ontology_mode=self.relation_ontology_mode,
            )
            if edge.edge_type == "SUBEVENT_OF":
                validate_subevent_semantics(
                    node_by_id[target].properties,
                    edge.properties,
                )
            lifted.append(
                GraphEdge(
                    edge.edge_type,
                    source,
                    target,
                    edge.confidence,
                    edge.evidence,
                    edge.properties,
                )
            )
            if edge.edge_type == "TIME":
                lifted.append(
                    GraphEdge(
                        "OCCURRED_ON",
                        source,
                        target,
                        edge.confidence,
                        edge.evidence,
                        edge.properties,
                    )
                )
        edges = _deduplicate_edges(lifted)
        graph = ArticleGraph(
            article_id,
            final_nodes,
            edges,
        )
        self.validate(graph)
        return graph

    def validate(self, graph: ArticleGraph) -> None:
        ids = [node.node_id for node in graph.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate final graph node ID")
        known = set(ids)
        node_by_id = {node.node_id: node for node in graph.nodes}
        for edge in graph.edges:
            if edge.source_id not in known or edge.target_id not in known:
                raise ValueError("graph edge endpoint is absent")
            validate_cardinality(edge.edge_type, edge.source_id, edge.target_id)
            validate_hard_relation_endpoint(
                edge.edge_type,
                node_by_id[edge.source_id].kind,
                node_by_id[edge.target_id].kind,
                ontology_mode=self.relation_ontology_mode,
            )
            if edge.edge_type == "SUBEVENT_OF":
                validate_subevent_semantics(
                    node_by_id[edge.target_id].properties,
                    edge.properties,
                )
        _validate_subevent_hierarchy(graph.edges, maximum_depth=2)


def _materialize_clusters(
    kind: str,
    clusters: Sequence[Sequence[str]],
    mentions: Sequence[GraphNode],
) -> tuple[dict[str, str], tuple[GraphNode, ...]]:
    by_id = {node.node_id: node for node in mentions}
    mapping: dict[str, str] = {}
    nodes = []
    for index, members in enumerate(clusters, start=1):
        cluster_id = f"{kind.lower()}-{index:04d}"
        evidence = tuple(item for member in members for item in by_id[member].evidence)
        properties: dict[str, object] = {"mention_ids": tuple(members)}
        if kind == "EVENT":
            member_nodes = [by_id[member] for member in members]
            properties.update(
                {
                    "grounded": all(
                        node.properties.get("grounded") is True
                        for node in member_nodes
                    ),
                    "bounded_episode": all(
                        node.properties.get("bounded_episode") is True
                        for node in member_nodes
                    ),
                    "synthetic": any(
                        node.properties.get("synthetic") is True
                        for node in member_nodes
                    ),
                }
            )
        for member in members:
            mapping[member] = cluster_id
        nodes.append(
            GraphNode(
                cluster_id,
                kind,
                properties,
                evidence,
            )
        )
    return mapping, tuple(nodes)


def _deduplicate_edges(edges: Iterable[GraphEdge]) -> tuple[GraphEdge, ...]:
    best: dict[tuple[str, str, str], GraphEdge] = {}
    for edge in edges:
        key = edge.edge_type, edge.source_id, edge.target_id
        if key not in best or edge.confidence > best[key].confidence:
            best[key] = edge
    return tuple(best[key] for key in sorted(best))


def _validate_subevent_hierarchy(
    edges: Iterable[GraphEdge], *, maximum_depth: int
) -> None:
    """child→parent forest에서 cycle과 초기 depth 상한을 검사한다."""

    parents: dict[str, set[str]] = {}
    for edge in edges:
        if edge.edge_type == "SUBEVENT_OF":
            parents.setdefault(edge.source_id, set()).add(edge.target_id)

    def depth(node: str, path: tuple[str, ...]) -> int:
        if node in path:
            raise ValueError("SUBEVENT_OF cycle is forbidden")
        next_nodes = parents.get(node, ())
        if not next_nodes:
            return 0
        return 1 + max(depth(parent, (*path, node)) for parent in next_nodes)

    for node in parents:
        if depth(node, ()) > maximum_depth:
            raise ValueError(
                f"SUBEVENT_OF hierarchy depth exceeds initial limit {maximum_depth}"
            )


def _parse_datetime(value: str) -> datetime:
    canonical = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(canonical)
    except ValueError as error:
        raise ValueError("publishedAt must be ISO-8601 for relative time normalization") from error
