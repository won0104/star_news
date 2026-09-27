"""Gold-free Event pair fine scoring and complete-link identity closure."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING, Sequence

import torch

from models.v3_pretraining.architecture import V3Core
from models.v3_pretraining.event_heads import EventPairFeatureBundle
from runtime.v3_pretraining.event_features import (
    EventMemberFeatureLease, build_event_pair_feature_bundle,
    event_member_sentence_indices)
from runtime.v3_pretraining.event_identity import EventClosure, close_event_identity
from runtime.v3_pretraining.event_pair_policy import event_pair_policy_features
from runtime.v3_pretraining.source_layout import RawArticle
from runtime.v3_pretraining.temporal import TemporalOccurrence

if TYPE_CHECKING:
    from runtime.v3_pretraining.pair_routing import RoutedPairs


@dataclass(frozen=True, slots=True)
class EventIdentityDecodeConfig:
    max_pairs: int = 4096
    chunk_size: int = 128
    margin_threshold: float = 0.0
    status: str = "PROVISIONAL_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        if self.max_pairs <= 0 or self.chunk_size <= 0:
            raise ValueError("Event pair budget/chunk must be positive")


@dataclass(frozen=True, slots=True)
class EventIdentityDecodeResult:
    closure: EventClosure
    scored_pairs: int
    eligible_pairs: int
    partial: bool
    policy_status: str
    accepted_pairs: int = 0
    rejected_pairs: int = 0
    raw_pair_margins: tuple[tuple[str, str, float], ...] = ()


@torch.no_grad()
def score_event_identity(article: RawArticle, lease: EventMemberFeatureLease, *,
                         core: V3Core,
                         config: EventIdentityDecodeConfig = EventIdentityDecodeConfig(),
                         strict_equivalence_pairs: frozenset[tuple[str, str]] = frozenset(),
                         routed_pairs: RoutedPairs | None = None,
                         occurrences: Sequence[TemporalOccurrence] = (),
                         sentence_spans: Sequence[tuple[int, int]] | None = None,
                         pair_bundle: EventPairFeatureBundle | None = None,
                         collect_raw_pair_margins: bool = False,
                         ) -> EventIdentityDecodeResult:
    """학습된 symmetric score 외의 관련성/시간 선후 관계를 merge 근거로 쓰지 않는다."""
    if (lease.closed or lease.channel_sums is None or lease.channel_counts is None or
            lease.document_state is None or
            lease.provenance.membership_source != "PREDICTED" or
            lease.provenance.role_source != "PREDICTED" or
            lease.article_version_id != article.article_version_id or
            lease.content_sha256 != article.content_sha256):
        raise ValueError("predicted Event scorer needs live matching source features")
    if "event_coreference" not in core.task_modules:
        raise ValueError("Event coreference head is not registered")
    head = core.task_modules["event_coreference"]
    bundle = pair_bundle or build_event_pair_feature_bundle(lease)
    if lease.encoded_event_features is None:
        if routed_pairs is not None:
            raise ValueError("routed Event pairs need every retained Event encoded before routing")
        lease.set_encoded_event_features(
            head.encode_events(bundle), member_ids=tuple(row.member_id for row in lease.members))
    encoded = lease.encoded_event_features
    sentence_indices = event_member_sentence_indices(lease)
    aligned = sum(row.aligned for row in lease.members)
    eligible_count = aligned * (aligned - 1) // 2
    selected = (tuple((a, b) for a, b in combinations(range(len(lease.members)), 2)
                      if lease.members[a].aligned and lease.members[b].aligned)[:config.max_pairs]
                if routed_pairs is None else routed_pairs.pairs)
    if routed_pairs is not None:
        from runtime.v3_pretraining.pair_routing import inventory_lineage
        lineage = inventory_lineage(
            article, tuple((row.member_id, row.start, row.end) for row in lease.members))
        if (routed_pairs.policy_id != "BCR_C_MONOTONIC_SEED_CLIQUE_V1" or
                routed_pairs.source_inventory_lineage != lineage or
                any(not 0 <= a < b < len(lease.members) or
                    not lease.members[a].aligned or not lease.members[b].aligned or
                    {record["query_id"], record["candidate_id"]} !=
                    {lease.members[a].member_id, lease.members[b].member_id}
                    for (a, b), record in zip(selected, routed_pairs.records))):
            raise ValueError("Event routed fine input differs from aligned source lease")
    sorted_pairs = tuple(sorted(selected))
    policy_features = event_pair_policy_features(
        article=article, members=lease.members, occurrences=occurrences,
        sentence_spans=(lease.original_sentence_spans if sentence_spans is None
                        else sentence_spans), pairs=sorted_pairs, reference=encoded)
    policy_index = {pair: index for index, pair in enumerate(sorted_pairs)}
    decisions = {}
    raw_pair_margins = []
    for start in range(0, len(selected), config.chunk_size):
        chunk = selected[start:start + config.chunk_size]
        indices = torch.tensor(chunk, dtype=torch.long, device=encoded.device).reshape(-1, 2)
        policy_rows = policy_features[torch.tensor(
            [policy_index[pair] for pair in chunk], dtype=torch.long,
            device=policy_features.device)]
        logits = head(
            bundle, encoded, sentence_indices, indices, policy_rows)
        if not torch.isfinite(logits).all():
            raise ValueError("Event pair scorer returned non-finite logits")
        margin_rows = (logits[:, 1] - logits[:, 0]).detach().cpu().tolist()
        if collect_raw_pair_margins:
            raw_pair_margins.extend(
                (lease.members[a].member_id, lease.members[b].member_id, float(margin))
                for (a, b), margin in zip(chunk, margin_rows))
        decisions.update({(lease.members[a].member_id, lease.members[b].member_id):
                          margin >= config.margin_threshold
                          for (a, b), margin in zip(chunk, margin_rows)})
    closure = close_event_identity(article, lease.members, pair_decisions=decisions,
                                   strict_equivalence_pairs=strict_equivalence_pairs,
                                   source_mode="PREDICTED")
    accepted_pairs = sum(decisions.values())
    return EventIdentityDecodeResult(closure, len(selected), eligible_count,
                                     len(selected) < eligible_count or closure.status in (
                                         "BOUNDED_PARTIAL", "PARTIAL_ALIGNMENT"), config.status,
                                     accepted_pairs, len(decisions) - accepted_pairs,
                                     tuple(raw_pair_margins))
