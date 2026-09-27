"""V23 source-ID adaptation for the verified v2.3 scalar pair routers.

Only candidate selection and scalar provenance live here. The existing v3
PairContext heads, acceptance, and clustering consume selected IDs separately.
"""

from __future__ import annotations

from collections import Counter
from bisect import bisect_left
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import json
from types import SimpleNamespace
from typing import Mapping, Sequence

from runtime.candidate_routing.event_blocks import EventSignals
from runtime.candidate_routing.event_monotonic import (_keys as event_route_keys,
                                                      _postings as event_postings,
                                                      route_monotonic_events)
from runtime.candidate_routing.integrated import IntegratedBoundedPolicies
from runtime.candidate_routing.participant_entity import (
    BoundedRescueIndex, FEATURE as PARTICIPANT_FEATURE,
    ParticipantEntityBoundedSession, ParticipantEntitySelection,
    ROLE_TYPE_PRIOR, _alias_key, _grams, _span_bins, participant_route_keys,
)
from runtime.candidate_routing.core import (
    ArticleCandidateIndex, BudgetRouter, IndexedCandidate, RequestBudget,
    nested_tier_prefix,
)
from runtime.v3_pretraining.entity_identity import EntityClosure
from runtime.v3_pretraining.entity_pair_blocking import (
    EntityAllPairShadowReference, EntityPairPolicy, POLICY_ID as ENTITY_BLOCK_POLICY_ID,
    block_entity_pairs,
)
from runtime.v3_pretraining.entity_union import EntityCandidate, RoleBinding
from runtime.candidate_routing.temporal import TemporalBoundedSession
from runtime.v3_pretraining.event_identity import EventMember
from runtime.v3_pretraining.source_layout import RawArticle
from runtime.v3_pretraining.temporal import TemporalOccurrence
from runtime.v3_pretraining.temporal_scoring import EventTimeFeatureLease


def inventory_lineage(article: RawArticle, rows: Sequence[tuple[str, int, int]]) -> str:
    """Bind a scalar inventory to one article without reading model or Gold state."""
    if len({row[0] for row in rows}) != len(rows) or any(
            not 0 <= start < end <= len(article.content)
            for _, start, end in rows):
        raise ValueError("pair routing source inventory has duplicate or invalid coordinates")
    return inventory_lineage_values(article.article_version_id,
                                    article.content_sha256, rows)


def inventory_lineage_values(article_version_id: str, content_sha256: str,
                             rows: Sequence[tuple[str, int, int]]) -> str:
    """Recompute a live lease's scalar lineage without retaining article text."""
    material = (article_version_id, content_sha256, tuple(rows))
    return sha256(json.dumps(material, ensure_ascii=False,
                            separators=(",", ":")).encode()).hexdigest()


def _sentence(spans: Sequence[tuple[int, int]], start: int) -> int:
    result = next((index for index, (left, right) in enumerate(spans)
                   if left <= start < right), None)
    if result is None:
        raise ValueError("pair source has no containing sentence")
    return result


@dataclass(frozen=True, slots=True)
class RoutedPairs:
    """Selected fine inputs; per-pair trace is optional in PUBLIC-only execution."""

    pairs: tuple[tuple[int, int], ...]
    records: tuple[dict, ...]
    policy_id: str
    policy_sha256: str
    source_inventory_lineage: str
    visited: int
    budget_exhausted_queries: int
    naive_pair_count: int
    missing_pair_status: str = "NOT_EVALUATED"
    rescue_status: str | None = None
    shadow_reference_policy_id: str | None = None
    query_count: int = 0
    retrieved_candidate_mentions: int = 0
    primary_candidate_mentions: int = 0
    records_materialized: bool = True

    def __post_init__(self) -> None:
        if (self.records_materialized and (
                len(self.pairs) != len(self.records) or
                len(set(self.pairs)) != len(self.pairs)) or
                not self.records_materialized and (
                    self.records or
                    any(left >= right for left, right in self.pairs) or
                    any(previous >= current for previous, current in
                        zip(self.pairs, self.pairs[1:])))):
            raise ValueError("selected pair trace and fine inputs differ")
        if (len(self.policy_sha256) != 64 or len(self.source_inventory_lineage) != 64 or
                any(row.get("policy_id") != self.policy_id or
                    row.get("policy_sha256") != self.policy_sha256 or
                    row.get("source_inventory_lineage") != self.source_inventory_lineage or
                    row.get("routing_status") != "SELECTED_FOR_FINE_SCORING" or
                    "fine_status" in row
                    for row in self.records)):
            raise ValueError("selected pair policy/lineage/status trace differs")

    def routing_status(self, pair: tuple[int, int]) -> str:
        return ("SELECTED_FOR_FINE_SCORING" if pair in self.pairs else
                self.missing_pair_status)


NATIVE_BOUNDARY_RESCUE_POLICY_ID = "V3_NATIVE_ENTITY_BOUNDARY_RESCUE_SHADOW_V1"


def native_boundary_rescue_policy_sha256() -> str:
    """Bind the v3-only source-coordinate adaptation, separate from v2.3 promotion."""
    return sha256((NATIVE_BOUNDARY_RESCUE_POLICY_ID +
                   ":native-ner;same-sentence;strict-overlap;different-boundary;"
                   "source-order;posting64;failure-only;fine16").encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class NativeBoundaryRescueSelection:
    candidate_ids: tuple[str, ...]
    visited: int
    posting_exhausted: bool
    fine_exhausted: bool
    policy_sha256: str


class V3NativeBoundaryRescueIndex:
    """Shadow-only v3 native Entity boundary alternatives for failed B2 fillers.

    Candidate identity/coordinates and v3 closure are unchanged. This index is
    source-only and does not recreate release promotion tiers or family owners.
    """

    def __init__(self, candidates: Sequence[EntityCandidate],
                 sentence_spans: Sequence[tuple[int, int]]) -> None:
        grouped: dict[int, list[EntityCandidate]] = {}
        for row in candidates:
            if "NER" in row.origins:
                grouped.setdefault(_sentence(sentence_spans, row.start), []).append(row)
        self.rows = {sentence: tuple(sorted(members, key=lambda row: (
            row.start, row.end, row.candidate_id)))
                     for sentence, members in grouped.items()}
        self.starts = {sentence: tuple(row.start for row in members)
                       for sentence, members in self.rows.items()}
        self.max_width = {sentence: max(row.end - row.start for row in members)
                          for sentence, members in self.rows.items()}

    def bounded_session_rows(self) -> dict[int, list[dict]]:
        """Adapt native coordinates to the release K16 request-budget index."""
        return {sentence: [{"prediction_id": row.candidate_id,
                            "source_family_id": f"V3_NATIVE:{row.candidate_id}",
                            "char_start": row.start, "char_end": row.end}
                           for row in members]
                for sentence, members in self.rows.items()}

    def retrieve_failed(self, binding: RoleBinding, *, sentence_index: int,
                        primary_ids: frozenset[str],
                        posting_visit_budget: int = 64,
                        fine_budget: int = 16) -> NativeBoundaryRescueSelection:
        """Visit overlapping native alternatives only after PRIMARY fine failure."""
        if posting_visit_budget <= 0 or fine_budget <= 0:
            raise ValueError("rescue budgets must be positive")
        rows = self.rows.get(sentence_index, ())
        if not rows:
            return NativeBoundaryRescueSelection((), 0, False, False,
                                                  native_boundary_rescue_policy_sha256())
        cursor = bisect_left(self.starts[sentence_index],
                             binding.start - self.max_width[sentence_index])
        visited = 0
        matched: list[str] = []
        while cursor < len(rows) and rows[cursor].start < binding.end:
            if visited == posting_visit_budget:
                break
            row = rows[cursor]
            cursor += 1
            visited += 1
            if (row.candidate_id not in primary_ids and
                    (row.start, row.end) != (binding.start, binding.end) and
                    row.start < binding.end and binding.start < row.end):
                matched.append(row.candidate_id)
        return NativeBoundaryRescueSelection(
            tuple(matched[:fine_budget]), visited,
            cursor < len(rows) and rows[cursor].start < binding.end,
            len(matched) > fine_budget, native_boundary_rescue_policy_sha256())

ENTITY_SEMANTIC_ADAPTER = "V3_ENTITY_SEMANTIC_ADAPTATION_V1"
PARTICIPANT_SCALAR_ADAPTER = "V3_PARTICIPANT_SCALAR_NO_PROMOTION_V2"
ENTITY_ROUTER_ADAPTER = "V3_UNIFIED_NATIVE_ROLE_UNKNOWN_BLOCKING_V1"


def entity_semantic_adapter_sha256() -> str:
    """Bind the deliberate absence of v2.3 promotion tiers to phase manifests."""
    return sha256((ENTITY_SEMANTIC_ADAPTER +
                   ":all-v3-typed-pairs;all-active-participant-targets;"
                   "neutral-promotion;v3-closure-unchanged").encode()).hexdigest()


def participant_scalar_adapter_sha256(salience_mode: str = "SOURCE_SCORE") -> str:
    if salience_mode not in ("SOURCE_SCORE", "BALANCED_ORIGIN_TYPE"):
        raise ValueError("unknown v3 Participant global reserve mode")
    return sha256((PARTICIPANT_SCALAR_ADAPTER +
                   ":alias;substring;overlap;sentence;role-type;source-score;"
                   "no-promotion;salience=" + salience_mode).encode()).hexdigest()


def entity_router_adapter_sha256() -> str:
    return sha256((ENTITY_ROUTER_ADAPTER +
                   ":source-lexical-local-type-union;type-cue-not-filter;"
                   "native-role-exact-use;unknown-role-no-type-posting;"
                   "single-complete-link-closure").encode()).hexdigest()


def entity_all_pair_shadow_sha256() -> str:
    return sha256((EntityAllPairShadowReference(0).policy_id +
                   ":all-v3-typed-candidate-pairs;no-selection;"
                   "audit-only").encode()).hexdigest()


def v3_participant_entity_coarse_score(item: dict, query: dict) -> float:
    """Rank with present v3 scalars; no v2.3 promotion or entity_priority."""
    left, right = query["text_norm"], item["text_norm"]
    overlap = max(query["char_start"], item["char_start"]) < min(
        query["char_end"], item["char_end"])
    distance = abs(query["sentence_index"] - item["sentence_index"])
    return (4.0 * float(bool(left and left == right)) +
            1.5 * float(bool(left and right and (left in right or right in left))) +
            2.0 * float(overlap) +
            0.7 * float(distance == 0) + 0.25 * float(distance == 1) +
            0.10 * float(distance == 2) +
            0.20 * float(item["entity_type"] in ROLE_TYPE_PRIOR[query["role"]]) +
            0.10 * float(item["entity_score"]))


class _V3ParticipantSession(ParticipantEntityBoundedSession):
    """Reuse release route topology/budgets with v3-only index and cheap rank."""

    def __init__(self, contract, catalog, version, content_hash, query_count,
                 *, salience_mode: str) -> None:
        if salience_mode not in ("SOURCE_SCORE", "BALANCED_ORIGIN_TYPE"):
            raise ValueError("unknown v3 Participant global reserve mode")
        self.contract = contract
        self.entity_inventory_lineage = None
        self.by_id = {row["prediction_id"]: row for row in catalog}
        if len(self.by_id) != len(catalog):
            raise ValueError("v3 Entity candidate IDs are not unique")
        self.gram_frequency = Counter(
            gram for row in catalog for gram in _grams(row["text_norm"]))
        ranked = sorted(catalog, key=lambda row: (-row["entity_score"], row["prediction_id"]))
        if salience_mode == "BALANCED_ORIGIN_TYPE":
            ranked = self._balanced_rank(catalog)
        selected: set[str] = set()
        cluster_counts: dict[str, int] = {}
        for row in ranked:
            cluster = str(row["cluster_index"])
            if cluster_counts.get(cluster, 0) >= 2:
                continue
            selected.add(row["prediction_id"])
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
            if len(selected) == 64:
                break
        index_rows = []
        for item in catalog:
            sentence = int(item["sentence_index"])
            keys = [f"local:sentence:{sentence}",
                    f"0:near:sentence:{sentence}", f"1:near:sentence:{sentence}"]
            keys += [f"local:overlap:{sentence}:{bin_id}"
                     for bin_id in _span_bins(item["char_start"], item["char_end"])]
            if item["text_norm"]:
                keys.append(_alias_key(item["text_norm"]))
                keys += [f"2:global:ngram:{self.gram_frequency[gram]:06d}:{gram}"
                         for gram in _grams(item["text_norm"])]
            if item["prediction_id"] in selected:
                keys.append("1:global:salience:top64")
            index_rows.append(IndexedCandidate(
                item["prediction_id"], version, content_hash,
                PARTICIPANT_FEATURE, "ENTITY", int(item["char_start"]),
                int(item["char_end"]), "V3_ENTITY_CANDIDATE",
                tuple(sorted(set(keys))), item["entity_type"],
                (("entity_score", float(item["entity_score"])),
                 ("sentence_index", sentence), ("text_norm", item["text_norm"]),
                 ("origin_group", item["origin_group"])),
                str(item["cluster_index"])))
        self.index = ArticleCandidateIndex(index_rows, article_version_id=version,
                                           content_sha256=content_hash)
        policy = contract.retrieval_policy(query_count)
        self.router = BudgetRouter(policy, self.index,
                                   request=RequestBudget(policy.request_budget))
        self.rescue_index = BoundedRescueIndex({})
        self.remaining_queries = query_count
        self._closed = False
        self.cache_key = sha256(json.dumps(
            {"policy_sha256": contract.manifest_sha256,
             "adapter_sha256": participant_scalar_adapter_sha256(salience_mode),
             "version": version, "content_hash": content_hash,
             "catalog": [(row["prediction_id"], row["entity_type"],
                          row["char_start"], row["char_end"], row["entity_score"],
                          row["cluster_index"], row["origin_group"]) for row in catalog]},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def _balanced_rank(catalog: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in catalog:
            grouped.setdefault((row["origin_group"], row["entity_type"] or "UNTYPED"), []).append(row)
        for rows in grouped.values():
            rows.sort(key=lambda row: (-row["entity_score"], row["prediction_id"]))
        ranked: list[dict] = []
        groups = sorted(grouped)
        while len(ranked) < len(catalog):
            changed = False
            for group in groups:
                if not grouped[group]:
                    continue
                ranked.append(grouped[group].pop(0))
                changed = True
            if not changed:
                break
        return ranked

    def route(self, filler: dict) -> ParticipantEntitySelection:
        if self._closed or self.remaining_queries <= 0:
            raise RuntimeError("bounded session has no remaining filler query")
        query = {
            "article_version_id": self.index.article_version_id,
            "content_sha256": self.index.content_sha256,
            "query_key": filler["participant_evidence_id"],
            "sentence_index": int(filler["sentence_index"]),
            "char_start": int(filler["char_start"]),
            "char_end": int(filler["char_end"]),
            "text_norm": "".join(str(filler["text"]).casefold().split()),
            "role": filler["role"],
        }
        keys = participant_route_keys(query, self.gram_frequency)
        decision = self.router.route(
            keys, lambda row, _keys: v3_participant_entity_coarse_score(
                self.by_id[row.candidate_id], query))
        ids, tiers = nested_tier_prefix(decision, self.contract.selected_tiers)
        self.remaining_queries -= 1
        return ParticipantEntitySelection(ids, tiers, decision)


def route_entity_coreference(*, article: RawArticle,
                             candidates: Sequence[EntityCandidate],
                             source_lineage: str,
                             policies: IntegratedBoundedPolicies,
                             sentence_spans: Sequence[tuple[int, int]] | None = None,
                             entity_policy: EntityPairPolicy | None = None,
                             shadow_all_pairs: bool = False,
                             materialize_records: bool = True) -> RoutedPairs:
    """Route v3 cross-type/GENERIC pairs; all-pair remains explicit audit mode."""
    rows = tuple((row.candidate_id, row.start, row.end) for row in candidates)
    if source_lineage != inventory_lineage(article, rows):
        raise ValueError("Entity coreference pair inventory lineage differs")
    if any(candidate.entity_type is None and "ROLE" not in candidate.origins
           for candidate in candidates):
        raise ValueError("only ROLE mentions may be internally UNKNOWN before coreference")
    if (entity_policy is None) != shadow_all_pairs:
        raise ValueError("Entity router requires one selected policy or explicit all-pair shadow")
    if entity_policy is not None:
        if sentence_spans is None:
            raise ValueError("Entity blocking requires source sentence spans")
        blocked = block_entity_pairs(article=article, candidates=candidates,
                                     sentence_spans=sentence_spans,
                                     policy=entity_policy,
                                     materialize_routes=materialize_records)
        policy_sha = entity_policy.sha256
        adapter_sha = entity_router_adapter_sha256()
        records = tuple({
            "query_id": candidates[query].candidate_id,
            "candidate_id": candidates[target].candidate_id,
            "routing_lane": "ENTITY_COREFERENCE",
            "route_tier": channel,
            "matched_route_key": key, "cheap_score": score,
            "candidate_rank": rank,
            "routing_status": "SELECTED_FOR_FINE_SCORING",
            "policy_id": ENTITY_BLOCK_POLICY_ID,
            "policy_sha256": policy_sha,
            "source_inventory_lineage": source_lineage,
            "semantic_adapter": "V3_UNKNOWN_ROLE_TYPE_IS_NOT_A_FILTER",
            "semantic_adapter_sha256": adapter_sha,
        } for query, target, channel, key, score, rank in blocked.routes)
        shadow = EntityAllPairShadowReference(len(candidates))
        return RoutedPairs(blocked.pairs, records, ENTITY_BLOCK_POLICY_ID,
                           policy_sha, source_lineage,
                           blocked.visited, blocked.exhausted_queries,
                           shadow.pair_count,
                           shadow_reference_policy_id=shadow.policy_id,
                           records_materialized=materialize_records)
    if not materialize_records:
        raise ValueError("all-pair shadow requires explicit route records")
    pairs = []
    records = []
    shadow_policy_id = EntityAllPairShadowReference(len(candidates)).policy_id
    adapter_sha = entity_all_pair_shadow_sha256()
    for left, right in combinations(range(len(candidates)), 2):
        pairs.append((left, right))
        records.append({"query_id": candidates[left].candidate_id,
                        "candidate_id": candidates[right].candidate_id,
                        "routing_lane": "ENTITY_COREFERENCE",
                        "route_tier": "V3_ALL_TYPED",
                        "matched_route_key": "ARTICLE_ENTITY_INVENTORY",
                        "cheap_score": 0.0, "candidate_rank": len(records) + 1,
                        "routing_status": "SELECTED_FOR_FINE_SCORING",
                        "policy_id": shadow_policy_id,
                        "policy_sha256": adapter_sha,
                        "source_inventory_lineage": source_lineage,
                        "semantic_adapter": ENTITY_SEMANTIC_ADAPTER})
    count = len(candidates)
    return RoutedPairs(tuple(pairs), tuple(records), shadow_policy_id,
                       adapter_sha, source_lineage, len(pairs), 0,
                       count * (count - 1) // 2)


def v3_participant_entity_catalog(
        candidates: Sequence[EntityCandidate], preliminary: EntityClosure,
        sentence_spans: Sequence[tuple[int, int]]) -> tuple[list[dict], dict[str, int]]:
    """Use one scalar catalog shape for normal routing and resolution-first shadow."""
    cluster_index = {entity.local_id: index
                     for index, entity in enumerate(preliminary.entities)}
    catalog = []
    for row in candidates:
        cluster = preliminary.candidate_to_entity.get(row.candidate_id)
        if cluster is None:
            continue
        catalog.append({"prediction_id": row.candidate_id,
                        "entity_type": row.entity_type,
                        "sentence_index": _sentence(sentence_spans, row.start),
                        "char_start": row.start, "char_end": row.end,
                        "text_norm": "".join(row.text.casefold().split()),
                        "entity_score": float(row.score),
                        "origin_group": ("NER" if "NER" in row.origins else
                                         "ROLE" if "ROLE" in row.origins else
                                         "ASSERTOR" if "ASSERTOR" in row.origins else
                                         "OTHER"),
                        "cluster_index": cluster_index[cluster]})
    return catalog, cluster_index


def route_participant_entities(*, article: RawArticle,
                               candidates: Sequence[EntityCandidate],
                               bindings: Sequence[RoleBinding],
                               preliminary: EntityClosure,
                               sentence_spans: Sequence[tuple[int, int]],
                               policies: IntegratedBoundedPolicies,
                               source_lineage: str,
                               active_evidence_ids: frozenset[str],
                               salience_mode: str = "SOURCE_SCORE"
                               ) -> RoutedPairs:
    """Use the release K64 retrieval / K32 primary mention selection.

    The v3 graph resolves selected mentions to Entity clusters at the fine scorer
    boundary. All active v3 candidates are eligible; no promotion tier is inferred.
    Original v2.3 RESCUE_ONLY families do not exist in this schema.
    """
    rows = (tuple((row.candidate_id, row.start, row.end) for row in candidates) +
            tuple((row.evidence_id, row.start, row.end) for row in bindings))
    if source_lineage != inventory_lineage(article, rows):
        raise ValueError("Participant pair inventory lineage differs")
    adapted_policy_sha = sha256((policies.config_sha256 +
                                 participant_scalar_adapter_sha256(salience_mode)).encode()).hexdigest()
    catalog, cluster_index = v3_participant_entity_catalog(
        candidates, preliminary, sentence_spans)
    active = [(index, row) for index, row in enumerate(bindings)
              if row.role in ("ACTOR", "TARGET", "PLACE") and
              row.status == "CANDIDATE" and row.evidence_id in active_evidence_ids]
    session = _V3ParticipantSession(
        policies.participant_entity, catalog, article.article_version_id,
        article.content_sha256, len(active), salience_mode=salience_mode)
    pairs = []
    records = []
    visited = exhausted = retrieved = primary = 0
    try:
        for binding_index, binding in active:
            filler = {"participant_evidence_id": binding.evidence_id,
                      "sentence_index": _sentence(sentence_spans, binding.start),
                      "char_start": binding.start, "char_end": binding.end,
                      "text": binding.text, "role": binding.role}
            result = session.route(filler)
            retrieved += len(result.decision.selected_candidate_ids)
            primary += len(result.selected_candidate_ids)
            query = {"article_version_id": article.article_version_id,
                     "content_sha256": article.content_sha256,
                     "query_key": binding.evidence_id,
                     "sentence_index": filler["sentence_index"],
                     "char_start": filler["char_start"],
                     "char_end": filler["char_end"],
                     "text_norm": "".join(binding.text.casefold().split()),
                     "role": binding.role}
            keys = participant_route_keys(query, session.gram_frequency)
            selected_clusters: set[str] = set()
            for rank, candidate_id in enumerate(result.selected_candidate_ids, 1):
                item = session.by_id[candidate_id]
                cluster_id = preliminary.candidate_to_entity[candidate_id]
                if cluster_id in selected_clusters:
                    continue
                selected_clusters.add(cluster_id)
                tier = next(tier for tier in ("LOCAL", "NEAR", "GLOBAL")
                            if candidate_id in result.tier_selected_ids[tier])
                matched = next((key for key in keys.keys(tier)
                                if key in session.index.row(candidate_id).bucket_keys), "")
                if not matched:
                    raise ValueError("Participant selected pair lacks a matched route key")
                pairs.append((binding_index, cluster_index[cluster_id]))
                records.append({"query_id": binding.evidence_id,
                                "candidate_id": cluster_id,
                                "candidate_mention_id": candidate_id,
                                "routing_lane": "PARTICIPANT_ENTITY",
                                "route_tier": tier, "matched_route_key": matched,
                                "cheap_score": v3_participant_entity_coarse_score(item, query),
                                "candidate_rank": rank,
                                "routing_status": "SELECTED_FOR_FINE_SCORING",
                                "policy_id": policies.participant_entity.policy_id,
                                "policy_sha256": adapted_policy_sha,
                                "source_inventory_lineage": source_lineage,
                                "global_reserve_mode": salience_mode,
                                "semantic_adapter": PARTICIPANT_SCALAR_ADAPTER,
                                "semantic_adapter_sha256":
                                participant_scalar_adapter_sha256(salience_mode)})
            session.record_and_release(binding.evidence_id,
                                       len(selected_clusters))
            visited += result.decision.visited
            exhausted += int(result.decision.budget_exhausted)
    finally:
        session.close()
    return RoutedPairs(tuple(pairs), tuple(records),
                       policies.participant_entity.policy_id,
                       adapted_policy_sha, source_lineage, visited, exhausted,
                       len(active) * len(catalog),
                       rescue_status="UNAVAILABLE_V3_SCHEMA",
                       query_count=len(active),
                       retrieved_candidate_mentions=retrieved,
                       primary_candidate_mentions=primary)


def route_event_time(*, article: RawArticle, lease: EventTimeFeatureLease,
                     sentence_spans: Sequence[tuple[int, int]],
                     time_scores: Mapping[str, float],
                     policies: IntegratedBoundedPolicies,
                     source_lineage: str,
                     audit_oracle_source: bool = False,
                     include_diagnostics: bool = True) -> RoutedPairs:
    """Use the release LOCAL 8 / NEAR 8 / GLOBAL 64 K80 router."""
    expected_source_mode = "GOLD_ORACLE" if audit_oracle_source else "PREDICTED"
    if (lease.closed or lease.source_mode != expected_source_mode or
            (lease.article_version_id, lease.content_sha256) !=
            (article.article_version_id, article.content_sha256)):
        raise ValueError("Event-Time pair router requires matching predicted features")
    rows = (tuple((key, *span) for key, span in zip(lease.event_ids, lease.event_spans)) +
            tuple((key, *span) for key, span in zip(lease.time_ids, lease.time_spans)))
    if source_lineage != inventory_lineage(article, rows):
        raise ValueError("Event-Time pair inventory lineage differs")
    if set(time_scores) != set(lease.time_ids):
        raise ValueError("Time routing scores differ from source inventory")
    prepared = SimpleNamespace(article=article,
                               sentences=tuple({"sentence_index": index, "start": start,
                                                "end": end}
                                               for index, (start, end) in enumerate(sentence_spans)))
    events = tuple({"prediction_id": key, "char_start": start, "char_end": end,
                    "sentence_index": _sentence(sentence_spans, start)}
                   for key, (start, end) in zip(lease.event_ids, lease.event_spans))
    times = tuple({"prediction_id": key, "char_start": start, "char_end": end,
                   "sentence_index": _sentence(sentence_spans, start),
                   "score": float(time_scores[key])}
                  for key, (start, end) in zip(lease.time_ids, lease.time_spans))
    selected: list[tuple[int, int]] = []
    records: list[dict] = []
    visited = exhausted = 0
    session = TemporalBoundedSession(policies.event_time, prepared, events, times)
    try:
        for event_index, event in enumerate(events):
            decision = session.route(event)
            ids = decision.selected_candidate_ids
            counts = dict(decision.route_counts)
            tiers = (("LOCAL", counts["LOCAL"]), ("NEAR", counts["NEAR"]),
                     ("GLOBAL", counts["GLOBAL"]))
            tier_by_position = [tier for tier, count in tiers for _ in range(count)]
            if len(tier_by_position) != len(ids):
                raise ValueError("Time route tier counts differ from selected IDs")
            for rank, (candidate_id, tier) in enumerate(zip(ids, tier_by_position), 1):
                time_index = session._time_index_by_id[candidate_id]
                selected.append((event_index, time_index))
                if not include_diagnostics:
                    # Fine input identity is still checked without retaining
                    # matched keys, scalar scores, or ranking diagnostics.
                    records.append({"query_id": event["prediction_id"],
                                    "candidate_id": candidate_id,
                                    "routing_status": "SELECTED_FOR_FINE_SCORING",
                                    "policy_id": policies.event_time.policy_id,
                                    "policy_sha256": policies.config_sha256,
                                    "source_inventory_lineage": source_lineage})
                    continue
                item = times[time_index]
                key = (("local:clause:" + str(item["sentence_index"]) + ":" +
                        str(session._clause(item["sentence_index"], item["char_start"])))
                       if tier == "LOCAL" and item["sentence_index"] ==
                       event["sentence_index"] and
                       session._clause(item["sentence_index"], item["char_start"]) ==
                       session._clause(event["sentence_index"], event["char_start"])
                       else "local:sentence:" + str(item["sentence_index"])
                       if tier == "LOCAL" else
                       "near:sentence:" + str(item["sentence_index"])
                       if tier == "NEAR" else "global:finite-time-score-top64")
                records.append({"query_id": event["prediction_id"],
                                "candidate_id": candidate_id,
                                "routing_lane": "EVENT_TIME", "route_tier": tier,
                                "matched_route_key": key,
                                "cheap_score": (2.0 * float(item["char_start"] >= event["char_start"]
                                                            and item["char_end"] <= event["char_end"])
                                                + 0.6 * float(item["sentence_index"] ==
                                                              event["sentence_index"])
                                                + 0.2 * float(abs(item["sentence_index"] -
                                                                  event["sentence_index"]) <= 2)
                                                + 0.4 * item["score"]
                                                - min(1.0, abs(item["char_start"] -
                                                               event["char_start"]) / 10000.0)),
                                "candidate_rank": rank,
                                "routing_status": "SELECTED_FOR_FINE_SCORING",
                                "policy_id": policies.event_time.policy_id,
                                "policy_sha256": policies.config_sha256,
                                "source_inventory_lineage": source_lineage})
            session.record_and_release(event["prediction_id"], len(ids))
            visited += decision.visited
            exhausted += int(decision.budget_exhausted)
    finally:
        session.close()
    return RoutedPairs(tuple(selected), tuple(records), policies.event_time.policy_id,
                       policies.config_sha256, source_lineage, visited, exhausted,
                       len(events) * len(times))


def route_event_coreference(*, article: RawArticle, members: Sequence[EventMember],
                            occurrences: Sequence[TemporalOccurrence],
                            sentence_spans: Sequence[tuple[int, int]],
                            policies: IntegratedBoundedPolicies,
                            source_lineage: str) -> RoutedPairs:
    """Reuse the release five-channel seed and bounded clique completion."""
    rows = tuple((row.member_id, row.start, row.end) for row in members)
    if source_lineage != inventory_lineage(article, rows):
        raise ValueError("Event coreference pair inventory lineage differs")
    by_time = {row.local_id: row for row in occurrences}
    signals = []
    for member in members:
        if not member.aligned:
            continue
        roles = tuple(frozenset(role.entity_id for role in member.roles
                                if role.role == name and role.entity_id is not None)
                      for name in ("ACTOR", "TARGET", "PLACE"))
        time_rows = [by_time[time_id] for time_id in member.time_ids]
        available = {"event_text", "sentence"}
        if member.trigger_text:
            available.add("trigger")
        if any(roles):
            available.add("resolved_entity")
        if time_rows:
            available.add("time")
        signals.append(EventSignals(
            member.member_id, _sentence(sentence_spans, member.start), member.text,
            0.0, member.trigger_text or "", roles, ((), (), ()),
            frozenset(row.normalized_value for row in time_rows
                      if row.normalized_value is not None),
            frozenset(member.time_ids), frozenset(available)))
    routed = route_monotonic_events(tuple(signals), policies.event_identity.router_policy)
    signals_by_id = {row.event_id: row for row in signals}
    posting_keys = {row.event_id: frozenset(event_postings((row,)))
                    for row in signals}

    def matched_key(left: str, right: str) -> str:
        if (left, right) not in routed.seed_pairs:
            return "BOUNDED_CLIQUE"
        for channel in ("LOCAL", "LEXICAL", "TRIGGER", "ENTITY", "TEMPORAL"):
            keys = ((set(event_route_keys(signals_by_id[left], channel)) & posting_keys[right]) |
                    (set(event_route_keys(signals_by_id[right], channel)) & posting_keys[left]))
            if keys:
                kind, value = min(keys, key=lambda key: str(key))
                return f"{channel}:{kind}:{value}"
        raise ValueError("Event seed pair lost its scalar posting key")

    index = {row.member_id: position for position, row in enumerate(members)}
    pairs = tuple(tuple(sorted((index[a], index[b])))
                  for a, b in sorted(routed.selected_pairs))
    records = tuple({"query_id": a, "candidate_id": b,
                     "routing_lane": "EVENT_COREFERENCE",
                     "route_tier": ("SEED" if (a, b) in routed.seed_pairs else "COMPLETION"),
                     "matched_route_key": matched_key(a, b),
                     "route_channels": routed.provenance.get((a, b), ()),
                     "cheap_score": float(-rank), "candidate_rank": rank,
                     "cheap_score_semantics": "V23_BLOCK_RANK_ORDINAL_NOT_FINE_LOGIT",
                     "routing_status": "SELECTED_FOR_FINE_SCORING",
                     "policy_id": policies.event_identity.policy_id,
                     "policy_sha256": policies.event_identity.config_sha256,
                     "source_inventory_lineage": source_lineage}
                    for rank, (a, b) in enumerate(sorted(routed.selected_pairs), 1))
    return RoutedPairs(pairs, records, policies.event_identity.policy_id,
                       policies.event_identity.config_sha256, source_lineage,
                       sum(routed.census["channel_posting_visits"].values()),
                       int(bool(routed.census["channel_visit_or_quota_exhaustion"])) +
                       int(routed.census["completion_skipped_by_budget"] > 0),
                       routed.census["full_possible_pair_count"])
