"""Representation-only PUBLIC/AUDIT/DEBUG projection for Release V2.1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any, Generic, Mapping, TypeVar


OutputT = TypeVar("OutputT")
ASSEMBLY_OUTPUT_PROFILE_CONTRACT_ID = "ASSEMBLY_OUTPUT_PROFILE_V2"
V22_OUTPUT_PROFILE_CONTRACT_ID = "ASSEMBLY_OUTPUT_PROFILE_V3"


class OutputProfile(str, Enum):
    PUBLIC = "PUBLIC"
    AUDIT = "AUDIT"
    DEBUG = "DEBUG"


@dataclass(frozen=True, slots=True)
class OutputProfileContract:
    """Stable PUBLIC response plus non-stable developer diagnostics."""

    contract_id: str = ASSEMBLY_OUTPUT_PROFILE_CONTRACT_ID
    default_profile: OutputProfile = OutputProfile.PUBLIC
    supported_profiles: tuple[OutputProfile, ...] = (
        OutputProfile.PUBLIC,
        OutputProfile.AUDIT,
        OutputProfile.DEBUG,
    )
    compact_public_enabled: bool = True
    graph_identity_profile_invariant: bool = True
    stable_public_profile: OutputProfile = OutputProfile.PUBLIC
    diagnostic_profiles: tuple[OutputProfile, ...] = (
        OutputProfile.AUDIT,
        OutputProfile.DEBUG,
    )
    diagnostic_profiles_are_stable_public_contract: bool = False
    public_excludes: tuple[str, ...] = (
        "source_lanes bodies",
        "full unmaterialized evidence body",
        "full trace body",
    )
    audit_excludes: tuple[str, ...] = ("source_lanes bodies",)
    debug_preserves_full_carrier: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["default_profile"] = self.default_profile.value
        payload["supported_profiles"] = [value.value for value in self.supported_profiles]
        payload["stable_public_profile"] = self.stable_public_profile.value
        payload["diagnostic_profiles"] = [value.value for value in self.diagnostic_profiles]
        return payload


def _item_count(value: Any) -> int:
    """Count one evidence category without retaining its internal identifiers."""

    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return int(value is not None)


def _compact_coverage(value: Mapping[str, Any]) -> dict[str, Any]:
    runtime = value.get("runtime", {})
    lanes = runtime.get("lanes", {}) if isinstance(runtime, Mapping) else {}
    lane_statuses = value.get("lane_statuses", {})
    assembly = lane_statuses.get("graph_assembly", {}) if isinstance(lane_statuses, Mapping) else {}
    return {
        "runtime_status": runtime.get("status") if isinstance(runtime, Mapping) else None,
        "runtime_lanes": deepcopy(lanes) if isinstance(lanes, Mapping) else {},
        "graph_assembly_status": assembly.get("status") if isinstance(assembly, Mapping) else None,
        "details_profile": "AUDIT_OR_DEBUG",
    }


class OutputProfileProjector(Generic[OutputT]):
    """Project auxiliary fields while preserving the public graph byte-for-byte."""

    def __init__(self, contract: OutputProfileContract | None = None) -> None:
        self.contract = contract or OutputProfileContract()

    def project(
        self,
        value: OutputT,
        profile: OutputProfile | str | None = None,
    ) -> OutputT:
        selected = OutputProfile(profile or self.contract.default_profile)
        if selected not in self.contract.supported_profiles:
            raise ValueError(f"unsupported assembly output profile: {selected.value}")
        provenance = {
            **deepcopy(getattr(value, "provenance")),
            "release_version": "2.1",
            "output_profile_contract": self.contract.contract_id,
            "output_profile": selected.value,
        }
        if selected is OutputProfile.DEBUG:
            return replace(value, output_profile=selected.value, provenance=provenance)
        if selected is OutputProfile.AUDIT:
            return replace(
                value,
                output_profile=selected.value,
                source_lanes={},
                provenance=provenance,
            )

        evidence = getattr(value, "evidence")
        unmaterialized = evidence.get("unmaterialized", {}) if isinstance(evidence, Mapping) else {}
        compact_evidence = {
            "policy": evidence.get("policy") if isinstance(evidence, Mapping) else None,
            "unmaterialized_included": False,
            "unmaterialized_category_counts": {
                str(key): _item_count(item)
                for key, item in sorted(unmaterialized.items())
            } if isinstance(unmaterialized, Mapping) else {},
            "details_profile": "AUDIT_OR_DEBUG",
        }
        return replace(
            value,
            output_profile=selected.value,
            evidence=compact_evidence,
            source_lanes={},
            coverage=_compact_coverage(getattr(value, "coverage")),
            provenance=provenance,
            trace=(),
        )


# Historical import compatibility. The behavior is intentionally no longer pass-through.
PassThroughOutputProjector = OutputProfileProjector


class CompactOutputProfileProjector(Generic[OutputT]):
    """v2.2 semantic graph를 그대로 두고 시작 시 capture한 진단만 결합한다."""

    contract_id = V22_OUTPUT_PROFILE_CONTRACT_ID

    def project(self, value: OutputT, *, policy) -> OutputT:
        selected = OutputProfile(policy.output_profile)
        summary = policy.diagnostic_sink.summary()
        if selected is OutputProfile.PUBLIC:
            diagnostics = {
                "capture_level": policy.capture_level.value, "summary": summary,
                "records": (), "artifact_reference": summary["artifact_path"],
            }
        else:
            diagnostics = {
                "capture_level": policy.capture_level.value,
                "summary": summary,
                "records": tuple(deepcopy(policy.diagnostic_sink.records)),
                "artifact_reference": summary["artifact_path"],
            }
        return replace(
            value, output_profile=selected.value, diagnostics=diagnostics,
        )

    @staticmethod
    def request_diagnostics(value: OutputT, profile: OutputProfile | str) -> Mapping[str, Any]:
        """이미 종료한 raw owner를 다시 요구하지 않고 capture 부족을 명시한다."""
        requested = OutputProfile(profile)
        captured = OutputProfile(getattr(value, "output_profile"))
        order = {OutputProfile.PUBLIC: 0, OutputProfile.AUDIT: 1,
                 OutputProfile.DEBUG: 2}
        diagnostics = getattr(value, "diagnostics")
        captured_level = diagnostics.get("capture_level", "SUMMARY")
        level_order = {"SUMMARY": 0, "DECISIONS": 1, "FULL": 2}
        if (level_order.get(captured_level, 0) < order[requested]
            or (order[requested] > order[captured]
                and not diagnostics.get("records")
                and not diagnostics.get("artifact_reference"))):
            return {
                "status": "diagnostics_not_captured",
                "requested_profile": requested.value,
                "captured_profile": captured.value,
            }
        records = diagnostics.get("records", ())
        if requested is OutputProfile.AUDIT and captured is OutputProfile.DEBUG:
            records = tuple(row for row in records if row.get("kind") != "candidate")
        return {
            "status": "CAPTURED", "requested_profile": requested.value,
            "summary": diagnostics.get("summary", {}),
            "records": records if requested is not OutputProfile.PUBLIC else (),
            "artifact_reference": diagnostics.get("artifact_reference"),
        }
