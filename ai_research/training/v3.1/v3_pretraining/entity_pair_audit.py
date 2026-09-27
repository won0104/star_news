"""Post-routing Gold join for v3 Entity blocking and complete-link coverage.

The runtime router never imports this module. These metrics evaluate exact source
coordinates only after a Gold-free candidate universe and route have been fixed.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Mapping, Sequence

from runtime.v3_pretraining.entity_union import EntityCandidate
from runtime.v3_pretraining.pair_routing import RoutedPairs


def entity_route_survival(*, candidates: Sequence[EntityCandidate],
                          routed: RoutedPairs, gold: Mapping) -> dict:
    """Count reachable/routed Gold pairs and all-pairs-ready multi-mention clusters.

    A Gold mention is reachable when an exact coordinate exists in the predicted
    inventory. If several predicted candidates share it, a Gold pair is routed
    when any candidate-pair mapping is selected; this is an optimistic coordinate
    survival measure, not a claim about fine decisions or final clustering.
    """
    coordinates: dict[tuple[int, int], set[int]] = defaultdict(set)
    for index, candidate in enumerate(candidates):
        coordinates[(candidate.start, candidate.end)].add(index)
    mentions = {row["mention_id"]: row for row in gold["entity_mentions"]}
    selected = set(routed.pairs)
    pair_totals = defaultdict(lambda: {"reachable": 0, "routed": 0})
    cluster_totals = defaultdict(lambda: {"reachable": 0, "ready": 0})
    for cluster in gold["entity_clusters"]:
        members = [mentions[key] for key in cluster["mention_ids"]]
        if len(members) < 2:
            continue
        categories = {"all"}
        types = {row["type"] for row in members}
        if len(types) == 1:
            categories.add("same_type")
        else:
            categories.add("cross_type")
        if "GENERIC" in types:
            categories.add("generic_containing")
        mapped = [coordinates[(row["span"]["start"], row["span"]["end"])]
                  for row in members]
        cluster_reachable = all(mapped)
        cluster_ready = cluster_reachable
        for left, right in combinations(range(len(members)), 2):
            pair_categories = {"all"}
            left_type, right_type = members[left]["type"], members[right]["type"]
            pair_categories.add("same_type" if left_type == right_type else "cross_type")
            if "GENERIC" in (left_type, right_type):
                pair_categories.add("generic_related")
            if not mapped[left] or not mapped[right]:
                cluster_ready = False
                continue
            pair_routed = any((min(a, b), max(a, b)) in selected
                              for a in mapped[left] for b in mapped[right] if a != b)
            for category in pair_categories:
                pair_totals[category]["reachable"] += 1
                pair_totals[category]["routed"] += int(pair_routed)
            cluster_ready &= pair_routed
        if cluster_reachable:
            for category in categories:
                cluster_totals[category]["reachable"] += 1
                cluster_totals[category]["ready"] += int(cluster_ready)
    all_pairs = pair_totals["all"]
    return {"reachable_gold_positive_pairs": all_pairs["reachable"],
            "routed_gold_positive_pairs": all_pairs["routed"],
            "routing_survival": (all_pairs["routed"] / all_pairs["reachable"]
                                 if all_pairs["reachable"] else None),
            "routing_miss_count": all_pairs["reachable"] - all_pairs["routed"],
            "pair": dict(pair_totals), "complete_link_cluster": dict(cluster_totals),
            "coordinate_matching": "EXISTENTIAL_PREDICTED_CANDIDATE",
            "gold_used_after_routing": True}
