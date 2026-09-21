"""추론 계산량만 제한하는 optional pair ranking/pruning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar


PairT = TypeVar("PairT")


@dataclass(frozen=True, slots=True)
class RuntimePairPrunerConfig:
    enabled: bool = True
    max_pairs_per_task: int = 512

    def __post_init__(self) -> None:
        if self.max_pairs_per_task <= 0:
            raise ValueError("max_pairs_per_task must be positive")


class RuntimePairPruner:
    """Gold label을 보지 않고 eligible runtime pair의 top-k만 선택한다."""

    def __init__(self, config: RuntimePairPrunerConfig | None = None) -> None:
        self.config = config or RuntimePairPrunerConfig()

    def prune(
        self,
        task: str,
        pairs: Sequence[PairT],
        *,
        rank_score: Callable[[PairT], float],
    ) -> list[PairT]:
        del task
        if not self.config.enabled or len(pairs) <= self.config.max_pairs_per_task:
            return list(pairs)
        ranked = sorted(
            enumerate(pairs), key=lambda item: (-rank_score(item[1]), item[0])
        )[: self.config.max_pairs_per_task]
        keep = {index for index, _ in ranked}
        return [pair for index, pair in enumerate(pairs) if index in keep]


class KeepAllRuntimePairPruner(RuntimePairPruner):
    """Runtime policy ablation용 no-op pruner."""

    def prune(self, task, pairs, *, rank_score):
        del task, rank_score
        return list(pairs)
