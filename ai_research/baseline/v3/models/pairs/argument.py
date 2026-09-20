"""Event→Candidate ACTOR/TARGET/PLACE/TIME classifier."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import PairOutput


class ArgumentHead(nn.Module):
    def __init__(self, hidden_size: int, labels: int) -> None:
        super().__init__()
        self.classifier = nn.Linear(hidden_size, labels)

    def forward(self, pair_states, pair_mask, class_mask=None) -> PairOutput:
        logits = self.classifier(pair_states)
        if class_mask is not None:
            logits = logits.masked_fill(~class_mask, -1e4)
        return PairOutput(logits, pair_mask, class_mask)
