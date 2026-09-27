"""Gold 주입·Gold span·predicted span cohort를 분리하는 exact matcher."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class EvaluationCohort(str, Enum):
    GOLD_INJECTED = "GOLD_INJECTED"
    GOLD_SPAN = "GOLD_SPAN"
    PREDICTED_SPAN = "PREDICTED_SPAN"


@dataclass(frozen=True, slots=True)
class MatchCounts:
    cohort: EvaluationCohort
    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = 2 * self.true_positive + self.false_positive + self.false_negative
        return 2 * self.true_positive / denominator if denominator else 0.0


def exact_match(gold: Iterable[tuple], predicted: Iterable[tuple], *,
                cohort: EvaluationCohort) -> MatchCounts:
    """span은 (label,start,end), role은 (event,role,start,end), edge는 방향 endpoint tuple."""
    expected, actual = set(gold), set(predicted)
    common = expected & actual
    return MatchCounts(cohort, len(common), len(actual - common), len(expected - common))


@dataclass(frozen=True, slots=True)
class RankCounts:
    cohort: EvaluationCohort
    strict_correct: int
    strict_wrong: int
    strict_missing: int
    tie_pairs_ignored: int


def evaluate_rank_pairs(gold_pairs: Iterable[tuple[str, str, bool | None]],
                        predicted_scores: dict[str, float], *,
                        cohort: EvaluationCohort) -> RankCounts:
    correct = wrong = missing = ties = 0
    for left, right, preferred in gold_pairs:
        if preferred is None:
            ties += 1
            continue
        if left not in predicted_scores or right not in predicted_scores:
            missing += 1
            continue
        if (predicted_scores[left] > predicted_scores[right]) == preferred:
            correct += 1
        else:
            wrong += 1
    return RankCounts(cohort, correct, wrong, missing, ties)
