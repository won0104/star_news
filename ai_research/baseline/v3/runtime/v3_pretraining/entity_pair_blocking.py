"""Gold-free scalar blocking before the v3 Entity coreference fine head.

This module owns candidate pair selection only. It never decides Entity type,
cluster membership, representative, fine confidence, or a negative label.
"""

from __future__ import annotations

from collections import defaultdict
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass
from hashlib import sha256
from heapq import heapify, heappop
import json
from pathlib import Path
import unicodedata
from typing import Sequence

from runtime.v3_pretraining.entity_union import EntityCandidate
from runtime.v3_pretraining.source_layout import RawArticle


CHANNELS = ("SOURCE", "LEXICAL", "LOCAL", "TYPE")
ROUND_ROBIN = ("SOURCE", "LEXICAL", "LOCAL", "TYPE", "LOCAL", "TYPE")
POLICY_ID = "V3_UNIFIED_ENTITY_MENTION_BLOCKING_V1"


@dataclass(frozen=True, slots=True)
class EntityPairPolicy:
    """Nested K curve over one fixed posting search; all limits are explicit."""

    per_query_budget: int
    query_visit_budget: int
    posting_visit_budget: int
    gram_keys_per_query: int = 4

    def __post_init__(self) -> None:
        if min(self.per_query_budget, self.query_visit_budget,
               self.posting_visit_budget, self.gram_keys_per_query) <= 0:
            raise ValueError("Entity pair routing budgets must be positive")
        if self.query_visit_budget < max(self.per_query_budget, len(CHANNELS)):
            raise ValueError("Entity pair visit budget cannot undercut selected K or channels")

    @property
    def sha256(self) -> str:
        value = {"policy_id": POLICY_ID, "policy": asdict(self),
                 "channel_order": ROUND_ROBIN,
                 "adapter": "V3_UNKNOWN_ROLE_TYPE_IS_NOT_A_FILTER"}
        return sha256(json.dumps(value, sort_keys=True,
                                 separators=(",", ":")).encode()).hexdigest()

    @classmethod
    def load_predicted_validated(
            cls, path: str | Path, *, checkpoint_sha256: str,
            source_policy_sha256: str,
            acceptance_sha256: str) -> "EntityPairPolicy":
        """Load a predicted-validated policy for the unified mention universe."""
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        report_sha = artifact.get("predicted_pair_routing_validation_report_sha256")
        if (set(artifact) != {"schema_version", "source_profile", "selection_status",
                             "policy", "policy_sha256", "checkpoint_sha256",
                             "source_policy_sha256", "acceptance_sha256",
                             "mention_contract",
                             "predicted_pair_routing_validation_report_sha256"} or
                artifact["schema_version"] != "v23-unified-entity-pair-policy-v1" or
                artifact["source_profile"] != "V23_BASELINE" or
                artifact["selection_status"] != "PREDICTED_VALIDATED" or
                artifact["mention_contract"] != "UNIFIED_MENTION_COREF_V1" or
                artifact["checkpoint_sha256"] != checkpoint_sha256 or
                artifact["source_policy_sha256"] != source_policy_sha256 or
                artifact["acceptance_sha256"] != acceptance_sha256 or
                not isinstance(report_sha, str) or len(report_sha) != 64 or
                any(char not in "0123456789abcdef" for char in report_sha) or
                set(artifact["policy"]) != set(cls.__dataclass_fields__)):
            raise ValueError("Entity pair policy requires predicted-source validation artifact")
        policy = cls(**artifact["policy"])
        if artifact["policy_sha256"] != policy.sha256:
            raise ValueError("Entity pair policy artifact SHA differs")
        return policy


@dataclass(frozen=True, slots=True)
class BlockedEntityPairs:
    pairs: tuple[tuple[int, int], ...]
    routes: tuple[tuple[int, int, str, str, float, int], ...]
    visited: int
    exhausted_queries: int
    naive_pairs: int
    policy: EntityPairPolicy


@dataclass(frozen=True, slots=True)
class EntityAllPairShadowReference:
    """Audit-only universe; avoids allocating N choose 2 pair objects."""

    candidate_count: int
    policy_id: str = "ENTITY_ALL_PAIR_SHADOW_REFERENCE"

    @property
    def pair_count(self) -> int:
        return self.candidate_count * (self.candidate_count - 1) // 2

    def contains(self, left: int, right: int) -> bool:
        return 0 <= left < self.candidate_count and 0 <= right < self.candidate_count and left != right


def _surface(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def _alias(text: str) -> str:
    return "".join(char for char in _surface(text) if char.isalnum())


def _grams(text: str) -> frozenset[str]:
    return frozenset(text[index:index + 2] for index in range(len(text) - 1))


def _sentence(sentences: Sequence[tuple[int, int]], start: int,
              sentence_starts: Sequence[int] | None = None) -> int:
    if sentence_starts is None:
        sentence_starts = tuple(left for left, _ in sentences)
    result = bisect_right(sentence_starts, start) - 1
    if result < 0 or not start < sentences[result][1]:
        raise ValueError("Entity pair candidate has no containing sentence")
    return result


def _score(left: EntityCandidate, right: EntityCandidate, channel: str,
           sentence_distance: int, left_surface: str, right_surface: str,
           left_alias: str, right_alias: str,
           left_evidence: frozenset[str], right_evidence: frozenset[str],
           left_grams: frozenset[str], right_grams: frozenset[str],
           left_origins: frozenset[str], right_origins: frozenset[str]) -> float:
    base = _pair_base_score(
        left, right, sentence_distance, left_surface, right_surface,
        left_alias, right_alias, left_evidence, right_evidence,
        left_grams, right_grams, left_origins, right_origins)
    return base + 0.01 * max(min(right.score, 10.0), -10.0) + {
        "SOURCE": 0.3, "LEXICAL": 0.2, "LOCAL": 0.1, "TYPE": 0.05}[channel]


def _pair_base_score(left: EntityCandidate, right: EntityCandidate,
                     sentence_distance: int, left_surface: str, right_surface: str,
                     left_alias: str, right_alias: str,
                     left_evidence: frozenset[str], right_evidence: frozenset[str],
                     left_grams: frozenset[str], right_grams: frozenset[str],
                     left_origins: frozenset[str], right_origins: frozenset[str]) -> float:
    """The channel-independent part of the unchanged cheap score."""
    shared_evidence = bool(left_evidence & right_evidence)
    same_coordinate = (left.start, left.end) == (right.start, right.end)
    overlap = max(left.start, right.start) < min(left.end, right.end)
    exact = bool(left_surface and left_surface == right_surface)
    alias = bool(left_alias and left_alias == right_alias)
    substring = bool(left_alias and right_alias and
                     (left_alias in right_alias or right_alias in left_alias))
    shared_grams = len(left_grams & right_grams)
    type_cue = (0.2 if left.entity_type and left.entity_type == right.entity_type
                else 0.1 if "GENERIC" in (left.entity_type, right.entity_type)
                else 0.0)
    origin_cue = 0.1 * bool(left_origins & right_origins)
    base = (5.0 * shared_evidence + 4.0 * same_coordinate +
            3.0 * exact + 2.5 * alias + 1.5 * substring +
            min(shared_grams, 4) * 0.15 + 1.5 * overlap +
            0.7 * (sentence_distance == 0) + 0.25 * (sentence_distance == 1) +
            0.1 * (sentence_distance == 2) + type_cue + origin_cue -
            min(abs(left.start - right.start), 10000) / 10000.0)
    # A source-score tie break is a routing cue only, never representative choice.
    return base


_CHANNEL_BONUS = {"SOURCE": 0.3, "LEXICAL": 0.2, "LOCAL": 0.1, "TYPE": 0.05}


def _ordered_channel_targets(rows: dict[int, tuple[float, str]],
                             candidates: Sequence[EntityCandidate],
                             budget: int):
    key = lambda index: (-rows[index][0], candidates[index].candidate_id)
    if len(rows) <= budget * 4:
        return iter(sorted(rows, key=key))
    # A channel may need rows past its first K because earlier channels took
    # the same targets. Pop lazily, while retaining the exact full sort order.
    heap = [(key(index), index) for index in rows]
    heapify(heap)
    return (heappop(heap)[1] for _ in range(len(heap)))


def _type_posting_visits(posting: Sequence[int], starts: Sequence[int],
                         query_start: int, limit: int) -> tuple[int, ...]:
    """Bound a type cue with nearby rows and article-wide anchors, not a type gate."""
    if len(posting) <= limit:
        return tuple(posting)
    position = bisect_left(starts, query_start)
    left, right = position - 1, position
    local = []
    while len(local) < max(1, limit // 2) and (left >= 0 or right < len(posting)):
        if left >= 0 and (right >= len(posting) or
                          query_start - starts[left] <= starts[right] - query_start):
            local.append(posting[left])
            left -= 1
        else:
            local.append(posting[right])
            right += 1
    reserve = limit - len(local)
    anchors = [posting[(index * (len(posting) - 1)) // max(1, reserve - 1)]
               for index in range(reserve)]
    return tuple(dict.fromkeys((*local, *anchors)))[:limit]


def block_entity_pairs(*, article: RawArticle,
                       candidates: Sequence[EntityCandidate],
                       sentence_spans: Sequence[tuple[int, int]],
                       policy: EntityPairPolicy,
                       materialize_routes: bool = True) -> BlockedEntityPairs:
    """Route unchanged pairs; omit per-pair provenance only for normal inference."""
    count = len(candidates)
    if len({row.candidate_id for row in candidates}) != count or any(
            not 0 <= row.start < row.end <= len(article.content) or
            article.content[row.start:row.end] != row.text
            for row in candidates):
        raise ValueError("Entity pair source inventory differs from exact article text")
    sentence_starts = tuple(left for left, _ in sentence_spans)
    if sentence_starts != tuple(sorted(sentence_starts)) or len(set(sentence_starts)) != len(sentence_starts):
        raise ValueError("Entity pair sentence inventory must be in source order")
    sentences = tuple(_sentence(sentence_spans, row.start, sentence_starts)
                      for row in candidates)
    surfaces = tuple(_surface(row.text) for row in candidates)
    aliases = tuple(_alias(row.text) for row in candidates)
    gram_sets = tuple(_grams(value) for value in aliases)
    evidence_sets = tuple(frozenset(row.evidence_ids) for row in candidates)
    origin_sets = tuple(frozenset(row.origins) for row in candidates)
    postings: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(candidates):
        keys = {f"SOURCE:COORD:{row.start}:{row.end}",
                f"LOCAL:SENT:{sentences[index]}",
                f"LOCAL:BIN:{row.start // 64}"}
        if row.entity_type:
            keys.add(f"TYPE:{row.entity_type}")
        keys.update(f"LOCAL:BIN:{bin_id}" for bin_id in
                    range(row.start // 64, min(row.end // 64 + 1, row.start // 64 + 4)))
        keys.update(f"SOURCE:EVIDENCE:{evidence_id}" for evidence_id in row.evidence_ids)
        if surfaces[index]:
            keys.add(f"LEXICAL:EXACT:{surfaces[index]}")
        if aliases[index]:
            keys.add(f"LEXICAL:ALIAS:{aliases[index]}")
            keys.update(f"LEXICAL:GRAM:{gram}" for gram in gram_sets[index])
        for key in keys:
            postings[key].append(index)
    candidate_order = tuple((row.start, row.end, row.candidate_id)
                            for row in candidates)
    for key in postings:
        postings[key].sort(key=candidate_order.__getitem__)
    posting_starts = {key: tuple(candidates[index].start for index in rows)
                      for key, rows in postings.items() if key.startswith("TYPE:")}

    selected: dict[tuple[int, int], tuple[int, int, str, str, float, int]] = {}
    # PUBLIC keeps an O(selected pairs) scalar dedup set, rather than either
    # millions of provenance records or an O(all pairs) triangular bitmap.
    selected_keys: set[int] | None = None if materialize_routes else set()
    visited_total = exhausted_total = 0
    channel_limits = tuple((policy.query_visit_budget * (index + 1)) // len(CHANNELS)
                           - (policy.query_visit_budget * index) // len(CHANNELS)
                           for index in range(len(CHANNELS)))
    for query_index, query in enumerate(candidates):
        source_keys = [f"SOURCE:COORD:{query.start}:{query.end}"] + [
            f"SOURCE:EVIDENCE:{evidence_id}" for evidence_id in query.evidence_ids]
        lexical_keys = [f"LEXICAL:EXACT:{surfaces[query_index]}",
                        f"LEXICAL:ALIAS:{aliases[query_index]}"]
        gram_keys = [f"LEXICAL:GRAM:{gram}" for gram in gram_sets[query_index]]
        lexical_keys += sorted(gram_keys, key=lambda key: (len(postings.get(key, ())), key))[
            :policy.gram_keys_per_query]
        local_keys = [f"LOCAL:SENT:{sentences[query_index]}"] + [
            f"LOCAL:SENT:{other}" for other in
            (sentences[query_index] - 1, sentences[query_index] + 1,
             sentences[query_index] - 2, sentences[query_index] + 2)
            if 0 <= other < len(sentence_spans)] + [
            f"LOCAL:BIN:{bin_id}" for bin_id in
            (query.start // 64 - 1, query.start // 64, query.start // 64 + 1)
            if bin_id >= 0]
        channel_keys = {"SOURCE": source_keys, "LEXICAL": lexical_keys,
                        "LOCAL": local_keys,
                        "TYPE": ([f"TYPE:{query.entity_type}"]
                                 if query.entity_type else [])}
        ranked: dict[str, dict[int, tuple[float, str]]] = {
            channel: {} for channel in CHANNELS}
        # Several posting keys revisit the same query/target in one channel.
        # The scalar score depends on that pair and channel, not the key.
        base_cache: dict[int, float] = {}
        visited_query = 0
        exhausted = False
        # A dense SOURCE posting must not consume the LEXICAL/LOCAL search budget.
        # Fixed channel shares keep the candidate curve nested as K changes.
        for channel, channel_limit in zip(CHANNELS, channel_limits):
            channel_visited = 0
            for key in dict.fromkeys(channel_keys[channel]):
                posting = postings.get(key, ())
                if channel == "TYPE" and posting:
                    posting = _type_posting_visits(
                        posting, posting_starts[key], query.start,
                        policy.posting_visit_budget)
                for position, candidate_index in enumerate(posting):
                    if (position >= policy.posting_visit_budget or
                            channel_visited >= channel_limit):
                        exhausted = True
                        break
                    visited_query += 1
                    channel_visited += 1
                    if candidate_index == query_index:
                        continue
                    target = candidates[candidate_index]
                    base = base_cache.get(candidate_index)
                    if base is None:
                        base = _pair_base_score(
                            query, target,
                            abs(sentences[query_index] - sentences[candidate_index]),
                            surfaces[query_index], surfaces[candidate_index],
                            aliases[query_index], aliases[candidate_index],
                            evidence_sets[query_index], evidence_sets[candidate_index],
                            gram_sets[query_index], gram_sets[candidate_index],
                            origin_sets[query_index], origin_sets[candidate_index])
                        base_cache[candidate_index] = base
                    score = (base + 0.01 * max(min(target.score, 10.0), -10.0)
                             + _CHANNEL_BONUS[channel])
                    old = ranked[channel].get(candidate_index)
                    if old is None or (score, key) > old:
                        ranked[channel][candidate_index] = (score, key)
                if channel_visited >= channel_limit:
                    break
        visited_total += visited_query
        order = {channel: _ordered_channel_targets(
            rows, candidates, policy.per_query_budget)
                 for channel, rows in ranked.items()}
        chosen: set[int] = set()
        rank = 0
        while rank < policy.per_query_budget:
            progressed = False
            for channel in ROUND_ROBIN:
                if rank >= policy.per_query_budget:
                    break
                candidate_index = next(order[channel], None)
                while candidate_index is not None and candidate_index in chosen:
                    candidate_index = next(order[channel], None)
                if candidate_index is None:
                    continue
                progressed = True
                chosen.add(candidate_index)
                rank += 1
                left, right = min(query_index, candidate_index), max(
                    query_index, candidate_index)
                if selected_keys is None:
                    pair = (left, right)
                    score, key = ranked[channel][candidate_index]
                    if pair not in selected:
                        selected[pair] = (query_index, candidate_index,
                                          channel, key, score, rank)
                else:
                    pair_key = left * count + right
                    if pair_key not in selected_keys:
                        selected_keys.add(pair_key)
            if not progressed:
                break
        exhausted_total += int(exhausted or any(
            index not in chosen for rows in ranked.values() for index in rows))
    pairs = (tuple(sorted(selected)) if selected_keys is None else
             tuple((key // count, key % count) for key in sorted(selected_keys)))
    routes = tuple(selected[pair] for pair in pairs) if selected_keys is None else ()
    return BlockedEntityPairs(pairs, routes,
                              visited_total, exhausted_total,
                              count * (count - 1) // 2, policy)
