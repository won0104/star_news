"""Production relation family별 독립 binary classifier.

공통 ``DirectedPairEncoder``는 재사용하지만 CAUSES, SUBEVENT_OF, ABOUT이 하나의
softmax에서 경쟁하지 않게 각 classifier가 별도 label space를 소유한다.
"""

from __future__ import annotations

from torch import nn

from ..contracts import PairOutput


class BinaryRelationHead(nn.Module):
    """독립적인 ``NONE / positive`` relation classifier."""

    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.classifier = nn.Linear(hidden_size, 2)

    def forward(self, pair_states, pair_mask, class_mask=None) -> PairOutput:
        logits = self.classifier(pair_states)
        if class_mask is not None:
            logits = logits.masked_fill(~class_mask, -1e4)
        return PairOutput(logits, pair_mask, class_mask)


class CausalHead(BinaryRelationHead):
    """Event → Event CAUSES binary classifier."""


class SubeventHead(BinaryRelationHead):
    """Child Event → parent Event SUBEVENT_OF binary classifier."""


class StatementAboutHead(BinaryRelationHead):
    """Statement → Event/Entity ABOUT binary classifier."""
