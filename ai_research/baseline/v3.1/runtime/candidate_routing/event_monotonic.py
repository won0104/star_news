"""Monotonic Event seed retrieval and bounded clique completion.

Only scalar handoff signals participate in retrieval. Fine scores and Gold are
absent from this module; an unevaluated pair never licenses complete-link merge.
The same pure core serves saved shadow audit and explicit bounded runtime mode.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from time import perf_counter

from runtime.candidate_routing.event_blocks import EventSignals


CHANNELS = ("LOCAL", "LEXICAL", "TRIGGER", "ENTITY", "TEMPORAL")


@dataclass(frozen=True, slots=True)
class MonotonicEventPolicy:
    policy_id: str = "SHADOW_C_MONOTONIC_SEED_CLIQUE_V1"
    local_quota: int = 3
    lexical_quota: int = 5
    trigger_quota: int = 2
    entity_quota: int = 3
    temporal_quota: int = 2
    local_visit_cap: int = 24
    lexical_visit_cap: int = 64
    trigger_visit_cap: int = 24
    entity_visit_cap: int = 48
    temporal_visit_cap: int = 24
    neighborhood_size: int = 12
    article_pair_hard_cap: int = 3072
    article_pair_linear_factor: int = 32

    def validate(self) -> None:
        values = (self.local_quota, self.lexical_quota, self.trigger_quota,
                  self.entity_quota, self.temporal_quota, self.local_visit_cap,
                  self.lexical_visit_cap, self.trigger_visit_cap,
                  self.entity_visit_cap, self.temporal_visit_cap,
                  self.neighborhood_size, self.article_pair_hard_cap,
                  self.article_pair_linear_factor)
        if (not self.policy_id or any(value < 1 for value in values)
            or max(values[:5]) > 16 or max(values[5:10]) > 128
            or self.neighborhood_size > 12 or self.article_pair_hard_cap > 3072
            or self.article_pair_linear_factor > 32):
            raise ValueError("Monotonic Event policy is invalid or unbounded")

    def quota(self, channel: str) -> int:
        return getattr(self, channel.lower() + "_quota")

    def visit_cap(self, channel: str) -> int:
        return getattr(self, channel.lower() + "_visit_cap")


@dataclass(slots=True)
class MonotonicRoute:
    seed_pairs: frozenset[tuple[str, str]]
    completion_pairs: frozenset[tuple[str, str]]
    selected_pairs: frozenset[tuple[str, str]]
    provenance: dict[tuple[str, str], tuple[str, ...]]
    prefix_neighbors: dict[str, tuple[frozenset[str], ...]]
    prefix_pairs: tuple[frozenset[tuple[str, str]], ...]
    census: dict


def _pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _postings(signals: tuple[EventSignals, ...]) -> dict:
    postings: dict[tuple[str, object], list[str]] = defaultdict(list)
    for row in sorted(signals, key=lambda item: item.event_id):
        postings[("sentence", row.sentence_index)].append(row.event_id)
        for gram in row.text_grams:
            postings[("text_gram", gram)].append(row.event_id)
        if "trigger" in row.availability and row.trigger_norm:
            postings[("trigger", row.trigger_norm)].append(row.event_id)
            for gram in row.trigger_grams:
                postings[("trigger_gram", gram)].append(row.event_id)
        if "resolved_entity" in row.availability:
            all_entities = set().union(*row.roles)
            for role_index, role in enumerate(("ACTOR", "TARGET", "PLACE")):
                for entity_id in row.roles[role_index]:
                    postings[("entity_" + role, entity_id)].append(row.event_id)
            for entity_id in all_entities:
                postings[("entity_any", entity_id)].append(row.event_id)
        if "time" in row.availability:
            for time_key in row.normalized_times:
                postings[("time_normalized", time_key)].append(row.event_id)
            for occurrence_id in row.raw_time_ids:
                postings[("time_occurrence", occurrence_id)].append(row.event_id)
    return postings


def _keys(row: EventSignals, channel: str) -> list[tuple[str, object]]:
    if channel == "LOCAL":
        return [("sentence", row.sentence_index + offset)
                for offset in range(-3, 4)]
    if channel == "LEXICAL":
        return [("text_gram", gram) for gram in row.text_grams]
    if channel == "TRIGGER":
        return ([("trigger", row.trigger_norm)] if row.trigger_norm else []) + [
            ("trigger_gram", gram) for gram in row.trigger_grams]
    if channel == "ENTITY":
        keys = []
        for role_index, role in enumerate(("ACTOR", "TARGET", "PLACE")):
            keys.extend(("entity_" + role, item) for item in row.roles[role_index])
        keys.extend(("entity_any", item) for item in set().union(*row.roles))
        return keys
    return ([("time_normalized", item) for item in row.normalized_times] +
            [("time_occurrence", item) for item in row.raw_time_ids])


def _rank(query: EventSignals, target: EventSignals, channel: str,
          grounds: set[str]) -> tuple:
    distance = abs(query.sentence_index - target.sentence_index)
    if channel == "LOCAL":
        return (distance, target.event_id)
    if channel == "LEXICAL":
        shared = len(query.text_grams & target.text_grams)
        containment = bool(query.text_norm and target.text_norm and
                           (query.text_norm in target.text_norm or
                            target.text_norm in query.text_norm))
        return (-shared, -int(containment), distance, target.event_id)
    if channel == "TRIGGER":
        return (-int(query.trigger_norm == target.trigger_norm),
                -len(query.trigger_grams & target.trigger_grams),
                distance, target.event_id)
    if channel == "ENTITY":
        return (-len(grounds & {"ENTITY_ACTOR", "ENTITY_TARGET",
                                "ENTITY_PLACE"}), -int("ENTITY_ANY" in grounds),
                distance, target.event_id)
    return (-int("TIME_NORMALIZED" in grounds),
            -int("TIME_OCCURRENCE" in grounds), distance, target.event_id)


def _components(ids: tuple[str, ...], pairs: frozenset[tuple[str, str]]) -> list[tuple[str, ...]]:
    adjacency = {item: set() for item in ids}
    for left, right in pairs:
        adjacency[left].add(right)
        adjacency[right].add(left)
    unseen = set(ids)
    components = []
    while unseen:
        start = min(unseen)
        stack = [start]
        members = set()
        while stack:
            item = stack.pop()
            if item in members:
                continue
            members.add(item)
            stack.extend(adjacency[item] - members)
        unseen -= members
        components.append(tuple(sorted(members)))
    return components


def route_monotonic_events(signals: tuple[EventSignals, ...],
                           policy: MonotonicEventPolicy = MonotonicEventPolicy(),
                           *, timing: dict | None = None,
                           ) -> MonotonicRoute:
    """Retrieve independent channel seeds, then add only bounded clique witnesses."""
    policy.validate()
    by_id = {row.event_id: row for row in signals}
    if len(by_id) != len(signals):
        raise ValueError("Canonical Event ID duplicated")
    ids = tuple(sorted(by_id))
    index_started = perf_counter() if timing is not None else None
    postings = _postings(signals)
    if timing is not None:
        timing["posting_index_seconds"] = perf_counter() - index_started
    seed_started = perf_counter() if timing is not None else None
    retained: dict[str, dict[str, set[str]]] = {item: {} for item in ids}
    provenance: dict[tuple[str, str], set[str]] = defaultdict(set)
    visits = Counter()
    retains = Counter()
    exhausted = Counter()
    max_visits = Counter()
    for event_id in ids:
        row = by_id[event_id]
        for channel in CHANNELS:
            keys = sorted(set(_keys(row, channel)),
                          key=lambda key: (len(postings.get(key, ())), str(key)))
            found: dict[str, set[str]] = defaultdict(set)
            query_visits = 0
            cap = policy.visit_cap(channel)
            for key in keys:
                for candidate in postings.get(key, ()):
                    if candidate == event_id:
                        continue
                    if query_visits == cap:
                        exhausted[channel] += 1
                        break
                    query_visits += 1
                    found[candidate].add({"sentence": "LOCAL",
                                           "text_gram": "LEXICAL"}.get(
                                               key[0], key[0].upper()))
                if query_visits == cap:
                    break
            visits[channel] += query_visits
            max_visits[channel] = max(max_visits[channel], query_visits)
            winners = sorted(found,
                             key=lambda item: _rank(row, by_id[item], channel,
                                                    found[item]))[:policy.quota(channel)]
            if len(found) > policy.quota(channel):
                exhausted[channel + "_quota"] += 1
            retains[channel] += len(winners)
            retained[event_id][channel] = set(winners)
            for winner in winners:
                provenance[_pair(event_id, winner)].update(found[winner])

    prefix_neighbors = {}
    prefix_pairs: list[frozenset[tuple[str, str]]] = []
    for event_id in ids:
        cumulative: set[str] = set()
        snapshots = []
        for channel in CHANNELS:
            cumulative.update(retained[event_id][channel])
            if channel != "LOCAL":
                snapshots.append(frozenset(cumulative))
        prefix_neighbors[event_id] = tuple(snapshots)  # S1..S4
    for index in range(4):
        prefix_pairs.append(frozenset(
            _pair(item, neighbor) for item in ids
            for neighbor in prefix_neighbors[item][index]))
    if any(not a <= b for a, b in zip(prefix_pairs, prefix_pairs[1:])):
        raise AssertionError("Article seed monotonicity violated")
    if any(not a <= b for snapshots in prefix_neighbors.values()
           for a, b in zip(snapshots, snapshots[1:])):
        raise AssertionError("Per-Event seed monotonicity violated")
    seed = prefix_pairs[-1]
    full = len(ids) * (len(ids) - 1) // 2
    pair_budget = min(full, policy.article_pair_hard_cap,
                      policy.article_pair_linear_factor * len(ids))
    if len(seed) > pair_budget:
        raise ValueError(f"Protected seed pairs {len(seed)} exceed hard budget {pair_budget}")
    if timing is not None:
        timing["multi_channel_seed_retrieval_seconds"] = perf_counter() - seed_started
    completion_started = perf_counter() if timing is not None else None
    adjacency = defaultdict(set)
    for left, right in seed:
        adjacency[left].add(right)
        adjacency[right].add(left)
    completion_candidates: set[tuple[str, str]] = set()
    max_neighborhood = 0
    large_component_count = 0
    overlapping_duplicate = 0
    for component in _components(ids, seed):
        if len(component) <= policy.neighborhood_size:
            neighborhoods = [component]
        else:
            large_component_count += 1
            neighborhoods = []
            for center in component:
                neighbors = sorted(adjacency[center], key=lambda item: (
                    -len(provenance[_pair(center, item)]),
                    -len(by_id[center].text_grams & by_id[item].text_grams),
                    abs(by_id[center].sentence_index - by_id[item].sentence_index), item))
                neighborhoods.append(tuple(sorted((center, *neighbors[:policy.neighborhood_size - 1]))))
        for neighborhood in neighborhoods:
            max_neighborhood = max(max_neighborhood, len(neighborhood))
            for left, right in combinations(neighborhood, 2):
                pair = _pair(left, right)
                if pair in seed:
                    continue
                if pair in completion_candidates:
                    overlapping_duplicate += 1
                completion_candidates.add(pair)
    room = pair_budget - len(seed)
    completion = frozenset(sorted(completion_candidates)[:room])
    selected = seed | completion
    if timing is not None:
        timing["clique_completion_seconds"] = perf_counter() - completion_started
    census = {
        "event_count": len(ids), "full_possible_pair_count": full,
        "channel_posting_visits": dict(visits),
        "channel_retained_neighbor_sum": dict(retains),
        "channel_max_query_visit": dict(max_visits),
        "channel_visit_or_quota_exhaustion": dict(exhausted),
        "unique_seed_pair_count": len(seed),
        "completion_candidate_count": len(completion_candidates),
        "completion_added_pair_count": len(completion),
        "completion_skipped_by_budget": len(completion_candidates) - len(completion),
        "final_selected_unique_pair_count": len(selected),
        "pair_budget": pair_budget, "pair_budget_usage": len(selected),
        "max_neighborhood_size": max_neighborhood,
        "large_component_count": large_component_count,
        "max_component_size": max((len(item) for item in _components(ids, seed)), default=0),
        "overlapping_completion_duplicate_count": overlapping_duplicate,
        "missing_pair_status": "NOT_EVALUATED",
    }
    return MonotonicRoute(seed, completion, selected,
                          {key: tuple(sorted(value)) for key, value in provenance.items()},
                          prefix_neighbors, tuple(prefix_pairs), census)


def map_selected_exact_features(signals: tuple[EventSignals, ...],
                                selected: frozenset[tuple[str, str]], feature_fn):
    """Step 10 wiring contract: exact pair feature callback sees selected IDs only."""
    by_id = {row.event_id: row for row in signals}
    return {pair: feature_fn(by_id[pair[0]], by_id[pair[1]])
            for pair in sorted(selected)}
