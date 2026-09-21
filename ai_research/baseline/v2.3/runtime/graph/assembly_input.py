"""Runtime/legacy graph input adapter and immutable resolved assembly carrier."""

from __future__ import annotations

from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any, Mapping

from runtime.eventframe.contracts import ArticleLocalRuntimeResult

from .assembly import ArticleLocalKGAssembler
from .contracts import ArticleLocalKnowledgeGraphResult, GRAPH_SCHEMA_VERSION


def deep_freeze(value: Any) -> Any:
    """Recursively detach and freeze a JSON-compatible value."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(deep_freeze(item) for item in value)
    return value


def deep_thaw(value: Any) -> Any:
    """Return a detached JSON-compatible copy of a frozen carrier value."""

    if isinstance(value, Mapping):
        return {str(key): deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [deep_thaw(item) for item in value]
    return value


def _json_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


@dataclass(frozen=True, slots=True)
class ResolvedAssemblyState:
    """Immutable assembly-only view of already resolved runtime identities."""

    source_kind: str
    source_graph: Mapping[str, Any]
    article: Mapping[str, Any]
    resolved_events: tuple[Mapping[str, Any], ...]
    resolved_entities: tuple[Mapping[str, Any], ...]
    statements: tuple[Mapping[str, Any], ...]
    time_expressions: tuple[Mapping[str, Any], ...]
    semantic_edges: tuple[Mapping[str, Any], ...]
    unmaterialized_evidence: Mapping[str, Any]
    source_lanes: Mapping[str, Any]
    coverage: Mapping[str, Any]
    runtime_provenance: Mapping[str, Any]

    @classmethod
    def from_legacy_graph(
        cls,
        graph: Mapping[str, Any],
        *,
        source_kind: str,
    ) -> "ResolvedAssemblyState":
        detached = _json_copy(graph)
        if detached.get("schema_version") != GRAPH_SCHEMA_VERSION:
            raise ValueError("resolved assembly state requires the canonical legacy graph")
        nodes = detached.get("nodes", [])
        edges = detached.get("edges", [])
        member_event_ids = {
            str(edge["source_id"])
            for edge in edges
            if edge.get("edge_type") == "MEMBER_OF_EVENT"
        }
        resolved_events = [node for node in nodes if node.get("kind") == "LOCAL_EVENT"]
        resolved_events.extend(
            node
            for node in nodes
            if node.get("kind") == "EVENT" and str(node["node_id"]) not in member_event_ids
        )
        frozen_graph = deep_freeze(detached)
        return cls(
            source_kind=source_kind,
            source_graph=frozen_graph,
            article=deep_freeze(detached["article"]),
            resolved_events=tuple(deep_freeze(row) for row in resolved_events),
            resolved_entities=tuple(
                deep_freeze(node) for node in nodes if node.get("kind") == "LOCAL_ENTITY"
            ),
            statements=tuple(
                deep_freeze(node) for node in nodes if node.get("kind") == "STATEMENT"
            ),
            time_expressions=tuple(
                deep_freeze(node) for node in nodes if node.get("kind") == "TIME"
            ),
            semantic_edges=tuple(
                deep_freeze(edge)
                for edge in edges
                if edge.get("edge_type") != "MEMBER_OF_EVENT"
            ),
            unmaterialized_evidence=deep_freeze(
                detached.get("unmaterialized_evidence", {})
            ),
            source_lanes=deep_freeze(detached.get("source_lanes", {})),
            coverage=deep_freeze(detached.get("lane_statuses", {})),
            runtime_provenance=deep_freeze(detached.get("provenance", {})),
        )

    def identity_ids_by_scope(self) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType(
            {
                "EVENT": tuple(str(row["node_id"]) for row in self.resolved_events),
                "ENTITY": tuple(str(row["node_id"]) for row in self.resolved_entities),
                "STATEMENT": tuple(str(row["node_id"]) for row in self.statements),
                "TIME": tuple(str(row["node_id"]) for row in self.time_expressions),
            }
        )

    def identity_ids(self) -> tuple[str, ...]:
        return tuple(
            identity
            for scope in ("EVENT", "ENTITY", "STATEMENT", "TIME")
            for identity in self.identity_ids_by_scope()[scope]
        )

    def to_legacy_graph(self) -> dict[str, Any]:
        return deep_thaw(self.source_graph)


class AssemblyInputAdapter:
    """Adapt only canonical runtime/legacy contracts without model or Gold imports."""

    policy_id = "ASSEMBLY_INPUT_ADAPTER_V1"

    def __init__(self, legacy_assembler: ArticleLocalKGAssembler) -> None:
        self._legacy_assembler = legacy_assembler

    def adapt(
        self,
        source: (
            ArticleLocalRuntimeResult
            | ArticleLocalKnowledgeGraphResult
            | Mapping[str, Any]
        ),
    ) -> ResolvedAssemblyState:
        if isinstance(source, ArticleLocalRuntimeResult):
            graph = self._legacy_assembler.assemble(source).to_dict()
            source_kind = "ARTICLE_LOCAL_RUNTIME_RESULT"
        elif isinstance(source, ArticleLocalKnowledgeGraphResult):
            graph = source.to_dict()
            source_kind = "LEGACY_ASSEMBLY_RESULT"
        elif isinstance(source, Mapping):
            snapshot = _json_copy(source)
            if snapshot.get("schema_version") == GRAPH_SCHEMA_VERSION:
                graph = snapshot
                source_kind = "LEGACY_ASSEMBLY_MAPPING"
            else:
                graph = self._legacy_assembler.assemble(snapshot).to_dict()
                source_kind = "RUNTIME_RESULT_MAPPING"
            if snapshot != _json_copy(source):
                raise ValueError("assembly input adapter mutated its source mapping")
        else:
            raise TypeError("unsupported assembly input contract")
        return ResolvedAssemblyState.from_legacy_graph(graph, source_kind=source_kind)
