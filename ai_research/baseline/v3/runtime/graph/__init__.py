"""v2.2 direct PUBLIC assembly와 명시적 legacy graph 분석 API."""

from .assembly import ArticleLocalKGAssembler, AssemblyConfig, load_assembly_config
from .assembly_input import AssemblyInputAdapter, ResolvedAssemblyState
from .canonicalization import (
    EVENT_SPAN_VARIANT_POLICY_ID,
    EVENT_SPAN_VARIANT_POLICY_V2_ID,
    EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID,
    TEMPORAL_SURFACE_CANONICALIZATION_POLICY_ID,
    ENTITY_IDENTITY_CONSTRAINT_POLICY_ID,
    RELEASE_V21_CANONICALIZATION_POLICY_ID,
    CanonicalIdentityIndex,
    CanonicalizationPipeline,
    CanonicalizationPolicyRegistry,
    EventSpanVariantCanonicalizationPolicy,
    EventSpanVariantCanonicalizationPolicyV2,
    EventSpanEquivalenceStrictPolicy,
    NoOpCanonicalizationPolicy,
    TemporalSurfaceCanonicalizationPolicy,
    EntityIdentityConstraintPolicy,
    ReleaseV21CanonicalizationPolicy,
)
from .contracts import ArticleLocalKnowledgeGraphResult
from .compact_assembly import (
    CompactArticleLocalKGAssembler, CompactKnowledgeGraphResult,
    load_compact_assembly_config,
)
from ..eventframe.resolved_contracts import ResolvedGraphState
from .derivation import (
    DerivationPolicyRegistry,
    DeterministicDerivationPipeline,
    NoOpDerivationPolicy,
    TIME_NORMALIZER_V2_POLICY_ID,
    EVENT_TIME_RESCUE_POLICY_ID,
    RELEASE_V21_DERIVATION_POLICY_ID,
    TimeNormalizerV2,
    TimeNormalizerV2Policy,
    EventTimeRescuePolicy,
    ReleaseV21DerivationPolicy,
)
from .foundation import AssemblyFoundationOutcome, AssemblyFoundationPipeline
from .materialization import PublicMaterializer
from .neo4j import (
    PROJECTION_SCHEMA_VERSION, V22_PROJECTION_SCHEMA_VERSION,
    project_graph_for_neo4j, projections_to_cypher,
)
from .observability import AssemblyAuditTrail, ScopeStageCensus, StageCensus
from .output_profiles import (
    ASSEMBLY_OUTPUT_PROFILE_CONTRACT_ID,
    OutputProfile,
    OutputProfileContract,
    OutputProfileProjector,
    PassThroughOutputProjector,
)
from .provenance import PolicyProvenance

__all__ = (
    "ArticleLocalKGAssembler",
    "ArticleLocalKnowledgeGraphResult",
    "CompactArticleLocalKGAssembler",
    "CompactKnowledgeGraphResult",
    "ResolvedGraphState",
    "AssemblyAuditTrail",
    "AssemblyConfig",
    "AssemblyFoundationOutcome",
    "AssemblyFoundationPipeline",
    "AssemblyInputAdapter",
    "CanonicalIdentityIndex",
    "CanonicalizationPipeline",
    "CanonicalizationPolicyRegistry",
    "EVENT_SPAN_VARIANT_POLICY_ID",
    "EVENT_SPAN_VARIANT_POLICY_V2_ID",
    "EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID",
    "TEMPORAL_SURFACE_CANONICALIZATION_POLICY_ID",
    "ENTITY_IDENTITY_CONSTRAINT_POLICY_ID",
    "RELEASE_V21_CANONICALIZATION_POLICY_ID",
    "EventSpanVariantCanonicalizationPolicy",
    "EventSpanVariantCanonicalizationPolicyV2",
    "EventSpanEquivalenceStrictPolicy",
    "TemporalSurfaceCanonicalizationPolicy",
    "EntityIdentityConstraintPolicy",
    "ReleaseV21CanonicalizationPolicy",
    "DerivationPolicyRegistry",
    "DeterministicDerivationPipeline",
    "NoOpCanonicalizationPolicy",
    "NoOpDerivationPolicy",
    "TIME_NORMALIZER_V2_POLICY_ID",
    "EVENT_TIME_RESCUE_POLICY_ID",
    "RELEASE_V21_DERIVATION_POLICY_ID",
    "TimeNormalizerV2",
    "TimeNormalizerV2Policy",
    "EventTimeRescuePolicy",
    "ReleaseV21DerivationPolicy",
    "OutputProfile",
    "OutputProfileContract",
    "OutputProfileProjector",
    "PassThroughOutputProjector",
    "ASSEMBLY_OUTPUT_PROFILE_CONTRACT_ID",
    "PolicyProvenance",
    "PublicMaterializer",
    "ResolvedAssemblyState",
    "ScopeStageCensus",
    "StageCensus",
    "load_assembly_config",
    "load_compact_assembly_config",
    "PROJECTION_SCHEMA_VERSION",
    "V22_PROJECTION_SCHEMA_VERSION",
    "project_graph_for_neo4j",
    "projections_to_cypher",
)
