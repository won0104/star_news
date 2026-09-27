"""Canonical representation policy contracts and deterministic pipeline."""

from .contracts import (
    CanonicalAssemblyState,
    CanonicalIdentityIndex,
    CanonicalizationContext,
    CanonicalizationDecision,
    CanonicalizationPolicy,
    CanonicalizationResult,
)
from .event_span import (
    EVENT_SPAN_VARIANT_POLICY_ID,
    EventSpanVariantCanonicalizationPolicy,
    evaluate_event_pair,
    representative_sort_key,
)
from .event_span_v2 import (
    EVENT_SPAN_VARIANT_POLICY_V2_ID,
    EventSpanVariantCanonicalizationPolicyV2,
    evaluate_event_pair_v2,
)
from .event_equivalence_strict import (
    EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID,
    EventSpanEquivalenceStrictPolicy,
    evaluate_event_equivalence,
)
from .equivalence import EquivalenceDecision, EquivalenceEvidence, EventSupportSignature
from .event_view import EventIdentityView, build_event_identity_views
from .semantic_expansion import SemanticExpansionDecision, SemanticExpansionGuard
from .temporal_surface import (
    TEMPORAL_SURFACE_CANONICALIZATION_POLICY_ID,
    TemporalSurfaceCanonicalizationPolicy,
)
from .entity_identity import (
    ENTITY_IDENTITY_CONSTRAINT_POLICY_ID,
    EntityIdentityConstraintPolicy,
)
from .composite import (
    RELEASE_V21_CANONICALIZATION_POLICY_ID,
    ReleaseV21CanonicalizationPolicy,
)
from .pipeline import CanonicalizationPipeline, CanonicalizationPolicyRegistry
from .policies import NoOpCanonicalizationPolicy, default_canonicalization_registry

__all__ = (
    "CanonicalAssemblyState",
    "CanonicalIdentityIndex",
    "CanonicalizationContext",
    "CanonicalizationDecision",
    "CanonicalizationPolicy",
    "CanonicalizationResult",
    "CanonicalizationPipeline",
    "CanonicalizationPolicyRegistry",
    "EVENT_SPAN_VARIANT_POLICY_ID",
    "EVENT_SPAN_VARIANT_POLICY_V2_ID",
    "EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID",
    "EventIdentityView",
    "EventSpanVariantCanonicalizationPolicy",
    "EventSpanVariantCanonicalizationPolicyV2",
    "EventSpanEquivalenceStrictPolicy",
    "NoOpCanonicalizationPolicy",
    "default_canonicalization_registry",
    "build_event_identity_views",
    "evaluate_event_pair",
    "evaluate_event_pair_v2",
    "evaluate_event_equivalence",
    "EquivalenceDecision",
    "EquivalenceEvidence",
    "EventSupportSignature",
    "representative_sort_key",
    "SemanticExpansionDecision",
    "SemanticExpansionGuard",
    "TEMPORAL_SURFACE_CANONICALIZATION_POLICY_ID",
    "TemporalSurfaceCanonicalizationPolicy",
    "ENTITY_IDENTITY_CONSTRAINT_POLICY_ID",
    "EntityIdentityConstraintPolicy",
    "RELEASE_V21_CANONICALIZATION_POLICY_ID",
    "ReleaseV21CanonicalizationPolicy",
)
