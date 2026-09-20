"""Public payload와 분리된 deterministic assembly audit 구조."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class StageCensus:
    """한 assembly stage의 공통 입출력 census."""

    stage: str
    input_count: int
    output_count: int
    preserved_count: int
    collapsed_count: int
    derived_count: int
    unresolved_count: int
    policy_id: str
    elapsed_seconds: float

    def __post_init__(self) -> None:
        if not self.stage or not self.policy_id:
            raise ValueError("stage census requires stage and policy_id")
        for name in (
            "input_count",
            "output_count",
            "preserved_count",
            "collapsed_count",
            "derived_count",
            "unresolved_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"stage census {name} must be non-negative")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("stage census elapsed_seconds must be finite and non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScopeStageCensus:
    """한 canonicalization scope의 identity 보존/감소 census."""

    scope: str
    input_count: int
    output_count: int
    preserved_count: int
    collapsed_count: int
    derived_count: int = 0
    unresolved_count: int = 0

    def __post_init__(self) -> None:
        if not self.scope:
            raise ValueError("scope census requires scope")
        for name in (
            "input_count",
            "output_count",
            "preserved_count",
            "collapsed_count",
            "derived_count",
            "unresolved_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"scope census {name} must be non-negative")
        if self.collapsed_count != self.input_count - self.output_count:
            raise ValueError("scope census collapsed count is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssemblyAuditTrail:
    """Optional audit carrier; never materialized as a public graph object."""

    canonicalization_ledger: tuple[Mapping[str, Any], ...]
    derivation_ledger: tuple[Mapping[str, Any], ...]
    stage_census: tuple[StageCensus, ...]
    output_profile: str
    canonical_identity_index: Mapping[str, Any]
    canonicalization_pair_diagnostics: tuple[Mapping[str, Any], ...]
    canonicalization_scope_census: tuple[ScopeStageCensus, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonicalization_ledger": [dict(row) for row in self.canonicalization_ledger],
            "derivation_ledger": [dict(row) for row in self.derivation_ledger],
            "stage_census": [row.to_dict() for row in self.stage_census],
            "output_profile": self.output_profile,
            "canonical_identity_index": dict(self.canonical_identity_index),
            "canonicalization_pair_diagnostics": [
                dict(row) for row in self.canonicalization_pair_diagnostics
            ],
            "canonicalization_scope_census": [
                row.to_dict() for row in self.canonicalization_scope_census
            ],
        }
