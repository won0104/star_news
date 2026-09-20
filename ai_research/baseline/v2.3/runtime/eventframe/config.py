"""Pinned runtime configuration and SHA validation.

Paths are repository-relative. Checkpoint identity is validated before deserialization;
there is no implicit fallback to another experiment or production checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .contracts import CheckpointMismatchError, RuntimeConfigurationError


def digest(path: Path) -> str:
    block = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            block.update(chunk)
    return block.hexdigest()


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    path: Path
    root: Path
    payload: Mapping[str, Any]

    @property
    def runtime_config_id(self) -> str:
        return str(self.payload["runtime_config_id"])

    @property
    def schema_version(self) -> str:
        return str(self.payload["schema_version"])

    def resolve(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute():
            raise RuntimeConfigurationError("runtime config paths must be repository-relative")
        resolved = (self.root / path).resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError as error:
            raise RuntimeConfigurationError(f"path escapes repository: {relative}") from error
        return resolved

    def artifact(self, name: str) -> Path:
        artifacts = self.payload.get("artifacts")
        if not isinstance(artifacts, Mapping) or name not in artifacts:
            raise RuntimeConfigurationError(f"missing runtime artifact: {name}")
        row = artifacts[name]
        if not isinstance(row, Mapping):
            raise RuntimeConfigurationError(f"artifact {name} must be an object")
        path = self.resolve(str(row["path"]))
        if not path.is_file():
            raise RuntimeConfigurationError(f"artifact is absent: {row['path']}")
        actual = digest(path)
        expected = str(row["sha256"])
        if actual != expected:
            raise CheckpointMismatchError(
                f"{name} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        return path

    def backbone_cache_root(self) -> Path | None:
        payload = self.payload["backbone"]
        variable = payload.get("cache_root_env")
        if variable:
            value = os.environ.get(str(variable))
            if value:
                return Path(value).expanduser().resolve()
        relative = payload.get("cache_root")
        return self.resolve(str(relative)) if relative else None

    def backbone_snapshot(self) -> Path:
        """Resolve the immutable HF snapshot and validate declared files.

        A release bundle may keep the pinned base model as an explicit external
        dependency. Component weights remain bundle-local; only this declared
        base snapshot may be loaded from a caller-provided HF cache or network.
        """

        payload = self.payload["backbone"]
        cache_root = self.backbone_cache_root()
        if cache_root is not None:
            escaped = str(payload["model_id"]).replace("/", "--")
            local = cache_root / f"models--{escaped}" / "snapshots" / str(payload["revision"])
            if local.is_dir():
                snapshot = local
            else:
                snapshot = None
        else:
            snapshot = None
        if snapshot is None:
            try:
                from huggingface_hub import snapshot_download

                snapshot = Path(
                    snapshot_download(
                        repo_id=str(payload["model_id"]),
                        revision=str(payload["revision"]),
                        cache_dir=str(cache_root) if cache_root else None,
                        local_files_only=bool(payload.get("local_files_only", False)),
                    )
                )
            except Exception as error:
                raise RuntimeConfigurationError(
                    "pinned external backbone snapshot could not be resolved"
                ) from error
        declared = dict(payload.get("files_sha256") or {})
        declared.setdefault("pytorch_model.bin", str(payload["weight_sha256"]))
        for name, expected in declared.items():
            path = snapshot / name
            if not path.is_file():
                raise RuntimeConfigurationError(f"backbone file is absent: {name}")
            actual = digest(path)
            if actual != expected:
                raise CheckpointMismatchError(
                    f"backbone {name} SHA-256 mismatch: expected {expected}, got {actual}"
                )
        return snapshot

    def validate(self) -> dict[str, Any]:
        required = tuple(
            self.payload.get(
                "required_artifacts",
                (
                    "semantic_checkpoint",
                    "semantic_boundary_source_checkpoint",
                    "participant_b2_checkpoint",
                    "backbone_weights",
                    "backbone_tokenizer_config",
                    "backbone_cache_manifest",
                ),
            )
        )
        checked = {}
        for name in required:
            path = self.artifact(name)
            checked[name] = {"path": str(path.relative_to(self.root)), "sha256": digest(path)}
        if self.payload.get("experimental_auxiliary_signal_enabled") is not False:
            raise RuntimeConfigurationError("experimental auxiliary signals must remain disabled")
        if self.payload.get("graph_assembly_enabled") is not False:
            raise RuntimeConfigurationError("graph assembly must remain disabled in the runtime candidate")
        artifacts = self.payload.get("artifacts", {})
        v3_socket = any(name in artifacts for name in (
            "semantic_proposer_checkpoint", "semantic_v3_checkpoint",
        ))
        if v3_socket:
            if not all(name in artifacts for name in (
                "semantic_proposer_checkpoint", "semantic_v3_checkpoint",
            )):
                raise RuntimeConfigurationError("Canonical V3 needs both pinned semantic checkpoints")
            semantic = self.payload.get("semantic", {})
            candidate_policy = semantic.get("candidate_policy", {})
            acceptance = semantic.get("acceptance", {})
            if (semantic.get("architecture") != "CANONICAL_A_TOP32_TO_CANONICAL_V3"
                or candidate_policy.get("family") != "RUNTIME_LIKE_TOP32"
                or int(candidate_policy.get("top_k", 0)) != 32
                or candidate_policy.get("gold_injection") is not False
                or semantic.get("proposal_metadata_feature_use") is not False
                or acceptance.get("family") != "INDEPENDENT_SEMANTIC_AND_BOUNDARY"
                or self.payload.get("new_content_preprocessor_enabled") is not False):
                raise RuntimeConfigurationError("pinned release-v2 Semantic socket contract differs")
        if self.payload.get("participant_b2_enabled") is not True:
            raise RuntimeConfigurationError("the runtime candidate requires the fixed Participant B2 lane")
        components = self.payload.get("components", {})
        entity_resolution = self.payload.get("entity_resolution", {})
        expected_entity_resolution = bool(
            entity_resolution.get("enabled")
            and components.get("entity_coreference", {}).get("enabled")
            and components.get("participant_entity_resolution", {}).get("enabled")
        )
        if self.payload.get("entity_resolution_enabled") != expected_entity_resolution:
            raise RuntimeConfigurationError(
                "entity_resolution_enabled must exactly reflect active Entity identity and Participant resolution"
            )
        time_enabled = bool(self.payload.get("components", {}).get("time", {}).get("enabled"))
        normalization_enabled = bool(self.payload.get("time_normalization", {}).get("enabled"))
        if self.payload.get("time_resolution_enabled") != (
            time_enabled and normalization_enabled
        ):
            raise RuntimeConfigurationError(
                "time_resolution_enabled must exactly reflect active deterministic Time normalization"
            )
        event_identity_enabled = bool(
            components.get("event_coreference", {}).get("enabled")
        )
        event_identity = self.payload.get("event_identity", {})
        if event_identity_enabled != bool(event_identity.get("enabled")):
            raise RuntimeConfigurationError(
                "event identity config must exactly reflect the active component"
            )
        if event_identity_enabled:
            threshold = float(event_identity.get("threshold", -1.0))
            if ((v3_socket and threshold != 0.4)
                or (not v3_socket and threshold != 0.64)):
                raise RuntimeConfigurationError("selected Event identity threshold differs from its fixed config")
            if event_identity.get("clustering") != "COMPLETE_LINK_EXACT_TIME_CONFLICT":
                raise RuntimeConfigurationError("Event identity clustering policy mismatch")
            if event_identity.get("cross_article_identity") is not False:
                raise RuntimeConfigurationError("Event identity must remain article-local")
            if self.payload.get("compact_default_execution") is True:
                if (event_identity.get("raw_eventframe_preserved") is not False
                    or event_identity.get("legacy_compat_raw_eventframe_preserved")
                    is not True):
                    raise RuntimeConfigurationError(
                        "v2.2 compact EventFrame and legacy compatibility lifetimes differ"
                    )
            elif event_identity.get("raw_eventframe_preserved") is not True:
                raise RuntimeConfigurationError(
                    "legacy Event identity must preserve raw EventFrame evidence"
                )
        execution = self.payload.get("execution", {})
        if execution.get("model_dtype") != "float32":
            raise RuntimeConfigurationError("the runtime candidate requires explicit float32 model dtype")
        if int(execution.get("cpu_threads", 0)) <= 0:
            raise RuntimeConfigurationError("execution.cpu_threads must be positive")
        return {
            "status": "PASS",
            "runtime_config_id": self.runtime_config_id,
            "config_sha256": digest(self.path),
            "artifacts": checked,
        }


def load_runtime_config(path: str | Path, *, root: str | Path | None = None) -> RuntimeConfig:
    path = Path(path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeConfigurationError("runtime config must be a JSON object")
    expected_schema = "articlelocal-eventframe-runtime-config-v1"
    if payload.get("schema_version") != expected_schema:
        raise RuntimeConfigurationError(f"unsupported runtime schema: {payload.get('schema_version')}")
    if root:
        resolved_root = Path(root).resolve()
    elif payload.get("path_base") == "config_directory_parent":
        resolved_root = path.parent.parent.resolve()
    else:
        resolved_root = repository_root()
    config = RuntimeConfig(path, resolved_root, payload)
    config.validate()
    return config
