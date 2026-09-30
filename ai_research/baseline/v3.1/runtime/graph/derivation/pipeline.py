"""Small explicit deterministic-derivation registry and executor."""

from __future__ import annotations

import time

from .contracts import (
    DerivationContext,
    DerivedAssemblyState,
    DeterministicDerivationPolicy,
)
from ..canonicalization.contracts import CanonicalAssemblyState
from ..observability import StageCensus


class DerivationPolicyRegistry:
    def __init__(self) -> None:
        self._policies: dict[str, DeterministicDerivationPolicy] = {}

    def register(self, policy: DeterministicDerivationPolicy) -> None:
        if not policy.policy_id:
            raise ValueError("derivation policy requires policy_id")
        if policy.policy_id in self._policies:
            raise ValueError(f"duplicate derivation policy: {policy.policy_id}")
        self._policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> DeterministicDerivationPolicy:
        try:
            return self._policies[policy_id]
        except KeyError as error:
            raise ValueError(f"unknown derivation policy: {policy_id}") from error


class DeterministicDerivationPipeline:
    def __init__(
        self,
        registry: DerivationPolicyRegistry,
        *,
        active_policy_id: str = "NO_OP_DERIVATION",
    ) -> None:
        self.registry = registry
        self.active_policy_id = active_policy_id

    def run(self, state: CanonicalAssemblyState) -> DerivedAssemblyState:
        started = time.perf_counter()
        policy = self.registry.get(self.active_policy_id)
        result = policy.apply(DerivationContext(state))
        if result.canonical_state is not state:
            raise ValueError("derivation must retain the immutable canonical state object")
        if result.canonical_state.resolved_state.identity_ids() != state.resolved_state.identity_ids():
            raise ValueError("derivation changed canonical identities")
        for fact in result.facts:
            if not fact.derived_kind or not fact.source_ids or not fact.value:
                raise ValueError("derived fact requires kind, source identities, and value")
            if not fact.provenance.derived or fact.provenance.model_generated:
                raise ValueError("deterministic fact provenance is misclassified")
        census = StageCensus(
            stage="DETERMINISTIC_DERIVATION",
            input_count=len(state.resolved_state.identity_ids()),
            output_count=len(state.resolved_state.identity_ids()) + len(result.facts),
            preserved_count=len(state.resolved_state.identity_ids()),
            collapsed_count=0,
            derived_count=len(result.facts),
            unresolved_count=sum(
                row.decision == "NOT_DERIVED" for row in result.decisions
            ),
            policy_id=policy.policy_id,
            elapsed_seconds=time.perf_counter() - started,
        )
        return DerivedAssemblyState(state, result.facts, result.decisions, census)
