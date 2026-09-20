"""모델 설정과 tensor 계약.

모든 span index는 ``[sentence, token_start, token_end_exclusive]``이고, 원문 span은
``[character_start, character_end_exclusive)``다. Config dataclass는 run artifact에서
JSON round-trip이 가능하고, tensor dataclass는 학습/추론 경계를 fail-loud하게 검증한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping

import torch


DEFAULT_MODEL_ID = "kakaobank/kf-deberta-base"
DEFAULT_MODEL_REVISION = "363b171d71443b0874b0bf9cea053eb5b1650633"
DEFAULT_WEIGHTS_SHA256 = "3cd6cd7811b3c9190e97cae7eb41571c2bc0076431baae7d41d449a8c1c18c6c"

PRESENCE_LABELS = ("EVENT", "STATEMENT")
PRESENCE_STATES = ("DROP", "EVENT", "STATEMENT", "MIX")
SPAN_KINDS = (
    "ENTITY",
    "TIME",
    "EVENT",
    "STATEMENT",
    "TRIGGER",
    "EVIDENCE",
    "TYPED_LITERAL",
)
LEGACY_RELATION_ONTOLOGY = "legacy_v2_2"
PRODUCTION_RELATION_ONTOLOGY = "production_v1"
RELATION_ONTOLOGY_MODES = (
    LEGACY_RELATION_ONTOLOGY,
    PRODUCTION_RELATION_ONTOLOGY,
)
LEGACY_PAIR_TASKS = (
    "assertor",
    "argument",
    "relation",
    "entity_coreference",
    "event_coreference",
)
PRODUCTION_PAIR_TASKS = (
    "assertor",
    "argument",
    "causal",
    "subevent",
    "statement_about",
    "entity_coreference",
    "event_coreference",
)
# Historical public alias. Keeping its value stable preserves legacy checkpoint shapes.
PAIR_TASKS = LEGACY_PAIR_TASKS
EVENT_ARGUMENT_ROLES = ("ACTOR", "TARGET", "PLACE", "TIME")
TRIGGER_DECODERS = ("greedy_one_to_one", "cartesian")


@dataclass(frozen=True, slots=True)
class TaxonomyConfig:
    """Gold adapter가 교체할 수 있는 label 순서.

    기본값은 Gold v2.0 계약이지만 Head는 tuple 길이만 사용하므로 이후 v2.x에서
    subtype을 추가해도 구조를 다시 작성할 필요가 없다.
    """

    entity_types: tuple[str, ...] = (
        "PERSON",
        "ORGANIZATION",
        "LOCATION",
        "PRODUCT",
    )
    time_types: tuple[str, ...] = ("DATE", "TIME", "DURATION", "SET")
    semantic_labels: tuple[str, ...] = ("EVENT", "STATEMENT")
    statement_types: tuple[str, ...] = ("FORECAST", "CLAIM", "EVALUATION")
    assertor_labels: tuple[str, ...] = ("NONE", "ASSERTED_BY")
    argument_labels: tuple[str, ...] = ("NONE", "ACTOR", "TARGET", "PLACE", "TIME")
    causal_labels: tuple[str, ...] = ("NONE", "CAUSES")
    subevent_labels: tuple[str, ...] = ("NONE", "SUBEVENT_OF")
    statement_about_labels: tuple[str, ...] = ("NONE", "ABOUT")
    # Historical reproduction only. Production mode never registers this label space.
    relation_labels: tuple[str, ...] = ("NONE", "CAUSES", "RESPONDS_TO", "ABOUT")
    coreference_labels: tuple[str, ...] = ("KEEP", "MERGE")

    @property
    def entity_bio_labels(self) -> tuple[str, ...]:
        return ("O",) + tuple(
            label
            for entity_type in self.entity_types
            for label in (f"B-{entity_type}", f"I-{entity_type}")
        )

    @property
    def time_bio_labels(self) -> tuple[str, ...]:
        return ("O",) + tuple(
            label
            for time_type in self.time_types
            for label in (f"B-{time_type}", f"I-{time_type}")
        )


@dataclass(frozen=True, slots=True)
class BackboneConfig:
    """고정된 KF-DeBERTa identity와 명시적 hidden-layer 요청."""

    model_id: str = DEFAULT_MODEL_ID
    revision: str = DEFAULT_MODEL_REVISION
    expected_weights_sha256: str = DEFAULT_WEIGHTS_SHA256
    required_layers: tuple[int, ...] = (8, 10, 12)
    trainable: bool = False
    local_files_only: bool = False

    def __post_init__(self) -> None:
        if self.model_id != DEFAULT_MODEL_ID:
            raise ValueError("Base architecture requires kakaobank/kf-deberta-base")
        if not self.revision or len(self.revision) != 40:
            raise ValueError("backbone revision must be an immutable 40-character commit")
        if tuple(sorted(set(self.required_layers))) != self.required_layers:
            raise ValueError("required_layers must be sorted and unique")
        if not {8, 10, 12}.issubset(self.required_layers):
            raise ValueError("base architecture requires L8, L10, and L12")


@dataclass(frozen=True, slots=True)
class TaskLayerPolicy:
    """학습 mix가 없는 static task-to-layer routing."""

    sentence_presence: int = 8
    entity: int = 12
    time: int = 10
    semantic: int = 8
    trigger: int = 8
    evidence: int = 8
    typed_literal: int = 8

    def for_span_kind(self, kind: str) -> int:
        mapping = {
            "ENTITY": self.entity,
            "TIME": self.time,
            "EVENT": self.semantic,
            "STATEMENT": self.semantic,
            "TRIGGER": self.trigger,
            "EVIDENCE": self.evidence,
            "TYPED_LITERAL": self.typed_literal,
        }
        try:
            return mapping[kind]
        except KeyError as error:
            raise ValueError(f"unknown span kind: {kind}") from error


@dataclass(frozen=True, slots=True)
class ContextConfig:
    input_hidden_size: int = 768
    hidden_size: int = 256
    pooling_hidden_size: int = 128
    document_layers: int = 2
    attention_heads: int = 8
    feedforward_size: int = 1024
    dropout: float = 0.1
    max_span_width: int = 96
    width_embedding_size: int = 32
    kind_embedding_size: int = 24

    def __post_init__(self) -> None:
        if self.hidden_size % self.attention_heads:
            raise ValueError("context hidden_size must be divisible by attention_heads")
        if self.max_span_width <= 0:
            raise ValueError("max_span_width must be positive")


@dataclass(frozen=True, slots=True)
class PairConfig:
    hidden_size: int = 256
    projection_size: int = 256
    kind_embedding_size: int = 24
    distance_embedding_size: int = 32
    order_embedding_size: int = 8
    task_embedding_size: int = 16
    max_sentence_distance: int = 32
    policy_feature_size: int = 4
    dropout: float = 0.1


@dataclass(frozen=True, slots=True)
class TriggerTrainingConfig:
    """확정된 full-source Trigger boundary 학습 계약.

    ``negative_to_positive_ratio=None``은 positive를 포함한 모든 source-token
    boundary를 loss에 사용한다. Ratio가 있는 설정은 ablation에서만 명시적으로 만든다.
    """

    pos_weight: float = 4.0
    negative_to_positive_ratio: float | None = None
    sampling_seed: int = 1008
    status: str = "PRODUCTION_CONTRACT_ADOPTED"

    def __post_init__(self) -> None:
        if self.pos_weight <= 0:
            raise ValueError("Trigger pos_weight must be positive")
        if (
            self.negative_to_positive_ratio is not None
            and self.negative_to_positive_ratio <= 0
        ):
            raise ValueError("Trigger negative ratio must be positive or None")

    @property
    def negative_sampling_enabled(self) -> bool:
        return self.negative_to_positive_ratio is not None


@dataclass(frozen=True, slots=True)
class TriggerDecodeConfig:
    """확정된 Trigger inference와 명시적 decoder ablation 계약."""

    decoder: str = "greedy_one_to_one"
    threshold: float = 0.5
    max_width: int = 64
    max_outputs_per_sentence_label: int | None = 4
    endpoint_reuse: bool = False
    overlap_policy: str = "allow_when_both_endpoints_differ"
    status: str = "PRODUCTION_CONTRACT_ADOPTED"

    def __post_init__(self) -> None:
        if self.decoder not in TRIGGER_DECODERS:
            raise ValueError(f"unsupported Trigger decoder: {self.decoder}")
        if not 0 <= self.threshold <= 1:
            raise ValueError("Trigger threshold must be in [0,1]")
        if self.max_width <= 0:
            raise ValueError("Trigger max_width must be positive")
        if (
            self.max_outputs_per_sentence_label is not None
            and self.max_outputs_per_sentence_label <= 0
        ):
            raise ValueError("Trigger output cap must be positive or None")
        if self.decoder == "greedy_one_to_one":
            if self.endpoint_reuse:
                raise ValueError("greedy Trigger decoder forbids endpoint reuse")
            if self.max_outputs_per_sentence_label is None:
                raise ValueError("greedy Trigger decoder requires an output cap")
            if self.overlap_policy != "allow_when_both_endpoints_differ":
                raise ValueError("greedy Trigger overlap policy differs from implementation")
        elif not self.endpoint_reuse or self.overlap_policy != "unrestricted":
            raise ValueError("Cartesian Trigger decoder reuses unrestricted endpoints")

    @classmethod
    def cartesian_ablation(cls) -> "TriggerDecodeConfig":
        """과거 production/ablation의 Cartesian decoder를 명시적으로 요청한다."""

        return cls(
            decoder="cartesian",
            threshold=0.5,
            max_width=96,
            max_outputs_per_sentence_label=None,
            endpoint_reuse=True,
            overlap_policy="unrestricted",
            status="ABLATION_ONLY",
        )


@dataclass(frozen=True, slots=True)
class ModelConfig:
    backbone: BackboneConfig = field(default_factory=BackboneConfig)
    layers: TaskLayerPolicy = field(default_factory=TaskLayerPolicy)
    context: ContextConfig = field(default_factory=ContextConfig)
    pairs: PairConfig = field(default_factory=PairConfig)
    taxonomy: TaxonomyConfig = field(default_factory=TaxonomyConfig)
    trigger_training: TriggerTrainingConfig = field(
        default_factory=TriggerTrainingConfig
    )
    trigger_decode: TriggerDecodeConfig = field(default_factory=TriggerDecodeConfig)
    head_hidden_size: int = 256
    semantic_biaffine_size: int = 128
    dropout: float = 0.1
    predicted_argument_pooling: str = "decoded"
    event_role_presence_threshold: float = 0.5
    relation_ontology_mode: str = LEGACY_RELATION_ONTOLOGY
    subevent_materialization_enabled: bool = False

    def __post_init__(self) -> None:
        if self.predicted_argument_pooling not in {"decoded", "soft"}:
            raise ValueError("predicted_argument_pooling must be decoded or soft")
        if not 0 <= self.event_role_presence_threshold <= 1:
            raise ValueError("event_role_presence_threshold must be in [0,1]")
        if self.relation_ontology_mode not in RELATION_ONTOLOGY_MODES:
            raise ValueError(
                f"relation_ontology_mode must be one of {RELATION_ONTOLOGY_MODES}"
            )

    @property
    def pair_tasks(self) -> tuple[str, ...]:
        if self.relation_ontology_mode == PRODUCTION_RELATION_ONTOLOGY:
            return PRODUCTION_PAIR_TASKS
        return LEGACY_PAIR_TASKS

    @property
    def hard_relation_tasks(self) -> tuple[str, ...]:
        if self.relation_ontology_mode == PRODUCTION_RELATION_ONTOLOGY:
            return ("causal", "subevent", "statement_about")
        return ("relation",)

    @property
    def materialized_relation_tasks(self) -> tuple[str, ...]:
        if self.relation_ontology_mode != PRODUCTION_RELATION_ONTOLOGY:
            return ("relation",)
        tasks = ["causal", "statement_about"]
        if self.subevent_materialization_enabled:
            tasks.insert(1, "subevent")
        return tuple(tasks)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.relation_ontology_mode == PRODUCTION_RELATION_ONTOLOGY:
            taxonomy = payload["taxonomy"]
            taxonomy["legacy_relation_labels_historical_only"] = taxonomy.pop(
                "relation_labels"
            )
            payload["production_relation_task_labels"] = {
                "causal": list(self.taxonomy.causal_labels),
                "subevent": list(self.taxonomy.subevent_labels),
                "statement_about": list(self.taxonomy.statement_about_labels),
            }
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ModelConfig":
        """``to_dict``/JSON을 거친 model config를 typed contract로 복원한다."""

        def section(name: str) -> dict[str, object]:
            value = payload.get(name)
            if not isinstance(value, Mapping):
                raise TypeError(f"model config section {name} must be a mapping")
            return dict(value)

        backbone = section("backbone")
        backbone["required_layers"] = tuple(backbone["required_layers"])
        taxonomy = section("taxonomy")
        historical_relation_labels = taxonomy.pop(
            "legacy_relation_labels_historical_only", None
        )
        if "relation_labels" not in taxonomy and historical_relation_labels is not None:
            taxonomy["relation_labels"] = historical_relation_labels
        for name in (
            "entity_types",
            "time_types",
            "semantic_labels",
            "statement_types",
            "assertor_labels",
            "argument_labels",
            "causal_labels",
            "subevent_labels",
            "statement_about_labels",
            "relation_labels",
            "coreference_labels",
        ):
            if name in taxonomy:
                taxonomy[name] = tuple(taxonomy[name])
        return cls(
            backbone=BackboneConfig(**backbone),
            layers=TaskLayerPolicy(**section("layers")),
            context=ContextConfig(**section("context")),
            pairs=PairConfig(**section("pairs")),
            taxonomy=TaxonomyConfig(**taxonomy),
            trigger_training=TriggerTrainingConfig(
                **section("trigger_training")
            ),
            trigger_decode=TriggerDecodeConfig(**section("trigger_decode")),
            head_hidden_size=int(payload["head_hidden_size"]),
            semantic_biaffine_size=int(payload["semantic_biaffine_size"]),
            dropout=float(payload["dropout"]),
            predicted_argument_pooling=str(payload["predicted_argument_pooling"]),
            event_role_presence_threshold=float(
                payload["event_role_presence_threshold"]
            ),
            relation_ontology_mode=str(
                payload.get("relation_ontology_mode", LEGACY_RELATION_ONTOLOGY)
            ),
            subevent_materialization_enabled=bool(
                payload.get("subevent_materialization_enabled", False)
            ),
        )


@dataclass(slots=True)
class ArticleBatch:
    """한 article batch의 sentence-token 입력.

    Shapes: ids/masks ``[B,S,T]``, token offsets ``[B,S,T,2]``, sentence character
    offsets ``[B,S,2]``. ``source_token_mask``는 special/padding을 제외한다.
    """

    input_ids: torch.LongTensor
    attention_mask: torch.BoolTensor
    source_token_mask: torch.BoolTensor
    sentence_mask: torch.BoolTensor
    sentence_positions: torch.LongTensor
    token_offsets: torch.LongTensor
    sentence_char_offsets: torch.LongTensor
    article_ids: tuple[str, ...]
    contents: tuple[str, ...]
    published_at: tuple[str | None, ...]

    def validate(self) -> None:
        if self.input_ids.ndim != 3:
            raise ValueError("input_ids must have shape [B,S,T]")
        shape = self.input_ids.shape
        for name, value in (
            ("attention_mask", self.attention_mask),
            ("source_token_mask", self.source_token_mask),
        ):
            if value.shape != shape or value.dtype is not torch.bool:
                raise ValueError(f"{name} must be bool [B,S,T]")
        if self.sentence_mask.shape != shape[:2] or self.sentence_mask.dtype is not torch.bool:
            raise ValueError("sentence_mask must be bool [B,S]")
        if self.sentence_positions.shape != shape[:2]:
            raise ValueError("sentence_positions must have shape [B,S]")
        if self.token_offsets.shape != (*shape, 2):
            raise ValueError("token_offsets must have shape [B,S,T,2]")
        if self.sentence_char_offsets.shape != (*shape[:2], 2):
            raise ValueError("sentence_char_offsets must have shape [B,S,2]")
        if len(self.article_ids) != shape[0] or len(self.contents) != shape[0]:
            raise ValueError("article metadata must align with B")
        if torch.any(self.source_token_mask & ~self.attention_mask):
            raise ValueError("source tokens must also be attended")
        if not torch.all(self.sentence_mask.any(dim=1)):
            raise ValueError("every article must contain at least one sentence")

    def to(self, device: torch.device | str) -> "ArticleBatch":
        return ArticleBatch(
            input_ids=self.input_ids.to(device),
            attention_mask=self.attention_mask.to(device),
            source_token_mask=self.source_token_mask.to(device),
            sentence_mask=self.sentence_mask.to(device),
            sentence_positions=self.sentence_positions.to(device),
            token_offsets=self.token_offsets.to(device),
            sentence_char_offsets=self.sentence_char_offsets.to(device),
            article_ids=self.article_ids,
            contents=self.contents,
            published_at=self.published_at,
        )


@dataclass(slots=True)
class PairIndexBatch:
    """Head에 전달할 사전 제한된 packed pair. Shapes are ``[B,P]``/``[B,P,F]``."""

    source_indices: torch.LongTensor
    target_indices: torch.LongTensor
    mask: torch.BoolTensor
    policy_features: torch.Tensor
    class_mask: torch.BoolTensor | None = None

    def validate(self, candidate_count: int) -> None:
        shape = self.source_indices.shape
        if self.target_indices.shape != shape or self.mask.shape != shape:
            raise ValueError("pair index tensors must share [B,P]")
        if self.mask.dtype is not torch.bool or self.policy_features.shape[:2] != shape:
            raise ValueError("pair mask/features do not align")
        for values in (self.source_indices[self.mask], self.target_indices[self.mask]):
            if values.numel() and (torch.any(values < 0) or torch.any(values >= candidate_count)):
                raise ValueError("pair candidate index is out of range")
        if self.class_mask is not None and self.class_mask.shape[:2] != shape:
            raise ValueError("class_mask must start with [B,P]")

    def to(self, device: torch.device | str) -> "PairIndexBatch":
        return PairIndexBatch(
            self.source_indices.to(device),
            self.target_indices.to(device),
            self.mask.to(device),
            self.policy_features.to(device),
            None if self.class_mask is None else self.class_mask.to(device),
        )


@dataclass(slots=True)
class CandidateBatch:
    """teacher-forced 또는 decoded candidate graph의 packed tensor 계약.

    ``span_indices`` is ``[B,N,3]``. Semantic verifier proposals use the same
    sentence/start/end format in ``[B,Q,3]`` and permit multi-label targets.
    """

    span_indices: torch.LongTensor
    span_kind_ids: torch.LongTensor
    span_mask: torch.BoolTensor
    semantic_proposal_indices: torch.LongTensor
    semantic_proposal_mask: torch.BoolTensor
    statement_indices: torch.LongTensor
    statement_mask: torch.BoolTensor
    event_indices: torch.LongTensor
    event_source_indices: torch.LongTensor
    event_mask: torch.BoolTensor
    event_trigger_indices: torch.LongTensor
    event_trigger_mask: torch.BoolTensor
    oracle_argument_role_weights: torch.Tensor | None
    pairs: dict[str, PairIndexBatch]
    pair_task_names: tuple[str, ...] = LEGACY_PAIR_TASKS

    def validate(self, article_shape: tuple[int, int, int]) -> None:
        batch, sentence_count, token_count = article_shape
        if self.span_indices.ndim != 3 or self.span_indices.shape[-1] != 3:
            raise ValueError("span_indices must have shape [B,N,3]")
        if self.span_indices.shape[0] != batch:
            raise ValueError("candidate batch B differs from article batch")
        shape = self.span_indices.shape[:2]
        if self.span_kind_ids.shape != shape or self.span_mask.shape != shape:
            raise ValueError("candidate kind/mask must align with [B,N]")
        active = self.span_indices[self.span_mask]
        if active.numel():
            if torch.any(active[:, 0] < 0) or torch.any(active[:, 0] >= sentence_count):
                raise ValueError("candidate sentence index is out of range")
            if torch.any(active[:, 1] < 0) or torch.any(active[:, 2] > token_count):
                raise ValueError("candidate token boundary is out of range")
            if torch.any(active[:, 1] >= active[:, 2]):
                raise ValueError("candidate spans must be non-empty")
        if self.semantic_proposal_indices.shape[:1] != (batch,):
            raise ValueError("semantic proposals must align with B")
        if (
            self.semantic_proposal_indices.ndim != 3
            or self.semantic_proposal_indices.shape[-1] != 3
            or self.semantic_proposal_mask.shape
            != self.semantic_proposal_indices.shape[:2]
        ):
            raise ValueError("semantic proposals/mask must be [B,Q,3]/[B,Q]")
        if self.statement_indices.shape != self.statement_mask.shape:
            raise ValueError("statement indices/mask must align")
        if self.event_indices.shape != self.event_mask.shape:
            raise ValueError("event indices/mask must align")
        if self.event_source_indices.shape != self.event_mask.shape:
            raise ValueError("event source indices must align with event candidates")
        if self.event_trigger_indices.shape != self.event_mask.shape or self.event_trigger_mask.shape != self.event_mask.shape:
            raise ValueError("event trigger index/mask must align with event candidates")
        for name, values, active_mask in (
            ("statement", self.statement_indices, self.statement_mask),
            ("event", self.event_indices, self.event_mask),
            ("event source", self.event_source_indices, self.event_mask),
            ("event trigger", self.event_trigger_indices, self.event_trigger_mask),
        ):
            active_values = values[active_mask]
            if active_values.numel() and (
                torch.any(active_values < 0) or torch.any(active_values >= shape[1])
            ):
                raise ValueError(f"{name} candidate index is out of range")
        if tuple(self.pairs) != self.pair_task_names:
            raise ValueError(
                "candidate batch pair order/names must match its ontology contract"
            )
        argument_shape = self.pairs["argument"].mask.shape
        if self.oracle_argument_role_weights is not None and self.oracle_argument_role_weights.shape != (*argument_shape, len(EVENT_ARGUMENT_ROLES)):
            raise ValueError("oracle argument weights must be [B,P_argument,4]")
        if self.oracle_argument_role_weights is not None and (
            not torch.isfinite(self.oracle_argument_role_weights).all()
            or torch.any(self.oracle_argument_role_weights < 0)
        ):
            raise ValueError("oracle argument weights must be finite and non-negative")
        for pair in self.pairs.values():
            pair.validate(shape[1])

    def to(self, device: torch.device | str) -> "CandidateBatch":
        return CandidateBatch(
            span_indices=self.span_indices.to(device),
            span_kind_ids=self.span_kind_ids.to(device),
            span_mask=self.span_mask.to(device),
            semantic_proposal_indices=self.semantic_proposal_indices.to(device),
            semantic_proposal_mask=self.semantic_proposal_mask.to(device),
            statement_indices=self.statement_indices.to(device),
            statement_mask=self.statement_mask.to(device),
            event_indices=self.event_indices.to(device),
            event_source_indices=self.event_source_indices.to(device),
            event_mask=self.event_mask.to(device),
            event_trigger_indices=self.event_trigger_indices.to(device),
            event_trigger_mask=self.event_trigger_mask.to(device),
            oracle_argument_role_weights=(
                None
                if self.oracle_argument_role_weights is None
                else self.oracle_argument_role_weights.to(device)
            ),
            pairs={name: value.to(device) for name, value in self.pairs.items()},
            pair_task_names=self.pair_task_names,
        )


@dataclass(slots=True)
class BackboneOutput:
    hidden_by_layer: Mapping[int, torch.Tensor]
    attention_mask: torch.BoolTensor
    sentence_mask: torch.BoolTensor

    def layer(self, index: int) -> torch.Tensor:
        try:
            return self.hidden_by_layer[index]
        except KeyError as error:
            raise ValueError(f"backbone output does not contain L{index}") from error


@dataclass(slots=True)
class DocumentContextOutput:
    sentence_states: torch.Tensor
    token_states: torch.Tensor
    document_state: torch.Tensor
    token_attention: torch.Tensor
    reinjection_gate: torch.Tensor


@dataclass(slots=True)
class PresenceOutput:
    bit_logits: torch.Tensor
    state_logits: torch.Tensor
    event_present: torch.BoolTensor
    statement_present: torch.BoolTensor
    state_ids: torch.LongTensor
    keep_mask: torch.BoolTensor


@dataclass(slots=True)
class TokenHeadOutput:
    logits: torch.Tensor
    mask: torch.BoolTensor


@dataclass(slots=True)
class BoundaryHeadOutput:
    start_logits: torch.Tensor
    end_logits: torch.Tensor
    mask: torch.BoolTensor


@dataclass(slots=True)
class SemanticSpanOutput:
    boundaries: BoundaryHeadOutput
    proposal_logits: torch.Tensor | None
    proposal_mask: torch.BoolTensor | None


@dataclass(slots=True)
class PairOutput:
    logits: torch.Tensor
    mask: torch.BoolTensor
    class_mask: torch.BoolTensor | None = None


@dataclass(slots=True)
class ConstructionOutput:
    candidate_states: torch.Tensor
    statement_type: PairOutput
    pairs: dict[str, PairOutput]
    event_features: object
    event_states: torch.Tensor
    event_feature_mode: str


@dataclass(slots=True)
class ArticleModelOutput:
    backbone: BackboneOutput
    context: DocumentContextOutput
    presence: PresenceOutput
    entity: object
    time: object
    trigger: object
    semantic: object
    construction: ConstructionOutput | None
    task_outputs: Mapping[str, object] = field(default_factory=dict)


def gather_candidates(states: torch.Tensor, indices: torch.Tensor) -> torch.Tensor:
    """Gather ``[B,N,H]`` with packed ``[B,K]`` indices; negative padding maps to zero."""

    if states.ndim != 3 or indices.ndim != 2 or states.shape[0] != indices.shape[0]:
        raise ValueError("candidate gather expects states [B,N,H] and indices [B,K]")
    safe = indices.clamp(0, max(states.shape[1] - 1, 0))
    if states.shape[1] == 0:
        return states.new_zeros(indices.shape[0], indices.shape[1], states.shape[-1])
    return states.gather(1, safe.unsqueeze(-1).expand(-1, -1, states.shape[-1]))
