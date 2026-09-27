"""v3 smoke checkpoint의 완전성·provenance·strict resume 경계.

Pinned backbone bytes는 저장하지 않는다. torch.load는 weights-only로 읽고 active-task
registry, optimizer name/shape ownership, run/config/data snapshot을 비교 후 복원한다.
"""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
from typing import Any, Mapping

import numpy as np
import torch

from models.contracts import BackboneConfig, ContextConfig, TaskLayerPolicy
from models.v3_pretraining.architecture import V3ArchitectureConfig
from models.v3_pretraining.extraction_heads import ENTITY_TYPES, PARTICIPANT_ROLES, STATEMENT_TYPES
from models.v3_pretraining.task_contract import HEAD_TASKS
from models.v3_pretraining.time_heads import TIME_CHARS, TIME_FORMATS
from runtime.v3_pretraining.source_layout import LAYOUT_POLICY
from training.v3_pretraining.corpus import DOCS, GOLD_DIR, TrainGoldReader
from training.v3_pretraining.harness import (HarnessConfig, V3Trainer, audit_optimizer,
                                             build_optimizer, fresh_full_core,
                                             parameter_manifest)
from training.v3_pretraining.relation_sampling import (
    RelationSamplingPolicy, validate_relation_training_metadata)
from training.v3_pretraining.selection_contract import (
    validate_checkpoint_selection_contract)


FORMAT_VERSION = "v3-fresh-train-checkpoint-v6-no-entity-priority"
PROJECT = Path(__file__).resolve().parents[2]
ENGINEERING_CHECKPOINT_REQUIRED_FIELDS = frozenset({
    "format_version", "mode", "run_id", "seed", "harness_config",
    "harness_config_sha256", "architecture_config", "architecture_config_sha256",
    "backbone", "tokenizer", "task_registry", "label_mappings", "producer_hashes",
    "parameter_manifest", "parameter_ownership_audit", "relation_training_metadata",
    "selection_contract", "source_snapshot", "model_state", "optimizer_state", "scheduler_state",
    "scaler_state", "rng_state", "sampler_state", "training_state", "eval_reference",
})


def relation_policy_from_config(config: HarnessConfig) -> RelationSamplingPolicy:
    """Reconstruct the strict D7 policy without creating a model or loading weights."""
    return RelationSamplingPolicy(
        version=config.relation_sampling_policy_version,
        seed=config.relation_sampling_seed,
        negative_limit=config.relation_negative_limit,
        about_lexical_policy=config.relation_about_lexical_policy)


def label_mappings() -> dict:
    return {"entity_types": list(ENTITY_TYPES), "participant_roles": list(PARTICIPANT_ROLES),
            "statement_types": list(STATEMENT_TYPES), "time_formats": list(TIME_FORMATS),
            "time_characters": list(TIME_CHARS)}


def producer_hashes() -> dict:
    paths = ("models/backbone.py", "models/v3_pretraining/architecture.py",
             "runtime/v3_pretraining/source_layout.py",
             "training/v3_pretraining/targets.py",
             "training/v3_pretraining/relation_sampling.py",
             "training/v3_pretraining/relation_evaluation.py",
             "training/v3_pretraining/selection_contract.py",
             "training/v3_pretraining/selection_evaluation.py",
             "training/v3_pretraining/optimization_contract.py",
             "training/v3_pretraining/attribution.py",
             "training/v3_pretraining/harness.py",
             "training/v3_pretraining/checkpoint.py")
    return {name: _file_digest(PROJECT / name) for name in paths}


def _json_digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def capture_rng() -> dict:
    numpy_state = np.random.get_state()
    return {"python": random.getstate(),
            "numpy": {"bit_generator": numpy_state[0], "state": numpy_state[1].tolist(),
                      "position": int(numpy_state[2]), "has_gauss": int(numpy_state[3]),
                      "cached_gaussian": float(numpy_state[4])},
            "torch_cpu": torch.get_rng_state(),
            "torch_cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


def restore_rng(value: Mapping[str, Any]) -> None:
    if set(value) != {"python", "numpy", "torch_cpu", "torch_cuda"}:
        raise ValueError("checkpoint RNG state incomplete")
    random.setstate(value["python"])
    n = value["numpy"]
    np.random.set_state((n["bit_generator"], np.asarray(n["state"], dtype=np.uint32),
                         n["position"], n["has_gauss"], n["cached_gaussian"]))
    torch.set_rng_state(value["torch_cpu"])
    if torch.cuda.is_available():
        if len(value["torch_cuda"]) != torch.cuda.device_count():
            raise ValueError("checkpoint CUDA RNG device count differs")
        torch.cuda.set_rng_state_all(value["torch_cuda"])
    elif value["torch_cuda"]:
        raise ValueError("checkpoint CUDA RNG cannot be restored on CPU-only runtime")


def source_snapshot(reader: TrainGoldReader, article_ids: tuple[str, ...]) -> dict:
    if len(set(article_ids)) != len(article_ids) or not article_ids:
        raise ValueError("checkpoint exposure needs unique nonempty train IDs")
    joined = DOCS / "source-join-manifest.json"
    rows = []
    for aid in article_ids:
        row = reader.rows.get(aid)
        if row is None or row["split"] != "train" or row["validation_status"] != "PASS" or reader.membership.get(aid) != "train":
            raise ValueError("checkpoint exposure includes unverified/non-train Gold")
        if _file_digest(GOLD_DIR / row["gold_file"]) != row["gold_file_sha256"]:
            raise ValueError("checkpoint Gold hash drift")
        rows.append({"article_id": aid, "gold_file": row["gold_file"],
                     "gold_sha256": row["gold_file_sha256"],
                     "source_sha256": row["source_sha256"], "split": "train"})
    return {"source_join_sha256": _file_digest(joined),
            "split_sha256": json.loads(joined.read_text())["split_manifest_sha256"],
            "exposure": rows}


def source_cache_key(*, article_sha256: str, backbone: BackboneConfig,
                     tokenizer_sha256: str, dtype: str,
                     window_digest: str) -> str:
    """frozen producer만 캐시할 때의 완전한 키; DCE 출력은 캐시하지 않는다."""
    if any(not item for item in (article_sha256, tokenizer_sha256, dtype, window_digest)):
        raise ValueError("source cache key lacks producer/source identity")
    return _json_digest({"source_sha256": article_sha256,
                         "backbone_model_id": backbone.model_id,
                         "backbone_revision": backbone.revision,
                         "backbone_weights_sha256": backbone.expected_weights_sha256,
                         "tokenizer_sha256": tokenizer_sha256,
                         "dtype": dtype, "required_layers": backbone.required_layers,
                         "layout_policy": LAYOUT_POLICY,
                         "window_digest": window_digest})


def build_checkpoint_payload(
        trainer: V3Trainer, optimizer: torch.optim.Optimizer, *,
        reader: TrainGoldReader, exposed_ids: tuple[str, ...],
        eval_reference: Mapping[str, Any],
        selection_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the strict writer payload in memory for validation before I/O."""
    core = trainer.core
    config = trainer.config.to_dict()
    ownership = audit_optimizer(core, trainer.backbone, optimizer)
    source = source_snapshot(reader, exposed_ids)
    architecture = asdict(core.config)
    if selection_contract is None:
        raise ValueError("D8 checkpoint requires frozen selection contract metadata")
    selection = validate_checkpoint_selection_contract(selection_contract)
    clip_summary = selection["gradient_clipping_summary"]
    if (clip_summary["cumulative_clipped_count"]
            != trainer.cumulative_clipped_count
            or (trainer.optimizer_steps > 0 and clip_summary["groups"] <= 0)):
        raise ValueError("D8 checkpoint clipping summary differs from trainer state")
    payload = {"format_version": FORMAT_VERSION, "mode": "ENGINEERING_SMOKE_ONLY",
               "run_id": trainer.config.run_id, "seed": trainer.config.seed,
               "harness_config": config, "harness_config_sha256": _json_digest(config),
               "architecture_config": architecture,
               "architecture_config_sha256": core.config.fingerprint(),
               "backbone": {"model_id": core.config.backbone.model_id,
                            "revision": core.config.backbone.revision,
                            "weights_sha256": core.config.backbone.expected_weights_sha256,
                            "stored_in_checkpoint": False},
               "tokenizer": {"revision": core.config.backbone.revision,
                             "sha256": core.config.tokenizer_sha256},
               "task_registry": list(HEAD_TASKS),
               "label_mappings": label_mappings(),
               "producer_hashes": producer_hashes(),
               "parameter_manifest": list(parameter_manifest(core)),
               "parameter_ownership_audit": ownership,
               "relation_training_metadata": trainer.relation_training_metadata(),
               "selection_contract": selection,
               "source_snapshot": source,
               "model_state": core.state_dict(),
               "optimizer_state": optimizer.state_dict(),
               "scheduler_state": {"kind": "NONE", "state": None},
               "scaler_state": {"kind": "NONE_FP32", "state": None},
               "rng_state": capture_rng(),
               "sampler_state": {"article_ids": list(exposed_ids),
                                 "cursor": trainer.articles_seen},
               "training_state": {"optimizer_steps": trainer.optimizer_steps,
                                  "articles_seen": trainer.articles_seen},
               "eval_reference": dict(eval_reference)}
    if set(payload) != ENGINEERING_CHECKPOINT_REQUIRED_FIELDS:
        raise AssertionError("checkpoint writer schema differs from strict loader")
    validate_relation_training_metadata(
        payload["relation_training_metadata"],
        expected_policy=relation_policy_from_config(trainer.config))
    return payload


def save_checkpoint(path: str | Path, trainer: V3Trainer,
                    optimizer: torch.optim.Optimizer, *,
                    reader: TrainGoldReader, exposed_ids: tuple[str, ...],
                    eval_reference: Mapping[str, Any],
                    selection_contract: Mapping[str, Any] | None = None) -> dict:
    """한 fresh run의 완전한 resume 상태만 원자적으로 저장한다."""
    payload = build_checkpoint_payload(
        trainer, optimizer, reader=reader, exposed_ids=exposed_ids,
        eval_reference=eval_reference, selection_contract=selection_contract)
    source = payload["source_snapshot"]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(target)
    return {"path": str(target.resolve()), "sha256": _file_digest(target),
            "bytes": target.stat().st_size,
            "format_version": FORMAT_VERSION, "run_id": trainer.config.run_id,
            "optimizer_steps": trainer.optimizer_steps,
            "source_snapshot_sha256": _json_digest(source),
            "parameter_manifest_sha256": _json_digest(payload["parameter_manifest"]),
            "backbone_weights_stored": False}


def load_checkpoint(path: str | Path, backbone: torch.nn.Module, *,
                    expected_run_id: str, expected_config_sha256: str,
                    reader: TrainGoldReader, tokenizer=None,
                    restore_rng_state: bool = True,
                    expected_selection_support_manifest_sha256: str | None = None
                    ) -> tuple[V3Trainer, torch.optim.Optimizer, dict]:
    """구버전/부분/다른 run·config·Gold snapshot을 거부하며 strict load한다."""
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if (not isinstance(payload, dict)
            or set(payload) != ENGINEERING_CHECKPOINT_REQUIRED_FIELDS
            or payload["format_version"] != FORMAT_VERSION
            or payload["mode"] != "ENGINEERING_SMOKE_ONLY"):
        raise ValueError("incomplete or old v3 checkpoint")
    if payload["run_id"] != expected_run_id or payload["harness_config_sha256"] != expected_config_sha256:
        raise ValueError("checkpoint run/config identity differs")
    config_data = payload["harness_config"]
    if _json_digest(config_data) != expected_config_sha256 or set(config_data) != set(HarnessConfig.__dataclass_fields__):
        raise ValueError("checkpoint harness config digest/shape differs")
    config = HarnessConfig(**config_data)
    config.validate()
    relation_articles = validate_relation_training_metadata(
        payload["relation_training_metadata"],
        expected_policy=relation_policy_from_config(config))
    validate_checkpoint_selection_contract(
        payload["selection_contract"],
        expected_manifest_sha256=expected_selection_support_manifest_sha256)
    if expected_selection_support_manifest_sha256 is None:
        raise ValueError("D8 resume requires the current frozen support manifest SHA")
    if config.run_id != expected_run_id or config.seed != payload["seed"]:
        raise ValueError("checkpoint run/seed differs")
    a = payload["architecture_config"]
    architecture = V3ArchitectureConfig(run_id=a["run_id"], seed=a["seed"],
                                        backbone=BackboneConfig(**a["backbone"]),
                                        context=ContextConfig(**a["context"]),
                                        layers=TaskLayerPolicy(**a["layers"]),
                                        tokenizer_sha256=a["tokenizer_sha256"],
                                        layout_policy=a["layout_policy"], dtype=a["dtype"])
    if _json_digest(a) != payload["architecture_config_sha256"] or architecture.fingerprint() != payload["architecture_config_sha256"]:
        raise ValueError("checkpoint architecture config digest differs")
    if architecture.run_id != config.run_id or architecture.seed != config.seed or payload["task_registry"] != list(HEAD_TASKS):
        raise ValueError("checkpoint architecture/task registry differs")
    if payload["label_mappings"] != label_mappings() or payload["producer_hashes"] != producer_hashes():
        raise ValueError("checkpoint label/producer code contract differs")
    expected_backbone = {"model_id": architecture.backbone.model_id,
                         "revision": architecture.backbone.revision,
                         "weights_sha256": architecture.backbone.expected_weights_sha256,
                         "stored_in_checkpoint": False}
    if payload["backbone"] != expected_backbone or payload["tokenizer"] != {
            "revision": architecture.backbone.revision, "sha256": architecture.tokenizer_sha256}:
        raise ValueError("checkpoint pinned backbone/tokenizer identity differs")
    exposure = payload["source_snapshot"]["exposure"]
    ids = tuple(row["article_id"] for row in exposure)
    if payload["source_snapshot"] != source_snapshot(reader, ids) or payload["sampler_state"]["article_ids"] != list(ids):
        raise ValueError("checkpoint Gold/split exposure snapshot differs")
    core = fresh_full_core(config)
    if core.config.fingerprint() != architecture.fingerprint() or list(parameter_manifest(core)) != payload["parameter_manifest"]:
        raise ValueError("checkpoint model parameter registry/shape differs")
    if set(core.state_dict()) != set(payload["model_state"]):
        raise ValueError("checkpoint model state is partial/foreign")
    core.load_state_dict(payload["model_state"], strict=True)
    optimizer = build_optimizer(core, backbone, config)
    saved_groups = payload["optimizer_state"]["param_groups"]
    if [(row["name"], row["param_names"], row["param_shapes"]) for row in saved_groups] != [
            (row["name"], row["param_names"], row["param_shapes"]) for row in optimizer.param_groups]:
        raise ValueError("checkpoint optimizer ownership differs")
    optimizer.load_state_dict(payload["optimizer_state"])
    if audit_optimizer(core, backbone, optimizer) != payload["parameter_ownership_audit"]:
        raise ValueError("checkpoint optimizer audit differs")
    if payload["scheduler_state"] != {"kind": "NONE", "state": None} or payload["scaler_state"] != {"kind": "NONE_FP32", "state": None}:
        raise ValueError("checkpoint scheduler/scaler contract differs")
    trainer = V3Trainer(core, backbone, config, tokenizer=tokenizer)
    trainer.relation_sampling_manifest = relation_articles
    state = payload["training_state"]
    if state["optimizer_steps"] < 0 or state["articles_seen"] < 0 or payload["sampler_state"]["cursor"] != state["articles_seen"]:
        raise ValueError("checkpoint run/sampler state differs")
    trainer.optimizer_steps = state["optimizer_steps"]
    trainer.articles_seen = state["articles_seen"]
    trainer.cumulative_clipped_count = payload["selection_contract"][
        "gradient_clipping_summary"]["cumulative_clipped_count"]
    if restore_rng_state:
        restore_rng(payload["rng_state"])
    return trainer, optimizer, payload
