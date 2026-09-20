"""Closed public Article-local KG projection for Release V2.

The runtime and legacy evidence-preserving assembler retain implementation
objects.  This module consumes their resolved identities without making a new
coreference decision, then exposes only ARTICLE/EVENT/STATEMENT/ENTITY/TIME and
currently supported semantic relations.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from runtime.eventframe.contracts import ArticleLocalRuntimeResult

from .assembly import ArticleLocalKGAssembler
from .assembly_input import AssemblyInputAdapter
from .canonicalization import (
    EVENT_SPAN_VARIANT_POLICY_ID,
    CanonicalIdentityIndex,
    CanonicalizationDecision,
    CanonicalizationPipeline,
    default_canonicalization_registry,
)
from .derivation import (
    DeterministicDerivationPipeline,
    DerivedFact,
    default_derivation_registry,
)
from .foundation import AssemblyFoundationOutcome, AssemblyFoundationPipeline
from .materialization import PublicMaterializer
from .output_profiles import OutputProfile, OutputProfileProjector


PUBLIC_GRAPH_SCHEMA_VERSION = "articlelocal-kg-public-v2"
PUBLIC_ASSEMBLY_CONFIG_SCHEMA_VERSION = "articlelocal-kg-public-assembly-config-v2"
PUBLIC_NODE_KINDS = ("ARTICLE", "EVENT", "STATEMENT", "ENTITY", "TIME")
PUBLIC_EDGE_TYPES = (
    "COVERS",
    "CONTAINS_STATEMENT",
    "MENTIONS",
    "ACTOR",
    "TARGET",
    "PLACE",
    "OCCURRED_ON",
)
PUBLIC_EDGE_ENDPOINTS = {
    "COVERS": ("ARTICLE", "EVENT"),
    "CONTAINS_STATEMENT": ("ARTICLE", "STATEMENT"),
    "MENTIONS": ("ARTICLE", "ENTITY"),
    "ACTOR": ("EVENT", "ENTITY"),
    "TARGET": ("EVENT", "ENTITY"),
    "PLACE": ("EVENT", "ENTITY"),
    "OCCURRED_ON": ("EVENT", "TIME"),
}
PUBLIC_NODE_PROPERTY_KEYS = {
    "ARTICLE": (
        "article_id",
        "article_version_id",
        "title",
        "published_at",
        "source",
        "article_local",
    ),
    "EVENT": ("event_id", "canonical_text", "article_local", "triggers"),
    "STATEMENT": ("statement_id", "text", "statement_type"),
    "ENTITY": ("entity_id", "canonical_name", "entity_type", "article_local"),
    "TIME": ("time_id", "normalized_value", "granularity", "texts"),
}
PUBLIC_NODE_REQUIRED_PROPERTIES = {
    "ARTICLE": ("article_id", "article_local"),
    "EVENT": ("event_id", "canonical_text", "article_local", "triggers"),
    "STATEMENT": ("statement_id", "text", "statement_type"),
    "ENTITY": ("entity_id", "canonical_name", "entity_type", "article_local"),
    "TIME": ("time_id", "normalized_value", "texts"),
}
INTERNAL_NODE_KINDS = (
    "LOCAL_EVENT",
    "LOCAL_ENTITY",
    "EVENT_MENTION",
    "ENTITY_MENTION",
    "TRIGGER",
    "EVENTFRAME",
    "COREFERENCE_GROUP",
    "CANDIDATE",
    "STATEMENT_TYPE",
)
INTERNAL_EDGE_TYPES = (
    "MEMBER_OF_EVENT",
    "MEMBER_OF_ENTITY",
    "COREFERENT_WITH",
    "CANDIDATE_OF",
    "SELECTED_FROM",
    "REPRESENTATIVE_OF",
    "SAME_EVENT",
    "SAME_ENTITY",
)


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def _stable_id(kind: str, article_id: str, internal_identity: str) -> str:
    material = "\u241f".join((PUBLIC_GRAPH_SCHEMA_VERSION, article_id, internal_identity))
    return f"{kind}-{sha256(material.encode('utf-8')).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class PublicGraphEvidenceV2:
    article_id: str
    sentence_index: int
    char_start: int
    char_end: int
    text: str
    prediction_id: str | None = None
    source_lane: str | None = None
    confidence: float | None = None

    def validate(self, article_id: str, content: str) -> None:
        if self.article_id != article_id:
            raise ValueError("public evidence crossed an article boundary")
        if not 0 <= self.char_start < self.char_end <= len(content):
            raise ValueError("public evidence offset is outside source article")
        if content[self.char_start : self.char_end] != self.text:
            raise ValueError("public evidence does not round-trip to source article")


@dataclass(frozen=True, slots=True)
class PublicGraphNodeV2:
    node_id: str
    kind: str
    properties: Mapping[str, Any]
    evidence: tuple[PublicGraphEvidenceV2, ...]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class PublicGraphEdgeV2:
    edge_id: str
    edge_type: str
    source_id: str
    target_id: str
    confidence: float
    evidence: tuple[PublicGraphEvidenceV2, ...]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ArticleLocalKnowledgeGraphResultV2:
    """Default HF output: semantic ontology plus separated source evidence."""

    schema_version: str
    assembly_config_id: str
    runtime_config_id: str
    output_profile: str
    status: str
    article: Mapping[str, Any]
    nodes: tuple[PublicGraphNodeV2, ...]
    edges: tuple[PublicGraphEdgeV2, ...]
    evidence: Mapping[str, Any]
    source_lanes: Mapping[str, Any]
    coverage: Mapping[str, Any]
    provenance: Mapping[str, Any]
    trace: tuple[Mapping[str, Any], ...]
    warnings: tuple[Mapping[str, Any], ...] = ()
    source_failures: tuple[Mapping[str, Any], ...] = ()
    validation: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(asdict(self), ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"public graph result is not JSON serializable: {error}") from error

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, allow_nan=False, indent=indent, sort_keys=True
        )


@dataclass(frozen=True, slots=True)
class PublicAssemblyConfigV2:
    path: Path
    payload: Mapping[str, Any]
    legacy_assembly_path: Path
    ontology_path: Path

    @property
    def assembly_config_id(self) -> str:
        return str(self.payload["assembly_config_id"])

    @property
    def runtime_config_id(self) -> str:
        return str(self.payload["source_runtime_config_id"])


def _resolve_release_file(config_path: Path, row: Mapping[str, Any], name: str) -> Path:
    root = config_path.parent.parent.resolve()
    relative = Path(str(row["path"]))
    if relative.is_absolute():
        raise ValueError(f"{name} path must be release-relative")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{name} path escapes release root") from error
    if not path.is_file() or _digest(path) != str(row["sha256"]):
        raise ValueError(f"{name} is absent or has a SHA-256 mismatch")
    return path


def load_public_assembly_config_v2(path: str | Path) -> PublicAssemblyConfigV2:
    config_path = Path(path).resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PUBLIC_ASSEMBLY_CONFIG_SCHEMA_VERSION:
        raise ValueError("unsupported public graph assembly config schema")
    if payload.get("output_schema_version") != PUBLIC_GRAPH_SCHEMA_VERSION:
        raise ValueError("public graph output schema mismatch")
    if payload.get("materialized_node_kinds") != list(PUBLIC_NODE_KINDS):
        raise ValueError("public node allowlist mismatch")
    if payload.get("materialized_edge_types") != list(PUBLIC_EDGE_TYPES):
        raise ValueError("public edge allowlist mismatch")
    if payload.get("internal_only_node_kinds") != list(INTERNAL_NODE_KINDS):
        raise ValueError("internal-only node contract mismatch")
    if payload.get("internal_only_edge_types") != list(INTERNAL_EDGE_TYPES):
        raise ValueError("internal-only edge contract mismatch")
    if payload.get("coreference_decision_in_assembler") is not False:
        raise ValueError("public assembler must not make coreference decisions")
    if payload.get("fake_node_fallback") is not False:
        raise ValueError("public assembler must not create fake nodes")
    legacy = _resolve_release_file(config_path, payload["legacy_assembly_config"], "legacy assembly")
    ontology = _resolve_release_file(config_path, payload["ontology"], "public ontology")
    ontology_payload = json.loads(ontology.read_text(encoding="utf-8"))
    if ontology_payload.get("node_kinds") != list(PUBLIC_NODE_KINDS):
        raise ValueError("public ontology node allowlist mismatch")
    if ontology_payload.get("edge_types") != list(PUBLIC_EDGE_TYPES):
        raise ValueError("public ontology edge allowlist mismatch")
    if ontology_payload.get("edge_endpoints") != {
        name: list(endpoints) for name, endpoints in PUBLIC_EDGE_ENDPOINTS.items()
    }:
        raise ValueError("public ontology edge endpoint contract mismatch")
    if ontology_payload.get("node_property_contract") != {
        name: list(properties) for name, properties in PUBLIC_NODE_PROPERTY_KEYS.items()
    }:
        raise ValueError("public ontology node property contract mismatch")
    return PublicAssemblyConfigV2(config_path, payload, legacy, ontology)


def _evidence(
    value: Mapping[str, Any],
    *,
    prediction_id: str | None = None,
    source_lane: str | None = None,
    confidence: float | None = None,
) -> PublicGraphEvidenceV2:
    return PublicGraphEvidenceV2(
        article_id=str(value["article_id"]),
        sentence_index=int(value["sentence_index"]),
        char_start=int(value["char_start"]),
        char_end=int(value["char_end"]),
        text=str(value["text"]),
        prediction_id=prediction_id,
        source_lane=source_lane,
        confidence=confidence,
    )


def _unique_evidence(values: list[PublicGraphEvidenceV2]) -> tuple[PublicGraphEvidenceV2, ...]:
    keyed = {
        (
            row.article_id,
            row.sentence_index,
            row.char_start,
            row.char_end,
            row.text,
            row.prediction_id,
            row.source_lane,
        ): row
        for row in values
    }
    return tuple(keyed[key] for key in sorted(keyed, key=lambda item: tuple(str(v) for v in item)))


def _public_trigger(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep trigger meaning in node properties while excluding model trace."""

    fields = ("text", "sentence_index", "char_start", "char_end")
    return {name: deepcopy(value[name]) for name in fields if value.get(name) is not None}


class PublicArticleLocalKGAssemblerV2:
    """Project resolved v1 implementation objects into the closed public ontology."""

    def __init__(
        self,
        config: PublicAssemblyConfigV2,
        *,
        canonicalization_policy_id: str = "NO_OP_CANONICALIZATION",
        derivation_policy_id: str = "NO_OP_DERIVATION",
    ) -> None:
        self.config = config
        self.canonicalization_policy_id = canonicalization_policy_id
        self.derivation_policy_id = derivation_policy_id
        self._legacy = ArticleLocalKGAssembler.from_config(config.legacy_assembly_path)
        self._foundation = AssemblyFoundationPipeline(
            input_adapter=AssemblyInputAdapter(self._legacy),
            canonicalization=CanonicalizationPipeline(
                default_canonicalization_registry(),
                active_policy_id=canonicalization_policy_id,
            ),
            derivation=DeterministicDerivationPipeline(
                default_derivation_registry(),
                active_policy_id=derivation_policy_id,
            ),
            materializer=PublicMaterializer(
                projector=self._materialize_legacy_graph,
                validator=self.validate,
                validation_attacher=lambda result, validation: replace(
                    result, validation=validation
                ),
            ),
            output_projector=OutputProfileProjector(),
        )

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        *,
        canonicalization_policy_id: str = "NO_OP_CANONICALIZATION",
        derivation_policy_id: str = "NO_OP_DERIVATION",
    ) -> "PublicArticleLocalKGAssemblerV2":
        return cls(
            load_public_assembly_config_v2(path),
            canonicalization_policy_id=canonicalization_policy_id,
            derivation_policy_id=derivation_policy_id,
        )

    def assemble(
        self,
        runtime_result: ArticleLocalRuntimeResult | Mapping[str, Any],
        *,
        output_profile: OutputProfile | str = OutputProfile.PUBLIC,
    ) -> ArticleLocalKnowledgeGraphResultV2:
        return self.assemble_with_audit(
            runtime_result, output_profile=output_profile
        ).output

    def assemble_with_audit(
        self,
        source: ArticleLocalRuntimeResult | Mapping[str, Any],
        *,
        output_profile: OutputProfile | str = OutputProfile.PUBLIC,
    ) -> AssemblyFoundationOutcome[ArticleLocalKnowledgeGraphResultV2]:
        """Run explicit stages and return audit ledgers outside the public payload."""

        return self._foundation.run(source, output_profile=output_profile)

    def project_legacy_graph(
        self,
        legacy_graph: Mapping[str, Any],
        *,
        output_profile: OutputProfile | str = OutputProfile.PUBLIC,
    ) -> ArticleLocalKnowledgeGraphResultV2:
        """Compatibility facade for callers with an existing legacy assembly graph."""

        return self.assemble_with_audit(
            legacy_graph, output_profile=output_profile
        ).output

    def _materialize_legacy_graph(
        self,
        legacy_graph: Mapping[str, Any],
        identity_index: CanonicalIdentityIndex | None = None,
        canonicalization_decisions: tuple[CanonicalizationDecision, ...] = (),
        derived_facts: tuple[DerivedFact, ...] = (),
    ) -> ArticleLocalKnowledgeGraphResultV2:
        """Represent an already decided derived state without new semantic judgment."""

        legacy = json.loads(json.dumps(legacy_graph, ensure_ascii=False, allow_nan=False))
        self._apply_derived_facts(legacy, derived_facts)
        article = deepcopy(legacy["article"])
        article_id = str(article["article_id"])
        legacy_nodes = {str(row["node_id"]): row for row in legacy["nodes"]}
        if len(legacy_nodes) != len(legacy["nodes"]):
            raise ValueError("legacy graph contains duplicate node identities")
        nodes: list[PublicGraphNodeV2] = []
        public_by_internal: dict[str, str] = {}

        article_nodes = [row for row in legacy["nodes"] if row["kind"] == "ARTICLE"]
        if len(article_nodes) != 1:
            raise ValueError("legacy graph must contain exactly one ARTICLE")
        source_article = article_nodes[0]
        article_public_id = _stable_id("ARTICLE", article_id, str(source_article["node_id"]))
        public_by_internal[str(source_article["node_id"])] = article_public_id
        nodes.append(
            PublicGraphNodeV2(
                node_id=article_public_id,
                kind="ARTICLE",
                properties={**deepcopy(source_article["properties"]), "article_local": True},
                evidence=(),
                provenance={
                    "source": "PUBLIC_V2_IDENTITY_PROJECTION",
                    "source_node_id": source_article["node_id"],
                    "source_provenance": deepcopy(source_article["provenance"]),
                },
            )
        )

        local_event_nodes = [row for row in legacy["nodes"] if row["kind"] == "LOCAL_EVENT"]
        member_edges = [row for row in legacy["edges"] if row["edge_type"] == "MEMBER_OF_EVENT"]
        event_members_by_local: dict[str, list[str]] = defaultdict(list)
        for edge in member_edges:
            event_members_by_local[str(edge["target_id"])].append(str(edge["source_id"]))
        clustered_event_ids: set[str] = {
            member_id
            for member_ids in event_members_by_local.values()
            for member_id in member_ids
        }
        resolved_event_ids = {
            str(row["node_id"]) for row in local_event_nodes
        } | {
            str(row["node_id"])
            for row in legacy["nodes"]
            if row["kind"] == "EVENT" and str(row["node_id"]) not in clustered_event_ids
        }
        event_groups = (
            identity_index.groups("EVENT")
            if identity_index is not None
            else tuple((identity, (identity,)) for identity in sorted(resolved_event_ids))
        )
        indexed_event_ids = {
            member for _representative, members in event_groups for member in members
        }
        if indexed_event_ids != resolved_event_ids:
            raise ValueError("canonical EVENT index does not cover resolved identities exactly")
        collapsed_groups = tuple(
            (representative, members)
            for representative, members in event_groups
            if len(members) >= 2
        )
        collapsed_source_ids = {
            member for _representative, members in collapsed_groups for member in members
        }
        for local_event in sorted(local_event_nodes, key=lambda row: str(row["node_id"])):
            internal_id = str(local_event["node_id"])
            if internal_id in collapsed_source_ids:
                continue
            public_id = _stable_id("EVENT", article_id, internal_id)
            member_node_ids = sorted(event_members_by_local.get(internal_id, ()))
            expected_frame_ids = sorted(
                str(value) for value in local_event["properties"].get("member_eventframe_ids", ())
            )
            if member_node_ids != expected_frame_ids or not member_node_ids:
                raise ValueError("LocalEvent membership cannot be deterministically projected")
            public_by_internal[internal_id] = public_id
            for member_id in member_node_ids:
                public_by_internal[member_id] = public_id
            member_prediction_ids = tuple(
                str(value)
                for value in local_event["properties"]["member_event_prediction_ids"]
            )
            representative = str(
                local_event["properties"]["representative_event_prediction_id"]
            )
            raw_evidence = list(local_event["evidence"])
            if len(raw_evidence) != len(member_prediction_ids):
                raise ValueError("LocalEvent member evidence cardinality mismatch")
            evidence = _unique_evidence(
                [
                    _evidence(
                        value,
                        prediction_id=prediction_id,
                        source_lane="event_mentions",
                    )
                    for value, prediction_id in zip(raw_evidence, member_prediction_ids)
                ]
            )
            source_triggers = []
            for member_id in member_node_ids:
                trigger = legacy_nodes[member_id]["properties"].get("trigger")
                if trigger and trigger not in source_triggers:
                    source_triggers.append(deepcopy(trigger))
            nodes.append(
                PublicGraphNodeV2(
                    node_id=public_id,
                    kind="EVENT",
                    properties={
                        "event_id": public_id,
                        "canonical_text": local_event["properties"]["canonical_text"],
                        "article_local": True,
                        "triggers": [_public_trigger(value) for value in source_triggers],
                    },
                    evidence=evidence,
                    provenance={
                        "source": "RESOLVED_ARTICLE_LOCAL_EVENT_IDENTITY",
                        "source_local_event_id": internal_id,
                        "source_eventframe_ids": member_node_ids,
                        "representative_prediction_id": representative,
                        "member_prediction_ids": member_prediction_ids,
                        "cluster_confidence": local_event["properties"].get("confidence"),
                        "source_triggers": source_triggers,
                        "source_provenance": deepcopy(local_event["provenance"]),
                    },
                )
            )
        for event in sorted(
            (row for row in legacy["nodes"] if row["kind"] == "EVENT"),
            key=lambda row: str(row["node_id"]),
        ):
            internal_id = str(event["node_id"])
            if internal_id in clustered_event_ids or internal_id in collapsed_source_ids:
                continue
            prediction_id = str(event["properties"]["source_prediction_id"])
            public_id = _stable_id("EVENT", article_id, internal_id)
            public_by_internal[internal_id] = public_id
            nodes.append(
                PublicGraphNodeV2(
                    node_id=public_id,
                    kind="EVENT",
                    properties={
                        "event_id": public_id,
                        "canonical_text": event["properties"]["text"],
                        "article_local": True,
                        "triggers": [_public_trigger(event["properties"]["trigger"])]
                        if event["properties"].get("trigger")
                        else [],
                    },
                    evidence=_unique_evidence(
                        [
                            _evidence(
                                event["evidence"][0],
                                prediction_id=prediction_id,
                                source_lane="event_mentions",
                            )
                        ]
                    ),
                    provenance={
                        "source": "UNCLUSTERED_EVENT_IDENTITY",
                        "source_eventframe_ids": [internal_id],
                        "representative_prediction_id": prediction_id,
                        "member_prediction_ids": [prediction_id],
                        "source_triggers": [deepcopy(event["properties"]["trigger"])]
                        if event["properties"].get("trigger")
                        else [],
                        "source_provenance": deepcopy(event["provenance"]),
                    },
                )
            )

        event_decisions = {
            row.output_representative_id: row
            for row in canonicalization_decisions
            if row.scope == "EVENT"
        }
        event_node_by_prediction = {
            str(row["properties"]["source_prediction_id"]): row
            for row in legacy["nodes"]
            if row["kind"] == "EVENT"
        }
        for representative_id, member_resolved_ids in collapsed_groups:
            decision = event_decisions.get(representative_id)
            if decision is None or decision.decision != "COLLAPSE":
                raise ValueError("collapsed EVENT family lacks its canonicalization decision")
            public_id = _stable_id("EVENT", article_id, representative_id)
            source_eventframe_ids: list[str] = []
            source_local_event_ids: list[str] = []
            member_prediction_ids: list[str] = []
            evidence_rows: list[PublicGraphEvidenceV2] = []
            source_provenance = []
            original_coreference_provenance = []
            source_triggers = []
            representative_prediction_id = None
            for resolved_id in member_resolved_ids:
                resolved = legacy_nodes[resolved_id]
                public_by_internal[resolved_id] = public_id
                if resolved["kind"] == "LOCAL_EVENT":
                    frame_ids = sorted(event_members_by_local.get(resolved_id, ()))
                    expected_frame_ids = sorted(
                        str(value)
                        for value in resolved["properties"].get("member_eventframe_ids", ())
                    )
                    if frame_ids != expected_frame_ids or not frame_ids:
                        raise ValueError("canonical family contains invalid LocalEvent membership")
                    prediction_ids = [
                        str(value)
                        for value in resolved["properties"]["member_event_prediction_ids"]
                    ]
                    raw_evidence = list(resolved["evidence"])
                    if len(raw_evidence) != len(prediction_ids):
                        raise ValueError("canonical family LocalEvent evidence cardinality mismatch")
                    source_local_event_ids.append(resolved_id)
                    original_coreference_provenance.append(deepcopy(resolved["provenance"]))
                    candidate_representative_prediction = str(
                        resolved["properties"]["representative_event_prediction_id"]
                    )
                elif resolved["kind"] == "EVENT":
                    frame_ids = [resolved_id]
                    candidate_representative_prediction = str(
                        resolved["properties"]["source_prediction_id"]
                    )
                    prediction_ids = [candidate_representative_prediction]
                    raw_evidence = list(resolved["evidence"])
                else:
                    raise ValueError("canonical EVENT family contains a non-EVENT identity")
                if resolved_id == representative_id:
                    representative_prediction_id = candidate_representative_prediction
                source_eventframe_ids.extend(frame_ids)
                member_prediction_ids.extend(prediction_ids)
                source_provenance.append(deepcopy(resolved["provenance"]))
                evidence_rows.extend(
                    _evidence(
                        value,
                        prediction_id=prediction_id,
                        source_lane="event_mentions",
                    )
                    for value, prediction_id in zip(raw_evidence, prediction_ids)
                )
                for frame_id in frame_ids:
                    public_by_internal[frame_id] = public_id
                    trigger = legacy_nodes[frame_id]["properties"].get("trigger")
                    if trigger and trigger not in source_triggers:
                        source_triggers.append(deepcopy(trigger))
            if representative_prediction_id is None:
                raise ValueError("canonical EVENT representative prediction is unavailable")
            representative_event = event_node_by_prediction.get(representative_prediction_id)
            if representative_event is None:
                raise ValueError("canonical EVENT representative source EventFrame is unavailable")
            source_eventframe_ids = list(dict.fromkeys(source_eventframe_ids))
            source_local_event_ids = list(dict.fromkeys(source_local_event_ids))
            member_prediction_ids = list(dict.fromkeys(member_prediction_ids))
            nodes.append(
                PublicGraphNodeV2(
                    node_id=public_id,
                    kind="EVENT",
                    properties={
                        "event_id": public_id,
                        "canonical_text": representative_event["properties"]["text"],
                        "article_local": True,
                        "triggers": [
                            _public_trigger(value) for value in source_triggers
                        ],
                    },
                    evidence=_unique_evidence(evidence_rows),
                    provenance={
                        "source": "CANONICALIZED_ARTICLE_LOCAL_EVENT_IDENTITY",
                        "canonicalization_policy_id": decision.policy_id,
                        "canonicalization_policy_version": decision.policy_version,
                        "representative_resolved_event_id": representative_id,
                        "representative_prediction_id": representative_prediction_id,
                        "source_resolved_event_ids": list(member_resolved_ids),
                        "member_prediction_ids": member_prediction_ids,
                        "source_eventframe_ids": source_eventframe_ids,
                        "source_local_event_ids": source_local_event_ids,
                        "original_coreference_provenance": original_coreference_provenance,
                        "span_variant_member_count": len(member_resolved_ids),
                        "source_triggers": source_triggers,
                        "source_provenance": source_provenance,
                        "canonicalization_decision_provenance": decision.provenance.to_dict(),
                    },
                )
            )

        for entity in sorted(
            (row for row in legacy["nodes"] if row["kind"] == "LOCAL_ENTITY"),
            key=lambda row: str(row["node_id"]),
        ):
            internal_id = str(entity["node_id"])
            public_id = _stable_id("ENTITY", article_id, internal_id)
            public_by_internal[internal_id] = public_id
            member_prediction_ids = tuple(
                str(value)
                for value in entity["properties"]["member_entity_prediction_ids"]
            )
            representative = str(
                entity["properties"]["representative_entity_prediction_id"]
            )
            raw_evidence = list(entity["evidence"])
            if len(raw_evidence) != len(member_prediction_ids):
                raise ValueError("LocalEntity member evidence cardinality mismatch")
            evidence = _unique_evidence(
                [
                    _evidence(
                        value,
                        prediction_id=prediction_id,
                        source_lane="entity_mentions",
                    )
                    for value, prediction_id in zip(raw_evidence, member_prediction_ids)
                ]
            )
            nodes.append(
                PublicGraphNodeV2(
                    node_id=public_id,
                    kind="ENTITY",
                    properties={
                        "entity_id": public_id,
                        "canonical_name": entity["properties"]["canonical_name"],
                        "entity_type": entity["properties"]["entity_type"],
                        "article_local": True,
                    },
                    evidence=evidence,
                    provenance={
                        "source": "RESOLVED_ARTICLE_LOCAL_ENTITY_IDENTITY",
                        "source_local_entity_id": internal_id,
                        "representative_prediction_id": representative,
                        "member_prediction_ids": member_prediction_ids,
                        "source_provenance": deepcopy(entity["provenance"]),
                    },
                )
            )

        for statement in sorted(
            (row for row in legacy["nodes"] if row["kind"] == "STATEMENT"),
            key=lambda row: str(row["node_id"]),
        ):
            internal_id = str(statement["node_id"])
            public_id = _stable_id("STATEMENT", article_id, internal_id)
            public_by_internal[internal_id] = public_id
            prediction_id = str(statement["properties"]["source_prediction_id"])
            nodes.append(
                PublicGraphNodeV2(
                    node_id=public_id,
                    kind="STATEMENT",
                    properties={
                        "statement_id": public_id,
                        "text": statement["properties"]["text"],
                        "statement_type": statement["properties"].get("statement_type"),
                    },
                    evidence=_unique_evidence(
                        [
                            _evidence(
                                statement["evidence"][0],
                                prediction_id=prediction_id,
                                source_lane="statement_mentions",
                            )
                        ]
                    ),
                    provenance={
                        "source": "STATEMENT_SEMANTIC_PROPOSITION",
                        "source_statement_id": internal_id,
                        "representative_prediction_id": prediction_id,
                        "member_prediction_ids": [prediction_id],
                        "source_properties": deepcopy(statement["properties"]),
                        "source_provenance": deepcopy(statement["provenance"]),
                    },
                )
            )

        time_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        indexed_time_ids = (
            set(identity_index.source_to_representative.get("TIME", {}))
            if identity_index is not None
            else set()
        )
        for temporal in (row for row in legacy["nodes"] if row["kind"] == "TIME"):
            internal_id = str(temporal["node_id"])
            representative_id = (
                identity_index.representative_for("TIME", internal_id)
                if identity_index is not None and internal_id in indexed_time_ids
                else internal_id
            )
            time_groups[representative_id].append(temporal)
        for representative_id in sorted(time_groups):
            members = sorted(time_groups[representative_id], key=lambda row: str(row["node_id"]))
            normalized = {
                (
                    str(row["properties"]["normalized_value"]),
                    str(row["properties"].get("granularity")),
                    str(row["properties"].get("temporal_semantic_type", "POINT")),
                    str(row["properties"].get("timezone") or ""),
                )
                for row in members
            }
            if len(normalized) != 1:
                raise ValueError("canonical TIME family contains incompatible value/granularity/type/timezone")
            normalized_value, granularity, _semantic_type, _timezone = next(iter(normalized))
            public_id = _stable_id("TIME", article_id, representative_id)
            evidence_by_prediction = {}
            for temporal in members:
                internal_id = str(temporal["node_id"])
                public_by_internal[internal_id] = public_id
                prediction_ids = tuple(
                    str(value)
                    for value in temporal["properties"].get("source_time_prediction_ids", ())
                )
                raw_evidence = list(temporal["evidence"])
                if len(raw_evidence) != len(prediction_ids):
                    raise ValueError("TIME evidence cardinality mismatch")
                evidence_by_prediction.update(zip(prediction_ids, raw_evidence))
            prediction_ids = tuple(sorted(evidence_by_prediction))
            raw_evidence = [evidence_by_prediction[value] for value in prediction_ids]
            nodes.append(
                PublicGraphNodeV2(
                    node_id=public_id,
                    kind="TIME",
                    properties={
                        "time_id": public_id,
                        "normalized_value": normalized_value,
                        "granularity": None if granularity == "None" else granularity,
                        "texts": sorted({str(value["text"]) for value in raw_evidence}),
                    },
                    evidence=_unique_evidence(
                        [
                            _evidence(
                                value,
                                prediction_id=prediction_id,
                                source_lane="time_expressions",
                            )
                            for value, prediction_id in zip(raw_evidence, prediction_ids)
                        ]
                    ),
                    provenance={
                        "source": "CANONICAL_NORMALIZED_TIME",
                        "source_time_node_id": representative_id,
                        "source_time_node_ids": [str(row["node_id"]) for row in members],
                        "member_prediction_ids": prediction_ids,
                        "source_provenance": [deepcopy(row["provenance"]) for row in members],
                    },
                )
            )

        public_node_by_id = {node.node_id: node for node in nodes}
        edge_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for edge in legacy["edges"]:
            edge_type = str(edge["edge_type"])
            if edge_type == "MEMBER_OF_EVENT":
                continue
            if edge_type not in PUBLIC_EDGE_TYPES:
                raise ValueError(f"implementation or unsupported edge leaked: {edge_type}")
            source = public_by_internal.get(str(edge["source_id"]))
            target = public_by_internal.get(str(edge["target_id"]))
            if source is None or target is None:
                raise ValueError("semantic relation endpoint cannot be deterministically remapped")
            edge_groups[(edge_type, source, target)].append(edge)
        edges: list[PublicGraphEdgeV2] = []
        for (edge_type, source, target), source_edges in sorted(edge_groups.items()):
            evidence_rows: list[PublicGraphEvidenceV2] = []
            if edge_type == "MENTIONS":
                evidence_rows.extend(public_node_by_id[target].evidence)
            else:
                for edge in source_edges:
                    if edge_type == "OCCURRED_ON" and edge.get("provenance", {}).get("source_time_prediction_ids"):
                        occurrence_ids = tuple(
                            str(value) for value in edge["provenance"]["source_time_prediction_ids"]
                        )
                        if len(occurrence_ids) != len(edge.get("evidence", ())):
                            raise ValueError("Event-Time support evidence cardinality mismatch")
                        evidence_rows.extend(
                            _evidence(value, prediction_id=prediction_id, source_lane="occurred_on")
                            for value, prediction_id in zip(edge["evidence"], occurrence_ids)
                        )
                        continue
                    prediction_id = edge.get("provenance", {}).get(
                        "participant_evidence_id",
                        edge.get("provenance", {}).get(
                            "source_prediction_id",
                            edge.get("provenance", {}).get("source_time_prediction_id"),
                        ),
                    )
                    evidence_rows.extend(
                        _evidence(
                            value,
                            prediction_id=str(prediction_id) if prediction_id else None,
                            source_lane=edge_type.lower(),
                        )
                        for value in edge.get("evidence", ())
                    )
            source_ids = tuple(sorted(str(edge["edge_id"]) for edge in source_edges))
            edges.append(
                PublicGraphEdgeV2(
                    edge_id=_stable_id(
                        "EDGE", article_id, "|".join((edge_type, source, target))
                    ),
                    edge_type=edge_type,
                    source_id=source,
                    target_id=target,
                    confidence=max(float(edge["confidence"]) for edge in source_edges),
                    evidence=_unique_evidence(evidence_rows),
                    provenance={
                        "source": "SEMANTIC_EDGE_ENDPOINT_PROJECTION",
                        "source_edge_ids": source_ids,
                        "source_provenance": [
                            deepcopy(edge["provenance"]) for edge in source_edges
                        ],
                    },
                )
            )

        source_lanes = {
            "sentences": deepcopy(legacy.get("sentences", [])),
            "eventframes": deepcopy(legacy.get("eventframes", [])),
            "statements": deepcopy(legacy.get("statements", [])),
            **deepcopy(legacy.get("source_lanes", {})),
        }
        result = ArticleLocalKnowledgeGraphResultV2(
            schema_version=PUBLIC_GRAPH_SCHEMA_VERSION,
            assembly_config_id=self.config.assembly_config_id,
            runtime_config_id=str(legacy["runtime_config_id"]),
            output_profile=OutputProfile.DEBUG.value,
            status="PUBLIC_ARTICLE_LOCAL_KG_READY",
            article=article,
            nodes=tuple(sorted(nodes, key=lambda row: (PUBLIC_NODE_KINDS.index(row.kind), row.node_id))),
            edges=tuple(sorted(edges, key=lambda row: (PUBLIC_EDGE_TYPES.index(row.edge_type), row.edge_id))),
            evidence={
                "unmaterialized": deepcopy(legacy.get("unmaterialized_evidence", {})),
                "policy": "raw and unresolved evidence remains outside nodes/edges",
            },
            source_lanes=source_lanes,
            coverage={
                "runtime": deepcopy(legacy.get("source_lanes", {}).get("coverage", {})),
                "lane_statuses": deepcopy(legacy.get("lane_statuses", {})),
            },
            provenance={
                "source_schema_version": legacy["schema_version"],
                "source_assembly_config_id": legacy["assembly_config_id"],
                "public_assembly_config_id": self.config.assembly_config_id,
                "identity_scope": "ARTICLE_LOCAL_ONLY",
                "coreference_decision_in_assembler": False,
                "fake_node_fallback": False,
                "active_canonicalization_policy": self.canonicalization_policy_id,
                "active_canonicalization_component_policies": list(
                    getattr(
                        self._foundation.canonicalization.registry.get(
                            self.canonicalization_policy_id
                        ),
                        "component_policy_ids",
                        (self.canonicalization_policy_id,),
                    )
                ),
                "active_derivation_policy": self.derivation_policy_id,
                "active_derivation_component_policies": list(
                    getattr(
                        self._foundation.derivation.registry.get(
                            self.derivation_policy_id
                        ),
                        "component_policy_ids",
                        (self.derivation_policy_id,),
                    )
                ),
            },
            trace=(
                {
                    "stage": "HF_PUBLIC_OUTPUT_PROJECTION_V2",
                    "source_node_count": len(legacy["nodes"]),
                    "public_node_count": len(nodes),
                    "source_edge_count": len(legacy["edges"]),
                    "public_edge_count": len(edges),
                    "removed_node_kinds": list(INTERNAL_NODE_KINDS),
                    "removed_edge_types": list(INTERNAL_EDGE_TYPES),
                },
            ),
            warnings=tuple(deepcopy(legacy.get("warnings", []))),
            source_failures=tuple(deepcopy(legacy.get("source_failures", []))),
        )
        return result

    @staticmethod
    def _apply_derived_facts(
        legacy: dict[str, Any], derived_facts: tuple[DerivedFact, ...]
    ) -> None:
        """Represent already-decided temporal facts in the legacy projection carrier."""

        time_nodes = {
            str(row["node_id"]): row
            for row in legacy["nodes"]
            if row["kind"] == "TIME"
        }
        for fact in derived_facts:
            value = fact.value
            if fact.derived_kind != "TIME_NORMALIZATION":
                continue
            time_id = str(value["canonical_time_identity_id"])
            prediction_id = str(value["source_time_prediction_id"])
            evidence = deepcopy(value["source_evidence"])
            evidence.pop("prediction_id", None)
            evidence.pop("confidence", None)
            node = time_nodes.get(time_id)
            if node is None:
                node = {
                    "node_id": time_id,
                    "kind": "TIME",
                    "properties": {
                        "normalized_value": value["normalized_value"],
                        "granularity": value["granularity"],
                        "temporal_semantic_type": value.get("temporal_semantic_type", "POINT"),
                        "timezone": value.get("timezone"),
                        "source_time_prediction_ids": [prediction_id],
                    },
                    "evidence": [evidence],
                    "provenance": {
                        "source": "DETERMINISTIC_TIME_NORMALIZER_V2",
                        "derivation_provenance": [fact.provenance.to_dict()],
                    },
                }
                legacy["nodes"].append(node)
                time_nodes[time_id] = node
                continue
            pairs = {
                str(source_id): source_evidence
                for source_id, source_evidence in zip(
                    node["properties"].get("source_time_prediction_ids", ()),
                    node.get("evidence", ()),
                )
            }
            pairs[prediction_id] = evidence
            node["properties"]["source_time_prediction_ids"] = sorted(pairs)
            node["evidence"] = [pairs[source_id] for source_id in sorted(pairs)]
            node.setdefault("provenance", {}).setdefault(
                "derivation_provenance", []
            ).append(fact.provenance.to_dict())

        existing_edge_ids = {str(row["edge_id"]) for row in legacy["edges"]}
        for fact in derived_facts:
            if fact.derived_kind not in {
                "LEARNED_EVENT_TIME_MATERIALIZATION",
                "EVENT_TIME_RESCUE",
            }:
                continue
            value = fact.value
            edge_id = "DEDGE-" + sha256(
                str(value["fact_id"]).encode("utf-8")
            ).hexdigest()[:24]
            if edge_id in existing_edge_ids:
                continue
            evidence = deepcopy(value["source_evidence"])
            evidence.pop("prediction_id", None)
            evidence.pop("confidence", None)
            legacy["edges"].append(
                {
                    "edge_id": edge_id,
                    "edge_type": "OCCURRED_ON",
                    "source_id": str(value["source_event_identity_id"]),
                    "target_id": str(value["target_time_identity_id"]),
                    "confidence": float(value["confidence"]),
                    "evidence": [evidence],
                    "provenance": {
                        "source": (
                            "DETERMINISTIC_EVENT_TIME_RESCUE"
                            if fact.derived_kind == "EVENT_TIME_RESCUE"
                            else "LEARNED_EVENT_TIME_ATTACHMENT_PLUS_TIME_NORMALIZER_V2"
                        ),
                        "source_time_prediction_id": value[
                            "source_time_prediction_id"
                        ],
                        "source_attachment_id": value.get("source_attachment_id"),
                        "proof_type": value["proof_type"],
                        "derivation_provenance": fact.provenance.to_dict(),
                    },
                }
            )
            existing_edge_ids.add(edge_id)

    def validate(self, result: ArticleLocalKnowledgeGraphResultV2) -> dict[str, Any]:
        payload = result.to_dict()
        if payload["schema_version"] != PUBLIC_GRAPH_SCHEMA_VERSION:
            raise ValueError("public graph schema mismatch")
        article_id = str(payload["article"]["article_id"])
        content = str(payload["article"]["content"])
        nodes = payload["nodes"]
        edges = payload["edges"]
        node_ids = [str(row["node_id"]) for row in nodes]
        edge_ids = [str(row["edge_id"]) for row in edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate public node identity")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate public edge identity")
        node_by_id = {str(row["node_id"]): row for row in nodes}
        kind_counts = Counter(str(row["kind"]) for row in nodes)
        if kind_counts["ARTICLE"] != 1:
            raise ValueError("public graph requires one ARTICLE")
        if set(kind_counts) - set(PUBLIC_NODE_KINDS):
            raise ValueError("public graph contains an internal or unknown node kind")
        if any(row["kind"] in INTERNAL_NODE_KINDS for row in nodes):
            raise ValueError("internal node leaked into public graph")
        for node in nodes:
            kind = str(node["kind"])
            property_names = set(node["properties"])
            if property_names - set(PUBLIC_NODE_PROPERTY_KEYS[kind]):
                raise ValueError("public node contains a property outside its ontology contract")
            if not set(PUBLIC_NODE_REQUIRED_PROPERTIES[kind]).issubset(property_names):
                raise ValueError("public node is missing a required ontology property")
            if kind == "EVENT":
                for trigger in node["properties"]["triggers"]:
                    if set(trigger) - {"text", "sentence_index", "char_start", "char_end"}:
                        raise ValueError("EVENT trigger semantic property contains model trace")
            for value in node["evidence"]:
                PublicGraphEvidenceV2(**value).validate(article_id, content)
            if node["kind"] in {"EVENT", "ENTITY"}:
                provenance = node["provenance"]
                representative = provenance["representative_prediction_id"]
                members = set(provenance["member_prediction_ids"])
                evidence_ids = {value.get("prediction_id") for value in node["evidence"]}
                if representative not in members or representative not in evidence_ids:
                    raise ValueError("representative is not preserved in member evidence")
                if not members.issubset(evidence_ids):
                    raise ValueError("canonical identity lost member evidence")
        for edge in edges:
            edge_type = str(edge["edge_type"])
            if edge_type not in PUBLIC_EDGE_TYPES or edge_type in INTERNAL_EDGE_TYPES:
                raise ValueError("public graph contains an implementation edge")
            if edge["source_id"] not in node_by_id or edge["target_id"] not in node_by_id:
                raise ValueError("public graph contains a dangling edge")
            endpoints = (
                node_by_id[edge["source_id"]]["kind"],
                node_by_id[edge["target_id"]]["kind"],
            )
            if endpoints != PUBLIC_EDGE_ENDPOINTS[edge_type]:
                raise ValueError("public semantic edge has invalid endpoint kinds")
            for value in edge["evidence"]:
                PublicGraphEvidenceV2(**value).validate(article_id, content)
        if json.loads(result.to_json()) != payload:
            raise ValueError("public graph deterministic serialization failed")
        return {
            "status": "PASS",
            "schema_validation": "PASS",
            "serialization": "PASS",
            "allowed_public_node_kinds": list(PUBLIC_NODE_KINDS),
            "allowed_public_edge_types": list(PUBLIC_EDGE_TYPES),
            "node_kind_counts": dict(kind_counts),
            "edge_type_counts": dict(Counter(row["edge_type"] for row in edges)),
            "local_event_node_count": kind_counts["LOCAL_EVENT"],
            "local_entity_node_count": kind_counts["LOCAL_ENTITY"],
            "member_of_event_edge_count": sum(
                row["edge_type"] == "MEMBER_OF_EVENT" for row in edges
            ),
            "membership_implementation_edge_count": sum(
                row["edge_type"] in INTERNAL_EDGE_TYPES for row in edges
            ),
            "dangling_edge_count": 0,
            "invalid_endpoint_count": 0,
            "duplicate_node_id_count": 0,
            "duplicate_edge_id_count": 0,
            "fake_node_count": 0,
            "event_identity_flattened": True,
            "entity_identity_flattened": True,
            "event_evidence_preserved": True,
            "entity_evidence_preserved": True,
            "relation_endpoint_remap_complete": True,
            "coreference_decision_in_assembler": False,
        }
