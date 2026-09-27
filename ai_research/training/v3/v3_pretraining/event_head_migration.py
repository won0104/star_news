"""Explicit P4→P5 Event head migration; never rewrites the selected P4 checkpoint.

The legacy Event member encoder and pair classifier are discarded together.
The new P5 Event encoder/pair head is freshly initialized; every unchanged
parameter is copied byte-for-byte. P6 Primary owns no Event encoder.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Mapping

import torch

from models.v3_pretraining.architecture import V3Core
from models.v3_pretraining.event_heads import EVENT_PAIR_POLICY_VERSION
from training.v3_pretraining.code_snapshot import (PROJECT, relevant_code_snapshot,
                                                   training_code_snapshot)
from training.v3_pretraining.harness import HarnessConfig, fresh_full_core


MIGRATION_SCHEMA = "v3-p4-p5-event-feature-interaction-migration-v5"
LEGACY_P4_FORMAT = "v3-dag-gold-only-phase-checkpoint-v8-unified-entity-no-priority"
OLD_EVENT_PREFIX = "task_modules.event_coreference."
# The selected Gold400 P4 recorded one dirty source file. Its exact bytes were
# later committed; this narrow attestation never broadens the accepted paths.
LEGACY_P4_SOURCE_ATTESTATION = {
    "checkpoint_repository_head": "4f5622982440af0af53088871e7abb06d77ab4e7",
    "source_path": "training/v3_pretraining/attribution.py",
    "recorded_sha256": "2ef66751226b6e5fe06e705ed711e28826e7f1b6d550c0fa18db39912a9170b1",
    "later_committed_revision": "291d43649e8f8d4d393e04de79778867c0f8f884",
}


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def _file_sha(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def legacy_selection_code_snapshot_sha256(revision: str) -> str:
    """Rebuild the old dev-selector closure, including its attested P4 source byte."""
    if (not isinstance(revision, str) or len(revision) != 40 or
            any(char not in "0123456789abcdef" for char in revision)):
        raise ValueError("P4 repository revision is invalid")
    prefix = PROJECT.name + "/"
    try:
        listed = subprocess.check_output(
            ["git", "ls-tree", "-r", "-z", "--name-only", revision, "--",
             prefix + "models", prefix + "runtime", prefix + "training"],
            cwd=PROJECT.parent, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        raise ValueError("P4 legacy selection revision is unavailable") from error
    paths = [name for name in listed.decode("utf-8").split("\0")
             if name.endswith(".py") and name.startswith(prefix)]
    if not paths:
        raise ValueError("P4 legacy selection source inventory is empty")
    with TemporaryDirectory(prefix="v3-p4-selection-snapshot-") as directory:
        root = Path(directory)
        for name in paths:
            relative = Path(name.removeprefix(prefix))
            source_revision = revision
            attestation = LEGACY_P4_SOURCE_ATTESTATION
            if (revision == attestation["checkpoint_repository_head"] and
                    relative.as_posix() == attestation["source_path"]):
                source_revision = attestation["later_committed_revision"]
            try:
                source = subprocess.check_output(
                    ["git", "show", f"{source_revision}:{name}"], cwd=PROJECT.parent,
                    stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as error:
                raise ValueError("P4 legacy selection source is unavailable") from error
            if (source_revision != revision and
                    sha256(source).hexdigest() != attestation["recorded_sha256"]):
                raise ValueError("P4 attested selection source bytes differ")
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source)
        snapshot = relevant_code_snapshot(
            root=root, entrypoints=("training/v3_pretraining/epoch_selection.py",
                                    "training/v3_pretraining/code_snapshot.py"))
    return snapshot["sha256"]


def verify_legacy_source_snapshot(checkpoint: Mapping) -> str:
    """Verify P4 code bytes at its HEAD or the one explicit later attestation."""
    revision = checkpoint.get("repository_head")
    snapshot = checkpoint.get("relevant_code_snapshot")
    if (not isinstance(revision, str) or len(revision) != 40 or
            not isinstance(snapshot, dict) or not isinstance(snapshot.get("files"), dict) or
            not isinstance(snapshot.get("sha256"), str) or
            snapshot["sha256"] != _digest(snapshot["files"])):
        raise ValueError("P4 legacy code snapshot is malformed")
    diverged: list[tuple[str, str]] = []
    for relative, expected_sha in snapshot["files"].items():
        if (not isinstance(relative, str) or not relative.endswith(".py") or
                not isinstance(expected_sha, str) or len(expected_sha) != 64):
            raise ValueError("P4 legacy code snapshot contains an invalid path/hash")
        try:
            old_bytes = subprocess.check_output(
                ["git", "show", f"{revision}:{PROJECT.name}/{relative}"],
                cwd=PROJECT.parent, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise ValueError("P4 legacy source is not available at its recorded HEAD") from error
        if sha256(old_bytes).hexdigest() != expected_sha:
            diverged.append((relative, expected_sha))
    if diverged:
        attestation = LEGACY_P4_SOURCE_ATTESTATION
        if (revision != attestation["checkpoint_repository_head"] or
                diverged != [(attestation["source_path"],
                              attestation["recorded_sha256"])]):
            raise ValueError("P4 legacy source differed from its recorded Git HEAD")
        later = attestation["later_committed_revision"]
        try:
            subprocess.check_call(
                ["git", "merge-base", "--is-ancestor", revision, later],
                cwd=PROJECT.parent, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            committed_bytes = subprocess.check_output(
                ["git", "show", f"{later}:{PROJECT.name}/{attestation['source_path']}"],
                cwd=PROJECT.parent, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise ValueError("P4 later source attestation is unavailable") from error
        if sha256(committed_bytes).hexdigest() != attestation["recorded_sha256"]:
            raise ValueError("P4 later source attestation bytes differ")
    return snapshot["sha256"]


def migrate_event_head_state(old_state: Mapping[str, torch.Tensor],
                             core: V3Core) -> dict[str, torch.Tensor]:
    """Discard only the verified legacy Event head and preserve all common bytes."""
    target = core.state_dict()
    old_member = {key for key in old_state
                  if key.startswith(OLD_EVENT_PREFIX + "member_encoder.")}
    new_event = {key for key in target if key.startswith(OLD_EVENT_PREFIX)}
    old_pair = {key for key in old_state if key.startswith(OLD_EVENT_PREFIX + "pair.")}
    hidden = core.config.context.hidden_size
    legacy_member_shapes = {
        "member_encoder.0.weight": (hidden * 8 + 8,),
        "member_encoder.0.bias": (hidden * 8 + 8,),
        "member_encoder.1.weight": (hidden, hidden * 8 + 8),
        "member_encoder.1.bias": (hidden,),
        "member_encoder.3.weight": (hidden,),
        "member_encoder.3.bias": (hidden,),
    }
    if (old_member != {OLD_EVENT_PREFIX + suffix for suffix in legacy_member_shapes} or
            any(tuple(old_state[OLD_EVENT_PREFIX + suffix].shape) != shape
                for suffix, shape in legacy_member_shapes.items()) or
            any("member_encoder" in key for key in target)):
        raise ValueError("legacy Event member encoder inventory differs")
    legacy_pair_shapes = {
        "pair.0.weight": (hidden * 3 + 4,),
        "pair.0.bias": (hidden * 3 + 4,),
        "pair.1.weight": (hidden, hidden * 3 + 4),
        "pair.1.bias": (hidden,),
        "pair.3.weight": (2, hidden),
        "pair.3.bias": (2,),
    }
    if (old_pair != {OLD_EVENT_PREFIX + suffix for suffix in legacy_pair_shapes} or
            any(tuple(old_state[OLD_EVENT_PREFIX + suffix].shape) != shape
                for suffix, shape in legacy_pair_shapes.items())):
        raise ValueError("P4 Event pair head does not match the declared legacy architecture")
    common = set(target) - new_event
    if set(old_state) != common | old_member | old_pair:
        raise ValueError("P4 model state has unexpected or missing parameter keys")
    result = {}
    for key, initialized in target.items():
        value = initialized if key in new_event else old_state[key]
        if value.shape != initialized.shape or value.dtype != initialized.dtype:
            raise ValueError(f"P4/P5 parameter shape or dtype changed: {key}")
        result[key] = value
    return result


def build_migration_artifact(parent_path: str | Path, core: V3Core) -> dict:
    parent = torch.load(parent_path, map_location="cpu", weights_only=True)
    if (not isinstance(parent, dict) or parent.get("phase") != "entity_role_time_attribution" or
            parent.get("format_version") != LEGACY_P4_FORMAT or
            parent.get("base_config_sha256") != _digest(parent.get("base_config"))):
        raise ValueError("migration parent must be the old selected Phase 4 checkpoint")
    old_snapshot_sha = verify_legacy_source_snapshot(parent)
    migrate_event_head_state(parent["model_state"], core)
    return {
        "schema_version": MIGRATION_SCHEMA,
        "parent_phase": "entity_role_time_attribution",
        "parent_checkpoint_sha256": _file_sha(parent_path),
        "legacy_repository_head": parent["repository_head"],
        "legacy_code_snapshot_sha256": old_snapshot_sha,
        "legacy_source_attestation": (
            LEGACY_P4_SOURCE_ATTESTATION
            if parent["repository_head"] ==
            LEGACY_P4_SOURCE_ATTESTATION["checkpoint_repository_head"] and
            parent["relevant_code_snapshot"]["files"].get(
                LEGACY_P4_SOURCE_ATTESTATION["source_path"]) ==
            LEGACY_P4_SOURCE_ATTESTATION["recorded_sha256"] else None),
        "legacy_selection_code_snapshot_sha256": legacy_selection_code_snapshot_sha256(
            parent["repository_head"]),
        "target_code_snapshot_sha256": training_code_snapshot()["sha256"],
        "base_config_sha256": parent["base_config_sha256"],
        "event_pair_input_schema": EVENT_PAIR_POLICY_VERSION,
        "key_move": None,
        "discarded_head": "event_coreference.member_encoder+pair",
        "new_head": "event_coreference.EventFeatureEncoderV3+symmetric_pair+channel_interaction:FRESH_INIT",
        "status": "P4_SELECTED_TO_P5_FRESH_EVENT_HEAD_ONLY",
    }


def load_migration_artifact(path: str | Path, *, parent_path: str | Path,
                            core: V3Core) -> tuple[dict, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = build_migration_artifact(parent_path, core)
    if payload != expected:
        raise ValueError("P4→P5 migration artifact or code/checkpoint binding drifted")
    return payload, _file_sha(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seal an explicit selected-P4 to P5 head migration")
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = torch.load(args.parent, map_location="cpu", weights_only=True)
    if not isinstance(parent, dict) or not isinstance(parent.get("base_config"), dict):
        raise ValueError("P4 checkpoint has no base config")
    base = HarnessConfig(**parent["base_config"])
    core = fresh_full_core(base)
    artifact = build_migration_artifact(args.parent, core)
    if args.output.exists():
        raise FileExistsError("migration artifact is immutable")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True)
                           + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
