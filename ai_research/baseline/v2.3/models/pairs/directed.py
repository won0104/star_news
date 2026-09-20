"""방향 pair task가 공유하는 source→target representation."""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import LEGACY_PAIR_TASKS, PairConfig, PairIndexBatch, SPAN_KINDS


class DirectedPairEncoder(nn.Module):
    """사전 제한된 ``[B,P]`` pair를 공통 ``[B,P,H]``로 encoding한다.

    source/target, kind, signed sentence distance, relative order, document context,
    candidate-policy features와 task embedding을 사용한다. Head별 classifier parameter는
    이 모듈 밖에 있어 supervision responsibility를 하나의 Head로 합치지 않는다.
    """

    def __init__(
        self,
        config: PairConfig,
        *,
        task_names: tuple[str, ...] = LEGACY_PAIR_TASKS,
    ) -> None:
        super().__init__()
        if not task_names or len(set(task_names)) != len(task_names):
            raise ValueError("directed pair task names must be non-empty and unique")
        self.config = config
        self.task_names = tuple(task_names)
        self.source_kind = nn.Embedding(len(SPAN_KINDS), config.kind_embedding_size)
        self.target_kind = nn.Embedding(len(SPAN_KINDS), config.kind_embedding_size)
        self.distance = nn.Embedding(
            config.max_sentence_distance * 2 + 1,
            config.distance_embedding_size,
        )
        self.order = nn.Embedding(3, config.order_embedding_size)
        self.task = nn.Embedding(len(self.task_names), config.task_embedding_size)
        feature_size = (
            config.hidden_size * 5
            + config.kind_embedding_size * 2
            + config.distance_embedding_size
            + config.order_embedding_size
            + config.task_embedding_size
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
        candidate_kinds: torch.LongTensor,
        candidate_mask: torch.BoolTensor,
        pairs: PairIndexBatch,
        document_state: torch.Tensor,
        *,
        task_name: str,
    ) -> tuple[torch.Tensor, torch.BoolTensor]:
        try:
            task_id = self.task_names.index(task_name)
        except ValueError as error:
            raise ValueError(f"unknown directed pair task: {task_name}") from error
        pairs.validate(candidate_states.shape[1])
        source, source_mask = _gather(candidate_states, candidate_mask, pairs.source_indices)
        target, target_mask = _gather(candidate_states, candidate_mask, pairs.target_indices)
        source_spans, _ = _gather(candidate_spans, candidate_mask, pairs.source_indices)
        target_spans, _ = _gather(candidate_spans, candidate_mask, pairs.target_indices)
        source_kinds, _ = _gather(candidate_kinds, candidate_mask, pairs.source_indices)
        target_kinds, _ = _gather(candidate_kinds, candidate_mask, pairs.target_indices)
        source_kinds = source_kinds.long().clamp(0, len(SPAN_KINDS) - 1)
        target_kinds = target_kinds.long().clamp(0, len(SPAN_KINDS) - 1)
        distance = (target_spans[..., 0] - source_spans[..., 0]).clamp(
            -self.config.max_sentence_distance,
            self.config.max_sentence_distance,
        )
        source_order = source_spans[..., 0] * 100000 + source_spans[..., 1]
        target_order = target_spans[..., 0] * 100000 + target_spans[..., 1]
        order = torch.where(
            target_order < source_order,
            torch.zeros_like(source_order),
            torch.where(target_order == source_order, torch.ones_like(source_order), torch.full_like(source_order, 2)),
        )
        pair_mask = pairs.mask & source_mask & target_mask
        task = self.task.weight[task_id].view(1, 1, -1).expand(
            source.shape[0], source.shape[1], -1
        )
        document = document_state.unsqueeze(1).expand(-1, source.shape[1], -1)
        features = torch.cat(
            (
                source,
                target,
                source * target,
                source - target,
                document,
                self.source_kind(source_kinds),
                self.target_kind(target_kinds),
                self.distance(distance + self.config.max_sentence_distance),
                self.order(order),
                task,
                pairs.policy_features.to(source.dtype),
            ),
            dim=-1,
        )
        return self.output(features) * pair_mask.unsqueeze(-1), pair_mask


def _gather(
    values: torch.Tensor,
    candidate_mask: torch.BoolTensor,
    indices: torch.LongTensor,
) -> tuple[torch.Tensor, torch.BoolTensor]:
    if values.shape[:2] != candidate_mask.shape:
        raise ValueError("candidate values and mask must align")
    safe = indices.clamp(0, max(values.shape[1] - 1, 0))
    if values.shape[1] == 0:
        output = values.new_zeros((*indices.shape, *values.shape[2:]))
        return output, torch.zeros_like(indices, dtype=torch.bool)
    suffix = values.shape[2:]
    gather_index = safe.reshape(*safe.shape, *([1] * len(suffix))).expand(*safe.shape, *suffix)
    output = values.gather(1, gather_index)
    active = candidate_mask.gather(1, safe)
    return output, active
