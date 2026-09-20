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
from runtime.v3_pretraining.event_features import (EventFeatureProvenance, EventMemberFeatureLease,
                                                   build_event_member_features, event_pair_geometry)
from runtime.v3_pretraining.event_identity import (EventClosure, EventMember, MemberRoleFact,
                                                   close_event_identity)
from runtime.v3_pretraining.temporal import TemporalOccurrence
from runtime.v3_pretraining.temporal_scoring import EventTimeFeatureLease
from training.v3_pretraining.entity import OracleEntityStructure, build_oracle_entity_structure
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

    def close(self) -> None:
        self.member.close()
        self.time.close()

    def __enter__(self) -> "EventGoldFeatures":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class EventLossResult:
    loss: torch.Tensor
    positive_pairs: int
    negative_pairs_sampled: int
    final_clusters: int
    all_member_roles: int
    all_member_times: int


class EventGoldAdapter:
    def __init__(self, core: V3Core, *, negative_limit: int = 128,
                 chunk_size: int = 128) -> None:
        if any(name in core.unimplemented_tasks for name in (
                "event_coreference", "event_time", "time_normalization", "entity_coreference",
                "role_entity", "trigger")):
            raise ValueError("stage 5–8 Event upstream/head dependencies are missing")
        if negative_limit <= 0 or chunk_size <= 0:
            raise ValueError("Event pair sample/chunk sizes must be positive")
        self.core = core
        self.negative_limit = negative_limit
        self.chunk_size = chunk_size

    def prepare(self, article: ValidatedGoldArticle, target: ArticleTargets,
                batch: ArticleBatch, backbone: BackboneOutput,
                shared: SharedForwardLease, *,
                include_relations: bool = False) -> EventGoldFeatures:
        if article.split != "train" or article.raw.article_version_id != target.article_version_id:
            raise ValueError("Event Gold adapter needs joined train source")
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
        candidates = entity_oracle.universe.candidate_by_id()
        for entity in entity_oracle.closure.entities:
            candidate = candidates[entity.representative_candidate_id]
            alignment = target.layout.align({"start": candidate.start, "end": candidate.end,
                                             "text": candidate.text})
            extra.append(("ENTITY:" + entity.local_id, alignment, "ENTITY"))
        time = TimeGoldAdapter(self.core).encode(target, batch, backbone, shared,
                                                 extra_rows=tuple(extra))
        try:
            member = build_event_member_features(
                time, members=members, occurrences=occurrences,
                head=self.core.task_modules["event_coreference"],
                provenance=EventFeatureProvenance("GOLD_ORACLE", "GOLD_ORACLE"))
        except Exception:
            time.close()
            raise
        return EventGoldFeatures(time, member, closure, occurrences, entity_oracle)

    def loss(self, target: ArticleTargets, features: EventGoldFeatures) -> EventLossResult:
        lease = features.member
        if (lease.closed or lease.member_states is None or lease.document_state is None or
                lease.article_version_id != target.article_version_id or
                lease.content_sha256 != target.content_sha256 or
                lease.provenance.membership_source != "GOLD_ORACLE"):
            raise ValueError("Event Gold loss needs live matching oracle member features")
        universe = target.pairs["event_coreference"]
        if tuple(row.member_id for row in lease.members) != universe.left_ids:
            raise ValueError("Event member feature order differs from Gold pair universe")
        sample = sorted(universe.positive_pairs) + [
            (row.left_id, row.right_id) for row in universe.sample_negatives(
                limit=self.negative_limit, seed=self.core.config.seed,
                content_sha256=target.content_sha256)]
        index = {row.member_id: position for position, row in enumerate(lease.members)}
        losses = []
        for start in range(0, len(sample), self.chunk_size):
            chunk = sample[start:start + self.chunk_size]
            coordinates = [(index[a], index[b]) for a, b in chunk]
            indices = torch.tensor(coordinates, dtype=torch.long, device=lease.member_states.device)
            labels = torch.tensor([int(pair in universe.positive_pairs) for pair in chunk],
                                  dtype=torch.long, device=lease.member_states.device)
            logits = self.core.task_modules["event_coreference"](
                lease.member_states, indices, lease.document_state,
                event_pair_geometry(lease.members, coordinates,
                                    content_length=len(target.layout.article.content),
                                    reference=lease.member_states))
            losses.append(F.cross_entropy(logits, labels, reduction="sum"))
        loss = sum(losses) / len(sample) if sample else lease.document_state.sum() * 0
        if not torch.isfinite(loss):
            raise ValueError("Event coreference loss is non-finite")
        return EventLossResult(loss, len(universe.positive_pairs),
                               len(sample) - len(universe.positive_pairs),
                               len(features.closure.events),
                               sum(len(row.roles) for row in features.closure.events),
                               sum(len(row.times) for row in features.closure.events))
