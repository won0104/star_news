"""Evidence-preserving contracts for canonical article-local KG assembly.

The graph result deliberately keeps unresolved participant evidence outside the
canonical edge set.  A raw ACTOR/TARGET/PLACE span is useful evidence, but it is
not an Entity and must not be promoted into a fake graph node.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Mapping


GRAPH_SCHEMA_VERSION = "articlelocal-kg-runtime-graph-v1"


@dataclass(frozen=True, slots=True)
class GraphEvidence:
    article_id: str
    char_start: int
    char_end: int
    text: str
    sentence_index: int

    def validate(self, content: str) -> None:
        if not 0 <= self.char_start < self.char_end <= len(content):
            raise ValueError("graph evidence offset is outside source article")
        if content[self.char_start : self.char_end] != self.text:
            raise ValueError("graph evidence text does not round-trip to source article")


@dataclass(frozen=True, slots=True)
class CanonicalGraphNode:
    node_id: str
    kind: str
    properties: Mapping[str, Any]
    evidence: tuple[GraphEvidence, ...]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CanonicalGraphEdge:
    edge_id: str
    edge_type: str
    source_id: str
    target_id: str
    confidence: float
    evidence: tuple[GraphEvidence, ...]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ArticleLocalKnowledgeGraphResult:
    """Deterministic JSON boundary between ⑧ graph assembly and its consumers."""

    schema_version: str
    assembly_config_id: str
    runtime_config_id: str
    status: str
    article: Mapping[str, Any]
    nodes: tuple[CanonicalGraphNode, ...]
    edges: tuple[CanonicalGraphEdge, ...]
    sentences: tuple[Mapping[str, Any], ...]
    eventframes: tuple[Mapping[str, Any], ...]
    statements: tuple[Mapping[str, Any], ...]
    unmaterialized_evidence: Mapping[str, Any]
    lane_statuses: Mapping[str, Any]
    source_lanes: Mapping[str, Any]
    provenance: Mapping[str, Any]
    source_runtime_trace: tuple[Mapping[str, Any], ...]
    trace: tuple[Mapping[str, Any], ...]
    warnings: tuple[Mapping[str, Any], ...] = ()
    source_failures: tuple[Mapping[str, Any], ...] = ()
    validation: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(asdict(self), ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"graph result is not JSON serializable: {error}") from error

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=indent,
            sort_keys=True,
        )
