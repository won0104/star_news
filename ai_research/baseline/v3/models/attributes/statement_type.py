"""Statement span representation의 교체 가능한 taxonomy classifier."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import PairOutput


class StatementTypeHead(nn.Module):
    """``[B,N,H] -> [B,N,C]``; C는 Gold adapter/config가 정한다."""

    def __init__(self, hidden_size: int, labels: int, dropout: float) -> None:
        super().__init__()
        self.classifier = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, labels),
        )

    def forward(self, states: torch.Tensor, mask: torch.BoolTensor) -> PairOutput:
        if states.ndim != 3 or mask.shape != states.shape[:2]:
            raise ValueError("statement type expects [B,N,H] and mask [B,N]")
        return PairOutput(self.classifier(states), mask)
