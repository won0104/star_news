"""Canonical raw Article → Semantic proposition → EventFrame carrier runtime."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import time
from pathlib import Path
from typing import Any, Mapping

import torch
from ..lifecycle import ArticleRunScope, ExecutionPolicy
from ..application_profile import ApplicationProfile
from transformers import AutoTokenizer

from .config import RuntimeConfig, digest, load_runtime_config
from .contracts import (
    ArticleInput,
    ArticleLocalRuntimeResult,
    LaneResult,
    RuntimeContractError,
    RuntimeConfigurationError,
    RuntimeFailure,
)
from .features import SharedBackboneProvider
from .models import (
    CanonicalV3SemanticRuntimeModel,
    EntityCandidatePriorityRuntimeModel,
    EntityCoreferenceRuntimeModel,
    EntityMentionRuntimeModel,
    EventIdentityInteractionRuntimeModel,
    EventTimeAttachmentRuntimeModel,
    ParticipantB2RuntimeModel,
    ParticipantEntityResolutionRuntimeModel,
    SemanticRuntimeModel,
    StatementTypeRuntimeModel,
    TimeExpressionRuntimeModel,
    TriggerRuntimeModel,
)
from .event_identity import FixedEventIdentityRuntime
from .event_closure import (
    build_compact_eventframes, build_compact_eventframes_from_mentions,
    canonical_partial_event_closure,
    close_event_identity,
)
from .entity import FixedEntityMentionRuntime
from .entity_consolidation import EntityBoundaryPolicy
from .participant import FixedParticipantB2Runtime
from .resolution import FixedEntityIdentityParticipantResolutionRuntime
from .resolution_handoff import IdentityResolutionHandoff
from .resolved_contracts import (
    CanonicalStatementState, CanonicalTemporalState, GroundingRef,
    LocalEntityState,
)
from .role_handoff import EventRoleFeatureHandoff, build_event_role_feature_handoff
from .preprocessing import RuntimePreprocessor
from .mention_consolidation import MentionPolicy, consolidate
from .semantic import FixedSemanticRuntime
from .semantic_v3 import FixedCanonicalV3SemanticRuntime
from .statement_type import FixedStatementTypeRuntime
from .trigger import FixedTriggerRuntime
from .time import (
    ArticleRelativeTimeNormalizer,
    FixedEventTimeAttachmentRuntime,
    FixedTimeExpressionRuntime,
)
from .temporal_consolidation import TimeOccurrencePolicy, close_temporal_occurrences
from ..temporal_identity import normalized_temporal_key


OUTPUT_SCHEMA_VERSION = "articlelocal-eventframe-runtime-result-v1"


def resolve_device(value: str) -> torch.device:
    if value == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if value == "cuda" and not torch.cuda.is_available():
        raise RuntimeConfigurationError("CUDA was requested but is unavailable")
    if value not in {"cpu", "cuda"}:
        raise RuntimeConfigurationError("device must be auto, cpu, or cuda")
    return torch.device(value)


class ArticleLocalRuntime:
    """One source-of-truth configuration and one public article entry point."""

    def __init__(self, config: RuntimeConfig, *, device: str = "auto") -> None:
        started = time.perf_counter()
        self.config = config
        self.device = resolve_device(device)
        if self.device.type == "cpu":
            torch.set_num_threads(int(config.payload["execution"]["cpu_threads"]))
        snapshot = config.backbone_snapshot()
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot, local_files_only=True, use_fast=True
        )
        self.preprocessor = RuntimePreprocessor(
            tokenizer,
            max_sentence_tokens=int(config.payload["preprocessing"]["max_sentence_tokens"]),
        )
        self.v3_semantic_socket = "semantic_v3_checkpoint" in config.payload.get("artifacts", {})
        semantic_config = dict(config.payload["semantic"])
        semantic_config.update(
            {
                "canonical_runtime_config_id": config.runtime_config_id,
                "source_semantic_runtime_config_id": config.payload[
                    "source_semantic_runtime_config_id"
                ],
            }
        )
        self.mention_policy = MentionPolicy.load() if self.v3_semantic_socket else None
        self.entity_boundary_policy = (
            EntityBoundaryPolicy.load() if self.v3_semantic_socket else None
        )
        self.time_occurrence_policy = (
            TimeOccurrencePolicy.load() if self.v3_semantic_socket else None
        )
        if self.v3_semantic_socket:
            with torch.random.fork_rng(devices=[]):
                semantic_model = CanonicalV3SemanticRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                proposer_path = config.artifact("semantic_proposer_checkpoint")
                v3_path = config.artifact("semantic_v3_checkpoint")
                semantic_model.load_upstream_state(
                    torch.load(proposer_path, map_location=self.device, weights_only=True)
                )
                semantic_model.canonical_v3.load_state_dict(
                    torch.load(v3_path, map_location=self.device, weights_only=True), strict=True
                )
                if sum(parameter.numel() for parameter in semantic_model.canonical_v3.parameters()) != 760226:
                    raise RuntimeConfigurationError("Canonical V3 parameter count mismatch")
                semantic_model.eval()
            self.semantic = FixedCanonicalV3SemanticRuntime(
                semantic_model, semantic_config, digest(proposer_path), digest(v3_path),
            )
        else:
            with torch.random.fork_rng(devices=[]):
                semantic_model = SemanticRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                semantic_path = config.artifact("semantic_checkpoint")
                semantic_model.load_state_dict(
                    torch.load(semantic_path, map_location=self.device, weights_only=True), strict=True
                )
                semantic_model.eval()
            self.semantic = FixedSemanticRuntime(
                semantic_model, semantic_config, digest(semantic_path)
            )
        with torch.random.fork_rng(devices=[]):
            participant_model = ParticipantB2RuntimeModel().to(
                device=self.device, dtype=torch.float32
            )
            participant_path = config.artifact("participant_b2_checkpoint")
            participant_model.load_state_dict(
                torch.load(participant_path, map_location=self.device, weights_only=True), strict=True
            )
            participant_model.eval()
        self.participant = FixedParticipantB2Runtime(
            participant_model,
            config.payload["participant_b2"],
            digest(participant_path),
        )
        self.entity = None
        self.entity_resolution = None
        if config.payload["components"]["entity"]["enabled"]:
            with torch.random.fork_rng(devices=[]):
                entity_model = EntityMentionRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                entity_path = config.artifact("entity_checkpoint")
                entity_payload = torch.load(
                    entity_path, map_location=self.device, weights_only=True
                )
                entity_model.load_state_dict(entity_payload["model"], strict=True)
                entity_model.eval()
            entity_config = dict(config.payload["entity"])
            entity_config["runtime_config_id"] = config.runtime_config_id
            priority_model = None
            priority_config = None
            priority_sha = None
            if config.payload["components"]["entity_candidate_restriction"]["enabled"]:
                priority_path = config.artifact("entity_candidate_restriction_checkpoint")
                priority_payload = torch.load(
                    priority_path, map_location=self.device, weights_only=True
                )
                if priority_payload["entity_checkpoint_sha256"] != digest(entity_path):
                    raise RuntimeConfigurationError(
                        "Entity priority verifier was trained against another stage-③ checkpoint"
                    )
                if float(priority_payload["entity_threshold"]) != float(entity_config["threshold"]):
                    raise RuntimeConfigurationError(
                        "Entity priority verifier stage-③ threshold mismatch"
                    )
                with torch.random.fork_rng(devices=[]):
                    priority_model = EntityCandidatePriorityRuntimeModel(
                        priority_payload["input_size"],
                        priority_payload["hidden_size"],
                        priority_payload["dropout"],
                    ).to(device=self.device, dtype=torch.float32)
                    priority_model.load_state_dict(priority_payload["model"], strict=True)
                    priority_model.eval()
                priority_config = dict(config.payload["entity_candidate_restriction"])
                priority_config["runtime_config_id"] = config.runtime_config_id
                priority_sha = digest(priority_path)
            self.entity = FixedEntityMentionRuntime(
                entity_model,
                entity_config,
                digest(entity_path),
                priority_model=priority_model,
                priority_config=priority_config,
                priority_checkpoint_sha=priority_sha,
                boundary_policy=self.entity_boundary_policy,
            )
            if config.payload["components"].get("entity_coreference", {}).get("enabled"):
                if priority_model is None:
                    raise RuntimeConfigurationError(
                        "Entity identity requires the frozen soft-priority component"
                    )
                coreference_path = config.artifact("entity_coreference_checkpoint")
                coreference_payload = torch.load(
                    coreference_path, map_location=self.device, weights_only=True
                )
                participant_resolution_path = config.artifact(
                    "participant_entity_resolution_checkpoint"
                )
                participant_resolution_payload = torch.load(
                    participant_resolution_path,
                    map_location=self.device,
                    weights_only=True,
                )
                for name, payload in (
                    ("entity_coreference", coreference_payload),
                    ("participant_entity_resolution", participant_resolution_payload),
                ):
                    if payload["entity_checkpoint_sha256"] != digest(entity_path):
                        raise RuntimeConfigurationError(
                            f"{name} was trained against another Entity checkpoint"
                        )
                    if payload["entity_priority_checkpoint_sha256"] != priority_sha:
                        raise RuntimeConfigurationError(
                            f"{name} was trained against another priority checkpoint"
                        )
                with torch.random.fork_rng(devices=[]):
                    coreference_model = EntityCoreferenceRuntimeModel(
                        coreference_payload["policy_feature_size"]
                    ).to(device=self.device, dtype=torch.float32)
                    coreference_model.load_state_dict(
                        coreference_payload["model"], strict=True
                    )
                    coreference_model.eval()
                    participant_resolution_model = ParticipantEntityResolutionRuntimeModel(
                        participant_resolution_payload["policy_feature_size"]
                    ).to(device=self.device, dtype=torch.float32)
                    participant_resolution_model.load_state_dict(
                        participant_resolution_payload["model"], strict=True
                    )
                    participant_resolution_model.eval()
                resolution_config = dict(config.payload["entity_resolution"])
                resolution_config.update(
                    {
                        "runtime_config_id": config.runtime_config_id,
                        "entity_coreference_threshold": coreference_payload["threshold"],
                        "participant_resolution_threshold": participant_resolution_payload["threshold"],
                    }
                )
                self.entity_resolution = FixedEntityIdentityParticipantResolutionRuntime(
                    entity_model,
                    coreference_model,
                    participant_resolution_model,
                    resolution_config,
                    digest(coreference_path),
                    digest(participant_resolution_path),
                )
        self.trigger = None
        if config.payload["components"]["trigger"]["enabled"]:
            with torch.random.fork_rng(devices=[]):
                trigger_model = TriggerRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                trigger_path = config.artifact("trigger_checkpoint")
                trigger_model.load_state_dict(
                    torch.load(
                        trigger_path,
                        map_location=self.device,
                        weights_only=True,
                    ),
                    strict=True,
                )
                trigger_model.eval()
            self.trigger = FixedTriggerRuntime(
                trigger_model,
                config.payload["trigger"],
                digest(trigger_path),
                config.runtime_config_id,
            )
        self.statement_type = None
        if config.payload["components"]["statement_type"]["enabled"]:
            with torch.random.fork_rng(devices=[]):
                statement_type_model = StatementTypeRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                statement_type_path = config.artifact("statement_type_checkpoint")
                statement_type_model.load_state_dict(
                    torch.load(
                        statement_type_path,
                        map_location=self.device,
                        weights_only=True,
                    ),
                    strict=True,
                )
                statement_type_model.eval()
            self.statement_type = FixedStatementTypeRuntime(
                statement_type_model,
                config.payload["statement_type"],
                digest(statement_type_path),
            )
        self.time_expression = None
        if config.payload["components"]["time"]["enabled"]:
            with torch.random.fork_rng(devices=[]):
                time_model = TimeExpressionRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                time_path = config.artifact("time_expression_checkpoint")
                time_payload = torch.load(
                    time_path, map_location=self.device, weights_only=True
                )
                if time_payload.get("neural_subtypes") is not False:
                    raise RuntimeConfigurationError(
                        "canonical TimeExpression checkpoint must be subtype-free"
                    )
                time_model.load_state_dict(time_payload["model"], strict=True)
                time_model.eval()
            time_config = dict(config.payload["time_expression"])
            time_config["runtime_config_id"] = config.runtime_config_id
            self.time_expression = FixedTimeExpressionRuntime(
                time_model, time_config, digest(time_path)
            )
        self.event_time_attachment = None
        if config.payload["components"].get("event_time_attachment", {}).get("enabled"):
            with torch.random.fork_rng(devices=[]):
                attachment_model = EventTimeAttachmentRuntimeModel().to(
                    device=self.device, dtype=torch.float32
                )
                attachment_path = config.artifact("event_time_attachment_checkpoint")
                attachment_payload = torch.load(
                    attachment_path, map_location=self.device, weights_only=True
                )
                if attachment_payload.get("direction") != "EVENT_TO_TIME_EXPRESSION":
                    raise RuntimeConfigurationError("Event-Time checkpoint direction mismatch")
                attachment_model.load_state_dict(attachment_payload["model"], strict=True)
                attachment_model.eval()
            attachment_config = dict(config.payload["event_time_attachment"])
            attachment_config["runtime_config_id"] = config.runtime_config_id
            self.event_time_attachment = FixedEventTimeAttachmentRuntime(
                attachment_model, attachment_config, digest(attachment_path)
            )
        self.time_normalizer = ArticleRelativeTimeNormalizer()
        self.event_identity = None
        if config.payload["components"].get("event_coreference", {}).get("enabled"):
            identity_path = config.artifact("event_coreference_checkpoint")
            identity_payload = torch.load(
                identity_path, map_location=self.device, weights_only=False
            )
            if identity_payload.get("architecture") != "EventCoreferenceInteractionHead":
                raise RuntimeConfigurationError(
                    "Event identity checkpoint architecture mismatch"
                )
            if identity_payload.get("feature_contract") != "CURRENT_EVENTFRAME_EVENTFEATUREBUNDLE_V1":
                raise RuntimeConfigurationError(
                    "Event identity checkpoint feature contract mismatch"
                )
            identity_config = dict(config.payload["event_identity"])
            if int(identity_payload.get("policy_feature_size", -1)) != int(
                identity_config["policy_feature_size"]
            ):
                raise RuntimeConfigurationError("Event identity policy feature size mismatch")
            if int(identity_payload.get("interaction_size", -1)) != int(
                identity_config["interaction_size"]
            ):
                raise RuntimeConfigurationError("Event identity interaction size mismatch")
            with torch.random.fork_rng(devices=[]):
                identity_model = EventIdentityInteractionRuntimeModel(
                    int(identity_payload["policy_feature_size"]),
                    int(identity_payload["interaction_size"]),
                ).to(device=self.device, dtype=torch.float32)
                identity_model.load_state_dict(identity_payload["model"], strict=True)
                identity_model.eval()
            identity_config["runtime_config_id"] = config.runtime_config_id
            self.event_identity = FixedEventIdentityRuntime(
                identity_model,
                identity_config,
                digest(identity_path),
            )
        tokenizer_file = snapshot / "tokenizer.json"
        tokenizer_sha = digest(tokenizer_file) if tokenizer_file.is_file() else None
        self.backbone = SharedBackboneProvider(
            config, self.device, tokenizer_sha256=tokenizer_sha,
        )
        self.load_seconds = time.perf_counter() - started

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        *,
        device: str = "auto",
        repository_root: str | Path | None = None,
    ) -> "ArticleLocalRuntime":
        return cls(load_runtime_config(path, root=repository_root), device=device)

    def run(
        self,
        article: ArticleInput | Mapping[str, Any],
        *,
        debug_trace: bool = False,
        policy: ExecutionPolicy | None = None,
    ) -> ArticleLocalRuntimeResult:
        """legacy raw result 호환 경로. capture와 run owner는 요청 시작에 생성한다."""

        if not isinstance(article, ArticleInput):
            article = ArticleInput.from_mapping(article)
        selected = policy or ExecutionPolicy.from_request(debug_trace=debug_trace)
        with ArticleRunScope(article, selected) as scope:
            return self._run_legacy(article, policy=selected, scope=scope)

    def run_compact(self, article: ArticleInput | Mapping[str, Any], *,
                    assembler, policy: ExecutionPolicy | None = None,
                    validation_capture=None,
                    application_profiler: ApplicationProfile | None = None,
                    routing_observer=None,
                    event_identity_audit_sink=None,
                    entity_span_bounded_policy=None,
                    time_span_bounded_policy=None,
                    participant_entity_bounded_policy=None,
                    event_time_bounded_policy=None,
                    event_identity_bounded_policy=None):
        """v2.2 direct graph 경로; caller article source는 이 scope 안에서만 읽는다."""
        from runtime.graph.compact_assembly import CompactArticleLocalKGAssembler

        if not isinstance(assembler, CompactArticleLocalKGAssembler):
            raise RuntimeConfigurationError("compact graph cannot use a legacy assembler")
        if not self.v3_semantic_socket:
            raise RuntimeConfigurationError("compact graph requires canonical v2.2 runtime socket")
        if not isinstance(article, ArticleInput):
            article = ArticleInput.from_mapping(article)
        selected = policy or ExecutionPolicy.from_request()
        captured = {} if validation_capture is not None else None
        with ArticleRunScope(article, selected) as scope:
            output = self._run_legacy(
                article, policy=selected, scope=scope,
                compact_assembler=assembler,
                validation_capture=(captured.update if captured is not None else None),
                application_profiler=application_profiler,
                routing_observer=routing_observer,
                event_identity_audit_sink=event_identity_audit_sink,
                entity_span_bounded_policy=entity_span_bounded_policy,
                time_span_bounded_policy=time_span_bounded_policy,
                participant_entity_bounded_policy=participant_entity_bounded_policy,
                event_time_bounded_policy=event_time_bounded_policy,
                event_identity_bounded_policy=event_identity_bounded_policy,
            )
        if captured is not None:
            captured["post_run_scope_owner_census"] = scope.owner_census()
            validation_capture(captured)
        return output

    @torch.inference_mode()
    def _run_legacy(
        self,
        article: ArticleInput,
        *,
        policy: ExecutionPolicy,
        scope: ArticleRunScope,
        compact_assembler=None,
        validation_capture=None,
        application_profiler: ApplicationProfile | None = None,
        routing_observer=None,
        event_identity_audit_sink=None,
        entity_span_bounded_policy=None,
        time_span_bounded_policy=None,
        participant_entity_bounded_policy=None,
        event_time_bounded_policy=None,
        event_identity_bounded_policy=None,
    ):
        if not isinstance(article, ArticleInput):
            article = ArticleInput.from_mapping(article)
        total_started = time.perf_counter()
        preprocess_started = time.perf_counter()
        prepared = scope.own(self.preprocessor.prepare(article))
        preprocessing_seconds = time.perf_counter() - preprocess_started
        if application_profiler is not None:
            application_profiler.add_seconds(
                "preprocessing_tokenization", preprocessing_seconds
            )
            application_profiler.count("preprocessing", "sentence_count", len(prepared.sentences))
            application_profiler.count(
                "preprocessing", "token_count",
                sum(len(sentence["positions"]) for sentence in prepared.sentences),
            )
        backbone_started = time.perf_counter() if application_profiler is not None else None
        try:
            backbone, backbone_trace = self.backbone.get(prepared, scope=scope)
        except RuntimeContractError:
            raise
        except Exception as error:
            raise RuntimeContractError(
                f"required shared backbone runtime failed: {error}"
            ) from error
        if application_profiler is not None:
            application_profiler.stop("shared_frozen_backbone", backbone_started)
            application_profiler.count(
                "preprocessing", "backbone_online_runs", self.backbone.online_runs
            )
        trigger_failure = None
        trigger_trace = None
        trigger_extraction = None
        trigger_by_event = {}
        if self.trigger is not None:
            try:
                trigger_started = time.perf_counter() if application_profiler is not None else None
                trigger_extraction = self.trigger.extract(prepared, backbone)
                if application_profiler is not None:
                    application_profiler.stop("trigger_extraction_attachment", trigger_started)
            except Exception as error:
                trigger_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="trigger",
                    fatal=False,
                )
                trigger_trace = {
                    "stage": "③ 구간 추출부 / ⑤ 방향 관계 판정부",
                    "component": "Trigger occurrence extraction",
                    "checkpoint_sha": self.trigger.checkpoint_sha,
                    "input_count": len(prepared.sentences),
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["Trigger failed; no Event/Statement was deleted."],
                    "elapsed_seconds": 0.0,
                }
        scoring_trace = None
        try:
            if self.v3_semantic_socket:
                scoring_started = time.perf_counter() if application_profiler is not None else None
                scored = self.semantic.run(
                    prepared, backbone,
                    debug_trace=policy.capture_level.value == "FULL",
                    diagnostic_sink=policy.diagnostic_sink,
                )
                if application_profiler is not None:
                    application_profiler.stop("semantic_proposer_v3_scoring", scoring_started)
                scoring_trace = scored.trace
                consolidation_started = time.perf_counter() if application_profiler is not None else None
                semantic = consolidate(
                    prepared, scored.accepted_hypotheses,
                    trigger_extraction.occurrences if trigger_extraction else (),
                    policy=self.mention_policy,
                    semantic_config=self.semantic.config,
                    proposer_checkpoint_sha=self.semantic.proposer_checkpoint_sha,
                    v3_checkpoint_sha=self.semantic.v3_checkpoint_sha,
                    diagnostic_sink=policy.diagnostic_sink,
                )
                if application_profiler is not None:
                    application_profiler.stop(
                        "semantic_consolidation_arbitration", consolidation_started
                    )
                scored = None  # rejected/absorbed hypotheses remain only in detached sink records.
            else:
                semantic = self.semantic.run(
                    prepared, backbone, debug_trace=policy.capture_level.value == "FULL"
                )
        except RuntimeContractError:
            raise
        except Exception as error:
            raise RuntimeContractError(
                f"required Semantic runtime failed: {error}"
            ) from error
        event_propositions = [row for row in semantic.propositions if row["kind"] == "EVENT"]
        statement_propositions = [
            row for row in semantic.propositions if row["kind"] == "STATEMENT"
        ]
        if application_profiler is not None:
            transitions = semantic.trace.get("transition_counts", {})
            for name, value in (
                ("proposer_candidate_count", scoring_trace["candidate_count"]),
                ("accepted_hypothesis_count", scoring_trace["output_count"]),
                ("boundary_family_count", transitions.get("BOUNDARY_FAMILY", 0)),
                ("absorbed_boundary_count", transitions.get("ABSORBED_BOUNDARY", 0)),
                ("canonical_event_count", len(event_propositions)),
                ("canonical_statement_count", len(statement_propositions)),
            ):
                application_profiler.count("semantic", name, int(value))
        entity_failure = None
        entity_trace = None
        priority_failure = None
        priority_trace = None
        entity_mentions = ()
        entity_candidate_priorities = ()
        rescue_only_entities = ()
        if self.entity is not None:
            try:
                entity_result = self.entity.run(
                    prepared, backbone, diagnostic_sink=policy.diagnostic_sink,
                    application_profiler=application_profiler,
                    routing_observer=routing_observer,
                    bounded_policy=entity_span_bounded_policy,
                )
                (
                    entity_mentions, entity_trace, entity_candidate_priorities,
                    priority_trace, priority_error,
                ) = entity_result[:5]
                if self.entity_boundary_policy is not None:
                    rescue_only_entities = entity_result[5]
                if application_profiler is not None:
                    closure = entity_trace.get("entity_boundary_closure", {})
                    for name, value in (
                        ("enumerated_candidate_count", entity_trace["candidate_count"]),
                        ("accepted_candidate_count", closure.get("input_count", len(entity_mentions))),
                        ("canonical_primary_count", len(entity_mentions)),
                        ("rescue_only_count", len(rescue_only_entities)),
                    ):
                        application_profiler.count("entity", name, int(value))
                entity_result = ()  # 반환 tuple의 RESCUE_ONLY 별도 alias 종료.
                if priority_error is not None:
                    priority_failure = RuntimeFailure(
                        category="COMPONENT_RUNTIME_ERROR",
                        message=priority_error,
                        component="entity_candidate_restriction",
                        fatal=False,
                    )
            except Exception as error:
                entity_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="entity",
                    fatal=False,
                )
                entity_trace = {
                    "stage": "③ 구간 추출부",
                    "component": "Nested-capable Entity Mention span classifier",
                    "checkpoint_sha": self.entity.checkpoint_sha,
                    "input_count": 0,
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["Entity failed; Event/Statement/B2 outputs were preserved."],
                    "elapsed_seconds": 0.0,
                }
        if self.trigger is not None and trigger_extraction is not None:
            try:
                trigger_attach_started = (
                    time.perf_counter() if application_profiler is not None else None
                )
                trigger_by_event, trigger_trace = self.trigger.attach(
                    event_propositions, trigger_extraction,
                )
                if application_profiler is not None:
                    application_profiler.stop(
                        "trigger_extraction_attachment", trigger_attach_started
                    )
            except Exception as error:
                trigger_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="trigger",
                    fatal=False,
                )
                trigger_trace = {
                    "stage": "③ 구간 추출부 / ⑤ 방향 관계 판정부",
                    "component": "Trigger canonical Event attachment",
                    "checkpoint_sha": self.trigger.checkpoint_sha,
                    "input_count": len(event_propositions),
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["Trigger attachment failed; canonical Events were preserved."],
                    "elapsed_seconds": 0.0,
                }
        trigger_extraction = None  # raw occurrence pool의 마지막 소비는 canonical attachment.
        statement_type_failure = None
        statement_type_trace = None
        statement_type_by_id = {}
        if self.statement_type is not None:
            try:
                statement_started = time.perf_counter() if application_profiler is not None else None
                statement_type_by_id, statement_type_trace = self.statement_type.run(
                    prepared, backbone, statement_propositions
                )
                if application_profiler is not None:
                    application_profiler.stop("statement_type", statement_started)
            except Exception as error:
                statement_type_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="statement_type",
                    fatal=False,
                )
                statement_type_trace = {
                    "stage": "④ 속성 판정부",
                    "component": "StatementType",
                    "checkpoint_sha": self.statement_type.checkpoint_sha,
                    "input_count": len(statement_propositions),
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["StatementType failed; Statement propositions were preserved."],
                    "elapsed_seconds": 0.0,
                }
        time_failure = None
        time_trace = None
        normalization_trace = None
        time_expressions = ()
        temporal_feature_rows = ()
        if self.time_expression is not None:
            try:
                time_scoring_started = time.perf_counter() if application_profiler is not None else None
                raw_times, time_trace = self.time_expression.run(
                    prepared, backbone, diagnostic_sink=policy.diagnostic_sink,
                    routing_observer=routing_observer,
                    bounded_policy=time_span_bounded_policy,
                )
                if application_profiler is not None:
                    application_profiler.stop(
                        "time_candidate_enumeration_scoring", time_scoring_started
                    )
                normalization_started = time.perf_counter()
                if self.time_occurrence_policy is not None:
                    time_expressions, temporal_states, temporal_closure_trace = (
                        close_temporal_occurrences(
                            prepared, raw_times, normalizer=self.time_normalizer,
                            policy=self.time_occurrence_policy,
                            diagnostic_sink=policy.diagnostic_sink,
                        )
                    )
                    temporal_feature_rows = tuple(
                        state.feature_row() for state in temporal_states
                    )
                    temporal_states = ()  # compact feature row가 마지막 consumer에 넘길 owner.
                    time_trace["temporal_occurrence_closure"] = temporal_closure_trace
                    if time_span_bounded_policy is not None:
                        time_trace["time_span_budget_census"].update({
                            "canonical_temporal_occurrence_count": len(time_expressions),
                            "occurrence_closure_seconds":
                                time.perf_counter() - normalization_started,
                        })
                    raw_time_count = len(raw_times)
                    raw_times = ()  # absorbed boundary rows는 독립 decision 이후 해제.
                else:
                    time_expressions = tuple(
                        {
                            **row,
                            "normalization": self.time_normalizer.normalize(
                                row["text"], article.published_at
                            ).to_dict(),
                        }
                        for row in raw_times
                    )
                    raw_time_count = len(raw_times)
                normalization_trace = {
                    "stage": "⑧ 그래프 조립부",
                    "component": "Article-relative Time normalization",
                    "checkpoint_config": "DETERMINISTIC_RULES_V1",
                    "input_count": raw_time_count,
                    "candidate_count": raw_time_count,
                    "output_count": sum(
                        row["normalization"]["status"] == "NORMALIZED"
                        for row in time_expressions
                    ),
                    "reference": "article.publishedAt only when required",
                    "system_current_time_used": False,
                    "warnings": [
                        "UNRESOLVED is a valid evidence-preserving normalization result."
                    ],
                    "elapsed_seconds": time.perf_counter() - normalization_started,
                }
                if application_profiler is not None:
                    application_profiler.stop(
                        "time_occurrence_normalization", normalization_started
                    )
                    closure = time_trace.get("temporal_occurrence_closure", {})
                    for name, value in (
                        ("enumerated_candidate_count", time_trace["candidate_count"]),
                        ("accepted_candidate_count", closure.get("input_count", len(time_expressions))),
                        ("canonical_occurrence_count", len(time_expressions)),
                    ):
                        application_profiler.count("time", name, int(value))
            except Exception as error:
                if time_span_bounded_policy is not None:
                    raise RuntimeContractError(
                        f"bounded Time span extraction failed without reference fallback: {error}"
                    ) from error
                time_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="time_expression",
                    fatal=False,
                )
                time_trace = {
                    "stage": "③ 구간 추출부",
                    "component": "Generic TimeExpression span classifier",
                    "checkpoint_sha": self.time_expression.checkpoint_sha,
                    "input_count": len(article.content),
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["Time failed; all existing runtime lanes were preserved."],
                    "elapsed_seconds": 0.0,
                }
        attachment_failure = None
        attachment_trace = None
        time_by_event = {}
        event_time_attachments = ()
        if self.event_time_attachment is not None and time_failure is None:
            try:
                attachment_started = time.perf_counter() if application_profiler is not None else None
                time_by_event, event_time_attachments, attachment_trace = (
                    self.event_time_attachment.run(
                        prepared, backbone, event_propositions, time_expressions,
                        bounded_policy=event_time_bounded_policy,
                    )
                )
                if application_profiler is not None:
                    application_profiler.stop(
                        "event_time_pair_construction_scoring", attachment_started
                    )
                    scored_pairs = int(attachment_trace["candidate_count"])
                    for name, value in (
                        ("event_count", len(event_propositions)),
                        ("time_count", len(time_expressions)),
                        ("eligible_pair_count", scored_pairs - int(attachment_trace.get("inactive_pair_count", 0))),
                        ("actually_scored_pair_count", scored_pairs),
                        ("accepted_attachment_count", len(event_time_attachments)),
                    ):
                        application_profiler.count("event_time", name, int(value))
            except Exception as error:
                if event_time_bounded_policy is not None:
                    raise RuntimeContractError(
                        f"bounded Event-Time routing failed without reference fallback: {error}"
                    ) from error
                attachment_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="event_time_attachment",
                    fatal=False,
                )
                attachment_trace = {
                    "stage": "⑤ 방향 관계 판정부",
                    "component": "Event→TimeExpression attachment",
                    "checkpoint_sha": self.event_time_attachment.checkpoint_sha,
                    "input_count": len(event_propositions) + len(time_expressions),
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["Attachment failed; raw TimeExpression evidence was preserved."],
                    "elapsed_seconds": 0.0,
                }
        participant_failed = False
        participant_failure = None
        try:
            participant_started = time.perf_counter() if application_profiler is not None else None
            participant, participant_trace = self.participant.run(
                prepared, backbone, event_propositions,
                canonical_only=self.v3_semantic_socket,
                diagnostic_sink=policy.diagnostic_sink,
            )
            if application_profiler is not None:
                application_profiler.stop("participant_b2", participant_started)
                application_profiler.count(
                    "participant", "enumerated_boundary_count",
                    int(participant_trace["candidate_count"]),
                )
                for role in ("ACTOR", "TARGET", "PLACE"):
                    application_profiler.count(
                        "participant", f"filler_count_{role.lower()}",
                        sum(len(roles[role]) for roles in participant.values()),
                    )
        except Exception as error:
            participant_failed = True
            participant = {}
            participant_failure = RuntimeFailure(
                category="COMPONENT_RUNTIME_ERROR",
                message=str(error),
                component="participant_b2",
                fatal=False,
            )
            participant_trace = {
                "stage": "③ 구간 추출부",
                "component": "Event-conditioned Participant B2",
                "checkpoint_sha": self.participant.checkpoint_sha,
                "input_count": len(event_propositions),
                "candidate_count": 0,
                "output_count": 0,
                "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                "warnings": ["Participant B2 failed; Semantic propositions were preserved."],
                "elapsed_seconds": 0.0,
            }

        resolution_failure = None
        resolution_trace = None
        local_entities = ()
        entity_coreference = ()
        participant_entity_resolutions = ()
        identity_handoff = None
        if (
            self.entity_resolution is not None
            and entity_failure is None
            and priority_failure is None
            and (not participant_failed or self.v3_semantic_socket)
        ):
            try:
                resolution_result = self.entity_resolution.run(
                    prepared, backbone, entity_mentions,
                    entity_candidate_priorities, participant,
                    rescue_only=rescue_only_entities,
                    two_pass=self.v3_semantic_socket,
                    compact_handoff=self.v3_semantic_socket,
                    diagnostic_sink=policy.diagnostic_sink,
                    application_profiler=application_profiler,
                    routing_observer=routing_observer,
                    bounded_policy=participant_entity_bounded_policy,
                    entity_inventory_lineage=(
                        (entity_span_bounded_policy.policy_id,
                         entity_span_bounded_policy.config_sha256)
                        if entity_span_bounded_policy is not None else None
                    ),
                )
                (
                    local_entities,
                    entity_coreference,
                    participant_entity_resolutions,
                    resolution_trace,
                ) = resolution_result[:4]
                if self.v3_semantic_socket:
                    identity_handoff = resolution_result[4]
                if (compact_assembler is not None and validation_capture is not None
                    and (participant_entity_bounded_policy is not None
                         or event_time_bounded_policy is not None)):
                    # 같은 PUBLIC run의 scalar census만 독립 평가 sidecar에 넘긴다.
                    # graph/member tensor 또는 탈락 pair inventory는 보존하지 않는다.
                    validation_capture({"phase_a_bounded_census": {
                        "participant": (
                            resolution_trace.get("participant_bounded_routing")
                            if resolution_trace is not None else None
                        ),
                        "participant_primary_fine_pair_count": (
                            resolution_trace.get("candidate_count", {}).get("primary_pass_pairs", 0)
                            if resolution_trace is not None else 0
                        ),
                        "participant_rescue_fine_pair_count": (
                            resolution_trace.get("candidate_count", {}).get("rescue_pass_pairs", 0)
                            if resolution_trace is not None else 0
                        ),
                        "time": (
                            attachment_trace.get("time_bounded_routing")
                            if attachment_trace is not None else None
                        ),
                        "time_fine_pair_count": (
                            attachment_trace.get("candidate_count", 0)
                            if attachment_trace is not None else 0
                        ),
                        "time_broad_possible_pair_count": (
                            attachment_trace.get("broad_possible_pair_count", 0)
                            if attachment_trace is not None else 0
                        ),
                        "time_positive_attachment_count": len(event_time_attachments),
                    }})
            except Exception as error:
                if participant_entity_bounded_policy is not None:
                    raise RuntimeContractError(
                        f"bounded Participant routing failed without reference fallback: {error}"
                    ) from error
                resolution_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="entity_resolution",
                    fatal=False,
                )
                resolution_trace = {
                    "stage": "⑥ 동일성 판정부",
                    "component": "Entity identity + Participant resolution",
                    "input_count": len(entity_mentions),
                    "candidate_count": 0,
                    "output_count": 0,
                    "drop_reason_counts": {"COMPONENT_RUNTIME_ERROR": 1},
                    "warnings": ["Resolution failed; canonical Event and compatibility evidence were preserved."],
                    "elapsed_seconds": 0.0,
                }
        role_handoff = None
        participant_item_count = sum(
            len(items) for roles in participant.values() for items in roles.values()
        )
        entity_mention_count = len(entity_mentions)
        priority_count = len(entity_candidate_priorities)
        temporal_mention_count = len(time_expressions)
        attachment_count = len(event_time_attachments)
        if self.v3_semantic_socket:
            if identity_handoff is None:
                identity_handoff = IdentityResolutionHandoff({}, (), {})
            try:
                role_handoff_started = (
                    time.perf_counter() if application_profiler is not None else None
                )
                role_handoff = build_event_role_feature_handoff(
                    prepared, backbone, event_propositions, participant,
                    self.participant.model,
                )
                if application_profiler is not None:
                    application_profiler.stop(
                        "role_entity_compact_handoff", role_handoff_started
                    )
                    application_profiler.count(
                        "handoff", "resolved_role_fact_count",
                        len(identity_handoff.resolved_role_facts),
                    )
                    application_profiler.count(
                        "handoff", "entity_aggregate_count",
                        len(identity_handoff.entity_by_local_id),
                    )
                    application_profiler.count(
                        "handoff", "role_representation_filler_count",
                        sum(aggregate.member_count
                            for roles in role_handoff.by_event.values()
                            for aggregate in roles.values()),
                    )
            except Exception as error:
                role_handoff = EventRoleFeatureHandoff({})
                policy.diagnostic_sink.record("decision", {
                    "component": "participant_role_feature_handoff",
                    "article_version_id": article.article_version_id,
                    "decision": "PARTIAL_ROLE_FEATURE_UNAVAILABLE",
                    "reason": str(error),
                })
            if compact_assembler is not None and validation_capture is not None:
                # 평가용 canonical span만 같은 run에서 분리 저장한다. PUBLIC graph나
                # diagnostic capture policy에는 raw mention을 다시 주입하지 않는다.
                priorities_by_id = {row["entity_prediction_id"]: row
                                    for row in entity_candidate_priorities}
                validation_capture({
                    "article_id": article.article_id,
                    "article_version_id": article.article_version_id,
                    "content_sha256": sha256(article.content.encode("utf-8")).hexdigest(),
                    "semantic": [
                        {"kind": row["kind"], "char_start": row["char_start"],
                         "char_end": row["char_end"], "prediction_id": row["prediction_id"]}
                        for row in semantic.propositions
                    ],
                    "entity": [
                        {"char_start": row["char_start"], "char_end": row["char_end"],
                         "entity_type": row["entity_type"],
                         "prediction_id": row["prediction_id"]}
                        for row in entity_mentions
                    ],
                    "semantic_trace": semantic.trace,
                    "scoring_trace": scoring_trace,
                    "entity_trace": entity_trace,
                    **({"entity_primary_scores": [
                        {"prediction_id": row["prediction_id"],
                         "entity_score": float(row["score"]),
                         "priority_tier": priorities_by_id[row["prediction_id"]]["priority_tier"],
                         "promotion_score": priorities_by_id[row["prediction_id"]]["promotion_score"]}
                        for row in entity_mentions
                    ]} if entity_span_bounded_policy is not None else {}),
                    **({
                        "time_span_budget_census": time_trace.get(
                            "time_span_budget_census", {}) if time_trace else {},
                        "time_occurrences": [
                            {"prediction_id": row["prediction_id"],
                             "sentence_index": row["sentence_index"],
                             "char_start": row["char_start"],
                             "char_end": row["char_end"],
                             "normalization_status": row["normalization"]["status"]}
                            for row in time_expressions
                        ],
                    } if time_span_bounded_policy is not None else {}),
                })
            # legacy raw API에서만 compatibility payload를 별도 생성한다.
            if compact_assembler is None:
                participant_compat = {
                    event_id: {role: [dict(row) for row in rows]
                               for role, rows in roles.items()}
                    for event_id, roles in participant.items()
                }
                entity_mentions_compat = tuple(dict(row) for row in entity_mentions)
            else:
                participant_compat = {}
                entity_mentions_compat = ()
            participant = {}  # compact execution의 raw B2 live reference 종료.
            entity_mentions = ()  # compact execution의 raw EntityMention live reference 종료.
        else:
            participant_compat = participant
            entity_mentions_compat = entity_mentions
        rescue_only_entities = ()  # resolution winner/remap 이후 pool 마지막 소비 종료.
        resolution_result = () if self.v3_semantic_socket else None
        compact_local_entities = ()
        if compact_assembler is not None:
            entity_handoff_started = (
                time.perf_counter() if application_profiler is not None else None
            )
            states = []
            for row in local_entities:
                grounding = row["representative_grounding"]
                representative = GroundingRef(
                    str(grounding["article_version_id"]),
                    int(grounding["char_start"]), int(grounding["char_end"]),
                    int(grounding["sentence_index"]),
                )
                if representative.text(
                    article_version_id=str(article.article_version_id),
                    source_text=article.content,
                ) != row["canonical_name"]:
                    raise RuntimeContractError("canonical LocalEntity source differs")
                states.append(LocalEntityState(
                    str(row["local_entity_id"]), str(row["canonical_name"]),
                    str(row["entity_type"]), (representative,), None,
                    float(row["confidence"]),
                    str(row["identity_confidence_source"]),
                ))
            compact_local_entities = tuple(states)
            states.clear()
            local_entities = ()
            entity_coreference = ()
            participant_entity_resolutions = ()
            entity_candidate_priorities = ()
            if application_profiler is not None:
                application_profiler.stop(
                    "role_entity_compact_handoff", entity_handoff_started
                )

        eventframes = []
        resolutions_by_event = Counter()
        resolution_items_by_event = {}
        for row in (participant_entity_resolutions if compact_assembler is None else ()):
            resolution_items_by_event.setdefault(
                row["source_event_prediction_id"], []
            ).append(row)
        for proposition in (event_propositions if compact_assembler is None else ()):
            roles = participant_compat.get(
                proposition["prediction_id"], {role: [] for role in ("ACTOR", "TARGET", "PLACE")}
            )
            role_payload = {
                role: {
                    "status": (
                        "ERROR" if participant_failed else "EXECUTED" if values else "EMPTY"
                    ),
                    "items": values,
                    "semantic_interpretation": (
                        "raw participant evidence; EMPTY is model output, not Gold ABSENT"
                    ),
                }
                for role, values in roles.items()
            }
            eventframes.append(
                {
                    "eventframe_id": "EFR-" + proposition["prediction_id"].split("-", 1)[1],
                    "event": proposition,
                    "trigger": {
                        "status": (
                            "NOT_RUN"
                            if self.trigger is None
                            else "ERROR"
                            if trigger_failure is not None
                            else "EXECUTED"
                            if trigger_by_event.get(proposition["prediction_id"])
                            else "EMPTY"
                        ),
                        "item": trigger_by_event.get(proposition["prediction_id"]),
                        "reason": (
                            self.config.payload["components"]["trigger"]["reason"]
                            if self.trigger is None
                            else "Fixed predicted Trigger extraction and nearest-contained attachment."
                        ),
                    },
                    "participants": role_payload,
                    "time": {
                        "status": (
                            "NOT_RUN"
                            if self.event_time_attachment is None
                            else "ERROR"
                            if time_failure is not None or attachment_failure is not None
                            else "EXECUTED"
                            if time_by_event.get(proposition["prediction_id"])
                            else "EMPTY"
                        ),
                        "items": time_by_event.get(proposition["prediction_id"], []),
                        "reason": (
                            self.config.payload["components"].get(
                                "event_time_attachment", {}
                            ).get("reason", "Event-Time attachment is not configured.")
                            if self.event_time_attachment is None
                            else "Predicted Event→raw TimeExpression attachment; normalization is a separate stage-⑧ derivation."
                        ),
                    },
                    "relations": {
                        "status": "NOT_RUN",
                        "items": [],
                        "reason": "Hard relation lanes are outside runtime consolidation v1.",
                    },
                    "resolution": {
                        "status": (
                            "NOT_RUN"
                            if self.entity_resolution is None
                            else "ERROR"
                            if resolution_failure is not None
                            else "EXECUTED"
                        ),
                        "participant_entity_resolution": (
                            "NOT_RUN"
                            if self.entity_resolution is None
                            else "ERROR"
                            if resolution_failure is not None
                            else "EXECUTED"
                        ),
                        "items": resolution_items_by_event.get(
                            proposition["prediction_id"], []
                        ),
                        "contextual_antecedent_resolution": "NOT_RUN",
                    },
                    "provenance": {
                        "runtime_config_id": self.config.runtime_config_id,
                        "semantic_checkpoint_sha": proposition["checkpoint_sha"],
                        "b2_checkpoint_sha": self.participant.checkpoint_sha,
                        "raw_participant_requires_entity": False,
                    },
                    "trace": {
                        "source_event_prediction_id": proposition["prediction_id"],
                        "participant_component": "Event-conditioned Participant B2",
                    },
                }
            )
        statements = []
        for proposition in (statement_propositions if compact_assembler is None else ()):
            statement_type = statement_type_by_id.get(proposition["prediction_id"])
            if self.statement_type is None:
                statement_type = {
                    "status": "NOT_RUN",
                    "value": None,
                    "reason": self.config.payload["components"]["statement_type"]["reason"],
                }
            elif statement_type_failure is not None:
                statement_type = {
                    "status": "ERROR",
                    "value": None,
                    "reason": "StatementType component failed; proposition preserved.",
                }
            statements.append({
                "statement_id": proposition["prediction_id"],
                "proposition": proposition,
                "statement_type": statement_type,
                "assertor": {
                    "status": "NOT_RUN",
                    "items": [],
                    "reason": self.config.payload["components"]["assertor"]["reason"],
                },
                "about": {
                    "status": "NOT_RUN",
                    "items": [],
                    "target_contract": "EVENT|STATEMENT",
                    "reason": self.config.payload["components"]["about"]["reason"],
                },
                "provenance": {
                    "runtime_config_id": self.config.runtime_config_id,
                    "semantic_checkpoint_sha": proposition["checkpoint_sha"],
                },
                "trace": {"source_proposition_id": proposition["prediction_id"]},
            })
        statements = tuple(statements)
        identity_failure = None
        identity_trace = None
        local_events = ()
        event_coreference = ()
        identity_upstream_failures = tuple(
            failure
            for failure in (
                participant_failure,
                resolution_failure,
                trigger_failure,
                entity_failure,
                priority_failure,
                time_failure,
                attachment_failure,
            )
            if failure is not None
        )
        optional_feature_reasons = tuple(
            failure.component + ":" + (
                failure.category if compact_assembler is not None
                else failure.message
            )
            for failure in identity_upstream_failures
        )
        compact_eventframes = (
            (
                build_compact_eventframes_from_mentions(
                    event_propositions, trigger_by_event, time_by_event,
                ) if compact_assembler is not None
                else build_compact_eventframes(eventframes)
            )
            if self.v3_semantic_socket else ()
        )
        if self.event_identity is not None and (
            not identity_upstream_failures or self.v3_semantic_socket
        ):
            try:
                identity_started = (
                    time.perf_counter() if application_profiler is not None else None
                )
                identity_result = self.event_identity.run(
                    prepared,
                    backbone,
                    compact_eventframes if self.v3_semantic_socket else eventframes,
                    () if self.v3_semantic_socket else entity_mentions_compat,
                    () if self.v3_semantic_socket else local_entities,
                    temporal_feature_rows if self.time_occurrence_policy is not None
                    else time_expressions,
                    self.participant.model,
                    self.entity.model if self.entity is not None else None,
                    self.time_expression.model,
                    identity_handoff=identity_handoff if self.v3_semantic_socket else None,
                    role_handoff=role_handoff if self.v3_semantic_socket else None,
                    diagnostic_sink=policy.diagnostic_sink if self.v3_semantic_socket else None,
                    routing_observer=routing_observer,
                    event_identity_audit_sink=event_identity_audit_sink,
                    event_identity_bounded_policy=event_identity_bounded_policy,
                    missing_feature_reasons=(
                        optional_feature_reasons if self.v3_semantic_socket else ()
                    ),
                )
                local_events, event_coreference, identity_trace = identity_result[:3]
                if self.v3_semantic_socket:
                    scope.compact_event_closure = identity_result[3]
                if application_profiler is not None:
                    identity_seconds = time.perf_counter() - identity_started
                    feature_seconds = float(identity_trace["feature_bundle_seconds"])
                    scoring_seconds = float(identity_trace["scoring_seconds"])
                    application_profiler.add_seconds(
                        "event_feature_construction", feature_seconds
                    )
                    application_profiler.add_seconds("event_pair_scoring", scoring_seconds)
                    application_profiler.add_seconds(
                        "complete_link_b3_event_closure",
                        max(0.0, identity_seconds - feature_seconds - scoring_seconds),
                    )
                    closure = identity_trace.get("compact_closure") or {}
                    learned_clusters = int(closure.get("learned_local_event_count", len(local_events)))
                    final_clusters = int(closure.get("final_local_event_count", learned_clusters))
                    event_count = int(identity_trace["input_count"])
                    for name, value in (
                        ("event_count", event_count),
                        ("possible_pair_count", event_count * (event_count - 1) // 2),
                        ("scored_pair_count", identity_trace["candidate_count"]),
                        ("accepted_pair_count", len(event_coreference)),
                        ("cluster_count", final_clusters),
                        ("learned_cluster_count", learned_clusters),
                        ("b3_evaluated_pair_count", learned_clusters * (learned_clusters - 1) // 2),
                        ("b3_positive_pair_count", closure.get("b3_positive_pair_count", 0)),
                        ("b3_merged_cluster_reduction_count", learned_clusters - final_clusters),
                    ):
                        application_profiler.count("event_identity", name, int(value))
                identity_result = ()
            except Exception as error:
                if event_identity_bounded_policy is not None:
                    raise  # bounded contract failure cannot silently enter partial/reference handling.
                identity_failure = RuntimeFailure(
                    category="COMPONENT_RUNTIME_ERROR",
                    message=str(error),
                    component="event_coreference",
                    fatal=False,
                )
        elif self.event_identity is not None:
            identity_failure = RuntimeFailure(
                category="UPSTREAM_COMPONENT_ERROR",
                message="Event identity did not run because a required predicted feature lane failed.",
                component="event_coreference",
                fatal=False,
                details={
                    "upstream_components": [
                        failure.component for failure in identity_upstream_failures
                    ]
                },
            )
        if self.event_identity is not None and identity_trace is None:
            identity_trace = {
                "stage": "⑥ 동일성 판정부",
                "component": "Event identity/coreference",
                "checkpoint_sha": self.event_identity.checkpoint_sha,
                "input_count": (
                    len(compact_eventframes) if compact_assembler is not None
                    else len(eventframes)
                ),
                "candidate_count": 0,
                "output_count": {"merge_decisions": 0, "local_events": 0},
                "drop_reason_counts": {
                    (
                        "COMPONENT_RUNTIME_ERROR"
                        if self.v3_semantic_socket or not identity_upstream_failures
                        else "UPSTREAM_COMPONENT_ERROR"
                    ): 1
                },
                "warnings": ["Canonical Event state and failure reason were preserved."],
                "elapsed_seconds": 0.0,
            }
        if self.v3_semantic_socket:
            if identity_trace is None:
                identity_trace = {
                    "stage": "⑥ 동일성 판정부",
                    "component": "Event identity/coreference",
                    "input_count": len(compact_eventframes),
                    "elapsed_seconds": 0.0,
                    "warnings": ["Canonical partial Event state retained."],
                }
            if scope.compact_event_closure is None:
                reason = (
                    (
                        identity_failure.component + ":" + identity_failure.category
                        if compact_assembler is not None
                        else identity_failure.message
                    ) if identity_failure is not None
                    else "EVENT_IDENTITY_NOT_RUN"
                )
                try:
                    partial, partial_trace = close_event_identity(
                        prepared, compact_frames=compact_eventframes,
                        clusters=[{index} for index in range(len(compact_eventframes))],
                        score_by_pair={}, identity_handoff=identity_handoff,
                        role_handoff=role_handoff,
                        temporal_rows=(
                            temporal_feature_rows
                            if self.time_occurrence_policy is not None else ()
                        ),
                        diagnostic_sink=policy.diagnostic_sink,
                        failure_reason=reason,
                        missing_feature_reasons=optional_feature_reasons,
                    )
                    scope.compact_event_closure = partial
                    identity_trace["compact_partial_closure"] = partial_trace
                except Exception as partial_error:
                    if compact_assembler is not None:
                        policy.diagnostic_sink.record("decision", {
                            "component": "event_identity_partial_handoff",
                            "decision": "FACT_HANDOFF_UNAVAILABLE",
                            "error": str(partial_error),
                        })
                    scope.compact_event_closure = canonical_partial_event_closure(
                        prepared, compact_eventframes,
                        reason + "; partial fact handoff: " + (
                            type(partial_error).__name__
                            if compact_assembler is not None else str(partial_error)
                        ),
                    )
            compact_entity_remap = dict(identity_handoff.entity_identity_remap)
            compact_temporal_states = tuple(
                CanonicalTemporalState(
                    str(row["prediction_id"]),
                    str(row["temporal_occurrence_id"]),
                    GroundingRef(
                        str(row["article_version_id"]),
                        int(row["char_start"]), int(row["char_end"]),
                        int(row["sentence_index"]),
                    ),
                    str(row["semantic_type"]),
                    str(row["normalization"]["status"]),
                    normalized_temporal_key(
                        row["normalization"],
                        semantic_type=str(row["semantic_type"]),
                    ),
                ) for row in temporal_feature_rows
            )
            # compact Event identity의 마지막 소비 뒤 tensor owner를 종료한다.
            identity_handoff.release()
            role_handoff.release()
            compact_eventframes = ()
            eventframes_compat = (
                tuple(eventframes) if compact_assembler is None else ()
            )
            eventframes.clear()  # identity 실행 EventFrame[] owner 종료; legacy는 별도 사본.
            local_event_count = len(scope.compact_event_closure.local_events)
            if compact_assembler is not None:
                local_events = ()
                event_coreference = ()
                time_expressions = ()
                event_time_attachments = ()
                time_by_event.clear()
        else:
            eventframes_compat = tuple(eventframes)
            compact_entity_remap = {}
            compact_temporal_states = ()
            local_event_count = len(local_events)
        temporal_feature_rows = ()  # Event identity의 time rep/conflict 마지막 소비 뒤 해제.
        if compact_assembler is None:
            sentence_counts = Counter(
                (row["sentence_index"], row["kind"]) for row in semantic.propositions
            )
            sentences = tuple(
                {
                    **{key: value for key, value in sentence.items() if key != "tokens"},
                    "state": _sentence_state(
                        sentence_counts[sentence["sentence_index"], "EVENT"],
                        sentence_counts[sentence["sentence_index"], "STATEMENT"],
                    ),
                    "presence": {
                        "status": "NOT_RUN",
                        "hard_gate_used": False,
                        "derived_from_final_propositions": True,
                    },
                }
                for sentence in prepared.sentences
            )
        else:
            sentences = ()
        truncation_warnings = []
        for sentence in prepared.sentences:
            if sentence["tokens"] and sentence["tokens"][-1]["end"] < sentence["end"]:
                truncation_warnings.append(
                    {
                        "code": "TOKEN_TRUNCATION",
                        "message": "sentence tail is outside the 128-token model view",
                        "sentence_id": sentence["sentence_id"],
                    }
                )
        trace_rows = [
            {
                "stage": "입력 전처리",
                "component": "sentence splitter + pinned fast tokenizer",
                "checkpoint_config": self.config.payload["backbone"]["revision"],
                "input_count": len(article.content),
                "candidate_count": len(prepared.sentences),
                "output_count": sum(len(sentence["positions"]) for sentence in prepared.sentences),
                "drop_reason_counts": {"TOKEN_TRUNCATION": len(truncation_warnings)},
                "warnings": truncation_warnings,
                "elapsed_seconds": preprocessing_seconds,
            },
            {
                "stage": "① 공통 표현부",
                "component": "frozen KF-DeBERTa L8/L10/L12",
                "checkpoint_config": self.config.payload["backbone"]["revision"],
                "input_count": sum(len(sentence["positions"]) for sentence in prepared.sentences),
                "candidate_count": 0,
                "output_count": 3,
                "drop_reason_counts": {},
                "warnings": [],
                **backbone_trace,
            },
            {
                "stage": "② 문장 판정부",
                "component": "Sentence Presence",
                "checkpoint_config": None,
                "input_count": (
                    len(prepared.sentences) if compact_assembler is not None
                    else len(sentences)
                ),
                "candidate_count": 0,
                "output_count": 0,
                "drop_reason_counts": {},
                "warnings": ["NOT_RUN; presence is not a destructive gate"],
                "elapsed_seconds": 0.0,
            },
        ]
        if scoring_trace is not None:
            trace_rows.append(scoring_trace)
        trace_rows.append(semantic.trace)
        if trigger_trace is not None:
            trace_rows.append(trigger_trace)
        if statement_type_trace is not None:
            trace_rows.append(statement_type_trace)
        if entity_trace is not None:
            trace_rows.append(entity_trace)
        if priority_trace is not None:
            trace_rows.append(priority_trace)
        if time_trace is not None:
            trace_rows.append(time_trace)
        if attachment_trace is not None:
            trace_rows.append(attachment_trace)
        if normalization_trace is not None:
            trace_rows.append(normalization_trace)
        if resolution_trace is not None:
            trace_rows.append(resolution_trace)
        if identity_trace is not None:
            trace_rows.append(identity_trace)
        trace_rows.append(participant_trace)
        if compact_assembler is None:
            trace_rows.append({
                "stage": "⑧ 그래프 조립부",
                "component": "Graph assembly",
                "checkpoint_config": None,
                "input_count": len(eventframes_compat) + len(statements),
                "candidate_count": 0,
                "output_count": 0,
                "drop_reason_counts": {},
                "warnings": ["NOT_RUN by contract"],
                "elapsed_seconds": 0.0,
            })
        for row in trace_rows:
            policy.diagnostic_sink.record("stage", row)
        ledger = semantic.debug.get("proposals", ())
        if policy.capture_level.value == "FULL" and isinstance(ledger, (list, tuple)):
            for decision in ledger:
                policy.diagnostic_sink.record("candidate", {
                    "component": "semantic_proposition",
                    "article_version_id": article.article_version_id,
                    "proposal_id": decision["proposal_id"],
                    "kind": decision["kind"],
                    "sentence_index": decision["sentence_index"],
                    "char_start": decision["char_start"],
                    "char_end": decision["char_end"],
                    "boundary_score": decision["boundary_score"],
                    "verifier_score": decision["verifier_score"],
                    "accepted": decision["accepted"],
                })
        if policy.capture_level.value != "SUMMARY":
            for proposition in semantic.propositions:
                policy.diagnostic_sink.record("decision", {
                    "component": "semantic_proposition",
                    "prediction_id": proposition["prediction_id"],
                    "article_version_id": article.article_version_id,
                    "char_start": proposition["char_start"],
                    "char_end": proposition["char_end"],
                    "kind": proposition["kind"],
                })
            for mention in entity_mentions_compat:
                policy.diagnostic_sink.record("decision", {
                    "component": "entity_mentions",
                    "prediction_id": mention["prediction_id"],
                    "article_version_id": article.article_version_id,
                    "char_start": mention["char_start"],
                    "char_end": mention["char_end"],
                    "entity_type": mention["entity_type"],
                })
            for temporal in (
                compact_temporal_states if compact_assembler is not None
                else time_expressions
            ):
                policy.diagnostic_sink.record("decision", {
                    "component": "time_expressions",
                    "prediction_id": (
                        temporal.prediction_id if compact_assembler is not None
                        else temporal["prediction_id"]
                    ),
                    "article_version_id": article.article_version_id,
                    "char_start": (
                        temporal.representative.char_start if compact_assembler is not None
                        else temporal["char_start"]
                    ),
                    "char_end": (
                        temporal.representative.char_end if compact_assembler is not None
                        else temporal["char_end"]
                    ),
                    "normalization_status": (
                        temporal.v1_normalization_status if compact_assembler is not None
                        else temporal["normalization"]["status"]
                    ),
                })
            for item in entity_candidate_priorities:
                policy.diagnostic_sink.record("decision", {
                    "component": "entity_candidate_prioritization",
                    "entity_prediction_id": item["entity_prediction_id"],
                    "priority_tier": item["priority_tier"],
                    "promotion_score": item["promotion_score"],
                })
        trace = tuple(policy.diagnostic_sink.stage_summaries)
        lane = self.config.payload["components"]
        total = time.perf_counter() - total_started
        coverage = {
            "status": "EXECUTED",
            "lanes": {
                "shared_representation": "EXECUTED",
                "sentence_presence": lane["presence"]["status"],
                "semantic_proposition": "EXECUTED" if semantic.propositions else "EMPTY",
                "participant_b2": (
                    "ERROR" if participant_failed else "EXECUTED"
                    if (participant_item_count if compact_assembler is not None
                        else participant_compat) else "EMPTY"
                ),
                "entity_mentions": (
                    "NOT_RUN" if self.entity is None else "ERROR" if entity_failure
                    else "EXECUTED" if (entity_mention_count if compact_assembler is not None
                                         else entity_mentions_compat) else "EMPTY"
                ),
                "entity_candidate_prioritization": (
                    "NOT_RUN"
                    if self.entity is None or self.entity.priority_model is None
                    else "ERROR"
                    if entity_failure or priority_failure
                    else "EXECUTED"
                    if (priority_count if compact_assembler is not None
                        else entity_candidate_priorities)
                    else "EMPTY"
                ),
                "time_expressions": (
                    "NOT_RUN"
                    if self.time_expression is None
                    else "ERROR"
                    if time_failure is not None
                    else "EXECUTED"
                    if (temporal_mention_count if compact_assembler is not None
                        else time_expressions)
                    else "EMPTY"
                ),
                "event_time_attachment": (
                    "NOT_RUN"
                    if self.event_time_attachment is None
                    else "ERROR"
                    if time_failure is not None or attachment_failure is not None
                    else "EXECUTED"
                    if (attachment_count if compact_assembler is not None
                        else event_time_attachments)
                    else "EMPTY"
                ),
                "trigger": (
                    "NOT_RUN"
                    if self.trigger is None
                    else "ERROR"
                    if trigger_failure is not None
                    else "EXECUTED"
                    if any(trigger_by_event.values())
                    else "EMPTY"
                ),
                "statement_type": (
                    "NOT_RUN"
                    if self.statement_type is None
                    else "ERROR"
                    if statement_type_failure is not None
                    else "EXECUTED"
                    if statement_type_by_id
                    else "EMPTY"
                ),
                "entity_resolution": (
                    "NOT_RUN"
                    if self.entity_resolution is None
                    else "ERROR"
                    if resolution_failure is not None
                    else "EXECUTED"
                ),
                "time_resolution": (
                    "NOT_RUN"
                    if self.time_expression is None
                    else "ERROR"
                    if time_failure is not None
                    else "EXECUTED"
                ),
                "event_identity": (
                    "NOT_RUN"
                    if self.event_identity is None
                    else "ERROR"
                    if identity_failure is not None
                    else "EXECUTED"
                    if (local_event_count if compact_assembler is not None
                        else local_events)
                    else "EMPTY"
                ),
                "relations": "NOT_RUN",
                "graph_assembly": "NOT_RUN",
            },
            "timing_seconds": {
                "preprocessing": preprocessing_seconds,
                "shared_backbone": backbone_trace["elapsed_seconds"],
                "semantic": semantic.trace["elapsed_seconds"] + (
                    scoring_trace["elapsed_seconds"] if scoring_trace else 0.0
                ),
                "trigger": trigger_trace["elapsed_seconds"] if trigger_trace else 0.0,
                "statement_type": (
                    statement_type_trace["elapsed_seconds"] if statement_type_trace else 0.0
                ),
                "participant_b2": participant_trace["elapsed_seconds"],
                "entity_mentions": entity_trace["elapsed_seconds"] if entity_trace else 0.0,
                "entity_candidate_prioritization": (
                    priority_trace["elapsed_seconds"] if priority_trace else 0.0
                ),
                "time_expressions": time_trace["elapsed_seconds"] if time_trace else 0.0,
                "event_time_attachment": (
                    attachment_trace["elapsed_seconds"] if attachment_trace else 0.0
                ),
                "time_normalization": (
                    normalization_trace["elapsed_seconds"] if normalization_trace else 0.0
                ),
                "entity_resolution": (
                    resolution_trace["elapsed_seconds"] if resolution_trace else 0.0
                ),
                "event_identity": (
                    identity_trace["elapsed_seconds"] if identity_trace else 0.0
                ),
                "total": total,
            },
            "backbone_feature_source": backbone_trace["source"],
        }
        if compact_assembler is not None:
            from runtime.graph.compact_assembly import build_resolved_graph_state

            assembly_started = (
                time.perf_counter() if application_profiler is not None else None
            )
            canonical_statements = []
            for proposition in statement_propositions:
                type_row = statement_type_by_id.get(proposition["prediction_id"])
                if type_row is None:
                    type_row = {
                        "status": (
                            "NOT_RUN" if self.statement_type is None else
                            "ERROR" if statement_type_failure is not None else "EMPTY"
                        ),
                        "value": None,
                    }
                representative = GroundingRef(
                    str(article.article_version_id),
                    int(proposition["char_start"]), int(proposition["char_end"]),
                    int(proposition["sentence_index"]),
                )
                if representative.text(
                    article_version_id=str(article.article_version_id),
                    source_text=article.content,
                ) != proposition["text"]:
                    raise RuntimeContractError("canonical Statement source differs")
                canonical_statements.append(CanonicalStatementState(
                    str(proposition["prediction_id"]),
                    str(proposition["text"]), representative,
                    str(type_row["status"]),
                    str(type_row["value"]) if type_row.get("value") is not None else None,
                ))
            active_policy_ids = (
                self.mention_policy.family_policy_id,
                self.mention_policy.cross_kind_policy_id,
                self.entity_boundary_policy.policy_id,
                self.time_occurrence_policy.policy_id,
                "EVENT_SPAN_EQUIVALENCE_STRICT_V1",
                "TIME_NORMALIZER_V2",
            )
            checkpoint_provenance = {
                name: str(row["sha256"])
                for name, row in self.config.payload.get("artifacts", {}).items()
                if isinstance(row, Mapping) and row.get("sha256") is not None
            }
            policy_config_sha = {
                name: digest(
                    Path(__file__).resolve().parents[1] / "configs" / filename
                )
                for name, filename in (
                    ("semantic_mention", "semantic-mention-v22.json"),
                    ("entity_boundary", "entity-mention-v22.json"),
                    ("time_occurrence", "time-mention-v22.json"),
                )
            }
            failures = (
                participant_failure, resolution_failure, trigger_failure,
                statement_type_failure, entity_failure, priority_failure,
                time_failure, attachment_failure, identity_failure,
            )
            lane_reasons = {
                str(failure.component): failure.category
                for failure in failures if failure is not None
            }
            for failure in failures:
                if failure is not None:
                    policy.diagnostic_sink.record("decision", {
                        "component": "compact_partial_failure",
                        "failed_component": failure.component,
                        "category": failure.category,
                        "message": failure.message,
                    })
            state = build_resolved_graph_state(
                article, event_closure=scope.compact_event_closure,
                local_entities=compact_local_entities,
                entity_identity_remap=compact_entity_remap,
                statements=tuple(canonical_statements),
                temporal_occurrences=compact_temporal_states,
                lane_statuses=coverage["lanes"],
                runtime_config_id=self.config.runtime_config_id,
                assembly_config_id=compact_assembler.config.assembly_config_id,
                active_policy_ids=active_policy_ids,
                component_provenance=checkpoint_provenance,
                lane_reasons=lane_reasons,
                runtime_config_sha256=digest(self.config.path),
                assembly_config_sha256=(
                    digest(compact_assembler.config.path)
                    if compact_assembler.config.path.is_file() else None
                ),
                public_schema_sha256=compact_assembler.config.payload[
                    "public_schema"
                ]["sha256"],
                policy_config_sha256=policy_config_sha,
                diagnostic_sink=policy.diagnostic_sink,
            )
            output = compact_assembler.assemble(
                state, source_article=article, policy=policy,
            )
            if application_profiler is not None:
                application_profiler.stop(
                    "compact_graph_assembly_materialization", assembly_started
                )
                application_profiler.count("serving", "public_node_count", len(output.nodes))
                application_profiler.count("serving", "public_edge_count", len(output.edges))
                application_profiler.count(
                    "serving", "public_evidence_count",
                    sum(len(row.evidence) for row in (*output.nodes, *output.edges)),
                )
            # graph source roundtrip 뒤 compat owner를 default 경로에서 종료한다.
            eventframes_compat = ()
            entity_mentions_compat = ()
            participant_compat.clear()
            time_expressions = ()
            statements = ()
            local_events = ()
            local_entities = ()
            entity_coreference = ()
            participant_entity_resolutions = ()
            entity_candidate_priorities = ()
            event_time_attachments = ()
            time_by_event.clear()
            resolution_items_by_event.clear()
            compact_entity_remap.clear()
            compact_temporal_states = ()
            return output
        result = ArticleLocalRuntimeResult(
            schema_version=OUTPUT_SCHEMA_VERSION,
            runtime_config_id=self.config.runtime_config_id,
            article={
                "article_id": article.article_id,
                "article_version_id": article.article_version_id,
                "title": article.title,
                "content": article.content,
                "published_at": article.published_at,
                "source": article.source,
                "metadata": dict(article.metadata),
            },
            coverage=coverage,
            sentences=sentences,
            events=eventframes_compat,
            statements=statements,
            entity_mentions=LaneResult(
                "NOT_RUN" if self.entity is None else "ERROR" if entity_failure else "EXECUTED" if entity_mentions_compat else "EMPTY",
                tuple(entity_mentions_compat),
                lane["entity"]["reason"] if self.entity is None else "Entity Mention discovery executed; identity resolution remains NOT_RUN.",
            ),
            entity_candidate_priorities=LaneResult(
                "NOT_RUN"
                if self.entity is None or self.entity.priority_model is None
                else "ERROR"
                if entity_failure or priority_failure
                else "EXECUTED"
                if entity_candidate_priorities
                else "EMPTY",
                tuple(entity_candidate_priorities),
                (
                    lane["entity_candidate_restriction"]["reason"]
                    if self.entity is None or self.entity.priority_model is None
                    else "Soft priority metadata only; TIER2 remains raw Entity evidence and rescue is deferred."
                ),
            ),
            local_entities=LaneResult(
                "NOT_RUN"
                if self.entity_resolution is None
                else "ERROR"
                if resolution_failure is not None
                else "EXECUTED"
                if local_entities
                else "EMPTY",
                tuple(local_entities),
                "Predicted article-local identity clusters; no cross-article identity.",
            ),
            entity_coreference=LaneResult(
                "NOT_RUN"
                if self.entity_resolution is None
                else "ERROR"
                if resolution_failure is not None
                else "EXECUTED"
                if entity_coreference
                else "EMPTY",
                tuple(entity_coreference),
                "Accepted symmetric MERGE decisions used by safe complete-link clustering.",
            ),
            participant_entity_resolutions=LaneResult(
                "NOT_RUN"
                if self.entity_resolution is None
                else "ERROR"
                if resolution_failure is not None
                else "EXECUTED"
                if participant_entity_resolutions
                else "EMPTY",
                tuple(participant_entity_resolutions),
                "Derived Participant→LocalEntity decisions; raw B2 spans remain unchanged.",
            ),
            local_events=LaneResult(
                "NOT_RUN"
                if self.event_identity is None
                else "ERROR"
                if identity_failure is not None
                else "EXECUTED"
                if local_events
                else "EMPTY",
                tuple(local_events),
                "Conservative article-local Event identity; raw EventFrame members remain canonical evidence.",
            ),
            event_coreference=LaneResult(
                "NOT_RUN"
                if self.event_identity is None
                else "ERROR"
                if identity_failure is not None
                else "EXECUTED"
                if event_coreference
                else "EMPTY",
                tuple(event_coreference),
                "Accepted pair scores used by deterministic complete-link clustering.",
            ),
            time_expressions=LaneResult(
                "NOT_RUN"
                if self.time_expression is None
                else "ERROR"
                if time_failure is not None
                else "EXECUTED"
                if time_expressions
                else "EMPTY",
                tuple(time_expressions),
                (
                    lane["time"]["reason"]
                    if self.time_expression is None
                    else "Generic raw TimeExpression evidence with separate deterministic normalization result."
                ),
            ),
            resolution={
                "status": (
                    "NOT_RUN"
                    if self.entity_resolution is None
                    else "ERROR"
                    if resolution_failure is not None
                    else "EXECUTED"
                ),
                "entity_resolution": (
                    "NOT_RUN"
                    if self.entity_resolution is None
                    else "ERROR"
                    if resolution_failure is not None
                    else "EXECUTED"
                ),
                "participant_entity_resolution": (
                    "NOT_RUN"
                    if self.entity_resolution is None
                    else "ERROR"
                    if resolution_failure is not None
                    else "EXECUTED"
                ),
                "time_normalization": (
                    "NOT_RUN"
                    if self.time_expression is None
                    else "ERROR"
                    if time_failure is not None
                    else "EXECUTED"
                ),
                "contextual_antecedent_resolution": "NOT_RUN",
            },
            relations={
                "status": "NOT_RUN",
                "event_coreference": (
                    "NOT_RUN"
                    if self.event_identity is None
                    else "ERROR"
                    if identity_failure is not None
                    else "EXECUTED"
                    if event_coreference
                    else "EMPTY"
                ),
                "entity_coreference": (
                    "NOT_RUN"
                    if self.entity_resolution is None
                    else "ERROR"
                    if resolution_failure is not None
                    else "EXECUTED"
                ),
                "causes": "NOT_RUN",
                "subevent_of": "NOT_RUN",
                "about_target_contract": "EVENT|STATEMENT",
                "event_time_attachment": (
                    "NOT_RUN"
                    if self.event_time_attachment is None
                    else "ERROR"
                    if time_failure is not None or attachment_failure is not None
                    else "EXECUTED"
                    if event_time_attachments
                    else "EMPTY"
                ),
            },
            trace=trace + (
                {"stage": "diagnostic_capture", "summary": policy.diagnostic_sink.summary()},
            ) + (
                {"stage": "diagnostic_records", "items": tuple(policy.diagnostic_sink.records)},
            ) if policy.capture_level.value == "FULL" and policy.diagnostic_sink.path is None else trace + (
                {"stage": "diagnostic_capture", "summary": policy.diagnostic_sink.summary()},
            ),
            warnings=tuple(truncation_warnings),
            failures=tuple(
                failure
                for failure in (
                    participant_failure,
                    resolution_failure,
                    trigger_failure,
                    statement_type_failure,
                    entity_failure,
                    priority_failure,
                    time_failure,
                    attachment_failure,
                    identity_failure,
                )
                if failure is not None
            ),
        )
        self._validate_result(result)
        return result

    @staticmethod
    def _validate_result(result: ArticleLocalRuntimeResult) -> None:
        payload = result.to_dict()
        content = payload["article"]["content"]
        ids = set()
        for eventframe in payload["events"]:
            proposition = eventframe["event"]
            _validate_span(content, proposition)
            if proposition["prediction_id"] in ids:
                raise RuntimeError("duplicate prediction ID")
            ids.add(proposition["prediction_id"])
            for role in ("ACTOR", "TARGET", "PLACE"):
                for filler in eventframe["participants"][role]["items"]:
                    _validate_span(content, filler)
                    if filler["source_event_prediction_id"] != proposition["prediction_id"]:
                        raise RuntimeError("participant crossed Event identity")
        for statement in payload["statements"]:
            _validate_span(content, statement["proposition"])
        for mention in payload["entity_mentions"]["items"]:
            _validate_span(content, mention)
            if mention["prediction_id"] in ids:
                raise RuntimeError("duplicate prediction ID")
            ids.add(mention["prediction_id"])
            if mention.get("resolution_status") != "NOT_RESOLVED":
                raise RuntimeError("Entity Mention must not imply identity resolution")
        time_ids = set()
        for temporal in payload["time_expressions"]["items"]:
            _validate_span(content, temporal)
            prediction_id = temporal["prediction_id"]
            if prediction_id in ids or prediction_id in time_ids:
                raise RuntimeError("duplicate TimeExpression prediction ID")
            time_ids.add(prediction_id)
            normalization = temporal.get("normalization")
            if not isinstance(normalization, Mapping) or normalization.get("status") not in {
                "NORMALIZED",
                "UNRESOLVED",
            }:
                raise RuntimeError("TimeExpression normalization status is missing")
        attachment_ids = set()
        for eventframe in payload["events"]:
            for attachment in eventframe["time"]["items"]:
                if attachment["attachment_id"] in attachment_ids:
                    raise RuntimeError("duplicate Event-Time attachment ID")
                attachment_ids.add(attachment["attachment_id"])
                if attachment["source_event_prediction_id"] != eventframe["event"]["prediction_id"]:
                    raise RuntimeError("Event-Time attachment direction/source mismatch")
                if attachment["target_time_prediction_id"] not in time_ids:
                    raise RuntimeError("Event-Time attachment has a dangling TimeExpression")
        priorities = payload["entity_candidate_priorities"]
        if priorities["status"] == "EXECUTED":
            raw_ids = {
                mention["prediction_id"]
                for mention in payload["entity_mentions"]["items"]
            }
            priority_ids = [
                row["entity_prediction_id"] for row in priorities["items"]
            ]
            if len(priority_ids) != len(set(priority_ids)):
                raise RuntimeError("duplicate Entity priority decision")
            if set(priority_ids) != raw_ids:
                raise RuntimeError("Entity priority decisions must cover all raw evidence exactly once")
            if any(
                row["priority_tier"]
                not in {"TIER1_PROMOTED", "TIER2_EVIDENCE_ONLY"}
                for row in priorities["items"]
            ):
                raise RuntimeError("unknown Entity priority tier")
        raw_entity_ids = {
            mention["prediction_id"] for mention in payload["entity_mentions"]["items"]
        }
        local_entity_ids = set()
        materialized_mention_ids = set()
        for local_entity in payload["local_entities"]["items"]:
            local_entity_id = local_entity["local_entity_id"]
            if local_entity_id in local_entity_ids:
                raise RuntimeError("duplicate LocalEntity ID")
            local_entity_ids.add(local_entity_id)
            members = tuple(local_entity["member_entity_prediction_ids"])
            if not members or not set(members) <= raw_entity_ids:
                raise RuntimeError("LocalEntity has missing or dangling EntityMention members")
            if materialized_mention_ids & set(members):
                raise RuntimeError("EntityMention belongs to more than one LocalEntity")
            materialized_mention_ids.update(members)
            if local_entity["representative_entity_prediction_id"] not in members:
                raise RuntimeError("LocalEntity representative is not a cluster member")
            if local_entity["article_id"] != payload["article"]["article_id"]:
                raise RuntimeError("LocalEntity crossed article identity")
        raw_participant_count = sum(
            len(eventframe["participants"][role]["items"])
            for eventframe in payload["events"]
            for role in ("ACTOR", "TARGET", "PLACE")
        )
        resolution_items = payload["participant_entity_resolutions"]["items"]
        if payload["participant_entity_resolutions"]["status"] in {"EXECUTED", "EMPTY"}:
            if len(resolution_items) != raw_participant_count:
                raise RuntimeError("Participant resolution must preserve every raw B2 filler")
        evidence_ids = [row["participant_evidence_id"] for row in resolution_items]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise RuntimeError("duplicate Participant resolution evidence ID")
        for resolution in resolution_items:
            status = resolution["resolution_status"]
            if status not in {"ENTITY_RESOLVED", "UNRESOLVED"}:
                raise RuntimeError("unknown Participant Entity resolution status")
            if status == "ENTITY_RESOLVED":
                if resolution["target_entity_prediction_id"] not in raw_entity_ids:
                    raise RuntimeError("Participant resolution has a dangling EntityMention")
                if resolution["target_local_entity_id"] not in local_entity_ids:
                    raise RuntimeError("Participant resolution has a dangling LocalEntity")
            elif (
                resolution["target_entity_prediction_id"] is not None
                or resolution["target_local_entity_id"] is not None
            ):
                raise RuntimeError("unresolved Participant must not imply an Entity target")
        raw_event_ids = {
            row["event"]["prediction_id"] for row in payload["events"]
        }
        raw_eventframe_ids = {row["eventframe_id"] for row in payload["events"]}
        local_event_ids = set()
        materialized_event_ids = set()
        materialized_eventframe_ids = set()
        for local_event in payload["local_events"]["items"]:
            local_event_id = local_event["local_event_id"]
            if local_event_id in local_event_ids:
                raise RuntimeError("duplicate LocalEvent ID")
            local_event_ids.add(local_event_id)
            members = set(local_event["member_event_prediction_ids"])
            member_frames = set(local_event["member_eventframe_ids"])
            if not members or not members <= raw_event_ids:
                raise RuntimeError("LocalEvent has missing or dangling Event members")
            if not member_frames or not member_frames <= raw_eventframe_ids:
                raise RuntimeError("LocalEvent has missing or dangling EventFrame members")
            if materialized_event_ids & members or materialized_eventframe_ids & member_frames:
                raise RuntimeError("Event belongs to more than one LocalEvent")
            materialized_event_ids.update(members)
            materialized_eventframe_ids.update(member_frames)
            if local_event["representative_event_prediction_id"] not in members:
                raise RuntimeError("LocalEvent representative is not a cluster member")
            if local_event["article_id"] != payload["article"]["article_id"]:
                raise RuntimeError("LocalEvent crossed article identity")
        if payload["local_events"]["status"] in {"EXECUTED", "EMPTY"}:
            if materialized_event_ids != raw_event_ids:
                raise RuntimeError("LocalEvents must partition every raw Event exactly once")
            if materialized_eventframe_ids != raw_eventframe_ids:
                raise RuntimeError("LocalEvents must preserve every raw EventFrame exactly once")
        for row in payload["event_coreference"]["items"]:
            if row["left_event_prediction_id"] not in raw_event_ids:
                raise RuntimeError("Event coreference has a dangling left Event")
            if row["right_event_prediction_id"] not in raw_event_ids:
                raise RuntimeError("Event coreference has a dangling right Event")
            if row["left_local_event_id"] not in local_event_ids:
                raise RuntimeError("Event coreference has a dangling left LocalEvent")
            if row["right_local_event_id"] not in local_event_ids:
                raise RuntimeError("Event coreference has a dangling right LocalEvent")
            if row["left_local_event_id"] != row["right_local_event_id"]:
                raise RuntimeError("accepted Event coreference pair crosses LocalEvent clusters")


def _validate_span(content: str, row: Mapping[str, Any]) -> None:
    start, end = int(row["char_start"]), int(row["char_end"])
    if not 0 <= start < end <= len(content):
        raise RuntimeError("runtime span is outside article content")
    if content[start:end] != row["text"]:
        raise RuntimeError("runtime span text does not round-trip")


def _sentence_state(event_count: int, statement_count: int) -> str:
    if event_count and statement_count:
        return "MIX"
    if event_count:
        return "EVENT"
    if statement_count:
        return "STATEMENT"
    return "DROP"
