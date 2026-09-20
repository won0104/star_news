"""요청 단위 application stage 시간과 기존 candidate universe의 가벼운 census.

PUBLIC graph와 diagnostic capture policy에는 관여하지 않는다. 한 기사마다 새 인스턴스를
만들고 stage 경계에서만 perf_counter를 읽는다.
"""

from __future__ import annotations

from collections import defaultdict
from time import perf_counter


class ApplicationProfile:
    """한 번의 PUBLIC inference에 대한 stage wall time과 scalar count를 저장한다."""

    def __init__(self) -> None:
        self.stage_seconds: dict[str, float] = defaultdict(float)
        self.census: dict[str, dict[str, int | float]] = defaultdict(dict)

    @staticmethod
    def start() -> float:
        return perf_counter()

    def stop(self, stage: str, started: float) -> None:
        self.add_seconds(stage, perf_counter() - started)

    def add_seconds(self, stage: str, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(f"negative application stage duration: {stage}")
        self.stage_seconds[stage] += seconds

    def count(self, group: str, name: str, value: int | float) -> None:
        self.census[group][name] = value

    def exclusive_residual(self, inference_seconds: float, *, tolerance: float = 0.001) -> float:
        """서로 겹치지 않는 stage 합과 inference 구간의 남은 시간을 검사한다.

        Inclusive parent timer를 함께 더하면 이 검사가 실패한다. Serialization과
        report 시간은 호출자가 inference_seconds에서 제외해야 한다.
        """
        if inference_seconds < 0 or tolerance < 0:
            raise ValueError("inference duration/tolerance must be non-negative")
        residual = inference_seconds - sum(self.stage_seconds.values())
        if residual < -tolerance:
            raise ValueError("application stage accounting exceeds inference latency")
        return max(0.0, residual)

    def snapshot(self) -> dict:
        return {
            "stage_seconds": dict(self.stage_seconds),
            "census": {group: dict(values) for group, values in self.census.items()},
        }
