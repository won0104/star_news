"""Canonical ⑧ graph assembly from ``ArticleLocalRuntimeResult`` only."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from runtime.eventframe.contracts import ArticleLocalRuntimeResult
from runtime.temporal_identity import normalized_temporal_key

from .contracts import (
    GRAPH_SCHEMA_VERSION,
    ArticleLocalKnowledgeGraphResult,
    CanonicalGraphEdge,
    CanonicalGraphNode,
    GraphEvidence,
)


INPUT_SCHEMA_VERSION = "articlelocal-eventframe-runtime-result-v1"
ASSEMBLY_CONFIG_SCHEMA_VERSION = "articlelocal-kg-assembly-config-v1"


@dataclass(frozen=True, slots=True)
class AssemblyConfig:
    path: Path
    payload: Mapping[str, Any]

    @property
    def assembly_config_id(self) -> str:
        return str(self.payload["assembly_config_id"])

    @property
    def runtime_config_id(self) -> str:
        return str(self.payload["source_runtime_config_id"])


def load_assembly_config(path: str | Path) -> AssemblyConfig:
    config_path = Path(path).resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != ASSEMBLY_CONFIG_SCHEMA_VERSION:
        raise ValueError("unsupported graph assembly config schema")
    if payload.get("input_schema_version") != INPUT_SCHEMA_VERSION:
        raise ValueError("graph assembly requires the canonical EventFrame runtime contract")
    if payload.get("output_schema_version") != GRAPH_SCHEMA_VERSION:
        raise ValueError("graph assembly output schema does not match implementation")
    if payload.get("materialized_node_kinds") != [
        "ARTICLE",
        "EVENT",
        "LOCAL_EVENT",
        "STATEMENT",
        "TIME",
        "LOCAL_ENTITY",
    ]:
        raise ValueError("graph assembly materialized node contract mismatch")
    if payload.get("materialized_edge_types") != [
        "COVERS",
        "MEMBER_OF_EVENT",
        "CONTAINS_STATEMENT",
        "OCCURRED_ON",
        "MENTIONS",
        "ACTOR",
        "TARGET",
        "PLACE",
    ]:
        raise ValueError("graph assembly materialized edge contract mismatch")
    if payload.get("fake_entity_fallback") is not False:
        raise ValueError("fake Entity fallback must remain disabled")
    if payload.get("entity_candidate_hard_deletion_authorized") is not False:
        raise ValueError("Entity candidate priority must never delete raw evidence")
    if payload.get("entity_candidate_hard_identity_eligibility_gate_authorized") is not False:
        raise ValueError("soft priority must not become a hard identity eligibility gate")
    return AssemblyConfig(config_path, payload)


class ArticleLocalKGAssembler:
    """Build a partial KG without inferring facts absent from canonical runtime output."""

    def __init__(self, config: AssemblyConfig) -> None:
        self.config = config

    @classmethod
    def from_config(cls, path: str | Path) -> "ArticleLocalKGAssembler":
        return cls(load_assembly_config(path))

    def assemble(
        self,
        runtime_result: ArticleLocalRuntimeResult | Mapping[str, Any],
    ) -> ArticleLocalKnowledgeGraphResult:
        # Only the public JSON contract is consumed; no experiment/model internals cross ⑧.
        payload = (
            runtime_result.to_dict()
            if isinstance(runtime_result, ArticleLocalRuntimeResult)
            else json.loads(json.dumps(runtime_result, ensure_ascii=False, allow_nan=False))
        )
        self._validate_input(payload)
        source_coverage = deepcopy(payload.get("coverage", {}))
        source_coverage.pop("timing_seconds", None)
        source_runtime_trace = tuple(
            {
                key: value
                for key, value in row.items()
                if key != "elapsed_seconds" and not key.endswith("_seconds")
            }
            for row in deepcopy(payload.get("trace", []))
        )
        article = deepcopy(payload["article"])
        content = str(article["content"])
        article_id = str(article["article_id"])
        article_node_id = _stable_id(
            "ART",
            article_id,
            str(article.get("article_version_id", "")),
        )

        nodes: list[CanonicalGraphNode] = [
            CanonicalGraphNode(
                node_id=article_node_id,
                kind="ARTICLE",
                properties={
                    "article_id": article_id,
                    "article_version_id": article.get("article_version_id"),
                    "title": article.get("title"),
                    "published_at": article.get("published_at"),
                    "source": article.get("source"),
                },
                evidence=(),
                provenance={
                    "source": "CANONICAL_ARTICLE_INPUT",
                    "runtime_config_id": payload["runtime_config_id"],
                    "assembly_config_id": self.config.assembly_config_id,
                },
            )
        ]
        edges: list[CanonicalGraphEdge] = []
        raw_fillers: list[dict[str, Any]] = []
        raw_entity_mentions = deepcopy(payload["entity_mentions"]["items"])
        entity_priority_lane = deepcopy(
            payload.get(
                "entity_candidate_priorities",
                {
                    "status": "NOT_RUN",
                    "items": [],
                    "reason": "Entity candidate soft priority is absent from this runtime result.",
                },
            )
        )
        entity_candidate_priorities = deepcopy(entity_priority_lane["items"])
        local_entity_lane = deepcopy(
            payload.get("local_entities", {"status": "NOT_RUN", "items": []})
        )
        participant_resolution_lane = deepcopy(
            payload.get(
                "participant_entity_resolutions",
                {"status": "NOT_RUN", "items": []},
            )
        )
        local_event_lane = deepcopy(
            payload.get("local_events", {"status": "NOT_RUN", "items": []})
        )
        event_coreference_lane = deepcopy(
            payload.get("event_coreference", {"status": "NOT_RUN", "items": []})
        )
        raw_local_entities = deepcopy(local_entity_lane["items"])
        participant_resolutions = deepcopy(participant_resolution_lane["items"])
        raw_time_expressions = deepcopy(payload["time_expressions"]["items"])
        for mention in raw_entity_mentions:
            _validate_evidence_mapping(
                {
                    "article_id": article_id,
                    "char_start": mention["char_start"],
                    "char_end": mention["char_end"],
                    "text": mention["text"],
                    "sentence_index": mention["sentence_index"],
                },
                article_id,
                content,
            )
        if entity_priority_lane["status"] == "EXECUTED":
            raw_prediction_ids = {
                mention["prediction_id"] for mention in raw_entity_mentions
            }
            priority_prediction_ids = [
                row["entity_prediction_id"] for row in entity_candidate_priorities
            ]
            if len(priority_prediction_ids) != len(set(priority_prediction_ids)):
                raise ValueError("duplicate Entity soft-priority decision")
            if set(priority_prediction_ids) != raw_prediction_ids:
                raise ValueError(
                    "Entity soft-priority decisions must preserve and cover all raw evidence"
                )
        raw_entity_by_id = {
            mention["prediction_id"]: mention for mention in raw_entity_mentions
        }
        local_entity_ids = set()
        mention_to_local = {}
        for local_entity in raw_local_entities:
            local_entity_id = str(local_entity["local_entity_id"])
            if local_entity_id in local_entity_ids:
                raise ValueError("duplicate LocalEntity identity")
            local_entity_ids.add(local_entity_id)
            members = [
                raw_entity_by_id.get(prediction_id)
                for prediction_id in local_entity["member_entity_prediction_ids"]
            ]
            if any(member is None for member in members):
                raise ValueError("LocalEntity references absent raw EntityMention")
            evidence = tuple(_evidence(article_id, member) for member in members)
            nodes.append(
                CanonicalGraphNode(
                    node_id=local_entity_id,
                    kind="LOCAL_ENTITY",
                    properties={
                        "entity_type": local_entity["entity_type"],
                        "canonical_name": local_entity["canonical_name"],
                        "representative_entity_prediction_id": local_entity[
                            "representative_entity_prediction_id"
                        ],
                        "member_entity_prediction_ids": tuple(
                            local_entity["member_entity_prediction_ids"]
                        ),
                        "materialization_source": local_entity[
                            "materialization_source"
                        ],
                    },
                    evidence=evidence,
                    provenance={
                        "source": "PREDICTED_ARTICLE_LOCAL_ENTITY_IDENTITY",
                        "coreference_checkpoint_sha": local_entity[
                            "coreference_checkpoint_sha"
                        ],
                        "runtime_config_id": payload["runtime_config_id"],
                        "assembly_config_id": self.config.assembly_config_id,
                        "responsibility": "⑥ 동일성 판정부",
                    },
                )
            )
            edges.append(
                CanonicalGraphEdge(
                    edge_id=_stable_id(
                        "GEDGE",
                        self.config.assembly_config_id,
                        "MENTIONS",
                        article_node_id,
                        local_entity_id,
                    ),
                    edge_type="MENTIONS",
                    source_id=article_node_id,
                    target_id=local_entity_id,
                    confidence=float(local_entity["confidence"]),
                    evidence=evidence,
                    provenance={
                        "source": "PREDICTED_ARTICLE_LOCAL_ENTITY_IDENTITY",
                        "runtime_config_id": payload["runtime_config_id"],
                        "assembly_config_id": self.config.assembly_config_id,
                    },
                )
            )
            for prediction_id in local_entity["member_entity_prediction_ids"]:
                if prediction_id in mention_to_local:
                    raise ValueError("EntityMention belongs to multiple LocalEntities")
                mention_to_local[prediction_id] = local_entity_id
        resolution_by_evidence_id = {
            row["participant_evidence_id"]: row
            for row in participant_resolutions
        }
        if len(resolution_by_evidence_id) != len(participant_resolutions):
            raise ValueError("duplicate Participant resolution identity")
        for temporal in raw_time_expressions:
            _validate_evidence_mapping(
                {
                    "article_id": article_id,
                    "char_start": temporal["char_start"],
                    "char_end": temporal["char_end"],
                    "text": temporal["text"],
                    "sentence_index": temporal["sentence_index"],
                },
                article_id,
                content,
            )
        eventframes = deepcopy(payload["events"])
        event_prediction_to_frame: dict[str, str] = {}
        event_time_attachments: list[dict[str, Any]] = []

        for eventframe in eventframes:
            eventframe_id = str(eventframe["eventframe_id"])
            proposition = eventframe["event"]
            event_prediction_to_frame[str(proposition["prediction_id"])] = eventframe_id
            event_time_attachments.extend(deepcopy(eventframe["time"]["items"]))
            evidence = _evidence(article_id, proposition)
            evidence.validate(content)
            nodes.append(
                CanonicalGraphNode(
                    node_id=eventframe_id,
                    kind="EVENT",
                    properties={
                        "source_eventframe_id": eventframe_id,
                        "source_prediction_id": proposition["prediction_id"],
                        "sentence_index": proposition["sentence_index"],
                        "char_start": proposition["char_start"],
                        "char_end": proposition["char_end"],
                        "text": proposition["text"],
                        "boundary_score": proposition["boundary_score"],
                        "verifier_score": proposition["verifier_score"],
                        "acceptance_score": proposition["acceptance_score"],
                        "trigger_status": eventframe["trigger"]["status"],
                        "trigger": deepcopy(eventframe["trigger"].get("item")),
                        "time_status": eventframe["time"]["status"],
                        "resolution_status": eventframe["resolution"]["status"],
                        "relations_status": eventframe["relations"]["status"],
                    },
                    evidence=(evidence,),
                    provenance=deepcopy(eventframe["provenance"]),
                )
            )
            edges.append(
                CanonicalGraphEdge(
                    edge_id=_stable_id(
                        "GEDGE",
                        self.config.assembly_config_id,
                        "COVERS",
                        article_node_id,
                        eventframe_id,
                    ),
                    edge_type="COVERS",
                    source_id=article_node_id,
                    target_id=eventframe_id,
                    confidence=float(proposition["acceptance_score"]),
                    evidence=(evidence,),
                    provenance={
                        "source": "CANONICAL_RUNTIME_EVENTFRAME",
                        "source_eventframe_id": eventframe_id,
                        "source_prediction_id": proposition["prediction_id"],
                        "runtime_config_id": payload["runtime_config_id"],
                        "assembly_config_id": self.config.assembly_config_id,
                    },
                )
            )
            for role in ("ACTOR", "TARGET", "PLACE"):
                lane = eventframe["participants"][role]
                for ordinal, filler in enumerate(lane["items"]):
                    filler_copy = deepcopy(filler)
                    filler_evidence = _evidence(
                        article_id,
                        filler_copy,
                        sentence_index=int(proposition["sentence_index"]),
                    )
                    filler_evidence.validate(content)
                    evidence_id = _stable_id(
                        "RAW",
                        eventframe_id,
                        role,
                        str(filler_copy["char_start"]),
                        str(filler_copy["char_end"]),
                        str(ordinal),
                    )
                    resolution = resolution_by_evidence_id.get(evidence_id)
                    raw_fillers.append(
                        {
                            "evidence_id": evidence_id,
                            "source_eventframe_id": eventframe_id,
                            "source_event_prediction_id": proposition["prediction_id"],
                            "sentence_index": proposition["sentence_index"],
                            "role": role,
                            "filler": filler_copy,
                            "materialization_status": "UNMATERIALIZED",
                            "reason": (
                                "DERIVED_ENTITY_RESOLUTION_AVAILABLE"
                                if resolution is not None
                                and resolution["resolution_status"] == "ENTITY_RESOLVED"
                                else "ENTITY_RESOLUTION_UNRESOLVED"
                            ),
                            "semantic_interpretation": (
                                "raw semantic participant evidence; not an Entity prerequisite"
                            ),
                        }
                    )
                    if (
                        resolution is not None
                        and resolution["resolution_status"] == "ENTITY_RESOLVED"
                    ):
                        target_id = resolution["target_local_entity_id"]
                        if target_id not in local_entity_ids:
                            raise ValueError(
                                "Participant resolution references absent LocalEntity"
                            )
                        edges.append(
                            CanonicalGraphEdge(
                                edge_id=_stable_id(
                                    "GEDGE",
                                    self.config.assembly_config_id,
                                    role,
                                    eventframe_id,
                                    target_id,
                                    evidence_id,
                                ),
                                edge_type=role,
                                source_id=eventframe_id,
                                target_id=target_id,
                                confidence=float(resolution["resolution_score"]),
                                evidence=(filler_evidence,),
                                provenance={
                                    "source": "PREDICTED_PARTICIPANT_ENTITY_RESOLUTION",
                                    "participant_evidence_id": evidence_id,
                                    "target_entity_prediction_id": resolution[
                                        "target_entity_prediction_id"
                                    ],
                                    "checkpoint_sha": resolution["checkpoint_sha"],
                                    "runtime_config_id": payload["runtime_config_id"],
                                    "assembly_config_id": self.config.assembly_config_id,
                                    "responsibility": "⑥ 동일성 판정부",
                                },
                            )
                        )

        eventframe_by_id = {
            str(row["eventframe_id"]): row for row in eventframes
        }
        for local_event in local_event_lane["items"]:
            local_event_id = str(local_event["local_event_id"])
            member_ids = tuple(local_event["member_eventframe_ids"])
            members = [eventframe_by_id.get(str(member_id)) for member_id in member_ids]
            if not members or any(member is None for member in members):
                raise ValueError("LocalEvent references absent raw EventFrame evidence")
            evidence = tuple(_evidence(article_id, member["event"]) for member in members)
            for item in evidence:
                item.validate(content)
            nodes.append(
                CanonicalGraphNode(
                    node_id=local_event_id,
                    kind="LOCAL_EVENT",
                    properties={
                        "canonical_text": local_event["canonical_text"],
                        "representative_event_prediction_id": local_event[
                            "representative_event_prediction_id"
                        ],
                        "member_event_prediction_ids": tuple(
                            local_event["member_event_prediction_ids"]
                        ),
                        "member_eventframe_ids": member_ids,
                        "cluster_size": int(local_event["cluster_size"]),
                        "confidence": float(local_event["confidence"]),
                        "article_local": True,
                    },
                    evidence=evidence,
                    provenance={
                        "source": "PREDICTED_ARTICLE_LOCAL_EVENT_IDENTITY",
                        "coreference_checkpoint_sha": local_event["checkpoint_sha"],
                        "runtime_config_id": payload["runtime_config_id"],
                        "assembly_config_id": self.config.assembly_config_id,
                        "responsibility": "⑥ 동일성 판정부",
                    },
                )
            )
            for member in members:
                proposition = member["event"]
                member_evidence = _evidence(article_id, proposition)
                edges.append(
                    CanonicalGraphEdge(
                        edge_id=_stable_id(
                            "GEDGE",
                            self.config.assembly_config_id,
                            "MEMBER_OF_EVENT",
                            member["eventframe_id"],
                            local_event_id,
                        ),
                        edge_type="MEMBER_OF_EVENT",
                        source_id=member["eventframe_id"],
                        target_id=local_event_id,
                        confidence=float(local_event["confidence"]),
                        evidence=(member_evidence,),
                        provenance={
                            "source": "PREDICTED_ARTICLE_LOCAL_EVENT_IDENTITY",
                            "source_event_prediction_id": proposition["prediction_id"],
                            "checkpoint_sha": local_event["checkpoint_sha"],
                            "runtime_config_id": payload["runtime_config_id"],
                            "assembly_config_id": self.config.assembly_config_id,
                            "raw_eventframe_preserved": True,
                        },
                    )
                )

        time_by_prediction = {
            str(row["prediction_id"]): row for row in raw_time_expressions
        }
        attached_time_ids = {
            str(row["target_time_prediction_id"]) for row in event_time_attachments
        }
        materializable = defaultdict(list)
        for prediction_id in sorted(attached_time_ids):
            temporal = time_by_prediction.get(prediction_id)
            if temporal is None:
                raise ValueError("Event-Time attachment references absent raw evidence")
            normalization = temporal.get("normalization", {})
            if normalization.get("status") != "NORMALIZED" or not normalization.get("value"):
                continue
            key = normalized_temporal_key(
                normalization,
                semantic_type=str(temporal.get("temporal_semantic_type", "POINT")),
            )
            if key is None:
                continue  # 유효 unresolved/DURATION/SET 근거를 fake TIME으로 만들지 않는다.
            materializable[key].append(temporal)

        time_node_by_prediction: dict[str, str] = {}
        for temporal_key, expressions in sorted(
            materializable.items(), key=lambda item: item[0].parts(),
        ):
            time_node_id = _stable_id(
                "TIME", article_id, *temporal_key.parts()
            )
            evidence = tuple(_evidence(article_id, row) for row in expressions)
            for item in evidence:
                item.validate(content)
            source_prediction_ids = tuple(
                sorted(str(row["prediction_id"]) for row in expressions)
            )
            for prediction_id in source_prediction_ids:
                time_node_by_prediction[prediction_id] = time_node_id
            nodes.append(
                CanonicalGraphNode(
                    node_id=time_node_id,
                    kind="TIME",
                    properties={
                        "normalized_value": temporal_key.value,
                        "granularity": temporal_key.granularity,
                        "temporal_semantic_type": temporal_key.semantic_type,
                        "timezone": temporal_key.timezone,
                        "normalization_status": "NORMALIZED",
                        "source_time_prediction_ids": source_prediction_ids,
                    },
                    evidence=evidence,
                    provenance={
                        "source": "DETERMINISTIC_TIME_NORMALIZATION",
                        "runtime_config_id": payload["runtime_config_id"],
                        "assembly_config_id": self.config.assembly_config_id,
                        "responsibility": "⑧ 그래프 조립부",
                    },
                )
            )

        time_edge_support: dict[tuple[str, str], list[tuple[Mapping[str, Any], GraphEvidence]]] = defaultdict(list)
        for attachment in event_time_attachments:
            source_prediction_id = str(attachment["source_event_prediction_id"])
            target_prediction_id = str(attachment["target_time_prediction_id"])
            source_id = event_prediction_to_frame.get(source_prediction_id)
            target_id = time_node_by_prediction.get(target_prediction_id)
            if source_id is None:
                raise ValueError("Event-Time attachment references absent Event")
            if target_id is None:
                continue
            temporal = time_by_prediction[target_prediction_id]
            evidence = _evidence(article_id, temporal)
            evidence.validate(content)
            key = (source_id, target_id)
            time_edge_support[key].append((attachment, evidence))
        for (source_id, target_id), supports in sorted(time_edge_support.items()):
            best_attachment, _ = min(
                supports,
                key=lambda item: (-float(item[0]["score"]), str(item[0]["attachment_id"])),
            )
            unique_by_occurrence = {
                str(attachment["target_time_prediction_id"]): evidence
                for attachment, evidence in supports
            }
            occurrence_ids = tuple(sorted(unique_by_occurrence))
            edge = CanonicalGraphEdge(
                edge_id=_stable_id(
                    "GEDGE",
                    self.config.assembly_config_id,
                    "OCCURRED_ON",
                    source_id,
                    target_id,
                ),
                edge_type="OCCURRED_ON",
                source_id=source_id,
                target_id=target_id,
                confidence=float(best_attachment["score"]),
                evidence=tuple(unique_by_occurrence[prediction_id] for prediction_id in occurrence_ids),
                provenance={
                    "source": "PREDICTED_EVENT_TIME_ATTACHMENT_PLUS_NORMALIZATION",
                    "source_attachment_id": best_attachment["attachment_id"],
                    "source_attachment_ids": tuple(sorted(str(row["attachment_id"]) for row, _ in supports)),
                    "source_time_prediction_id": best_attachment["target_time_prediction_id"],
                    "source_time_prediction_ids": occurrence_ids,
                    "runtime_config_id": payload["runtime_config_id"],
                    "assembly_config_id": self.config.assembly_config_id,
                    "responsibility": "⑤ 방향 관계 판정부 + ⑧ 그래프 조립부",
                },
            )
            edges.append(edge)

        statements = deepcopy(payload["statements"])
        for statement in statements:
            proposition = statement["proposition"]
            statement_id = str(statement["statement_id"])
            evidence = _evidence(article_id, proposition)
            evidence.validate(content)
            nodes.append(
                CanonicalGraphNode(
                    node_id=statement_id,
                    kind="STATEMENT",
                    properties={
                        "source_prediction_id": proposition["prediction_id"],
                        "sentence_index": proposition["sentence_index"],
                        "char_start": proposition["char_start"],
                        "char_end": proposition["char_end"],
                        "text": proposition["text"],
                        "boundary_score": proposition["boundary_score"],
                        "verifier_score": proposition["verifier_score"],
                        "acceptance_score": proposition["acceptance_score"],
                        "statement_type_status": statement["statement_type"]["status"],
                        "statement_type": statement["statement_type"].get("value"),
                        "statement_type_score": statement["statement_type"].get("score"),
                        "assertor_status": statement["assertor"]["status"],
                        "about_status": statement["about"]["status"],
                    },
                    evidence=(evidence,),
                    provenance=deepcopy(statement["provenance"]),
                )
            )
            edges.append(
                CanonicalGraphEdge(
                    edge_id=_stable_id(
                        "GEDGE",
                        self.config.assembly_config_id,
                        "CONTAINS_STATEMENT",
                        article_node_id,
                        statement_id,
                    ),
                    edge_type="CONTAINS_STATEMENT",
                    source_id=article_node_id,
                    target_id=statement_id,
                    confidence=float(proposition["acceptance_score"]),
                    evidence=(evidence,),
                    provenance={
                        "source": "CANONICAL_RUNTIME_STATEMENT",
                        "source_statement_id": statement_id,
                        "source_prediction_id": proposition["prediction_id"],
                        "runtime_config_id": payload["runtime_config_id"],
                        "assembly_config_id": self.config.assembly_config_id,
                    },
                )
            )

        source_statuses = {
            "entity_mentions": payload["entity_mentions"]["status"],
            "entity_candidate_priorities": entity_priority_lane["status"],
            "local_entities": local_entity_lane["status"],
            "participant_entity_resolutions": participant_resolution_lane["status"],
            "local_events": local_event_lane["status"],
            "event_coreference": event_coreference_lane["status"],
            "time_expressions": payload["time_expressions"]["status"],
            "resolution": payload["resolution"]["status"],
            "relations": payload["relations"]["status"],
            "trigger": _uniform_status(eventframes, "trigger"),
            "event_time": _uniform_status(eventframes, "time"),
            "event_relations": _uniform_status(eventframes, "relations"),
            "event_resolution": _uniform_status(eventframes, "resolution"),
            "statement_type": _uniform_status(statements, "statement_type"),
            "assertor": _uniform_status(statements, "assertor"),
            "about": _uniform_status(statements, "about"),
        }
        result = ArticleLocalKnowledgeGraphResult(
            schema_version=GRAPH_SCHEMA_VERSION,
            assembly_config_id=self.config.assembly_config_id,
            runtime_config_id=str(payload["runtime_config_id"]),
            status="PARTIAL_KG_ASSEMBLY_READY",
            article=article,
            nodes=tuple(nodes),
            edges=tuple(edges),
            sentences=tuple(deepcopy(payload.get("sentences", []))),
            eventframes=tuple(eventframes),
            statements=tuple(statements),
            unmaterialized_evidence={
                "status": "EXECUTED"
                if raw_fillers or raw_entity_mentions or raw_time_expressions
                else "EMPTY",
                "participant_fillers": tuple(raw_fillers),
                "entity_mentions": tuple(raw_entity_mentions),
                "entity_candidate_priorities": tuple(entity_candidate_priorities),
                "local_entities": tuple(raw_local_entities),
                "participant_entity_resolutions": tuple(participant_resolutions),
                "local_events": tuple(local_event_lane["items"]),
                "event_coreference": tuple(event_coreference_lane["items"]),
                "time_expressions": tuple(raw_time_expressions),
                "event_time_attachments": tuple(event_time_attachments),
                "time_materialization": {
                    "status": "EXECUTED" if materializable else "EMPTY",
                    "materialized_time_node_count": len(materializable),
                    "occurred_on_count": sum(
                        edge.edge_type == "OCCURRED_ON" for edge in edges
                    ),
                    "unresolved_or_unattached_evidence_count": len(raw_time_expressions)
                    - len(time_node_by_prediction),
                    "policy": "requires predicted Event→TimeExpression attachment and materializable normalization",
                    "fake_time_fallback": False,
                },
                "entity_candidate_priority_policy": {
                    "status": entity_priority_lane["status"],
                    "hard_deletion_authorized": False,
                    "hard_identity_eligibility_gate_authorized": False,
                    "raw_entity_evidence_preserved": True,
                    "tier2_rescue_policy": "COREFERENCE_WITH_TIER1_OR_HIGH_CONFIDENCE_PARTICIPANT_TARGET",
                },
                "entity_materialization": {
                    "status": local_entity_lane["status"],
                    "materialized_local_entity_count": len(raw_local_entities),
                    "unmaterialized_raw_entity_mention_count": len(raw_entity_mentions)
                    - len(mention_to_local),
                    "policy": "TIER1-primary complete-link clusters plus bounded TIER2 rescue",
                },
                "canonical_role_edges": {
                    "status": participant_resolution_lane["status"],
                    "materialized_role_edge_count": sum(
                        edge.edge_type in {"ACTOR", "TARGET", "PLACE"}
                        for edge in edges
                    ),
                    "raw_fillers_preserved": True,
                },
                "event_identity_materialization": {
                    "status": local_event_lane["status"],
                    "materialized_local_event_count": len(local_event_lane["items"]),
                    "member_edge_count": sum(
                        edge.edge_type == "MEMBER_OF_EVENT" for edge in edges
                    ),
                    "raw_eventframe_preserved": True,
                    "policy": "article-local complete-link identity with immutable member evidence",
                },
            },
            lane_statuses={
                "source_runtime": source_statuses,
                "graph_assembly": {
                    "status": "EXECUTED",
                    "materialized_node_kinds": (
                        "ARTICLE", "EVENT", "LOCAL_EVENT", "STATEMENT", "TIME", "LOCAL_ENTITY"
                    ),
                    "materialized_edge_types": (
                        "COVERS",
                        "MEMBER_OF_EVENT",
                        "CONTAINS_STATEMENT",
                        "OCCURRED_ON",
                        "MENTIONS",
                        "ACTOR",
                        "TARGET",
                        "PLACE",
                    ),
                },
            },
            source_lanes={
                "coverage": source_coverage,
                "entity_mentions": deepcopy(payload["entity_mentions"]),
                "entity_candidate_priorities": entity_priority_lane,
                "local_entities": local_entity_lane,
                "participant_entity_resolutions": participant_resolution_lane,
                "local_events": local_event_lane,
                "event_coreference": event_coreference_lane,
                "time_expressions": deepcopy(payload["time_expressions"]),
                "resolution": deepcopy(payload["resolution"]),
                "relations": deepcopy(payload["relations"]),
            },
            provenance={
                "source": "ArticleLocalRuntimeResult",
                "source_schema_version": payload["schema_version"],
                "source_runtime_config_id": payload["runtime_config_id"],
                "assembly_config_id": self.config.assembly_config_id,
                "information_preserving_partial_graph": True,
                "volatile_runtime_timing_excluded_from_canonical_serialization": True,
            },
            source_runtime_trace=source_runtime_trace,
            trace=(
                {
                    "stage": "⑧ 그래프 조립부",
                    "component": "ArticleLocalKGAssembler",
                    "input_count": {
                        "events": len(eventframes),
                        "statements": len(statements),
                        "raw_participant_fillers": len(raw_fillers),
                        "raw_entity_mentions": len(raw_entity_mentions),
                        "entity_candidate_priorities": len(entity_candidate_priorities),
                        "local_entities": len(raw_local_entities),
                        "participant_entity_resolutions": len(participant_resolutions),
                        "raw_time_expressions": len(raw_time_expressions),
                        "event_time_attachments": len(event_time_attachments),
                        "local_events": len(local_event_lane["items"]),
                        "event_coreference_pairs": len(event_coreference_lane["items"]),
                    },
                    "output_count": {
                        "nodes": len(nodes),
                        "edges": len(edges),
                        "time_nodes": len(materializable),
                        "occurred_on": sum(
                            edge.edge_type == "OCCURRED_ON" for edge in edges
                        ),
                        "local_entities": len(raw_local_entities),
                        "local_events": len(local_event_lane["items"]),
                        "event_memberships": sum(
                            edge.edge_type == "MEMBER_OF_EVENT" for edge in edges
                        ),
                        "role_edges": sum(
                            edge.edge_type in {"ACTOR", "TARGET", "PLACE"}
                            for edge in edges
                        ),
                    },
                    "materialization_policy": (
                        "Article/raw EventFrame/LocalEvent/Statement/LocalEntity plus attached normalized Time; member evidence remains raw"
                    ),
                },
            ),
            warnings=tuple(deepcopy(payload.get("warnings", []))),
            source_failures=tuple(deepcopy(payload.get("failures", []))),
        )
        validation = self.validate(result)
        return replace(result, validation=validation)

    def validate(self, result: ArticleLocalKnowledgeGraphResult) -> dict[str, Any]:
        payload = result.to_dict()
        content = str(payload["article"]["content"])
        nodes = payload["nodes"]
        edges = payload["edges"]
        node_ids = [node["node_id"] for node in nodes]
        edge_ids = [edge["edge_id"] for edge in edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate deterministic graph node ID")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate deterministic graph edge ID")
        node_by_id = {node["node_id"]: node for node in nodes}
        kind_counts = Counter(node["kind"] for node in nodes)
        if kind_counts["ARTICLE"] != 1:
            raise ValueError("graph requires exactly one ARTICLE node")
        if set(kind_counts) - {
            "ARTICLE", "EVENT", "LOCAL_EVENT", "STATEMENT", "TIME", "LOCAL_ENTITY"
        }:
            raise ValueError("unsupported/fake graph node kind was materialized")
        if kind_counts["EVENT"] != len(payload["eventframes"]):
            raise ValueError("Event node count differs from canonical EventFrame count")
        eventframe_ids = {row["eventframe_id"] for row in payload["eventframes"]}
        event_node_ids = {node["node_id"] for node in nodes if node["kind"] == "EVENT"}
        if eventframe_ids != event_node_ids:
            raise ValueError("EVENT node identity differs from canonical EventFrame identity")
        statement_count = len(payload["statements"])
        if kind_counts["STATEMENT"] != statement_count:
            raise ValueError("Statement node/edge count parity failed")
        statement_ids = {row["statement_id"] for row in payload["statements"]}
        statement_node_ids = {
            node["node_id"] for node in nodes if node["kind"] == "STATEMENT"
        }
        if statement_ids != statement_node_ids:
            raise ValueError("STATEMENT node identity differs from canonical carrier identity")
        if sum(edge["edge_type"] == "CONTAINS_STATEMENT" for edge in edges) != statement_count:
            raise ValueError("Statement carrier/edge count parity failed")
        for node in nodes:
            if not node["provenance"]:
                raise ValueError("canonical node lacks provenance")
            for evidence in node["evidence"]:
                _validate_evidence_mapping(evidence, payload["article"]["article_id"], content)
        for edge in edges:
            if edge["source_id"] not in node_by_id or edge["target_id"] not in node_by_id:
                raise ValueError("dangling graph edge endpoint")
            if not edge["provenance"]:
                raise ValueError("canonical edge lacks provenance")
            source_kind = node_by_id[edge["source_id"]]["kind"]
            target_kind = node_by_id[edge["target_id"]]["kind"]
            expected = {
                "COVERS": ("ARTICLE", "EVENT"),
                "MEMBER_OF_EVENT": ("EVENT", "LOCAL_EVENT"),
                "CONTAINS_STATEMENT": ("ARTICLE", "STATEMENT"),
                "OCCURRED_ON": ("EVENT", "TIME"),
                "MENTIONS": ("ARTICLE", "LOCAL_ENTITY"),
                "ACTOR": ("EVENT", "LOCAL_ENTITY"),
                "TARGET": ("EVENT", "LOCAL_ENTITY"),
                "PLACE": ("EVENT", "LOCAL_ENTITY"),
            }.get(edge["edge_type"])
            if expected is None or (source_kind, target_kind) != expected:
                raise ValueError("invalid canonical graph edge endpoint")
            for evidence in edge["evidence"]:
                _validate_evidence_mapping(evidence, payload["article"]["article_id"], content)
        covers_targets = [
            edge["target_id"] for edge in edges if edge["edge_type"] == "COVERS"
        ]
        statement_targets = [
            edge["target_id"]
            for edge in edges
            if edge["edge_type"] == "CONTAINS_STATEMENT"
        ]
        if len(covers_targets) != len(eventframe_ids) or set(covers_targets) != eventframe_ids:
            raise ValueError("COVERS does not map each canonical EventFrame exactly once")
        if len(statement_targets) != len(statement_ids) or set(statement_targets) != statement_ids:
            raise ValueError("CONTAINS_STATEMENT does not map each Statement exactly once")

        raw_local_events = payload["source_lanes"]["local_events"]["items"]
        local_event_node_ids = {
            node["node_id"] for node in nodes if node["kind"] == "LOCAL_EVENT"
        }
        expected_local_event_ids = {
            row["local_event_id"] for row in raw_local_events
        }
        if local_event_node_ids != expected_local_event_ids:
            raise ValueError("LOCAL_EVENT node identity differs from runtime identity")
        member_edges = [
            edge for edge in edges if edge["edge_type"] == "MEMBER_OF_EVENT"
        ]
        member_eventframes = [edge["source_id"] for edge in member_edges]
        if payload["source_lanes"]["local_events"]["status"] in {"EXECUTED", "EMPTY"}:
            if len(member_eventframes) != len(set(member_eventframes)):
                raise ValueError("EventFrame belongs to multiple LocalEvent nodes")
            if set(member_eventframes) != eventframe_ids:
                raise ValueError("LocalEvent membership must preserve every EventFrame")
        accepted_pairs = payload["source_lanes"]["event_coreference"]["items"]
        if any(
            row["left_local_event_id"] not in expected_local_event_ids
            or row["right_local_event_id"] not in expected_local_event_ids
            for row in accepted_pairs
        ):
            raise ValueError("Event coreference lane has a dangling LocalEvent reference")

        raw_times = payload["unmaterialized_evidence"]["time_expressions"]
        if raw_times != payload["source_lanes"]["time_expressions"]["items"]:
            raise ValueError("raw TimeExpression evidence changed during assembly")
        raw_entities = payload["unmaterialized_evidence"]["entity_mentions"]
        if raw_entities != payload["source_lanes"]["entity_mentions"]["items"]:
            raise ValueError("raw EntityMention evidence changed during assembly")
        raw_time_by_id = {row["prediction_id"]: row for row in raw_times}
        if len(raw_time_by_id) != len(raw_times):
            raise ValueError("duplicate raw TimeExpression prediction ID")
        event_prediction_to_frame = {
            row["event"]["prediction_id"]: row["eventframe_id"]
            for row in payload["eventframes"]
        }
        attachments = payload["unmaterialized_evidence"]["event_time_attachments"]
        attachment_ids = [row["attachment_id"] for row in attachments]
        if len(attachment_ids) != len(set(attachment_ids)):
            raise ValueError("duplicate Event-Time attachment")
        for attachment in attachments:
            if attachment["source_event_prediction_id"] not in event_prediction_to_frame:
                raise ValueError("Event-Time attachment has a dangling Event reference")
            if attachment["target_time_prediction_id"] not in raw_time_by_id:
                raise ValueError("Event-Time attachment has a dangling TimeExpression reference")
        materialized_prediction_ids = set()
        for node in nodes:
            if node["kind"] != "TIME":
                continue
            source_ids = tuple(node["properties"].get("source_time_prediction_ids", ()))
            if not source_ids:
                raise ValueError("canonical Time node lacks source TimeExpression evidence")
            for prediction_id in source_ids:
                temporal = raw_time_by_id.get(prediction_id)
                if temporal is None:
                    raise ValueError("canonical Time node references absent raw evidence")
                normalization = temporal.get("normalization", {})
                if normalization.get("status") != "NORMALIZED":
                    raise ValueError("unresolved TimeExpression became a canonical Time node")
                if normalization.get("value") != node["properties"]["normalized_value"]:
                    raise ValueError("canonical Time value differs from its evidence")
                materialized_prediction_ids.add(prediction_id)
        attached_time_ids = {
            row["target_time_prediction_id"] for row in attachments
        }
        if not materialized_prediction_ids.issubset(attached_time_ids):
            raise ValueError("unattached TimeExpression became a canonical Time node")
        occurred_on_endpoints = [
            (edge["source_id"], edge["target_id"])
            for edge in edges
            if edge["edge_type"] == "OCCURRED_ON"
        ]
        if len(occurred_on_endpoints) != len(set(occurred_on_endpoints)):
            raise ValueError("duplicate canonical OCCURRED_ON endpoint pair")

        eventframes = {row["eventframe_id"]: row for row in payload["eventframes"]}
        expected_fillers = []
        for eventframe_id, eventframe in eventframes.items():
            for role in ("ACTOR", "TARGET", "PLACE"):
                expected_fillers.extend(
                    (eventframe_id, role, filler)
                    for filler in eventframe["participants"][role]["items"]
                )
        preserved = payload["unmaterialized_evidence"]["participant_fillers"]
        if len(expected_fillers) != len(preserved):
            raise ValueError("raw participant filler count changed during assembly")
        for record in preserved:
            source_eventframe_id = record["source_eventframe_id"]
            if source_eventframe_id not in eventframes:
                raise ValueError("raw filler references an unknown EventFrame")
            source_items = eventframes[source_eventframe_id]["participants"][record["role"]][
                "items"
            ]
            if record["filler"] not in source_items:
                raise ValueError("participant evidence was mixed across EventFrames")
            _validate_evidence_mapping(
                record["filler"],
                payload["article"]["article_id"],
                content,
                sentence_index=int(eventframes[source_eventframe_id]["event"]["sentence_index"]),
            )
        resolution_rows = payload["source_lanes"][
            "participant_entity_resolutions"
        ]["items"]
        resolved_ids = {
            row["participant_evidence_id"]
            for row in resolution_rows
            if row["resolution_status"] == "ENTITY_RESOLVED"
        }
        role_edges = [
            edge
            for edge in edges
            if edge["edge_type"] in {"ACTOR", "TARGET", "PLACE"}
        ]
        if any(
            edge["provenance"].get("participant_evidence_id") not in resolved_ids
            for edge in role_edges
        ):
            raise ValueError("unresolved participant was promoted to a canonical role edge")
        if any(node["kind"] == "MIX" for node in nodes):
            raise ValueError("MIX is a sentence state, not a graph node")
        if payload["lane_statuses"]["graph_assembly"]["status"] != "EXECUTED":
            raise ValueError("graph assembly status must be explicit")
        for lane in (
            "entity_mentions",
            "entity_candidate_priorities",
            "local_entities",
            "participant_entity_resolutions",
            "local_events",
            "event_coreference",
            "time_expressions",
            "resolution",
            "relations",
        ):
            if (
                payload["source_lanes"][lane]["status"]
                != payload["lane_statuses"]["source_runtime"][lane]
            ):
                raise ValueError(f"source {lane} status changed during graph assembly")
        # Deterministic JSON round-trip is part of the schema gate.
        round_trip = json.loads(result.to_json())
        if round_trip != payload:
            raise ValueError("deterministic graph JSON round-trip failed")
        return {
            "status": "PASS",
            "schema_validation": "PASS",
            "serialization": "PASS",
            "dangling_reference_count": 0,
            "duplicate_node_id_count": 0,
            "duplicate_edge_id_count": 0,
            "invalid_endpoint_count": 0,
            "event_count": kind_counts["EVENT"],
            "local_event_count": kind_counts["LOCAL_EVENT"],
            "event_member_edge_count": sum(
                edge["edge_type"] == "MEMBER_OF_EVENT" for edge in edges
            ),
            "fake_event_count": 0,
            "dangling_event_reference_count": 0,
            "duplicate_lifted_edge_count": 0,
            "statement_count": kind_counts["STATEMENT"],
            "time_node_count": kind_counts["TIME"],
            "occurred_on_count": sum(
                edge["edge_type"] == "OCCURRED_ON" for edge in edges
            ),
            "raw_time_expression_count": len(raw_times),
            "event_time_attachment_count": len(attachments),
            "unresolved_or_unattached_time_count": len(raw_times)
            - len(materialized_prediction_ids),
            "duplicate_time_edge_count": 0,
            "dangling_time_reference_count": 0,
            "raw_participant_filler_count": len(preserved),
            "local_entity_count": kind_counts["LOCAL_ENTITY"],
            "mentions_edge_count": sum(
                edge["edge_type"] == "MENTIONS" for edge in edges
            ),
            "fake_entity_count": 0,
            "canonical_role_edge_count": len(role_edges),
            "fake_time_node_count": 0,
        }

    def _validate_input(self, payload: Mapping[str, Any]) -> None:
        if payload.get("schema_version") != INPUT_SCHEMA_VERSION:
            raise ValueError("⑧ graph assembly accepts canonical runtime result v1 only")
        if payload.get("runtime_config_id") != self.config.runtime_config_id:
            raise ValueError("runtime result does not match release-freeze runtime config")
        required = {
            "article",
            "events",
            "statements",
            "entity_mentions",
            "local_entities",
            "participant_entity_resolutions",
            "local_events",
            "event_coreference",
            "time_expressions",
            "resolution",
            "relations",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"canonical runtime result is missing fields: {missing}")
        article = payload["article"]
        if not isinstance(article.get("content"), str) or not article["content"]:
            raise ValueError("canonical runtime article content is the offset source-of-truth")
        for sentence in payload.get("sentences", []):
            if sentence.get("presence", {}).get("hard_gate_used") is True:
                raise ValueError("Presence must not destructively gate graph propositions")
        for eventframe in payload["events"]:
            if eventframe.get("eventframe_id") is None:
                raise ValueError("EventFrame identity is required")
            if eventframe.get("event", {}).get("kind") != "EVENT":
                raise ValueError("EventFrame must wrap an EVENT proposition")
            participants = eventframe.get("participants", {})
            if set(participants) != {"ACTOR", "TARGET", "PLACE"}:
                raise ValueError("EventFrame participant lanes must remain role-independent")
        for statement in payload["statements"]:
            if statement.get("proposition", {}).get("kind") != "STATEMENT":
                raise ValueError("Statement carrier must wrap a STATEMENT proposition")


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\u241f".join(parts).encode("utf-8")
    return f"{prefix}-{sha256(material).hexdigest()[:24]}"


def _evidence(
    article_id: str,
    item: Mapping[str, Any],
    *,
    sentence_index: int | None = None,
) -> GraphEvidence:
    return GraphEvidence(
        article_id=article_id,
        char_start=int(item["char_start"]),
        char_end=int(item["char_end"]),
        text=str(item["text"]),
        sentence_index=int(
            item["sentence_index"] if "sentence_index" in item else sentence_index
        ),
    )


def _validate_evidence_mapping(
    evidence: Mapping[str, Any],
    article_id: str,
    content: str,
    *,
    sentence_index: int | None = None,
) -> None:
    GraphEvidence(
        article_id=str(evidence.get("article_id", article_id)),
        char_start=int(evidence["char_start"]),
        char_end=int(evidence["char_end"]),
        text=str(evidence["text"]),
        sentence_index=int(
            evidence["sentence_index"] if "sentence_index" in evidence else sentence_index
        ),
    ).validate(content)
    if evidence.get("article_id", article_id) != article_id:
        raise ValueError("cross-article evidence is forbidden")


def _uniform_status(rows: list[Mapping[str, Any]], field: str) -> str:
    statuses = {row[field]["status"] for row in rows}
    if not statuses:
        return "NOT_RUN"
    if len(statuses) == 1:
        return str(next(iter(statuses)))
    return "MIXED_STATUS"
