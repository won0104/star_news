"""Event/Statement→Event/Entity graph relation classifier."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import PairOutput


class RelationHead(nn.Module):
    """Class mask는 endpoint kind별 allowed label을 보존하며 loss/decoder가 사용한다."""

    def __init__(self, hidden_size: int, labels: int) -> None:
        super().__init__()
        self.classifier = nn.Linear(hidden_size, labels)

    def forward(
        self,
        pair_states: torch.Tensor,
        pair_mask: torch.BoolTensor,
        class_mask: torch.BoolTensor | None,
    ) -> PairOutput:
        logits = self.classifier(pair_states)
        if class_mask is not None:
            logits = logits.masked_fill(~class_mask, -1e4)
        return PairOutput(logits, pair_mask, class_mask)
