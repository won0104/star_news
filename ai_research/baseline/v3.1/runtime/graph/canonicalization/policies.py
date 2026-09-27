"""Built-in canonicalization policies; Work Package A activates NO_OP only."""

from __future__ import annotations

from .contracts import (
    CanonicalizationContext,
    CanonicalizationDecision,
    CanonicalizationResult,
)
from .evidence import preserved_evidence_references
from ..provenance import PolicyProvenance


class NoOpCanonicalizationPolicy:
    """Preserve every existing resolved identity and every evidence reference."""

    policy_id = "NO_OP_CANONICALIZATION"
    policy_version = "1"
    target_scopes: tuple[str, ...] = ()

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        decisions = []
        identities_by_scope = {
            "EVENT": context.resolved_state.resolved_events,
            "ENTITY": context.resolved_state.resolved_entities,
            "STATEMENT": context.resolved_state.statements,
            "TIME": context.resolved_state.time_expressions,
        }
        for scope, rows in identities_by_scope.items():
            for row in rows:
                identity = str(row["node_id"])
                reason = "Work Package A preserves the existing resolved identity verbatim."
                provenance = PolicyProvenance(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    decision_type="PASS_THROUGH",
                    source_ids=(identity,),
                    representative_id=identity,
                    member_ids=(identity,),
                    reason=reason,
                    source_stage="CANONICALIZATION",
                    derived=False,
                    model_generated=False,
                )
                decisions.append(
                    CanonicalizationDecision(
                        policy_id=self.policy_id,
                        policy_version=self.policy_version,
                        scope=scope,
                        input_ids=(identity,),
                        output_representative_id=identity,
                        member_ids=(identity,),
                        decision="PASS_THROUGH",
                        reason=reason,
                        preserved_evidence_references=preserved_evidence_references(
                            identity, row
                        ),
                        provenance=provenance,
                    )
                )
        return CanonicalizationResult(context.resolved_state, tuple(decisions))


def default_canonicalization_registry():
    # Local import avoids a contracts -> registry cycle while keeping registration explicit.
    from .pipeline import CanonicalizationPolicyRegistry

    registry = CanonicalizationPolicyRegistry()
    registry.register(NoOpCanonicalizationPolicy())
    from .event_span import EventSpanVariantCanonicalizationPolicy
    from .event_span_v2 import EventSpanVariantCanonicalizationPolicyV2
    from .event_equivalence_strict import EventSpanEquivalenceStrictPolicy
    from .temporal_surface import TemporalSurfaceCanonicalizationPolicy
    from .entity_identity import EntityIdentityConstraintPolicy
    from .composite import ReleaseV21CanonicalizationPolicy

    registry.register(EventSpanVariantCanonicalizationPolicy())
    registry.register(EventSpanVariantCanonicalizationPolicyV2())
    registry.register(EventSpanEquivalenceStrictPolicy())
    registry.register(TemporalSurfaceCanonicalizationPolicy())
    registry.register(EntityIdentityConstraintPolicy())
    registry.register(ReleaseV21CanonicalizationPolicy())
    return registry
