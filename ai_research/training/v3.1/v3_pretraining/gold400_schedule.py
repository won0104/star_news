"""Gold400 staged training schedule and checkpoint selection boundary.

One epoch is one complete pass over frozen train314. Dev selection uses raw
Phase 1 Extraction E or the phase's existing Gold-only active loss metric.
Calibration and predicted cascade results never select an epoch.
"""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from models.v3_pretraining.task_contract import TRAINING_PHASES
from training.v3_pretraining.selection_contract import SELECTION_TOLERANCE


CONTRACT = "V23_BASELINE_GOLD400_SIX_PHASE_MAX20_PATIENCE3_V1"
PHASE1_POLICY = "GOLD400_PHASE1_EXTRACTION_RAW_E_EARLY_STOP_V1"
DOWNSTREAM_POLICY = "GOLD400_PHASE_ACTIVE_GOLD_LOSS_EARLY_STOP_V1"
MAX_EPOCHS = 20
PATIENCE = 3


def manifest() -> dict:
    return {
        "contract": CONTRACT,
        "phase_epochs": {phase: {"max_epochs": MAX_EPOCHS, "patience": PATIENCE}
                         for phase in TRAINING_PHASES},
        "max_epochs": MAX_EPOCHS,
        "patience": PATIENCE,
        "early_stopping": True,
        "min_epochs_before_stop": PATIENCE + 1,
        "min_improvement": SELECTION_TOLERANCE,
        "immutable_epoch_checkpoints": True,
        "checkpoint_before_dev_evaluation": True,
        "phase1_selection_policy": PHASE1_POLICY,
        "phase1_selection_tuple": "(raw_E,-active_dev_loss,-epoch)",
        "downstream_selection_policy": DOWNSTREAM_POLICY,
        "downstream_selection_metric": "phase_active_gold_only_selection_metric",
        "calibration_used_for_selection": False,
        "sampler_equivalence": "1 pass == 1 complete epoch over frozen train314 order",
    }


def schedule_sha256() -> str:
    return sha256(json.dumps(manifest(), sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def validate_epochs(value: int) -> None:
    if type(value) is not int or value != MAX_EPOCHS:
        raise ValueError("Gold400 requires an immutable max-20 epoch schedule")


def _metric(row: Mapping, phase: str) -> tuple[float, float]:
    if phase == "extraction":
        if row.get("checkpoint_selection_used_calibrated_thresholds") is not False:
            raise ValueError("Gold400 Phase 1 selection used calibrated thresholds")
        primary = row.get("E")
        tie = row.get("dev_phase1_extraction_loss")
        if not isinstance(primary, (int, float)) or not isinstance(tie, (int, float)):
            raise ValueError("Gold400 Phase 1 raw selection metric missing")
        values = (float(primary), -float(tie))
    else:
        if (row.get("calibrated_thresholds_used") is not False or
                row.get("predicted_runtime_executed") is not False):
            raise ValueError("Gold400 downstream selection used predicted/calibrated metric")
        primary = row.get("selection_metric")
        if not isinstance(primary, (int, float)):
            raise ValueError("Gold400 phase active selection metric missing")
        values = (float(primary), 0.0)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Gold400 selection metric is nonfinite")
    return values


def inspect_epochs(records: Sequence[Mapping], *, phase: str,
                   selection_snapshot_sha256: str | None = None) -> dict:
    """Return best checkpoint and whether patience has stopped this phase.

    Call only after each checkpoint is immutable and its raw dev record exists.
    This pure function never reads Gold or changes a training artifact.
    """
    if (phase not in TRAINING_PHASES or not records or len(records) > MAX_EPOCHS or
            [row.get("epoch") for row in records] != list(range(1, len(records) + 1))):
        raise ValueError("Gold400 contiguous epoch records required")
    if (selection_snapshot_sha256 is not None and
            (len(selection_snapshot_sha256) != 64 or
             any(char not in "0123456789abcdef"
                 for char in selection_snapshot_sha256))):
        raise ValueError("Gold400 legacy selection snapshot SHA is invalid")
    best = None
    best_metric = None
    stale = 0
    for row in records:
        path = Path(row["checkpoint_path"])
        if (sha256(path.read_bytes()).hexdigest() != row.get("checkpoint_sha256") or
                row.get("test_access_count") != 0):
            raise ValueError("Gold400 checkpoint or test ledger differs")
        if phase == "extraction":
            from training.v3_pretraining.phase1_selection import gold400_policy_sha256
            if row.get("selection_policy_sha256") != gold400_policy_sha256():
                raise ValueError("Gold400 Phase 1 raw selection policy drifted")
        else:
            from training.v3_pretraining.code_snapshot import selection_code_snapshot
            expected_snapshot = (selection_snapshot_sha256 or
                                 selection_code_snapshot()["sha256"])
            if (row.get("phase") != phase or
                    row.get("selection_code_snapshot_sha256") != expected_snapshot):
                raise ValueError("Gold400 downstream selection code/phase drifted")
        current = _metric(row, phase)
        improved = (best is None or current[0] > best_metric[0] + SELECTION_TOLERANCE or
                    (abs(current[0] - best_metric[0]) <= SELECTION_TOLERANCE and
                     current[1] > best_metric[1] + SELECTION_TOLERANCE))
        if improved:
            best, best_metric, stale = row, current, 0
        else:
            stale += 1
        if stale >= PATIENCE and row is not records[-1]:
            raise ValueError("Gold400 epoch exists after the patience stop boundary")
    stopped = stale >= PATIENCE
    complete = stopped or len(records) == MAX_EPOCHS
    return {"schedule_contract": CONTRACT,
            "schedule_sha256": schedule_sha256(), "phase": phase,
            "completed_epochs": len(records), "stale_epochs": stale,
            "early_stopped": stopped, "phase_complete": complete,
            "selected_epoch": best["epoch"] if complete else None,
            "selected_checkpoint_path": best["checkpoint_path"] if complete else None,
            "selected_checkpoint_sha256": best["checkpoint_sha256"] if complete else None,
            "selection_metric": best_metric[0] if complete else None,
            "calibration_executed": False, "test_access_count": 0}
