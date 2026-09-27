"""Gold100 three-epoch rehearsal authority, separate from main training approval."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from models.v3_pretraining.task_contract import TRAINING_PHASES
from training.v3_pretraining.code_snapshot import training_code_snapshot
from training.v3_pretraining.negative_authority import ReviewedNegativeAuthority
from training.v3_pretraining.phase1_selection import policy_manifest
from training.v3_pretraining.staged import DAG_EXECUTION_VERSION


MAX_EPOCHS = 3
SCHEDULE_CONTRACT = "V23_BASELINE_SIX_PHASE_MAX3_REHEARSAL_ONLY_V1"
POLICY_VERSION = "PHASE1_EXTRACTION_MAX3_TRIGGER_EXACT_SCORE_REHEARSAL_V1"
BINDING_SCHEMA = "v3-r06-gold100-max3-rehearsal-authority-v1"


def _sha(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def schedule_manifest() -> dict:
    return {"contract": SCHEDULE_CONTRACT,
            "phase_epochs": {phase: MAX_EPOCHS for phase in TRAINING_PHASES},
            "planned_epochs": [1, 2, 3], "max_epochs": MAX_EPOCHS,
            "early_stopping": False, "selection_after_all_epochs": True,
            "immutable_epoch_checkpoints": True,
            "sampler_equivalence": "1 pass == 1 complete epoch over frozen train73 order",
            "main_training_parent_allowed": False}


def schedule_sha256() -> str:
    return _digest(schedule_manifest())


def selection_policy_manifest() -> dict:
    result = policy_manifest()
    result.update({"version": POLICY_VERSION,
                   "schedule_sha256": schedule_sha256(),
                   "planned_epochs": [1, 2, 3]})
    return result


def selection_policy_sha256() -> str:
    return _digest(selection_policy_manifest())


def binding_sha256(path: str | Path, *, gold_path: str | Path,
                   split_path: str | Path, source_path: str | Path,
                   negative_path: str | Path, provenance_path: str | Path,
                   prior_approved_path: str | Path,
                   dev_selection_authority_path: str | Path,
                   train_article_count: int) -> str:
    """Require explicit rehearsal approval and exact current code/data bytes."""
    raw = Path(path).read_bytes()
    row = json.loads(raw)
    negative = ReviewedNegativeAuthority.from_json(negative_path)
    expected = {
        "schema_version": BINDING_SCHEMA,
        "selection_status": "APPROVED_REHEARSAL_ONLY",
        "purpose": "GOLD100_TRAIN73_DEV15_P1_P6_THREE_EPOCH_MINI_REHEARSAL_ONLY",
        "main_training_allowed": False,
        "may_parent_1k_main_training": False,
        "approved_train_article_count": 73,
        "gold_sha256": _sha(gold_path),
        "split_sha256": _sha(split_path),
        "processed_source_sha256": _sha(source_path),
        "negative_authority_file_sha256": _sha(negative_path),
        "negative_authority_canonical_sha256": negative.sha256,
        "review_provenance_source_sha256": _sha(provenance_path),
        "previous_approved_binding_sha256": _sha(prior_approved_path),
        "dev_selection_authority_sha256": _sha(dev_selection_authority_path),
        "dag_execution_version": DAG_EXECUTION_VERSION,
        "schedule_contract": SCHEDULE_CONTRACT,
        "schedule_sha256": schedule_sha256(),
        "phase1_selection_policy_sha256": selection_policy_sha256(),
        "training_code_snapshot_sha256": training_code_snapshot()["sha256"],
    }
    if row != expected or train_article_count != 73:
        raise ValueError("Gold100 rehearsal authority/code/data/schedule differs")
    return sha256(raw).hexdigest()
