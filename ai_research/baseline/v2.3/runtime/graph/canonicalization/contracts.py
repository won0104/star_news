"""Typed carriers for deterministic public-representation canonicalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from ..assembly_input import ResolvedAssemblyState
from ..observability import ScopeStageCensus, StageCensus
from ..provenance import PolicyProvenance


CANONICALIZATION_DECISIONS = ("PASS_THROUGH", "COLLAPSE", "KEEP_SEPARATE")


@dataclass(frozen=True, slots=True)
class CanonicalizationDecision:
    policy_id: str
    policy_version: str
    scope: str
    input_ids: tuple[str, ...]
    output_representative_id: str
    member_ids: tuple[str, ...]
    decision: str
    reason: str
    preserved_evidence_references: tuple[str, ...]
    provenance: PolicyProvenance
    diagnostics: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.decision not in CANONICALIZATION_DECISIONS:
            raise ValueError("invalid canonicalization decision")
        if not self.scope or not self.input_ids or not self.member_ids:
            raise ValueError("canonicalization decision requires scoped identities")
        if self.output_representative_id not in self.member_ids:
            raise ValueError("canonicalization representative must be a member")
        if self.decision == "PASS_THROUGH":
            if self.input_ids != self.member_ids or len(self.input_ids) != 1:
                raise ValueError("PASS_THROUGH must preserve exactly one input identity")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.to_dict()
        payload["diagnostics"] = dict(self.diagnostics)
        return payload


@dataclass(frozen=True, slots=True)
class CanonicalizationContext:
    resolved_state: ResolvedAssemblyState


@dataclass(frozen=True, slots=True)
class CanonicalizationResult:
    resolved_state: ResolvedAssemblyState
    decisions: tuple[CanonicalizationDecision, ...]
    pair_diagnostics: tuple[Mapping[str, Any], ...] = ()


class CanonicalizationPolicy(Protocol):
    policy_id: str
    policy_version: str
    target_scopes: tuple[str, ...]

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        ...


@dataclass(frozen=True, slots=True)
class CanonicalIdentityIndex:
    """Immutable source-to-representative and representative-to-members mapping."""

    source_to_representative: Mapping[str, Mapping[str, str]]
    representative_to_members: Mapping[str, Mapping[str, tuple[str, ...]]]

    @classmethod
    def from_decisions(
        cls, decisions: tuple[CanonicalizationDecision, ...]
    ) -> "CanonicalIdentityIndex":
        source: dict[str, dict[str, str]] = {}
        groups: dict[str, dict[str, tuple[str, ...]]] = {}
        for row in decisions:
            source_scope = source.setdefault(row.scope, {})
            group_scope = groups.setdefault(row.scope, {})
            if row.output_representative_id in group_scope:
                raise ValueError("duplicate canonical representative identity")
            group_scope[row.output_representative_id] = row.member_ids
            for member in row.member_ids:
                if member in source_scope:
                    raise ValueError("source identity belongs to multiple canonical families")
                source_scope[member] = row.output_representative_id
        return cls(
            source_to_representative=MappingProxyType(
                {
                    scope: MappingProxyType(dict(values))
                    for scope, values in source.items()
                }
            ),
            representative_to_members=MappingProxyType(
                {
                    scope: MappingProxyType(dict(values))
                    for scope, values in groups.items()
                }
            ),
        )

    def representative_for(self, scope: str, source_id: str) -> str:
        try:
            return self.source_to_representative[scope][source_id]
        except KeyError as error:
            raise ValueError(f"identity is absent from canonical index: {scope}/{source_id}") from error

    def members_for(self, scope: str, representative_id: str) -> tuple[str, ...]:
        try:
            return self.representative_to_members[scope][representative_id]
        except KeyError as error:
            raise ValueError(
                f"representative is absent from canonical index: {scope}/{representative_id}"
            ) from error

    def groups(self, scope: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
        values = self.representative_to_members.get(scope, {})
        return tuple((representative, values[representative]) for representative in sorted(values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_to_representative": {
                scope: dict(values)
                for scope, values in self.source_to_representative.items()
            },
            "representative_to_members": {
                scope: {representative: list(members) for representative, members in values.items()}
                for scope, values in self.representative_to_members.items()
            },
        }


@dataclass(frozen=True, slots=True)
class CanonicalAssemblyState:
    resolved_state: ResolvedAssemblyState
    decisions: tuple[CanonicalizationDecision, ...]
    identity_index: CanonicalIdentityIndex
    pair_diagnostics: tuple[Mapping[str, Any], ...]
    census: StageCensus
    scope_census: tuple[ScopeStageCensus, ...]
