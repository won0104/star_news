"""Frozen six-epoch schedule for r06 V23 main training.

One internal sampler pass is one complete epoch over the fixed train73 order.
Selection runs only after all six immutable epoch checkpoints exist.
"""

from __future__ import annotations

from hashlib import sha256
import json

from models.v3_pretraining.task_contract import TRAINING_PHASES


SCHEDULE_CONTRACT = "V23_BASELINE_SIX_PHASE_MAX6_SELECT_BEST_V1"
MAX_EPOCHS = 6


def schedule_manifest() -> dict:
    return {
        "contract": SCHEDULE_CONTRACT,
        "phase_epochs": {phase: MAX_EPOCHS for phase in TRAINING_PHASES},
        "planned_epochs": list(range(1, MAX_EPOCHS + 1)),
        "max_epochs": MAX_EPOCHS,
        "early_stopping": False,
        "patience": None,
        "immutable_epoch_checkpoints": True,
        "selection_after_all_epochs": True,
        "sampler_equivalence": "1 pass == 1 complete epoch over frozen train73 order",
    }


def schedule_sha256() -> str:
    return sha256(json.dumps(schedule_manifest(), sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def validate_main_training_epochs(value: int) -> None:
    if type(value) is not int or value != MAX_EPOCHS:
        raise ValueError("r06 V23 main training requires exactly six complete epochs")
