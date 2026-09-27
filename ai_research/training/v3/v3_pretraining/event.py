"""검증된 train same-event pair와 final-cluster oracle 구조의 학습 adapter.

Gold cluster ID는 pair label 검사에만 쓰고 learned Event feature에 주입하지 않는다.
7번 Event/Time lease와 한 direct-gather pass의 role/Entity/trigger state를 공유한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import torch
from torch.nn import functional as F

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from runtime.v3_pretraining.attribution_features import (
    ASSERTOR_ENTITY_STATE_PREFIX,
    ENTITY_MEMBER_STATE_PREFIX,
    EVENT_ENTITY_STATE_PREFIX,
    build_entity_representation_views,
)
from runtime.v3_pretraining.event_features import (EventFeatureProvenance, EventMemberFeatureLease,
                                                   EventOptionalConfidenceEvidence,
                                                   build_event_member_features,
                                                   build_event_pair_feature_bundle,
                                                   event_member_sentence_indices)
from runtime.v3_pretraining.event_identity import (EventClosure, EventMember, MemberRoleFact,
                                                   close_event_identity)
from runtime.v3_pretraining.event_pair_policy import event_pair_policy_features
from runtime.v3_pretraining.temporal import TemporalOccurrence
from runtime.v3_pretraining.temporal_scoring import EventTimeFeatureLease
from training.v3_pretraining.entity import OracleEntityStructure, build_oracle_entity_structure
from training.v3_pretraining.relation_evaluation import score_full_universe
from training.v3_pretraining.targets import ArticleTargets, ValidatedGoldArticle
from training.v3_pretraining.time import TimeGoldAdapter, gold_time_occurrences


def oracle_event_members(article: ValidatedGoldArticle, target: ArticleTargets,
                         entity_oracle: OracleEntityStructure,
                         occurrences: tuple[TemporalOccurrence, ...]) -> tuple[EventMember, ...]:
    """Gold fact를 final local endpoint 근거로 변환하되 identity label은 feature 밖에 둔다."""
    trigger = {row.owner_id: row.alignment for row in target.spans["trigger"]}
    event_span = {row.owner_id: row.alignment for row in target.spans["semantic_proposer"]
                  if row.label == "EVENT"}
    endpoint = {row.evidence_id: row for row in entity_oracle.closure.endpoints}
    time_by_evidence = {evidence_id: row.local_id for row in occurrences
                        for evidence_id in row.evidence_ids}
    roles_by_event: dict[str, list[MemberRoleFact]] = {}
    for role in target.roles:
        local = endpoint[role.role_id]
        roles_by_event.setdefault(role.event_id, []).append(
            MemberRoleFact(role.role_id, role.role, role.alignment.start,
                           role.alignment.end, role.alignment.text,
                           local.local_entity_id, local.status))
    output = []
    for row in article.annotations["events"]:
        event_id = row["event_id"]
        semantic = event_span[event_id]
        firing = trigger[event_id]
        output.append(EventMember(event_id, semantic.start, semantic.end, semantic.text,
                                  firing.start, firing.end, firing.text,
                                  tuple(roles_by_event.get(event_id, ())),
                                  tuple(time_by_evidence[tid] for tid in row["times"])))
    return tuple(output)


def oracle_event_closure(article: ValidatedGoldArticle, target: ArticleTargets,
                         members: tuple[EventMember, ...]) -> EventClosure:
    universe = target.pairs["event_coreference"]
    decisions = {(a, b): (a, b) in universe.positive_pairs
                 for a, b in combinations(universe.left_ids, 2)}
    result = close_event_identity(article.raw, members, pair_decisions=decisions,
                                  source_mode="GOLD_ORACLE")
    if result.unassessed_pairs or len(result.events) != len(article.annotations["event_clusters"]):
        raise AssertionError("Gold Event clusters did not close exactly")
    gold_membership = {eid: cluster["cluster_id"] for cluster in article.annotations["event_clusters"]
                       for eid in cluster["event_ids"]}
    for a, b in combinations(universe.left_ids, 2):
        if (result.member_to_cluster[a] == result.member_to_cluster[b]) != (
                gold_membership[a] == gold_membership[b]):
            raise AssertionError("oracle final Event identity differs from Gold membership")
    return result


class EventGoldFeatures:
    """학습 호출 안에서만 7번 source lease와 8번 member lease를 공동 소유한다."""

    def __init__(self, time: EventTimeFeatureLease, member: EventMemberFeatureLease,
                 closure: EventClosure, occurrences: tuple[TemporalOccurrence, ...],
                 entity_oracle: OracleEntityStructure) -> None:
        self.time = time
        self.member = member
        self.closure = closure
        self.occurrences = occurrences
        self.entity_oracle = entity_oracle
        self.pair_bundle = None

    def close(self) -> None:
        self.pair_bundle = None
        self.member.close()
        self.time.close()

    def __enter__(self) -> "EventGoldFeatures":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _oracle_confidence_evidence(lease: EventMemberFeatureLease
                                ) -> tuple[EventOptionalConfidenceEvidence, ...]:
    """Gold oracle source existence has probability 1 only in this oracle path."""
    evidence = []
    for member in lease.members:
        sources = {
            "trigger": (("TRIGGER:" + member.member_id,) if member.trigger_text else ()),
            "actor": tuple(row.evidence_id for row in member.roles if row.role == "ACTOR"),
            "target": tuple(row.evidence_id for row in member.roles if row.role == "TARGET"),
            "place": tuple(row.evidence_id for row in member.roles if row.role == "PLACE"),
            "entity": tuple(sorted({row.entity_id for row in member.roles
                                    if row.entity_id is not None and
                                    row.entity_id not in lease.missing_entity_features})),
            "time": member.time_ids,
        }
        for channel, ids in sources.items():
            evidence.extend(EventOptionalConfidenceEvidence(
                member.member_id, channel, source_id, 1.0, "GOLD_ORACLE")
                for source_id in ids)
    return tuple(evidence)


def _oracle_optional_source_counts(features: EventGoldFeatures) -> tuple[tuple[int, ...], ...]:
    lease = features.member
    by_candidate = {candidate.candidate_id: candidate
                    for candidate in features.entity_oracle.universe.candidates}
    native_count = {entity.local_id: sum(
        "NER" in by_candidate[candidate_id].origins
        for candidate_id in entity.candidate_ids)
        for entity in features.entity_oracle.closure.entities}
    time_count = {row.local_id: len(row.evidence_ids) for row in features.occurrences}
    return tuple(
        (int(member.trigger_text is not None),
         *(sum(role.role == name for role in member.roles)
           for name in ("ACTOR", "TARGET", "PLACE")),
         sum(native_count.get(entity_id, 0) for entity_id in {
             role.entity_id for role in member.roles if role.entity_id is not None}),
         sum(time_count[time_id] for time_id in member.time_ids))
        for member in lease.members)


def _event_head_inputs(features: EventGoldFeatures, head):
    lease = features.member
    if features.pair_bundle is None:
        features.pair_bundle = build_event_pair_feature_bundle(
            lease, confidence_evidence=_oracle_confidence_evidence(lease),
            optional_source_counts=_oracle_optional_source_counts(features))
    bundle = features.pair_bundle
    if lease.encoded_event_features is None:
        lease.set_encoded_event_features(
            head.encode_events(bundle),
            member_ids=tuple(row.member_id for row in lease.members))
    return bundle, lease.encoded_event_features, event_member_sentence_indices(lease)


def _event_pair_inputs(target: ArticleTargets, lease: EventMemberFeatureLease,
                       occurrences: tuple[TemporalOccurrence, ...],
                       coordinates: list[tuple[int, int]], reference: torch.Tensor
                       ) -> tuple[torch.LongTensor, torch.Tensor]:
    canonical = tuple(sorted({(min(a, b), max(a, b)) for a, b in coordinates}))
    features = event_pair_policy_features(
        article=target.layout.article, members=lease.members,
        occurrences=occurrences,
        sentence_spans=lease.original_sentence_spans,
        pairs=canonical, reference=reference)
    positions = {pair: index for index, pair in enumerate(canonical)}
    rows = torch.tensor([positions[(min(a, b), max(a, b))] for a, b in coordinates],
                        dtype=torch.long, device=reference.device)
    return (torch.tensor(coordinates, dtype=torch.long, device=reference.device).reshape(-1, 2),
            features[rows])


@dataclass(frozen=True, slots=True)
class EventLossResult:
    loss: torch.Tensor
    positive_pairs: int
    negative_pairs_sampled: int
    final_clusters: int
    all_member_roles: int
    all_member_times: int


def eight_to_one_negative_quotas(
        pair_counts: dict[str, tuple[int, int]]) -> dict[str, int]:
    """Allocate exactly eight supervised KEEP samples per MERGE over one cohort.

    Every positive pair remains. Extra KEEP quota is distributed by stable article
    order, and the existing seeded reservoir chooses coordinates within each article.
    The dev cohort gets its own quotas; no test article is examined.
    """
    if not pair_counts or any(pos < 0 or neg < 0 for pos, neg in pair_counts.values()):
        raise ValueError("Event pair counts are invalid")
    target = 8 * sum(pos for pos, _ in pair_counts.values())
    if target > sum(neg for _, neg in pair_counts.values()):
        raise ValueError("Event 8:1 target exceeds supervised KEEP universe")
    quotas = {article_id: min(negative, 8 * positive)
              for article_id, (positive, negative) in pair_counts.items()}
    remaining = target - sum(quotas.values())
    ordered = sorted(pair_counts)
    while remaining:
        progressed = False
        for article_id in ordered:
            if quotas[article_id] >= pair_counts[article_id][1]:
                continue
            quotas[article_id] += 1
            remaining -= 1
            progressed = True
            if not remaining:
                break
        if not progressed:
            raise AssertionError("Event negative quota allocation stalled")
    return quotas


class EventGoldAdapter:
    def __init__(self, core: V3Core, *, negative_limit: int = 128,
                 chunk_size: int = 128) -> None:
        if any(name in core.unimplemented_tasks for name in (
                "event_coreference", "event_time", "time_normalization", "entity_coreference",
                "trigger")):
            raise ValueError("stage 5–8 Event upstream/head dependencies are missing")
        if negative_limit <= 0 or chunk_size <= 0:
            raise ValueError("Event pair sample/chunk sizes must be positive")
        self.core = core
        self.negative_limit = negative_limit
        self.chunk_size = chunk_size
        self.negative_quotas: dict[str, int] | None = None
        self.merge_weight = 1.0

    def configure_imbalance_experiment(self, negative_quotas: dict[str, int]) -> None:
        """Bind fixed Gold-only sampling quotas for the P5 8:1 comparison run."""
        if not negative_quotas or any(value < 0 for value in negative_quotas.values()):
            raise ValueError("Event negative quota map is empty or invalid")
        self.negative_quotas = dict(negative_quotas)
        self.merge_weight = 4.0

    def prepare(self, article: ValidatedGoldArticle, target: ArticleTargets,
                batch: ArticleBatch, backbone: BackboneOutput,
                shared: SharedForwardLease, *,
                include_relations: bool = False) -> EventGoldFeatures:
        if article.split not in ("train", "dev", "test") or article.raw.article_version_id != target.article_version_id:
            raise ValueError("Event Gold adapter needs a joined validated source")
        entity_oracle = build_oracle_entity_structure(article, target,
                                                      include_assertors=include_relations)
        occurrences = gold_time_occurrences(target)
        members = oracle_event_members(article, target, entity_oracle, occurrences)
        closure = oracle_event_closure(article, target, members)
        extra = []
        for row in target.spans["trigger"]:
            extra.append(("TRIGGER:" + row.owner_id, row.alignment, "TRIGGER"))
        for row in target.roles:
            extra.append(("ROLE:" + row.role_id, row.alignment, "PARTICIPANT"))
        if include_relations:
            for row in target.spans["semantic_proposer"]:
                if row.label == "STATEMENT":
                    extra.append(("STATEMENT:" + row.owner_id, row.alignment, "STATEMENT"))
            for row in target.assertors:
                if row.alignment is not None:
                    extra.append(("ASSERTOR:" + row.statement_id, row.alignment, "STATEMENT"))
        for candidate in entity_oracle.universe.candidates:
            alignment = target.layout.align({"start": candidate.start, "end": candidate.end,
                                             "text": candidate.text})
            extra.append((ENTITY_MEMBER_STATE_PREFIX + candidate.candidate_id,
                          alignment, "ENTITY"))
        time = TimeGoldAdapter(self.core).encode(target, batch, backbone, shared,
                                                 extra_rows=tuple(extra))
        if time.extra_states is None:
            time.close()
            raise RuntimeError("Entity attribution aggregation lost exact member states")
        member_states = {
            candidate.candidate_id:
            time.extra_states[ENTITY_MEMBER_STATE_PREFIX + candidate.candidate_id]
            for candidate in entity_oracle.universe.candidates}
        views = build_entity_representation_views(
            entity_oracle.closure.entities,
            member_states,
            candidate_sort_keys={
                candidate.candidate_id: (
                    candidate.start, candidate.end, candidate.text)
                for candidate in entity_oracle.universe.candidates})
        time.extra_states.update({EVENT_ENTITY_STATE_PREFIX + local_id: state
                                  for local_id, state in views.event_representative.items()})
        time.extra_states.update({ASSERTOR_ENTITY_STATE_PREFIX + local_id: state
                                  for local_id, state in views.assertor_all_member_mean.items()})
        try:
            member = build_event_member_features(
                time, members=members, occurrences=occurrences,
                provenance=EventFeatureProvenance("GOLD_ORACLE", "GOLD_ORACLE"))
        except Exception:
            time.close()
            raise
        features = EventGoldFeatures(time, member, closure, occurrences, entity_oracle)
        try:
            _event_head_inputs(features, self.core.task_modules["event_coreference"])
        except Exception:
            features.close()
            raise
        return features

    def loss(self, target: ArticleTargets, features: EventGoldFeatures) -> EventLossResult:
        lease = features.member
        if (lease.closed or lease.channel_sums is None or lease.channel_counts is None or
                lease.document_state is None or
                lease.article_version_id != target.article_version_id or
                lease.content_sha256 != target.content_sha256 or
                lease.provenance.membership_source != "GOLD_ORACLE"):
            raise ValueError("Event Gold loss needs live matching oracle member features")
        universe = target.pairs["event_coreference"]
        if tuple(row.member_id for row in lease.members) != universe.left_ids:
            raise ValueError("Event member feature order differs from Gold pair universe")
        article_id = target.article_version_id.split(":r06:", 1)[0]
        if self.negative_quotas is not None and article_id not in self.negative_quotas:
            raise ValueError("Event imbalance quota is missing for this Gold article")
        negative_limit = (self.negative_quotas[article_id]
                          if self.negative_quotas is not None else self.negative_limit)
        sample = sorted(universe.positive_pairs) + [
            (row.left_id, row.right_id) for row in universe.sample_negatives(
                limit=negative_limit, seed=self.core.config.seed,
                content_sha256=target.content_sha256)]
        index = {row.member_id: position for position, row in enumerate(lease.members)}
        head = self.core.task_modules["event_coreference"]
        bundle, encoded, sentence_indices = _event_head_inputs(features, head)
        losses = []
        for start in range(0, len(sample), self.chunk_size):
            chunk = sample[start:start + self.chunk_size]
            coordinates = [(index[a], index[b]) for a, b in chunk]
            indices, policy = _event_pair_inputs(
                target, lease, features.occurrences, coordinates, encoded)
            labels = torch.tensor([int(pair in universe.positive_pairs) for pair in chunk],
                                  dtype=torch.long, device=encoded.device)
            logits = head(bundle, encoded, sentence_indices, indices, policy)
            weight = (torch.tensor([1.0, self.merge_weight], device=encoded.device)
                      if self.negative_quotas is not None else None)
            losses.append(F.cross_entropy(logits, labels, weight=weight, reduction="sum"))
        denominator = (len(sample) - len(universe.positive_pairs) +
                       self.merge_weight * len(universe.positive_pairs))
        loss = sum(losses) / denominator if sample else lease.document_state.sum() * 0
        if not torch.isfinite(loss):
            raise ValueError("Event coreference loss is non-finite")
        return EventLossResult(loss, len(universe.positive_pairs),
                               len(sample) - len(universe.positive_pairs),
                               len(features.closure.events),
                               sum(len(row.roles) for row in features.closure.events),
                               sum(len(row.times) for row in features.closure.events))

    @torch.no_grad()
    def evaluate_full_universe(self, target: ArticleTargets,
                               features: EventGoldFeatures,
                               *, article_id: str) -> dict[str, object]:
        """Use the class-1 MERGE margin for every eligible Event-member pair."""
        lease = features.member
        if self.core.training or lease.closed or lease.channel_sums is None \
                or lease.channel_counts is None \
                or lease.document_state is None:
            raise ValueError("Event coreference selection evaluation needs a live eval lease")
        index = {row.member_id: position for position, row in enumerate(lease.members)}
        head = self.core.task_modules["event_coreference"]
        bundle, encoded, sentence_indices = _event_head_inputs(features, head)

        def scorer(chunk):
            coordinates = [(index[row.left_id], index[row.right_id]) for row in chunk]
            indices, policy = _event_pair_inputs(
                target, lease, features.occurrences, coordinates, encoded)
            logits = head(bundle, encoded, sentence_indices, indices, policy)
            return logits[:, 1] - logits[:, 0]

        return score_full_universe(
            article_id=article_id, universe=target.pairs["event_coreference"],
            chunk_size=self.chunk_size, score_chunk=scorer)
