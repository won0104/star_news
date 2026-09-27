"""Fail-closed Gold400 approval binding for the user-frozen draft sidecar.

The user froze the original DRAFT annotations for training. This binding
records that decision without relabeling their review status or editing input.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from training.v3_pretraining.corpus import SOURCE, SPLIT
from training.v3_pretraining.gold400_schedule import CONTRACT, schedule_sha256
from training.v3_pretraining.negative_authority import ReviewedNegativeAuthority
from training.v3_pretraining.staged import DAG_EXECUTION_VERSION


SCHEMA = "v23-gold400-user-frozen-training-authority-v1"
PURPOSE = "R06_GOLD400_V23_STAGED_TRAIN314"
STATUS = "APPROVED_USER_FROZEN_DRAFT_NOT_HUMAN_REVIEWED"


def file_sha256(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def expected_binding(*, gold_path: str | Path, authority_path: str | Path,
                     provenance_path: str | Path, input_manifest_path: str | Path) -> dict:
    authority = ReviewedNegativeAuthority.from_json(authority_path)
    input_manifest = json.loads(Path(input_manifest_path).read_text(encoding="utf-8"))
    if (input_manifest.get("gold_sha256") != file_sha256(gold_path) or
            input_manifest.get("negative_authority_file_sha256") != file_sha256(authority_path) or
            input_manifest.get("negative_authority_canonical_sha256") != authority.sha256 or
            input_manifest.get("split_counts") != {"train": 314, "dev": 49, "test": 37} or
            input_manifest.get("source_review_status") != "DRAFT_USER_FROZEN"):
        raise ValueError("Gold400 prepared input manifest differs")
    return {
        "schema_version": SCHEMA, "selection_status": STATUS,
        "purpose": PURPOSE, "main_training_allowed": True,
        "gold_sha256": file_sha256(gold_path),
        "original_gold_file_sha256": [row["sha256"] for row in input_manifest["source_files"]
                                        if row["kind"] == "gold"],
        "original_sidecar_file_sha256": [row["sha256"] for row in input_manifest["source_files"]
                                           if row["kind"] == "sidecar"],
        "split_sha256": file_sha256(SPLIT),
        "processed_source_sha256": file_sha256(SOURCE),
        "negative_authority_file_sha256": file_sha256(authority_path),
        "negative_authority_canonical_sha256": authority.sha256,
        "projection_provenance_sha256": file_sha256(provenance_path),
        "input_manifest_sha256": file_sha256(input_manifest_path),
        "approved_train_article_count": 314,
        "training_phase_contract": CONTRACT,
        "schedule_sha256": schedule_sha256(),
        "dag_execution_version": DAG_EXECUTION_VERSION,
        "source_review_status": "DRAFT_USER_FROZEN",
        "review_claim": "USER_FROZEN_NOT_HUMAN_REVIEWED",
    }


def binding_sha256(path: str | Path, *, gold_path: str | Path,
                   authority_path: str | Path, provenance_path: str | Path,
                   input_manifest_path: str | Path, train_article_count: int) -> str:
    if train_article_count != 314:
        raise ValueError("Gold400 train314 article count differs")
    raw = Path(path).read_bytes()
    if json.loads(raw) != expected_binding(
            gold_path=gold_path, authority_path=authority_path,
            provenance_path=provenance_path,
            input_manifest_path=input_manifest_path):
        raise ValueError("Gold400 user-frozen authority/input/schedule/DAG drifted")
    return sha256(raw).hexdigest()
