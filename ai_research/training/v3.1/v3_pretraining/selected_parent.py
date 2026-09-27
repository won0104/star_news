"""다음 Gold-only phase의 부모를 이전 phase 선택 기록에서 확정한다."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from models.v3_pretraining.task_contract import TRAINING_PHASES


@dataclass(frozen=True, slots=True)
class SelectedParentBinding:
    phase: str
    checkpoint_sha256: str
    selection_record_sha256: str
    selected_epoch: int


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def resolve_selected_parent(*, selection_record_path: str | Path,
                            predecessor_phase: str,
                            supplied_parent_path: str | Path | None,
                            gold400: bool) -> tuple[Path, SelectedParentBinding]:
    """Validate selected record, optional epoch ledger, and the checkpoint bytes.

    The record's checkpoint path is deliberately exact: moving an old result
    requires an explicit recovery procedure, not an implicit SHA-only fallback.
    """
    if predecessor_phase not in TRAINING_PHASES:
        raise ValueError("selected parent predecessor phase differs")
    record_path = Path(selection_record_path).resolve()
    if record_path.name != "selected-checkpoint.json" or not record_path.is_file():
        raise ValueError("selected parent record is missing")
    selected = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(selected, dict):
        raise ValueError("selected parent record is not an object")
    epoch = selected.get("selected_epoch")
    checkpoint_value = selected.get("selected_checkpoint_path")
    checkpoint_sha = selected.get("selected_checkpoint_sha256")
    maximum = 20 if gold400 else 6
    if (selected.get("phase") != predecessor_phase or type(epoch) is not int or
            not 1 <= epoch <= maximum or not isinstance(checkpoint_value, str) or
            not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64 or
            any(char not in "0123456789abcdef" for char in checkpoint_sha)):
        raise ValueError("selected parent phase/epoch/checkpoint record differs")
    checkpoint = Path(checkpoint_value).resolve()
    if (checkpoint.parent.parent != record_path.parent or
            checkpoint.parent.name != f"epoch-{epoch:02d}" or
            checkpoint.name != "checkpoint.pt" or not checkpoint.is_file() or
            (supplied_parent_path is not None and
             Path(supplied_parent_path).resolve() != checkpoint) or
            _sha(checkpoint) != checkpoint_sha):
        raise ValueError("supplied parent is not the predecessor selected checkpoint")
    ledger_path = record_path.with_name("selection-ledger.json")
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        records = ledger.get("epochs") if isinstance(ledger, dict) else None
        if not isinstance(records, list):
            raise ValueError("selected parent epoch ledger differs")
        if gold400:
            from training.v3_pretraining.gold400_schedule import inspect_epochs
            expected = inspect_epochs(records, phase=predecessor_phase)
        elif predecessor_phase == "extraction":
            from training.v3_pretraining.phase1_selection import select_completed_epochs
            from training.v3_pretraining.mini_rehearsal_contract import (
                MAX_EPOCHS as REHEARSAL_EPOCHS, SCHEDULE_CONTRACT,
                selection_policy_manifest)
            if ledger.get("schedule_contract") == SCHEDULE_CONTRACT:
                expected = select_completed_epochs(
                    records, expected_epochs=REHEARSAL_EPOCHS,
                    expected_policy=selection_policy_manifest(),
                    schedule_contract=SCHEDULE_CONTRACT)
            else:
                expected = select_completed_epochs(records)
        else:
            from training.v3_pretraining.epoch_selection import select_completed_epochs
            expected = select_completed_epochs(records)
            if ledger.get("schedule_contract") is not None:
                from training.v3_pretraining.mini_rehearsal_contract import (
                    MAX_EPOCHS, SCHEDULE_CONTRACT)
                if (ledger["schedule_contract"] != SCHEDULE_CONTRACT or
                        len(records) != MAX_EPOCHS):
                    raise ValueError("selected parent rehearsal schedule differs")
                expected = {**expected, "schedule_contract": SCHEDULE_CONTRACT,
                            "completed_epochs": MAX_EPOCHS}
        if expected != selected:
            raise ValueError("selected parent record differs from epoch ledger")
    return checkpoint, SelectedParentBinding(
        predecessor_phase, checkpoint_sha, _sha(record_path), epoch)
