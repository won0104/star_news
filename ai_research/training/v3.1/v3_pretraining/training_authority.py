"""Bind approved r06 training authority to exact input bytes and the staged DAG.

The reviewed negative sidecar describes candidate labels, not permission to use
them for main training. This separate binding must be explicitly approved.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

from training.v3_pretraining.negative_authority import ReviewedNegativeAuthority
from training.v3_pretraining.staged import DAG_EXECUTION_VERSION
from training.v3_pretraining.max6_schedule import SCHEDULE_CONTRACT


SCHEMA_VERSION = "v3-r06-training-authority-binding-v3-unified-entity"
PURPOSE = "R06_GOLD100_V23_STAGED_TRAIN73"
PREVIOUS_APPROVAL_SHA256 = "bd374074701f27230bae4c1e61748b93fb0103d6e1c1cea4e61533d25ca84bad"
PREVIOUS_APPROVAL_PATH = (Path(__file__).resolve().parents[2] /
                          "docs/v3-pretraining/r06-train73-max6-main-training-authority-binding.json")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset({
    "schema_version", "selection_status", "purpose", "main_training_allowed",
    "gold_sha256", "split_sha256", "processed_source_sha256",
    "negative_authority_file_sha256", "negative_authority_canonical_sha256",
    "review_provenance_source_sha256", "approved_train_article_count",
    "training_phase_contract", "dag_execution_version", "previous_approval_sha256",
})


def file_sha256(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def binding_sha256(path: str | Path, *, gold_path: str | Path,
                   split_path: str | Path, source_path: str | Path,
                   authority_path: str | Path, provenance_path: str | Path,
                   train_article_count: int) -> str:
    """Return binding byte SHA only after every approval and data field matches."""
    raw = Path(path).read_bytes()
    if file_sha256(PREVIOUS_APPROVAL_PATH) != PREVIOUS_APPROVAL_SHA256:
        raise ValueError("previous user-approved authority binding bytes drifted")
    binding = json.loads(raw)
    if not isinstance(binding, dict) or set(binding) != FIELDS:
        raise ValueError("main-training authority binding schema differs")
    authority = ReviewedNegativeAuthority.from_json(authority_path)
    expected = {
        "schema_version": SCHEMA_VERSION,
        "selection_status": "APPROVED",
        "purpose": PURPOSE,
        "main_training_allowed": True,
        "gold_sha256": file_sha256(gold_path),
        "split_sha256": file_sha256(split_path),
        "processed_source_sha256": file_sha256(source_path),
        "negative_authority_file_sha256": file_sha256(authority_path),
        "negative_authority_canonical_sha256": authority.sha256,
        "review_provenance_source_sha256": file_sha256(provenance_path),
        "approved_train_article_count": 73,
        "training_phase_contract": SCHEDULE_CONTRACT,
        "dag_execution_version": DAG_EXECUTION_VERSION,
        "previous_approval_sha256": PREVIOUS_APPROVAL_SHA256,
    }
    if (binding != expected or type(binding["main_training_allowed"]) is not bool or
            type(binding["approved_train_article_count"]) is not int or
            train_article_count != 73):
        raise ValueError("main-training authority is unapproved or input/DAG bytes drifted")
    if any(not _SHA.fullmatch(binding[key]) for key in (
            "gold_sha256", "split_sha256", "processed_source_sha256",
            "negative_authority_file_sha256", "negative_authority_canonical_sha256",
            "review_provenance_source_sha256", "previous_approval_sha256")):
        raise ValueError("main-training authority SHA is malformed")
    return sha256(raw).hexdigest()
