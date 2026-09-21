"""Participant evidence to EntityMention resolution scorer.

This head only ranks a pre-audited directed candidate universe. It does not
change raw participant spans, create Entity mentions, or infer coreference.
"""

from __future__ import annotations

from torch import nn

from ..contracts import PairConfig, PairOutput
from .directed import DirectedPairEncoder


class ParticipantEntityResolutionHead(nn.Module):
    """Score directed Participant→EntityMention pairs with one binary logit."""

    TASK_NAME = "participant_entity_resolution"

    def __init__(self, config: PairConfig) -> None:
        super().__init__()
        self.encoder = DirectedPairEncoder(config, task_names=(self.TASK_NAME,))
        self.classifier = nn.Linear(config.hidden_size, 1)

    def forward(
        self,
        candidate_states,
        candidate_spans,
        candidate_kinds,
        candidate_mask,
        pairs,
        document_state,
    ):
        states, mask = self.encoder(
            candidate_states,
            candidate_spans,
            candidate_kinds,
            candidate_mask,
            pairs,
            document_state,
            task_name=self.TASK_NAME,
        )
        return PairOutput(self.classifier(states), mask)
