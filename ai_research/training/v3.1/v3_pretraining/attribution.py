"""검증된 train Gold의 Assertor/ASSERTED_BY/ABOUT/CAUSES target 실행 adapter.

Gold ID는 label/remap에만 사용한다. final local Event/Entity tensor와 기존
direct-gather source state를 소비하며 pair universe를 확장하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import torch
from torch.nn import functional as F

from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.pair_context import (build_pair_context,
                                                summarize_statements)
from runtime.v3_pretraining.attribution_features import (
    ASSERTOR_ENTITY_STATE_PREFIX,
    assertor_option_target_status,
    assertor_relation_left,
    build_assertor_entity_options,
)
from runtime.v3_pretraining.attribution_scoring import bridge_token_states
from runtime.v3_pretraining.event_features import FinalClusterFeatureLease
from training.v3_pretraining.event import EventGoldFeatures
from training.v3_pretraining.relation_evaluation import score_full_universe
from training.v3_pretraining.relation_sampling import (
    RELATION_NEGATIVE_LIMIT,
    ClassBalancedLoss,
    RelationSamplingPolicy,
    class_balanced_pair_loss,
    deterministic_stratified_sample,
)
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
        if gold_id is None:
            continue
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
    loss_components: dict[str, torch.Tensor]
    supervision_census: dict[str, int]
    source_positive: int
    source_absent: int
    assertor_entity_positive: int
    assertor_entity_negative_sampled: int
    about_positive: int
    about_negative_sampled: int
    causes_positive: int
    causes_negative_sampled: int
    unresolved_span_only: int
    relation_sampling: dict[str, Mapping[str, object]]


def _sentence_cohort(left_anchor: int, right_anchor: int) -> str:
    distance = abs(right_anchor - left_anchor)
    return ("same_sentence" if distance == 0 else
            "adjacent_sentence" if distance == 1 else "non_adjacent")


def _relation_memberships(
        article: ValidatedGoldArticle, target: ArticleTargets,
        features: EventGoldFeatures, *, cluster_map: Mapping[str, str],
        entity_map: Mapping[str, str], statement_summaries: Mapping[str, object],
        event_summaries: Sequence[object],
        option_ids: Mapping[str, tuple[str, ...]],
) -> tuple[dict[str, dict[tuple[str, str], frozenset[str]]], dict[str, object]]:
    """Gold label과 독립적인 source/identity proxy membership을 한 번 만든다."""
    inverse_cluster = {local: gold for gold, local in cluster_map.items()}
    inverse_entity = {local: gold for gold, local in entity_map.items()}
    cluster_index = {row.local_id: index for index, row in enumerate(features.closure.events)}
    if set(inverse_cluster) != set(cluster_index):
        raise ValueError("relation strata need one-to-one final Event identity")
    event_entities: dict[str, frozenset[str]] = {}
    event_triggers: dict[str, frozenset[str]] = {}
    for event in features.closure.events:
        gold_id = inverse_cluster[event.local_id]
        event_entities[gold_id] = frozenset(
            row.entity_id for row in event.roles if row.entity_id is not None)
        event_triggers[gold_id] = frozenset(
            text for _start, _end, text, _member_id in event.triggers if text)
    statement_spans = {row.owner_id: (row.alignment.start, row.alignment.end)
                       for row in target.spans["semantic_proposer"]
                       if row.label == "STATEMENT"}
    statement_entities: dict[str, set[str]] = {sid: set() for sid in statement_spans}
    for row in target.assertors:
        if row.resolution_mask == "SUPERVISE" and row.entity_id is not None:
            statement_entities[row.statement_id].add(entity_map[row.entity_id])
    candidates = features.entity_oracle.universe.candidates
    candidate_to_entity = features.entity_oracle.closure.candidate_to_entity
    for statement_id, (start, end) in statement_spans.items():
        statement_entities[statement_id].update(
            candidate_to_entity[row.candidate_id] for row in candidates
            if row.candidate_id in candidate_to_entity
            and max(start, row.start) < min(end, row.end))

    output: dict[str, dict[tuple[str, str], frozenset[str]]] = {
        "assertor_entity": {}, "about": {}, "causes": {}}
    for statement_id, entities in option_ids.items():
        for local_entity_id in entities:
            gold_entity_id = inverse_entity.get(local_entity_id)
            pair = (statement_id, gold_entity_id) if gold_entity_id is not None else None
            if pair in {(row.left_id, row.right_id)
                        for row in target.pairs["assertor_entity"] if not row.positive}:
                output["assertor_entity"][pair] = frozenset(("option_confounder",))

    about_lexical_candidates = 0
    about_universe = target.pairs["about"]
    about_negative = {(row.left_id, row.right_id) for row in about_universe if not row.positive}
    for statement_id, cluster_id in about_negative:
        tags = {_sentence_cohort(statement_summaries[statement_id].anchor_index,
                                 event_summaries[cluster_index[cluster_map[cluster_id]]].anchor_index)}
        if statement_entities[statement_id] & event_entities[cluster_id]:
            tags.add("shared_resolved_entity")
        start, end = statement_spans[statement_id]
        statement_text = article.raw.content[start:end]
        # EXACT_TRIGGER_SUBSTRING_V1 is a sampling proxy only. It never creates a
        # label and deliberately adds no normalization or semantic matching.
        if any(surface in statement_text for surface in event_triggers[cluster_id]):
            about_lexical_candidates += 1
            tags.add("lexical_overlap")
        output["about"][(statement_id, cluster_id)] = frozenset(tags)

    causes_universe = target.pairs["causes"]
    for left_id, right_id in ((row.left_id, row.right_id) for row in causes_universe
                              if not row.positive):
        tags = {_sentence_cohort(
            event_summaries[cluster_index[cluster_map[left_id]]].anchor_index,
            event_summaries[cluster_index[cluster_map[right_id]]].anchor_index)}
        if (right_id, left_id) in causes_universe.positive_pairs:
            tags.add("reverse_positive")
        if event_entities[left_id] & event_entities[right_id]:
            tags.add("shared_resolved_entity")
        if event_triggers[left_id] & event_triggers[right_id]:
            tags.add("shared_trigger")
        output["causes"][(left_id, right_id)] = frozenset(tags)
    return output, {
        "about_exact_trigger_substring_membership": about_lexical_candidates,
        "about_lexical_overlap_policy": "EXACT_TRIGGER_SUBSTRING_V1",
        "about_lexical_overlap_policy_status": "APPROVED_WIRED",
    }


def _assertor_objective_overlap_census(
        *, main_positive: set[tuple[str, str]],
        main_negative: set[tuple[str, str]],
        option_labeled_pairs: Sequence[tuple[tuple[str, str], bool]],
) -> dict[str, int]:
    """Validate option uniqueness and report label-specific objective overlap."""
    option_total = len(option_labeled_pairs)
    option_labels: dict[tuple[str, str], bool] = {}
    for pair, positive in option_labeled_pairs:
        if pair in option_labels and option_labels[pair] != positive:
            raise ValueError("Assertor option pair has conflicting supervision")
        option_labels[pair] = positive
    option_duplicate = option_total - len(option_labels)
    if option_duplicate:
        raise ValueError("Assertor option set contains duplicate pair supervision")
    option_positive = {pair for pair, positive in option_labels.items() if positive}
    option_negative = set(option_labels) - option_positive
    cross_label = ((main_positive & option_negative) |
                   (main_negative & option_positive))
    if cross_label:
        raise ValueError("Assertor main/option objectives disagree on pair label")
    positive_overlap = main_positive & option_positive
    negative_overlap = main_negative & option_negative
    return {
        "option_set_total_pair_count": option_total,
        "option_set_unique_pair_count": len(option_labels),
        "option_set_duplicate_count": option_duplicate,
        "option_set_unique_positive": len(option_positive),
        "option_set_unique_negative": len(option_negative),
        "main_option_positive_overlap": len(positive_overlap),
        "main_option_negative_overlap": len(negative_overlap),
        "main_option_total_overlap": len(positive_overlap | negative_overlap),
        "main_option_cross_label_overlap": len(cross_label),
    }


class AttributionGoldAdapter:
    def __init__(self, core: V3Core, *, negative_limit: int = RELATION_NEGATIVE_LIMIT,
                 chunk_size: int = 128,
                 sampling_policy: RelationSamplingPolicy | None = None) -> None:
        if any(name in core.unimplemented_tasks for name in (
                "assertor_source", "assertor_entity", "about", "causes")):
            raise ValueError("stage 9 heads are not registered")
        if min(negative_limit, chunk_size) <= 0:
            raise ValueError("attribution pair bounds must be positive")
        self.sampling_policy = sampling_policy or RelationSamplingPolicy(
            negative_limit=negative_limit)
        self.sampling_policy.validate()
        self.core = core
        self.negative_limit = self.sampling_policy.negative_limit
        self.chunk_size = chunk_size

    def assertor_source_loss(self, target: ArticleTargets, lease,
                             shared: SharedForwardLease) -> torch.Tensor:
        """Gold Assertor source objective without Event identity or relation heads."""
        if (lease.closed or lease.source_mode != "GOLD_ORACLE" or
                lease.extra_states is None or lease.extra_residuals is None or
                lease.extra_link_logits is None or lease.document_state is None):
            raise ValueError("Assertor source needs live oracle states")
        extras = lease.extra_states
        residuals = lease.extra_residuals
        links = lease.extra_link_logits
        doc = lease.document_state
        zero = doc.sum() * 0
        statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                      for row in target.spans["semantic_proposer"]
                      if row.label == "STATEMENT"}
        tokens = bridge_token_states(target.layout, shared)
        source_head = self.core.task_modules["assertor_source"]
        source_losses = []
        for row in target.assertors:
            statement = statements[row.statement_id]
            if row.source_mask == "IGNORE":
                continue
            if row.source_mask not in ("SUPERVISE", "NO_EXPLICIT_SOURCE"):
                raise ValueError("unknown Assertor source supervision mask")
            exists = row.source_mask == "SUPERVISE"
            if exists != (row.alignment is not None):
                raise ValueError("Assertor source mask/alignment contract differs")
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
        return source_loss

    def assertor_source_loss_batched(self, target: ArticleTargets, lease,
                                    shared: SharedForwardLease) -> torch.Tensor:
        """Dev-only batched equivalent of the fixed Gold Assertor source loss."""
        if (lease.closed or lease.source_mode != "GOLD_ORACLE" or
                lease.extra_states is None or lease.extra_residuals is None or
                lease.extra_link_logits is None or lease.document_state is None):
            raise ValueError("batched Assertor source needs live oracle states")
        rows = [row for row in target.assertors if row.source_mask != "IGNORE"]
        zero = lease.document_state.sum() * 0
        if not rows:
            return zero
        if any(row.source_mask not in ("SUPERVISE", "NO_EXPLICIT_SOURCE") or
               (row.source_mask == "SUPERVISE") != (row.alignment is not None)
               for row in rows):
            raise ValueError("Assertor source mask/alignment contract differs")
        head = self.core.task_modules["assertor_source"]
        statements = {row.owner_id: lease.extra_states["STATEMENT:" + row.owner_id]
                      for row in target.spans["semantic_proposer"]
                      if row.label == "STATEMENT"}
        owner = torch.stack([statements[row.statement_id] for row in rows])
        exists = owner.new_tensor([float(row.source_mask == "SUPERVISE") for row in rows])
        total = F.binary_cross_entropy_with_logits(
            head.exists(owner).squeeze(-1), exists, reduction="sum")
        positive = [row for row in rows if row.source_mask == "SUPERVISE"]
        if positive:
            owner = torch.stack([statements[row.statement_id] for row in positive])
            sources = torch.stack([lease.extra_states["ASSERTOR:" + row.statement_id]
                                   for row in positive])
            residuals = torch.stack([lease.extra_residuals[
                "ASSERTOR:" + row.statement_id] for row in positive])
            links = torch.stack([lease.extra_link_logits[
                "ASSERTOR:" + row.statement_id] for row in positive])
            tokens = bridge_token_states(target.layout, shared)
            expanded_owner = owner[:, None, :].expand(-1, len(tokens), -1)
            expanded_tokens = tokens[None, :, :].expand(len(positive), -1, -1)
            logits = head.token(torch.cat((expanded_owner, expanded_tokens,
                                           expanded_owner * expanded_tokens), dim=-1))
            starts = []
            ends = []
            signed = []
            for row in positive:
                alignment = row.alignment
                start_ref = next(token for token in target.layout.window_lookup[
                    alignment.start_ref.window_id].tokens
                    if token.position == alignment.start_ref.token_position)
                end_ref = next(token for token in target.layout.window_lookup[
                    alignment.end_ref.window_id].tokens
                    if token.position == alignment.end_ref.token_position)
                start_token = target.layout.bridge_tokens[start_ref.source_index]
                end_token = target.layout.bridge_tokens[end_ref.source_index]
                starts.append(start_token.source_index)
                ends.append(end_token.source_index)
                signed.append((alignment.start - start_token.start,
                               alignment.end - end_token.end))
            total = (total + F.cross_entropy(
                logits[:, :, 0], torch.tensor(starts, device=owner.device),
                reduction="sum") + F.cross_entropy(
                logits[:, :, 1], torch.tensor(ends, device=owner.device),
                reduction="sum"))
            delta = head.residual(torch.cat((owner, sources, residuals), dim=-1))
            total = total + F.smooth_l1_loss(
                residuals + delta, owner.new_tensor(signed), reduction="none").mean(dim=1).sum()
            span_logits = head.span(torch.cat((owner, sources, owner * sources),
                                              dim=-1)).squeeze(-1)
            total = total + F.binary_cross_entropy_with_logits(
                links + span_logits, torch.ones_like(span_logits), reduction="sum")
        return total / (len(rows) + 4 * len(positive))

    def _score_pairs(
            self, name: str, pairs: Sequence[tuple[str, str]], *,
            statements: Mapping[str, torch.Tensor], extras: Mapping[str, torch.Tensor],
            entity_states: Mapping[str, torch.Tensor], entity_map: Mapping[str, str],
            cluster_map: Mapping[str, str], cluster_index: Mapping[str, int],
            view, statement_summaries: Mapping[str, object], doc: torch.Tensor,
    ) -> torch.Tensor:
        if not pairs:
            return doc.new_empty((0,))
        if name == "assertor_entity":
            left = torch.stack([assertor_relation_left(
                statements[a], extras["ASSERTOR:" + a]) for a, _ in pairs])
            right = torch.stack([entity_states[entity_map[b]] for _, b in pairs])
            return self.core.task_modules[name](left, right, doc)
        if name == "about":
            left = torch.stack([statements[a] for a, _ in pairs])
            right = torch.stack([view.mean_reference[cluster_index[cluster_map[b]]]
                                 for _, b in pairs])
            left_summaries = [statement_summaries[a] for a, _ in pairs]
        elif name == "causes":
            left = torch.stack([view.mean_reference[cluster_index[cluster_map[a]]]
                                for a, _ in pairs])
            right = torch.stack([view.mean_reference[cluster_index[cluster_map[b]]]
                                 for _, b in pairs])
            left_summaries = [view.event_sentence_summaries[
                cluster_index[cluster_map[a]]] for a, _ in pairs]
        else:
            raise ValueError("unknown attribution relation lane")
        right_summaries = [view.event_sentence_summaries[
            cluster_index[cluster_map[b]]] for _, b in pairs]
        pair_context = build_pair_context(
            left=left, right=right, left_summaries=left_summaries,
            right_summaries=right_summaries,
            sentence_states=view.original_sentence_states, document_state=doc)
        return self.core.task_modules[name](pair_context.features)

    def loss(self, article: ValidatedGoldArticle, target: ArticleTargets,
             features: EventGoldFeatures, final: FinalClusterFeatureLease,
             shared: SharedForwardLease, *,
             channels: frozenset[str] | None = None) -> AttributionLossResult:
        """Keep the historical full loss unless an epoch evaluator selects lanes."""
        requested = (frozenset(("assertor_source", "assertor_entity", "about", "causes"))
                     if channels is None else channels)
        if not requested or not requested <= {"assertor_source", "assertor_entity",
                                              "about", "causes"}:
            raise ValueError("unknown attribution Gold loss channel")
        if (article.split not in ("train", "dev", "test") or target.article_version_id != final.article_version_id
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
        statement_spans = {row.owner_id: (row.alignment.start, row.alignment.end)
                           for row in target.spans["semantic_proposer"]
                           if row.label == "STATEMENT"}
        statement_summaries = summarize_statements(
            view.original_sentence_states, view.original_sentence_spans, statement_spans)
        source_loss = (self.assertor_source_loss(target, features.time, shared)
                       if "assertor_source" in requested else zero)
        cluster_map = gold_cluster_local_ids(article, features)
        entity_map = gold_entity_local_ids(article, features)
        cluster_index = {cid: index for index, cid in enumerate(view.cluster_ids)}
        entity_states = {eid: extras[ASSERTOR_ENTITY_STATE_PREFIX + eid]
                         for eid in entity_map.values()}
        binding_by_id = {row.evidence_id: row for row in features.entity_oracle.universe.bindings}
        option_cache = {}
        for row in target.assertors if "assertor_entity" in requested else ():
            if row.resolution_mask != "SUPERVISE":
                continue
            if row.entity_id is None or row.alignment is None:
                raise ValueError("resolved Assertor supervision contract differs")
            option_cache[row.statement_id] = build_assertor_entity_options(
                layout=target.layout, universe=features.entity_oracle.universe,
                preliminary=features.entity_oracle.closure,
                binding=binding_by_id["ASSERTOR:" + row.statement_id])
        memberships, unresolved_proxy = _relation_memberships(
            article, target, features, cluster_map=cluster_map, entity_map=entity_map,
            statement_summaries=statement_summaries,
            event_summaries=view.event_sentence_summaries,
            option_ids={statement_id: options.entity_ids
                        for statement_id, options in option_cache.items()})
        pair_losses = {}
        samples = {}
        reductions: dict[str, ClassBalancedLoss] = {}
        for name in ("assertor_entity", "about", "causes"):
            if name not in requested:
                reductions[name] = class_balanced_pair_loss((), zero=zero)
                pair_losses[name] = zero
                continue
            universe = target.pairs[name]
            sample = deterministic_stratified_sample(
                universe, content_sha256=target.content_sha256,
                memberships=memberships[name], policy=self.sampling_policy)
            samples[name] = sample
            loss_chunks = []
            rows = sample.pairs
            for offset in range(0, len(rows), self.chunk_size):
                chunk = rows[offset:offset + self.chunk_size]
                pairs = tuple((row.left_id, row.right_id) for row in chunk)
                logits = self._score_pairs(
                    name, pairs, statements=statements, extras=extras,
                    entity_states=entity_states, entity_map=entity_map,
                    cluster_map=cluster_map, cluster_index=cluster_index,
                    view=view, statement_summaries=statement_summaries, doc=doc)
                labels = doc.new_tensor([float(row.positive) for row in chunk])
                loss_chunks.append((logits, labels))
            reduction = class_balanced_pair_loss(loss_chunks, zero=zero)
            reductions[name] = reduction
            pair_losses[name] = reduction.loss

        # Runtime-style bounded option loss는 discovery 뒤에만 Gold target을 대조한다.
        # OPTION_MISS는 IGNORE이며 article-wide complement BCE와 count를 섞지 않는다.
        option_losses = []
        option_positive = 0
        option_negative = 0
        option_miss = 0
        option_ignored = 0
        option_pairs = 0
        option_truncated = 0
        option_unknown_ignored = 0
        option_labeled_pairs: list[tuple[tuple[str, str], bool]] = []
        inverse_entity_map = {local: gold for gold, local in entity_map.items()}
        for row in target.assertors if "assertor_entity" in requested else ():
            if row.resolution_mask == "IGNORE":
                option_ignored += 1
                continue
            if row.resolution_mask != "SUPERVISE" or row.entity_id is None or row.alignment is None:
                raise ValueError("resolved Assertor supervision contract differs")
            options = option_cache[row.statement_id]
            target_local = entity_map[row.entity_id]
            option_truncated += options.truncated_count
            # The source-only option builder may return an unresolved ROLE
            # singleton. Its Gold identity is unknown, so it cannot become an
            # automatic negative in the supervised option loss.
            supervised_ids = tuple(entity_id for entity_id in options.entity_ids
                                   if entity_id in inverse_entity_map)
            option_unknown_ignored += len(options.entity_ids) - len(supervised_ids)
            if assertor_option_target_status(options, target_local) == "OPTION_MISS":
                option_miss += 1
                continue
            left = assertor_relation_left(
                statements[row.statement_id], extras["ASSERTOR:" + row.statement_id])
            right = torch.stack([entity_states[entity_id] for entity_id in supervised_ids])
            logits = self.core.task_modules["assertor_entity"](
                left.unsqueeze(0).expand_as(right), right, doc)
            labels = doc.new_tensor([float(entity_id == target_local)
                                     for entity_id in supervised_ids])
            option_losses.append(F.binary_cross_entropy_with_logits(logits, labels))
            option_pairs += len(supervised_ids)
            option_positive += 1
            option_negative += len(supervised_ids) - 1
            option_labeled_pairs.extend(
                ((row.statement_id, inverse_entity_map[entity_id]),
                 entity_id == target_local)
                for entity_id in supervised_ids)
        option_loss = torch.stack(option_losses).mean() if option_losses else zero
        full_universe_loss = pair_losses["assertor_entity"]
        pair_losses["assertor_entity"] = full_universe_loss + option_loss
        losses = {"assertor_source": source_loss, **pair_losses}
        loss_components = {
            "assertor_entity_main_class_balanced": full_universe_loss,
            "assertor_entity_option_set_bce": option_loss,
        }
        main_assertor_positive = {(row.left_id, row.right_id)
                                  for row in samples["assertor_entity"].positives} if (
                                      "assertor_entity" in samples) else set()
        main_assertor_negative = {(row.pair.left_id, row.pair.right_id)
                                  for row in samples["assertor_entity"].negatives} if (
                                      "assertor_entity" in samples) else set()
        overlap_census = _assertor_objective_overlap_census(
            main_positive=main_assertor_positive,
            main_negative=main_assertor_negative,
            option_labeled_pairs=option_labeled_pairs)
        supervision_census = {
            "assertor_source_positive": sum(
                row.source_mask == "SUPERVISE" for row in target.assertors),
            "assertor_source_no_explicit_negative": sum(
                row.source_mask == "NO_EXPLICIT_SOURCE" for row in target.assertors),
            "assertor_source_ignored": sum(
                row.source_mask == "IGNORE" for row in target.assertors),
            "full_universe_positive": len(target.pairs["assertor_entity"].positive_pairs),
            "main_positive": reductions["assertor_entity"].positive_count,
            "main_negative_sampled": reductions["assertor_entity"].negative_count,
            "main_positive_effective_weight": reductions["assertor_entity"].positive_weight,
            "main_negative_effective_weight": reductions["assertor_entity"].negative_weight,
            "option_set_positive": option_positive,
            "option_set_safe_negative": option_negative,
            "option_set_pairs_scored": option_pairs,
            "option_unknown_identity_ignored": option_unknown_ignored,
            "option_miss_ignored": option_miss,
            "resolution_ignored": option_ignored,
            "option_truncated": option_truncated,
            **overlap_census,
            "assertor_entity_final_main_coefficient": 1,
            "assertor_entity_final_option_coefficient": 1,
            "gold_target_injected": 0,
        }
        relation_sampling = {
            name: {**sample.census,
                   "positive_reduction_denominator": reductions[name].positive_count,
                   "negative_reduction_denominator": reductions[name].negative_count,
                   "positive_effective_weight": reductions[name].positive_weight,
                   "negative_effective_weight": reductions[name].negative_weight,
                   "article_id": article.raw.article_id,
                   "article_version_id": article.raw.article_version_id,
                   "annotation_provenance": "r05.3_VALIDATED_GOLD",
                   **(unresolved_proxy if name == "about" else {})}
            for name, sample in samples.items()}
        if "assertor_entity" in relation_sampling:
            relation_sampling["assertor_entity"] = {
                **relation_sampling["assertor_entity"],
                "eligible_ignored": option_ignored,
                **overlap_census,
                "main_loss_coefficient": 1,
                "option_loss_coefficient": 1,
            }
        if any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("attribution relation loss is non-finite")
        return AttributionLossResult(
            losses=losses, loss_components=loss_components,
            supervision_census=supervision_census,
            source_positive=supervision_census["assertor_source_positive"],
            source_absent=supervision_census["assertor_source_no_explicit_negative"],
            assertor_entity_positive=len(target.pairs["assertor_entity"].positive_pairs),
            assertor_entity_negative_sampled=reductions["assertor_entity"].negative_count,
            about_positive=len(target.pairs["about"].positive_pairs),
            about_negative_sampled=reductions["about"].negative_count,
            causes_positive=len(target.pairs["causes"].positive_pairs),
            causes_negative_sampled=reductions["causes"].negative_count,
            unresolved_span_only=sum(row.alignment is not None and row.entity_id is None
                                     for row in target.assertors),
            relation_sampling=relation_sampling)

    @torch.no_grad()
    def evaluate_full_universe(
            self, article: ValidatedGoldArticle, target: ArticleTargets,
            features: EventGoldFeatures, final: FinalClusterFeatureLease,
    ) -> dict[str, object]:
        """Gold endpoint/identity 고정, sampling·serving cap 없는 세 lane 평가."""
        if (article.split not in ("dev", "test")
                or target.article_version_id != final.article_version_id
                or target.content_sha256 != final.content_sha256
                or features.closure.source_mode != "GOLD_ORACLE"
                or final.source_mode != "GOLD_ORACLE"
                or self.core.training
                or features.time.closed or features.time.extra_states is None):
            raise ValueError("full-universe relation evaluation needs live evaluation Gold")
        view = final.view_for("RELATION")
        extras = features.time.extra_states
        doc = view.document_state
        statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                      for row in target.spans["semantic_proposer"]
                      if row.label == "STATEMENT"}
        statement_spans = {row.owner_id: (row.alignment.start, row.alignment.end)
                           for row in target.spans["semantic_proposer"]
                           if row.label == "STATEMENT"}
        statement_summaries = summarize_statements(
            view.original_sentence_states, view.original_sentence_spans,
            statement_spans)
        cluster_map = gold_cluster_local_ids(article, features)
        entity_map = gold_entity_local_ids(article, features)
        cluster_index = {cid: index for index, cid in enumerate(view.cluster_ids)}
        entity_states = {eid: extras[ASSERTOR_ENTITY_STATE_PREFIX + eid]
                         for eid in entity_map.values()}

        reports = {}
        for name in ("assertor_entity", "about", "causes"):
            def scorer(chunk, lane=name):
                return self._score_pairs(
                    lane, tuple((row.left_id, row.right_id) for row in chunk),
                    statements=statements, extras=extras,
                    entity_states=entity_states, entity_map=entity_map,
                    cluster_map=cluster_map, cluster_index=cluster_index,
                    view=view, statement_summaries=statement_summaries, doc=doc)

            def cohort(row, lane=name):
                if lane == "assertor_entity":
                    return None
                left_summary = (statement_summaries[row.left_id] if lane == "about"
                                else view.event_sentence_summaries[
                                    cluster_index[cluster_map[row.left_id]]])
                right_summary = view.event_sentence_summaries[
                    cluster_index[cluster_map[row.right_id]]]
                return _sentence_cohort(left_summary.anchor_index,
                                        right_summary.anchor_index).upper()

            reports[name] = score_full_universe(
                article_id=article.raw.article_id, universe=target.pairs[name],
                chunk_size=self.chunk_size, score_chunk=scorer,
                cohort_for=cohort if name != "assertor_entity" else None,
                cohort_names=(("SAME_SENTENCE", "ADJACENT_SENTENCE", "NON_ADJACENT")
                              if name != "assertor_entity" else ()))

        binding_by_id = {row.evidence_id: row
                         for row in features.entity_oracle.universe.bindings}
        option_ready = option_present = option_miss = option_pairs = 0
        for row in target.assertors:
            if row.resolution_mask != "SUPERVISE":
                continue
            options = build_assertor_entity_options(
                layout=target.layout, universe=features.entity_oracle.universe,
                preliminary=features.entity_oracle.closure,
                binding=binding_by_id["ASSERTOR:" + row.statement_id])
            option_ready += 1
            option_pairs += len(options.entity_ids)
            if assertor_option_target_status(options, entity_map[row.entity_id]) == "OPTION_MISS":
                option_miss += 1
            else:
                option_present += 1
        return {
            "mode": "GOLD_ENDPOINT_IDENTITY_FULL_UNIVERSE",
            "sampling_applied": False,
            "serving_pair_cap_applied": False,
            "lanes": reports,
            "assertor_runtime_option_diagnostic": {
                "separate_from_article_wide_discrimination": True,
                "resolved_sources": option_ready,
                "target_option_present": option_present,
                "option_miss": option_miss,
                "option_pairs": option_pairs,
            },
        }
