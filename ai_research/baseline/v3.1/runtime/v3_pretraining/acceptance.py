"""Checkpoint-bound runtime acceptance policy and score-gate helpers.

This module owns decision thresholds and their provenance.  Retrieval budgets stay
in :mod:`serving`; a rejected candidate is never reintroduced to fill a budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping, TypeVar


SCORE_CONTRACT_VERSION = "v3-unified-entity-identity-r4"
V23_TRIGGER_FINE_PRODUCER = "trigger.span_score"
V23_TRIGGER_FINE_RAW_SCORE_VERSION = "TRIGGER_EXACT_SPAN_RAW_LOGIT"
V23_TRIGGER_ENDPOINT_PRODUCER = "trigger.boundary.start_logits/end_logits:sigmoid_min"
RUNTIME_MODES = frozenset({
    "LEGACY_DIAGNOSTIC", "CALIBRATION_CANDIDATE", "SERVICE_CALIBRATED",
    "PROJECT_FINAL_USER_SELECTED",
})
ACCEPTANCE_LANES = (
    "EVENT", "STATEMENT", "TRIGGER", "ENTITY", "TIME", "PARTICIPANT",
    "ASSERTOR_SOURCE", "ASSERTOR_ENTITY", "EVENT_TIME",
    "ENTITY_COREFERENCE", "EVENT_COREFERENCE", "ABOUT", "CAUSES", "PRIMARY",
)
BOUNDARY_KINDS = ("EVENT", "STATEMENT")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class AcceptanceContractError(ValueError):
    """The runtime is not allowed to execute under this acceptance binding."""


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def _threshold_map(value: Mapping[str, Any]) -> dict[str, float]:
    if set(value) != set(ACCEPTANCE_LANES):
        missing = sorted(set(ACCEPTANCE_LANES) - set(value))
        extra = sorted(set(value) - set(ACCEPTANCE_LANES))
        raise AcceptanceContractError(
            f"acceptance thresholds differ; missing={missing}, extra={extra}")
    if any(isinstance(value[lane], bool) or not isinstance(value[lane], (int, float))
           for lane in ACCEPTANCE_LANES):
        raise AcceptanceContractError("acceptance thresholds/margins must be numeric")
    output = {lane: float(value[lane]) for lane in ACCEPTANCE_LANES}
    if not all(math.isfinite(score) for score in output.values()):
        raise AcceptanceContractError("acceptance thresholds/margins must be finite")
    return output


def _boundary_threshold_map(value: Mapping[str, Any]) -> dict[str, float]:
    if set(value) != set(BOUNDARY_KINDS):
        missing = sorted(set(BOUNDARY_KINDS) - set(value))
        extra = sorted(set(value) - set(BOUNDARY_KINDS))
        raise AcceptanceContractError(
            f"boundary thresholds differ; missing={missing}, extra={extra}")
    if any(isinstance(value[kind], bool) or not isinstance(value[kind], (int, float))
           for kind in BOUNDARY_KINDS):
        raise AcceptanceContractError("boundary thresholds must be numeric")
    output = {kind: float(value[kind]) for kind in BOUNDARY_KINDS}
    if not all(math.isfinite(score) for score in output.values()):
        raise AcceptanceContractError("boundary thresholds must be finite")
    return output


@dataclass(frozen=True, slots=True)
class AcceptanceConfig:
    """One immutable score policy bound to a checkpoint and score contract.

    ``calibration_artifact_sha256`` is required only for ``SERVICE_CALIBRATED``.
    The referenced artifact contains the four provenance fields and the exact
    threshold map; the loader compares both its digest and contents.
    """

    mode: str
    score_contract_version: str
    checkpoint_sha256: str
    calibration_split: str
    calibration_version: str
    thresholds: tuple[tuple[str, float], ...]
    boundary_thresholds: tuple[tuple[str, float], ...]
    calibration_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in RUNTIME_MODES:
            raise AcceptanceContractError("unknown acceptance runtime mode")
        if self.score_contract_version != SCORE_CONTRACT_VERSION:
            raise AcceptanceContractError("unknown score-contract version")
        if _SHA256.fullmatch(self.checkpoint_sha256) is None:
            raise AcceptanceContractError("checkpoint_sha256 must be lowercase SHA-256")
        if not self.calibration_split or not self.calibration_version:
            raise AcceptanceContractError("calibration split/version provenance is required")
        _threshold_map(dict(self.thresholds))
        _boundary_threshold_map(dict(self.boundary_thresholds))
        if self.mode == "LEGACY_DIAGNOSTIC" and (
                any(value != 0.0 for _, value in self.thresholds) or
                any(value != 0.0 for _, value in self.boundary_thresholds)):
            raise AcceptanceContractError(
                "LEGACY_DIAGNOSTIC uses the immutable pre-D4 mixed policy")
        if self.calibration_artifact_sha256 is not None and _SHA256.fullmatch(
                self.calibration_artifact_sha256) is None:
            raise AcceptanceContractError("calibration artifact digest must be lowercase SHA-256")
        if self.mode == "SERVICE_CALIBRATED" and self.calibration_artifact_sha256 is None:
            raise AcceptanceContractError("SERVICE_CALIBRATED requires a calibration artifact digest")

    @classmethod
    def legacy_diagnostic(cls, checkpoint_sha256: str) -> "AcceptanceConfig":
        return cls("LEGACY_DIAGNOSTIC", SCORE_CONTRACT_VERSION, checkpoint_sha256,
                   "LEGACY_RAW_ZERO", "legacy-diagnostic-v1",
                   tuple((lane, 0.0) for lane in ACCEPTANCE_LANES),
                   tuple((kind, 0.0) for kind in BOUNDARY_KINDS))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AcceptanceConfig":
        expected = {"mode", "score_contract_version", "checkpoint_sha256",
                    "calibration_split", "calibration_version", "thresholds",
                    "boundary_thresholds",
                    "calibration_artifact_sha256"}
        if (set(value) != expected or not isinstance(value.get("thresholds"), Mapping)
                or not isinstance(value.get("boundary_thresholds"), Mapping)):
            raise AcceptanceContractError("acceptance config schema differs")
        string_fields = ("mode", "score_contract_version", "checkpoint_sha256",
                         "calibration_split", "calibration_version")
        if any(not isinstance(value.get(name), str) for name in string_fields):
            raise AcceptanceContractError("acceptance provenance fields must be strings")
        thresholds = _threshold_map(value["thresholds"])
        boundary_thresholds = _boundary_threshold_map(value["boundary_thresholds"])
        artifact_sha = value["calibration_artifact_sha256"]
        if artifact_sha is not None and not isinstance(artifact_sha, str):
            raise AcceptanceContractError("calibration artifact digest must be string or null")
        return cls(value["mode"], value["score_contract_version"],
                   value["checkpoint_sha256"], value["calibration_split"],
                   value["calibration_version"], tuple(thresholds.items()),
                   tuple(boundary_thresholds.items()), artifact_sha)

    @classmethod
    def load(cls, path: str | Path) -> "AcceptanceConfig":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise AcceptanceContractError("acceptance config root must be an object")
        return cls.from_mapping(value)

    def threshold(self, lane: str) -> float:
        try:
            return dict(self.thresholds)[lane]
        except KeyError as error:
            raise AcceptanceContractError(f"unknown acceptance lane: {lane}") from error

    def boundary_threshold(self, kind: str) -> float:
        try:
            return dict(self.boundary_thresholds)[kind]
        except KeyError as error:
            raise AcceptanceContractError(f"unknown boundary kind: {kind}") from error

    @property
    def service_ready(self) -> bool:
        # Project-final inference policy is frozen by the release loader's
        # checkpoint/config SHA checks; validation lineage remains separate.
        return self.mode in ("SERVICE_CALIBRATED", "PROJECT_FINAL_USER_SELECTED")

    def calibration_payload(self) -> dict[str, Any]:
        return {
            "score_contract_version": self.score_contract_version,
            "checkpoint_sha256": self.checkpoint_sha256,
            "calibration_split": self.calibration_split,
            "calibration_version": self.calibration_version,
            "thresholds": dict(self.thresholds),
            "boundary_thresholds": dict(self.boundary_thresholds),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, **self.calibration_payload(),
                "calibration_artifact_sha256": self.calibration_artifact_sha256,
                "service_ready": self.service_ready}

    def validate_runtime(self, *, checkpoint_sha256: str,
                         score_contract_version: str = SCORE_CONTRACT_VERSION,
                         calibration_artifact: Mapping[str, Any] | None = None) -> None:
        """Fail closed before inference when any binding differs."""
        if checkpoint_sha256 != self.checkpoint_sha256:
            raise AcceptanceContractError("acceptance checkpoint SHA mismatch")
        if score_contract_version != self.score_contract_version:
            raise AcceptanceContractError("acceptance score-contract mismatch")
        if self.mode != "SERVICE_CALIBRATED":
            return
        if calibration_artifact is None:
            raise AcceptanceContractError("SERVICE_CALIBRATED calibration artifact is missing")
        artifact = dict(calibration_artifact)
        if artifact != self.calibration_payload():
            raise AcceptanceContractError("calibration artifact provenance/threshold mismatch")
        if _canonical_digest(artifact) != self.calibration_artifact_sha256:
            raise AcceptanceContractError("calibration artifact SHA mismatch")


@dataclass(frozen=True, slots=True)
class AcceptanceTrace:
    lane: str
    candidate_count: int
    accepted_before_budget: int
    accepted_count: int
    rejected_count: int
    budget_truncated_count: int
    unresolved_count: int = 0
    rejection_reason: str = "BELOW_THRESHOLD"
    budget_reason: str = "BUDGET_TRUNCATION"
    rejection_reason_counts: tuple[tuple[str, int], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "candidate_count": self.candidate_count,
            "accepted_before_budget": self.accepted_before_budget,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "rejection_reasons": (dict(self.rejection_reason_counts)
                                  if self.rejection_reason_counts else
                                  {self.rejection_reason: self.rejected_count}
                                  if self.rejected_count else {}),
            "budget_truncated_count": self.budget_truncated_count,
            "budget_reasons": ({self.budget_reason: self.budget_truncated_count}
                               if self.budget_truncated_count else {}),
            "unresolved_semantic_count": self.unresolved_count,
        }


T = TypeVar("T")


def cap_only(rows: Iterable[T], *, limit: int, rank_key: Callable[[T], Any],
             output_key: Callable[[T], Any]) -> tuple[T, ...]:
    """Pre-D4 compatibility selection: deterministic rank/cap with no score gate."""
    if limit <= 0:
        raise ValueError("positive cap is required")
    return tuple(sorted(sorted(tuple(rows), key=rank_key)[:limit], key=output_key))


def accept_then_cap(rows: Iterable[T], *, lane: str, threshold: float, limit: int,
                    score: Callable[[T], float], rank_key: Callable[[T], Any],
                    output_key: Callable[[T], Any]) -> tuple[tuple[T, ...], AcceptanceTrace]:
    """Apply ``score >= threshold`` before rank/cap; never backfill rejects."""
    if lane not in ACCEPTANCE_LANES or not math.isfinite(threshold) or limit <= 0:
        raise ValueError("known lane, finite threshold and positive cap are required")
    candidates = tuple(rows)
    if any(not math.isfinite(score(row)) for row in candidates):
        raise ValueError("acceptance candidate score must be finite")
    accepted = tuple(row for row in candidates if score(row) >= threshold)
    selected = tuple(sorted(accepted, key=rank_key)[:limit])
    selected = tuple(sorted(selected, key=output_key))
    trace = AcceptanceTrace(lane, len(candidates), len(accepted), len(selected),
                            len(candidates) - len(accepted), len(accepted) - len(selected))
    return selected, trace


def accept_decision_boundary_then_cap(
        rows: Iterable[T], *, kind: str, decision_threshold: float,
        boundary_threshold: float, limit: int,
        decision_score: Callable[[T], float], boundary_score: Callable[[T], float | None],
        rank_key: Callable[[T], Any], output_key: Callable[[T], Any],
) -> tuple[tuple[T, ...], AcceptanceTrace]:
    """AND exact kind decision and N1 boundary fitness before deterministic cap.

    A missing boundary score is a fail-closed rejection.  Boundary residuals,
    proposal scores and semantic validity are deliberately not accepted as a
    substitute for the dedicated boundary-fitness producer.
    """
    if (kind not in BOUNDARY_KINDS or not math.isfinite(decision_threshold)
            or not math.isfinite(boundary_threshold) or limit <= 0):
        raise ValueError("known kind, finite thresholds and positive cap are required")
    candidates = tuple(rows)
    accepted: list[T] = []
    reasons: dict[str, int] = {}
    for row in candidates:
        decision = decision_score(row)
        boundary = boundary_score(row)
        if not math.isfinite(decision):
            raise ValueError("decision score must be finite")
        decision_ok = decision >= decision_threshold
        boundary_ok = boundary is not None and math.isfinite(boundary) and (
            boundary >= boundary_threshold)
        if boundary is not None and not math.isfinite(boundary):
            raise ValueError("boundary-fitness score must be finite when present")
        if decision_ok and boundary_ok:
            accepted.append(row)
            continue
        reason = ("BOUNDARY_SCORE_MISSING" if boundary is None else
                  "DECISION_AND_BOUNDARY_BELOW_THRESHOLD"
                  if not decision_ok and not boundary_ok else
                  "DECISION_BELOW_THRESHOLD" if not decision_ok else
                  "BOUNDARY_BELOW_THRESHOLD")
        reasons[reason] = reasons.get(reason, 0) + 1
    selected = cap_only(accepted, limit=limit, rank_key=rank_key, output_key=output_key)
    trace = AcceptanceTrace(
        kind, len(candidates), len(accepted), len(selected),
        len(candidates) - len(accepted), len(accepted) - len(selected),
        rejection_reason_counts=tuple(sorted(reasons.items())))
    return selected, trace
