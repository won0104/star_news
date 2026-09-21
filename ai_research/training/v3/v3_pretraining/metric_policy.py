"""향후 dev 선택을 위한 metric lane/early-stop 순수 계약.

현재 단계에서는 metric을 계산하거나 dev/test를 읽지 않는다. 세 lane을 섞어
하나의 수치로 checkpoint를 고르지 않도록 형식을 먼저 고정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


METRIC_LANES = ("HEAD_CONDITIONAL", "PREDICTED_CASCADE", "SELECTED_PUBLIC")


@dataclass(frozen=True, slots=True)
class MetricObservation:
    checkpoint_id: str
    split: str
    lane: str
    metric_name: str
    value: float

    def validate(self) -> None:
        if (not self.checkpoint_id or self.split != "dev" or self.lane not in METRIC_LANES
                or not self.metric_name or not math.isfinite(self.value)):
            raise ValueError("checkpoint selection needs one finite named dev metric lane")


def dev_early_stop_decision(history: Sequence[MetricObservation],
                            current: MetricObservation, *,
                            patience: int, min_delta: float = 0.0,
                            maximize: bool = True) -> str:
    """외부에서 명시한 dev metric만 비교한다; 이번 engineering run은 호출하지 않는다."""
    current.validate()
    if patience <= 0 or min_delta < 0 or not math.isfinite(min_delta):
        raise ValueError("early-stop patience/min_delta invalid")
    for row in history:
        row.validate()
        if (row.lane, row.metric_name) != (current.lane, current.metric_name):
            raise ValueError("different metric lanes/names cannot select one checkpoint")
    if not history:
        return "SAVE_BEST"
    values = [row.value for row in history]
    best = max(values) if maximize else min(values)
    improved = (current.value > best + min_delta if maximize else
                current.value < best - min_delta)
    if improved:
        return "SAVE_BEST"
    best_index = values.index(best)
    return "STOP" if len(history) - best_index >= patience else "CONTINUE"
