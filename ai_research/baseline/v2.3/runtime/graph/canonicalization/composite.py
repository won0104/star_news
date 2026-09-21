"""Explicit scope composition for the Release V2.1 canonicalization family."""

from __future__ import annotations

from .contracts import CanonicalizationContext, CanonicalizationResult
from .entity_identity import EntityIdentityConstraintPolicy
from .event_equivalence_strict import EventSpanEquivalenceStrictPolicy
from .policies import NoOpCanonicalizationPolicy
from .temporal_surface import TemporalSurfaceCanonicalizationPolicy


RELEASE_V21_CANONICALIZATION_POLICY_ID = (
    "RELEASE_V21_TEMPORAL_IDENTITY_CANONICALIZATION_V1"
)


class ReleaseV21CanonicalizationPolicy:
    """Compose fixed EVENT, TIME, and ENTITY decisions without copying policy logic."""

    policy_id = RELEASE_V21_CANONICALIZATION_POLICY_ID
    policy_version = "1"
    target_scopes = ("EVENT", "TIME", "ENTITY")

    def __init__(self) -> None:
        self._policies = {
            "EVENT": EventSpanEquivalenceStrictPolicy(),
            "TIME": TemporalSurfaceCanonicalizationPolicy(),
            "ENTITY": EntityIdentityConstraintPolicy(),
        }
        self.component_policy_ids = tuple(
            policy.policy_id for policy in self._policies.values()
        )

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        component_results = {
            scope: policy.apply(context)
            for scope, policy in self._policies.items()
        }
        no_op = NoOpCanonicalizationPolicy().apply(context)
        decisions = []
        diagnostics = []
        for scope in ("EVENT", "ENTITY", "TIME"):
            result = component_results[scope]
            decisions.extend(row for row in result.decisions if row.scope == scope)
            diagnostics.extend(
                {"component_policy_id": self._policies[scope].policy_id, **dict(row)}
                for row in result.pair_diagnostics
            )
        decisions.extend(row for row in no_op.decisions if row.scope == "STATEMENT")
        return CanonicalizationResult(
            context.resolved_state,
            tuple(decisions),
            tuple(diagnostics),
        )

