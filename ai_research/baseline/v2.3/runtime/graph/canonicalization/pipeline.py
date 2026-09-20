"""Small explicit registry and canonicalization stage executor."""

from __future__ import annotations

import time

from .contracts import (
    CanonicalAssemblyState,
    CanonicalIdentityIndex,
    CanonicalizationContext,
    CanonicalizationPolicy,
)
from ..assembly_input import ResolvedAssemblyState
from ..observability import ScopeStageCensus, StageCensus


CANONICALIZATION_SCOPES = ("EVENT", "ENTITY", "STATEMENT", "TIME")


class CanonicalizationPolicyRegistry:
    """Explicit in-process registry; no reflection or dynamic plugin discovery."""

    def __init__(self) -> None:
        self._policies: dict[str, CanonicalizationPolicy] = {}

    def register(self, policy: CanonicalizationPolicy) -> None:
        if not policy.policy_id:
            raise ValueError("canonicalization policy requires policy_id")
        if policy.policy_id in self._policies:
            raise ValueError(f"duplicate canonicalization policy: {policy.policy_id}")
        self._policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> CanonicalizationPolicy:
        try:
            return self._policies[policy_id]
        except KeyError as error:
            raise ValueError(f"unknown canonicalization policy: {policy_id}") from error


class CanonicalizationPipeline:
    def __init__(
        self,
        registry: CanonicalizationPolicyRegistry,
        *,
        active_policy_id: str = "NO_OP_CANONICALIZATION",
    ) -> None:
        self.registry = registry
        self.active_policy_id = active_policy_id

    def run(self, state: ResolvedAssemblyState) -> CanonicalAssemblyState:
        started = time.perf_counter()
        policy = self.registry.get(self.active_policy_id)
        result = policy.apply(CanonicalizationContext(state))
        if result.resolved_state is not state:
            raise ValueError("canonicalization must retain the original resolved state object")
        source_by_scope = state.identity_ids_by_scope()
        seen_by_scope = {scope: set() for scope in CANONICALIZATION_SCOPES}
        output_by_scope = {scope: 0 for scope in CANONICALIZATION_SCOPES}
        for decision in result.decisions:
            if decision.scope not in CANONICALIZATION_SCOPES:
                raise ValueError(f"unsupported canonicalization scope: {decision.scope}")
            if decision.input_ids != decision.member_ids:
                raise ValueError("canonical family input_ids and member_ids must be identical")
            if len(set(decision.member_ids)) != len(decision.member_ids):
                raise ValueError("canonical family contains duplicate source identities")
            if decision.decision == "COLLAPSE" and len(decision.member_ids) < 2:
                raise ValueError("COLLAPSE requires at least two source identities")
            if decision.decision in {"PASS_THROUGH", "KEEP_SEPARATE"} and len(
                decision.member_ids
            ) != 1:
                raise ValueError(f"{decision.decision} must preserve one source identity")
            if decision.output_representative_id not in decision.member_ids:
                raise ValueError("canonical representative is not a source family member")
            if decision.scope not in policy.target_scopes and decision.decision != "PASS_THROUGH":
                raise ValueError("non-target canonicalization scope must pass through")
            source_scope = set(source_by_scope[decision.scope])
            for member in decision.member_ids:
                if member not in source_scope:
                    raise ValueError("canonical family invented an unknown source identity")
                if member in seen_by_scope[decision.scope]:
                    raise ValueError("source identity belongs to multiple canonical families")
                seen_by_scope[decision.scope].add(member)
            output_by_scope[decision.scope] += 1
        for scope in CANONICALIZATION_SCOPES:
            if seen_by_scope[scope] != set(source_by_scope[scope]):
                raise ValueError(f"canonical identity coverage is incomplete for {scope}")
            if scope not in policy.target_scopes:
                mappings = [
                    row
                    for row in result.decisions
                    if row.scope == scope
                ]
                if any(
                    row.member_ids != (row.output_representative_id,)
                    for row in mappings
                ):
                    raise ValueError("non-target scope identity mapping changed")

        identity_index = CanonicalIdentityIndex.from_decisions(result.decisions)
        input_ids = state.identity_ids()
        output_count = sum(output_by_scope.values())
        scope_census = tuple(
            ScopeStageCensus(
                scope=scope,
                input_count=len(source_by_scope[scope]),
                output_count=output_by_scope[scope],
                preserved_count=output_by_scope[scope],
                collapsed_count=len(source_by_scope[scope]) - output_by_scope[scope],
            )
            for scope in CANONICALIZATION_SCOPES
        )
        census = StageCensus(
            stage="CANONICALIZATION",
            input_count=len(input_ids),
            output_count=output_count,
            preserved_count=output_count,
            collapsed_count=len(input_ids) - output_count,
            derived_count=0,
            unresolved_count=0,
            policy_id=policy.policy_id,
            elapsed_seconds=time.perf_counter() - started,
        )
        return CanonicalAssemblyState(
            result.resolved_state,
            result.decisions,
            identity_index,
            result.pair_diagnostics,
            census,
            scope_census,
        )
