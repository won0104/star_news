"""Build the D2/E1 project release from a clean Git HEAD and selected P6 files."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
import re
from pathlib import Path
import shutil
import subprocess
from typing import Mapping

import torch

from models.v3_pretraining.architecture import V3ArchitectureConfig
from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.project_release import (
    CHECKPOINT_SHA, MANIFEST_VERSION, SOURCE_ACCEPTANCE_SHA, SOURCE_POLICY_SHA,
    verify_phase6_primary_training,
)


PROJECT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT / "release/kf-deberta-base-kg-extractor-v3-main"
CHECKPOINT_FORMAT = "v3-dag-gold-only-phase-checkpoint-v11-event-feature-pair-15"
GIT_CONFIGS = (
    "runtime/configs/bcr-integrated-v23-rc1.json",
    "runtime/configs/bcr-entity-span-t14-c6-v1.json",
    "runtime/configs/bcr-time-span-t16-c8-candidate-v1.json",
    "runtime/configs/bcr-event-monotonic-bounded-v1.json",
    "runtime/configs/time-span-policy-provenance-v1.json",
    "training/configs/v3-gold400-runtime-threshold-d2-selection-v1.json",
    "training/configs/v3-gold400-runtime-d2-e1-selection-v1.json",
    "docs/v3-pretraining/public-graph-v3.schema.json",
    "docs/v3-pretraining/public-v3-projection-contract.md",
    "docs/v3-pretraining/canonical-text-policy.md",
)
ROUTING_CONFIGS = GIT_CONFIGS[:5]
TEMPLATES = ("README.md", "requirements.txt", ".gitattributes",
             "verify_bundle.py", "examples/inference.py")
RELEASE_VERSION = "3.0-project-final-d2-e1"
V30_PROJECTION_VERSION = "v3-public-projection-r6-edge-confidence"


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=PROJECT, check=True,
                          capture_output=True).stdout


def _write(root: Path, relative: str, data: bytes, files: dict[str, str]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    files[relative] = _sha(data)


def _projection_version(source: bytes) -> str:
    for statement in ast.parse(source).body:
        if (isinstance(statement, ast.Assign) and
                any(isinstance(target, ast.Name) and target.id == "PROJECTION_VERSION"
                    for target in statement.targets) and
                isinstance(statement.value, ast.Constant) and
                isinstance(statement.value.value, str)):
            return statement.value.value
    raise ValueError("PUBLIC projection version missing from runtime")


def build(checkpoint: Path, source_dir: Path, output: Path = OUTPUT, *,
          release_version: str = RELEASE_VERSION,
          template_overrides: Mapping[str, str] | None = None,
          config_overrides: Mapping[str, str] | None = None,
          checkpoint_sha256: str = CHECKPOINT_SHA,
          source_policy_sha256: str = SOURCE_POLICY_SHA,
          source_acceptance_sha256: str = SOURCE_ACCEPTANCE_SHA,
          checkpoint_format: str = CHECKPOINT_FORMAT,
          candidate_status: bool = False,
          working_tree_candidate: bool = False,
          extra_artifacts: Mapping[str, Path] | None = None) -> Path:
    """Copy HEAD code and selected artifacts; allow a release to supply its templates."""
    overrides = template_overrides or {}
    config_sources = config_overrides or {}
    extras = extra_artifacts or {}
    if (not release_version or set(overrides) - set(TEMPLATES) or
            set(config_sources) - set(GIT_CONFIGS)):
        raise ValueError("invalid project release version or template override")
    if (candidate_status != (release_version == "3.1-project-candidate-d2-e1") or
            (working_tree_candidate and not candidate_status) or
            (bool(extras) and not candidate_status) or
            any(not name.startswith("config/") or ".." in Path(name).parts
                for name in extras) or
            any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in
                (checkpoint_sha256, source_policy_sha256, source_acceptance_sha256))):
        raise ValueError("release candidate identity or artifact SHA differs")
    if not working_tree_candidate and _git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("release must be built from a clean tracked Git HEAD")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite release: {output}")
    for path, expected in ((checkpoint, checkpoint_sha256),
                           (source_dir / "source-policy.json", source_policy_sha256),
                           (source_dir / "source-acceptance.json", source_acceptance_sha256)):
        if not path.is_file() or _sha(path.read_bytes()) != expected:
            raise ValueError(f"selected artifact SHA differs: {path.name}")
    checkpoint_row = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if (checkpoint_row.get("phase") != "cluster_consumers" or
            checkpoint_row.get("format_version") != checkpoint_format):
        raise ValueError("selected Phase 6 checkpoint format differs")
    primary_training = verify_phase6_primary_training(
        checkpoint_row, checkpoint_sha256=checkpoint_sha256)
    run_id = checkpoint_row["base_config"]["run_id"]
    seed = checkpoint_row["base_config"]["seed"]
    architecture = V3ArchitectureConfig(run_id=run_id, seed=seed)
    head = _git("rev-parse", "HEAD").decode().strip()

    def source_bytes(relative: str) -> bytes:
        return ((PROJECT / relative).read_bytes() if working_tree_candidate else
                _git("show", f"HEAD:./{relative}"))

    output.mkdir(parents=True)
    files: dict[str, str] = {}
    try:
        tracked = _git("ls-tree", "-r", "--name-only", "HEAD", "--", "models", "runtime").decode().splitlines()
        for relative in tracked:
            if relative.endswith(".py"):
                _write(output, relative, source_bytes(relative), files)
        if "runtime/v3_pretraining/project_release.py" not in files:
            raise ValueError("release loader was not committed to HEAD")
        for relative in GIT_CONFIGS:
            destination = ({"training/configs/v3-gold400-runtime-threshold-d2-selection-v1.json":
                            "config/d2.json",
                            "training/configs/v3-gold400-runtime-d2-e1-selection-v1.json":
                            "config/e1.json",
                            "docs/v3-pretraining/public-graph-v3.schema.json":
                            "contracts/public-graph-v3.schema.json",
                            "docs/v3-pretraining/public-v3-projection-contract.md":
                            "contracts/public-v3-projection-contract.md",
                            "docs/v3-pretraining/canonical-text-policy.md":
                            "contracts/canonical-text-policy.md"}.get(relative, relative))
            source_relative = config_sources.get(relative, relative)
            _write(output, destination, source_bytes(source_relative), files)
        source_config = json.loads(source_bytes("runtime/configs/article-local-runtime-v22.json"))
        _write(output, "runtime/configs/article-local-runtime-v22.json",
               (json.dumps({"backbone": source_config["backbone"]},
                           ensure_ascii=False, indent=2) + "\n").encode(), files)
        for name in TEMPLATES:
            relative = overrides.get(name, "scripts/v3_release_final/" + name)
            _write(output, name, source_bytes(relative), files)
        _write(output, "weights/selected-phase6.pt", checkpoint.read_bytes(), files)
        _write(output, "config/source-policy.json",
               (source_dir / "source-policy.json").read_bytes(), files)
        _write(output, "config/source-acceptance.json",
               (source_dir / "source-acceptance.json").read_bytes(), files)
        for relative, source_path in sorted(extras.items()):
            if relative in files:
                raise ValueError("extra release artifact destination collides")
            _write(output, relative, source_path.read_bytes(), files)
        d2 = json.loads((output / "config/d2.json").read_text())
        e1 = json.loads((output / "config/e1.json").read_text())
        if (d2["checkpoint_sha256"] != checkpoint_sha256 or
                e1["checkpoint_sha256"] != checkpoint_sha256 or
                e1["d2_threshold_selection_sha256"] != files["config/d2.json"] or
                d2["source_reference"]["source_policy_file_sha256"] != source_policy_sha256 or
                d2["source_reference"]["source_acceptance_file_sha256"] != source_acceptance_sha256):
            raise ValueError("D2/E1 selected lineage differs")
        entity_pair = EntityPairPolicy(32, 256, 64)
        routing = {
            "schema_version": "v3-project-active-routing-d2-e1-v1",
            "entity_pair_policy": {"per_query_budget": 32,
                                   "query_visit_budget": 256,
                                   "posting_visit_budget": 64,
                                   "gram_keys_per_query": 4},
            "entity_pair_policy_sha256": entity_pair.sha256,
            "integrated_bounded_policy_sha256": files[ROUTING_CONFIGS[0]],
            "relation_routing_artifact": None,
            "relation_routing_mode": "CURRENT_RUNTIME_DEFAULT_WITHOUT_PREDICTED_ARTIFACT",
            "participant_salience_mode": "SOURCE_SCORE",
            "source_profile": "V23_BASELINE",
        }
        _write(output, "config/active-routing.json",
               (json.dumps(routing, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), files)
        backbone = source_config["backbone"]
        public_schema = json.loads((output / "contracts/public-graph-v3.schema.json").read_text())
        projection_version = public_schema["properties"]["projection_version"]["const"]
        runtime_projection_version = _projection_version(
            (output / "runtime/v3_pretraining/public_graph.py").read_bytes())
        if (projection_version != runtime_projection_version or
                (release_version == RELEASE_VERSION and
                 projection_version != V30_PROJECTION_VERSION)):
            raise ValueError("PUBLIC projection version differs from release identity")
        manifest = {
            "schema_version": MANIFEST_VERSION,
            "release_version": release_version,
            "status": ("FROZEN_GOLD100_REHEARSAL_CANDIDATE" if candidate_status else
                       "FROZEN_USER_SELECTED_D2_E1"),
            "training_provenance": primary_training.as_dict(),
            "inference_policy_status": ("DEV15_PROVISIONAL_SHA_BOUND" if candidate_status else
                                        "USER_SELECTED_SHA_BOUND"),
            "source_validation_status": ("DEV15_P6_CALIBRATED" if candidate_status else
                                         "PROVISIONAL_ENGINEERING_ONLY"),
            "service_validation_status": ("NOT_PREDICTED_VALIDATED" if candidate_status else
                                          "PROVISIONAL_NOT_PREDICTED_VALIDATED"),
            "service_ready": not candidate_status,
            "inference_ready": True,
            "source_git_commit": head,
            "source_tree_mode": ("WORKING_TREE_SNAPSHOT" if working_tree_candidate else
                                 "CLEAN_GIT_HEAD"),
            "source_snapshot_sha256": _sha(json.dumps(
                files, sort_keys=True, separators=(",", ":")).encode()),
            "checkpoint": {"path": "weights/selected-phase6.pt", "sha256": checkpoint_sha256,
                           "format": checkpoint_format,
                           "architecture": {"run_id": run_id, "seed": seed,
                                            "sha256": architecture.fingerprint()}},
            "binding": {"checkpoint": "weights/selected-phase6.pt",
                        "d2": "config/d2.json", "e1": "config/e1.json",
                        "source_policy": "config/source-policy.json",
                        "source_acceptance": "config/source-acceptance.json",
                        "routing": "config/active-routing.json"},
            "active_routing_policy_sha256": {name: files[name] for name in ROUTING_CONFIGS},
            "entity_pair_policy_sha256": entity_pair.sha256,
            "public": {"schema_version": public_schema["$id"],
                       "projection_version": projection_version,
                       "schema_sha256": files["contracts/public-graph-v3.schema.json"],
                       "time_policy": "r06-time-public-projection-v1",
                       "canonical_display": "v3-span-first-minimal-edit-r06-v4"},
            "backbone": {"model_id": backbone["model_id"],
                         "revision": backbone["revision"],
                         "weight_sha256": backbone["weight_sha256"],
                         "tokenizer_sha256": backbone["files_sha256"]["tokenizer.json"],
                         "packaging": "EXTERNAL_PINNED_DEPENDENCY"},
            "dependencies": ["torch>=2.4,<3", "transformers>=4.45,<5"],
            "files_sha256": dict(sorted(files.items())),
        }
        (output / "release-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    except Exception:
        shutil.rmtree(output)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(build(args.checkpoint, args.source_dir, args.output))


if __name__ == "__main__":
    main()
