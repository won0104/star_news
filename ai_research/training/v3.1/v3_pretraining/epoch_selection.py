"""Gold-only, threshold-free dev selection for downstream staged phases.

Prepared Gold layouts and frozen backbone views are reused across epochs. Each
article still runs one current-checkpoint DCE forward; no predicted producer,
runtime routing, calibration, optimizer, or backward graph enters this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import resource
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Sequence

import torch

from models.v3_pretraining.frozen_features import (
    FrozenBackboneFeatureBuilder, RunLocalFrozenFeatureCache)
from models.v3_pretraining.task_contract import PHASE_TASKS
from runtime.v3_pretraining.event_features import finalize_cluster_features
from runtime.v3_pretraining.handoff import FrozenSourceViewKey
from training.v3_pretraining.code_snapshot import selection_code_snapshot
from training.v3_pretraining.harness import V3Trainer
from training.v3_pretraining.optimization_contract import reduce_active_task_losses
from training.v3_pretraining.targets import ValidatedGoldArticle


SELECTION_CONTRACT_VERSION = "v3-downstream-gold-epoch-selection-v3-unified-entity-no-priority"
DOWNSTREAM_PHASES = tuple(name for name in PHASE_TASKS if name != "extraction")


@dataclass(frozen=True, slots=True)
class PreparedDevArticle:
    article: ValidatedGoldArticle
    target: Any
    batch: Any
    cache_key: FrozenSourceViewKey
    preparation_seconds: float


class PhaseEpochSelectionEvaluator:
    """One fixed dev cohort and one run-local backbone cache across epochs."""

    def __init__(self, trainer: V3Trainer, phase: str,
                 articles: Sequence[ValidatedGoldArticle], *,
                 use_backbone_cache: bool = True) -> None:
        if phase not in DOWNSTREAM_PHASES or not articles or any(
                row.split != "dev" for row in articles):
            raise ValueError("downstream epoch selection requires dev-only articles")
        ids = tuple(row.raw.article_id for row in articles)
        if len(ids) != len(set(ids)):
            raise ValueError("epoch selection article IDs must be unique")
        self.trainer = trainer
        self.phase = phase
        self.representation_device = str(trainer.device)
        self.use_backbone_cache = use_backbone_cache
        self.backbone_cache = (RunLocalFrozenFeatureCache()
                               if use_backbone_cache else None)
        self.features = FrozenBackboneFeatureBuilder(
            trainer.backbone, cache=self.backbone_cache)
        self.prepared = []
        for article in articles:
            started = perf_counter()
            target = trainer.compiler.compile(article)
            windows = trainer.collator([target]).windows
            key = FrozenSourceViewKey.from_config(
                article.raw, windows, backbone=trainer.core.config.backbone,
                tokenizer_sha256=trainer.tokenizer_sha256,
                dtype=trainer.core.config.dtype, source_view="all")
            batch = windows.article_view(article.raw, view="all").to(trainer.device)
            self.prepared.append(PreparedDevArticle(
                article, target, batch, key, perf_counter() - started))
        self.dev_ids_sha256 = sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def phase_losses(trainer: V3Trainer, phase: str, row: PreparedDevArticle,
                     frozen, shared
                     ) -> tuple[dict[str, torch.Tensor], dict[str, bool],
                                dict[str, float]]:
        """Compute only this phase's Gold heads; shared by train and raw dev."""
        article, target, batch = row.article, row.target, row.batch
        losses: dict[str, torch.Tensor] = {}
        active: dict[str, bool] = {}
        stage_seconds: dict[str, float] = {}
        if phase == "entity_identity":
            lanes = frozenset(("entity_coreference",))
            started = perf_counter()
            entity = trainer.entity.loss(article, target, batch, frozen, shared,
                                         channels=lanes)
            stage_seconds["entity_gold_features_and_heads"] = perf_counter() - started
            for name in lanes:
                losses[name] = entity.losses[name]
            active.update({
                "entity_coreference": (entity.coref_positive_pairs +
                                       entity.coref_sampled_negative_pairs > 0),
            })
        if phase == "entity_identity":
            return losses, {name: active[name] for name in PHASE_TASKS[phase]}, stage_seconds
        if phase == "entity_role_time_attribution_sources":
            extra = [("STATEMENT:" + item.owner_id, item.alignment, "STATEMENT")
                     for item in target.spans["semantic_proposer"]
                     if item.label == "STATEMENT"]
            extra.extend(("ASSERTOR:" + item.statement_id, item.alignment,
                          "STATEMENT") for item in target.assertors
                         if item.alignment is not None)
            started = perf_counter()
            time_features = trainer.time.encode(
                target, batch, frozen, shared, extra_rows=tuple(extra))
            stage_seconds["time_and_assertor_feature_encode"] = perf_counter() - started
            with time_features:
                started = perf_counter()
                time = trainer.time.loss(target, time_features)
                stage_seconds["time_heads"] = perf_counter() - started
                losses.update(time.losses)
                started = perf_counter()
                losses["assertor_source"] = trainer.attribution.assertor_source_loss_batched(
                    target, time_features, shared)
                stage_seconds["assertor_source_head"] = perf_counter() - started
                active.update({
                    "time_normalization": time.normalized_supervised > 0,
                    "event_time": time.attachment_positive + time.attachment_negative_sampled > 0,
                    "assertor_source": any(item.source_mask in (
                        "SUPERVISE", "NO_EXPLICIT_SOURCE") for item in target.assertors),
                })
            return losses, {name: active[name] for name in PHASE_TASKS[phase]}, stage_seconds
        started = perf_counter()
        features = trainer.event.prepare(
            article, target, batch, frozen, shared,
            include_relations=phase != "event_identity")
        stage_seconds["event_gold_feature_prepare"] = perf_counter() - started
        with features:
            if phase == "event_identity":
                started = perf_counter()
                event = trainer.event.loss(target, features)
                stage_seconds["event_identity_head"] = perf_counter() - started
                return {"event_coreference": event.loss}, {
                    "event_coreference": event.positive_pairs + event.negative_pairs_sampled > 0}, stage_seconds
            started = perf_counter()
            final = finalize_cluster_features(features.member, features.closure)
            stage_seconds["final_cluster_feature_prepare"] = perf_counter() - started
            try:
                lanes = (frozenset(("assertor_entity",))
                         if phase == "entity_role_time_attribution" else
                         frozenset(("about", "causes")))
                started = perf_counter()
                attribution = trainer.attribution.loss(
                    article, target, features, final, shared, channels=lanes)
                stage_seconds["attribution_heads"] = perf_counter() - started
                losses.update({name: attribution.losses[name] for name in lanes})
                active.update({
                    "assertor_entity": (attribution.assertor_entity_positive +
                                        attribution.assertor_entity_negative_sampled > 0),
                    "about": attribution.about_positive + attribution.about_negative_sampled > 0,
                    "causes": attribution.causes_positive + attribution.causes_negative_sampled > 0,
                })
                if phase == "cluster_consumers":
                    started = perf_counter()
                    primary = trainer.primary.loss(article, target, features, final)
                    stage_seconds["primary_head"] = perf_counter() - started
                    losses["primary"] = primary.loss
                    active["primary"] = primary.strict_pairs_sampled > 0
                return losses, {name: active[name] for name in PHASE_TASKS[phase]}, stage_seconds
            finally:
                for consumer in tuple(sorted(final.pending_consumers)):
                    final.release(consumer)

    def _oracle_losses(self, row: PreparedDevArticle, frozen, shared
                       ) -> tuple[dict[str, torch.Tensor], dict[str, bool],
                                  dict[str, float]]:
        return self.phase_losses(self.trainer, self.phase, row, frozen, shared)

    @torch.no_grad()
    def evaluate_epoch(self, *, epoch: int, checkpoint_sha256: str) -> dict[str, Any]:
        """Return a fixed Gold loss selection metric, with measured article costs."""
        if (epoch < 1 or len(checkpoint_sha256) != 64 or
                any(char not in "0123456789abcdef" for char in checkpoint_sha256)):
            raise ValueError("epoch selection checkpoint binding differs")
        trainer = self.trainer
        if (str(trainer.device) != self.representation_device or
                any(str(row.batch.input_ids.device) != self.representation_device
                    for row in self.prepared)):
            raise ValueError("epoch backbone cache execution device differs")
        trainer.core.eval()
        trainer.backbone.eval()
        rows = []
        for prepared in self.prepared:
            calls = {"backbone": 0, "dce": 0}
            scorer_calls: dict[str, int] = {}
            scorer_seconds: dict[str, float] = {}
            scorer_starts: dict[str, list[float]] = {}
            hooks = [trainer.backbone.register_forward_hook(
                lambda *_: calls.__setitem__("backbone", calls["backbone"] + 1)),
                trainer.core.document_context.register_forward_hook(
                    lambda *_: calls.__setitem__("dce", calls["dce"] + 1))]
            modules = {**dict(trainer.core.task_modules),
                       "exact_source_span": trainer.core.exact_source_span,
                       "candidate_span": trainer.core.candidate_span}
            for name, module in modules.items():
                scorer_starts[name] = []
                hooks.append(module.register_forward_pre_hook(
                    lambda *_args, name=name: scorer_starts[name].append(perf_counter())))
                def finished(_module, _args, _result, *, name=name):
                    scorer_calls[name] = scorer_calls.get(name, 0) + 1
                    scorer_seconds[name] = (scorer_seconds.get(name, 0.0) +
                                            perf_counter() - scorer_starts[name].pop())
                hooks.append(module.register_forward_hook(finished))
            try:
                started = perf_counter()
                frozen = self.features.build(
                    prepared.batch,
                    cache_key=prepared.cache_key if self.use_backbone_cache else None,
                    scope="epoch-selection")
                backbone_seconds = perf_counter() - started
                started = perf_counter()
                with trainer.core.forward_shared(prepared.batch, frozen) as shared:
                    dce_seconds = perf_counter() - started
                    started = perf_counter()
                    losses, active, stages = self._oracle_losses(prepared, frozen, shared)
                    head_seconds = perf_counter() - started
                started = perf_counter()
                if set(losses) != set(PHASE_TASKS[self.phase]) or set(active) != set(losses):
                    raise ValueError("epoch selection loss inventory differs")
                loss = reduce_active_task_losses(
                    [SimpleNamespace(losses=losses, active=active)],
                    weights=trainer.config.loss_weights,
                    channels=PHASE_TASKS[self.phase])
                value = float(loss)
                if not math.isfinite(value):
                    raise ValueError("epoch selection Gold loss is nonfinite")
                metric_seconds = perf_counter() - started
            finally:
                for hook in hooks:
                    hook.remove()
            if (calls["dce"] != 1 or calls["backbone"] not in (0, 1) or
                    (not self.use_backbone_cache and calls["backbone"] != 1)):
                raise RuntimeError("epoch selection duplicated backbone/DCE")
            rows.append({
                "article_id": prepared.article.raw.article_id,
                "gold_loss": value,
                "active_losses": sorted(name for name, enabled in active.items() if enabled),
                "channel_losses": {name: float(losses[name]) for name in losses},
                "backbone_calls": calls["backbone"], "dce_calls": calls["dce"],
                "scorer_forward_calls": scorer_calls,
                "scorer_seconds": scorer_seconds,
                "phase_stage_seconds": stages,
                "profile_seconds": {
                    "article_preparation_once": prepared.preparation_seconds,
                    "backbone_or_cache": backbone_seconds,
                    "dce_shared": dce_seconds, "phase_heads": head_seconds,
                    "metric_accumulation": metric_seconds,
                    "total_per_epoch": backbone_seconds + dce_seconds +
                                       head_seconds + metric_seconds},
            })
        scored = [row["gold_loss"] for row in rows if row["active_losses"]]
        if not scored:
            raise ValueError("NO_SELECTABLE_PHASE_CHECKPOINT")
        cache = self.backbone_cache.snapshot() if self.backbone_cache is not None else None
        return {
            "schema_version": SELECTION_CONTRACT_VERSION,
            "mode": "EPOCH_SELECTION_EVALUATOR",
            "phase": self.phase, "epoch": epoch,
            "checkpoint_sha256": checkpoint_sha256,
            "dev_ids_sha256": self.dev_ids_sha256,
            "selection_code_snapshot_sha256": selection_code_snapshot()["sha256"],
            "selection_metric": -sum(scored) / len(scored),
            "selection_metric_name": "NEGATIVE_MEAN_ACTIVE_GOLD_ORACLE_LOSS",
            "calibrated_thresholds_used": False,
            "predicted_runtime_executed": False,
            "test_access_count": 0,
            "backbone_cache": cache,
            "dce_cache_enabled": False,
            "representation_device": self.representation_device,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "mps_allocated_bytes": (torch.mps.current_allocated_memory()
                                    if trainer.device.type == "mps" else None),
            "articles": rows,
        }


def select_completed_epochs(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Choose the maximum fixed Gold metric; earliest epoch breaks exact ties."""
    if not records or [row.get("epoch") for row in records] != list(
            range(1, len(records) + 1)):
        raise ValueError("completed downstream epoch inventory differs")
    phase = records[0].get("phase")
    ids_sha = records[0].get("dev_ids_sha256")
    code_sha = selection_code_snapshot()["sha256"]
    if any(row.get("schema_version") != SELECTION_CONTRACT_VERSION or
           row.get("phase") != phase or row.get("dev_ids_sha256") != ids_sha or
           row.get("selection_code_snapshot_sha256") != code_sha or
           row.get("calibrated_thresholds_used") is not False or
           row.get("predicted_runtime_executed") is not False or
           row.get("test_access_count") != 0 or
           not isinstance(row.get("selection_metric"), (int, float)) or
           not math.isfinite(row["selection_metric"])
           for row in records):
        raise ValueError("downstream epoch selection contract differs")
    best = max(records, key=lambda row: (row["selection_metric"], -row["epoch"]))
    return {"schema_version": SELECTION_CONTRACT_VERSION,
            "phase": phase, "selected_epoch": best["epoch"],
            "selected_checkpoint_path": best["checkpoint_path"],
            "selected_checkpoint_sha256": best["checkpoint_sha256"],
            "selection_metric": best["selection_metric"],
            "dev_ids_sha256": ids_sha, "calibration_executed": False,
            "selection_code_snapshot_sha256": code_sha,
            "predicted_runtime_executed": False, "test_access_count": 0}
