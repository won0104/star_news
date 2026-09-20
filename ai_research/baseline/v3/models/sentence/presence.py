"""EVENT/STATEMENT 독립 bit와 파생 4-state 보조 분류."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import PRESENCE_STATES, PresenceOutput


class SentencePresenceHead(nn.Module):
    """문장별 two-bit logits와 auxiliary 4-state logits를 분리해 출력한다.

    runtime state와 KEEP/DROP은 two-bit threshold에서만 파생한다. 이 출력은 Semantic
    Span의 hard gate가 아니며 model orchestration에서도 span tensor를 마스킹하지 않는다.
    """

    def __init__(self, hidden_size: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.shared = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.bit_classifier = nn.Linear(hidden_size, 2)
        self.state_classifier = nn.Linear(hidden_size, len(PRESENCE_STATES))

    def forward(
        self,
        sentence_states: torch.Tensor,
        sentence_mask: torch.BoolTensor,
        *,
        event_threshold: float = 0.5,
        statement_threshold: float = 0.5,
    ) -> PresenceOutput:
        if sentence_states.ndim != 3 or sentence_mask.shape != sentence_states.shape[:2]:
            raise ValueError("presence expects sentence states [B,S,H] and mask [B,S]")
        hidden = self.shared(sentence_states)
        bit_logits = self.bit_classifier(hidden)
        state_logits = self.state_classifier(hidden)
        probabilities = torch.sigmoid(bit_logits)
        event_present = (probabilities[..., 0] >= event_threshold) & sentence_mask
        statement_present = (probabilities[..., 1] >= statement_threshold) & sentence_mask
        state_ids = event_present.long() + statement_present.long() * 2
        return PresenceOutput(
            bit_logits=bit_logits,
            state_logits=state_logits,
            event_present=event_present,
            statement_present=statement_present,
            state_ids=state_ids,
            keep_mask=event_present | statement_present,
        )
