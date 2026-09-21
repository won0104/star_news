"""Statement→Entity ASSERTED_BY classifier."""

from __future__ import annotations

from torch import nn

from ..contracts import PairOutput


class AssertorHead(nn.Module):
    def __init__(self, hidden_size: int, labels: int = 2) -> None:
        super().__init__()
        self.classifier = nn.Linear(hidden_size, labels)

    def forward(self, pair_states, pair_mask) -> PairOutput:
        return PairOutput(self.classifier(pair_states), pair_mask)
