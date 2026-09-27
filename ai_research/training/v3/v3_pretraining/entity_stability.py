"""Fail-closed Phase 4→5 Entity identity stability validation binding.

This loader verifies lineage only. It neither evaluates predicted quality nor
creates a PREDICTED_VALIDATED artifact during preflight.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re


SCHEMA_VERSION = "v23-post-assertor-entity-stability-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
SHA_FIELDS = frozenset({
    "phase3_entity_identity_checkpoint_sha256", "phase4_checkpoint_sha256",
    "source_policy_sha256", "source_acceptance_sha256",
    "entity_pair_policy_sha256", "entity_pair_artifact_sha256",
    "entity_identity_policy_sha256", "asserted_by_option_artifact_sha256",
    "predicted_validation_report_sha256",
})
FIELDS = SHA_FIELDS | {"schema_version", "selection_status"}


def load_predicted_validated(path: str | Path, *, expected: dict[str, str]) -> str:
    """Validate all predecessor/policy bytes and return the artifact byte SHA."""
    raw = Path(path).read_bytes()
    row = json.loads(raw)
    if (not isinstance(row, dict) or set(row) != FIELDS or
            row.get("schema_version") != SCHEMA_VERSION or
            row.get("selection_status") != "PREDICTED_VALIDATED" or
            set(expected) != SHA_FIELDS or
            any(not isinstance(row.get(key), str) or not _SHA.fullmatch(row[key])
                or row[key] != expected[key] for key in SHA_FIELDS)):
        raise ValueError("Phase 4 Entity stability artifact is absent, unvalidated, or drifted")
    return sha256(raw).hexdigest()
