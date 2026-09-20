"""기사 호출의 capture 정책과 process/run/stage 참조 소유권을 구분한다.

기존 raw result의 의미 판단은 이 모듈이 바꾸지 않는다. 진단 기록은 값으로
분리하며, stage/run scope는 마지막 소비 뒤 자신이 소유한 참조를 해제한다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
import json
import math
from pathlib import Path
from typing import Any, Mapping


class CaptureLevel(str, Enum):
    SUMMARY = "SUMMARY"
    DECISIONS = "DECISIONS"
    FULL = "FULL"


def _independent(value: Any) -> Any:
    """원 객체를 잡아두지 않는 JSON 값만 복사한다. Tensor/임의 객체는 거부한다."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("diagnostic record must contain finite numbers")
        return value
    if isinstance(value, Mapping):
        return {str(key): _independent(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_independent(item) for item in value]
    raise TypeError(f"diagnostic record cannot retain {type(value).__name__}")


def _stage_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    warnings = row.get("warnings", ())
    return {
        "stage": str(row.get("stage", "UNKNOWN")),
        "component": str(row.get("component", "UNKNOWN")),
        "input_count": int(row.get("input_count", 0)),
        "candidate_count": _independent(row.get("candidate_count", 0)),
        "output_count": _independent(row.get("output_count", 0)),
        "drop_reason_counts": _independent(row.get("drop_reason_counts", {})),
        "warning_count": len(warnings) if isinstance(warnings, (list, tuple)) else int(bool(warnings)),
        "elapsed_seconds": float(row.get("elapsed_seconds", 0.0)),
    }


class DiagnosticSink:
    """Bounded 독립 record sink; full capture는 JSONL 순차 기록을 권장한다."""

    def __init__(self, level: CaptureLevel, *, path: Path | None = None,
                 max_records: int = 512, max_record_bytes: int = 262144) -> None:
        if max_records <= 0 or max_record_bytes <= 0:
            raise ValueError("diagnostic limits must be positive")
        self.level = level
        self.path = path
        self.max_records = max_records
        self.max_record_bytes = max_record_bytes
        self.records: list[dict[str, Any]] = []
        self.stage_summaries: list[dict[str, Any]] = []
        self.counts: Counter[str] = Counter()
        self.truncated_count = 0
        self.failed_reason: str | None = None
        self._stream = None
        self._opened = False

    def record(self, kind: str, value: Mapping[str, Any]) -> None:
        self.counts[kind] += 1
        if kind == "stage":
            try:
                self.stage_summaries.append(_stage_summary(value))
            except (TypeError, ValueError) as error:
                self.failed_reason = f"{type(error).__name__}: {error}"
                self.truncated_count += 1
                return
        if self.level is CaptureLevel.SUMMARY:
            return
        if self.level is CaptureLevel.DECISIONS and kind == "candidate":
            return
        if len(self.records) + self.counts.get("written_to_file", 0) >= self.max_records:
            self.truncated_count += 1
            return
        try:
            detached = {"kind": kind, "record": _independent(value)}
            encoded = json.dumps(detached, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > self.max_record_bytes:
                self.truncated_count += 1
                return
            if self.path is None:
                self.records.append(detached)
            else:
                if self._stream is None:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self._stream = self.path.open("x", encoding="utf-8")
                    self._opened = True
                self._stream.write(encoded + "\n")
                self.counts["written_to_file"] += 1
        except (OSError, TypeError, ValueError) as error:
            self.failed_reason = f"{type(error).__name__}: {error}"
            self.truncated_count += 1

    def summary(self) -> dict[str, Any]:
        if self._stream is not None:
            try:
                self._stream.flush()
            except OSError as error:
                self.failed_reason = f"{type(error).__name__}: {error}"
        return {
            "capture_level": self.level.value,
            "observed_counts": dict(self.counts),
            "stored_in_memory": len(self.records),
            "written_to_file": self.counts.get("written_to_file", 0),
            "truncated_count": self.truncated_count,
            "failed_reason": self.failed_reason,
            "artifact_path": str(self.path) if self.path and self._opened else None,
            "max_records": self.max_records,
            "max_record_bytes": self.max_record_bytes,
        }

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.close()
            except OSError as error:
                self.failed_reason = f"{type(error).__name__}: {error}"
            finally:
                self._stream = None


class NoOpDiagnosticSink(DiagnosticSink):
    def __init__(self) -> None:
        super().__init__(CaptureLevel.SUMMARY)


class DecisionDiagnosticSink(DiagnosticSink):
    def __init__(self, *, path: Path | None = None, max_records: int = 512) -> None:
        super().__init__(CaptureLevel.DECISIONS, path=path, max_records=max_records)


class FullDiagnosticSink(DiagnosticSink):
    def __init__(self, *, path: Path | None = None, max_records: int | None = None) -> None:
        if max_records is None:
            max_records = 512 if path is None else 100000
        super().__init__(CaptureLevel.FULL, path=path, max_records=max_records)


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    output_profile: str
    capture_level: CaptureLevel
    diagnostic_sink: DiagnosticSink

    @classmethod
    def from_request(cls, output_profile: str = "PUBLIC", *, debug_trace: bool = False,
                     diagnostic_sink: DiagnosticSink | None = None,
                     diagnostic_path: Path | None = None) -> "ExecutionPolicy":
        profile = str(getattr(output_profile, "value", output_profile))
        if profile not in ("PUBLIC", "AUDIT", "DEBUG"):
            raise ValueError(f"unsupported output profile: {profile}")
        level = (CaptureLevel.FULL if debug_trace or profile == "DEBUG" else
                 CaptureLevel.DECISIONS if profile == "AUDIT" else CaptureLevel.SUMMARY)
        sink = diagnostic_sink or (
            NoOpDiagnosticSink() if level is CaptureLevel.SUMMARY else
            DecisionDiagnosticSink(path=diagnostic_path) if level is CaptureLevel.DECISIONS else
            FullDiagnosticSink(path=diagnostic_path)
        )
        if sink.level is not level:
            raise ValueError("diagnostic sink capture level differs from execution policy")
        return cls(profile, level, sink)


class StageScope:
    """한 scorer batch의 임시 tensor/map 참조를 해당 stage 끝에 닫는다."""

    def __init__(self) -> None:
        self._owned: list[object] = []

    def own(self, value: Any) -> Any:
        self._owned.append(value)
        return value

    def close(self) -> None:
        self._owned.clear()

    def __enter__(self) -> "StageScope":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class ArticleRunScope:
    """한 article의 원문 view와 request-local 표현만 소유한다."""

    def __init__(self, article: Any, policy: ExecutionPolicy) -> None:
        self.article_version_id = str(article.article_version_id)
        self.source_text: str | None = article.content
        self.policy = policy
        self.representations: dict[object, object] = {}
        self.compact_event_closure: object | None = None
        self._owned: list[object] = []

    def own(self, value: Any) -> Any:
        self._owned.append(value)
        return value

    def close(self) -> None:
        self.representations.clear()
        self.compact_event_closure = None
        self._owned.clear()
        self.source_text = None
        self.policy.diagnostic_sink.close()

    def owner_census(self) -> dict[str, int | bool]:
        """요청 반환 후 scope가 직접 소유한 source/feature 참조 수만 보고한다."""
        return {
            "source_text_retained": self.source_text is not None,
            "request_representation_count": len(self.representations),
            "compact_event_closure_retained": self.compact_event_closure is not None,
            "owned_object_count": len(self._owned),
        }

    def __enter__(self) -> "ArticleRunScope":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
