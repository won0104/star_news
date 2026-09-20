"""EntityMention 동일성 전용 scorer."""

from __future__ import annotations

from torch import nn

from ..contracts import PairConfig, PairOutput
from .symmetric import SymmetricPairEncoder


class EntityCoreferenceHead(nn.Module):
    """Entity surface/type policy feature를 받는 독립 encoder+KEEP/MERGE branch."""

    def __init__(self, config: PairConfig, labels: int = 2) -> None:
        super().__init__()
        self.encoder = SymmetricPairEncoder(config)
        self.classifier = nn.Linear(config.hidden_size, labels)

    def forward(self, candidate_states, candidate_spans, candidate_mask, pairs, document_state):
        states, mask = self.encoder(
            candidate_states, candidate_spans, candidate_mask, pairs, document_state
        )
        return PairOutput(self.classifier(states), mask)
