"""128-token window를 넘는 exact 문자 span의 공유 feature·residual 경계.

한 article의 이미 계산된 L8/L10/L12와 단일 DCE만 사용한다. window 내부는
기존 CandidateSpanEncoder의 direct gather를 쓰고, 교차 span만 양 끝을 모은다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import torch
from torch import nn

from models.contracts import ArticleBatch, BackboneOutput, CandidateBatch, SPAN_KINDS
from runtime.v3_pretraining.source_layout import SourceLayout, SpanAlignment


KIND_TO_SPAN = {"EVENT": "EVENT", "STATEMENT": "STATEMENT", "TRIGGER": "TRIGGER",
                "PARTICIPANT": "EVIDENCE", "ENTITY": "ENTITY", "TIME": "TIME"}
KIND_LAYER = {"EVENT": 8, "STATEMENT": 8, "TRIGGER": 8, "PARTICIPANT": 8,
              "ENTITY": 12, "TIME": 10}


@dataclass(slots=True)
class ExactSpanFeatures:
    states: torch.Tensor  # [N,256]
    residuals: torch.Tensor  # [N,2], signed character deltas
    link_logits: torch.Tensor  # [N], includes cross-window endpoint pairs
    local_mask: tuple[bool, ...]


def _candidate_batch(rows: list[tuple[int, int, int]], kind_ids: list[int],
                     device: torch.device) -> CandidateBatch:
    count = len(rows)
    empty_indices = torch.zeros((1, 0), dtype=torch.long, device=device)
    empty_mask = torch.zeros((1, 0), dtype=torch.bool, device=device)
    return CandidateBatch(
        span_indices=torch.tensor([rows], dtype=torch.long, device=device),
        span_kind_ids=torch.tensor([kind_ids], dtype=torch.long, device=device),
        span_mask=torch.ones((1, count), dtype=torch.bool, device=device),
        semantic_proposal_indices=torch.zeros((1, 0, 3), dtype=torch.long, device=device),
        semantic_proposal_mask=empty_mask,
        statement_indices=empty_indices, statement_mask=empty_mask,
        event_indices=empty_indices, event_source_indices=empty_indices, event_mask=empty_mask,
        event_trigger_indices=empty_indices, event_trigger_mask=empty_mask,
        oracle_argument_role_weights=None, pairs={}, pair_task_names=(),
    )


class ExactSourceSpanBridge(nn.Module):
    """기존 in-window projection과 cross-window 양 끝 projection의 단일 owner."""

    def __init__(self, *, hidden_size: int = 256, raw_size: int = 768) -> None:
        super().__init__()
        self.cross_projection = nn.Sequential(
            nn.Linear(raw_size * 2 + hidden_size * 3 + 2, hidden_size),
            nn.GELU(), nn.LayerNorm(hidden_size),
        )
        self.kind_embedding = nn.Embedding(len(KIND_LAYER), 16)
        self.endpoint = nn.Linear(hidden_size, len(KIND_LAYER) * 2)
        self.residual = nn.Sequential(nn.Linear(hidden_size * 3 + 16, hidden_size),
                                      nn.GELU(), nn.Linear(hidden_size, 2))
        self.link = nn.Sequential(nn.Linear(hidden_size * 3 + 16, hidden_size),
                                  nn.GELU(), nn.Linear(hidden_size, 1))

    def endpoint_logits(self, token_states: torch.Tensor) -> torch.Tensor:
        """Gold 없이 bridge source token의 kind별 start/end를 제안한다."""
        return self.endpoint(token_states).view(*token_states.shape[:3], len(KIND_LAYER), 2)

    def forward(self, *, layout: SourceLayout, batch: ArticleBatch,
                backbone: BackboneOutput, token_states: torch.Tensor,
                sentence_states: torch.Tensor, document_state: torch.Tensor,
                candidate_encoder: nn.Module,
                rows: Sequence[tuple[SpanAlignment, str]],
                runtime_sentence_cache=None,
                native_state_lookup: Callable[[str, int, int, int, SpanAlignment],
                                              torch.Tensor | None] | None = None
                ) -> ExactSpanFeatures:
        if batch.input_ids.shape[0] != 1 or batch.input_ids.shape[1] != len(layout.windows):
            raise ValueError("exact bridge requires one article with all source windows")
        if batch.contents[0] != layout.article.content or token_states.shape[:3] != batch.input_ids.shape:
            raise ValueError("source layout and shared DCE input differ")
        # Validation is integer-only. Copy once per chunk instead of forcing an
        # MPS synchronization for every window and every candidate endpoint.
        input_ids_cpu = batch.input_ids[0].detach().cpu()
        offsets_cpu = batch.token_offsets[0].detach().cpu()
        for position, window in enumerate(layout.windows):
            expected = torch.tensor(window.input_ids, dtype=input_ids_cpu.dtype)
            if not torch.equal(input_ids_cpu[position, :len(window.input_ids)], expected):
                raise ValueError("source layout window order or tokenizer input differs")
        device = token_states.device
        window_index = {window.window_id: index for index, window in enumerate(layout.windows)}
        local_rows: list[tuple[int, int, int]] = []
        local_kinds: list[int] = []
        local_positions: list[int] = []
        reused: dict[int, torch.Tensor] = {}
        for index, (span, kind) in enumerate(rows):
            if kind not in KIND_LAYER or layout.reconstruct(span) != (span.start, span.end, span.text):
                raise ValueError("unknown kind or non-exact source span")
            for ref in (span.start_ref, span.end_ref):
                row = window_index[ref.window_id]
                token = layout.window_lookup[ref.window_id].tokens
                source = next(item for item in token if item.position == ref.token_position)
                offsets = offsets_cpu[row, ref.token_position]
                if (int(offsets[0]), int(offsets[1])) != (source.start, source.end):
                    raise ValueError("source window token alignment differs")
            if span.canonical_window_id is not None:
                row = window_index[span.canonical_window_id]
                first, last = span.start_ref.token_position, span.end_ref.token_position + 1
                cached = (native_state_lookup(kind, row, first, last, span)
                          if native_state_lookup is not None else None)
                if cached is None:
                    local_rows.append((row, first, last))
                    local_kinds.append(SPAN_KINDS.index(KIND_TO_SPAN[kind]))
                    local_positions.append(index)
                else:
                    if (cached.shape != (token_states.shape[-1],) or
                            cached.device != device or cached.dtype != token_states.dtype):
                        raise ValueError("native span cache representation differs")
                    reused[index] = cached
        if local_rows:
            candidates = _candidate_batch(local_rows, local_kinds, device)
            local_features = candidate_encoder.forward_runtime_direct_states(
                backbone, sentence_states, candidates, batch.source_token_mask,
                sentence_cache=runtime_sentence_cache)[0]
        else:
            local_features = token_states.new_empty((0, token_states.shape[-1]))
        local_lookup = {position: local_features[offset] for offset, position in enumerate(local_positions)}
        local_lookup.update(reused)
        feature_rows = []
        start_rows = []
        end_rows = []
        kind_rows = []
        for index, (span, kind) in enumerate(rows):
            start_row, end_row = window_index[span.start_ref.window_id], window_index[span.end_ref.window_id]
            start_pos, end_pos = span.start_ref.token_position, span.end_ref.token_position
            start_dce = token_states[0, start_row, start_pos]
            end_dce = token_states[0, end_row, end_pos]
            start_rows.append(start_dce)
            end_rows.append(end_dce)
            kind_rows.append(list(KIND_LAYER).index(kind))
            if index in local_lookup:
                feature_rows.append(local_lookup[index])
                continue
            layer = KIND_LAYER[kind]
            raw_start = backbone.layer(layer)[0, start_row, start_pos]
            raw_end = backbone.layer(layer)[0, end_row, end_pos]
            geometry = token_states.new_tensor((span.start / max(len(layout.article.content), 1),
                                                span.end / max(len(layout.article.content), 1)))
            vector = torch.cat((raw_start, raw_end, start_dce, end_dce,
                                document_state[0], geometry), dim=-1)
            feature_rows.append(self.cross_projection(vector))
        if not rows:
            empty = token_states.new_empty((0, token_states.shape[-1]))
            return ExactSpanFeatures(empty, token_states.new_empty((0, 2)),
                                     token_states.new_empty((0,)), ())
        states = torch.stack(feature_rows)
        kind_tensor = torch.tensor(kind_rows, dtype=torch.long, device=device)
        combined = torch.cat((states, torch.stack(start_rows), torch.stack(end_rows),
                              self.kind_embedding(kind_tensor)), dim=-1)
        return ExactSpanFeatures(states, self.residual(combined), self.link(combined).squeeze(-1),
                                 tuple(index in local_lookup for index in range(len(rows))))
