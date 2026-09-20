"""Explicit Release V2.1 temporal derivation composition."""

from __future__ import annotations

from .contracts import DerivationContext, DerivationResult
from .event_time_rescue import EventTimeRescuePolicy
from .time_normalization_v2 import TimeNormalizerV2Policy


RELEASE_V21_DERIVATION_POLICY_ID = "RELEASE_V21_TEMPORAL_IDENTITY_DERIVATION_V1"


class ReleaseV21DerivationPolicy:
    policy_id = RELEASE_V21_DERIVATION_POLICY_ID
    policy_version = "1"

    def __init__(self) -> None:
        self.time_normalizer = TimeNormalizerV2Policy()
        self.event_time_rescue = EventTimeRescuePolicy()
        self.component_policy_ids = (
            self.time_normalizer.policy_id,
            self.event_time_rescue.policy_id,
        )

    def apply(self, context: DerivationContext) -> DerivationResult:
        normalized = self.time_normalizer.apply(context)
        rescued = self.event_time_rescue.apply(
            DerivationContext(
                context.canonical_state,
                prior_facts=context.prior_facts + normalized.facts,
            )
        )
        return DerivationResult(
            context.canonical_state,
            normalized.facts + rescued.facts,
            normalized.decisions + rescued.decisions,
        )

