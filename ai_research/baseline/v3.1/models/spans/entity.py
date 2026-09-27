"""KF L12 Entity extraction heads.

`EntityBIOHead` remains a historical flat baseline. `EntitySpanNativeHead` is the
canonical nested-capable mention representation: every contiguous candidate span
receives independent logits for the existing Entity taxonomy.
"""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import TokenHeadOutput


class EntityBIOHead(nn.Module):
    """``[B,S,T,768] -> [B,S,T,1+2*entity_types]``."""

    def __init__(self, input_size: int, hidden_size: int, labels: int, dropout: float) -> None:
        super().__init__()
        self.classifier = nn.Sequential(
            nn.LayerNorm(input_size),
            nn.Linear(input_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, labels),
        )

    def forward(self, states: torch.Tensor, mask: torch.BoolTensor) -> TokenHeadOutput:
        if states.ndim != 4 or mask.shape != states.shape[:3]:
            raise ValueError("Entity BIO expects states [B,S,T,H] and mask [B,S,T]")
        return TokenHeadOutput(self.classifier(states), mask)


class EntitySpanNativeHead(nn.Module):
    """Classify span rows independently so nesting and overlap remain expressible.

    Boundary features preserve character positions inside the first/last covering
    tokenizer token. They distinguish valid Gold boundaries that cannot be written
    as an exclusive token BIO sequence without changing the original offsets.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        entity_types: int,
        dropout: float,
        boundary_feature_size: int = 4,
    ) -> None:
        super().__init__()
        self.boundary_projection = nn.Sequential(
            nn.Linear(boundary_feature_size, hidden_size // 2),
            nn.GELU(),
            nn.LayerNorm(hidden_size // 2),
        )
        self.classifier = nn.Sequential(
            nn.LayerNorm(input_size + hidden_size // 2),
            nn.Linear(input_size + hidden_size // 2, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, entity_types),
        )

    def forward(
        self,
        span_states: torch.Tensor,
        boundary_features: torch.Tensor,
        mask: torch.BoolTensor,
    ) -> torch.Tensor:
        if span_states.ndim != 3 or boundary_features.shape[:2] != span_states.shape[:2]:
            raise ValueError("Entity span head expects [B,N,H] states and [B,N,F] features")
        if mask.shape != span_states.shape[:2] or mask.dtype is not torch.bool:
            raise ValueError("Entity span mask must be bool [B,N]")
        boundary = self.boundary_projection(boundary_features)
        logits = self.classifier(torch.cat((span_states, boundary), dim=-1))
        return logits.masked_fill(~mask.unsqueeze(-1), 0.0)
