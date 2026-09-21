"""Single Gold-free Article -> canonical Article-local KG entry point.

v2.2 assembly config은 compact ResolvedGraphState direct 경로를 선택한다.
legacy config의 raw graph adapter는 호환 분석 API에만 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .eventframe import ArticleInput, ArticleLocalRuntime
from .eventframe.contracts import RuntimeConfigurationError
from .graph import ArticleLocalKGAssembler, ArticleLocalKnowledgeGraphResult
from .graph.compact_assembly import (
    COMPACT_ASSEMBLY_CONFIG_SCHEMA_VERSION, CompactArticleLocalKGAssembler,
    CompactKnowledgeGraphResult,
)
from .lifecycle import DiagnosticSink, ExecutionPolicy


PIPELINE_CONFIG_SCHEMA_VERSION = "articlelocal-goldfree-kg-pipeline-config-v1"


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


@dataclass(frozen=True, slots=True)
class GoldFreeKGPipelineConfig:
    """Validated paths and identities for one fixed end-to-end runtime."""

    path: Path
    repository_root: Path
    payload: Mapping[str, Any]
    runtime_config_path: Path
    assembly_config_path: Path
    checkpoint_manifest_path: Path

    @property
    def pipeline_config_id(self) -> str:
        return str(self.payload["pipeline_config_id"])

    def validation(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "pipeline_config_id": self.pipeline_config_id,
            "pipeline_config_sha256": _digest(self.path),
            "runtime_config": {
                "path": str(self.runtime_config_path.relative_to(self.repository_root)),
                "sha256": _digest(self.runtime_config_path),
            },
            "assembly_config": {
                "path": str(self.assembly_config_path.relative_to(self.repository_root)),
                "sha256": _digest(self.assembly_config_path),
            },
            "checkpoint_manifest": {
                "path": str(self.checkpoint_manifest_path.relative_to(self.repository_root)),
                "sha256": _digest(self.checkpoint_manifest_path),
            },
        }


def _resolve_checked(root: Path, row: Mapping[str, Any], name: str) -> Path:
    relative = Path(str(row["path"]))
    if relative.is_absolute():
        raise RuntimeConfigurationError(f"{name} path must be repository-relative")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise RuntimeConfigurationError(f"{name} path escapes repository root") from error
    if not path.is_file():
        raise RuntimeConfigurationError(f"{name} is absent: {relative}")
    actual = _digest(path)
    expected = str(row["sha256"])
    if actual != expected:
        raise RuntimeConfigurationError(
            f"{name} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return path


def load_goldfree_kg_pipeline_config(
    path: str | Path | None = None,
    *,
    repository_root: str | Path | None = None,
) -> GoldFreeKGPipelineConfig:
    config_path = (
        Path(path).resolve() if path is not None else
        Path(__file__).resolve().parent / "configs" /
        "goldfree-article-kg-pipeline-v22.json"
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PIPELINE_CONFIG_SCHEMA_VERSION:
        raise RuntimeConfigurationError("unsupported Gold-free KG pipeline config schema")
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[1]
    )
    runtime_config_path = _resolve_checked(root, payload["runtime_config"], "runtime config")
    assembly_config_path = _resolve_checked(root, payload["assembly_config"], "assembly config")
    checkpoint_manifest_path = _resolve_checked(
        root, payload["checkpoint_manifest"], "checkpoint manifest"
    )

    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assembly_payload = json.loads(assembly_config_path.read_text(encoding="utf-8"))
    if runtime_payload.get("runtime_config_id") != payload.get("runtime_config_id"):
        raise RuntimeConfigurationError("pipeline/runtime config identity mismatch")
    if assembly_payload.get("assembly_config_id") != payload.get("assembly_config_id"):
        raise RuntimeConfigurationError("pipeline/assembly config identity mismatch")
    if assembly_payload.get("source_runtime_config_id") != payload.get("runtime_config_id"):
        raise RuntimeConfigurationError("assembly input is not the fixed pipeline runtime")

    manifest = json.loads(checkpoint_manifest_path.read_text(encoding="utf-8"))
    manifest_base = checkpoint_manifest_path.parent.relative_to(root)
    manifest_weights = {}
    for row in manifest.get("weights", []):
        relative = Path(str(row["relative_path"]))
        expected = str(row["sha256"])
        manifest_weights[relative.as_posix()] = expected
        manifest_weights[(manifest_base / relative).as_posix()] = expected
    for row in runtime_payload.get("artifacts", {}).values():
        relative = str(row["path"])
        expected = str(row["sha256"])
        if manifest_weights.get(relative) != expected:
            raise RuntimeConfigurationError(
                f"runtime artifact is not pinned by checkpoint manifest: {relative}"
            )
    if payload.get("gold_runtime_dependency_allowed") is not False:
        raise RuntimeConfigurationError("Gold dependency must remain disabled in runtime")
    if payload.get("release_version") == "2.2":
        if (runtime_payload.get("release_version") != "2.2"
            or runtime_payload.get("compact_default_execution") is not True
            or assembly_payload.get("schema_version") != COMPACT_ASSEMBLY_CONFIG_SCHEMA_VERSION
            or assembly_payload.get("public_schema_version") !=
            payload.get("public_output_schema_version")
            or assembly_payload.get("output_profile_contract") !=
            payload.get("output_profile_contract")):
            raise RuntimeConfigurationError("pinned v2.2 compact pipeline contract differs")
    return GoldFreeKGPipelineConfig(
        path=config_path,
        repository_root=root,
        payload=payload,
        runtime_config_path=runtime_config_path,
        assembly_config_path=assembly_config_path,
        checkpoint_manifest_path=checkpoint_manifest_path,
    )


class ArticleLocalKGPipeline:
    """Config에 따라 v2.2 direct 또는 명시적 legacy assembly를 실행한다."""

    def __init__(
        self,
        config: GoldFreeKGPipelineConfig,
        runtime: ArticleLocalRuntime,
        assembler: ArticleLocalKGAssembler | CompactArticleLocalKGAssembler,
    ) -> None:
        if runtime.config.runtime_config_id != assembler.config.runtime_config_id:
            raise RuntimeConfigurationError("runtime and assembler config IDs differ")
        if runtime.config.runtime_config_id != config.payload["runtime_config_id"]:
            raise RuntimeConfigurationError("runtime does not match Gold-free pipeline config")
        self.config = config
        self.runtime = runtime
        self.assembler = assembler

    @classmethod
    def from_config(
        cls,
        path: str | Path | None = None,
        *,
        device: str = "auto",
        repository_root: str | Path | None = None,
    ) -> "ArticleLocalKGPipeline":
        config = load_goldfree_kg_pipeline_config(path, repository_root=repository_root)
        runtime = ArticleLocalRuntime.from_config(config.runtime_config_path, device=device)
        assembly_payload = json.loads(config.assembly_config_path.read_text(encoding="utf-8"))
        assembler = (
            CompactArticleLocalKGAssembler.from_config(config.assembly_config_path)
            if assembly_payload.get("schema_version") == COMPACT_ASSEMBLY_CONFIG_SCHEMA_VERSION
            else ArticleLocalKGAssembler.from_config(config.assembly_config_path)
        )
        return cls(config, runtime, assembler)

    def run(
        self,
        article: ArticleInput | Mapping[str, Any],
        *,
        output_profile: str = "PUBLIC",
        debug_trace: bool = False,
        diagnostic_sink: DiagnosticSink | None = None,
        validation_capture=None,
        application_profiler=None,
        routing_observer=None,
        event_identity_audit_sink=None,
        entity_span_bounded_policy=None,
        time_span_bounded_policy=None,
        participant_entity_bounded_policy=None,
        event_time_bounded_policy=None,
        event_identity_bounded_policy=None,
    ) -> ArticleLocalKnowledgeGraphResult | CompactKnowledgeGraphResult:
        """요청 시작에 capture를 고정하고 v2.2는 compact state에서 직접 조립한다."""

        policy = ExecutionPolicy.from_request(
            output_profile, debug_trace=debug_trace, diagnostic_sink=diagnostic_sink
        )
        if isinstance(self.assembler, CompactArticleLocalKGAssembler):
            if (validation_capture is None and application_profiler is None
                and routing_observer is None
                and event_identity_audit_sink is None
                and entity_span_bounded_policy is None
                and time_span_bounded_policy is None
                and participant_entity_bounded_policy is None
                and event_time_bounded_policy is None
                and event_identity_bounded_policy is None):
                return self.runtime.run_compact(
                    article, assembler=self.assembler, policy=policy,
                )
            return self.runtime.run_compact(
                article, assembler=self.assembler, policy=policy,
                validation_capture=validation_capture,
                application_profiler=application_profiler,
                routing_observer=routing_observer,
                event_identity_audit_sink=event_identity_audit_sink,
                entity_span_bounded_policy=entity_span_bounded_policy,
                time_span_bounded_policy=time_span_bounded_policy,
                participant_entity_bounded_policy=participant_entity_bounded_policy,
                event_time_bounded_policy=event_time_bounded_policy,
                event_identity_bounded_policy=event_identity_bounded_policy,
            )
        if (entity_span_bounded_policy is not None
            or time_span_bounded_policy is not None
            or participant_entity_bounded_policy is not None
            or event_time_bounded_policy is not None
            or event_identity_bounded_policy is not None):
            raise RuntimeConfigurationError(
                "bounded Phase A routing requires the v2.2 compact path"
            )
        if application_profiler is not None:
            raise RuntimeConfigurationError(
                "application profiling requires the v2.2 compact PUBLIC path"
            )
        if policy.output_profile != "PUBLIC":
            raise RuntimeConfigurationError(
                "AUDIT/DEBUG graph projection is not connected to the legacy assembler"
            )
        runtime_result = self.runtime.run(article, policy=policy)
        return self.assembler.assemble(runtime_result)
