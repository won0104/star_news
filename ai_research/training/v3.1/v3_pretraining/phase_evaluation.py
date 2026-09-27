"""Read-only predicted producer diagnostics using serving's exact stage boundaries.

The source prediction is completed before Gold is inspected for metrics. This
module does not score the student checkpoint: the existing worker has one core
while source policy is bound to its predecessor. It cannot certify phase or
runtime readiness and never changes training readiness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import subprocess
from typing import Any

import torch

from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.serving import V3ServingWorker
from runtime.v3_pretraining.source_funnel import SourceFunnelPolicy
from training.v3_pretraining.code_snapshot import (relevant_code_snapshot,
                                                   training_code_snapshot)
from training.v3_pretraining.corpus import R06GoldReader, TrainGoldReader
from training.v3_pretraining.evaluation import EvaluationCohort, exact_match
from training.v3_pretraining.harness import HarnessConfig
from training.v3_pretraining.staged import (FORMAT_VERSION, GOLD_ONLY_FORMAT_VERSION,
                                            EVENT_HEAD_FORMAT_VERSION,
                                            TRAINING_PHASES, _gold400_parent_selected as
                                            _gold400_selected_checkpoint,
                                            load_phase_checkpoint)
from training.v3_pretraining.targets import ValidatedGoldArticle


PHASES = ("entity_role_time_attribution_sources", "entity_identity",
          "entity_role_time_attribution", "event_identity", "cluster_consumers")
EVALUATOR_ARTIFACT_VERSION = "v3-predicted-phase-diagnostic-v1"


@dataclass(frozen=True, slots=True)
class PredictedEvaluationBinding:
    """Separate dev gate, with checkpoint bytes and predicted policy lineage."""

    phase: str
    checkpoint_sha256: str
    producer_checkpoint_sha256: str
    source_policy_sha256: str
    source_acceptance_sha256: str
    entity_pair_policy_sha256: str | None
    entity_pair_artifact_sha256: str | None
    relevant_code_snapshot_sha256: str
    metric_contract_sha256: str


def metric_contract_sha256() -> str:
    """Bind the existing exact matcher and this phase-specific metric join."""
    files = (Path(__file__).with_name("evaluation.py"), Path(__file__))
    return sha256(b"".join(path.read_bytes() for path in files)).hexdigest()


def load_predicted_evaluation_binding(*, phase: str, checkpoint_path: str | Path,
                                      producer_checkpoint_path: str | Path,
                                      source_policy_path: str | Path,
                                      source_acceptance_path: str | Path,
                                      budget: Any,
                                      base: HarnessConfig,
                                      reader: TrainGoldReader | R06GoldReader,
                                      article_ids: tuple[str, ...],
                                      entity_pair_artifact_path: str | Path | None = None
                                      ) -> tuple[PredictedEvaluationBinding, SourceFunnelPolicy,
                                                 EntityPairPolicy | None]:
    """Validate eval-only artifacts without changing any training checkpoint."""
    if phase not in PHASES:
        raise ValueError("unknown predicted evaluation phase")
    checkpoint_bytes = Path(checkpoint_path).read_bytes()
    producer_bytes = Path(producer_checkpoint_path).read_bytes()
    checkpoint_sha = sha256(checkpoint_bytes).hexdigest()
    producer_sha = sha256(producer_bytes).hexdigest()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    producer = torch.load(producer_checkpoint_path, map_location="cpu", weights_only=True)
    predecessor = TRAINING_PHASES[TRAINING_PHASES.index(phase) - 1]
    legacy_selection_sha = None
    if (predecessor == "entity_role_time_attribution" and
            isinstance(reader, R06GoldReader) and len(reader.gold) == 400 and
            isinstance(producer, dict)):
        from training.v3_pretraining.event_head_migration import (
            legacy_selection_code_snapshot_sha256, verify_legacy_source_snapshot)
        verify_legacy_source_snapshot(producer)
        legacy_selection_sha = legacy_selection_code_snapshot_sha256(
            producer["repository_head"])

    def completed(payload: dict, path: str | Path) -> bool:
        state = payload.get("training_state")
        return (isinstance(state, dict) and
                type(state.get("completed_passes")) is int and
                state["completed_passes"] > 0 and
                (state["completed_passes"] == state.get("target_passes") or
                 (isinstance(reader, R06GoldReader) and len(reader.gold) == 400 and
                  _gold400_selected_checkpoint(
                      path, state["completed_passes"],
                      selection_snapshot_sha256=(legacy_selection_sha
                                                 if Path(path) == Path(producer_checkpoint_path)
                                                 else None)))) and
                state.get("article_position") == 0 and
                type(state.get("optimizer_steps")) is int and
                state["optimizer_steps"] > 0)

    if (not isinstance(checkpoint, dict) or not isinstance(producer, dict) or
            checkpoint.get("format_version") != (
                EVENT_HEAD_FORMAT_VERSION if phase in ("event_identity", "cluster_consumers")
                else GOLD_ONLY_FORMAT_VERSION) or
            producer.get("format_version") != (FORMAT_VERSION if predecessor == "extraction"
                                               else EVENT_HEAD_FORMAT_VERSION if predecessor ==
                                               "event_identity" else GOLD_ONLY_FORMAT_VERSION) or
            checkpoint.get("phase") != phase or producer.get("phase") != predecessor or
            checkpoint.get("parent_checkpoint_sha256") != producer_sha or
            not completed(checkpoint, checkpoint_path) or
            not completed(producer, producer_checkpoint_path) or
            checkpoint.get("base_config_sha256") != producer.get("base_config_sha256") or
            checkpoint.get("data_snapshot") != producer.get("data_snapshot") or
            checkpoint.get("phase_manifest", {}).get("training_authority_binding_sha256") !=
            producer.get("phase_manifest", {}).get("training_authority_binding_sha256") or
            checkpoint.get("relevant_code_snapshot") != training_code_snapshot() or
            (predecessor not in ("extraction", "entity_role_time_attribution") and
             producer.get("relevant_code_snapshot") != training_code_snapshot())):
        raise ValueError("predicted evaluator checkpoint lineage/completion/code differs")
    if predecessor == "entity_role_time_attribution":
        from training.v3_pretraining.event_head_migration import verify_legacy_source_snapshot
        if (verify_legacy_source_snapshot(producer) !=
                producer["relevant_code_snapshot"]["sha256"] or
                not checkpoint["phase_manifest"].get("event_head_migration_sha256")):
            raise ValueError("P5 predicted evaluator lacks the verified P4 migration lineage")
    student_manifest = checkpoint["phase_manifest"]
    producer_manifest = producer["phase_manifest"]
    profile = student_manifest["source_profile"]
    if producer_manifest["source_profile"] != profile:
        raise ValueError("predicted evaluator profile lineage differs")
    authority_sha = student_manifest.get("training_authority_binding_sha256")
    load_phase_checkpoint(
        checkpoint_path, expected_phase=phase, base=base, reader=reader,
        article_ids=article_ids, expected_parent_sha256=producer_sha,
        expected_profile=profile,
        expected_passes=checkpoint["training_state"]["target_passes"],
        expected_training_authority_binding_sha256=authority_sha,
        expected_event_head_migration_sha256=student_manifest.get(
            "event_head_migration_sha256"),
        check_policy_bytes=False)
    load_phase_checkpoint(
        producer_checkpoint_path, expected_phase=predecessor, base=base,
        reader=reader, article_ids=article_ids,
        expected_parent_sha256=producer.get("parent_checkpoint_sha256"),
        expected_profile=profile,
        expected_passes=producer["training_state"]["target_passes"],
        expected_training_authority_binding_sha256=authority_sha,
        expected_event_head_migration_sha256=producer_manifest.get(
            "event_head_migration_sha256"),
        expected_legacy_code_snapshot=(producer["relevant_code_snapshot"]
                                       if predecessor == "entity_role_time_attribution" else None),
        expected_phase1_selection_support_sha256=(
            producer_manifest.get("phase1_selection_support_sha256")
            if predecessor == "extraction" else None),
        check_policy_bytes=False)
    policy = SourceFunnelPolicy.load(
        source_policy_path, source_acceptance_path,
        checkpoint_sha256=producer_sha, budget=budget)
    if policy.retrieval.candidate_profile != profile:
        raise ValueError("predicted evaluator source profile differs")
    pair = None
    pair_artifact_sha = None
    requires_pair = (policy.retrieval.candidate_profile == "V23_BASELINE" and
                     PHASES.index(phase) >= 1)
    if requires_pair != (entity_pair_artifact_path is not None):
        raise ValueError("predicted Entity pair artifact requirement differs by phase")
    if entity_pair_artifact_path is not None:
        pair = EntityPairPolicy.load_predicted_validated(
            entity_pair_artifact_path, checkpoint_sha256=producer_sha,
            source_policy_sha256=policy.policy_sha256,
            acceptance_sha256=policy.acceptance_sha256)
        pair_artifact_sha = sha256(Path(entity_pair_artifact_path).read_bytes()).hexdigest()
    binding = PredictedEvaluationBinding(
        phase, checkpoint_sha, producer_sha,
        policy.policy_sha256, policy.acceptance_sha256,
        pair.sha256 if pair is not None else None, pair_artifact_sha,
        relevant_code_snapshot()["sha256"], metric_contract_sha256())
    return binding, policy, pair


@dataclass(frozen=True, slots=True)
class ProducerPrefixDiagnostic:
    phase: str
    producer_checkpoint_sha256: str
    article_id: str
    content_sha256: str
    structure: dict[str, Any]
    source_metrics: dict[str, dict[str, int | float]]
    status: str


def diagnostic_artifact(binding: PredictedEvaluationBinding,
                        rows: tuple[ProducerPrefixDiagnostic, ...], *,
                        test_access_count: int) -> dict[str, Any]:
    """Serialize only dev diagnostics; this artifact never certifies readiness."""
    if (not rows or test_access_count != 0 or
            binding.relevant_code_snapshot_sha256 != relevant_code_snapshot()["sha256"] or
            binding.metric_contract_sha256 != metric_contract_sha256() or
            len({row.article_id for row in rows}) != len(rows) or
            any(row.phase != binding.phase or
                row.producer_checkpoint_sha256 != binding.producer_checkpoint_sha256 or
                row.status not in ("PRODUCER_SOURCE_ONLY_PHASE_2",
                                   "PRODUCER_PREFIX_ONLY")
                for row in rows)):
        raise ValueError("predicted diagnostic article/checkpoint/test boundary differs")
    repository_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
        text=True).strip()
    return {
        "schema_version": EVALUATOR_ARTIFACT_VERSION,
        "phase": binding.phase,
        "status": "DIAGNOSTIC_ONLY",
        "training_readiness_mutated": False,
        "runtime_readiness": "NOT_VALIDATED",
        "repository_head": repository_head,
        "checkpoint_sha256": binding.checkpoint_sha256,
        "producer_checkpoint_sha256": binding.producer_checkpoint_sha256,
        "source_policy_sha256": binding.source_policy_sha256,
        "source_acceptance_sha256": binding.source_acceptance_sha256,
        "entity_pair_policy_sha256": binding.entity_pair_policy_sha256,
        "entity_pair_artifact_sha256": binding.entity_pair_artifact_sha256,
        "relevant_code_snapshot": relevant_code_snapshot(),
        "relevant_code_snapshot_sha256": binding.relevant_code_snapshot_sha256,
        "metric_contract_sha256": binding.metric_contract_sha256,
        "test_access_count": 0,
        "articles": [asdict(row) for row in rows],
    }


def _gold_source_spans(article: ValidatedGoldArticle) -> dict[str, set[tuple]]:
    annotations = article.annotations
    result: dict[str, set[tuple]] = {}
    for kind, rows, label in (
            ("EVENT", annotations["events"], lambda row: "EVENT"),
            ("STATEMENT", annotations["statements"], lambda row: row["type"]),
            ("ENTITY", annotations["entity_mentions"], lambda row: row["type"]),
            ("TIME", annotations["time_mentions"], lambda row: "TIME")):
        result[kind] = {(label(row), row["span"]["start"], row["span"]["end"])
                        for row in rows}
    result["TRIGGER"] = {("TRIGGER", row["trigger"]["start"], row["trigger"]["end"])
                         for row in annotations["events"] if row.get("trigger") is not None}
    return result


def audit_producer_prefix(worker: V3ServingWorker, article: ValidatedGoldArticle, *,
                          phase: str,
                          binding: PredictedEvaluationBinding) -> ProducerPrefixDiagnostic:
    """Predict with the frozen producer; join existing exact-span dev metrics."""
    if article.split != "dev" or phase not in PHASES:
        raise ValueError("predicted phase diagnostic requires a dev article and known phase")
    if (worker.source_policy is None or
            worker.source_policy.checkpoint_sha256 != worker.checkpoint_sha256 or
            binding.phase != phase or
            binding.producer_checkpoint_sha256 != worker.checkpoint_sha256 or
            binding.source_policy_sha256 != worker.source_policy.policy_sha256 or
            binding.source_acceptance_sha256 != worker.source_policy.acceptance_sha256 or
            binding.relevant_code_snapshot_sha256 != relevant_code_snapshot()["sha256"] or
            binding.metric_contract_sha256 != metric_contract_sha256()):
        raise ValueError("predicted evaluator lacks checkpoint-bound source policy")
    if (worker.v23_pair_policies is not None and PHASES.index(phase) >= 1 and
            (worker.v23_entity_pair_policy is None or
             worker.v23_all_pair_shadow_reference or
             worker.v23_entity_pair_policy.sha256 != binding.entity_pair_policy_sha256)):
        raise ValueError("V23 Entity predicted diagnostic needs an explicit bounded pair route")
    raw = article.raw
    request = {"article_id": raw.article_id, "content": raw.content,
               "article_version_id": raw.article_version_id,
               "published_at": raw.published_at}
    if phase == "cluster_consumers":
        full = worker.analyze_with_prefix_trace(**request)
        structure = {"source": full.audit["source_funnel"],
                     "predicted_structure": full.audit["predicted_structure"],
                     "public": full.public}
        selected = full.audit["source_funnel"]["selected"]
    else:
        prefix = worker.analyze_until(phase=phase, **request)
        structure = prefix.structure
        selected = structure["source"]["selected"]
    # No Gold object is passed into serving. Metric join begins only here.
    gold = _gold_source_spans(article)
    metrics = {}
    for kind, expected in gold.items():
        predicted = {(row["label"], row["start"], row["end"])
                     for row in selected[kind]}
        counts = exact_match(expected, predicted, cohort=EvaluationCohort.PREDICTED_SPAN)
        metrics[kind] = {"tp": counts.true_positive, "fp": counts.false_positive,
                         "fn": counts.false_negative,
                         "precision": counts.precision, "recall": counts.recall,
                         "f1": counts.f1}
    return ProducerPrefixDiagnostic(
        phase, worker.checkpoint_sha256, raw.article_id, raw.content_sha256,
        structure, metrics,
        "PRODUCER_SOURCE_ONLY_PHASE_2" if phase == "entity_role_time_attribution_sources"
        else "PRODUCER_PREFIX_ONLY")
