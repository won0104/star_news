"""Fail-closed loader for a frozen, predicted-validated v3 release bundle.

Training checkpoints and Gold files are never loaded as service artifacts. A
finalizer must export model weights and bind every selected policy/report byte
before this loader can construct a worker.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import torch

from models.backbone import KFDeBERTaBackbone
from models.v3_pretraining.architecture import V3ArchitectureConfig, V3ArchitectureFactory
from models.v3_pretraining.attribution_heads import register_attribution_heads
from models.v3_pretraining.entity_heads import register_entity_heads
from models.v3_pretraining.event_heads import register_event_heads
from models.v3_pretraining.extraction_heads import register_extraction_heads
from models.v3_pretraining.primary_head import register_primary_head
from models.v3_pretraining.task_contract import HEAD_TASKS
from models.v3_pretraining.time_heads import register_time_heads
from runtime.v3_pretraining.acceptance import AcceptanceConfig, SCORE_CONTRACT_VERSION
from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.extraction_decode import RetrievalBudget
from runtime.v3_pretraining.relation_routing import (
    PredictedRelationRoutingArtifact, identity_policy_sha256)
from runtime.v3_pretraining.serving import ServingBudget, V3ServingWorker
from runtime.v3_pretraining.source_funnel import SourceFunnelPolicy
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer
from runtime.candidate_routing.integrated import IntegratedBoundedPolicies


RELEASE_MANIFEST_VERSION = "articlelocal-v3-runtime-release-v1"
WEIGHT_FORMAT_VERSION = "v3-selected-model-state-v1"
ARTIFACT_NAMES = (
    "model_state", "source_policy", "source_acceptance",
    "source_validation_report", "entity_pair_policy",
    "entity_pair_validation_report", "relation_routing_policy",
    "relation_validation_report", "downstream_acceptance",
    "downstream_calibration", "asserted_by_option_policy",
    "post_assertor_entity_stability",
)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _checked_file(root: Path, relative: str, expected_sha: str) -> Path:
    if (not isinstance(relative, str) or not relative or
            Path(relative).is_absolute() or ".." in Path(relative).parts or
            not isinstance(expected_sha, str) or len(expected_sha) != 64 or
            any(char not in "0123456789abcdef" for char in expected_sha)):
        raise ValueError("release file path or SHA is invalid")
    path = root / relative
    if not path.is_file() or path.is_symlink() or _file_sha256(path) != expected_sha:
        raise ValueError(f"release file differs: {relative}")
    return path


def verify_release_manifest(root: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    """Verify every bundle byte before importing a checkpoint or policy."""
    root = Path(root).resolve()
    manifest_path = root / "release-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("frozen v3 release manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or
            manifest.get("schema_version") != RELEASE_MANIFEST_VERSION or
            manifest.get("status") != "FROZEN_PREDICTED_VALIDATED" or
            manifest.get("inference_ready") is not True or
            manifest.get("source_profile") != "V23_BASELINE" or
            manifest.get("score_contract_version") != SCORE_CONTRACT_VERSION or
            set(manifest.get("artifacts", {})) != set(ARTIFACT_NAMES) or
            not isinstance(manifest.get("files_sha256"), dict)):
        raise ValueError("v3 release is incomplete or not predicted-validated")
    files = {relative: _checked_file(root, relative, digest)
             for relative, digest in manifest["files_sha256"].items()}
    artifacts: dict[str, Path] = {}
    for name in ARTIFACT_NAMES:
        entry = manifest["artifacts"][name]
        if (not isinstance(entry, dict) or set(entry) != {"path", "sha256"} or
                entry["path"] not in files or
                entry["sha256"] != manifest["files_sha256"][entry["path"]]):
            raise ValueError(f"v3 release artifact is unbound: {name}")
        artifacts[name] = files[entry["path"]]
    return manifest, artifacts


def load_release_worker(root: str | Path, *, backbone_snapshot: str | Path,
                        device: str = "cpu") -> V3ServingWorker:
    """Construct one selected v3 worker with exact checkpoint/policy lineage.

    The external pinned backbone snapshot is verified by the tokenizer and
    backbone loaders. All task weights are loaded strictly from the bundle.
    """
    if device not in ("cpu", "mps") or (device == "mps" and
                                         not torch.backends.mps.is_available()):
        raise ValueError("requested release device is unavailable")
    manifest, artifacts = verify_release_manifest(root)
    checkpoint_sha = manifest.get("selected_phase6_checkpoint_sha256")
    if not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64:
        raise ValueError("selected Phase 6 checkpoint SHA is missing")
    weights = torch.load(artifacts["model_state"], map_location="cpu",
                         weights_only=True)
    if (not isinstance(weights, dict) or
            set(weights) != {"format_version", "checkpoint_sha256", "run_id",
                             "seed", "architecture_sha256", "task_registry",
                             "model_state"} or
            weights["format_version"] != WEIGHT_FORMAT_VERSION or
            weights["checkpoint_sha256"] != checkpoint_sha or
            weights["task_registry"] != list(HEAD_TASKS) or
            not isinstance(weights["model_state"], dict)):
        raise ValueError("selected v3 model-state export differs")
    config = V3ArchitectureConfig(run_id=weights["run_id"], seed=weights["seed"])
    if weights["architecture_sha256"] != config.fingerprint():
        raise ValueError("v3 architecture SHA differs")
    core = V3ArchitectureFactory.fresh_core(config)
    for register in (register_extraction_heads, register_entity_heads,
                     register_time_heads, register_event_heads,
                     register_attribution_heads, register_primary_head):
        register(core)
    core.require_full_model()
    core.load_state_dict(weights["model_state"], strict=True)
    core.to(device).eval()
    snapshot = Path(backbone_snapshot).resolve()
    tokenizer, tokenizer_sha, _ = load_pinned_fast_tokenizer(snapshot)
    backbone = KFDeBERTaBackbone.from_pretrained(
        config.backbone, cache_dir=snapshot.parents[2]).to(device).eval()
    if any(parameter.requires_grad for parameter in backbone.parameters()):
        raise ValueError("release backbone must remain frozen")
    source_bytes = artifacts["source_policy"].read_bytes()
    source_acceptance_bytes = artifacts["source_acceptance"].read_bytes()
    source_json = json.loads(source_bytes)
    budget = ServingBudget(retrieval=RetrievalBudget(**source_json["retrieval_budget"]))
    source = SourceFunnelPolicy.from_artifacts(
        source_bytes, source_acceptance_bytes,
        checkpoint_sha256=checkpoint_sha, budget=budget)
    if (source.status != "PREDICTED_VALIDATED" or
            source_json["predicted_validation_report_sha256"] !=
            _file_sha256(artifacts["source_validation_report"])):
        raise ValueError("predicted source validation report differs")
    entity = EntityPairPolicy.load_predicted_validated(
        artifacts["entity_pair_policy"], checkpoint_sha256=checkpoint_sha,
        source_policy_sha256=source.policy_sha256,
        acceptance_sha256=source.acceptance_sha256)
    entity_json = json.loads(artifacts["entity_pair_policy"].read_text())
    if (entity_json["predicted_pair_routing_validation_report_sha256"] !=
            _file_sha256(artifacts["entity_pair_validation_report"])):
        raise ValueError("predicted Entity pair report differs")
    event_pair_sha = IntegratedBoundedPolicies.from_root().config_sha256
    relation = PredictedRelationRoutingArtifact.load_predicted_validated(
        artifacts["relation_routing_policy"], checkpoint_sha256=checkpoint_sha,
        source_policy_sha256=source.policy_sha256,
        source_acceptance_sha256=source.acceptance_sha256,
        entity_identity_policy_sha256=identity_policy_sha256("ENTITY", entity.sha256),
        event_identity_policy_sha256=identity_policy_sha256("EVENT", event_pair_sha))
    if relation.predicted_validation_report_sha256 != _file_sha256(
            artifacts["relation_validation_report"]):
        raise ValueError("predicted relation report differs")
    acceptance = AcceptanceConfig.load(artifacts["downstream_acceptance"])
    if not acceptance.service_ready:
        raise ValueError("downstream acceptance is not service calibrated")
    calibration = json.loads(artifacts["downstream_calibration"].read_text())
    return V3ServingWorker(
        core, backbone, tokenizer, tokenizer_sha, budget=budget,
        acceptance=acceptance, source_policy=source,
        checkpoint_sha256=checkpoint_sha,
        calibration_artifact=calibration,
        producer_version="V3_GOLD400_SELECTED_P6",
        entity_pair_policy=entity,
        relation_routing_artifact=relation)
