"""Typed carriers for facts derived after canonicalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol

from ..canonicalization.contracts import CanonicalAssemblyState
from ..observability import StageCensus
from ..provenance import PolicyProvenance


DERIVATION_DECISIONS = ("DERIVED", "NOT_DERIVED")


@dataclass(frozen=True, slots=True)
class DerivedFact:
    """One versioned deterministic fact decided before public materialization."""

    derived_kind: str
    source_ids: tuple[str, ...]
    value: Mapping[str, Any]
    provenance: PolicyProvenance


@dataclass(frozen=True, slots=True)
class DerivationDecision:
    policy_id: str
    policy_version: str
    source_ids: tuple[str, ...]
    derived_kind: str
    decision: str
    reason: str
    provenance: PolicyProvenance
    diagnostics: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.decision not in DERIVATION_DECISIONS:
            raise ValueError("invalid derivation decision")
        if not self.policy_id or not self.policy_version or not self.reason:
            raise ValueError("derivation decision requires policy identity and reason")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.to_dict()
        payload["diagnostics"] = dict(self.diagnostics)
        return payload


@dataclass(frozen=True, slots=True)
class DerivationContext:
    canonical_state: CanonicalAssemblyState
    prior_facts: tuple[DerivedFact, ...] = ()


@dataclass(frozen=True, slots=True)
class DerivationResult:
    canonical_state: CanonicalAssemblyState
    facts: tuple[DerivedFact, ...]
    decisions: tuple[DerivationDecision, ...]


class DeterministicDerivationPolicy(Protocol):
    policy_id: str
    policy_version: str

    def apply(self, context: DerivationContext) -> DerivationResult:
        ...


@dataclass(frozen=True, slots=True)
class DerivedAssemblyState:
    canonical_state: CanonicalAssemblyState
    facts: tuple[DerivedFact, ...]
    decisions: tuple[DerivationDecision, ...]
    census: StageCensus
