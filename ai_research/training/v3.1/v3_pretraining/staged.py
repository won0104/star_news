"""DAG-ordered v3 training, phase ownership, and strict phase handoff.

The current head/loss harness supplies the phase-scoped losses. This module
selects losses and parameters per phase while keeping the Gold oracle lane
independent of detached runtime source replay. It never calibrates policies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
from time import perf_counter
from types import SimpleNamespace
from typing import Mapping, Sequence

import torch

from models.v3_pretraining.task_contract import HEAD_TASKS, PHASE_TASKS, TRAINING_PHASES
from models.v3_pretraining.event_heads import EVENT_PAIR_POLICY_VERSION
from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.relation_routing import PredictedRelationRoutingArtifact
from runtime.v3_pretraining.serving import V3ServingWorker
from runtime.v3_pretraining.source_funnel import (SourceFunnelPolicy,
                                                  V23_SOURCE_FUNNEL_EXECUTION_VERSION)
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer
from training.v3_pretraining.checkpoint import capture_rng, restore_rng, source_snapshot
from training.v3_pretraining.code_snapshot import training_code_snapshot
from training.v3_pretraining.corpus import R06GoldReader, TrainGoldReader
from training.v3_pretraining.harness import (HarnessConfig, LOSS_CHANNELS,
                                             SHARED_OWNERS, V3Trainer,
                                             fresh_full_core, load_pinned_backbone)
from training.v3_pretraining.max6_schedule import validate_main_training_epochs
from training.v3_pretraining.optimization_contract import (
    parameter_owner, reduce_active_task_losses)
from training.v3_pretraining.selected_parent import (
    SelectedParentBinding, resolve_selected_parent)
from training.v3_pretraining.targets import ValidatedGoldArticle


FORMAT_VERSION = "v3-dag-phase-checkpoint-v8-selected-parent"
GOLD_ONLY_FORMAT_VERSION = "v3-dag-gold-only-phase-checkpoint-v9-selected-parent"
EVENT_HEAD_FORMAT_VERSION = "v3-dag-gold-only-phase-checkpoint-v12-selected-parent"
EVENT_HEAD_EXECUTION_CONTRACT = "P5_EVENT_FEATURE_PAIR_15_P6_PRECOMPUTED_V1"
DAG_EXECUTION_VERSION = "UNIFIED_ENTITY_IDENTITY_SINGLE_CLOSURE_V2_NO_PRIORITY"
GOLD_ONLY_DAG_EXECUTION_VERSION = "GOLD_TRAIN_PREDICTED_EVAL_V4_UNIFIED_ENTITY_NO_PRIORITY"
CHECKPOINT_FIELDS = frozenset({
    "format_version", "phase", "phase_manifest", "base_config",
    "base_config_sha256", "data_snapshot", "parent_checkpoint_sha256",
    "parent_phase", "parent_selected_record_sha256", "parent_selected_epoch",
    "producer_binding", "policy_artifact_sha256", "acceptance_artifact_sha256",
    "model_state", "optimizer_state", "optimizer_audit", "optimizer_groups",
    "training_state", "sampler_state", "rng_state", "step_logs",
})
GOLD_ONLY_CHECKPOINT_FIELDS = CHECKPOINT_FIELDS | frozenset({
    "repository_head", "relevant_code_snapshot"})


def _checkpoint_format(phase: str) -> str:
    if phase == "extraction":
        return FORMAT_VERSION
    if phase in ("event_identity", "cluster_consumers"):
        return EVENT_HEAD_FORMAT_VERSION
    return GOLD_ONLY_FORMAT_VERSION
SHARED_TRAIN = {
    "extraction": SHARED_OWNERS - {"primary_adapter"},
    "entity_role_time_attribution_sources": SHARED_OWNERS - {"primary_adapter"},
    "entity_identity": frozenset(),
    "entity_role_time_attribution": SHARED_OWNERS - {"primary_adapter"},
    "event_identity": frozenset(),
    "cluster_consumers": frozenset({"primary_adapter"}),
}
REPLAY_LOSS_CHANNELS = {
    "extraction": (),
    "entity_role_time_attribution_sources": (),
    "entity_identity": ("entity_coreference",),
    "entity_role_time_attribution": (),
    "event_identity": ("event_coreference",),
    "cluster_consumers": (),
}


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def _file_sha(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _gold400_parent_selected(path: str | Path, completed_epoch: int, *,
                             selection_snapshot_sha256: str | None = None) -> bool:
    """Accept an early-stopped parent only through its immutable dev ledger."""
    from training.v3_pretraining.gold400_schedule import inspect_epochs
    checkpoint = Path(path).resolve()
    root = checkpoint.parent.parent
    ledger_path = root / "selection-ledger.json"
    selected_path = root / "selected-checkpoint.json"
    if not ledger_path.exists() or not selected_path.exists():
        return False
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    if not isinstance(ledger, dict) or not isinstance(ledger.get("epochs"), list):
        return False
    phase = selected.get("phase")
    expected = inspect_epochs(ledger["epochs"], phase=phase,
                              selection_snapshot_sha256=selection_snapshot_sha256)
    return (selected == expected and expected["phase_complete"] is True and
            expected["selected_epoch"] == completed_epoch and
            Path(expected["selected_checkpoint_path"]).resolve() == checkpoint and
            expected["selected_checkpoint_sha256"] == _file_sha(checkpoint))


def training_data_snapshot(reader: TrainGoldReader | R06GoldReader,
                           article_ids: tuple[str, ...]) -> dict:
    """Pin exact Gold, source, split and selected train rows without dev/test access."""
    if isinstance(reader, TrainGoldReader):
        return source_snapshot(reader, article_ids)
    if not isinstance(reader, R06GoldReader) or not article_ids or len(set(article_ids)) != len(article_ids):
        raise ValueError("staged data reader/ID inventory differs")
    if any(reader.membership.get(article_id) != "train" or article_id not in reader.gold
           or article_id not in reader.source for article_id in article_ids):
        raise ValueError("r06 phase data includes missing/non-train Gold")
    return {"contract": "R06_0_TRAIN_ONLY", "gold_file_sha256": _file_sha(reader.gold_path),
            "source_file_sha256": _file_sha(reader.source_path),
            "split_file_sha256": _file_sha(reader.split_path),
            "exposure": [{"article_id": article_id,
                          "gold_sha256": _digest(reader.gold[article_id]),
                          "source_sha256": sha256(reader.source[article_id]["article"].encode()).hexdigest(),
                          "split": "train"} for article_id in article_ids]}


@dataclass(frozen=True, slots=True)
class PhaseConfig:
    """Explicit Gold loss and trainable ownership for one DAG phase."""

    phase: str
    active_losses: tuple[str, ...]
    trainable_owners: tuple[str, ...]
    oracle_weight: float
    predicted_weight: float
    loss_weights: Mapping[str, float]
    source_profile: str = "V3_WINDOW"
    entity_pair_policy: EntityPairPolicy | None = None
    entity_pair_policy_artifact_sha256: str | None = None
    relation_routing_artifact: PredictedRelationRoutingArtifact | None = None
    asserted_by_option_artifact_sha256: str | None = None
    training_authority_binding_sha256: str | None = None
    entity_stability_artifact_sha256: str | None = None
    phase1_selection_support_sha256: str | None = None
    phase1_selection_policy_sha256: str | None = None
    event_head_migration_sha256: str | None = None
    event_training_policy: str | None = None

    @classmethod
    def for_phase(cls, phase: str, base: HarnessConfig, *,
                  source_profile: str = "V3_WINDOW",
                  entity_pair_policy: EntityPairPolicy | None = None,
                  entity_pair_policy_artifact_sha256: str | None = None,
                  relation_routing_artifact: PredictedRelationRoutingArtifact | None = None,
                  asserted_by_option_artifact_sha256: str | None = None,
                  training_authority_binding_sha256: str | None = None,
                  entity_stability_artifact_sha256: str | None = None,
                  phase1_selection_support_sha256: str | None = None,
                  phase1_selection_policy_sha256: str | None = None,
                  event_head_migration_sha256: str | None = None,
                  event_training_policy: str | None = None) -> "PhaseConfig":
        if phase not in TRAINING_PHASES:
            raise ValueError("unknown DAG phase")
        losses = (*PHASE_TASKS[phase], *(
            ("entity_typing_union",) if phase == "extraction" else ()))
        owners = tuple(sorted(set(PHASE_TASKS[phase]) | SHARED_TRAIN[phase]))
        result = cls(phase, losses, owners, 1.0,
                     0.0,
                     {name: base.loss_weights[name] for name in losses}, source_profile,
                     entity_pair_policy,
                     entity_pair_policy_artifact_sha256, relation_routing_artifact,
                     asserted_by_option_artifact_sha256,
                     training_authority_binding_sha256,
                     entity_stability_artifact_sha256,
                     phase1_selection_support_sha256,
                     phase1_selection_policy_sha256, event_head_migration_sha256,
                     event_training_policy)
        result.validate()
        return result

    def validate(self) -> None:
        if self.phase not in TRAINING_PHASES:
            raise ValueError("unknown phase")
        expected = (*PHASE_TASKS[self.phase], *(
            ("entity_typing_union",) if self.phase == "extraction" else ()))
        if (self.source_profile not in ("V3_WINDOW", "V23_BASELINE") or
                (self.source_profile == "V3_WINDOW" and self.entity_pair_policy is not None) or
                (self.phase == "extraction" and (self.entity_pair_policy is not None or
                                                 self.entity_pair_policy_artifact_sha256 is not None)) or
                (self.source_profile == "V3_WINDOW" and
                 self.entity_pair_policy_artifact_sha256 is not None) or
                (self.entity_pair_policy is None and
                 self.entity_pair_policy_artifact_sha256 is not None) or
                (self.entity_pair_policy is not None and
                 (self.entity_pair_policy_artifact_sha256 is None or
                  len(self.entity_pair_policy_artifact_sha256) != 64)) or
                (self.asserted_by_option_artifact_sha256 is not None and
                 (not isinstance(self.asserted_by_option_artifact_sha256, str) or
                  len(self.asserted_by_option_artifact_sha256) != 64 or
                  any(char not in "0123456789abcdef"
                      for char in self.asserted_by_option_artifact_sha256))) or
                any(value is not None and (not isinstance(value, str) or len(value) != 64 or
                     any(char not in "0123456789abcdef" for char in value))
                    for value in (self.training_authority_binding_sha256,
                                  self.entity_stability_artifact_sha256,
                                  self.phase1_selection_support_sha256,
                                  self.event_head_migration_sha256)) or
                (self.phase1_selection_policy_sha256 is not None and
                 (len(self.phase1_selection_policy_sha256) != 64 or
                  self.phase != "extraction")) or
                (self.phase1_selection_support_sha256 is not None and
                 (self.phase != "extraction" or self.source_profile != "V23_BASELINE")) or
                (self.phase == "extraction" and self.source_profile == "V23_BASELINE" and
                 self.training_authority_binding_sha256 is not None and
                 self.phase1_selection_support_sha256 is None) or
                self.active_losses != expected or
                set(self.trainable_owners) != set(PHASE_TASKS[self.phase]) | SHARED_TRAIN[self.phase] or
                set(self.loss_weights) != set(expected) or
                self.oracle_weight != 1.0 or
                self.predicted_weight != 0.0 or
                (self.phase != "extraction" and any(value is not None for value in (
                    self.entity_pair_policy, self.entity_pair_policy_artifact_sha256,
                    self.relation_routing_artifact,
                    self.asserted_by_option_artifact_sha256,
                    self.entity_stability_artifact_sha256))) or
                (self.event_head_migration_sha256 is not None and
                 self.phase not in ("event_identity", "cluster_consumers")) or
                (self.event_training_policy is not None and
                 (self.phase not in ("event_identity", "cluster_consumers") or
                  self.event_training_policy != "GOLD400_EVENT_8TO1_MERGE_WEIGHT4_V1"))):
            raise ValueError("phase DAG/loss/ownership policy differs")

    def manifest(self) -> dict:
        self.validate()
        base_fields = asdict(self)
        base_fields.pop("entity_pair_policy")
        base_fields.pop("entity_pair_policy_artifact_sha256")
        base_fields.pop("relation_routing_artifact")
        base_fields.pop("asserted_by_option_artifact_sha256")
        base_fields.pop("training_authority_binding_sha256")
        base_fields.pop("entity_stability_artifact_sha256")
        base_fields.pop("phase1_selection_support_sha256")
        base_fields.pop("phase1_selection_policy_sha256")
        base_fields.pop("event_head_migration_sha256")
        base_fields.pop("event_training_policy")
        result = {**base_fields, "inactive_losses": sorted(set(LOSS_CHANNELS) - set(self.active_losses)),
                "dag_execution_version": (DAG_EXECUTION_VERSION if self.phase == "extraction"
                                          else GOLD_ONLY_DAG_EXECUTION_VERSION),
                "training_phase_order": list(TRAINING_PHASES),
                "frozen_owners": sorted((set(HEAD_TASKS) | SHARED_OWNERS) - set(self.trainable_owners)),
                "frozen_submodules": (["entity_mention.existence"]
                                      if self.source_profile == "V23_BASELINE" else []),
                "shared_dce": "TRAIN" if "document_context" in self.trainable_owners else "FROZEN",
                "predicted_loss_channels": ([] if self.phase != "extraction" else
                                            list(REPLAY_LOSS_CHANNELS[self.phase])),
                "oracle_lane": "GOLD_TEACHER_FORCED_UNGATED",
                "predicted_lane": ("RUNTIME_SOURCE_FUNNEL_NO_GOLD_BACKFILL"
                                   if self.phase == "extraction" else "EVALUATION_ONLY")}
        if self.phase != "extraction":
            result["phase_manifest_contract_version"] = "v3-gold-only-phase-manifest-v5-unified-entity-no-priority"
            result["training_contract"] = {
                "loss": "GOLD_ORACLE_ONLY", "parent_checkpoint_required": True,
                "predicted_artifacts_required": False}
            result["epoch_selection_contract"] = {
                "mode": "EPOCH_SELECTION_EVALUATOR",
                "score": "NEGATIVE_MEAN_ACTIVE_GOLD_ORACLE_LOSS",
                "dev_only": True, "predicted_cascade": False,
                "calibrated_thresholds": False,
                "independent_of_next_phase_training_readiness": True}
            result["evaluation_contract"] = {
                "mode": "PREDICTED_RUNTIME_EVALUATOR",
                "diagnostic_loss_channels": list(REPLAY_LOSS_CHANNELS[self.phase]),
                "source_policy_required": True, "source_acceptance_required": True,
                "entity_pair_policy_required": (self.source_profile == "V23_BASELINE" and
                                                TRAINING_PHASES.index(self.phase) >= 2)}
            result["predicted_calibration_contract"] = {
                "mode": "PREDICTED_CALIBRATION_MODE",
                "only_after_selected_checkpoint": True,
                "score_collection_before_offline_threshold_replay": True,
                "independent_of_next_phase_training_readiness": True}
            result["runtime_validation_contract"] = {
                "mode": "PREDICTED_CASCADE_READINESS",
                "source_policy_required": True,
                "source_acceptance_required": True,
                "entity_pair_policy_required": (self.source_profile == "V23_BASELINE" and
                                                TRAINING_PHASES.index(self.phase) >= 2),
                "asserted_by_option_required": (self.source_profile == "V23_BASELINE" and
                                                TRAINING_PHASES.index(self.phase) >= 3),
                "entity_stability_required": (self.source_profile == "V23_BASELINE" and
                                              TRAINING_PHASES.index(self.phase) >= 4),
                "relation_routing_required": (self.source_profile == "V23_BASELINE" and
                                              TRAINING_PHASES.index(self.phase) >= 5)}
        if self.phase in ("event_identity", "cluster_consumers"):
            result["event_head_execution_contract"] = EVENT_HEAD_EXECUTION_CONTRACT
            result["event_pair_input_schema"] = EVENT_PAIR_POLICY_VERSION
            result["event_head_migration_sha256"] = self.event_head_migration_sha256
            if self.event_training_policy is not None:
                result["event_training_policy"] = self.event_training_policy
        if self.training_authority_binding_sha256 is not None:
            result["training_authority_binding_sha256"] = self.training_authority_binding_sha256
        if self.entity_stability_artifact_sha256 is not None:
            result["entity_stability_artifact_sha256"] = self.entity_stability_artifact_sha256
        if self.source_profile == "V23_BASELINE":
            if self.phase == "extraction":
                result["source_execution_version"] = V23_SOURCE_FUNNEL_EXECUTION_VERSION
                from training.v3_pretraining.phase1_selection import policy_sha256
                result["phase1_selection_policy_sha256"] = (
                    self.phase1_selection_policy_sha256 or policy_sha256())
                if self.phase1_selection_support_sha256 is not None:
                    result["phase1_selection_support_sha256"] = (
                        self.phase1_selection_support_sha256)
        return result


def _parameter_active(name: str, phase: PhaseConfig) -> bool:
    return (parameter_owner(name) in phase.trainable_owners and
            not (phase.source_profile == "V23_BASELINE" and
                 name.startswith("task_modules.entity_mention.existence.")))


def configure_phase(core, phase: PhaseConfig) -> None:
    """Freeze all nonowners before optimizer construction or forward execution."""
    phase.validate()
    for name, parameter in core.named_parameters():
        parameter.requires_grad_(_parameter_active(name, phase))
        parameter.grad = None
    core.eval()
    for name, module in core.named_children():
        if name == "task_modules":
            for task_name, task_module in module.items():
                task_module.train(task_name in phase.trainable_owners)
        else:
            module.train(name in phase.trainable_owners)


def build_phase_optimizer(core, backbone, base: HarnessConfig,
                          phase: PhaseConfig) -> torch.optim.Optimizer:
    phase.validate()
    core.assert_unique_parameters()
    if any(parameter.requires_grad for parameter in backbone.parameters()):
        raise ValueError("pinned backbone is not frozen")
    groups: dict[str, dict] = {}
    for name, parameter in core.named_parameters():
        owner = parameter_owner(name)
        if parameter.requires_grad != _parameter_active(name, phase):
            raise ValueError("phase parameter freeze differs from owner policy")
        if not parameter.requires_grad:
            continue
        group = groups.setdefault(owner, {"name": owner, "params": [],
                                          "param_names": [], "param_shapes": [],
                                          "lr": (base.task_learning_rates[owner]
                                                 if owner in HEAD_TASKS else base.shared_learning_rate),
                                          "weight_decay": base.weight_decay})
        group["params"].append(parameter)
        group["param_names"].append(name)
        group["param_shapes"].append(list(parameter.shape))
    if set(groups) != set(phase.trainable_owners):
        raise ValueError("phase optimizer owner inventory differs")
    optimizer = torch.optim.AdamW([groups[name] for name in sorted(groups)])
    audit_phase_optimizer(core, backbone, optimizer, phase)
    return optimizer


def audit_phase_optimizer(core, backbone, optimizer, phase: PhaseConfig) -> dict:
    expected = {id(parameter): (name, tuple(parameter.shape))
                for name, parameter in core.named_parameters() if parameter.requires_grad}
    frozen = {id(parameter) for parameter in backbone.parameters()}
    seen = []
    for group in optimizer.param_groups:
        if group["name"] not in phase.trainable_owners or not (
                len(group["params"]) == len(group["param_names"]) == len(group["param_shapes"])):
            raise ValueError("phase optimizer group inventory differs")
        for parameter, name, shape in zip(group["params"], group["param_names"], group["param_shapes"]):
            if (id(parameter) in frozen or id(parameter) not in expected or
                    expected[id(parameter)] != (name, tuple(shape)) or
                    parameter_owner(name) != group["name"]):
                raise ValueError("phase optimizer has foreign/frozen parameter")
            seen.append(id(parameter))
    if len(seen) != len(set(seen)) or set(seen) != set(expected):
        raise ValueError("phase optimizer parameter missing or duplicated")
    return {"owners": sorted(group["name"] for group in optimizer.param_groups),
            "parameter_tensors": len(seen),
            "parameter_count": sum(parameter.numel() for parameter in core.parameters()
                                   if parameter.requires_grad)}


def optimizer_group_manifest(optimizer: torch.optim.Optimizer) -> list[dict]:
    return [{"name": group["name"], "lr": group["lr"],
             "weight_decay": group["weight_decay"],
             "param_names": list(group["param_names"]),
             "param_shapes": list(group["param_shapes"])}
            for group in optimizer.param_groups]


def _clip_phase_gradients(core, *, previous_count: int) -> dict:
    """Clip active gradients with CPU scalar accumulation compatible with MPS."""
    grads = [(name, parameter.grad) for name, parameter in core.named_parameters()
             if parameter.grad is not None]
    if any(not torch.isfinite(grad).all() for _, grad in grads):
        raise ValueError("non-finite phase gradient")
    def norm() -> float:
        # MPS cannot materialize float64 tensors; reduce FP32 squares to CPU scalars.
        return math.sqrt(math.fsum(float(grad.detach().float().square().sum())
                                   for _, grad in grads)) if grads else 0.0
    before = norm()
    owner_before = {owner: math.sqrt(math.fsum(
        float(grad.detach().float().square().sum()) for name, grad in grads
        if parameter_owner(name) == owner))
        for owner in sorted({parameter_owner(name) for name, _ in grads})}
    if before > 1.0:
        coefficient = 1.0 / (before + 1e-12)
        for _, grad in grads:
            grad.mul_(coefficient)
    else:
        coefficient = 1.0
    after = norm()
    if after > 1.000001:
        raise ValueError("phase gradient norm exceeds bound")
    return {"global_grad_norm_pre": before, "global_grad_norm_post": after,
            "max_grad_norm": 1.0, "clip_coefficient": coefficient,
            "clipped": before > 1.0,
            "cumulative_clipped_count": previous_count + int(before > 1.0),
            "owner_grad_norm_pre": owner_before}


class StagedTrainer:
    """Run one bounded Gold oracle phase; predicted diagnostics live outside training."""

    def __init__(self, trainer: V3Trainer, phase: PhaseConfig,
                 optimizer: torch.optim.Optimizer,
                 producer: V3ServingWorker | None = None, *,
                 article_ids: tuple[str, ...] | None = None,
                 target_passes: int = 1,
                 training_authority_binding_path: str | Path | None = None,
                 parent_selection: SelectedParentBinding | None = None) -> None:
        phase.validate()
        if trainer.extraction.profile != phase.source_profile:
            raise ValueError("phase and oracle extraction profile differ")
        if type(target_passes) is not int or target_passes < 1:
            raise ValueError("phase passes must be positive")
        if article_ids is not None and (not article_ids or len(set(article_ids)) != len(article_ids)):
            raise ValueError("phase article inventory must be nonempty and unique")
        self.trainer = trainer
        self.phase = phase
        self.optimizer = optimizer
        if producer is not None:
            raise ValueError("Gold-only phase cannot own a predicted producer")
        self.producer = None
        self.article_ids = article_ids
        self.target_passes = target_passes
        self.parent_selection = parent_selection
        self.training_authority_binding_path = (Path(training_authority_binding_path)
                                                if training_authority_binding_path is not None else None)
        self.gold400_phase_scoped = (
            self.training_authority_binding_path is not None and
            json.loads(self.training_authority_binding_path.read_text(encoding="utf-8"))
            .get("schema_version") == "v23-gold400-user-frozen-training-authority-v1")
        self.skipped_steps = 0
        self.step_logs: list[dict] = []
        audit_phase_optimizer(trainer.core, trainer.backbone, optimizer, phase)

    def assert_training_authority_binding(self) -> None:
        """Keep the approved Gold authority bound to every optimizer step."""
        if (self.training_authority_binding_path is not None and
                _file_sha(self.training_authority_binding_path) !=
                self.phase.training_authority_binding_sha256):
            raise ValueError("training-authority binding bytes drifted")

    def progress(self, article_ids: tuple[str, ...]) -> tuple[int, int]:
        if not article_ids or (self.article_ids is not None and article_ids != self.article_ids):
            raise ValueError("phase article inventory differs")
        exposures = self.trainer.articles_seen
        if exposures < 0 or exposures > len(article_ids) * self.target_passes:
            raise ValueError("phase article exposure exceeds requested passes")
        return divmod(exposures, len(article_ids))

    def _gold400_article_losses(self, article: ValidatedGoldArticle) -> SimpleNamespace:
        """Avoid Phase 1–6 inactive heads while preserving the active Gold loss."""
        from training.v3_pretraining.epoch_selection import PhaseEpochSelectionEvaluator
        trainer = self.trainer
        target = trainer.compiler.compile(article)
        batch, frozen = trainer._frozen_article_view(article, target, cache_scope="train")
        with trainer.core.forward_shared(batch, frozen) as shared:
            if self.phase.phase == "extraction":
                extraction = trainer.extraction.loss(target, batch, frozen, shared)
                extraction.validate()
                entity = trainer.entity.loss(
                    article, target, batch, frozen, shared,
                    channels=frozenset(("entity_typing_union",)))
                losses = {**extraction.losses,
                          "entity_typing_union": entity.losses["entity_typing_union"]}
                prefixes = {"semantic_validity": "semantic_validity:",
                            "trigger": "trigger:", "participant": "participant:",
                            "entity_mention": "entity_mention:",
                            "time_mention": "time_mention:"}
                active = {name: extraction.target_count[name] > 0 or any(
                    key.startswith(prefixes.get(name, "\0")) and census["negative"] > 0
                    for key, census in extraction.supervision_census.items())
                    for name in extraction.losses}
                active["entity_typing_union"] = bool(target.spans["entity_mention"])
            elif self.phase.phase == "entity_identity":
                entity = trainer.entity.loss(
                    article, target, batch, frozen, shared,
                    channels=frozenset(("entity_coreference",)))
                losses = {"entity_coreference": entity.losses["entity_coreference"]}
                active = {"entity_coreference": bool(entity.coref_pair_paths)}
            else:
                row = SimpleNamespace(article=article, target=target, batch=batch)
                losses, active, _profile = PhaseEpochSelectionEvaluator.phase_losses(
                    trainer, self.phase.phase, row, frozen, shared)
        if set(losses) != set(self.phase.active_losses) or set(active) != set(losses):
            raise ValueError("Gold400 phase-specific training loss inventory differs")
        return SimpleNamespace(
            losses=losses, active=active,
            supervision_census={"extraction": {"available": extraction.supervision_census}}
            if self.phase.phase == "extraction" else
            {"entity": {"entity_coreference_pair_paths": {
                path: entity.coref_pair_paths.count(path)
                for path in ("MERGE", "HARD_KEEP", "RANDOM_KEEP")}}}
            if self.phase.phase == "entity_identity" else {})

    def step(self, articles: Sequence[ValidatedGoldArticle], *,
             dynamics_observer=None) -> dict:
        started = perf_counter()
        self.assert_training_authority_binding()
        if not articles or len(articles) > self.trainer.config.gradient_accumulation_articles:
            raise ValueError("phase step requires one bounded accumulation group")
        if self.article_ids is not None:
            completed, position = self.progress(self.article_ids)
            expected = self.article_ids[position:position + len(articles)]
            if (completed >= self.target_passes or len(expected) != len(articles) or
                    tuple(row.raw.article_id for row in articles) != expected):
                raise ValueError("phase article order/pass boundary differs")
        audit_phase_optimizer(self.trainer.core, self.trainer.backbone,
                              self.optimizer, self.phase)
        configure_phase(self.trainer.core, self.phase)
        self.optimizer.zero_grad(set_to_none=True)
        oracle_rows = []
        predicted_rows = []
        retrieval = []
        for article in articles:
            if article.split != "train":
                raise ValueError("staged training accepts verified train Gold only")
            if self.gold400_phase_scoped:
                oracle_rows.append(self._gold400_article_losses(article))
            else:
                oracle = self.trainer.article_losses(article)
                oracle_rows.append(replace(oracle, active={name: oracle.active[name]
                                                           and name in self.phase.active_losses
                                                           for name in LOSS_CHANNELS}))
            # Runtime candidate diagnostics are evaluated after checkpointing.
        oracle_loss = reduce_active_task_losses(
            oracle_rows, weights=self.trainer.config.loss_weights,
            channels=self.phase.active_losses)
        predicted_terms = [self.trainer.config.loss_weights[name] * value
                           for row in predicted_rows for name, value in row.losses.items()
                           if row.active[name]]
        if any(name not in REPLAY_LOSS_CHANNELS[self.phase.phase]
               for row in predicted_rows for name in row.losses):
            raise ValueError("replay loss outside active phase")
        oracle_active = any(row.active[name] for row in oracle_rows
                            for name in self.phase.active_losses)
        predicted_loss = (torch.stack(predicted_terms).mean() if predicted_terms
                          else oracle_loss.detach() * 0)
        if not oracle_active and not predicted_terms:
            self.trainer.articles_seen += len(articles)
            self.skipped_steps += 1
            result = {"phase": self.phase.phase,
                    "articles": [row.raw.article_id for row in articles],
                    "optimizer_steps": self.trainer.optimizer_steps,
                    "skipped_steps": self.skipped_steps,
                    "article_exposures": self.trainer.articles_seen,
                    "skipped_no_active_supervision": True,
                    "inactive_losses": self.phase.manifest()["inactive_losses"],
                    "retrieval": retrieval, "gradient_owners": [],
                    "changed_owners": [], "active_loss_means": {},
                    "owner_update_norm": {}, "nonfinite": False,
                    "elapsed_seconds": perf_counter() - started,
                    "mps_allocated_bytes": (torch.mps.current_allocated_memory()
                                             if self.trainer.device.type == "mps" else None)}
            self.step_logs.append(result)
            return result
        total = (self.phase.oracle_weight * oracle_loss +
                 self.phase.predicted_weight * predicted_loss) if self.phase.phase == "extraction" else oracle_loss
        if dynamics_observer is not None:
            dynamics_observer.before_backward(
                core=self.trainer.core, oracle_rows=oracle_rows,
                phase=self.phase, total=total,
                step=self.trainer.optimizer_steps + 1)
        total.backward()
        decision_gradients = {}
        if self.phase.phase == "extraction":
            from training.v3_pretraining.loss_reachability import (
                assert_extraction_decision_reachability)
            decision_gradients = assert_extraction_decision_reachability(
                self.trainer.core, profile=self.phase.source_profile,
                article_censuses=[row.supervision_census for row in oracle_rows])
        elif self.phase.phase == "entity_identity":
            from training.v3_pretraining.loss_reachability import (
                assert_entity_identity_decision_reachability)
            decision_gradients = assert_entity_identity_decision_reachability(
                self.trainer.core, phase=self.phase.phase,
                article_active=[row.active for row in oracle_rows],
                article_censuses=[row.supervision_census for row in oracle_rows])
        gradient_owners = {parameter_owner(name) for name, parameter in self.trainer.core.named_parameters()
                           if parameter.grad is not None and parameter.grad.abs().sum().item() > 0}
        if gradient_owners - set(self.phase.trainable_owners):
            raise ValueError("inactive phase owner received gradient")
        if any(parameter.grad is not None for parameter in self.trainer.backbone.parameters()):
            raise ValueError("frozen backbone received gradient")
        if dynamics_observer is not None:
            dynamics_observer.after_backward(core=self.trainer.core)
        clip = _clip_phase_gradients(
            self.trainer.core,
            previous_count=self.trainer.cumulative_clipped_count)
        before = {name: parameter.detach().clone() for name, parameter in self.trainer.core.named_parameters()
                  if parameter.requires_grad}
        self.optimizer.step()
        changed = {parameter_owner(name) for name, parameter in self.trainer.core.named_parameters()
                   if name in before and not torch.equal(before[name], parameter.detach())}
        if not changed or changed - set(self.phase.trainable_owners):
            raise ValueError("phase optimizer update inventory differs")
        self.optimizer.zero_grad(set_to_none=True)
        self.trainer.optimizer_steps += 1
        self.trainer.articles_seen += len(articles)
        self.trainer.cumulative_clipped_count = clip["cumulative_clipped_count"]
        owner_update_squares: dict[str, float] = {}
        for name, parameter in self.trainer.core.named_parameters():
            if name in before:
                owner = parameter_owner(name)
                delta_square = float((parameter.detach() - before[name]).float().square().sum())
                owner_update_squares[owner] = owner_update_squares.get(owner, 0.0) + delta_square
        active_loss_means = {
            name: sum(float(row.losses[name].detach()) for row in oracle_rows
                      if row.active[name]) / sum(row.active[name] for row in oracle_rows)
            for name in self.phase.active_losses if any(row.active[name] for row in oracle_rows)}
        result = {"phase": self.phase.phase, "articles": [row.raw.article_id for row in articles],
                "optimizer_steps": self.trainer.optimizer_steps,
                "skipped_steps": self.skipped_steps,
                "article_exposures": self.trainer.articles_seen,
                "active_oracle_losses": sorted({name for row in oracle_rows for name in self.phase.active_losses
                                                if row.active[name]}),
                "inactive_losses": self.phase.manifest()["inactive_losses"],
                "oracle_loss": float(oracle_loss.detach()),
                "predicted_loss": float(predicted_loss.detach()),
                "predicted_weight": self.phase.predicted_weight,
                "predicted_active_losses": sorted({name for row in predicted_rows for name in row.losses}),
                "retrieval": retrieval, "gradient_owners": sorted(gradient_owners),
                "decision_producer_gradient_l1": decision_gradients,
                "changed_owners": sorted(changed), "gradient_clip": clip,
                "optimizer_groups": optimizer_group_manifest(self.optimizer),
                "optimizer": audit_phase_optimizer(self.trainer.core, self.trainer.backbone,
                                                   self.optimizer, self.phase),
                "active_loss_means": active_loss_means,
                "owner_update_norm": {owner: math.sqrt(value)
                                      for owner, value in owner_update_squares.items()},
                "nonfinite": False, "elapsed_seconds": perf_counter() - started,
                "mps_allocated_bytes": (torch.mps.current_allocated_memory()
                                         if self.trainer.device.type == "mps" else None)}
        if dynamics_observer is not None:
            dynamics_observer.after_step(
                core=self.trainer.core, before=before, clip=clip,
                result=result)
        self.step_logs.append({key: value for key, value in result.items()
                               if key not in ("optimizer_groups", "optimizer")})
        return result


def phase_checkpoint_payload(staged: StagedTrainer, reader: TrainGoldReader | R06GoldReader,
                             article_ids: tuple[str, ...], *, parent_sha256: str | None,
                             policy_paths: tuple[str | Path, str | Path] | None) -> dict:
    phase = staged.phase
    staged.assert_training_authority_binding()
    if ((phase.phase == "extraction" and
         (parent_sha256 is not None or policy_paths is not None)) or
            (phase.phase != "extraction" and
             (parent_sha256 is None or policy_paths is not None or staged.producer is not None))):
        raise ValueError("phase boundary checkpoint/training artifact inventory differs")
    selection = staged.parent_selection
    if ((phase.phase == "extraction" and selection is not None) or
            (selection is not None and
         (selection.phase != TRAINING_PHASES[TRAINING_PHASES.index(phase.phase) - 1] or
          selection.checkpoint_sha256 != parent_sha256)) or
            (phase.phase != "extraction" and
             phase.training_authority_binding_sha256 is not None and selection is None)):
        raise ValueError("phase selected-parent binding differs")
    policy = staged.producer.source_policy if staged.producer is not None else None
    policy_binding = policy.binding() if policy is not None else None
    if policy_paths is not None and (
            _file_sha(policy_paths[0]) != policy.policy_sha256 or
            _file_sha(policy_paths[1]) != policy.acceptance_sha256 or
            policy.checkpoint_sha256 != parent_sha256):
        raise ValueError("phase source artifact bytes/checkpoint differ")
    completed_passes, article_position = staged.progress(article_ids)
    payload = {"format_version": _checkpoint_format(phase.phase), "phase": phase.phase,
            "phase_manifest": phase.manifest(),
            "base_config": staged.trainer.config.to_dict(),
            "base_config_sha256": _digest(staged.trainer.config.to_dict()),
            "data_snapshot": training_data_snapshot(reader, article_ids),
            "parent_checkpoint_sha256": parent_sha256,
            "parent_phase": (TRAINING_PHASES[TRAINING_PHASES.index(phase.phase) - 1]
                             if phase.phase != "extraction" else None),
            "parent_selected_record_sha256": (selection.selection_record_sha256
                                              if selection is not None else None),
            "parent_selected_epoch": (selection.selected_epoch
                                      if selection is not None else None),
            "producer_binding": policy_binding,
            "policy_artifact_sha256": (policy.policy_sha256 if policy else None),
            "acceptance_artifact_sha256": (policy.acceptance_sha256 if policy else None),
            "model_state": staged.trainer.core.state_dict(),
            "optimizer_state": staged.optimizer.state_dict(),
            "optimizer_audit": audit_phase_optimizer(
                staged.trainer.core, staged.trainer.backbone, staged.optimizer, phase),
            "optimizer_groups": optimizer_group_manifest(staged.optimizer),
            "training_state": {"optimizer_steps": staged.trainer.optimizer_steps,
                               "articles_seen": staged.trainer.articles_seen,
                               "target_passes": staged.target_passes,
                               "completed_passes": completed_passes,
                               "article_position": article_position,
                               "skipped_steps": staged.skipped_steps,
                               "cumulative_clipped_count": staged.trainer.cumulative_clipped_count},
            "sampler_state": {"article_ids": list(article_ids),
                              "target_passes": staged.target_passes,
                              "completed_passes": completed_passes,
                              "article_position": article_position,
                              "cursor": staged.trainer.articles_seen},
            "rng_state": capture_rng(), "step_logs": list(staged.step_logs)}
    if phase.phase != "extraction":
        payload["repository_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
            text=True).strip()
        payload["relevant_code_snapshot"] = training_code_snapshot()
    expected_fields = (CHECKPOINT_FIELDS if phase.phase == "extraction"
                       else GOLD_ONLY_CHECKPOINT_FIELDS)
    if set(payload) != expected_fields:
        raise AssertionError("phase checkpoint field inventory differs")
    return payload


def save_phase_checkpoint(path: str | Path, staged: StagedTrainer, reader: TrainGoldReader | R06GoldReader,
                          article_ids: tuple[str, ...], *, parent_sha256: str | None,
                          policy_paths: tuple[str | Path, str | Path] | None) -> dict:
    payload = phase_checkpoint_payload(staged, reader, article_ids,
                                       parent_sha256=parent_sha256,
                                       policy_paths=policy_paths)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(target)
    return {"path": str(target.resolve()), "sha256": _file_sha(target),
            "phase": staged.phase.phase, "parent_checkpoint_sha256": parent_sha256,
            "producer_binding": payload["producer_binding"],
            "data_snapshot_sha256": _digest(payload["data_snapshot"])}


def load_phase_checkpoint(path: str | Path, *, expected_phase: str,
                          base: HarnessConfig, reader: TrainGoldReader | R06GoldReader,
                          article_ids: tuple[str, ...],
                          expected_parent_sha256: str | None,
                          expected_parent_selection: SelectedParentBinding | None = None,
                          expected_profile: str = "V3_WINDOW",
                          expected_passes: int | None = None,
                          expected_policy: SourceFunnelPolicy | None = None,
                          expected_entity_pair_policy: EntityPairPolicy | None = None,
                          expected_entity_pair_artifact_sha256: str | None = None,
                          expected_relation_routing_artifact: PredictedRelationRoutingArtifact | None = None,
                          expected_asserted_by_option_artifact_sha256: str | None = None,
                          expected_training_authority_binding_sha256: str | None = None,
                          expected_entity_stability_artifact_sha256: str | None = None,
                          expected_phase1_selection_support_sha256: str | None = None,
                          expected_phase1_selection_policy_sha256: str | None = None,
                          expected_event_head_migration_sha256: str | None = None,
                          expected_event_training_policy: str | None = None,
                          expected_legacy_code_snapshot: dict | None = None,
                          check_policy_bytes: bool = True) -> dict:
    if (expected_phase in ("event_identity", "cluster_consumers") and
            expected_event_head_migration_sha256 is None):
        raise ValueError("P5/P6 checkpoint load requires Event head migration SHA")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    phase = PhaseConfig.for_phase(expected_phase, base,
                                  source_profile=expected_profile,
                                  entity_pair_policy=expected_entity_pair_policy,
                                  entity_pair_policy_artifact_sha256=(
                                      expected_entity_pair_artifact_sha256),
                                  relation_routing_artifact=expected_relation_routing_artifact,
                                  asserted_by_option_artifact_sha256=(
                                      expected_asserted_by_option_artifact_sha256),
                                  training_authority_binding_sha256=(
                                      expected_training_authority_binding_sha256),
                                  entity_stability_artifact_sha256=(
                                      expected_entity_stability_artifact_sha256),
                                  phase1_selection_support_sha256=(
                                      expected_phase1_selection_support_sha256),
                                  phase1_selection_policy_sha256=(
                                      expected_phase1_selection_policy_sha256),
                                  event_head_migration_sha256=(
                                      expected_event_head_migration_sha256),
                                  event_training_policy=expected_event_training_policy)
    manifest = phase.manifest()
    format_version = payload.get("format_version") if isinstance(payload, dict) else None
    expected_fields = (CHECKPOINT_FIELDS if expected_phase == "extraction"
                       else GOLD_ONLY_CHECKPOINT_FIELDS)
    if (not isinstance(payload, dict) or set(payload) != expected_fields or
            format_version != _checkpoint_format(expected_phase) or
            (expected_phase != "extraction" and
             (payload.get("relevant_code_snapshot") != (
                 expected_legacy_code_snapshot if expected_phase ==
                 "entity_role_time_attribution" and expected_legacy_code_snapshot is not None
                 else training_code_snapshot()) or
              not isinstance(payload.get("repository_head"), str) or
              len(payload["repository_head"]) != 40)) or
            payload.get("phase") != expected_phase or
            payload.get("phase_manifest") != manifest or
            payload.get("base_config_sha256") != _digest(base.to_dict()) or
            payload.get("base_config") != base.to_dict() or
            payload.get("data_snapshot") != training_data_snapshot(reader, article_ids) or
            payload.get("parent_checkpoint_sha256") != expected_parent_sha256 or
            payload.get("parent_phase") != (TRAINING_PHASES[
                TRAINING_PHASES.index(expected_phase) - 1]
                if expected_phase != "extraction" else None) or
            (payload.get("parent_selected_record_sha256") is None) !=
            (payload.get("parent_selected_epoch") is None) or
            (expected_parent_selection is not None and (
                payload.get("parent_selected_record_sha256") !=
                expected_parent_selection.selection_record_sha256 or
                payload.get("parent_selected_epoch") !=
                expected_parent_selection.selected_epoch or
                expected_parent_sha256 != expected_parent_selection.checkpoint_sha256)) or
            (check_policy_bytes and payload.get("producer_binding") != (
                expected_policy.binding() if expected_policy else None)) or
            (check_policy_bytes and payload.get("policy_artifact_sha256") != (
                expected_policy.policy_sha256 if expected_policy else None)) or
            (check_policy_bytes and payload.get("acceptance_artifact_sha256") != (
                expected_policy.acceptance_sha256 if expected_policy else None))):
        raise ValueError("phase checkpoint/config/data/producer binding differs")
    record_sha = payload["parent_selected_record_sha256"]
    selected_epoch = payload["parent_selected_epoch"]
    if ((expected_phase == "extraction" and record_sha is not None) or
            (record_sha is not None and
         (not isinstance(record_sha, str) or len(record_sha) != 64 or
          any(char not in "0123456789abcdef" for char in record_sha) or
          type(selected_epoch) is not int or selected_epoch < 1)) or
            (expected_phase != "extraction" and
             expected_training_authority_binding_sha256 is not None and
             record_sha is None)):
        raise ValueError("phase checkpoint selected-parent lineage differs")
    state = payload["training_state"]
    if (not isinstance(state, dict) or
            set(state) != {"optimizer_steps", "articles_seen", "cumulative_clipped_count",
                           "target_passes", "completed_passes", "article_position", "skipped_steps"} or
            any(type(value) is not int or value < 0 for value in state.values())):
        raise ValueError("phase checkpoint sampler/optimizer state differs")
    minimum_steps = (state["completed_passes"] *
                     ((len(article_ids) + base.gradient_accumulation_articles - 1) //
                      base.gradient_accumulation_articles) +
                     (state["article_position"] + base.gradient_accumulation_articles - 1) //
                     base.gradient_accumulation_articles)
    if (state["target_passes"] < 1
            or (expected_passes is not None and state["target_passes"] != expected_passes)
            or state["articles_seen"] != (state["completed_passes"] * len(article_ids) +
                                          state["article_position"])
            or state["completed_passes"] > state["target_passes"]
            or state["article_position"] >= len(article_ids)
            or (state["completed_passes"] == state["target_passes"] and
                state["article_position"] != 0)
            or payload["sampler_state"] != {"article_ids": list(article_ids),
                                            "target_passes": state["target_passes"],
                                            "completed_passes": state["completed_passes"],
                                            "article_position": state["article_position"],
                                            "cursor": state["articles_seen"]}
            or state["articles_seen"] > len(article_ids) * state["target_passes"]
            or not minimum_steps <= state["optimizer_steps"] + state["skipped_steps"] <= state["articles_seen"]
            or not isinstance(payload["optimizer_groups"], list)
            or payload["optimizer_groups"] != [
                {key: group[key] for key in ("name", "lr", "weight_decay",
                                             "param_names", "param_shapes")}
                for group in payload["optimizer_state"]["param_groups"]]):
        raise ValueError("phase checkpoint sampler/optimizer state differs")
    step_logs = payload["step_logs"]
    if (not isinstance(step_logs, list) or
            len(step_logs) != state["optimizer_steps"] + state["skipped_steps"]):
        raise ValueError("phase checkpoint step ledger differs")
    exposures = 0
    for group, row in enumerate(step_logs, 1):
        if (not isinstance(row, dict) or row.get("phase") != expected_phase or
                not isinstance(row.get("articles"), list) or not row["articles"] or
                len(row["articles"]) > base.gradient_accumulation_articles):
            raise ValueError("phase checkpoint step ledger differs")
        start = exposures % len(article_ids)
        if row["articles"] != list(article_ids[start:start + len(row["articles"])]):
            raise ValueError("phase checkpoint step article order differs")
        exposures += len(row["articles"])
        if row.get("article_exposures") != exposures or (
                row.get("optimizer_steps", 0) + row.get("skipped_steps", 0) != group):
            raise ValueError("phase checkpoint step ledger differs")
    if exposures != state["articles_seen"]:
        raise ValueError("phase checkpoint step exposure differs")
    if not check_policy_bytes:
        binding = payload.get("producer_binding")
        if expected_phase == "extraction":
            if binding is not None:
                raise ValueError("Extraction parent unexpectedly has a producer")
        elif payload.get("format_version") in (GOLD_ONLY_FORMAT_VERSION,
                                                 EVENT_HEAD_FORMAT_VERSION):
            if (binding is not None or payload.get("policy_artifact_sha256") is not None or
                    payload.get("acceptance_artifact_sha256") is not None):
                raise ValueError("Gold-only parent carries predicted evaluator artifacts")
        elif (not isinstance(binding, dict) or
              binding.get("checkpoint_sha256") != expected_parent_sha256 or
              binding.get("policy_sha256") != payload.get("policy_artifact_sha256") or
              binding.get("source_acceptance_artifact_sha256") !=
              payload.get("acceptance_artifact_sha256")):
            raise ValueError("parent checkpoint has inconsistent producer binding")
    return payload


def start_phase(*, phase: str, base: HarnessConfig,
                reader: TrainGoldReader | R06GoldReader, article_ids: tuple[str, ...],
                parent_path: str | Path | None = None,
                parent_selection_path: str | Path | None = None,
                policy_paths: tuple[str | Path, str | Path] | None = None,
                resume_path: str | Path | None = None,
                target_passes: int = 1,
                candidate_profile: str = "V23_BASELINE",
                entity_pair_policy_path: str | Path | None = None,
                relation_routing_policy_path: str | Path | None = None,
                asserted_by_option_policy_path: str | Path | None = None,
                entity_stability_policy_path: str | Path | None = None,
                entity_stability_report_path: str | Path | None = None,
                training_authority_binding_sha256: str | None = None,
                training_authority_binding_path: str | Path | None = None,
                training_authority_provenance_path: str | Path | None = None,
                phase1_selection_support_sha256: str | None = None,
                phase1_selection_policy_sha256: str | None = None,
                gold400_input_manifest_path: str | Path | None = None,
                event_head_migration_path: str | Path | None = None,
                event_training_policy: str | None = None,
                participant_salience_mode: str = "SOURCE_SCORE",
                mini_rehearsal: bool = False,
                device: str = "cpu") -> tuple[StagedTrainer, str | None]:
    """Load the immediate predecessor for Gold-only student training."""
    if type(target_passes) is not int or target_passes < 1:
        raise ValueError("phase passes must be positive")
    if ((phase in ("event_identity", "cluster_consumers")) !=
            (event_head_migration_path is not None)):
        raise ValueError("P5/P6 require the same explicit P4 Event-head migration artifact")
    if event_training_policy is not None and (
            phase not in ("event_identity", "cluster_consumers") or
            not isinstance(reader, R06GoldReader) or len(reader.gold) != 400):
        raise ValueError("Event 8:1 comparison policy applies only to Gold400 P5/P6")
    index = TRAINING_PHASES.index(phase)
    if (index == 0 and (parent_path is not None or parent_selection_path is not None or
                        policy_paths is not None)) or (
            index > 0 and (parent_path is None and parent_selection_path is None or
                           policy_paths is not None)):
        raise ValueError("Gold-only downstream phase needs only its immediate parent")
    if any(path is not None for path in (
            entity_pair_policy_path, relation_routing_policy_path,
            asserted_by_option_policy_path, entity_stability_policy_path,
            entity_stability_report_path)):
        raise ValueError("predicted evaluator artifacts cannot gate Gold-only training")
    if participant_salience_mode != "SOURCE_SCORE":
        raise ValueError("Participant salience mode is retired with role_entity resolution")
    if isinstance(reader, R06GoldReader) and training_authority_binding_sha256 is None:
        raise ValueError("r06 staged training requires approved training-authority binding")
    if (training_authority_binding_path is None) != (training_authority_binding_sha256 is None):
        raise ValueError("training-authority binding path/SHA differ")
    if (training_authority_binding_path is not None and
            _file_sha(training_authority_binding_path) != training_authority_binding_sha256):
        raise ValueError("training-authority binding bytes drifted")
    if isinstance(reader, R06GoldReader):
        gold400 = len(reader.gold) == 400
        if mini_rehearsal and gold400:
            raise ValueError("three-epoch mini rehearsal is Gold100 only")
        if gold400:
            from training.v3_pretraining.gold400_authority import binding_sha256
            from training.v3_pretraining.gold400_schedule import validate_epochs
            if gold400_input_manifest_path is None:
                raise ValueError("Gold400 requires frozen input manifest")
            validate_epochs(target_passes)
        else:
            if mini_rehearsal:
                from training.v3_pretraining.mini_rehearsal_contract import (
                    MAX_EPOCHS, binding_sha256)
                if target_passes != MAX_EPOCHS:
                    raise ValueError("Gold100 mini rehearsal requires exactly three epochs")
            else:
                from training.v3_pretraining.training_authority import binding_sha256
                validate_main_training_epochs(target_passes)
        if phase == "extraction" and phase1_selection_support_sha256 is None:
            raise ValueError("r06 Phase 1 requires fixed dev Extraction selection support")
        if (candidate_profile != "V23_BASELINE" or
                base.negative_authority_path is None or
                training_authority_provenance_path is None or
                (binding_sha256(training_authority_binding_path,
                                gold_path=reader.gold_path,
                                authority_path=base.negative_authority_path,
                                provenance_path=training_authority_provenance_path,
                                input_manifest_path=gold400_input_manifest_path,
                                train_article_count=len(article_ids)) if gold400 else
                 (binding_sha256(training_authority_binding_path,
                                 gold_path=reader.gold_path, split_path=reader.split_path,
                                 source_path=reader.source_path,
                                 negative_path=base.negative_authority_path,
                                 provenance_path=training_authority_provenance_path,
                                 prior_approved_path=Path(__file__).resolve().parents[2] /
                                     "docs/v3-pretraining/r06-train73-max6-unified-entity-main-training-authority-binding.json",
                                 dev_selection_authority_path=Path(__file__).resolve().parents[2] /
                                     "training/results/v3-gold100-phase1-max6-v1/selection-support-authority.json",
                                 train_article_count=len(article_ids)) if mini_rehearsal else
                  binding_sha256(training_authority_binding_path,
                                 gold_path=reader.gold_path, split_path=reader.split_path,
                                 source_path=reader.source_path,
                                 authority_path=base.negative_authority_path,
                                 provenance_path=training_authority_provenance_path,
                                 train_article_count=len(article_ids)))) !=
                training_authority_binding_sha256):
            raise ValueError("r06 main-training authority/profile/schedule differs")
    parent_selection = None
    if index and (isinstance(reader, R06GoldReader) or parent_selection_path is not None):
        selection_path = (Path(parent_selection_path) if parent_selection_path is not None
                          else Path(parent_path).resolve().parent.parent /
                          "selected-checkpoint.json")
        parent_path, parent_selection = resolve_selected_parent(
            selection_record_path=selection_path,
            predecessor_phase=TRAINING_PHASES[index - 1],
            supplied_parent_path=parent_path,
            gold400=isinstance(reader, R06GoldReader) and len(reader.gold) == 400)
    parent_sha = _file_sha(parent_path) if parent_path is not None else None
    parent = None
    student_core = fresh_full_core(base, device=device)
    migration_sha = None
    legacy_selection_snapshot_sha = None
    if index:
        parent_header = torch.load(parent_path, map_location="cpu", weights_only=True)
        parent_manifest = parent_header.get("phase_manifest", {})
        if not isinstance(parent_manifest, dict):
            raise ValueError("parent phase manifest differs")
        if parent_manifest.get("training_authority_binding_sha256") != training_authority_binding_sha256:
            raise ValueError("parent training-authority binding differs")
        if phase == "event_identity":
            from training.v3_pretraining.event_head_migration import load_migration_artifact
            migration, migration_sha = load_migration_artifact(
                event_head_migration_path, parent_path=parent_path, core=student_core)
            legacy_selection_snapshot_sha = migration.get(
                "legacy_selection_code_snapshot_sha256")
        elif phase == "cluster_consumers":
            migration_sha = _file_sha(event_head_migration_path)
            if parent_manifest.get("event_head_migration_sha256") != migration_sha:
                raise ValueError("P6 migration lineage differs from selected P5 parent")
        parent = load_phase_checkpoint(
            parent_path, expected_phase=TRAINING_PHASES[index - 1],
            base=base, reader=reader, article_ids=article_ids,
            expected_profile=candidate_profile,
            expected_training_authority_binding_sha256=training_authority_binding_sha256,
            expected_phase1_selection_support_sha256=(
                parent_manifest.get("phase1_selection_support_sha256") if index == 1 else None),
            expected_phase1_selection_policy_sha256=(
                parent_manifest.get("phase1_selection_policy_sha256") if index == 1 and
                isinstance(reader, R06GoldReader) and
                (len(reader.gold) == 400 or mini_rehearsal) else None),
            expected_event_head_migration_sha256=(migration_sha if index == 5 else None),
            expected_event_training_policy=(event_training_policy if index == 5 else None),
            expected_legacy_code_snapshot=(parent_header["relevant_code_snapshot"]
                                           if phase == "event_identity" else None),
            expected_parent_sha256=(None if index == 1 else
                                    parent_header.get("parent_checkpoint_sha256")),
            check_policy_bytes=False)
        selected_mini_parent = (
            mini_rehearsal and parent_selection is not None and
            parent["training_state"]["completed_passes"] ==
            parent_selection.selected_epoch and
            parent_selection.checkpoint_sha256 == parent_sha)
        if ((parent["training_state"]["completed_passes"] != parent["training_state"]["target_passes"]
             and not selected_mini_parent
             and not (isinstance(reader, R06GoldReader) and len(reader.gold) == 400 and
                      _gold400_parent_selected(
                          parent_path, parent["training_state"]["completed_passes"],
                          selection_snapshot_sha256=legacy_selection_snapshot_sha))) or
                parent["training_state"]["article_position"] != 0 or
                parent["training_state"]["optimizer_steps"] == 0):
            raise ValueError("preceding DAG phase is incomplete or made no update")
    phase_config = PhaseConfig.for_phase(
        phase, base, source_profile=candidate_profile,
        training_authority_binding_sha256=training_authority_binding_sha256,
        phase1_selection_support_sha256=phase1_selection_support_sha256,
        phase1_selection_policy_sha256=phase1_selection_policy_sha256,
        event_head_migration_sha256=migration_sha,
        event_training_policy=event_training_policy)
    if parent is not None:
        if phase == "event_identity":
            from training.v3_pretraining.event_head_migration import (
                CONTINUITY_SCHEMA, migrate_event_head_state)
            state = (parent["model_state"] if migration["schema_version"] == CONTINUITY_SCHEMA
                     else migrate_event_head_state(parent["model_state"], student_core))
            student_core.load_state_dict(state, strict=True)
        else:
            student_core.load_state_dict(parent["model_state"], strict=True)
    student_backbone = load_pinned_backbone(student_core, device=device)
    configure_phase(student_core, phase_config)
    optimizer = build_phase_optimizer(student_core, student_backbone, base, phase_config)
    tokenizer, digest, _ = load_pinned_fast_tokenizer()
    trainer = V3Trainer(student_core, student_backbone, base, tokenizer=tokenizer,
                        extraction_profile=candidate_profile)
    staged = StagedTrainer(trainer, phase_config, optimizer,
                           article_ids=article_ids, target_passes=target_passes,
                           training_authority_binding_path=training_authority_binding_path,
                           parent_selection=parent_selection)
    if resume_path is not None:
        resumed = load_phase_checkpoint(
            resume_path, expected_phase=phase, base=base, reader=reader,
            article_ids=article_ids, expected_parent_sha256=parent_sha,
            expected_parent_selection=parent_selection,
            expected_profile=candidate_profile,
            expected_passes=target_passes,
            expected_training_authority_binding_sha256=training_authority_binding_sha256,
            expected_phase1_selection_support_sha256=phase1_selection_support_sha256,
            expected_phase1_selection_policy_sha256=phase1_selection_policy_sha256,
            expected_event_head_migration_sha256=migration_sha,
            expected_event_training_policy=event_training_policy)
        trainer.core.load_state_dict(resumed["model_state"], strict=True)
        expected_groups = optimizer_group_manifest(optimizer)
        if resumed["optimizer_groups"] != expected_groups:
            raise ValueError("resume optimizer LR/owner/shape policy differs")
        optimizer.load_state_dict(resumed["optimizer_state"])
        if audit_phase_optimizer(trainer.core, trainer.backbone, optimizer, phase_config) != resumed["optimizer_audit"]:
            raise ValueError("resumed phase optimizer ownership differs")
        state = resumed["training_state"]
        trainer.optimizer_steps = state["optimizer_steps"]
        trainer.articles_seen = state["articles_seen"]
        staged.skipped_steps = state["skipped_steps"]
        staged.step_logs = resumed["step_logs"]
        trainer.cumulative_clipped_count = state["cumulative_clipped_count"]
        restore_rng(resumed["rng_state"])
    return staged, parent_sha
