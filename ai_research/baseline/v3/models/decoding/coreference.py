"""KEEP/MERGE pair 출력의 deterministic transitive clustering."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable


class UnionFindClusterer:
    def cluster(
        self,
        mention_ids: Iterable[str],
        merge_edges: Iterable[tuple[str, str, float]],
        *,
        threshold: float = 0.5,
    ) -> tuple[tuple[str, ...], ...]:
        parent = {item: item for item in mention_ids}

        def find(item: str) -> str:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        for left, right, score in merge_edges:
            if score < threshold:
                continue
            if left not in parent or right not in parent:
                raise ValueError("coreference edge references unknown mention")
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root
        groups: dict[str, list[str]] = defaultdict(list)
        for item in parent:
            groups[find(item)].append(item)
        return tuple(sorted((tuple(sorted(group)) for group in groups.values()), key=lambda group: group[0]))
