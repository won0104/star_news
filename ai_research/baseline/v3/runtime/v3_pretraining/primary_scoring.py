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


@dataclass(frozen=True, slots=True)
class PrimaryTrainingProvenance:
    """Selected Phase 6 checkpoint proof, independent of service validation."""

    checkpoint_sha256: str
    optimizer_steps: int
    completed_epochs: int
    status: str = "TRAINED_PHASE6_CHECKPOINT_BOUND"

    def __post_init__(self) -> None:
        if (len(self.checkpoint_sha256) != 64 or
                any(char not in "0123456789abcdef" for char in self.checkpoint_sha256) or
                self.optimizer_steps <= 0 or self.completed_epochs <= 0 or
                self.status != "TRAINED_PHASE6_CHECKPOINT_BOUND"):
            raise ValueError("Primary training provenance is invalid")

    def as_dict(self) -> dict[str, str | int]:
        return {"phase": "cluster_consumers",
                "checkpoint_sha256": self.checkpoint_sha256,
                "optimizer_steps": self.optimizer_steps,
                "completed_epochs": self.completed_epochs,
                "primary_status": self.status}


@torch.no_grad()
def score_final_primary(*, core: V3Core, final: FinalClusterFeatureLease,
                        closure: EventClosure,
                        statement_states: Mapping[str, torch.Tensor],
                        assertor_states: Mapping[str, torch.Tensor],
                        training_provenance: PrimaryTrainingProvenance | None = None
                        ) -> tuple[PrimaryScore, ...]:
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
        output.append(PrimaryScore(
            local_id, "EVENT_CLUSTER" if kind == "E" else "STATEMENT", value,
            training_provenance.status if training_provenance is not None else
            "UNTRAINED_FRESH_WEIGHT_DIAGNOSTIC"))
    return tuple(output)
