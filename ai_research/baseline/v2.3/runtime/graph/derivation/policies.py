"""Explicit registry for built-in deterministic derivation policies."""

from __future__ import annotations

from .contracts import DerivationContext, DerivationDecision, DerivationResult
from ..provenance import PolicyProvenance


class NoOpDerivationPolicy:
    policy_id = "NO_OP_DERIVATION"
    policy_version = "1"

    def apply(self, context: DerivationContext) -> DerivationResult:
        source_ids = context.canonical_state.resolved_state.identity_ids()
        reason = "Work Package A replays existing deterministic behavior and derives no new fact."
        provenance = PolicyProvenance(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            decision_type="NOT_DERIVED",
            source_ids=source_ids,
            representative_id=None,
            member_ids=(),
            reason=reason,
            source_stage="DETERMINISTIC_DERIVATION",
            derived=False,
            model_generated=False,
        )
        decision = DerivationDecision(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            source_ids=source_ids,
            derived_kind="NONE",
            decision="NOT_DERIVED",
            reason=reason,
            provenance=provenance,
        )
        return DerivationResult(context.canonical_state, (), (decision,))


def default_derivation_registry():
    from .pipeline import DerivationPolicyRegistry

    registry = DerivationPolicyRegistry()
    registry.register(NoOpDerivationPolicy())
    from .time_normalization_v2 import TimeNormalizerV2Policy
    from .event_time_rescue import EventTimeRescuePolicy
    from .composite import ReleaseV21DerivationPolicy

    registry.register(TimeNormalizerV2Policy())
    registry.register(EventTimeRescuePolicy())
    registry.register(ReleaseV21DerivationPolicy())
    return registry
