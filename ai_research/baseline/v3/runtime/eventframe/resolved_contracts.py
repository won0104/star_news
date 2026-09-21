"""v2.2 mention/identity/fact/graph 경계의 작고 분리된 carrier 계약.

모델 tensor는 ModelHandoff에만 존재한다. 최종 graph state에는 raw member,
source graph, source lane 또는 모델 표현 참조를 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Any, Mapping

from ..temporal_identity import TemporalIdentityKey


COMPACT_RUNTIME_CONTRACT_ID = "ARTICLELOCAL_COMPACT_RUNTIME_V22_V1"
PUBLIC_SCHEMA_VERSION = "articlelocal-kg-public-v2.2"
OUTPUT_PROFILE_CONTRACT_ID = "ASSEMBLY_OUTPUT_PROFILE_V3"
SEMANTIC_KINDS = frozenset(("EVENT", "STATEMENT", "ENTITY", "TIME"))
STATE_STATUSES = frozenset(("EXECUTED", "EMPTY", "NOT_RUN", "UNRESOLVED", "ERROR"))
PUBLIC_SEMANTIC_PROPERTY_KEYS = {
    "ARTICLE": frozenset(("article_id", "article_version_id", "content_sha256",
                           "published_at", "title", "source", "article_local")),
    "EVENT": frozenset(("canonical_text", "identity_confidence",
                         "identity_confidence_source", "independent_support_count",
                         "triggers", "role_conflicts", "time_conflict",
                         "predicate_conflict", "modality_conflict",
                         "missing_feature_reasons", "status")),
    "STATEMENT": frozenset(("canonical_text", "statement_type_status",
                             "statement_type_value", "status")),
    "ENTITY": frozenset(("canonical_name", "entity_type",
                          "identity_confidence", "identity_confidence_source",
                          "article_local", "status")),
    "TIME": frozenset(("normalized_value", "granularity",
                        "normalization_status", "temporal_semantic_type",
                        "timezone", "normalization_source", "status")),
}
PUBLIC_SEMANTIC_REQUIRED_KEYS = {
    "ARTICLE": frozenset(("article_id", "article_version_id", "content_sha256",
                           "published_at", "title", "source", "article_local")),
    "EVENT": frozenset(("canonical_text", "identity_confidence",
                         "identity_confidence_source", "independent_support_count",
                         "triggers", "status")),
    "STATEMENT": frozenset(("canonical_text", "statement_type_status",
                             "statement_type_value", "status")),
    "ENTITY": frozenset(("canonical_name", "entity_type", "identity_confidence",
                          "identity_confidence_source", "status")),
    "TIME": frozenset(("normalized_value", "granularity",
                        "normalization_status", "temporal_semantic_type",
                        "timezone", "status")),
}


def _semantic_scalar(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, bool)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (tuple, list)):
        return all(_semantic_scalar(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _semantic_scalar(item)
                   for key, item in value.items())
    return False


@dataclass(frozen=True, slots=True)
class GroundingRef:
    article_version_id: str
    char_start: int
    char_end: int
    sentence_index: int | None = None

    def __post_init__(self) -> None:
        if not self.article_version_id or self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("grounding requires article version and nonempty [start,end)")

    def text(self, *, article_version_id: str, source_text: str) -> str:
        if article_version_id != self.article_version_id or self.char_end > len(source_text):
            raise ValueError("grounding source version or offset differs")
        return source_text[self.char_start:self.char_end]


@dataclass(frozen=True, slots=True)
class SpanHypothesis:
    hypothesis_id: str
    kind: str
    grounding: GroundingRef
    semantic_score: float
    boundary_score: float | None = None

    def __post_init__(self) -> None:
        if not self.hypothesis_id or self.kind not in SEMANTIC_KINDS:
            raise ValueError("invalid span hypothesis identity/kind")


@dataclass(frozen=True, slots=True)
class AcceptedSpanHypothesis:
    """두 frozen head의 AND를 통과했으나 아직 family/mention identity가 아닌 span."""

    hypothesis_id: str
    kind: str
    grounding: GroundingRef
    sentence_id: str
    sentence_index: int
    token_start: int
    token_end: int
    semantic_score: float
    boundary_score: float
    semantic_threshold: float
    boundary_threshold: float

    def __post_init__(self) -> None:
        if (not self.hypothesis_id or self.kind not in ("EVENT", "STATEMENT")
            or self.sentence_index < 0 or self.token_end <= self.token_start):
            raise ValueError("invalid accepted semantic hypothesis")
        if self.grounding.sentence_index not in (None, self.sentence_index):
            raise ValueError("hypothesis sentence and grounding differ")
        values = (self.semantic_score, self.boundary_score,
                  self.semantic_threshold, self.boundary_threshold)
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("semantic and boundary scores must be finite probabilities")
        if (self.semantic_score < self.semantic_threshold
            or self.boundary_score < self.boundary_threshold):
            raise ValueError("accepted hypothesis must pass both frozen heads")


@dataclass(frozen=True, slots=True)
class CanonicalMention:
    mention_id: str
    kind: str
    representative: GroundingRef
    accepted_score: float
    family_size: int = 1

    def __post_init__(self) -> None:
        if not self.mention_id or self.kind not in SEMANTIC_KINDS or self.family_size < 1:
            raise ValueError("invalid canonical mention")


class ModelHandoff:
    """동일 producer/layer/context에서 계산한 내부 표현; JSON 변환 API 없음."""

    __slots__ = ("producer", "layer", "context_id", "tensor", "member_count")

    def __init__(self, producer: str, layer: int, context_id: str,
                 tensor: object, member_count: int) -> None:
        if not producer or not context_id or layer < 0 or member_count < 1:
            raise ValueError("model handoff needs producer/layer/context/member count")
        self.producer = producer
        self.layer = layer
        self.context_id = context_id
        self.tensor = tensor
        self.member_count = member_count

    def release(self) -> None:
        self.tensor = None


@dataclass(slots=True)
class LocalEntityState:
    entity_id: str
    canonical_name: str
    entity_type: str
    grounding: tuple[GroundingRef, ...]
    representation: ModelHandoff | None = None
    identity_confidence: float | None = None
    identity_confidence_source: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalStatementState:
    statement_id: str
    canonical_text: str
    representative: GroundingRef
    statement_type_status: str
    statement_type_value: str | None

    def __post_init__(self) -> None:
        if self.statement_type_status not in STATE_STATUSES:
            raise ValueError("invalid canonical StatementType status")


@dataclass(frozen=True, slots=True)
class CanonicalTemporalState:
    """6단계 occurrence의 정적 normalization input; 원문 text/candidate는 없다."""

    prediction_id: str
    temporal_occurrence_id: str
    representative: GroundingRef
    temporal_semantic_type: str
    v1_normalization_status: str
    normalized_key: TemporalIdentityKey | None

    def __post_init__(self) -> None:
        if self.v1_normalization_status not in ("NORMALIZED", "UNRESOLVED"):
            raise ValueError("invalid V1 temporal normalization status")
        if self.normalized_key is not None and self.temporal_semantic_type != "POINT":
            raise ValueError("only point Time may have a normalized identity")


@dataclass(slots=True)
class EventFrameState:
    event_mention_id: str
    trigger: GroundingRef | None
    role_grounding: tuple[GroundingRef, ...]
    time_grounding: tuple[GroundingRef, ...]
    feature_handoff: ModelHandoff | None = None


@dataclass(frozen=True, slots=True)
class GroundedFact:
    fact_id: str
    relation: str
    source_identity_id: str
    target_identity_id: str
    supports: tuple[GroundingRef, ...]
    confidence: float | None = None
    status: str = "EXECUTED"

    def __post_init__(self) -> None:
        if not self.fact_id or not self.source_identity_id or not self.target_identity_id:
            raise ValueError("fact endpoints and identity are required")
        if self.status not in STATE_STATUSES:
            raise ValueError("invalid fact status")


@dataclass(frozen=True, slots=True)
class EventConflictSummary:
    role_conflicts: tuple[str, ...] = ()
    time_conflict: bool = False
    predicate_conflict: bool = False
    modality_conflict: bool = False
    missing_feature_reasons: tuple[str, ...] = ()

    @property
    def conflict_free(self) -> bool:
        return not (self.role_conflicts or self.time_conflict
                    or self.predicate_conflict or self.modality_conflict)


@dataclass(frozen=True, slots=True)
class EventSupportSummary:
    unique_fact_grounding_count: int
    unresolved_role_grounding: tuple[tuple[str, GroundingRef], ...] = ()
    unresolved_time_grounding: tuple[GroundingRef, ...] = ()
    normalized_time_keys: tuple[tuple[str, TemporalIdentityKey], ...] = ()


@dataclass(frozen=True, slots=True)
class LocalEventState:
    """Identity closure 뒤의 기본 live EVENT carrier; raw member/pair refs가 없다."""

    event_id: str
    canonical_text: str
    representative: GroundingRef
    triggers: tuple[GroundingRef, ...]
    facts: tuple[GroundedFact, ...]
    identity_confidence: float
    identity_confidence_source: str
    independent_support_count: int
    conflict_summary: EventConflictSummary
    support_summary: EventSupportSummary

    def __post_init__(self) -> None:
        if (not self.event_id or not self.canonical_text
            or self.independent_support_count < 1
            or not math.isfinite(self.identity_confidence)):
            raise ValueError("local event needs identity and independent support")


@dataclass(frozen=True, slots=True)
class EventIdentityClosure:
    """9단계 direct assembly handoff; legacy compatibility payload는 포함하지 않는다."""

    local_events: tuple[LocalEventState, ...]
    identity_remap: Mapping[str, str]
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PublicIdentity:
    identity_id: str
    kind: str
    representative: GroundingRef | None
    canonical_text: str | None = None
    semantic_properties: Mapping[str, Any] | None = None
    evidence: tuple[GroundingRef, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in PUBLIC_SEMANTIC_PROPERTY_KEYS or not self.identity_id:
            raise ValueError("invalid PUBLIC identity kind/ID")
        properties = self.semantic_properties or {}
        if (set(properties) - PUBLIC_SEMANTIC_PROPERTY_KEYS[self.kind]
            or not _semantic_scalar(properties)):
            raise ValueError("PUBLIC identity has nonsemantic/raw properties")
        if not PUBLIC_SEMANTIC_REQUIRED_KEYS[self.kind].issubset(properties):
            raise ValueError("PUBLIC identity lacks required semantic properties")
        if self.kind != "ARTICLE" and self.representative is None:
            raise ValueError("semantic identity needs representative grounding")
        if self.kind in ("EVENT", "ENTITY") and properties.get("identity_confidence") is None:
            raise ValueError("identity confidence cannot be absent")
        if self.kind == "EVENT" and any(
            not isinstance(trigger, Mapping)
            or set(trigger) != {"text", "sentence_index", "char_start", "char_end"}
            for trigger in properties["triggers"]
        ):
            raise ValueError("EVENT trigger properties must be allowlisted occurrences")
        if self.kind == "TIME" and (
            not properties.get("normalized_value") or not properties.get("granularity")
            or properties.get("normalization_status") != "NORMALIZED"
        ):
            raise ValueError("PUBLIC Time requires a real normalized identity")


@dataclass(frozen=True, slots=True)
class GroundingRegistry:
    """fact/identity의 source ref만 이관한다. 원문과 후보 inventory는 포함하지 않는다."""

    refs: Mapping[str, GroundingRef]


@dataclass(frozen=True, slots=True)
class ResolvedGraphState:
    article_id: str
    article_version_id: str
    content_sha256: str
    published_at: str
    identities: tuple[PublicIdentity, ...]
    facts: tuple[GroundedFact, ...]
    identity_remap: Mapping[str, str]
    grounding_registry: GroundingRegistry
    lane_statuses: Mapping[str, str]
    title: str | None = None
    source: str | None = None
    runtime_config_id: str = ""
    assembly_config_id: str = ""
    active_policy_ids: tuple[str, ...] = ()
    component_provenance: Mapping[str, str] | None = None
    temporal_occurrences: tuple[CanonicalTemporalState, ...] = ()
    pending_temporal_facts: tuple[GroundedFact, ...] = ()
    unresolved_fact_count: int = 0
    lane_reasons: Mapping[str, str] | None = None
    runtime_config_sha256: str | None = None
    assembly_config_sha256: str | None = None
    public_schema_sha256: str | None = None
    policy_config_sha256: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.article_id or not self.article_version_id or not self.published_at:
            raise ValueError("resolved graph requires article identity/version/date")
        if len(self.content_sha256) != 64:
            raise ValueError("resolved graph requires SHA-256 content digest")
        if any(status not in STATE_STATUSES for status in self.lane_statuses.values()):
            raise ValueError("invalid lane status")
        identity_ids = {row.identity_id for row in self.identities}
        if len(identity_ids) != len(self.identities):
            raise ValueError("duplicate compact identity")
        if any(fact.source_identity_id not in identity_ids
               or fact.target_identity_id not in identity_ids for fact in self.facts):
            raise ValueError("compact fact has dangling canonical endpoint")
        if any(target not in identity_ids for target in self.identity_remap.values()):
            raise ValueError("compact alias remap targets a nonmaterialized identity")
        if any(ref.article_version_id != self.article_version_id
               for ref in self.grounding_registry.refs.values()):
            raise ValueError("grounding registry crossed article version")
        hashes = (
            self.runtime_config_sha256, self.assembly_config_sha256,
            self.public_schema_sha256,
            *(self.policy_config_sha256 or {}).values(),
        )
        if any(value is not None and len(value) != 64 for value in hashes):
            raise ValueError("compact graph config/schema provenance needs SHA-256")

    @classmethod
    def content_digest(cls, content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()
