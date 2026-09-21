"""검증된 train Gold만 소비하는 v3 fresh-init 학습 step.

Pinned backbone은 외부의 frozen producer다. 하나의 DCE/shared feature 경로에서
19개 task loss를 결합하며, scalar loss 외의 feature는 요청 scope를 벗어나지 않는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from typing import Mapping, Sequence

import numpy as np
import torch
from torch import nn

from models.backbone import KFDeBERTaBackbone
from models.v3_pretraining.architecture import V3ArchitectureConfig, V3ArchitectureFactory, V3Core
from models.v3_pretraining.attribution_heads import register_attribution_heads
from models.v3_pretraining.entity_heads import register_entity_heads
from models.v3_pretraining.event_heads import register_event_heads
from models.v3_pretraining.extraction_heads import register_extraction_heads
from models.v3_pretraining.frozen_features import FrozenBackboneFeatureBuilder
from models.v3_pretraining.primary_head import register_primary_head
from models.v3_pretraining.task_contract import HEAD_TASKS
from models.v3_pretraining.time_heads import register_time_heads
from runtime.v3_pretraining.event_features import finalize_cluster_features
from runtime.v3_pretraining.source_layout import LayoutBuilder
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer
from training.v3_pretraining.attribution import AttributionGoldAdapter
from training.v3_pretraining.collator import TargetCollator
from training.v3_pretraining.entity import EntityGoldAdapter
from training.v3_pretraining.event import EventGoldAdapter
from training.v3_pretraining.extraction import ExtractionGoldAdapter
from training.v3_pretraining.primary import PrimaryGoldAdapter
from training.v3_pretraining.targets import ArticleTargets, TargetCompiler, ValidatedGoldArticle
from training.v3_pretraining.time import TimeGoldAdapter


LOSS_CHANNELS = HEAD_TASKS + ("entity_typing_union",)
SHARED_OWNERS = frozenset({"document_context", "candidate_span", "exact_source_span",
                           "canonical_span", "primary_adapter"})
CONFIG_VERSION = "v3-harness-engineering-v1"


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
    pair_chunk_size: int
    primary_pair_limit: int
    input_schedule: str
    curriculum_stage: str
    checkpoint_save_policy: str
    config_version: str = CONFIG_VERSION

    def validate(self) -> None:
        if (self.config_version != CONFIG_VERSION or not self.run_id or
                self.input_schedule != "GOLD_TEACHER_FORCED_ENGINEERING" or
                self.curriculum_stage != "ALL_19_HEADS_ENGINEERING_SMOKE" or
                self.checkpoint_save_policy != "SMOKE_ALWAYS_SAVE_NO_MODEL_SELECTION"):
            raise ValueError("v3 harness run/schedule contract mismatch")
        if set(self.loss_weights) != set(LOSS_CHANNELS) or set(self.task_learning_rates) != set(HEAD_TASKS):
            raise ValueError("all 19 task LR and 20 loss channels must be explicit")
        values = (*self.loss_weights.values(), *self.task_learning_rates.values(),
                  self.shared_learning_rate, self.max_grad_norm)
        if any(not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0
               for value in values):
            raise ValueError("loss weights, learning rates and clipping must be finite positive")
        if (not math.isfinite(self.weight_decay) or self.weight_decay < 0 or
                min(self.gradient_accumulation_articles, self.negative_limit,
                    self.pair_chunk_size, self.primary_pair_limit) <= 0):
            raise ValueError("invalid optimizer or bounded pair config")

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


def fresh_full_core(config: HarnessConfig) -> V3Core:
    """legacy task checkpoint 접근 없이 19개 task와 shared module을 새로 만든다."""
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
    return core


def load_pinned_backbone(core_or_config: V3Core | V3ArchitectureConfig) -> KFDeBERTaBackbone:
    """로컬 pinned pretrained backbone만 연다; v2 task weight는 읽지 않는다."""
    cache = Path(__file__).resolve().parents[2] / "training/checkpoints/huggingface"
    config = core_or_config.config if isinstance(core_or_config, V3Core) else core_or_config
    backbone = KFDeBERTaBackbone.from_pretrained(config.backbone, cache_dir=cache)
    if any(parameter.requires_grad for parameter in backbone.parameters()):
        raise ValueError("pinned backbone became trainable")
    backbone.eval()
    return backbone


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
                                  "positive_pairs": sorted(row.positive_pairs)}
                         for name, row in sorted(target.pairs.items())},
               "primary": target.primary.nodes}
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


class V3Trainer:
    """한 backbone forward와 한 shared DCE를 19 task adapter가 공동 소비한다."""

    def __init__(self, core: V3Core, backbone: nn.Module, config: HarnessConfig,
                 *, tokenizer=None) -> None:
        config.validate()
        core.require_full_model()
        if core.config.run_id != config.run_id or core.config.seed != config.seed:
            raise ValueError("trainer core and config run/seed differ")
        self.core = core
        self.backbone = backbone
        self.features = FrozenBackboneFeatureBuilder(backbone)
        self.config = config
        if tokenizer is None:
            tokenizer, digest, _ = load_pinned_fast_tokenizer()
        else:
            from models.v3_pretraining.architecture import PINNED_TOKENIZER_SHA256
            digest = PINNED_TOKENIZER_SHA256
        self.compiler = TargetCompiler(LayoutBuilder(tokenizer, tokenizer_sha256=digest))
        self.collator = TargetCollator(pad_token_id=tokenizer.pad_token_id)
        self.extraction = ExtractionGoldAdapter(core)
        self.entity = EntityGoldAdapter(core, negative_limit=config.negative_limit,
                                        chunk_size=config.pair_chunk_size)
        self.time = TimeGoldAdapter(core, negative_limit=config.negative_limit,
                                    chunk_size=config.pair_chunk_size)
        self.event = EventGoldAdapter(core, negative_limit=config.negative_limit,
                                      chunk_size=config.pair_chunk_size)
        self.attribution = AttributionGoldAdapter(core, negative_limit=config.negative_limit,
                                                  chunk_size=config.pair_chunk_size)
        self.primary = PrimaryGoldAdapter(core, max_pairs=config.primary_pair_limit)
        self.optimizer_steps = 0
        self.articles_seen = 0

    def article_losses(self, article: ValidatedGoldArticle) -> ArticleLosses:
        if article.split != "train":
            raise ValueError("only verified train Gold can enter v3 trainer")
        target = self.compiler.compile(article)
        batch = self.collator([target]).windows.article_view(article.raw, view="all")
        frozen = self.features.build(batch)
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
        losses = {**extraction.losses, **entity.losses, **time.losses,
                  "event_coreference": event.loss, **attribution.losses,
                  "primary": primary.loss}
        if set(losses) != set(LOSS_CHANNELS) or any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("v3 task loss inventory is incomplete or non-finite")
        active = {name: extraction.target_count[name] > 0 for name in extraction.losses}
        active.update({"entity_priority": entity.candidates > 0,
                       "entity_typing_union": entity.candidates > 0,
                       "entity_coreference": entity.coref_positive_pairs + entity.coref_sampled_negative_pairs > 0,
                       "role_entity": entity.role_positive_pairs + entity.role_sampled_negative_pairs > 0,
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
        return ArticleLosses(losses, active, scalar_scores, event_ids,
                             article.raw.article_id, target_contract_sha256(target))

    def combined_loss(self, articles: Sequence[ArticleLosses]) -> torch.Tensor:
        """각 head의 pair 평균 뒤 활성 article 평균; masked article은 분모에서 뺀다."""
        if not articles:
            raise ValueError("accumulation group cannot be empty")
        total = None
        for name in LOSS_CHANNELS:
            active = [row.losses[name] for row in articles if row.active[name]]
            if not active:
                continue
            component = self.config.loss_weights[name] * torch.stack(active).mean()
            total = component if total is None else total + component
        if total is None:
            total = sum(row.losses["semantic_proposer"] * 0 for row in articles)
        if not torch.isfinite(total):
            raise ValueError("combined v3 loss is non-finite")
        return total

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
        torch.nn.utils.clip_grad_norm_(self.core.parameters(), self.config.max_grad_norm,
                                       error_if_nonfinite=True)
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
                "articles_seen": self.articles_seen}

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
