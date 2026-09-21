"""검증된 train Gold의 Assertor/ASSERTED_BY/ABOUT/CAUSES target 실행 adapter.

Gold ID는 label/remap에만 사용한다. final local Event/Entity tensor와 기존
direct-gather source state를 소비하며 pair universe를 확장하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch.nn import functional as F

from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from runtime.v3_pretraining.attribution_scoring import bridge_token_states
from runtime.v3_pretraining.event_features import FinalClusterFeatureLease
from training.v3_pretraining.event import EventGoldFeatures
from training.v3_pretraining.targets import ArticleTargets, ValidatedGoldArticle


def gold_cluster_local_ids(article: ValidatedGoldArticle,
                           features: EventGoldFeatures) -> dict[str, str]:
    """Gold cluster membership을 final local identity로 검증하며 mapping한다."""
    result = {}
    for cluster in article.annotations["event_clusters"]:
        local = {features.closure.member_to_cluster[mid] for mid in cluster["event_ids"]}
        if len(local) != 1:
            raise ValueError("Gold EventCluster split across final identity")
        result[cluster["cluster_id"]] = next(iter(local))
    if len(set(result.values())) != len(result):
        raise ValueError("distinct Gold EventClusters merged in final identity")
    return result


def gold_entity_local_ids(article: ValidatedGoldArticle,
                          features: EventGoldFeatures) -> dict[str, str]:
    candidate_gold = features.entity_oracle.gold_entity_by_candidate
    result: dict[str, str] = {}
    for candidate_id, gold_id in candidate_gold.items():
        local_id = features.entity_oracle.closure.candidate_to_entity[candidate_id]
        if gold_id in result and result[gold_id] != local_id:
            raise ValueError("Gold Entity cluster split across final identity")
        result[gold_id] = local_id
    expected = {row["entity_id"] for row in article.annotations["entity_clusters"]}
    if set(result) != expected or len(set(result.values())) != len(result):
        raise ValueError("Gold Entity identity not represented one-to-one")
    return result


@dataclass(frozen=True, slots=True)
class AttributionLossResult:
    losses: dict[str, torch.Tensor]
    source_positive: int
    source_absent: int
    assertor_entity_positive: int
    assertor_entity_negative_sampled: int
    about_positive: int
    about_negative_sampled: int
    causes_positive: int
    causes_negative_sampled: int
    unresolved_span_only: int


class AttributionGoldAdapter:
    def __init__(self, core: V3Core, *, negative_limit: int = 128,
                 chunk_size: int = 128) -> None:
        if any(name in core.unimplemented_tasks for name in (
                "assertor_source", "assertor_entity", "about", "causes")):
            raise ValueError("stage 9 heads are not registered")
        if min(negative_limit, chunk_size) <= 0:
            raise ValueError("attribution pair bounds must be positive")
        self.core = core
        self.negative_limit = negative_limit
        self.chunk_size = chunk_size

    def loss(self, article: ValidatedGoldArticle, target: ArticleTargets,
             features: EventGoldFeatures, final: FinalClusterFeatureLease,
             shared: SharedForwardLease) -> AttributionLossResult:
        if (article.split != "train" or target.article_version_id != final.article_version_id
                or target.content_sha256 != final.content_sha256
                or features.closure.source_mode != "GOLD_ORACLE" or final.source_mode != "GOLD_ORACLE"
                or features.time.closed or features.time.extra_states is None
                or features.time.extra_residuals is None or features.time.extra_link_logits is None):
            raise ValueError("attribution loss needs matching live oracle representations")
        view = final.view_for("RELATION")
        extras = features.time.extra_states
        residuals = features.time.extra_residuals
        links = features.time.extra_link_logits
        doc = view.document_state
        zero = doc.sum() * 0
        statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                      for row in target.spans["semantic_proposer"] if row.label == "STATEMENT"}
        tokens = bridge_token_states(target.layout, shared)
        source_head = self.core.task_modules["assertor_source"]
        source_losses = []
        for row in target.assertors:
            statement = statements[row.statement_id]
            exists = row.alignment is not None
            source_losses.append(F.binary_cross_entropy_with_logits(
                source_head.existence_logit(statement), doc.new_tensor(float(exists))))
            if not exists:
                continue
            key = "ASSERTOR:" + row.statement_id
            source = extras[key]
            alignment = row.alignment
            start_ref_token = next(token for token in target.layout.window_lookup[
                alignment.start_ref.window_id].tokens
                if token.position == alignment.start_ref.token_position)
            end_ref_token = next(token for token in target.layout.window_lookup[
                alignment.end_ref.window_id].tokens
                if token.position == alignment.end_ref.token_position)
            start_token = target.layout.bridge_tokens[start_ref_token.source_index]
            end_token = target.layout.bridge_tokens[end_ref_token.source_index]
            start_index, end_index = start_token.source_index, end_token.source_index
            logits = source_head.token_logits(statement, tokens)
            source_losses.append(F.cross_entropy(logits[:, 0].unsqueeze(0),
                                                 torch.tensor([start_index], device=doc.device)))
            source_losses.append(F.cross_entropy(logits[:, 1].unsqueeze(0),
                                                 torch.tensor([end_index], device=doc.device)))
            signed_target = doc.new_tensor((alignment.start - start_token.start,
                                            alignment.end - end_token.end))
            predicted = residuals[key] + source_head.residual_delta(statement, source, residuals[key])
            source_losses.append(F.smooth_l1_loss(predicted, signed_target))
            source_losses.append(F.binary_cross_entropy_with_logits(
                links[key] + source_head.span_logit(statement, source), doc.new_tensor(1.0)))
        source_loss = torch.stack(source_losses).mean() if source_losses else zero
        cluster_map = gold_cluster_local_ids(article, features)
        entity_map = gold_entity_local_ids(article, features)
        cluster_index = {cid: index for index, cid in enumerate(view.cluster_ids)}
        entity_states = {eid: extras["ENTITY:" + eid] for eid in entity_map.values()}
        pair_losses = {}
        sampled = {}
        for name in ("assertor_entity", "about", "causes"):
            universe = target.pairs[name]
            sample = sorted(universe.positive_pairs) + [
                (row.left_id, row.right_id) for row in universe.sample_negatives(
                    limit=self.negative_limit, seed=self.core.config.seed,
                    content_sha256=target.content_sha256)]
            sampled[name] = len(sample) - len(universe.positive_pairs)
            chunks = []
            for offset in range(0, len(sample), self.chunk_size):
                pairs = sample[offset:offset + self.chunk_size]
                if name == "assertor_entity":
                    left = torch.stack([statements[a] + extras["ASSERTOR:" + a] for a, _ in pairs])
                    right = torch.stack([entity_states[entity_map[b]] for _, b in pairs])
                elif name == "about":
                    left = torch.stack([statements[a] for a, _ in pairs])
                    right = torch.stack([view.mean_reference[cluster_index[cluster_map[b]]]
                                         for _, b in pairs])
                else:
                    left = torch.stack([view.mean_reference[cluster_index[cluster_map[a]]]
                                        for a, _ in pairs])
                    right = torch.stack([view.mean_reference[cluster_index[cluster_map[b]]]
                                         for _, b in pairs])
                labels = doc.new_tensor([float(pair in universe.positive_pairs) for pair in pairs])
                logits = self.core.task_modules[name](left, right, doc)
                chunks.append(F.binary_cross_entropy_with_logits(logits, labels, reduction="sum"))
            pair_losses[name] = sum(chunks) / len(sample) if sample else zero
        losses = {"assertor_source": source_loss, **pair_losses}
        if any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("attribution relation loss is non-finite")
        return AttributionLossResult(
            losses, sum(row.alignment is not None for row in target.assertors),
            sum(row.alignment is None for row in target.assertors),
            len(target.pairs["assertor_entity"].positive_pairs), sampled["assertor_entity"],
            len(target.pairs["about"].positive_pairs), sampled["about"],
            len(target.pairs["causes"].positive_pairs), sampled["causes"],
            sum(row.alignment is not None and row.entity_id is None for row in target.assertors))
