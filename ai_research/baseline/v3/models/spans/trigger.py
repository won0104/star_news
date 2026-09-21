"""KF L8 Event Trigger 독립 start/end boundary Head."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import BoundaryHeadOutput


class TriggerBoundaryHead(nn.Module):
    """``[B,S,T,768] -> start/end [B,S,T,1]``."""

    def __init__(self, input_size: int, hidden_size: int, dropout: float) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(input_size),
            nn.Linear(input_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 2),
        )

    def forward(self, states: torch.Tensor, mask: torch.BoolTensor) -> BoundaryHeadOutput:
        if states.ndim != 4 or mask.shape != states.shape[:3]:
            raise ValueError("Trigger boundary expects states [B,S,T,H] and mask [B,S,T]")
        start, end = self.network(states).split(1, dim=-1)
        return BoundaryHeadOutput(start, end, mask)
