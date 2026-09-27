"""교체 가능한 task adapter와 registry 공개 API."""

from .base import (
    AlignedProposalTarget,
    AlignedSpanTarget,
    ClassificationLossStrategy,
    CrossEntropyLossStrategy,
    FocalCrossEntropyLossStrategy,
    TargetBuildContext,
    TaskAdapter,
    TaskLossResult,
    TaskRegistry,
)
from .baseline import BaselineTaskRegistry
from .trigger import TriggerBoundaryLossStrategy

__all__ = [
    "AlignedProposalTarget",
    "AlignedSpanTarget",
    "BaselineTaskRegistry",
    "ClassificationLossStrategy",
    "CrossEntropyLossStrategy",
    "FocalCrossEntropyLossStrategy",
    "TargetBuildContext",
    "TaskAdapter",
    "TaskLossResult",
    "TaskRegistry",
    "TriggerBoundaryLossStrategy",
]
