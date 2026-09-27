"""기존 phase 산출물의 독립 상태와 SHA binding을 한 manifest에 모은다.

학습, 선택, calibration, predicted evaluation을 실행하지 않는다. 후속 산출물이
생기면 같은 경로를 다시 계산하며, runtime readiness는 별도 검증 증거가 있어야 한다.
"""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Mapping

import torch

from models.v3_pretraining.task_contract import TRAINING_PHASES
from runtime.v3_pretraining.acceptance import (V23_TRIGGER_ENDPOINT_PRODUCER,
                                                V23_TRIGGER_FINE_PRODUCER)
from training.v3_pretraining.selected_parent import SelectedParentBinding


VERSION = "v3-staged-phase-lifecycle-v1"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _artifact(path: str | Path) -> tuple[Path, dict]:
    source = Path(path).resolve()
    row = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(row, dict):
        raise ValueError(f"lifecycle artifact is not an object: {source}")
    return source, row


def refresh_phase_lifecycle(*, output_path: str | Path,
                            selected_record_path: str | Path,
                            training_checkpoint_path: str | Path | None = None,
                            parent_binding: SelectedParentBinding | None = None,
                            calibration_acceptance_path: str | Path | None = None,
                            predicted_evaluation_path: str | Path | None = None,
                            runtime_readiness_path: str | Path | None = None,
                            training_code_snapshot_sha256: str | None = None,
                            selection_code_snapshot_sha256: str | None = None,
                            selection_policy_sha256: str | None = None
                            ) -> dict:
    """Rebuild a derived manifest only from checkpoint-bound artifact bytes."""
    output = Path(output_path).resolve()
    previous = None
    if output.exists():
        _, previous = _artifact(output)
        if previous.get("schema_version") != VERSION:
            raise ValueError("existing lifecycle schema differs")
    selected_path, selected = _artifact(selected_record_path)
    phase = selected.get("phase")
    if (phase not in TRAINING_PHASES or
            type(selected.get("selected_epoch")) is not int or
            selected["selected_epoch"] < 1):
        raise ValueError("selected phase is missing or unknown")
    selected_checkpoint = Path(selected["selected_checkpoint_path"]).resolve()
    selected_sha = selected.get("selected_checkpoint_sha256")
    if not selected_checkpoint.is_file() or _sha(selected_checkpoint) != selected_sha:
        raise ValueError("selected checkpoint bytes differ")
    selected_record_sha = _sha(selected_path)
    if previous is not None and previous["selection"]["selection_record_sha256"] != selected_record_sha:
        raise ValueError("lifecycle selected checkpoint was replaced")
    if training_checkpoint_path is None:
        training_checkpoint_path = (previous["training"]["checkpoint"]
                                    if previous is not None else selected_checkpoint)
    training_checkpoint = Path(training_checkpoint_path).resolve()
    if not training_checkpoint.is_file():
        raise ValueError("training checkpoint is missing")
    training_sha = _sha(training_checkpoint)
    if previous is not None and previous["training"]["checkpoint_sha256"] != training_sha:
        raise ValueError("lifecycle training checkpoint bytes differ")
    if parent_binding is None and previous is not None:
        parent = previous["parent"]
    elif phase == "extraction":
        if parent_binding is not None:
            raise ValueError("Phase 1 cannot have a selected parent")
        parent = {"status": "NOT_APPLICABLE"}
    else:
        if (parent_binding is None or
                parent_binding.phase != TRAINING_PHASES[TRAINING_PHASES.index(phase) - 1]):
            raise ValueError("downstream lifecycle needs immediate selected parent")
        checkpoint_payload = torch.load(
            selected_checkpoint, map_location="cpu", weights_only=True)
        if (checkpoint_payload.get("phase") != phase or
                checkpoint_payload.get("parent_phase") != parent_binding.phase or
                checkpoint_payload.get("parent_checkpoint_sha256") !=
                parent_binding.checkpoint_sha256 or
                checkpoint_payload.get("parent_selected_record_sha256") !=
                parent_binding.selection_record_sha256 or
                checkpoint_payload.get("parent_selected_epoch") !=
                parent_binding.selected_epoch):
            raise ValueError("selected checkpoint parent lineage differs")
        parent = {"status": "COMPLETE", "phase": parent_binding.phase,
                  "selected_checkpoint_sha256": parent_binding.checkpoint_sha256,
                  "selected_record_sha256": parent_binding.selection_record_sha256,
                  "selected_epoch": parent_binding.selected_epoch,
                  "verified": True}
    if (previous is not None and parent != previous["parent"]):
        raise ValueError("lifecycle parent selection differs")
    selection = {
        "status": "COMPLETE", "selected_epoch": selected["selected_epoch"],
        "selected_checkpoint": str(selected_checkpoint),
        "selected_checkpoint_sha256": selected_sha,
        "selection_record": str(selected_path),
        "selection_record_sha256": selected_record_sha,
        "selection_policy_sha256": (selection_policy_sha256 or
            selected.get("selection_policy_sha256") or
            (previous["selection"].get("selection_policy_sha256") if previous else None)),
        "selection_code_snapshot_sha256": (selection_code_snapshot_sha256 or
            (previous["selection"].get("selection_code_snapshot_sha256")
             if previous else selected.get("selection_code_snapshot_sha256"))),
        "calibrated_thresholds_used": selected.get(
            "checkpoint_selection_used_calibrated_thresholds", False)}
    if selection["calibrated_thresholds_used"] is not False:
        raise ValueError("selected epoch used calibrated thresholds")
    predicted = {"status": "NOT_RUN"}
    if predicted_evaluation_path is not None:
        path, row = _artifact(predicted_evaluation_path)
        if row.get("phase") != phase or row.get("checkpoint_sha256") != selected_sha:
            raise ValueError("predicted evaluation checkpoint/phase differs")
        evidence_status = row.get("status")
        if evidence_status not in ("DIAGNOSTIC_ONLY", "COMPLETE",
                                   "PREDICTED_VALIDATED"):
            raise ValueError("predicted evaluation status is not a validated contract")
        predicted = {"status": ("DIAGNOSTIC_ONLY" if evidence_status ==
                                "DIAGNOSTIC_ONLY" else "COMPLETE"),
                     "artifact": str(path), "artifact_sha256": _sha(path),
                     "code_snapshot_sha256": row.get("relevant_code_snapshot_sha256")}
    elif previous is not None:
        predicted = previous["predicted_evaluation"]
    calibration = {"status": "NOT_RUN", "TRIGGER_ENDPOINT": "PENDING",
                   "TRIGGER_FINE": "PENDING"} if phase == "extraction" else {"status": "NOT_RUN"}
    if calibration_acceptance_path is not None:
        path, row = _artifact(calibration_acceptance_path)
        if row.get("checkpoint_sha256") != selected_sha:
            raise ValueError("calibration checkpoint differs from selected checkpoint")
        if phase == "extraction":
            endpoints = row.get("v23_proposal_endpoint_thresholds")
            endpoint_selected = (isinstance(endpoints, Mapping) and
                                 type(endpoints.get("TRIGGER")) in (int, float) and
                                 math.isfinite(endpoints["TRIGGER"]) and
                                 0.0 <= endpoints["TRIGGER"] <= 1.0 and
                                 row.get("trigger_endpoint_score_producer") ==
                                 V23_TRIGGER_ENDPOINT_PRODUCER)
            fine_selected = (row.get("threshold_status", {}).get("TRIGGER") == "SELECTED" and
                             type(row.get("thresholds", {}).get("TRIGGER")) in (int, float) and
                             math.isfinite(row["thresholds"]["TRIGGER"]) and
                             row.get("trigger_final_score_producer") == V23_TRIGGER_FINE_PRODUCER)
            calibration = {
                "status": "COMPLETE" if endpoint_selected and fine_selected else "IN_PROGRESS",
                "TRIGGER_ENDPOINT": "SELECTED" if endpoint_selected else "PENDING",
                "TRIGGER_FINE": "SELECTED" if fine_selected else "PENDING",
                "artifact": str(path), "artifact_sha256": _sha(path),
                "selection_record_sha256": row.get("selection_record_sha256")}
            if (calibration["selection_record_sha256"] is not None and
                    calibration["selection_record_sha256"] != selected_record_sha):
                raise ValueError("calibration selection lineage differs")
        else:
            calibration = {"status": "COMPLETE", "artifact": str(path),
                           "artifact_sha256": _sha(path)}
    elif previous is not None:
        calibration = previous["calibration"]
    readiness = {"status": "NOT_VALIDATED"}
    if runtime_readiness_path is not None:
        path, row = _artifact(runtime_readiness_path)
        if (row.get("checkpoint_sha256") != selected_sha or
                row.get("status") != "PREDICTED_VALIDATED" or
                predicted["status"] != "COMPLETE" or
                calibration["status"] != "COMPLETE" or
                (phase == "extraction" and calibration["TRIGGER_FINE"] != "SELECTED")):
            raise ValueError("runtime readiness lacks predicted/calibrated binding")
        readiness = {"status": "VALIDATED", "artifact": str(path),
                     "artifact_sha256": _sha(path)}
    elif previous is not None:
        readiness = previous["runtime_readiness"]
        if (readiness["status"] == "VALIDATED" and
                (calibration != previous["calibration"] or
                 predicted != previous["predicted_evaluation"])):
            readiness = {"status": "NOT_VALIDATED"}
    row = {"schema_version": VERSION, "phase": phase,
           "training": {"status": "COMPLETE", "checkpoint": str(training_checkpoint),
                        "checkpoint_sha256": training_sha,
                        "code_snapshot_sha256": (training_code_snapshot_sha256 or
                            (previous["training"].get("code_snapshot_sha256")
                             if previous else None))},
           "selection": selection, "parent": parent,
           "predicted_evaluation": predicted, "calibration": calibration,
           "runtime_readiness": readiness}
    if previous is not None and (previous["phase"] != phase or
                                 previous["selection"]["selected_checkpoint_sha256"] != selected_sha):
        raise ValueError("lifecycle phase/selected checkpoint differs")
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(output.name + ".tmp")
    staged.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                 indent=2) + "\n", encoding="utf-8")
    staged.replace(output)
    return row
