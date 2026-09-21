"""Gold 없는 final proposition의 raw, article-comparable Primary scalar 실행."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

import torch

from models.v3_pretraining.architecture import V3Core
from runtime.v3_pretraining.event_features import FinalClusterFeatureLease
from runtime.v3_pretraining.event_identity import EventClosure


@dataclass(frozen=True, slots=True)
class PrimaryScore:
    local_id: str
    kind: str
    primary_score: float
    status: str = "UNTRAINED_FRESH_WEIGHT_DIAGNOSTIC"


@torch.no_grad()
def score_final_primary(*, core: V3Core, final: FinalClusterFeatureLease,
                        closure: EventClosure,
                        statement_states: Mapping[str, torch.Tensor],
                        assertor_states: Mapping[str, torch.Tensor]) -> tuple[PrimaryScore, ...]:
    """final closure 뒤 모든 후보를 점수화하며 quota/threshold/Top-K를 적용하지 않는다."""
    if closure.source_mode != "PREDICTED" or final.source_mode != "PREDICTED" or final.cluster_ids != tuple(
            row.local_id for row in closure.events):
        raise ValueError("Primary runtime needs predicted final Event identity")
    if "primary" not in core.task_modules:
        raise ValueError("Primary head is not registered")
    view = final.view_for("PRIMARY")
    scores = core.task_modules["primary"](
        view, statement_states, assertor_states, core.primary_adapter)
    output = []
    for key, scalar in scores.items():
        value = float(scalar)
        if not math.isfinite(value):
            raise ValueError("Primary scorer returned non-finite scalar")
        kind, local_id = key.split(":", 1)
        output.append(PrimaryScore(local_id, "EVENT_CLUSTER" if kind == "E" else "STATEMENT", value))
    return tuple(output)
