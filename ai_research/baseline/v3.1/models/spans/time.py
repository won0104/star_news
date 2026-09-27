"""KF L10 TimeExpression heads.

``TimeBIOHead`` is retained only for historical checkpoint compatibility.  The
canonical Curated-RC contract is the subtype-free, span-native binary head below;
normalization remains a deterministic graph-assembly responsibility.
"""

from __future__ import annotations

from .entity import EntityBIOHead, EntitySpanNativeHead


class TimeBIOHead(EntityBIOHead):
    """``[B,S,T,768] -> [B,S,T,1+2*time_types]``."""


class TimeExpressionSpanNativeHead(EntitySpanNativeHead):
    """Score each contiguous span as generic ``TIME_EXPRESSION`` or not.

    The inherited character-boundary projection preserves exact source offsets
    and permits nested/overlapping spans without introducing neural temporal
    subtypes.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        dropout: float,
        boundary_feature_size: int = 4,
    ) -> None:
        super().__init__(
            input_size,
            hidden_size,
            entity_types=1,
            dropout=dropout,
            boundary_feature_size=boundary_feature_size,
        )
