"""공개 EventFeatureBundle에서 투영된 state를 받는 독립 Event merge scorer."""

from __future__ import annotations

from torch import nn

from ..contracts import PairConfig, PairOutput
from .symmetric import SymmetricPairEncoder


class EventCoreferenceHead(nn.Module):
    """Entity coreference와 parameter를 공유하지 않는 Event 전용 scorer."""

    def __init__(self, config: PairConfig, labels: int = 2) -> None:
        super().__init__()
        self.pair_encoder = SymmetricPairEncoder(config)
        self.classifier = nn.Linear(config.hidden_size, labels)

    def forward(self, candidate_states, candidate_spans, candidate_mask, pairs, document_state):
        states, mask = self.pair_encoder(
            candidate_states, candidate_spans, candidate_mask, pairs, document_state
        )
        return PairOutput(self.classifier(states), mask)
