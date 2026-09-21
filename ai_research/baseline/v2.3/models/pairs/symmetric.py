"""순서 불변 coreference pair representation family."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import PairConfig, PairIndexBatch
from .directed import _gather


class SymmetricPairEncoder(nn.Module):
    """sum/product/absolute-difference만 사용해 A,B swap invariance를 보장한다."""

    def __init__(self, config: PairConfig) -> None:
        super().__init__()
        self.config = config
        self.distance = nn.Embedding(
            config.max_sentence_distance + 1,
            config.distance_embedding_size,
        )
        feature_size = (
            config.hidden_size * 4
            + config.distance_embedding_size
            + config.policy_feature_size
        )
        self.output = nn.Sequential(
            nn.Linear(feature_size, config.projection_size),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.projection_size, config.hidden_size),
            nn.LayerNorm(config.hidden_size),
        )

    def forward(
        self,
        candidate_states: torch.Tensor,
        candidate_spans: torch.LongTensor,
        candidate_mask: torch.BoolTensor,
        pairs: PairIndexBatch,
        document_state: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.BoolTensor]:
        pairs.validate(candidate_states.shape[1])
        left, left_mask = _gather(candidate_states, candidate_mask, pairs.source_indices)
        right, right_mask = _gather(candidate_states, candidate_mask, pairs.target_indices)
        left_spans, _ = _gather(candidate_spans, candidate_mask, pairs.source_indices)
        right_spans, _ = _gather(candidate_spans, candidate_mask, pairs.target_indices)
        distance = (left_spans[..., 0] - right_spans[..., 0]).abs().clamp(
            0, self.config.max_sentence_distance
        )
        pair_mask = pairs.mask & left_mask & right_mask
        document = document_state.unsqueeze(1).expand(-1, left.shape[1], -1)
        features = torch.cat(
            (
                left + right,
                left * right,
                (left - right).abs(),
                document,
                self.distance(distance),
                pairs.policy_features.to(left.dtype),
            ),
            dim=-1,
        )
        return self.output(features) * pair_mask.unsqueeze(-1), pair_mask
