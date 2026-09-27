"""Strict checkpoint boundary for the provisional 400/50/49 integration run."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import torch

from models.contracts import BackboneConfig, ContextConfig, TaskLayerPolicy
from models.v3_pretraining.architecture import V3ArchitectureConfig
from models.v3_pretraining.task_contract import HEAD_TASKS
from training.v3_pretraining.checkpoint import (capture_rng, label_mappings,
                                                relation_policy_from_config,
                                                restore_rng)
from training.v3_pretraining.corpus import ProvisionalGoldReader
from training.v3_pretraining.harness import (HarnessConfig, LOSS_CHANNELS,
                                             V3Trainer, audit_optimizer,
                                             build_optimizer, fresh_full_core,
                                             parameter_manifest)
from training.v3_pretraining.relation_sampling import validate_relation_training_metadata
from training.v3_pretraining.selection_contract import (
    selection_policy, validate_checkpoint_selection_contract)


FORMAT_VERSION = "v3-provisional-trained-checkpoint-v5-d8-b5-validated-selection"
MODE = "PROVISIONAL_TRAINED_INTEGRATION"
PROVISIONAL_CHECKPOINT_REQUIRED_FIELDS = frozenset({
    "format_version", "mode", "training_completed", "production_approved",
    "eligible_for_final_1k_warm_start", "run_id", "seed", "harness_config",
    "harness_config_sha256", "architecture_config", "architecture_config_sha256",
    "backbone", "tokenizer", "task_registry", "loss_channels", "label_mappings",
    "code_hashes", "parameter_manifest", "parameter_ownership_audit",
    "relation_training_metadata", "split_snapshot", "model_state", "optimizer_state",
    "scheduler_state", "scaler_state", "rng_state", "sampler_state", "training_state",
    "selection", "test_evaluation", "eval_reference",
})
DEFAULT_SELECTION_POLICY = selection_policy()
PROJECT = Path(__file__).resolve().parents[2]
CODE_PATHS = (
    "models/backbone.py",
    "models/v3_pretraining/architecture.py",
    "models/v3_pretraining/attribution_heads.py",
    "models/v3_pretraining/entity_heads.py",
    "models/v3_pretraining/event_heads.py",
    "models/v3_pretraining/extraction_heads.py",
    "models/v3_pretraining/frozen_features.py",
    "models/v3_pretraining/primary_head.py",
    "models/v3_pretraining/task_contract.py",
    "models/v3_pretraining/time_heads.py",
    "runtime/v3_pretraining/source_layout.py",
    "runtime/v3_pretraining/serving.py",
    "runtime/v3_pretraining/extraction_decode.py",
    "runtime/v3_pretraining/public_graph.py",
    "runtime/v3_pretraining/canonical_text.py",
    "training/v3_pretraining/targets.py",
    "training/v3_pretraining/attribution.py",
    "training/v3_pretraining/collator.py",
    "training/v3_pretraining/corpus.py",
    "training/v3_pretraining/entity.py",
    "training/v3_pretraining/event.py",
    "training/v3_pretraining/extraction.py",
    "training/v3_pretraining/harness.py",
    "training/v3_pretraining/evaluation.py",
    "training/v3_pretraining/primary.py",
    "training/v3_pretraining/relation_sampling.py",
    "training/v3_pretraining/relation_evaluation.py",
    "training/v3_pretraining/selection_contract.py",
    "training/v3_pretraining/selection_evaluation.py",
    "training/v3_pretraining/optimization_contract.py",
    "training/v3_pretraining/provisional_checkpoint.py",
    "training/v3_pretraining/time.py",
    "training/scripts/v3_provisional_integration.py",
    "training/scripts/v3_provisional_train.py",
    "training/scripts/v3_provisional_finalize_interrupted.py",
)


def file_digest(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def json_digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def code_hashes() -> dict[str, str]:
    return {name: file_digest(PROJECT / name) for name in CODE_PATHS}


def _cpu_tree(value: Any) -> Any:
    """Detach checkpoint tensor payloads from CPU/MPS execution placement."""
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {key: _cpu_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cpu_tree(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_cpu_tree(item) for item in value)
    return value


def _selection_policy(value: Mapping[str, Any] | None) -> dict[str, Any]:
    policy = dict(DEFAULT_SELECTION_POLICY if value is None else value)
    if policy != DEFAULT_SELECTION_POLICY:
        raise ValueError("provisional checkpoint selection policy is invalid")
    return policy


def _capture_provisional_rng(device: torch.device) -> dict[str, Any]:
    state = capture_rng()
    if device.type == "mps":
        state["torch_mps"] = torch.mps.get_rng_state().cpu()
    return state


def _restore_provisional_rng(value: Mapping[str, Any], device: torch.device) -> None:
    allowed = {"python", "numpy", "torch_cpu", "torch_cuda", "torch_mps"}
    if not set(value) <= allowed or not {"python", "numpy", "torch_cpu", "torch_cuda"} <= set(value):
        raise ValueError("provisional checkpoint RNG state is incomplete")
    restore_rng({key: value[key] for key in ("python", "numpy", "torch_cpu", "torch_cuda")})
    if device.type == "mps":
        if "torch_mps" not in value:
            raise ValueError("MPS resume requires an MPS RNG state")
        torch.mps.set_rng_state(value["torch_mps"])


def split_snapshot(reader: ProvisionalGoldReader,
                   train_exposure: tuple[str, ...]) -> dict[str, Any]:
    expected = reader.ids("train")
    if tuple(sorted(train_exposure)) != tuple(sorted(expected)):
        raise ValueError("provisional checkpoint must expose all and only 400 train articles")
    return {
        "manifest_path": str(reader.manifest_path.resolve()),
        "manifest_sha256": file_digest(reader.manifest_path),
        "counts": {split: len(reader.ids(split)) for split in ("train", "dev", "test")},
        "train_exposure": [dict(reader.rows[aid]) for aid in train_exposure],
    }


def save_provisional_checkpoint(
        path: str | Path, trainer: V3Trainer, optimizer: torch.optim.Optimizer, *,
        reader: ProvisionalGoldReader, train_exposure: tuple[str, ...], epoch: int,
        sampler_state: Mapping[str, Any], epoch_history: list[dict[str, Any]],
        best_epoch: int, best_dev_loss: float, patience_count: int,
        training_completed: bool, stop_reason: str | None,
        test_evaluation: Mapping[str, Any], eval_reference: Mapping[str, Any],
        selection_policy: Mapping[str, Any] | None = None,
        selection_contract: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Atomically save one complete epoch-boundary state; mid-group states are rejected."""
    if epoch <= 0 or sampler_state.get("group_remainder") != 0:
        raise ValueError("provisional checkpoint requires a completed epoch/group boundary")
    if selection_contract is None:
        raise ValueError("D8 provisional checkpoint requires selection metadata")
    if training_completed != (stop_reason is not None):
        raise ValueError("provisional completion and stop reason differ")
    config = trainer.config.to_dict()
    architecture = asdict(trainer.core.config)
    split = split_snapshot(reader, train_exposure)
    policy = _selection_policy(selection_policy)
    selection = validate_checkpoint_selection_contract(
        selection_contract, expected_epoch=epoch)
    if selection["selection_policy"] != policy:
        raise ValueError("D8 checkpoint policy and selection metadata differ")
    clip_summary = selection["gradient_clipping_summary"]
    if (clip_summary["cumulative_clipped_count"]
            != trainer.cumulative_clipped_count
            or (trainer.optimizer_steps > 0 and clip_summary["groups"] <= 0)):
        raise ValueError("D8 checkpoint clipping summary differs from trainer state")
    payload = {
        "format_version": FORMAT_VERSION,
        "mode": MODE,
        "training_completed": training_completed,
        "production_approved": False,
        "eligible_for_final_1k_warm_start": False,
        "run_id": trainer.config.run_id,
        "seed": trainer.config.seed,
        "harness_config": config,
        "harness_config_sha256": json_digest(config),
        "architecture_config": architecture,
        "architecture_config_sha256": trainer.core.config.fingerprint(),
        "backbone": {"model_id": trainer.core.config.backbone.model_id,
                     "revision": trainer.core.config.backbone.revision,
                     "weights_sha256": trainer.core.config.backbone.expected_weights_sha256,
                     "stored_in_checkpoint": False},
        "tokenizer": {"revision": trainer.core.config.backbone.revision,
                      "sha256": trainer.core.config.tokenizer_sha256},
        "task_registry": list(HEAD_TASKS),
        "loss_channels": list(LOSS_CHANNELS),
        "label_mappings": label_mappings(),
        "code_hashes": code_hashes(),
        "parameter_manifest": list(parameter_manifest(trainer.core)),
        "parameter_ownership_audit": audit_optimizer(trainer.core, trainer.backbone, optimizer),
        "relation_training_metadata": trainer.relation_training_metadata(),
        "split_snapshot": split,
        "model_state": _cpu_tree(trainer.core.state_dict()),
        "optimizer_state": _cpu_tree(optimizer.state_dict()),
        "scheduler_state": {"kind": "NONE", "state": None},
        "scaler_state": {"kind": "NONE_FP32", "state": None},
        "rng_state": _capture_provisional_rng(trainer.device),
        "sampler_state": dict(sampler_state),
        "training_state": {"epoch": epoch,
                           "optimizer_steps": trainer.optimizer_steps,
                           "articles_seen": trainer.articles_seen,
                           "stop_reason": stop_reason,
                           "execution_device": trainer.device.type,
                           "dtype": "float32"},
        "selection": selection,
        "test_evaluation": dict(test_evaluation),
        "eval_reference": dict(eval_reference),
    }
    if set(payload) != PROVISIONAL_CHECKPOINT_REQUIRED_FIELDS:
        raise AssertionError("provisional checkpoint writer schema differs from strict loader")
    validate_relation_training_metadata(
        payload["relation_training_metadata"],
        expected_policy=relation_policy_from_config(trainer.config))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(target)
    return {"path": str(target.resolve()), "sha256": file_digest(target),
            "bytes": target.stat().st_size, "format_version": FORMAT_VERSION,
            "mode": MODE, "epoch": epoch, "optimizer_steps": trainer.optimizer_steps,
            "training_completed": training_completed,
            "split_snapshot_sha256": json_digest(split),
            "parameter_manifest_sha256": json_digest(payload["parameter_manifest"])}


def load_provisional_checkpoint(
        path: str | Path, backbone: torch.nn.Module, *,
        expected_run_id: str, expected_config_sha256: str,
        reader: ProvisionalGoldReader, tokenizer=None,
        restore_rng_state: bool = True,
        require_completed: bool = False,
        device: str | torch.device = "cpu",
        expected_selection_policy: Mapping[str, Any] | None = None,
        expected_selection_support_manifest_sha256: str | None = None,
        allow_cross_device_eval: bool = False) -> tuple[V3Trainer, torch.optim.Optimizer, dict[str, Any]]:
    """Strictly restore only this run's complete, current-code epoch-boundary payload."""
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if (not isinstance(payload, dict) or set(payload) != PROVISIONAL_CHECKPOINT_REQUIRED_FIELDS or
            payload.get("format_version") != FORMAT_VERSION or payload.get("mode") != MODE):
        raise ValueError("incomplete, old, or foreign provisional checkpoint")
    if payload["production_approved"] or payload["eligible_for_final_1k_warm_start"]:
        raise ValueError("provisional checkpoint promotion flags are invalid")
    if require_completed and not payload["training_completed"]:
        raise ValueError("provisional training has not completed")
    if payload["run_id"] != expected_run_id or payload["harness_config_sha256"] != expected_config_sha256:
        raise ValueError("provisional checkpoint run/config identity differs")
    config_data = payload["harness_config"]
    if set(config_data) != set(HarnessConfig.__dataclass_fields__) or json_digest(config_data) != expected_config_sha256:
        raise ValueError("provisional checkpoint config digest/shape differs")
    config = HarnessConfig(**config_data)
    config.validate()
    relation_articles = validate_relation_training_metadata(
        payload["relation_training_metadata"],
        expected_policy=relation_policy_from_config(config))
    if config.run_id != payload["run_id"] or config.seed != payload["seed"]:
        raise ValueError("provisional checkpoint seed differs")
    raw_architecture = payload["architecture_config"]
    architecture = V3ArchitectureConfig(
        run_id=raw_architecture["run_id"], seed=raw_architecture["seed"],
        backbone=BackboneConfig(**raw_architecture["backbone"]),
        context=ContextConfig(**raw_architecture["context"]),
        layers=TaskLayerPolicy(**raw_architecture["layers"]),
        tokenizer_sha256=raw_architecture["tokenizer_sha256"],
        layout_policy=raw_architecture["layout_policy"], dtype=raw_architecture["dtype"])
    if (json_digest(raw_architecture) != payload["architecture_config_sha256"] or
            architecture.fingerprint() != payload["architecture_config_sha256"]):
        raise ValueError("provisional checkpoint architecture differs")
    if (payload["task_registry"] != list(HEAD_TASKS) or
            payload["loss_channels"] != list(LOSS_CHANNELS) or
            payload["label_mappings"] != label_mappings() or
            payload["code_hashes"] != code_hashes()):
        raise ValueError("provisional task/label/code contract differs")
    expected_backbone = {"model_id": architecture.backbone.model_id,
                         "revision": architecture.backbone.revision,
                         "weights_sha256": architecture.backbone.expected_weights_sha256,
                         "stored_in_checkpoint": False}
    if payload["backbone"] != expected_backbone or payload["tokenizer"] != {
            "revision": architecture.backbone.revision,
            "sha256": architecture.tokenizer_sha256}:
        raise ValueError("provisional pinned producer differs")
    expected_split = split_snapshot(reader, reader.ids("train"))
    if payload["split_snapshot"] != expected_split:
        raise ValueError("provisional split/Gold exposure differs")
    state = payload["training_state"]
    sampler = payload["sampler_state"]
    selection = payload["selection"]
    policy = _selection_policy(expected_selection_policy)
    validated_selection = validate_checkpoint_selection_contract(
        selection, expected_epoch=state["epoch"],
        expected_manifest_sha256=expected_selection_support_manifest_sha256)
    if expected_selection_support_manifest_sha256 is None:
        raise ValueError("D8 resume requires the current frozen support manifest SHA")
    if validated_selection["selection_policy"] != policy:
        raise ValueError("provisional checkpoint selection policy/state differs")
    if (state["epoch"] <= 0 or state["optimizer_steps"] < 0 or state["articles_seen"] < 0 or
            sampler.get("group_remainder") != 0 or sampler.get("completed_epoch") != state["epoch"]):
        raise ValueError("provisional resume state is not an epoch boundary")
    requested = torch.device(device)
    if requested.type not in ("cpu", "mps"):
        raise ValueError("provisional checkpoint device must be cpu or mps")
    saved_device = state.get("execution_device", "cpu")
    if saved_device not in ("cpu", "mps") or state.get("dtype", "float32") != "float32":
        raise ValueError("provisional checkpoint execution device/dtype differs")
    if requested.type != saved_device and restore_rng_state and not allow_cross_device_eval:
        raise ValueError("cross-device checkpoint use is eval-only; resume on the original device")
    core = fresh_full_core(config, device=requested)
    if (core.config.fingerprint() != architecture.fingerprint() or
            list(parameter_manifest(core)) != payload["parameter_manifest"] or
            set(core.state_dict()) != set(payload["model_state"])):
        raise ValueError("provisional model parameter registry/state differs")
    core.load_state_dict(payload["model_state"], strict=True)
    optimizer = build_optimizer(core, backbone, config)
    if [(row["name"], row["param_names"], row["param_shapes"])
            for row in payload["optimizer_state"]["param_groups"]] != [
                (row["name"], row["param_names"], row["param_shapes"])
                for row in optimizer.param_groups]:
        raise ValueError("provisional optimizer ownership differs")
    optimizer.load_state_dict(payload["optimizer_state"])
    if audit_optimizer(core, backbone, optimizer) != payload["parameter_ownership_audit"]:
        raise ValueError("provisional optimizer audit differs")
    if payload["scheduler_state"] != {"kind": "NONE", "state": None} or payload["scaler_state"] != {"kind": "NONE_FP32", "state": None}:
        raise ValueError("provisional scheduler/scaler contract differs")
    trainer = V3Trainer(core, backbone, config, tokenizer=tokenizer)
    trainer.relation_sampling_manifest = relation_articles
    trainer.optimizer_steps = state["optimizer_steps"]
    trainer.articles_seen = state["articles_seen"]
    trainer.cumulative_clipped_count = selection[
        "gradient_clipping_summary"]["cumulative_clipped_count"]
    if restore_rng_state:
        _restore_provisional_rng(payload["rng_state"], requested)
    return trainer, optimizer, payload
