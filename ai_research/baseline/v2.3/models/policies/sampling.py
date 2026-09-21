"""Eligibility를 통과한 학습 pair의 negative sampling 책임."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import random
from typing import Callable, Sequence, TypeVar


PairT = TypeVar("PairT")


@dataclass(frozen=True, slots=True)
class TrainingPairSamplerConfig:
    negative_to_positive_ratio: float = 8.0
    minimum_negatives: int = 16
    maximum_negatives: int = 512
    hard_negative_fraction: float = 0.5
    positive_class_balance: str = "none"
    seed: int = 41

    def __post_init__(self) -> None:
        if self.negative_to_positive_ratio < 0:
            raise ValueError("negative_to_positive_ratio must be non-negative")
        if not 0 <= self.minimum_negatives <= self.maximum_negatives:
            raise ValueError("negative limits are invalid")
        if not 0 <= self.hard_negative_fraction <= 1:
            raise ValueError("hard_negative_fraction must be in [0,1]")
        if self.positive_class_balance not in {"none", "oversample"}:
            raise ValueError("positive_class_balance must be none or oversample")


class TrainingPairSampler:
    """모든 positive를 보존하고 eligible negative만 줄인다."""

    def __init__(self, config: TrainingPairSamplerConfig | None = None) -> None:
        self.config = config or TrainingPairSamplerConfig()

    def sample(
        self,
        task: str,
        article_id: str,
        pairs: Sequence[PairT],
        *,
        is_positive: Callable[[PairT], bool],
        hardness: Callable[[PairT], float],
        class_label: Callable[[PairT], str] | None = None,
    ) -> tuple[list[PairT], int]:
        positives = [pair for pair in pairs if is_positive(pair)]
        negatives = [pair for pair in pairs if not is_positive(pair)]
        requested = max(
            self.config.minimum_negatives,
            int(round(len(positives) * self.config.negative_to_positive_ratio)),
        )
        limit = min(len(negatives), self.config.maximum_negatives, requested)
        hard_count = min(limit, int(round(limit * self.config.hard_negative_fraction)))
        ordered_hard = sorted(negatives, key=lambda pair: (-hardness(pair), repr(pair)))
        selected = ordered_hard[:hard_count]
        remainder = ordered_hard[hard_count:]
        seed_material = f"{self.config.seed}:{article_id}:{task}".encode("utf-8")
        stable_seed = int.from_bytes(sha256(seed_material).digest()[:8], "big")
        random.Random(stable_seed).shuffle(remainder)
        selected.extend(remainder[: limit - hard_count])
        selected_ids = {id(pair) for pair in selected}
        output = [pair for pair in pairs if is_positive(pair) or id(pair) in selected_ids]
        if self.config.positive_class_balance == "oversample":
            if class_label is None:
                raise ValueError("positive class balancing requires class_label")
            groups: dict[str, list[PairT]] = {}
            for pair in positives:
                groups.setdefault(class_label(pair), []).append(pair)
            target_count = max((len(group) for group in groups.values()), default=0)
            balanced_extras: list[PairT] = []
            balance_random = random.Random(stable_seed ^ 0x5A17)
            for label in sorted(groups):
                group = groups[label]
                balanced_extras.extend(
                    balance_random.choice(group)
                    for _ in range(target_count - len(group))
                )
            output.extend(balanced_extras)
        return output, len(selected)


class KeepAllTrainingPairSampler(TrainingPairSampler):
    """Ablation/test용 sampler; eligible pair를 그대로 반환한다."""

    def sample(
        self, task, article_id, pairs, *, is_positive, hardness, class_label=None
    ):
        del task, article_id, hardness, class_label
        return list(pairs), sum(not is_positive(pair) for pair in pairs)
