"""v2.2 Serving Plane: compact identity/fact에서 직접 PUBLIC을 조립한다.

legacy graph adapter, Event B3, Entity identity scorer는 이 경로의 입력이 아니다.
assembly가 하는 추가 의미 계산은 canonical temporal occurrence의 V2 규칙뿐이다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Mapping

from runtime.eventframe.contracts import ArticleInput
from runtime.eventframe.resolved_contracts import (
    COMPACT_RUNTIME_CONTRACT_ID, OUTPUT_PROFILE_CONTRACT_ID,
    PUBLIC_SCHEMA_VERSION, PUBLIC_SEMANTIC_PROPERTY_KEYS,
    PUBLIC_SEMANTIC_REQUIRED_KEYS,
    CanonicalStatementState, CanonicalTemporalState,
    EventIdentityClosure, GroundedFact, GroundingRef, GroundingRegistry,
    LocalEntityState, PublicIdentity, ResolvedGraphState,
)
from runtime.temporal_identity import normalized_temporal_key

from .derivation.time_normalization_v2 import TimeNormalizerV2
from .output_profiles import CompactOutputProfileProjector, OutputProfile


NODE_KINDS = ("ARTICLE", "EVENT", "STATEMENT", "ENTITY", "TIME")
EDGE_ENDPOINTS = {
    "COVERS": ("ARTICLE", "EVENT"),
    "CONTAINS_STATEMENT": ("ARTICLE", "STATEMENT"),
    "MENTIONS": ("ARTICLE", "ENTITY"),
    "ACTOR": ("EVENT", "ENTITY"),
    "TARGET": ("EVENT", "ENTITY"),
    "PLACE": ("EVENT", "ENTITY"),
    "OCCURRED_ON": ("EVENT", "TIME"),
}
EDGE_TYPES = tuple(EDGE_ENDPOINTS)
COMPACT_ASSEMBLY_CONFIG_SCHEMA_VERSION = "articlelocal-compact-assembly-config-v22-v1"


def _stable_id(prefix: str, *parts: object) -> str:
    material = "␟".join(str(part) for part in parts).encode("utf-8")
    return prefix + "-" + sha256(material).hexdigest()[:24]


def _unique_refs(refs) -> tuple[GroundingRef, ...]:
    return tuple(sorted(set(refs), key=lambda row: (
        row.article_version_id, row.char_start, row.char_end,
        row.sentence_index if row.sentence_index is not None else -1,
    )))


def _grounding_registry(identities, facts, pending=()) -> GroundingRegistry:
    refs = {}
    for identity in identities:
        for ref in _unique_refs(
            ref for ref in (identity.representative, *identity.evidence)
            if ref is not None
        ):
            refs[_stable_id("GREF", identity.identity_id, ref.article_version_id,
                            ref.char_start, ref.char_end)] = ref
    for fact in (*facts, *pending):
        for ref in _unique_refs(fact.supports):
            refs[_stable_id("GREF", fact.fact_id, ref.article_version_id,
                            ref.char_start, ref.char_end)] = ref
    return GroundingRegistry(refs)


def build_resolved_graph_state(
    article: ArticleInput, *, event_closure: EventIdentityClosure,
    local_entities: tuple[LocalEntityState, ...],
    entity_identity_remap: Mapping[str, str],
    statements: tuple[CanonicalStatementState, ...],
    temporal_occurrences: tuple[CanonicalTemporalState, ...],
    lane_statuses: Mapping[str, str], runtime_config_id: str,
    assembly_config_id: str, active_policy_ids: tuple[str, ...],
    component_provenance: Mapping[str, str], lane_reasons: Mapping[str, str] = None,
    runtime_config_sha256: str | None = None,
    assembly_config_sha256: str | None = None,
    public_schema_sha256: str | None = None,
    policy_config_sha256: Mapping[str, str] = None,
    diagnostic_sink=None,
) -> ResolvedGraphState:
    """canonical producer들의 allowlisted scalar/ref만 graph state에 이관한다."""
    article_id = str(article.article_id)
    article_version = str(article.article_version_id)
    digest = ResolvedGraphState.content_digest(article.content)
    identities = [PublicIdentity(
        article_id, "ARTICLE", None, None, {
            "article_id": article_id, "article_version_id": article_version,
            "content_sha256": digest, "published_at": article.published_at,
            "title": article.title, "source": article.source,
            "article_local": True,
        },
    )]
    remap = dict(event_closure.identity_remap)
    remap.update((str(key), str(value)) for key, value in entity_identity_remap.items())
    event_states = sorted(event_closure.local_events, key=lambda row: row.event_id)
    for event in event_states:
        trigger_refs = _unique_refs(event.triggers)
        conflicts = event.conflict_summary
        status = "UNRESOLVED" if (
            not conflicts.conflict_free or conflicts.missing_feature_reasons
        ) else "EXECUTED"
        identities.append(PublicIdentity(
            event.event_id, "EVENT", event.representative,
            event.canonical_text, {
                "canonical_text": event.canonical_text,
                "identity_confidence": event.identity_confidence,
                "identity_confidence_source": event.identity_confidence_source,
                "independent_support_count": event.independent_support_count,
                "triggers": tuple({
                    "text": ref.text(article_version_id=article_version,
                                     source_text=article.content),
                    "sentence_index": ref.sentence_index,
                    "char_start": ref.char_start, "char_end": ref.char_end,
                } for ref in trigger_refs),
                "role_conflicts": conflicts.role_conflicts,
                "time_conflict": conflicts.time_conflict,
                "predicate_conflict": conflicts.predicate_conflict,
                "modality_conflict": conflicts.modality_conflict,
                "missing_feature_reasons": conflicts.missing_feature_reasons,
                "status": status,
            }, trigger_refs,
        ))
    for statement in sorted(statements, key=lambda row: row.statement_id):
        identities.append(PublicIdentity(
            statement.statement_id, "STATEMENT", statement.representative,
            statement.canonical_text, {
                "canonical_text": statement.canonical_text,
                "statement_type_status": statement.statement_type_status,
                "statement_type_value": statement.statement_type_value,
                "status": (
                    "UNRESOLVED" if statement.statement_type_status in ("ERROR", "UNRESOLVED")
                    else "EXECUTED"
                ),
            },
        ))
        remap[statement.statement_id] = statement.statement_id
    for row in sorted(local_entities, key=lambda item: item.entity_id):
        if not row.grounding:
            raise ValueError("compact LocalEntity lacks representative grounding")
        ref = row.grounding[0]
        identity_id = row.entity_id
        name = row.canonical_name
        if ref.text(article_version_id=article_version, source_text=article.content) != name:
            raise ValueError("compact LocalEntity representative name differs from source")
        identities.append(PublicIdentity(
            identity_id, "ENTITY", ref, name, {
                "canonical_name": name,
                "entity_type": row.entity_type,
                "identity_confidence": row.identity_confidence,
                "identity_confidence_source": row.identity_confidence_source,
                "article_local": True, "status": "EXECUTED",
            },
        ))
    time_refs: dict[str, list[GroundingRef]] = {}
    time_keys = {}
    for occurrence in temporal_occurrences:
        if occurrence.representative.article_version_id != article_version:
            raise ValueError("canonical Time occurrence crossed article version")
        occurrence.representative.text(article_version_id=article_version,
                                       source_text=article.content)
        key = occurrence.normalized_key
        if key is None:
            continue
        identity_id = _stable_id("LTIME", article_id, *key.parts())
        time_keys[identity_id] = key
        time_refs.setdefault(identity_id, []).append(occurrence.representative)
        remap[occurrence.prediction_id] = identity_id
        remap[occurrence.temporal_occurrence_id] = identity_id
    for identity_id, key in sorted(time_keys.items()):
        refs = _unique_refs(time_refs[identity_id])
        identities.append(PublicIdentity(
            identity_id, "TIME", refs[0], key.value, {
                "normalized_value": key.value,
                "granularity": key.granularity,
                "normalization_status": "NORMALIZED",
                "temporal_semantic_type": key.semantic_type,
                "timezone": key.timezone,
                "normalization_source": "V1_RUNTIME_COMPATIBILITY_VIEW",
                "status": "EXECUTED",
            }, refs,
        ))
    identity_ids = {row.identity_id for row in identities}
    facts = []
    pending = []
    unresolved_count = 0
    unresolved_reasons = dict(lane_reasons or {})
    for event in event_states:
        for fact in event.facts:
            if fact.source_identity_id not in identity_ids:
                raise ValueError("Event closure fact lacks canonical LocalEvent source")
            if fact.target_identity_id in identity_ids:
                facts.append(fact)
            elif fact.relation == "OCCURRED_ON" and any(
                item.temporal_occurrence_id == fact.target_identity_id
                for item in temporal_occurrences
            ):
                pending.append(fact)
            else:
                unresolved_count += 1
                unresolved_reasons["fact_endpoint"] = "CANONICAL_TARGET_UNAVAILABLE"
                if diagnostic_sink is not None:
                    diagnostic_sink.record("decision", {
                        "component": "compact_fact_endpoint",
                        "fact_id": fact.fact_id,
                        "relation": fact.relation,
                        "target_identity_id": fact.target_identity_id,
                        "decision": "UNRESOLVED_CANONICAL_TARGET",
                    })
    for identity in identities:
        if identity.kind not in ("EVENT", "STATEMENT", "ENTITY"):
            continue
        relation = {"EVENT": "COVERS", "STATEMENT": "CONTAINS_STATEMENT",
                    "ENTITY": "MENTIONS"}[identity.kind]
        facts.append(GroundedFact(
            _stable_id("SFACT", article_id, relation, identity.identity_id),
            relation, article_id, identity.identity_id,
            (identity.representative,), 1.0, "EXECUTED",
        ))
    refs = _grounding_registry(identities, facts, pending)
    statuses = {str(key): str(value) for key, value in lane_statuses.items()}
    statuses["graph_assembly"] = "UNRESOLVED" if unresolved_count else "EXECUTED"
    return ResolvedGraphState(
        article_id, article_version, digest, article.published_at,
        tuple(identities), tuple(facts), remap, refs, statuses,
        article.title, article.source, runtime_config_id, assembly_config_id,
        tuple(active_policy_ids), dict(component_provenance),
        tuple(temporal_occurrences), tuple(pending), unresolved_count,
        unresolved_reasons,
        runtime_config_sha256, assembly_config_sha256,
        public_schema_sha256, dict(policy_config_sha256 or {}),
    )


def derive_canonical_time_v2(
    state: ResolvedGraphState, article: ArticleInput,
    *, diagnostic_sink=None,
) -> ResolvedGraphState:
    """V1 미정규화 canonical occurrence에만 V2를 적용하고 pending fact를 remap한다."""
    if (state.article_version_id != article.article_version_id
        or state.content_sha256 != ResolvedGraphState.content_digest(article.content)):
        raise ValueError("direct Time derivation source differs from graph state")
    identities = list(state.identities)
    known_ids = {row.identity_id for row in identities}
    remap = dict(state.identity_remap)
    reasons = dict(state.lane_reasons or {})
    normalizer = TimeNormalizerV2()
    time_derivation_issue = False
    for occurrence in state.temporal_occurrences:
        if occurrence.normalized_key is not None:
            continue  # V1 fact는 그대로 두고 V2가 덮어쓰지 않는다.
        text = occurrence.representative.text(
            article_version_id=state.article_version_id,
            source_text=article.content,
        )
        if occurrence.temporal_semantic_type != "POINT":
            result = None
            reason = "NON_POINT_TIME_NOT_NORMALIZED"
        else:
            result = normalizer.normalize(text, state.published_at)
            reason = result.rule_id
        key = normalized_temporal_key(
            result.to_dict(), semantic_type=occurrence.temporal_semantic_type,
        ) if result is not None else None
        if key is None:
            reasons["time_v2"] = "UNRESOLVED_CANONICAL_TIME"
            time_derivation_issue = True
            decision = "NOT_DERIVED"
        else:
            identity_id = _stable_id("LTIME", state.article_id, *key.parts())
            if identity_id not in known_ids:
                identities.append(PublicIdentity(
                    identity_id, "TIME", occurrence.representative, key.value, {
                        "normalized_value": key.value, "granularity": key.granularity,
                        "normalization_status": "NORMALIZED",
                        "temporal_semantic_type": key.semantic_type,
                        "timezone": key.timezone,
                        "normalization_source": "TIME_NORMALIZER_V2",
                        "status": "EXECUTED",
                    }, (occurrence.representative,),
                ))
                known_ids.add(identity_id)
            remap[occurrence.prediction_id] = identity_id
            remap[occurrence.temporal_occurrence_id] = identity_id
            decision = "DERIVED"
        if diagnostic_sink is not None:
            diagnostic_sink.record("decision", {
                "component": "compact_time_normalizer_v2",
                "temporal_occurrence_id": occurrence.temporal_occurrence_id,
                "decision": decision, "rule_id": reason,
                "article_version_id": state.article_version_id,
                "char_start": occurrence.representative.char_start,
                "char_end": occurrence.representative.char_end,
            })
    facts = list(state.facts)
    unresolved_count = state.unresolved_fact_count
    event_conflicts = {
        row.identity_id: row.semantic_properties
        for row in identities if row.kind == "EVENT"
    }
    for fact in state.pending_temporal_facts:
        target = remap.get(fact.target_identity_id)
        if target not in known_ids:
            unresolved_count += 1
            time_derivation_issue = True
            continue  # unresolved occurrence를 fake TIME node로 승격하지 않는다.
        conflict = event_conflicts[fact.source_identity_id]
        conflict_status = bool(
            conflict.get("time_conflict") or conflict.get("predicate_conflict")
            or conflict.get("modality_conflict")
        )
        facts.append(replace(
            fact, fact_id=_stable_id("EFACT", fact.source_identity_id,
                                    fact.relation, target),
            target_identity_id=target,
            status="UNRESOLVED" if conflict_status else "EXECUTED",
        ))
    # 동일 canonical endpoint의 learned relation은 최대 score/고유 support로 닫는다.
    grouped: dict[tuple[str, str, str], list[GroundedFact]] = {}
    for fact in facts:
        grouped.setdefault((fact.source_identity_id, fact.relation,
                            fact.target_identity_id), []).append(fact)
    compact_facts = tuple(GroundedFact(
        _stable_id("CFACT", *key), key[1], key[0], key[2],
        _unique_refs(ref for row in rows for ref in row.supports),
        max((row.confidence for row in rows if row.confidence is not None),
            default=None),
        "UNRESOLVED" if any(row.status == "UNRESOLVED" for row in rows)
        else "EXECUTED",
    ) for key, rows in sorted(grouped.items()))
    statuses = dict(state.lane_statuses)
    if time_derivation_issue:
        statuses["time_resolution"] = (
            "UNRESOLVED" if statuses.get("time_resolution") != "ERROR" else "ERROR"
        )
    if unresolved_count:
        statuses["graph_assembly"] = "UNRESOLVED"
    return replace(
        state, identities=tuple(identities), facts=compact_facts,
        identity_remap=remap,
        grounding_registry=_grounding_registry(identities, compact_facts),
        pending_temporal_facts=(), temporal_occurrences=(),
        unresolved_fact_count=unresolved_count,
        lane_statuses=statuses, lane_reasons=reasons,
    )


@dataclass(frozen=True, slots=True)
class CompactGraphEvidence:
    owner_id: str
    article_version_id: str
    sentence_index: int | None
    char_start: int
    char_end: int
    text: str
    semantic_purpose: str


@dataclass(frozen=True, slots=True)
class CompactGraphNode:
    node_id: str
    kind: str
    properties: Mapping[str, Any]
    evidence: tuple[CompactGraphEvidence, ...]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CompactGraphEdge:
    edge_id: str
    edge_type: str
    source_id: str
    target_id: str
    confidence: float | None
    status: str
    evidence: tuple[CompactGraphEvidence, ...]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CompactKnowledgeGraphResult:
    schema_version: str
    release_version: str
    compact_runtime_contract: str
    output_profile_contract: str
    output_profile: str
    assembly_config_id: str
    runtime_config_id: str
    status: str
    article: Mapping[str, Any]
    nodes: tuple[CompactGraphNode, ...]
    edges: tuple[CompactGraphEdge, ...]
    coverage: Mapping[str, Any]
    provenance: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    validation: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, allow_nan=False))

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False,
                          indent=indent, sort_keys=True)

    def pretty(self) -> str:
        """PUBLIC canonical identities와 relations를 표시한다."""
        labels = {
            "ARTICLE": "title", "EVENT": "canonical_text",
            "STATEMENT": "canonical_text", "ENTITY": "canonical_name",
            "TIME": "normalized_value",
        }
        lines = [f"ARTICLE {self.article['article_id']}: {self.article.get('title') or ''}"]
        for node in self.nodes:
            if node.kind == "ARTICLE":
                continue
            label = node.properties.get(labels[node.kind]) or (
                node.evidence[0].text if node.evidence else "UNRESOLVED"
            )
            lines.append(f"{node.kind} {node.node_id}: {label}")
        for edge in self.edges:
            lines.append(
                f"{edge.edge_type} {edge.source_id} -> {edge.target_id}"
                f" [{edge.status}]"
            )
        return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class CompactAssemblyOutcome:
    output: CompactKnowledgeGraphResult
    resolved_state: ResolvedGraphState
    diagnostic_records: tuple[Mapping[str, Any], ...] = ()
    diagnostic_artifact_reference: str | None = None


@dataclass(frozen=True, slots=True)
class CompactAssemblyConfig:
    path: Path
    payload: Mapping[str, Any]
    schema_path: Path

    @property
    def assembly_config_id(self) -> str:
        return str(self.payload["assembly_config_id"])

    @property
    def runtime_config_id(self) -> str:
        return str(self.payload["source_runtime_config_id"])


def load_compact_assembly_config(path: str | Path) -> CompactAssemblyConfig:
    config_path = Path(path).resolve()
    value = json.loads(config_path.read_text(encoding="utf-8"))
    if (value.get("schema_version") != COMPACT_ASSEMBLY_CONFIG_SCHEMA_VERSION
        or value.get("public_schema_version") != PUBLIC_SCHEMA_VERSION
        or value.get("compact_runtime_contract") != COMPACT_RUNTIME_CONTRACT_ID
        or value.get("output_profile_contract") != OUTPUT_PROFILE_CONTRACT_ID
        or value.get("release_version") != "2.2"
        or value.get("default_profile") != "PUBLIC"
        or value.get("node_kinds") != list(NODE_KINDS)
        or value.get("edge_types") != list(EDGE_TYPES)
        or value.get("default_legacy_graph_adapter") is not False
        or not value.get("source_runtime_config_id")
        or not value.get("assembly_config_id")):
        raise ValueError("unsupported v2.2 compact assembly config")
    relative = Path(str(value["public_schema"]["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("compact schema path must remain repository-relative")
    root = Path(__file__).resolve().parents[2]
    schema_path = (root / relative).resolve()
    schema_path.relative_to(root)
    if (not schema_path.is_file()
        or sha256(schema_path.read_bytes()).hexdigest()
        != str(value["public_schema"]["sha256"])):
        raise ValueError("compact PUBLIC schema is absent or differs")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if (schema.get("schema_version") != PUBLIC_SCHEMA_VERSION
        or schema.get("node_kinds") != list(NODE_KINDS)
        or schema.get("edge_endpoints") != {
            relation: list(kinds) for relation, kinds in EDGE_ENDPOINTS.items()
        }
        or {
            kind: set(keys) for kind, keys in
            schema.get("semantic_property_allowlist", {}).items()
        } != {
            kind: set(keys) for kind, keys in PUBLIC_SEMANTIC_PROPERTY_KEYS.items()
        }
        or {
            kind: set(keys) for kind, keys in
            schema.get("semantic_property_required", {}).items()
        } != {
            kind: set(keys) for kind, keys in PUBLIC_SEMANTIC_REQUIRED_KEYS.items()
        }):
        raise ValueError("compact PUBLIC schema ontology mismatch")
    return CompactAssemblyConfig(config_path, value, schema_path)


def _evidence(owner: str, ref: GroundingRef, purpose: str,
              state: ResolvedGraphState, article: ArticleInput) -> CompactGraphEvidence:
    return CompactGraphEvidence(
        owner, ref.article_version_id, ref.sentence_index,
        ref.char_start, ref.char_end,
        ref.text(article_version_id=state.article_version_id,
                 source_text=article.content), purpose,
    )


def _dedup_evidence(rows) -> tuple[CompactGraphEvidence, ...]:
    keyed = {
        (row.article_version_id, row.char_start, row.char_end,
         row.semantic_purpose): row for row in rows
    }
    return tuple(keyed[key] for key in sorted(keyed))


class CompactArticleLocalKGAssembler:
    """ResolvedGraphState -> narrow V2 Time derivation -> direct materialization."""

    def __init__(self, config: CompactAssemblyConfig) -> None:
        self.config = config
        self.output_projector = CompactOutputProfileProjector()

    @classmethod
    def from_config(cls, path: str | Path) -> "CompactArticleLocalKGAssembler":
        return cls(load_compact_assembly_config(path))

    def assemble(self, state: ResolvedGraphState, *, source_article: ArticleInput,
                 policy) -> CompactKnowledgeGraphResult:
        return self.assemble_with_audit(
            state, source_article=source_article, policy=policy,
        ).output

    def assemble_with_audit(self, state: ResolvedGraphState, *,
                            source_article: ArticleInput, policy) -> CompactAssemblyOutcome:
        started = time.perf_counter()
        if (not isinstance(state, ResolvedGraphState)
            or state.runtime_config_id != self.config.runtime_config_id
            or state.assembly_config_id != self.config.assembly_config_id):
            raise ValueError("v2.2 direct assembly requires its compact state/config")
        derived = derive_canonical_time_v2(
            state, source_article, diagnostic_sink=policy.diagnostic_sink,
        )
        derived = replace(
            derived, lane_statuses={**derived.lane_statuses,
                                    "graph_assembly": "EXECUTED"},
        )
        result = self._materialize(derived, source_article)
        validation = self.validate(result, source_article)
        result = replace(result, validation=validation)
        policy.diagnostic_sink.record("stage", {
            "stage": "⑧ 그래프 조립부",
            "component": "Compact direct PUBLIC assembly",
            "input_count": len(state.identities),
            "candidate_count": 0,
            "output_count": {
                "nodes": len(result.nodes), "edges": len(result.edges),
            },
            "drop_reason_counts": {
                "UNRESOLVED_FACT": derived.unresolved_fact_count,
            },
            "warnings": tuple(derived.lane_reasons or {}),
            "elapsed_seconds": time.perf_counter() - started,
        })
        result = self.output_projector.project(
            result, policy=policy,
        )
        capture = policy.diagnostic_sink.summary()
        return CompactAssemblyOutcome(
            result, derived,
            tuple(policy.diagnostic_sink.records)
            if policy.capture_level.value != "SUMMARY" else (),
            capture["artifact_path"],
        )

    def _materialize(self, state: ResolvedGraphState,
                     article: ArticleInput) -> CompactKnowledgeGraphResult:
        public_ids = {
            row.identity_id: _stable_id(
                row.kind, state.article_id, state.article_version_id, row.identity_id,
            ) for row in state.identities
        }
        nodes = []
        for identity in state.identities:
            node_id = public_ids[identity.identity_id]
            evidence = []
            if identity.representative is not None:
                evidence.append(_evidence(node_id, identity.representative,
                                          "REPRESENTATIVE", state, article))
            for ref in identity.evidence:
                purpose = "TRIGGER" if identity.kind == "EVENT" else (
                    "TIME_OCCURRENCE" if identity.kind == "TIME" else "SEMANTIC_SUPPORT"
                )
                if ref != identity.representative:
                    evidence.append(_evidence(node_id, ref, purpose, state, article))
            nodes.append(CompactGraphNode(
                node_id, identity.kind, dict(identity.semantic_properties),
                _dedup_evidence(evidence), {
                    "identity_confidence_source": identity.semantic_properties.get(
                        "identity_confidence_source"
                    ),
                    "independent_support_count": identity.semantic_properties.get(
                        "independent_support_count"
                    ),
                },
            ))
        edges = []
        for fact in state.facts:
            source, target = public_ids[fact.source_identity_id], public_ids[fact.target_identity_id]
            edge_id = _stable_id("EDGE", state.article_id, state.article_version_id,
                                 fact.relation, source, target)
            edges.append(CompactGraphEdge(
                edge_id, fact.relation, source, target, fact.confidence,
                fact.status,
                _dedup_evidence(
                    _evidence(edge_id, ref, fact.relation, state, article)
                    for ref in fact.supports
                ), {
                    "fact_status": fact.status,
                    "confidence_source": (
                        "LEARNED_RELATION_SCORE" if fact.relation in
                        ("ACTOR", "TARGET", "PLACE", "OCCURRED_ON")
                        else "DETERMINISTIC_ARTICLE_STRUCTURE"
                    ),
                },
            ))
        status = "PARTIAL" if (
            state.unresolved_fact_count
            or state.lane_reasons
            or any(value in ("UNRESOLVED", "ERROR")
                   for value in state.lane_statuses.values())
        ) else "READY"
        return CompactKnowledgeGraphResult(
            PUBLIC_SCHEMA_VERSION, "2.2", COMPACT_RUNTIME_CONTRACT_ID,
            OUTPUT_PROFILE_CONTRACT_ID, OutputProfile.PUBLIC.value,
            state.assembly_config_id, state.runtime_config_id, status,
            {
                "article_id": state.article_id,
                "article_version_id": state.article_version_id,
                "content_sha256": state.content_sha256,
                "published_at": state.published_at,
                "title": state.title, "source": state.source,
            },
            tuple(sorted(nodes, key=lambda row: (NODE_KINDS.index(row.kind), row.node_id))),
            tuple(sorted(edges, key=lambda row: (EDGE_TYPES.index(row.edge_type), row.edge_id))),
            {"lane_statuses": dict(state.lane_statuses),
             "unresolved_fact_count": state.unresolved_fact_count,
             "lane_reasons": dict(state.lane_reasons or {})},
            {
                "active_policy_ids": state.active_policy_ids,
                "component_checkpoint_sha256": dict(state.component_provenance or {}),
                "article_version_id": state.article_version_id,
                "content_sha256": state.content_sha256,
                "identity_scope": "ARTICLE_LOCAL_ONLY",
                "runtime_config_sha256": state.runtime_config_sha256,
                "assembly_config_sha256": state.assembly_config_sha256,
                "public_schema_sha256": state.public_schema_sha256,
                "policy_config_sha256": dict(state.policy_config_sha256 or {}),
            },
            {},
        )

    @staticmethod
    def validate(result: CompactKnowledgeGraphResult,
                 article: ArticleInput) -> Mapping[str, Any]:
        """직접 node/edge를 검사한다; full result.to_dict()를 만들지 않는다."""
        if (result.schema_version != PUBLIC_SCHEMA_VERSION
            or result.article["article_version_id"] != article.article_version_id
            or result.article["content_sha256"]
            != ResolvedGraphState.content_digest(article.content)):
            raise ValueError("v2.2 PUBLIC source/schema mismatch")
        node_by_id = {row.node_id: row for row in result.nodes}
        if len(node_by_id) != len(result.nodes):
            raise ValueError("duplicate v2.2 PUBLIC node")
        if sum(row.kind == "ARTICLE" for row in result.nodes) != 1:
            raise ValueError("v2.2 PUBLIC requires one ARTICLE")
        if len({row.edge_id for row in result.edges}) != len(result.edges):
            raise ValueError("duplicate v2.2 PUBLIC edge")
        for node in result.nodes:
            if node.kind not in NODE_KINDS:
                raise ValueError("internal node entered v2.2 PUBLIC")
            for ref in node.evidence:
                if (ref.owner_id != node.node_id
                    or ref.article_version_id != article.article_version_id
                    or article.content[ref.char_start:ref.char_end] != ref.text):
                    raise ValueError("v2.2 node grounding/owner differs")
        for edge in result.edges:
            if (edge.edge_type not in EDGE_ENDPOINTS
                or edge.source_id not in node_by_id
                or edge.target_id not in node_by_id
                or (node_by_id[edge.source_id].kind,
                    node_by_id[edge.target_id].kind) != EDGE_ENDPOINTS[edge.edge_type]):
                raise ValueError("v2.2 PUBLIC dangling/invalid relation endpoint")
            for ref in edge.evidence:
                if (ref.owner_id != edge.edge_id
                    or ref.article_version_id != article.article_version_id
                    or article.content[ref.char_start:ref.char_end] != ref.text):
                    raise ValueError("v2.2 edge grounding/owner differs")
        return {
            "status": "PASS", "node_count": len(result.nodes),
            "edge_count": len(result.edges), "dangling_edge_count": 0,
            "invalid_endpoint_count": 0, "source_grounding_roundtrip": "PASS",
        }
