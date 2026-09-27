"""검증된 train Gold만 소비하는 v3 fresh-init 학습 step.

Pinned backbone은 외부의 frozen producer다. 하나의 DCE/shared feature 경로에서
현재 등록된 task loss를 결합하며, scalar loss 외의 feature는 요청 scope를 벗어나지 않는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from time import perf_counter
from types import SimpleNamespace
from typing import Mapping, Sequence

import numpy as np
import torch
from torch import nn

from models.backbone import KFDeBERTaBackbone
from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import V3ArchitectureConfig, V3ArchitectureFactory, V3Core
from models.v3_pretraining.attribution_heads import register_attribution_heads
from models.v3_pretraining.entity_heads import register_entity_heads
from models.v3_pretraining.event_heads import register_event_heads
from models.v3_pretraining.extraction_heads import register_extraction_heads
from models.v3_pretraining.frozen_features import (FrozenBackboneFeatureBuilder,
                                                   RunLocalFrozenFeatureCache)
from models.v3_pretraining.primary_head import register_primary_head
from models.v3_pretraining.task_contract import HEAD_TASKS
from models.v3_pretraining.time_heads import register_time_heads
from runtime.v3_pretraining.event_features import finalize_cluster_features
from runtime.v3_pretraining.exact_feature_cache import RequestExactFeatureCache
from runtime.v3_pretraining.extraction_decode import (
    DecodeBudget, RetrievalBudget, decode_source_spans, event_source_state,
    precompute_v23_participant_boundaries, source_decode_context,
)
from runtime.v3_pretraining.source_layout import LayoutBuilder
from runtime.v3_pretraining.handoff import FrozenSourceViewKey
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer
from training.v3_pretraining.attribution import AttributionGoldAdapter
from training.v3_pretraining.collator import TargetCollator
from training.v3_pretraining.entity import EntityGoldAdapter
from training.v3_pretraining.event import EventGoldAdapter
from training.v3_pretraining.extraction import ExtractionGoldAdapter
from training.v3_pretraining.negative_authority import ReviewedNegativeAuthority
from training.v3_pretraining.optimization_contract import (
    clip_gradients_with_observability, reduce_active_task_losses)
from training.v3_pretraining.primary import PrimaryGoldAdapter
from training.v3_pretraining.relation_evaluation import aggregate_article_reports
from training.v3_pretraining.relation_sampling import (RelationSamplingPolicy,
                                                       build_relation_training_metadata)
from training.v3_pretraining.selection_contract import (
    GRADIENT_CLIP_CONTRACT_VERSION, LOSS_REDUCTION_CONTRACT_VERSION,
    SELECTION_POLICY_VERSION, average_precision_with_retrieval_misses)
from training.v3_pretraining.selection_evaluation import (
    ExtractionEvaluationAuthority, ap_from_full_universe,
    assemble_selection_components, bind_extraction_epoch_scores,
    score_extraction_authority)
from training.v3_pretraining.targets import ArticleTargets, TargetCompiler, ValidatedGoldArticle
from training.v3_pretraining.time import TimeGoldAdapter


LOSS_CHANNELS = HEAD_TASKS + ("entity_typing_union",)
SHARED_OWNERS = frozenset({"document_context", "candidate_span", "exact_source_span",
                           "canonical_span", "primary_adapter"})
CONFIG_VERSION = "v3-harness-engineering-v3-unified-entity-no-priority"
PROVISIONAL_CONFIG_VERSION = "v3-harness-provisional-integration-v4-unified-entity-no-priority"
TRAINING_DEVICES = ("cpu", "mps")


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """모든 수치는 engineering default이며 dev/test 최적화값이 아니다."""

    run_id: str
    seed: int
    loss_weights: Mapping[str, float]
    task_learning_rates: Mapping[str, float]
    shared_learning_rate: float
    weight_decay: float
    gradient_accumulation_articles: int
    max_grad_norm: float
    negative_limit: int
    relation_negative_limit: int
    relation_sampling_seed: int
    relation_sampling_policy_version: str
    relation_about_lexical_policy: str
    pair_chunk_size: int
    primary_pair_limit: int
    input_schedule: str
    curriculum_stage: str
    checkpoint_save_policy: str
    selection_policy_version: str
    loss_reduction_contract_version: str
    gradient_clipping_contract_version: str
    config_version: str = CONFIG_VERSION
    negative_authority_path: str | None = None
    negative_authority_sha256: str | None = None

    def validate(self) -> None:
        policies = {
            CONFIG_VERSION: ("GOLD_TEACHER_FORCED_ENGINEERING",
                             "ALL_17_HEADS_ENGINEERING_SMOKE",
                             "SMOKE_ALWAYS_SAVE_NO_MODEL_SELECTION"),
            PROVISIONAL_CONFIG_VERSION: ("GOLD_TEACHER_FORCED_PROVISIONAL_TRAIN_ONLY",
                                         "ALL_17_HEADS_PROVISIONAL_INTEGRATION",
                                         "D8_MAX6_IMMUTABLE_PRE_EVAL_SELECTION"),
        }
        if (self.config_version not in policies or not self.run_id or
                (self.input_schedule, self.curriculum_stage,
                 self.checkpoint_save_policy) != policies[self.config_version]):
            raise ValueError("v3 harness run/schedule contract mismatch")
        if (self.selection_policy_version != SELECTION_POLICY_VERSION
                or self.loss_reduction_contract_version
                != LOSS_REDUCTION_CONTRACT_VERSION
                or self.gradient_clipping_contract_version
                != GRADIENT_CLIP_CONTRACT_VERSION
                or self.max_grad_norm != 1.0):
            raise ValueError("v3 D8 selection/reduction/clipping contract mismatch")
        if set(self.loss_weights) != set(LOSS_CHANNELS) or set(self.task_learning_rates) != set(HEAD_TASKS):
            raise ValueError("all current task LR and loss channels must be explicit")
        values = (*self.loss_weights.values(), *self.task_learning_rates.values(),
                  self.shared_learning_rate, self.max_grad_norm)
        if any(not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0
               for value in values):
            raise ValueError("loss weights, learning rates and clipping must be finite positive")
        if (not math.isfinite(self.weight_decay) or self.weight_decay < 0 or
                min(self.gradient_accumulation_articles, self.negative_limit,
                    self.relation_negative_limit, self.pair_chunk_size,
                    self.primary_pair_limit) <= 0):
            raise ValueError("invalid optimizer or bounded pair config")
        relation_policy = RelationSamplingPolicy(
            version=self.relation_sampling_policy_version,
            seed=self.relation_sampling_seed,
            negative_limit=self.relation_negative_limit,
            about_lexical_policy=self.relation_about_lexical_policy)
        relation_policy.validate()
        if (self.negative_authority_path is None) != (
                self.negative_authority_sha256 is None):
            raise ValueError("negative authority path and SHA must be set together")
        if (self.negative_authority_sha256 is not None
                and (len(self.negative_authority_sha256) != 64
                     or any(value not in "0123456789abcdef"
                            for value in self.negative_authority_sha256))):
            raise ValueError("negative authority SHA must be lowercase sha256")

    @classmethod
    def from_json(cls, path: str | Path) -> "HarnessConfig":
        import json
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if set(payload) != set(cls.__dataclass_fields__):
            raise ValueError("harness config requires exact fields")
        config = cls(**payload)
        config.validate()
        return config

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_negative_authority(config: HarnessConfig) -> ReviewedNegativeAuthority | None:
    """Frozen config가 지목한 train-only sidecar와 digest를 함께 검증한다."""
    config.validate()
    if config.negative_authority_path is None:
        return None
    path = Path(config.negative_authority_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    authority = ReviewedNegativeAuthority.from_json(path)
    if authority.sha256 != config.negative_authority_sha256:
        raise ValueError("configured negative authority SHA differs")
    return authority


def resolve_training_device(name: str) -> torch.device:
    """Resolve an explicit CPU/MPS request without a silent device fallback."""
    if name not in TRAINING_DEVICES:
        raise ValueError(f"training device must be one of {TRAINING_DEVICES}")
    if name == "mps" and (not torch.backends.mps.is_built() or
                           not torch.backends.mps.is_available()):
        raise RuntimeError(
            "MPS was explicitly requested but is unavailable in this process; "
            "run the preflight from a native local terminal with Metal access")
    return torch.device(name)


def fresh_full_core(config: HarnessConfig, *, device: str | torch.device = "cpu") -> V3Core:
    """legacy task checkpoint 접근 없이 현재 task와 shared module을 새로 만든다."""
    config.validate()
    seed_everything(config.seed)
    core = V3ArchitectureFactory.fresh_core(V3ArchitectureConfig(run_id=config.run_id,
                                                                 seed=config.seed))
    register_extraction_heads(core)
    register_entity_heads(core)
    register_time_heads(core)
    register_event_heads(core)
    register_attribution_heads(core)
    register_primary_head(core)
    core.require_full_model()
    if set(core._ready_tasks) != set(HEAD_TASKS):
        raise ValueError("fresh registry has missing or extra task")
    requested = resolve_training_device(str(device))
    return core.to(requested)


def load_pinned_backbone(core_or_config: V3Core | V3ArchitectureConfig, *,
                         device: str | torch.device = "cpu") -> KFDeBERTaBackbone:
    """로컬 pinned pretrained backbone만 연다; v2 task weight는 읽지 않는다."""
    cache = Path(__file__).resolve().parents[2] / "training/checkpoints/huggingface"
    config = core_or_config.config if isinstance(core_or_config, V3Core) else core_or_config
    backbone = KFDeBERTaBackbone.from_pretrained(config.backbone, cache_dir=cache)
    if any(parameter.requires_grad for parameter in backbone.parameters()):
        raise ValueError("pinned backbone became trainable")
    backbone.eval()
    return backbone.to(resolve_training_device(str(device)))


def parameter_manifest(core: V3Core) -> tuple[dict, ...]:
    return tuple({"name": name, "shape": list(parameter.shape), "dtype": str(parameter.dtype),
                  "owner": (name.split(".", 2)[1] if name.startswith("task_modules.") else
                            name.split(".", 1)[0])}
                 for name, parameter in core.named_parameters(remove_duplicate=False))


def target_contract_sha256(target: ArticleTargets) -> str:
    """exact 문자 좌표, eligible pair/Primary universe의 checkpoint 회귀 서명."""
    payload = {"article_version_id": target.article_version_id,
               "content_sha256": target.content_sha256,
               "spans": {name: [(row.owner_id, row.label, row.alignment.start,
                                  row.alignment.end, row.alignment.text)
                                 for row in rows] for name, rows in sorted(target.spans.items())},
               "pairs": {name: {"shape": row.shape, "left_ids": row.left_ids,
                                  "right_ids": row.right_ids,
                                  "positive_pairs": sorted(row.positive_pairs),
                                  "supervised_identity": (None if row.supervised_identity is None
                                                          else sorted(row.supervised_identity.items())),
                                  "negative_authority": row.negative_authority}
                         for name, row in sorted(target.pairs.items())},
               "unified_entity_mentions": [
                   (row.mention_id, row.alignment.start, row.alignment.end,
                    row.entity_type, row.gold_entity_id, row.origins, row.role_use_ids)
                   for row in target.entity_mentions],
               "assertors": [
                   (row.statement_id,
                    None if row.alignment is None else row.alignment.start,
                    None if row.alignment is None else row.alignment.end,
                    row.entity_id, row.source_mask, row.resolution_mask)
                   for row in target.assertors
               ],
               "primary": target.primary.nodes,
               "reviewed_span_decisions": [
                   (row.candidate_id, row.kind, row.owner_id, row.role, row.role_status,
                    row.alignment.start, row.alignment.end, row.verdict,
                    row.reason, row.responsibility, row.authority_id,
                    row.review_version, row.sidecar_sha256)
                   for row in target.reviewed_span_decisions
               ]}
    for rows in target.spans.values():
        for row in rows:
            if target.layout.reconstruct(row.alignment) != (
                    row.alignment.start, row.alignment.end, row.alignment.text):
                raise ValueError("target exact source offset changed")
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def build_optimizer(core: V3Core, backbone: nn.Module, config: HarnessConfig) -> torch.optim.Optimizer:
    """이름/shape 기준으로 모든 fresh parameter를 정확히 한 optimizer group에 넣는다."""
    core.assert_unique_parameters()
    groups: dict[str, dict] = {}
    for name, parameter in core.named_parameters(remove_duplicate=False):
        if not parameter.requires_grad:
            raise ValueError(f"fresh v3 parameter is unexpectedly frozen: {name}")
        owner = name.split(".", 2)[1] if name.startswith("task_modules.") else name.split(".", 1)[0]
        if owner not in SHARED_OWNERS and owner not in HEAD_TASKS:
            raise ValueError(f"unknown optimizer parameter owner: {owner}")
        lr = config.task_learning_rates[owner] if owner in HEAD_TASKS else config.shared_learning_rate
        group = groups.setdefault(owner, {"name": owner, "params": [], "param_names": [],
                                          "param_shapes": [], "lr": lr, "weight_decay": config.weight_decay})
        group["params"].append(parameter)
        group["param_names"].append(name)
        group["param_shapes"].append(list(parameter.shape))
    if set(groups) != SHARED_OWNERS | set(HEAD_TASKS):
        raise ValueError("optimizer lacks a shared or task module")
    optimizer = torch.optim.AdamW([groups[name] for name in sorted(groups)])
    audit_optimizer(core, backbone, optimizer)
    return optimizer


def audit_optimizer(core: V3Core, backbone: nn.Module,
                    optimizer: torch.optim.Optimizer) -> dict:
    """중복/누락/오분류 owner와 frozen backbone 유입을 즉시 실패시킨다."""
    names = list(core.named_parameters(remove_duplicate=False))
    expected = {id(parameter): (name, tuple(parameter.shape)) for name, parameter in names}
    if len(expected) != len(names):
        raise ValueError("fresh parameter has multiple names/owners")
    frozen_ids = {id(parameter) for parameter in backbone.parameters()}
    if any(parameter.requires_grad for parameter in backbone.parameters()):
        raise ValueError("frozen backbone has trainable parameter")
    found: list[int] = []
    for group in optimizer.param_groups:
        if len(group["params"]) != len(group.get("param_names", ())) or len(group["params"]) != len(group.get("param_shapes", ())):
            raise ValueError("optimizer group name/shape inventory differs")
        for parameter, name, shape in zip(group["params"], group["param_names"], group["param_shapes"]):
            ident = id(parameter)
            if ident in frozen_ids or ident not in expected or expected[ident] != (name, tuple(shape)):
                raise ValueError("optimizer has frozen/foreign/misnamed parameter")
            found.append(ident)
    if len(found) != len(set(found)) or set(found) != set(expected):
        raise ValueError("optimizer parameter is missing or duplicated")
    return {"trainable_parameter_tensors": len(found),
            "trainable_parameter_count": sum(parameter.numel() for _, parameter in names),
            "frozen_backbone_parameter_tensors": len(frozen_ids),
            "owner_count": len(optimizer.param_groups)}


@dataclass(frozen=True, slots=True)
class ArticleLosses:
    losses: Mapping[str, torch.Tensor]
    active: Mapping[str, bool]
    primary_scores: Mapping[str, float]
    final_event_ids: tuple[str, ...]
    article_id: str
    target_contract_sha256: str
    relation_sampling: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    # Read-only rehearsal/audit carrier. These counts are produced by the same
    # adapters as the losses and never participate in reduction or gradients.
    supervision_census: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArticleSelectionBundle:
    """One-backbone/one-DCE dev result containing losses and all B5 metrics."""

    article_losses: ArticleLosses
    ap_components: Mapping[str, Mapping[str, object]]
    primary: Mapping[str, int]
    full_universe_reports: Mapping[str, Mapping[str, object]]
    extraction_authority: ExtractionEvaluationAuthority
    extraction_score_rows: Mapping[str, tuple[Mapping[str, object], ...]]
    producer_calls: Mapping[str, int]
    sampling_applied: bool
    serving_pair_cap_applied: bool


@dataclass(frozen=True, slots=True)
class ArticleGoldOracleBundle:
    """One-backbone/one-DCE dev result without unresolved extraction authority.

    Pair/identity metrics and Primary use their compiler-defined full universes.
    Extraction remains a teacher-forced loss observation because its fixed
    evaluation-negative authority is a separate, still-unapproved contract.
    """

    article_losses: ArticleLosses
    full_universe_reports: Mapping[str, Mapping[str, object]]
    primary: Mapping[str, int]
    producer_calls: Mapping[str, int]
    sampling_applied: bool
    serving_pair_cap_applied: bool


class V3Trainer:
    """한 backbone forward와 한 shared DCE를 active task adapter가 공동 소비한다."""

    def __init__(self, core: V3Core, backbone: nn.Module, config: HarnessConfig,
                 *, tokenizer=None, discriminative_extraction: bool = True,
                 extraction_profile: str = "V3_WINDOW",
                 negative_authority: ReviewedNegativeAuthority | None = None,
                 frozen_feature_cache: RunLocalFrozenFeatureCache | None = None) -> None:
        config.validate()
        core.require_full_model()
        if core.config.run_id != config.run_id or core.config.seed != config.seed:
            raise ValueError("trainer core and config run/seed differ")
        self.core = core
        self.backbone = backbone
        core_devices = {parameter.device for parameter in core.parameters()}
        backbone_devices = {parameter.device for parameter in backbone.parameters()}
        if len(core_devices) != 1 or len(backbone_devices) != 1 or core_devices != backbone_devices:
            raise ValueError("v3 core and frozen backbone must share one execution device")
        self.device = next(iter(core_devices))
        self.frozen_feature_cache = frozen_feature_cache or RunLocalFrozenFeatureCache()
        self.features = FrozenBackboneFeatureBuilder(
            backbone, cache=self.frozen_feature_cache)
        self.config = config
        if tokenizer is None:
            tokenizer, digest, _ = load_pinned_fast_tokenizer()
        else:
            from models.v3_pretraining.architecture import PINNED_TOKENIZER_SHA256
            digest = PINNED_TOKENIZER_SHA256
        self.tokenizer_sha256 = digest
        configured_authority = load_negative_authority(config)
        if negative_authority is None:
            negative_authority = configured_authority
        elif configured_authority is not None and (
                negative_authority.sha256 != configured_authority.sha256):
            raise ValueError("injected and configured negative authority differ")
        self.compiler = TargetCompiler(
            LayoutBuilder(tokenizer, tokenizer_sha256=digest),
            negative_authority=negative_authority)
        self.collator = TargetCollator(pad_token_id=tokenizer.pad_token_id)
        # 통제 pilot에서 학습 목표 변경 효과만 분리하기 위한 스위치. 기본값은 수정된 계약.
        self.extraction = ExtractionGoldAdapter(
            core, discriminative=discriminative_extraction, profile=extraction_profile)
        self.entity = EntityGoldAdapter(core, negative_limit=config.negative_limit,
                                        chunk_size=config.pair_chunk_size,
                                        extraction_profile=extraction_profile)
        self.time = TimeGoldAdapter(core, negative_limit=config.negative_limit,
                                    chunk_size=config.pair_chunk_size)
        self.event = EventGoldAdapter(core, negative_limit=config.negative_limit,
                                      chunk_size=config.pair_chunk_size)
        relation_policy = RelationSamplingPolicy(
            version=config.relation_sampling_policy_version,
            seed=config.relation_sampling_seed,
            negative_limit=config.relation_negative_limit,
            about_lexical_policy=config.relation_about_lexical_policy)
        self.attribution = AttributionGoldAdapter(
            core, negative_limit=config.relation_negative_limit,
            chunk_size=config.pair_chunk_size, sampling_policy=relation_policy)
        self.primary = PrimaryGoldAdapter(core, max_pairs=config.primary_pair_limit)
        self.optimizer_steps = 0
        self.articles_seen = 0
        self.cumulative_clipped_count = 0
        self.relation_sampling_manifest: dict[str, Mapping[str, Mapping[str, object]]] = {}

    def article_losses(self, article: ValidatedGoldArticle) -> ArticleLosses:
        if article.split != "train":
            raise ValueError("only verified train Gold can enter v3 trainer")
        result = self._compute_article_losses(article, cache_scope="train")
        self.relation_sampling_manifest[result.article_id] = result.relation_sampling
        return result

    @torch.no_grad()
    def evaluation_losses(self, article: ValidatedGoldArticle, *,
                          cache_scope: str = "evaluation") -> ArticleLosses:
        """Evaluate an explicit dev/test article without changing optimizer state."""
        if article.split not in ("dev", "test"):
            raise ValueError("evaluation loss requires explicit dev/test Gold")
        self.core.eval()
        self.backbone.eval()
        return self._compute_article_losses(article, cache_scope=cache_scope)

    def _frozen_article_view(self, article: ValidatedGoldArticle,
                             target: ArticleTargets, *,
                             cache_scope: str) -> tuple[ArticleBatch, BackboneOutput]:
        """Build the source batch while memoizing only frozen backbone output."""
        windows = self.collator([target]).windows
        key = FrozenSourceViewKey.from_config(
            article.raw, windows, backbone=self.core.config.backbone,
            tokenizer_sha256=self.tokenizer_sha256,
            dtype=self.core.config.dtype, source_view="all")
        batch = windows.article_view(article.raw, view="all").to(self.device)
        return batch, self.features.build(
            batch, cache_key=key, scope=cache_scope)

    def frozen_feature_cache_stats(self) -> Mapping[str, object]:
        return self.frozen_feature_cache.snapshot()

    def release_frozen_feature_cache(self) -> None:
        self.frozen_feature_cache.clear()

    def _compute_article_losses(self, article: ValidatedGoldArticle, *,
                                cache_scope: str) -> ArticleLosses:
        target = self.compiler.compile(article)
        batch, frozen = self._frozen_article_view(
            article, target, cache_scope=cache_scope)
        downstream_started = perf_counter()
        with self.core.forward_shared(batch, frozen) as shared:
            extraction = self.extraction.loss(target, batch, frozen, shared)
            extraction.validate()
            entity = self.entity.loss(article, target, batch, frozen, shared)
            with self.event.prepare(article, target, batch, frozen, shared,
                                    include_relations=True) as features:
                time = self.time.loss(target, features.time)
                event = self.event.loss(target, features)
                final = finalize_cluster_features(features.member, features.closure)
                try:
                    attribution = self.attribution.loss(article, target, features, final, shared)
                    primary = self.primary.loss(article, target, features, final)
                    extras = features.time.extra_states
                    statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                                  for row in target.spans["semantic_proposer"] if row.label == "STATEMENT"}
                    assertors = {row.statement_id: extras["ASSERTOR:" + row.statement_id]
                                 for row in target.assertors if row.alignment is not None}
                    with torch.no_grad():
                        scores = self.core.task_modules["primary"](
                            final.view_for("PRIMARY"), statements, assertors, self.core.primary_adapter)
                        scalar_scores = {name: float(value) for name, value in scores.items()}
                    event_ids = tuple(row.local_id for row in features.closure.events)
                finally:
                    for consumer in tuple(sorted(final.pending_consumers)):
                        final.release(consumer)
        result = self._finalize_article_losses(
            article, target, extraction, entity, time, event, attribution, primary,
            scalar_scores, event_ids)
        self.features.record_downstream(
            cache_scope, (perf_counter() - downstream_started) * 1000)
        return result

    def _finalize_article_losses(self, article, target, extraction, entity, time,
                                 event, attribution, primary, scalar_scores,
                                 event_ids) -> ArticleLosses:
        losses = {**extraction.losses, **entity.losses, **time.losses,
                  "event_coreference": event.loss, **attribution.losses,
                  "primary": primary.loss}
        if set(losses) != set(LOSS_CHANNELS) or any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("v3 task loss inventory is incomplete or non-finite")
        # 양성이 없어도 확정된 음성 supervision이 있으면 그 channel은 활성이다.
        # supervision이 전부 없거나 IGNORE면 분모에서 빠진다.
        census_prefix = {
            "semantic_validity": "semantic_validity:",
            "trigger": "trigger:",
            "participant": "participant:",
            "entity_mention": "entity_mention:",
            "time_mention": "time_mention:",
        }
        active = {name: extraction.target_count[name] > 0
                  or any(key.startswith(census_prefix.get(name, "\0"))
                         and row["negative"] > 0
                         for key, row in extraction.supervision_census.items())
                  for name in extraction.losses}
        active.update({"entity_typing_union": bool(target.spans["entity_mention"]),
                       "entity_coreference": entity.coref_positive_pairs + entity.coref_sampled_negative_pairs > 0,
                       "time_normalization": time.normalized_supervised > 0,
                       "event_time": time.attachment_positive + time.attachment_negative_sampled > 0,
                       "event_coreference": event.positive_pairs + event.negative_pairs_sampled > 0,
                       "assertor_source": attribution.source_positive + attribution.source_absent > 0,
                       "assertor_entity": attribution.assertor_entity_positive + attribution.assertor_entity_negative_sampled > 0,
                       "about": attribution.about_positive + attribution.about_negative_sampled > 0,
                       "causes": attribution.causes_positive + attribution.causes_negative_sampled > 0,
                       "primary": primary.strict_pairs_sampled > 0})
        if set(active) != set(LOSS_CHANNELS):
            raise AssertionError("loss activity inventory differs from configured channels")
        target_sha256 = target_contract_sha256(target)
        relation_sampling = {
            lane: {**row, "target_contract_sha256": target_sha256}
            for lane, row in attribution.relation_sampling.items()}
        supervision_census = {
            "extraction": {
                "available": extraction.supervision_census,
                "negative_scored": dict(extraction.negative_count),
                "negative_unrepresentable": dict(
                    extraction.unrepresentable_negative_count),
            },
            "entity": {
                "candidates": entity.candidates,
                "entity_coreference_positive": entity.coref_positive_pairs,
                "entity_coreference_negative_sampled":
                    entity.coref_sampled_negative_pairs,
                "entity_coreference_pair_paths": {
                    path: entity.coref_pair_paths.count(path)
                    for path in ("MERGE", "HARD_KEEP", "RANDOM_KEEP")},
            },
            "time": {
                "normalization_supervised": time.normalized_supervised,
                "normalization_ignored": time.normalization_ignored,
                "event_time_positive": time.attachment_positive,
                "event_time_negative_sampled":
                    time.attachment_negative_sampled,
            },
            "event": {
                "event_coreference_positive": event.positive_pairs,
                "event_coreference_negative_sampled":
                    event.negative_pairs_sampled,
            },
            "attribution": {
                **attribution.supervision_census,
                "assertor_entity_positive":
                    attribution.assertor_entity_positive,
                "assertor_entity_negative_sampled":
                    attribution.assertor_entity_negative_sampled,
                "about_positive": attribution.about_positive,
                "about_negative_sampled": attribution.about_negative_sampled,
                "causes_positive": attribution.causes_positive,
                "causes_negative_sampled": attribution.causes_negative_sampled,
            },
            "primary": {
                "strict_pairs_available": primary.strict_pairs_available,
                "strict_pairs_sampled": primary.strict_pairs_sampled,
                "ties_ignored": primary.ties_ignored,
            },
        }
        return ArticleLosses(losses, active, scalar_scores, event_ids,
                             article.raw.article_id, target_sha256,
                             relation_sampling, supervision_census)

    def selection_input_fingerprint(
            self, article: ValidatedGoldArticle) -> Mapping[str, str]:
        """Return the model-independent dev identity checked before future training."""
        target = self.compiler.compile(article)
        return {
            "article_id": article.raw.article_id,
            "content_sha256": article.raw.content_sha256,
            "target_contract_sha256": target_contract_sha256(target),
        }

    def _selection_extraction_epoch_scores(
            self, target: ArticleTargets, batch, frozen, shared,
            authority: ExtractionEvaluationAuthority,
            *, retrieval: RetrievalBudget | None = None,
            endpoint_thresholds: Mapping[str, float] | None = None,
            selection_only_threshold_free: bool = False,
    ) -> Mapping[str, Mapping[tuple[str | None, int, int], float]]:
        """Run current extraction retrieval/heads against fixed E authority support."""
        authority.validate()
        layout = target.layout
        event_rows = {row.owner_id: row for row in target.spans["semantic_proposer"]
                      if row.label == "EVENT"}
        for component, rows in authority.component_rows.items():
            for row in rows:
                if row["end"] > len(layout.article.content):
                    raise ValueError(f"{component}: authority span exceeds source")
                owner_id = row["owner_id"]
                if owner_id is not None and owner_id not in event_rows:
                    raise ValueError(f"{component}: authority Event owner is unknown")
        scores: dict[str, dict[tuple[str | None, int, int], float]] = {
            component: {} for component in authority.component_rows}
        generic_components = {
            "EVENT": "E.EVENT", "STATEMENT": "E.STATEMENT",
            "TRIGGER": "E.TRIGGER", "ENTITY": "E.ENTITY", "TIME": "E.TIME",
        }
        context = source_decode_context(layout, shared, self.core)
        participant_retrieval = retrieval
        retrieval = retrieval or RetrievalBudget()
        endpoint_thresholds = endpoint_thresholds or {}
        try:
            for kind, component in generic_components.items():
                decoded = decode_source_spans(
                    kind=kind, layout=layout, batch=batch, backbone=frozen,
                    shared=shared, core=self.core, budget=DecodeBudget(),
                    context=context, retrieval=retrieval,
                    endpoint_threshold=endpoint_thresholds.get(kind),
                    selection_only_threshold_free=(selection_only_threshold_free and
                                                   kind == "TRIGGER"))
                for row in decoded.spans:
                    key = (None, row.start, row.end)
                    previous = scores[component].get(key)
                    if previous is None or row.extraction_score > previous:
                        scores[component][key] = row.extraction_score
            participant_budget = DecodeBudget(12, 12, 24, 16)
            event_states = [(event_id, event_row, event_source_state(
                    alignment=event_row.alignment, layout=layout, batch=batch,
                    backbone=frozen, shared=shared, core=self.core,
                    profile=retrieval.candidate_profile))
                    for event_id, event_row in sorted(event_rows.items())]
            # Share the serving B2 forward across roles without changing the
            # threshold-free role-specific candidate enumeration.
            participant_boundaries = (precompute_v23_participant_boundaries(
                layout=layout, batch=batch, shared=shared, core=self.core,
                events=[(event_id, row.alignment, state)
                        for event_id, row, state in event_states])
                if selection_only_threshold_free and
                retrieval.candidate_profile == "V23_BASELINE" and event_states else {})
            for event_id, event_row, state in event_states:
                # A per-Event cache reuses exact source features across three
                # roles while keeping owner-conditioned decisions separate.
                feature_cache = (RequestExactFeatureCache(
                    layout=layout, batch=batch, backbone=frozen, shared=shared,
                    core=self.core, max_rows_per_kind=4096)
                    if selection_only_threshold_free and
                    retrieval.candidate_profile == "V23_BASELINE" else None)
                try:
                    for role in ("ACTOR", "TARGET", "PLACE"):
                        component = "E.PARTICIPANT." + role
                        decoded = decode_source_spans(
                            kind="PARTICIPANT", layout=layout, batch=batch,
                            backbone=frozen, shared=shared, core=self.core,
                            budget=participant_budget,
                            event_alignment=event_row.alignment, role=role,
                            context=context, event_state=state,
                            retrieval=participant_retrieval,
                            participant_boundary=participant_boundaries.get(event_id),
                            exact_feature_cache=feature_cache,
                            endpoint_threshold=endpoint_thresholds.get("PARTICIPANT"),
                            selection_only_threshold_free=selection_only_threshold_free)
                        for row in decoded.spans:
                            key = (event_id, row.start, row.end)
                            old = scores[component].get(key)
                            if old is None or row.extraction_score > old:
                                scores[component][key] = row.extraction_score
                finally:
                    if feature_cache is not None:
                        feature_cache.close()
        finally:
            context.close()
        return scores

    @torch.no_grad()
    def phase1_extraction_evaluation(
            self, article: ValidatedGoldArticle,
            authority: ExtractionEvaluationAuthority, *,
            retrieval: RetrievalBudget) -> dict:
        """Score V23 raw candidates and only Phase 1 active oracle losses.

        Trigger and Participant skip the runtime endpoint gate only for raw-score
        selection. Greedy/Cartesian topology, width, and character correction remain.
        """
        if (article.split != "dev" or article.raw.article_id != authority.article_id
                or retrieval.candidate_profile != "V23_BASELINE"):
            raise ValueError("Phase 1 selection needs dev/V23 raw candidates")
        self.core.eval()
        self.backbone.eval()
        from training.v3_pretraining.staged import PhaseConfig
        phase = PhaseConfig.for_phase("extraction", self.config,
                                      source_profile="V23_BASELINE")
        target = self.compiler.compile(article)
        batch, frozen = self._frozen_article_view(
                article, target, cache_scope="phase1-selection")
        with self.core.forward_shared(batch, frozen) as shared:
            extraction = self.extraction.loss(target, batch, frozen, shared)
            extraction.validate()
            typing_loss, typing_candidates = self.entity.phase1_typing_union_loss(
                article, target, batch, frozen, shared)
            census_prefix = {
                "semantic_validity": "semantic_validity:",
                "trigger": "trigger:",
                "participant": "participant:",
                "entity_mention": "entity_mention:",
                "time_mention": "time_mention:",
            }
            active = {name: extraction.target_count[name] > 0
                      or any(key.startswith(census_prefix.get(name, "\0"))
                             and row["negative"] > 0
                             for key, row in extraction.supervision_census.items())
                      for name in extraction.losses}
            active["entity_typing_union"] = typing_candidates > 0
            if set(active) != set(phase.active_losses):
                raise AssertionError("Phase 1 dev loss channel inventory differs")
            losses = {**extraction.losses, "entity_typing_union": typing_loss}
            reduced = reduce_active_task_losses(
                [SimpleNamespace(losses=losses, active=active)],
                weights=self.config.loss_weights, channels=phase.active_losses)
            scores = self._selection_extraction_epoch_scores(
                target, batch, frozen, shared, authority, retrieval=retrieval,
                selection_only_threshold_free=True)
        components, rows = score_extraction_authority(authority, scores)
        return {"article_id": article.raw.article_id,
                "active_losses": sorted(name for name in phase.active_losses if active[name]),
                "dev_phase1_extraction_loss": float(reduced),
                "components": components, "score_rows": rows,
                "calibrated_thresholds_used": False}

    @torch.no_grad()
    def selection_evaluation(
            self, article: ValidatedGoldArticle,
            extraction_authority: ExtractionEvaluationAuthority,
    ) -> ArticleSelectionBundle:
        """Collect dev loss plus E/R/P from one frozen-backbone/shared-DCE forward."""
        if article.split not in ("dev", "test") or article.raw.article_id != extraction_authority.article_id:
            raise ValueError("selection evaluation requires matching explicit dev/test authority")
        extraction_authority.validate()
        self.core.eval()
        self.backbone.eval()
        target = self.compiler.compile(article)
        batch, frozen = self._frozen_article_view(
            article, target, cache_scope="selection")
        downstream_started = perf_counter()
        with self.core.forward_shared(batch, frozen) as shared:
            extraction = self.extraction.loss(target, batch, frozen, shared)
            extraction.validate()
            extraction_epoch_scores = self._selection_extraction_epoch_scores(
                target, batch, frozen, shared, extraction_authority)
            extraction_score_rows = bind_extraction_epoch_scores(
                extraction_authority, extraction_epoch_scores)
            entity = self.entity.loss(article, target, batch, frozen, shared)
            entity_reports = self.entity.evaluate_full_universe(
                article, target, batch, frozen, shared)
            with self.event.prepare(article, target, batch, frozen, shared,
                                    include_relations=True) as features:
                time = self.time.loss(target, features.time)
                time_report = self.time.evaluate_full_universe(
                    target, features.time, article_id=article.raw.article_id)
                event = self.event.loss(target, features)
                event_report = self.event.evaluate_full_universe(
                    target, features, article_id=article.raw.article_id)
                final = finalize_cluster_features(features.member, features.closure)
                try:
                    attribution = self.attribution.loss(
                        article, target, features, final, shared)
                    attribution_report = self.attribution.evaluate_full_universe(
                        article, target, features, final)
                    primary = self.primary.loss(article, target, features, final)
                    primary_report = self.primary.evaluate_full_universe(
                        article, target, features, final)
                    extras = features.time.extra_states
                    statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                                  for row in target.spans["semantic_proposer"]
                                  if row.label == "STATEMENT"}
                    assertors = {row.statement_id: extras["ASSERTOR:" + row.statement_id]
                                 for row in target.assertors if row.alignment is not None}
                    scores = self.core.task_modules["primary"](
                        final.view_for("PRIMARY"), statements, assertors,
                        self.core.primary_adapter)
                    scalar_scores = {name: float(value) for name, value in scores.items()}
                    event_ids = tuple(row.local_id for row in features.closure.events)
                    components = assemble_selection_components(
                        extraction=extraction_authority,
                        extraction_epoch_scores=extraction_epoch_scores,
                        entity_reports=entity_reports, time_report=time_report,
                        event_report=event_report,
                        attribution_report=attribution_report)
                finally:
                    for consumer in tuple(sorted(final.pending_consumers)):
                        final.release(consumer)
        losses = self._finalize_article_losses(
            article, target, extraction, entity, time, event, attribution, primary,
            scalar_scores, event_ids)
        result = ArticleSelectionBundle(
            losses, components, primary_report["metric"],
            {
                "R.EVENT_TIME": time_report,
                "R.ENTITY_COREFERENCE_MERGE": entity_reports["entity_coreference"],
                "R.EVENT_COREFERENCE_MERGE": event_report,
                "R.ASSERTED_BY": attribution_report["lanes"]["assertor_entity"],
                "R.ABOUT": attribution_report["lanes"]["about"],
                "R.CAUSES": attribution_report["lanes"]["causes"],
            }, extraction_authority, extraction_score_rows,
            {"backbone": 1, "shared_dce": 1,
             "extraction_retrieval": 1,
             "event_time": 1,
             "entity_coreference": 1, "event_coreference": 1,
             "asserted_by_about_causes": 1, "primary": 1},
            sampling_applied=False, serving_pair_cap_applied=False)
        self.features.record_downstream(
            "selection", (perf_counter() - downstream_started) * 1000)
        return result

    @torch.no_grad()
    def selection_evaluation_set(
            self, articles: Sequence[ValidatedGoldArticle],
            extraction_authorities: Mapping[str, ExtractionEvaluationAuthority],
    ) -> Mapping[str, object]:
        """Pool actual component scores across an explicit split without train sampling."""
        if (not articles or len({row.split for row in articles}) != 1
                or set(extraction_authorities) != {row.raw.article_id for row in articles}):
            raise ValueError("selection set needs one split and one authority per article")
        bundles = [self.selection_evaluation(
            row, extraction_authorities[row.raw.article_id]) for row in articles]
        extraction_components = {}
        for name in next(iter(extraction_authorities.values())).component_rows:
            rows = []
            for bundle in bundles:
                for item in bundle.extraction_score_rows[name]:
                    rows.append({**item,
                                 "pair_id": bundle.extraction_authority.article_id
                                 + ":" + str(item["pair_id"])})
            extraction_components[name] = average_precision_with_retrieval_misses(rows)
        relation_components = {}
        for name in bundles[0].full_universe_reports:
            pooled = aggregate_article_reports(
                [bundle.full_universe_reports[name] for bundle in bundles])
            relation_components[name] = ap_from_full_universe({
                **pooled, "sampling_applied": False,
                "serving_pair_cap_applied": False})
        primary = {name: sum(bundle.primary[name] for bundle in bundles)
                   for name in bundles[0].primary}
        dev_loss = reduce_active_task_losses(
            [bundle.article_losses for bundle in bundles],
            weights=self.config.loss_weights, channels=LOSS_CHANNELS)
        return {
            "ap_components": {**extraction_components, **relation_components},
            "primary": primary,
            "dev_total_multitask_loss": float(dev_loss),
            "article_count": len(bundles),
            "producer_calls": {
                "backbone": len(bundles), "shared_dce": len(bundles)},
            "sampling_applied": False, "serving_pair_cap_applied": False,
        }

    @torch.no_grad()
    def gold_oracle_evaluation(
            self, article: ValidatedGoldArticle) -> ArticleGoldOracleBundle:
        """Evaluate compiler-authorized R/P universes in one shared dev forward."""
        if article.split != "dev":
            raise ValueError("scale rehearsal oracle evaluation is dev-only")
        self.core.eval()
        self.backbone.eval()
        target = self.compiler.compile(article)
        batch, frozen = self._frozen_article_view(
            article, target, cache_scope="oracle")
        downstream_started = perf_counter()
        with self.core.forward_shared(batch, frozen) as shared:
            extraction = self.extraction.loss(target, batch, frozen, shared)
            extraction.validate()
            entity = self.entity.loss(article, target, batch, frozen, shared)
            entity_reports = self.entity.evaluate_full_universe(
                article, target, batch, frozen, shared)
            with self.event.prepare(article, target, batch, frozen, shared,
                                    include_relations=True) as features:
                time = self.time.loss(target, features.time)
                time_report = self.time.evaluate_full_universe(
                    target, features.time, article_id=article.raw.article_id)
                event = self.event.loss(target, features)
                event_report = self.event.evaluate_full_universe(
                    target, features, article_id=article.raw.article_id)
                final = finalize_cluster_features(features.member, features.closure)
                try:
                    attribution = self.attribution.loss(
                        article, target, features, final, shared)
                    attribution_report = self.attribution.evaluate_full_universe(
                        article, target, features, final)
                    primary = self.primary.loss(article, target, features, final)
                    primary_report = self.primary.evaluate_full_universe(
                        article, target, features, final)
                    extras = features.time.extra_states
                    statements = {
                        row.owner_id: extras["STATEMENT:" + row.owner_id]
                        for row in target.spans["semantic_proposer"]
                        if row.label == "STATEMENT"}
                    assertors = {
                        row.statement_id: extras["ASSERTOR:" + row.statement_id]
                        for row in target.assertors if row.alignment is not None}
                    scores = self.core.task_modules["primary"](
                        final.view_for("PRIMARY"), statements, assertors,
                        self.core.primary_adapter)
                    scalar_scores = {name: float(value)
                                     for name, value in scores.items()}
                    event_ids = tuple(row.local_id for row in features.closure.events)
                finally:
                    for consumer in tuple(sorted(final.pending_consumers)):
                        final.release(consumer)
        losses = self._finalize_article_losses(
            article, target, extraction, entity, time, event, attribution, primary,
            scalar_scores, event_ids)
        reports = {
            "R.EVENT_TIME": time_report,
            "R.ENTITY_COREFERENCE_MERGE": entity_reports["entity_coreference"],
            "R.EVENT_COREFERENCE_MERGE": event_report,
            "R.ASSERTED_BY": attribution_report["lanes"]["assertor_entity"],
            "R.ABOUT": attribution_report["lanes"]["about"],
            "R.CAUSES": attribution_report["lanes"]["causes"],
        }
        result = ArticleGoldOracleBundle(
            losses, reports, primary_report["metric"],
            {"backbone": 1, "shared_dce": 1,
             "event_time": 1, "entity_coreference": 1,
             "event_coreference": 1, "asserted_by_about_causes": 1,
             "primary": 1},
            sampling_applied=False, serving_pair_cap_applied=False)
        self.features.record_downstream(
            "oracle", (perf_counter() - downstream_started) * 1000)
        return result

    @torch.no_grad()
    def gold_oracle_evaluation_set(
            self, articles: Sequence[ValidatedGoldArticle]) -> Mapping[str, object]:
        """Pool dev R/P metrics while keeping extraction authority unresolved."""
        if (not articles or any(row.split != "dev" for row in articles)
                or len({row.raw.article_id for row in articles}) != len(articles)):
            raise ValueError("oracle evaluation set needs unique explicit dev articles")
        bundles = [self.gold_oracle_evaluation(row) for row in articles]
        reports = {
            name: aggregate_article_reports(
                [bundle.full_universe_reports[name] for bundle in bundles])
            for name in bundles[0].full_universe_reports}
        components = {name: ap_from_full_universe({
            **report, "sampling_applied": False,
            "serving_pair_cap_applied": False})
                      for name, report in reports.items()}
        primary = {name: sum(int(bundle.primary[name]) for bundle in bundles)
                   for name in bundles[0].primary}
        dev_loss = reduce_active_task_losses(
            [bundle.article_losses for bundle in bundles],
            weights=self.config.loss_weights, channels=LOSS_CHANNELS)
        return {
            "mode": "GOLD_ORACLE_FULL_UNIVERSE_NO_EXTRACTION_EVAL_AUTHORITY",
            "article_count": len(bundles),
            "dev_total_multitask_loss": float(dev_loss),
            "relation_identity_components": components,
            "relation_identity_reports": reports,
            "primary": primary,
            "extraction_metric_status": "BLOCKED_BY_UNAPPROVED_FIXED_EVAL_AUTHORITY",
            "extraction_teacher_forced_losses_only": True,
            "sampling_applied": False,
            "serving_pair_cap_applied": False,
            "producer_calls": {"backbone": len(bundles),
                               "shared_dce": len(bundles)},
            "article_losses": [bundle.article_losses for bundle in bundles],
        }

    @torch.no_grad()
    def full_relation_evaluation(self, article: ValidatedGoldArticle) -> Mapping[str, object]:
        """Future dev/test caller: Gold relation universe 전체를 sampling 없이 score한다."""
        if article.split not in ("dev", "test"):
            raise ValueError("full relation evaluation requires explicit dev/test Gold")
        self.core.eval()
        self.backbone.eval()
        target = self.compiler.compile(article)
        batch, frozen = self._frozen_article_view(
            article, target, cache_scope="relation_evaluation")
        downstream_started = perf_counter()
        with self.core.forward_shared(batch, frozen) as shared:
            with self.event.prepare(article, target, batch, frozen, shared,
                                    include_relations=True) as features:
                final = finalize_cluster_features(features.member, features.closure)
                try:
                    report = self.attribution.evaluate_full_universe(
                        article, target, features, final)
                    result = {**report,
                              "target_contract_sha256": target_contract_sha256(target),
                              "article_version_id": article.raw.article_version_id,
                              "content_sha256": article.raw.content_sha256}
                finally:
                    for consumer in tuple(sorted(final.pending_consumers)):
                        final.release(consumer)
        self.features.record_downstream(
            "relation_evaluation", (perf_counter() - downstream_started) * 1000)
        return result

    def relation_training_metadata(self) -> dict[str, object]:
        """Run/checkpoint writer가 동일 policy와 article support를 직렬화한다."""
        return build_relation_training_metadata(
            self.attribution.sampling_policy, self.relation_sampling_manifest)

    @torch.no_grad()
    def full_relation_evaluation_set(
            self, articles: Sequence[ValidatedGoldArticle]) -> Mapping[str, object]:
        """Explicit dev/test sequence의 pooled와 article-macro relation metric entry."""
        if (not articles or any(row.split not in ("dev", "test") for row in articles)
                or len({row.split for row in articles}) != 1
                or len({row.raw.article_id for row in articles}) != len(articles)):
            raise ValueError("relation evaluation set needs one explicit split and unique articles")
        article_reports = [self.full_relation_evaluation(row) for row in articles]
        return {
            "mode": "GOLD_ENDPOINT_IDENTITY_FULL_UNIVERSE_SET",
            "split": articles[0].split,
            "article_count": len(articles),
            "sampling_applied": False,
            "serving_pair_cap_applied": False,
            "lanes": {
                lane: aggregate_article_reports(
                    [report["lanes"][lane] for report in article_reports])
                for lane in ("assertor_entity", "about", "causes")},
            "articles": article_reports,
        }

    def article_activity(self, article: ValidatedGoldArticle) -> Mapping[str, bool]:
        """Derive deterministic masks from Gold targets without a model forward."""
        if article.split != "train":
            raise ValueError("training activity preflight requires train Gold")
        target = self.compiler.compile(article)
        extraction = {
            name: len(target.spans[name]) > 0 for name in
            ("semantic_proposer", "semantic_boundary", "semantic_validity", "trigger",
             "participant", "entity_mention", "time_mention")
        }
        coverage = target.coverage()
        for name in ("participant", "entity_mention", "time_mention"):
            extraction[name] = extraction[name] or coverage[name]["negative"] > 0
        extraction["statement_type"] = any(row.task == "statement_type"
                                              for row in target.classes)
        native_candidates = len(target.spans["entity_mention"])
        active = {
            **extraction,
            "entity_typing_union": native_candidates > 0,
            "entity_coreference": target.pairs["entity_coreference"].counts()["positive"] +
                                  target.pairs["entity_coreference"].counts()["negative"] > 0,
            "time_normalization": any(row.normalization_mask == "SUPERVISE"
                                        for row in target.time_normalization),
            "event_time": target.pairs["event_time"].total_count > 0,
            "event_coreference": target.pairs["event_coreference"].total_count > 0,
            "assertor_source": bool(target.assertors),
            "assertor_entity": target.pairs["assertor_entity"].total_count > 0,
            "about": target.pairs["about"].total_count > 0,
            "causes": target.pairs["causes"].total_count > 0,
            "primary": target.primary.counts()["positive"] > 0,
        }
        if set(active) != set(LOSS_CHANNELS):
            raise AssertionError("static loss activity inventory differs")
        return active

    def combined_loss(self, articles: Sequence[ArticleLosses]) -> torch.Tensor:
        """각 head의 pair 평균 뒤 활성 article 평균; masked article은 분모에서 뺀다."""
        return reduce_active_task_losses(
            articles, weights=self.config.loss_weights, channels=LOSS_CHANNELS)

    def step(self, articles: Sequence[ValidatedGoldArticle],
             optimizer: torch.optim.Optimizer, *, max_steps: int = 1) -> dict:
        """bounded smoke: 불완전 마지막 accumulation group도 정확히 한 번 step한다."""
        if max_steps != 1:
            raise ValueError("step 13 permits one optimizer smoke step only")
        if not articles or len(articles) > self.config.gradient_accumulation_articles:
            raise ValueError("step 13 smoke requires one bounded accumulation group")
        return self.train_groups(articles, optimizer)[0]

    def train_groups(self, articles: Sequence[ValidatedGoldArticle],
                     optimizer: torch.optim.Optimizer) -> tuple[dict, ...]:
        """기사별 Gold loss를 accumulation group으로 묶고 마지막 부분 group도 step한다.

        CLI의 본학습 진입은 별도 승인 전까지 막혀 있다. 이 함수는 검증된 train
        기사만 받고 checkpoint/run 정책은 호출자가 소유한다.
        """
        if not articles:
            raise ValueError("training group input cannot be empty")
        audit_optimizer(self.core, self.backbone, optimizer)
        self.core.train()
        self.backbone.eval()
        optimizer.zero_grad(set_to_none=True)
        group: list[ArticleLosses] = []
        results = []
        for article in articles:
            if article.split != "train":
                raise ValueError("only train articles are allowed")
            group.append(self.article_losses(article))
            self.articles_seen += 1
            if len(group) == self.config.gradient_accumulation_articles:
                results.append(self._finish_group(group, optimizer))
                group = []
        if group:
            results.append(self._finish_group(group, optimizer))
        return tuple(results)

    def _finish_group(self, group: list[ArticleLosses], optimizer: torch.optim.Optimizer) -> dict:
        loss = self.combined_loss(group)
        loss.backward()
        gradients = {}
        for name, parameter in self.core.named_parameters():
            if parameter.grad is not None and not torch.isfinite(parameter.grad).all():
                raise ValueError(f"non-finite gradient: {name}")
            owner = name.split(".", 2)[1] if name.startswith("task_modules.") else name.split(".", 1)[0]
            if parameter.grad is not None and parameter.grad.abs().sum().item() > 0:
                gradients[owner] = gradients.get(owner, 0) + 1
        active_heads = {name for row in group for name, yes in row.active.items()
                        if yes and name != "entity_typing_union"}
        if active_heads - set(gradients):
            raise ValueError(f"active v3 task has no gradient: {sorted(active_heads - set(gradients))}")
        if any(parameter.grad is not None for parameter in self.backbone.parameters()):
            raise ValueError("frozen backbone received gradient")
        clip = clip_gradients_with_observability(
            self.core.named_parameters(), max_grad_norm=self.config.max_grad_norm,
            cumulative_clipped_count=self.cumulative_clipped_count,
            expected_owners=tuple(self.core.task_modules) + tuple(SHARED_OWNERS))
        self.cumulative_clipped_count = clip["cumulative_clipped_count"]
        before = {name: parameter.detach().clone() for name, parameter in self.core.named_parameters()}
        optimizer.step()
        changed = {name for name, parameter in self.core.named_parameters()
                   if not torch.equal(before[name], parameter.detach())}
        if not changed:
            raise ValueError("optimizer smoke step changed no fresh parameter")
        self.optimizer_steps += 1
        optimizer.zero_grad(set_to_none=True)
        return {"loss": float(loss.detach()), "active_channels": sorted({name for row in group for name, yes in row.active.items() if yes}),
                "gradient_owner_counts": gradients, "changed_parameter_tensors": len(changed),
                "changed_owners": sorted({name.split(".", 2)[1] if name.startswith("task_modules.")
                                          else name.split(".", 1)[0] for name in changed}),
                "articles": [row.article_id for row in group], "optimizer_steps": self.optimizer_steps,
                "articles_seen": self.articles_seen,
                "gradient_clip_observability": clip,
                "loss_reduction_contract_version": LOSS_REDUCTION_CONTRACT_VERSION}

    @torch.no_grad()
    def eval_fingerprint(self, article: ValidatedGoldArticle) -> dict:
        self.core.eval()
        self.backbone.eval()
        result = self.article_losses(article)
        return {"article_id": result.article_id,
                "losses": {name: float(value) for name, value in result.losses.items()},
                "primary_scores": dict(result.primary_scores),
                "final_event_ids": list(result.final_event_ids),
                "target_contract_sha256": result.target_contract_sha256}
