"""article-relative importance ordinal target를 shared Primary scalar loss로 연결한다."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import random
from typing import Sequence

import torch
from torch.nn import functional as F

from models.v3_pretraining.architecture import V3Core
from runtime.v3_pretraining.event_features import FinalClusterFeatureLease
from training.v3_pretraining.attribution import gold_cluster_local_ids
from training.v3_pretraining.event import EventGoldFeatures
from training.v3_pretraining.targets import ArticleTargets, RankTarget, ValidatedGoldArticle
from training.v3_pretraining.selection_contract import primary_strict_ordering_metric


@dataclass(frozen=True, slots=True)
class PrimaryLossResult:
    loss: torch.Tensor
    strict_pairs_available: int
    strict_pairs_sampled: int
    cross_kind_pairs_sampled: int
    ties_ignored: int
    event_candidates: int
    statement_candidates: int


def sample_strict_pairs(target: ArticleTargets, *, max_pairs: int,
                        seed: int) -> tuple[RankTarget, ...]:
    """동순위를 배제하고 deterministic cross-kind 비교를 남기는 article sampler."""
    if max_pairs <= 0:
        raise ValueError("Primary strict pair budget must be positive")
    strict = [row for row in target.primary if row.loss_mask == "SUPERVISE"]
    if len(strict) <= max_pairs:
        return tuple(strict)
    stable = int(sha256(f"{seed}:{target.content_sha256}:primary".encode()).hexdigest()[:16], 16)
    rng = random.Random(stable)
    cross = [row for row in strict if row.left_id[0] != row.right_id[0]]
    reserved = rng.sample(cross, min(len(cross), max(1, max_pairs // 2))) if cross else []
    reserved_keys = {(row.left_id, row.right_id) for row in reserved}
    remaining = [row for row in strict if (row.left_id, row.right_id) not in reserved_keys]
    chosen = reserved + rng.sample(remaining, max_pairs - len(reserved))
    return tuple(sorted(chosen, key=lambda row: (row.left_id, row.right_id)))


def pairwise_rank_loss(left_score: torch.Tensor, right_score: torch.Tensor,
                       *, left_preferred: bool) -> torch.Tensor:
    """순위 방향만 사용한다; rank 숫자 간격은 입력되지 않는다."""
    difference = left_score - right_score
    return F.softplus(-difference if left_preferred else difference)


class PrimaryGoldAdapter:
    def __init__(self, core: V3Core, *, max_pairs: int = 4096) -> None:
        if "primary" in core.unimplemented_tasks:
            raise ValueError("Primary head is not registered")
        if max_pairs <= 0:
            raise ValueError("Primary pair budget must be positive")
        self.core = core
        self.max_pairs = max_pairs

    def loss(self, article: ValidatedGoldArticle, target: ArticleTargets,
             features: EventGoldFeatures, final: FinalClusterFeatureLease) -> PrimaryLossResult:
        if (article.split not in ("train", "dev", "test") or target.article_version_id != final.article_version_id
                or target.content_sha256 != final.content_sha256
                or features.time.closed or features.time.extra_states is None
                or features.closure.source_mode != "GOLD_ORACLE"
                or final.source_mode != "GOLD_ORACLE"):
            raise ValueError("Primary loss needs matching live oracle final features")
        view = final.view_for("PRIMARY")
        extras = features.time.extra_states
        statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                      for row in target.spans["semantic_proposer"] if row.label == "STATEMENT"}
        assertors = {row.statement_id: extras["ASSERTOR:" + row.statement_id]
                     for row in target.assertors if row.alignment is not None}
        scores = self.core.task_modules["primary"](
            view, statements, assertors, self.core.primary_adapter)
        cluster_map = gold_cluster_local_ids(article, features)
        mapped = {"E:" + gold_id: "E:" + local_id for gold_id, local_id in cluster_map.items()}
        mapped.update({"S:" + sid: "S:" + sid for sid in statements})
        if set(mapped) != {node for node, _rank in target.primary.nodes} or set(scores) != set(mapped.values()):
            raise ValueError("Primary ranking inventory differs from final proposition universe")
        sampled = sample_strict_pairs(target, max_pairs=self.max_pairs,
                                      seed=self.core.config.seed)
        pair_losses = []
        for row in sampled:
            pair_losses.append(pairwise_rank_loss(scores[mapped[row.left_id]],
                                                  scores[mapped[row.right_id]],
                                                  left_preferred=row.left_preferred))
        if pair_losses:
            loss = torch.stack(pair_losses).mean()
        elif scores:
            loss = torch.stack(tuple(scores.values())).sum() * 0
        else:
            loss = self.core.task_modules["primary"].shared_scalar.weight.sum() * 0
        if not torch.isfinite(loss):
            raise ValueError("Primary ordinal loss is non-finite")
        counts = target.primary.counts()
        return PrimaryLossResult(loss, counts["positive"], len(sampled),
                                 sum(row.left_id[0] != row.right_id[0] for row in sampled),
                                 counts["ignored"], len(view.cluster_ids), len(statements))

    @torch.no_grad()
    def evaluate_full_universe(self, article: ValidatedGoldArticle,
                               target: ArticleTargets,
                               features: EventGoldFeatures,
                               final: FinalClusterFeatureLease) -> dict[str, object]:
        """Score every proposition once and evaluate all strict non-tie Gold pairs."""
        if self.core.training or article.split not in ("dev", "test"):
            raise ValueError("Primary selection evaluation requires eval-mode dev/test Gold")
        view = final.view_for("PRIMARY")
        extras = features.time.extra_states
        if extras is None:
            raise RuntimeError("Primary selection evaluation lost exact Statement states")
        statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                      for row in target.spans["semantic_proposer"]
                      if row.label == "STATEMENT"}
        assertors = {row.statement_id: extras["ASSERTOR:" + row.statement_id]
                     for row in target.assertors if row.alignment is not None}
        raw_scores = self.core.task_modules["primary"](
            view, statements, assertors, self.core.primary_adapter)
        cluster_map = gold_cluster_local_ids(article, features)
        mapped = {"E:" + gold_id: "E:" + local_id
                  for gold_id, local_id in cluster_map.items()}
        mapped.update({"S:" + sid: "S:" + sid for sid in statements})
        scores = {gold_id: float(raw_scores[local_id])
                  for gold_id, local_id in mapped.items()}
        pairs = tuple((row.left_id, row.right_id, row.left_preferred)
                      for row in target.primary)
        metric = primary_strict_ordering_metric(pairs, scores)
        return {
            "metric": metric,
            "score_inventory": scores,
            "strict_pair_count": target.primary.counts()["positive"],
            "ties_ignored": target.primary.counts()["ignored"],
            "sampling_applied": False,
            "serving_pair_cap_applied": False,
        }


def mean_article_primary_loss(results: Sequence[PrimaryLossResult]) -> torch.Tensor:
    """각 기사 valid strict pair 평균을 한 번씩 반영한다."""
    if not results:
        raise ValueError("at least one article result is required")
    valid = [row.loss for row in results if row.strict_pairs_sampled]
    return torch.stack(valid).mean() if valid else sum(row.loss for row in results)
