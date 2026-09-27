"""Build a v3.1 candidate from committed code and the pinned v3.0 D2/E1 base."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

from scripts.finalize_v3_project_release import PROJECT, build as build_v3


BASE_BUNDLE = PROJECT / "release/kf-deberta-base-kg-extractor-v3-main"
CHECKPOINT = BASE_BUNDLE / "weights/selected-phase6.pt"
SOURCE_DIR = BASE_BUNDLE / "config"
OUTPUT = PROJECT / "release/kf-deberta-base-kg-extractor-v3.1-candidate"
RELEASE_VERSION = "3.1-project-candidate-d2-e1"
TEMPLATE_OVERRIDES = {
    "README.md": "scripts/v31_release_final/README.md",
    "verify_bundle.py": "scripts/v31_release_final/verify_bundle.py",
}
V31_D2 = "training/configs/v3.1-runtime-participant-d2.json"
V31_E1 = "training/configs/v3.1-runtime-d2-e1.json"
MINI_ROOT = PROJECT / "training/results/v3-gold100-p1-p6-3epoch-mini-rehearsal-v2"
MINI_SOURCE = PROJECT / "training/results/v31-gold100-p6-source-calibration-v1"
MINI_MARGIN = PROJECT / "training/results/v31-gold100-p6-entity-margin-v1/margin-selection.json"
MINI_CHECKPOINT = MINI_ROOT / "phase6/epochs/epoch-01/checkpoint.pt"
MINI_D2 = "training/configs/v3.1-gold100-mini-p6-d2.json"
MINI_E1 = "training/configs/v3.1-gold100-mini-p6-e1.json"
MINI_FORMAT = "v3-dag-gold-only-phase-checkpoint-v12-selected-parent"
CONFIG_OVERRIDES = {
    "training/configs/v3-gold400-runtime-threshold-d2-selection-v1.json": V31_D2,
    "training/configs/v3-gold400-runtime-d2-e1-selection-v1.json": V31_E1,
}


def _validate_v31_configuration(d2: dict, e1: dict, *, mini: bool = False) -> None:
    """Keep the candidate unavailable until fine training and selection finish."""
    fine = d2["source_thresholds"].get("PARTICIPANT_FINE")
    trigger_fine = d2["source_thresholds"].get("TRIGGER_FINE")
    entity_margin = d2["downstream_thresholds"].get("ENTITY_COREFERENCE")
    if (d2.get("selection_status") != (
            "V31_GOLD100_DEV15_PROVISIONAL" if mini else "V31_SELECTED_LOCAL_FINE") or
            d2.get("participant_fine_threshold", {}).get(
                "local_training_coverage_verified") is not True or
            not isinstance(fine, (int, float)) or isinstance(fine, bool) or
            not math.isfinite(fine) or
            d2.get("trigger_fine_threshold", {}).get(
                "local_training_coverage_verified") is not True or
            not isinstance(trigger_fine, (int, float)) or
            isinstance(trigger_fine, bool) or not math.isfinite(trigger_fine) or
            d2.get("entity_coreference_margin", {}).get("calibration_verified") is not
            (False if mini else True) or
            (mini and d2.get("entity_coreference_margin", {}).get(
                "provisional_predicted_pair_threshold_selected") is not True) or
            d2.get("entity_coreference_margin", {}).get("decision_policy") != "MARGIN_GTE" or
            not isinstance(entity_margin, (int, float)) or
            isinstance(entity_margin, bool) or not math.isfinite(entity_margin) or
            e1.get("selection_status") != (
                "V31_FIXED_E1" if mini else "V31_REVALIDATED_E1") or
            (mini and (d2.get("service_ready") is not False or
                       e1.get("service_ready") is not False or
                       d2["entity_coreference_margin"].get("calibration_split") != "dev15"))):
        raise ValueError("v3.1 bundle needs trained Trigger/Participant fine, Entity margin D2 and revalidated E1")


def build(checkpoint: Path = CHECKPOINT, source_dir: Path = SOURCE_DIR,
          output: Path = OUTPUT) -> Path:
    """Bind v3.1 fine D2 only after local-head training and calibration."""
    d2 = json.loads((PROJECT / V31_D2).read_text())
    e1 = json.loads((PROJECT / V31_E1).read_text())
    _validate_v31_configuration(d2, e1)
    return build_v3(checkpoint, source_dir, output,
                    release_version=RELEASE_VERSION,
                    template_overrides=TEMPLATE_OVERRIDES,
                    config_overrides=CONFIG_OVERRIDES)


def build_mini_rehearsal(output: Path) -> Path:
    """Freeze the selected Gold100 P6 as a non-service-ready v3.1 candidate."""
    selected = json.loads((MINI_ROOT / "phase6/epochs/selected-checkpoint.json").read_text())
    source = json.loads((MINI_SOURCE / "report.json").read_text())
    margin = json.loads(MINI_MARGIN.read_text())
    d2 = json.loads((PROJECT / MINI_D2).read_text())
    e1 = json.loads((PROJECT / MINI_E1).read_text())
    _validate_v31_configuration(d2, e1, mini=True)
    checkpoint_sha = sha256(MINI_CHECKPOINT.read_bytes()).hexdigest()
    policy_sha = sha256((MINI_SOURCE / "source-policy.json").read_bytes()).hexdigest()
    acceptance_sha = sha256((MINI_SOURCE / "source-acceptance.json").read_bytes()).hexdigest()
    expected_source_thresholds = {
        "EVENT": source["thresholds"]["EVENT"]["decision_threshold"],
        "EVENT_BOUNDARY": source["thresholds"]["EVENT"]["boundary_threshold"],
        "STATEMENT": source["thresholds"]["STATEMENT"]["decision_threshold"],
        "STATEMENT_BOUNDARY": source["thresholds"]["STATEMENT"]["boundary_threshold"],
        "ENTITY_NATIVE": source["thresholds"]["ENTITY"]["decision_threshold"],
        "TIME": source["thresholds"]["TIME"]["decision_threshold"],
        "TRIGGER_ENDPOINT": source["thresholds"]["TRIGGER_ENDPOINT"]["decision_threshold"],
        "TRIGGER_FINE": source["thresholds"]["TRIGGER_FINE"]["decision_threshold"],
        "PARTICIPANT_ENDPOINT": source["thresholds"]["PARTICIPANT"]["decision_threshold"],
        "PARTICIPANT_FINE": source["thresholds"]["PARTICIPANT_FINE"]["decision_threshold"],
    }
    fixed_e1 = json.loads((PROJECT / V31_E1).read_text())
    if (selected.get("phase") != "cluster_consumers" or
            selected.get("selected_checkpoint_path") != str(MINI_CHECKPOINT) or
            selected.get("selected_checkpoint_sha256") != checkpoint_sha or
            selected.get("schedule_contract") !=
            "V23_BASELINE_SIX_PHASE_MAX3_REHEARSAL_ONLY_V1" or
            source.get("checkpoint_sha256") != checkpoint_sha or
            source.get("source_policy_sha256") != policy_sha or
            source.get("source_acceptance_sha256") != acceptance_sha or
            source.get("split_access_ledger") != {"train": 0, "dev": 15, "test": 0} or
            d2.get("source_thresholds") != expected_source_thresholds or
            d2.get("source_reference", {}).get("source_report_file_sha256") !=
            sha256((MINI_SOURCE / "report.json").read_bytes()).hexdigest() or
            d2.get("entity_coreference_margin", {}).get("margin_selection_file_sha256") !=
            sha256(MINI_MARGIN.read_bytes()).hexdigest() or
            d2.get("downstream_thresholds", {}).get("ENTITY_COREFERENCE") !=
            margin.get("selected_threshold") or
            margin.get("checkpoint_sha256") != checkpoint_sha or
            margin.get("source_policy_sha256") != policy_sha or
            margin.get("source_acceptance_sha256") != acceptance_sha or
            margin.get("split_access_ledger") != {"train": 0, "dev": 15, "test": 0} or
            margin.get("cluster_merge_error_validated") is not False or
            e1.get("v23_operational_caps") != fixed_e1["v23_operational_caps"] or
            e1.get("d2_threshold_selection_sha256") !=
            sha256((PROJECT / MINI_D2).read_bytes()).hexdigest() or
            d2.get("checkpoint_sha256") != checkpoint_sha or
            e1.get("checkpoint_sha256") != checkpoint_sha):
        raise ValueError("v3.1 mini selected P6/source lineage differs")
    overrides = {
        "training/configs/v3-gold400-runtime-threshold-d2-selection-v1.json": MINI_D2,
        "training/configs/v3-gold400-runtime-d2-e1-selection-v1.json": MINI_E1,
    }
    return build_v3(
        MINI_CHECKPOINT, MINI_SOURCE, output,
        release_version=RELEASE_VERSION,
        template_overrides=TEMPLATE_OVERRIDES,
        config_overrides=overrides,
        checkpoint_sha256=checkpoint_sha,
        source_policy_sha256=policy_sha,
        source_acceptance_sha256=acceptance_sha,
        checkpoint_format=MINI_FORMAT, candidate_status=True,
        working_tree_candidate=True,
        extra_artifacts={
            "config/selected-checkpoint.json":
                MINI_ROOT / "phase6/epochs/selected-checkpoint.json",
            "config/source-calibration-report.json": MINI_SOURCE / "report.json",
            "config/entity-margin-selection.json": MINI_MARGIN,
        })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mini-rehearsal", action="store_true")
    args = parser.parse_args()
    print(build_mini_rehearsal(args.output) if args.mini_rehearsal else
          build(args.checkpoint, args.source_dir, args.output))


if __name__ == "__main__":
    main()
