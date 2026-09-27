"""Load the user-selected D2/E1 project release from its own frozen files.

This loader preserves the provisional source-calibration lineage. It does not
claim that predicted-source validation artifacts exist or change model policy.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import math
from pathlib import Path

import torch

from models.backbone import KFDeBERTaBackbone
from models.v3_pretraining.architecture import V3ArchitectureConfig, V3ArchitectureFactory
from models.v3_pretraining.attribution_heads import register_attribution_heads
from models.v3_pretraining.entity_heads import register_entity_heads
from models.v3_pretraining.event_heads import register_event_heads
from models.v3_pretraining.extraction_heads import register_extraction_heads
from models.v3_pretraining.primary_head import register_primary_head
from models.v3_pretraining.time_heads import register_time_heads
from runtime.candidate_routing.integrated import IntegratedBoundedPolicies
from runtime.v3_pretraining.acceptance import AcceptanceConfig, SCORE_CONTRACT_VERSION
from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.extraction_decode import RetrievalBudget
from runtime.v3_pretraining.primary_scoring import PrimaryTrainingProvenance
from runtime.v3_pretraining.serving import ServingBudget, V23OperationalCaps, V3ServingWorker
from runtime.v3_pretraining.source_funnel import (
    SourceFunnelPolicy, V23_SOURCE_FUNNEL_EXECUTION_VERSION,
)
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer


MANIFEST_VERSION = "articlelocal-v3-project-release-d2-e1-v2"
CHECKPOINT_SHA = "87bc8b000490ebfff71287cbbe5c05605c02243178dc6411ac22a088eccb2acf"
SOURCE_POLICY_SHA = "6e77d2351648c4eb64e94534f2cd3240f4d610507888551fef219ca7f2ecf7e3"
SOURCE_ACCEPTANCE_SHA = "f6d28684a76908c451122114876690117fb641a1ca76aa0726cb11b368f1ed54"


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def verify_phase6_primary_training(checkpoint: dict, *, checkpoint_sha256: str
                                   ) -> PrimaryTrainingProvenance:
    """Prove that Primary and its adapter received Phase 6 optimizer updates."""
    manifest = checkpoint.get("phase_manifest")
    state = checkpoint.get("training_state")
    audit = checkpoint.get("optimizer_audit")
    groups = checkpoint.get("optimizer_groups")
    logs = checkpoint.get("step_logs")
    weights = checkpoint.get("model_state")
    owners = {"primary", "primary_adapter"}
    if (checkpoint.get("phase") != "cluster_consumers" or
            not isinstance(manifest, dict) or
            manifest.get("phase") != "cluster_consumers" or
            "primary" not in manifest.get("active_losses", ()) or
            not owners.issubset(set(manifest.get("trainable_owners", ()))) or
            not isinstance(state, dict) or
            not isinstance(audit, dict) or
            not isinstance(groups, (list, tuple)) or
            not isinstance(logs, (list, tuple)) or
            not isinstance(weights, dict) or
            not owners.issubset(set(audit.get("owners", ()))) or
            not owners.issubset({group.get("name") for group in groups}) or
            not any(key.startswith("task_modules.primary.") for key in weights) or
            not any(key.startswith("primary_adapter.") for key in weights)):
        raise ValueError("selected checkpoint lacks Phase 6 Primary training provenance")
    steps = state.get("optimizer_steps")
    epochs = state.get("completed_passes")
    if (type(steps) is not int or steps <= 0 or type(epochs) is not int or
            epochs <= 0 or len(logs) != steps or
            not any(
                isinstance(row, dict) and row.get("phase") == "cluster_consumers" and
                "primary" in row.get("active_oracle_losses", ()) and
                owners.issubset(set(row.get("changed_owners", ()))) and
                all(isinstance(row.get("owner_update_norm", {}).get(owner), (int, float)) and
                    math.isfinite(row["owner_update_norm"][owner]) and
                    row["owner_update_norm"][owner] > 0 for owner in owners)
                for row in logs)):
        raise ValueError("selected checkpoint has no verified Primary optimizer update")
    return PrimaryTrainingProvenance(checkpoint_sha256, steps, epochs)


def verify_project_release(root: str | Path) -> dict:
    """Reject missing, extra, symlinked, or modified release files."""
    root = Path(root).resolve()
    manifest = json.loads((root / "release-manifest.json").read_text(encoding="utf-8"))
    files = manifest.get("files_sha256")
    v31 = manifest.get("release_version") == "3.1-project-candidate-d2-e1"
    checkpoint_sha = (manifest.get("checkpoint", {}).get("sha256") if v31 else
                      CHECKPOINT_SHA)
    source_policy_sha = (files.get("config/source-policy.json")
                         if v31 and isinstance(files, dict) else SOURCE_POLICY_SHA)
    source_acceptance_sha = (files.get("config/source-acceptance.json")
                             if v31 and isinstance(files, dict) else SOURCE_ACCEPTANCE_SHA)
    if (manifest.get("schema_version") != MANIFEST_VERSION or
            manifest.get("status") != ("FROZEN_GOLD100_REHEARSAL_CANDIDATE" if v31 else
                                       "FROZEN_USER_SELECTED_D2_E1") or
            manifest.get("inference_policy_status") != (
                "DEV15_PROVISIONAL_SHA_BOUND" if v31 else "USER_SELECTED_SHA_BOUND") or
            manifest.get("source_validation_status") != (
                "DEV15_P6_CALIBRATED" if v31 else "PROVISIONAL_ENGINEERING_ONLY") or
            manifest.get("service_validation_status") != (
                "NOT_PREDICTED_VALIDATED" if v31 else "PROVISIONAL_NOT_PREDICTED_VALIDATED") or
            manifest.get("service_ready") is not (not v31) or
            manifest.get("inference_ready") is not True or
            (v31 and (manifest.get("source_tree_mode") != "WORKING_TREE_SNAPSHOT" or
                      manifest.get("source_snapshot_sha256") !=
                      sha256(json.dumps(files, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest())) or
            not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64 or
            any(not isinstance(value, str) or len(value) != 64 for value in
                (source_policy_sha, source_acceptance_sha)) or
            manifest.get("checkpoint", {}).get("sha256") != checkpoint_sha or
            not isinstance(manifest.get("training_provenance"), dict) or
            manifest["training_provenance"].get("checkpoint_sha256") != checkpoint_sha or
            not isinstance(files, dict) or not files):
        raise ValueError("project release contract differs")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*")
              if path.is_file() and not ({".git", "__pycache__"} &
                                         set(path.relative_to(root).parts))}
    if actual != set(files) | {"release-manifest.json"}:
        raise ValueError("project release file inventory differs")
    for relative, expected in files.items():
        path = root / relative
        if (Path(relative).is_absolute() or ".." in Path(relative).parts or
                path.is_symlink() or not path.is_file() or _sha(path) != expected):
            raise ValueError(f"project release file SHA differs: {relative}")
    binding = manifest["binding"]
    for key, expected in (("checkpoint", checkpoint_sha),
                          ("source_policy", source_policy_sha),
                          ("source_acceptance", source_acceptance_sha)):
        relative = binding[key] if key != "checkpoint" else manifest["checkpoint"]["path"]
        if files[relative] != expected:
            raise ValueError(f"project release {key} lineage differs")
    for key in ("d2", "e1", "routing"):
        if binding[key] not in files:
            raise ValueError(f"project release {key} binding missing")
    if v31:
        evidence = ("config/selected-checkpoint.json",
                    "config/source-calibration-report.json",
                    "config/entity-margin-selection.json")
        if any(name not in files for name in evidence):
            raise ValueError("v3.1 candidate calibration evidence missing")
        selected, source, margin = (json.loads((root / name).read_text())
                                    for name in evidence)
        d2 = json.loads((root / binding["d2"]).read_text())
        if (selected.get("phase") != "cluster_consumers" or
                selected.get("selected_checkpoint_sha256") != checkpoint_sha or
                source.get("checkpoint_sha256") != checkpoint_sha or
                source.get("source_policy_sha256") != source_policy_sha or
                source.get("source_acceptance_sha256") != source_acceptance_sha or
                source.get("split_access_ledger") != {"train": 0, "dev": 15, "test": 0} or
                margin.get("checkpoint_sha256") != checkpoint_sha or
                margin.get("source_policy_sha256") != source_policy_sha or
                margin.get("source_acceptance_sha256") != source_acceptance_sha or
                margin.get("split_access_ledger") != {"train": 0, "dev": 15, "test": 0} or
                margin.get("cluster_merge_error_validated") is not False or
                d2.get("source_reference", {}).get("source_report_file_sha256") !=
                files[evidence[1]] or
                d2.get("entity_coreference_margin", {}).get(
                    "margin_selection_file_sha256") != files[evidence[2]] or
                d2.get("downstream_thresholds", {}).get("ENTITY_COREFERENCE") !=
                margin.get("selected_threshold") or
                d2.get("service_ready") is not False):
            raise ValueError("v3.1 candidate calibration evidence differs")
    return manifest


def load_project_release_worker(root: str | Path, *, backbone_snapshot: str | Path,
                                device: str = "cpu") -> V3ServingWorker:
    """Construct the actual PUBLIC worker with bundled checkpoint and D2/E1."""
    root = Path(root).resolve()
    if Path(__file__).resolve().parents[2] != root:
        raise ValueError("load the release code from the bundle itself")
    if device not in ("cpu", "mps") or (device == "mps" and
                                         not torch.backends.mps.is_available()):
        raise ValueError("requested release device is unavailable")
    manifest = verify_project_release(root)
    binding = manifest["binding"]
    checkpoint_sha = manifest["checkpoint"]["sha256"]
    source_policy_sha = manifest["files_sha256"][binding["source_policy"]]
    source_acceptance_sha = manifest["files_sha256"][binding["source_acceptance"]]
    d2 = json.loads((root / binding["d2"]).read_text())
    e1 = json.loads((root / binding["e1"]).read_text())
    routing = json.loads((root / binding["routing"]).read_text())
    v31 = manifest.get("release_version") == "3.1-project-candidate-d2-e1"
    fine = d2.get("source_thresholds", {}).get("PARTICIPANT_FINE") if v31 else None
    trigger_fine = d2.get("source_thresholds", {}).get("TRIGGER_FINE") if v31 else None
    entity_margin = d2.get("downstream_thresholds", {}).get("ENTITY_COREFERENCE")
    if (d2["selection_status"] != ("V31_GOLD100_DEV15_PROVISIONAL" if v31 else
                                    "USER_SELECTED_D2") or
            e1["selection_status"] != ("V31_FIXED_E1" if v31 else
                                    "USER_SELECTED_D2_E1") or
            (v31 and (not isinstance(fine, (int, float)) or isinstance(fine, bool)
                      or not math.isfinite(fine) or
                      d2.get("participant_fine_threshold", {}).get(
                          "local_training_coverage_verified") is not True or
                      not isinstance(trigger_fine, (int, float)) or
                      isinstance(trigger_fine, bool) or not math.isfinite(trigger_fine) or
                      d2.get("trigger_fine_threshold", {}).get(
                          "local_training_coverage_verified") is not True or
                      d2.get("entity_coreference_margin", {}).get(
                          "calibration_verified") is not False or
                      d2.get("entity_coreference_margin", {}).get(
                          "provisional_predicted_pair_threshold_selected") is not True or
                      d2.get("entity_coreference_margin", {}).get(
                          "decision_policy") != "MARGIN_GTE" or
                      not isinstance(entity_margin, (int, float)) or
                      isinstance(entity_margin, bool) or not math.isfinite(entity_margin))) or
            d2["checkpoint_sha256"] != checkpoint_sha or
            e1["checkpoint_sha256"] != checkpoint_sha or
            e1["d2_threshold_selection_sha256"] != _sha(root / binding["d2"]) or
            d2["source_reference"]["source_policy_file_sha256"] != source_policy_sha or
            d2["source_reference"]["source_acceptance_file_sha256"] != source_acceptance_sha or
            routing["entity_pair_policy"] != {"per_query_budget": 32,
                                             "query_visit_budget": 256,
                                             "posting_visit_budget": 64,
                                             "gram_keys_per_query": 4} or
            routing["relation_routing_artifact"] is not None):
        raise ValueError("selected D2/E1 or active routing binding differs")
    checkpoint = torch.load(root / manifest["checkpoint"]["path"],
                            map_location="cpu", weights_only=True)
    if (checkpoint.get("phase") != "cluster_consumers" or
            checkpoint.get("format_version") != manifest["checkpoint"]["format"] or
            not isinstance(checkpoint.get("model_state"), dict)):
        raise ValueError("selected Phase 6 checkpoint format differs")
    primary_training = verify_phase6_primary_training(
        checkpoint, checkpoint_sha256=checkpoint_sha)
    if manifest["training_provenance"] != primary_training.as_dict():
        raise ValueError("Primary training provenance differs from checkpoint")
    architecture = manifest["checkpoint"]["architecture"]
    config = V3ArchitectureConfig(run_id=architecture["run_id"], seed=architecture["seed"])
    if config.fingerprint() != architecture["sha256"]:
        raise ValueError("release architecture fingerprint differs")
    core = V3ArchitectureFactory.fresh_core(config)
    for register in (register_extraction_heads, register_entity_heads,
                     register_time_heads, register_event_heads,
                     register_attribution_heads, register_primary_head):
        register(core)
    core.require_full_model()
    core.load_state_dict(checkpoint["model_state"], strict=True)
    core.to(device).eval()
    checkpoint = None

    snapshot = Path(backbone_snapshot).resolve()
    tokenizer, tokenizer_sha, revision = load_pinned_fast_tokenizer(snapshot)
    backbone_contract = manifest["backbone"]
    if (revision != backbone_contract["revision"] or
            tokenizer_sha != backbone_contract["tokenizer_sha256"] or
            config.backbone.model_id != backbone_contract["model_id"] or
            config.backbone.expected_weights_sha256 != backbone_contract["weight_sha256"]):
        raise ValueError("pinned backbone/tokenizer contract differs")
    backbone = KFDeBERTaBackbone.from_pretrained(
        config.backbone, cache_dir=snapshot.parents[2]).to(device).eval()
    if any(parameter.requires_grad for parameter in backbone.parameters()):
        raise ValueError("release backbone became trainable")

    source_payload = json.loads((root / binding["source_policy"]).read_text())
    source_payload["source_execution_version"] = V23_SOURCE_FUNNEL_EXECUTION_VERSION
    source_bytes = json.dumps(source_payload, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode()
    caps = V23OperationalCaps(**e1["v23_operational_caps"])
    budget = ServingBudget(retrieval=RetrievalBudget(**source_payload["retrieval_budget"]),
                           v23_operational_caps=caps)
    policy = SourceFunnelPolicy.from_artifacts(
        source_bytes, (root / binding["source_acceptance"]).read_bytes(),
        checkpoint_sha256=checkpoint_sha, budget=budget)
    source = d2["source_thresholds"]
    thresholds = {"EVENT": source["EVENT"], "STATEMENT": source["STATEMENT"],
                  "ENTITY": source["ENTITY_NATIVE"], "TIME": source["TIME"],
                  "TRIGGER": trigger_fine if v31 else source["TRIGGER_ENDPOINT"],
                  "PARTICIPANT": fine if v31 else source["PARTICIPANT_ENDPOINT"],
                  **d2["downstream_thresholds"]}
    boundary = {"EVENT": source["EVENT_BOUNDARY"],
                "STATEMENT": source["STATEMENT_BOUNDARY"]}
    acceptance = AcceptanceConfig(
        ("CALIBRATION_CANDIDATE" if v31 else "PROJECT_FINAL_USER_SELECTED"),
        SCORE_CONTRACT_VERSION, checkpoint_sha,
        ("dev15" if v31 else "dev49"), ("v31-gold100-p6-d2-fixed-e1" if v31 else
                  "user-selected-d2-e1-v1"), tuple(sorted(thresholds.items())),
        tuple(sorted(boundary.items())))
    policy = replace(
        policy,
        policy_sha256=_canonical_sha({
            "source_artifact_sha256": sha256(source_bytes).hexdigest(),
            "d2_selection_sha256": _canonical_sha(d2),
            "e1_selection_sha256": _canonical_sha(e1),
        }),
        acceptance_sha256=_canonical_sha(acceptance.as_dict()),
        thresholds=tuple((kind, thresholds[kind])
                         for kind in (("EVENT", "STATEMENT", "ENTITY", "TIME", "TRIGGER")
                                      if v31 else ("EVENT", "STATEMENT", "ENTITY", "TIME"))),
        boundary_thresholds=tuple(boundary.items()),
        trigger_endpoint_threshold=source["TRIGGER_ENDPOINT"],
        participant_endpoint_threshold=source["PARTICIPANT_ENDPOINT"],
        participant_threshold=fine if v31 else policy.participant_threshold,
        participant_threshold_status=("SELECTED_V31_FINE" if v31 else
                                      policy.participant_threshold_status),
        participant_mode="V31_FINE_SPAN_ACCEPTANCE" if v31 else policy.participant_mode,
        status="PROVISIONAL_CHECKPOINT_BOUND_CALIBRATION",
    )
    entity_pair = EntityPairPolicy(**routing["entity_pair_policy"])
    if (entity_pair.sha256 != routing["entity_pair_policy_sha256"] or
            IntegratedBoundedPolicies.from_root().config_sha256 !=
            routing["integrated_bounded_policy_sha256"]):
        raise ValueError("active pair policy SHA differs")
    return V3ServingWorker(
        core, backbone, tokenizer, tokenizer_sha, budget=budget,
        acceptance=acceptance, source_policy=policy,
        checkpoint_sha256=checkpoint_sha,
        entity_pair_policy=entity_pair,
        relation_routing_artifact=None,
        primary_training_provenance=primary_training,
        producer_version="V3_PROJECT_FINAL_D2_E1",
    )
