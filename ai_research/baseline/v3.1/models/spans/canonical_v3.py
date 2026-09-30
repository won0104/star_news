"""Release-local canonical proposer and Canonical Span V3 architectures.

This module is inference-only.  It intentionally contains no training import,
Gold adapter, proposal prior feature, threshold selection, or overlap decoder.
All token and span indices use end-exclusive ``[start, end)`` semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn


RAW_HIDDEN = 768
DCE_HIDDEN = 256
FUSED_HIDDEN = 256
Z_SPAN_HIDDEN = 256
SPAN_ATTENTION_HIDDEN = 128
WIDTH_EMBED_DIM = 32
LABEL_EMBED_DIM = 64
LABEL_COUNT = 2
DROPOUT = 0.1
MAX_SPAN_WIDTH = 96
BOUNDARY_VECTOR_INIT_SEED = 38003


@dataclass(frozen=True)
class CanonicalSpanV3Output:
    """Label-independent span state plus two private label-aware decisions."""

    z_span: torch.Tensor
    semantic_logits: torch.Tensor
    boundary_logits: torch.Tensor
    proposal_mask: torch.BoolTensor


class JointSpanProposalHead(nn.Module):
    """Score each ``(start, end-inclusive, label)`` proposal cell."""

    def __init__(
        self,
        hidden_size: int = DCE_HIDDEN,
        labels: int = LABEL_COUNT,
        projection_size: int = 128,
        dropout: float = DROPOUT,
    ) -> None:
        super().__init__()
        self.labels = labels
        self.start_projection = nn.Sequential(
            nn.Linear(hidden_size, projection_size), nn.GELU(), nn.Dropout(dropout)
        )
        self.end_projection = nn.Sequential(
            nn.Linear(hidden_size, projection_size), nn.GELU(), nn.Dropout(dropout)
        )
        self.biaffine = nn.Parameter(torch.empty(labels, projection_size, projection_size))
        self.label_bias = nn.Parameter(torch.zeros(labels))
        nn.init.xavier_uniform_(self.biaffine)

    def forward(self, token_states: torch.Tensor) -> torch.Tensor:
        start = self.start_projection(token_states)
        end = self.end_projection(token_states)
        return (
            torch.einsum("bstd,ldh,bsuh->bstul", start, self.biaffine, end)
            + self.label_bias
        )


class CanonicalTokenFusion(nn.Module):
    """Fuse RAW L8 and same-seed DCE tokens without proposer metadata."""

    def __init__(self) -> None:
        super().__init__()
        self.raw_projection = nn.Linear(RAW_HIDDEN, FUSED_HIDDEN)
        self.dce_projection = nn.Linear(DCE_HIDDEN, FUSED_HIDDEN)
        self.fusion_norm = nn.LayerNorm(FUSED_HIDDEN)

    def forward(
        self, raw_token_states: torch.Tensor, dce_token_states: torch.Tensor
    ) -> torch.Tensor:
        if raw_token_states.ndim != 4 or raw_token_states.shape[-1] != RAW_HIDDEN:
            raise ValueError("raw_token_states must have shape [B,S,T,768]")
        if dce_token_states.ndim != 4 or dce_token_states.shape[-1] != DCE_HIDDEN:
            raise ValueError("dce_token_states must have shape [B,S,T,256]")
        if raw_token_states.shape[:3] != dce_token_states.shape[:3]:
            raise ValueError("RAW and DCE token axes must match")
        return self.fusion_norm(
            self.raw_projection(raw_token_states)
            + self.dce_projection(dce_token_states)
        )


class CanonicalSpanEncoder(nn.Module):
    """Encode one candidate independently into label-free ``z_span``."""

    def __init__(self) -> None:
        super().__init__()
        self.span_attention = nn.Sequential(
            nn.Linear(FUSED_HIDDEN, SPAN_ATTENTION_HIDDEN),
            nn.Tanh(),
            nn.Linear(SPAN_ATTENTION_HIDDEN, 1, bias=False),
        )
        self.width_embedding = nn.Embedding(MAX_SPAN_WIDTH + 1, WIDTH_EMBED_DIM)
        self.span_projection = nn.Sequential(
            nn.Linear(3 * FUSED_HIDDEN + WIDTH_EMBED_DIM, Z_SPAN_HIDDEN),
            nn.GELU(),
            nn.Dropout(DROPOUT),
            nn.LayerNorm(Z_SPAN_HIDDEN),
        )

    def forward(
        self,
        fused_token_states: torch.Tensor,
        proposals: torch.LongTensor,
        proposal_mask: torch.BoolTensor,
        token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        _validate_candidate_inputs(fused_token_states, proposals, proposal_mask, token_mask)
        batch_size, candidate_count = proposals.shape[:2]
        if candidate_count == 0:
            return fused_token_states.new_zeros(batch_size, 0, Z_SPAN_HIDDEN)
        safe = _safe_proposals(proposals, fused_token_states.shape[1:3])
        batch_indices = torch.arange(batch_size, device=fused_token_states.device).unsqueeze(1)
        sentence_indices = safe[..., 0]
        sentence_tokens = fused_token_states[batch_indices, sentence_indices]
        sentence_mask = token_mask[batch_indices, sentence_indices]
        starts, ends = safe[..., 1], safe[..., 2]
        start_states = _gather_token(sentence_tokens, starts)
        end_states = _gather_token(sentence_tokens, ends - 1)
        positions = torch.arange(
            fused_token_states.shape[2], device=fused_token_states.device
        ).view(1, 1, -1)
        inside = (
            (positions >= starts.unsqueeze(-1))
            & (positions < ends.unsqueeze(-1))
            & sentence_mask
            & proposal_mask.unsqueeze(-1)
        )
        attention_logits = self.span_attention(sentence_tokens).squeeze(-1)
        attention_logits = attention_logits.masked_fill(~inside, -1e4)
        attention = torch.softmax(attention_logits, dim=-1) * inside.to(attention_logits.dtype)
        attention = attention / attention.sum(dim=-1, keepdim=True).clamp_min(1e-8)
        content = torch.einsum("bqt,bqth->bqh", attention, sentence_tokens)
        widths = (ends - starts).clamp(0, MAX_SPAN_WIDTH)
        features = torch.cat(
            (start_states, end_states, content, self.width_embedding(widths)), dim=-1
        )
        z_span = self.span_projection(features)
        return z_span * proposal_mask.unsqueeze(-1).to(z_span.dtype)


class SemanticEligibilityHead(nn.Module):
    """Apply label embeddings only inside the private Semantic head."""

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(Z_SPAN_HIDDEN + LABEL_EMBED_DIM, 128),
            nn.GELU(),
            nn.Dropout(DROPOUT),
            nn.Linear(128, 1),
        )

    def forward(
        self,
        z_span: torch.Tensor,
        label_embeddings: torch.Tensor,
        proposal_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        expanded_span, expanded_labels = _expand_labels(z_span, label_embeddings)
        logits = self.network(torch.cat((expanded_span, expanded_labels), dim=-1))
        return logits.squeeze(-1) * proposal_mask.unsqueeze(-1).to(logits.dtype)


class BoundaryExactnessHead(nn.Module):
    """Judge exact boundaries using private label-aware transition features."""

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(Z_SPAN_HIDDEN + 2 * FUSED_HIDDEN + LABEL_EMBED_DIM, 256),
            nn.GELU(),
            nn.Dropout(DROPOUT),
            nn.Linear(256, 1),
        )

    def forward(
        self,
        z_span: torch.Tensor,
        left_transition: torch.Tensor,
        right_transition: torch.Tensor,
        label_embeddings: torch.Tensor,
        proposal_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        expanded_span, expanded_labels = _expand_labels(z_span, label_embeddings)
        label_count = label_embeddings.shape[0]
        left = left_transition.unsqueeze(2).expand(-1, -1, label_count, -1)
        right = right_transition.unsqueeze(2).expand(-1, -1, label_count, -1)
        logits = self.network(
            torch.cat((expanded_span, left, right, expanded_labels), dim=-1)
        )
        return logits.squeeze(-1) * proposal_mask.unsqueeze(-1).to(logits.dtype)


class CanonicalSpanRepresentationV3(nn.Module):
    """Exact #38 architecture promoted as the v2 inference-only scorer."""

    def __init__(self) -> None:
        super().__init__()
        self.token_fusion = CanonicalTokenFusion()
        self.span_encoder = CanonicalSpanEncoder()
        self.label_embedding = nn.Embedding(LABEL_COUNT, LABEL_EMBED_DIM)
        self.semantic_head = SemanticEligibilityHead()
        self.boundary_head = BoundaryExactnessHead()
        generator = torch.Generator(device="cpu")
        generator.manual_seed(BOUNDARY_VECTOR_INIT_SEED)
        bound = 1.0 / math.sqrt(FUSED_HIDDEN)
        self.bos_boundary = nn.Parameter(
            torch.empty(FUSED_HIDDEN).uniform_(-bound, bound, generator=generator)
        )
        self.eos_boundary = nn.Parameter(
            torch.empty(FUSED_HIDDEN).uniform_(-bound, bound, generator=generator)
        )

    def forward(
        self,
        raw_token_states: torch.Tensor,
        dce_token_states: torch.Tensor,
        proposals: torch.LongTensor,
        proposal_mask: torch.BoolTensor,
        token_mask: torch.BoolTensor,
    ) -> CanonicalSpanV3Output:
        fused_tokens = self.token_fusion(raw_token_states, dce_token_states)
        z_span = self.span_encoder(fused_tokens, proposals, proposal_mask, token_mask)
        left, right = self._boundary_transitions(
            fused_tokens, proposals, proposal_mask, token_mask
        )
        semantic_logits = self.semantic_head(
            z_span, self.label_embedding.weight, proposal_mask
        )
        boundary_logits = self.boundary_head(
            z_span, left, right, self.label_embedding.weight, proposal_mask
        )
        return CanonicalSpanV3Output(
            z_span=z_span,
            semantic_logits=semantic_logits,
            boundary_logits=boundary_logits,
            proposal_mask=proposal_mask,
        )

    def _boundary_transitions(
        self,
        fused_token_states: torch.Tensor,
        proposals: torch.LongTensor,
        proposal_mask: torch.BoolTensor,
        token_mask: torch.BoolTensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        _validate_candidate_inputs(fused_token_states, proposals, proposal_mask, token_mask)
        batch_size, candidate_count = proposals.shape[:2]
        if candidate_count == 0:
            empty = fused_token_states.new_zeros(batch_size, 0, FUSED_HIDDEN)
            return empty, empty.clone()
        safe = _safe_proposals(proposals, fused_token_states.shape[1:3])
        batch_indices = torch.arange(batch_size, device=fused_token_states.device).unsqueeze(1)
        sentence_tokens = fused_token_states[batch_indices, safe[..., 0]]
        sentence_mask = token_mask[batch_indices, safe[..., 0]]
        starts, ends = safe[..., 1], safe[..., 2]
        start_inside = _gather_token(sentence_tokens, starts)
        end_inside = _gather_token(sentence_tokens, ends - 1)
        left_positions = (starts - 1).clamp(0, fused_token_states.shape[2] - 1)
        left_token = _gather_token(sentence_tokens, left_positions)
        left_valid = (starts > 0) & sentence_mask.gather(
            2, left_positions.unsqueeze(-1)
        ).squeeze(-1)
        left_outside = torch.where(
            left_valid.unsqueeze(-1), left_token, self.bos_boundary.view(1, 1, -1)
        )
        right_positions = ends.clamp(0, fused_token_states.shape[2] - 1)
        right_token = _gather_token(sentence_tokens, right_positions)
        right_valid = (ends < fused_token_states.shape[2]) & sentence_mask.gather(
            2, right_positions.unsqueeze(-1)
        ).squeeze(-1)
        right_outside = torch.where(
            right_valid.unsqueeze(-1), right_token, self.eos_boundary.view(1, 1, -1)
        )
        active = proposal_mask.unsqueeze(-1).to(fused_token_states.dtype)
        return (
            (start_inside - left_outside) * active,
            (end_inside - right_outside) * active,
        )


def _expand_labels(
    z_span: torch.Tensor, label_embeddings: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    batch_size, candidate_count = z_span.shape[:2]
    label_count = label_embeddings.shape[0]
    return (
        z_span.unsqueeze(2).expand(-1, -1, label_count, -1),
        label_embeddings.view(1, 1, label_count, -1).expand(
            batch_size, candidate_count, -1, -1
        ),
    )


def _gather_token(
    sentence_tokens: torch.Tensor, positions: torch.LongTensor
) -> torch.Tensor:
    hidden_size = sentence_tokens.shape[-1]
    return sentence_tokens.gather(
        2, positions[..., None, None].expand(-1, -1, 1, hidden_size)
    ).squeeze(2)


def _safe_proposals(
    proposals: torch.LongTensor, sentence_token_shape: tuple[int, int]
) -> torch.LongTensor:
    sentence_count, token_count = sentence_token_shape
    safe = proposals.clone()
    safe[..., 0] = safe[..., 0].clamp(0, sentence_count - 1)
    safe[..., 1] = safe[..., 1].clamp(0, token_count - 1)
    safe[..., 2] = safe[..., 2].clamp(1, token_count)
    return safe


def _validate_candidate_inputs(
    token_states: torch.Tensor,
    proposals: torch.LongTensor,
    proposal_mask: torch.BoolTensor,
    token_mask: torch.BoolTensor,
) -> None:
    if token_states.ndim != 4 or token_states.shape[-1] != FUSED_HIDDEN:
        raise ValueError("fused token states must have shape [B,S,T,256]")
    if proposals.ndim != 3 or proposals.shape[-1] != 3:
        raise ValueError("proposals must have shape [B,Q,3]")
    if proposals.shape[:2] != proposal_mask.shape:
        raise ValueError("proposal_mask must have shape [B,Q]")
    if token_states.shape[:3] != token_mask.shape:
        raise ValueError("token_mask must have shape [B,S,T]")
    if proposals.shape[0] != token_states.shape[0]:
        raise ValueError("proposal and token batch sizes must match")
    if proposal_mask.any():
        active = proposals[proposal_mask]
        if torch.any(active[:, 2] <= active[:, 1]):
            raise ValueError("active proposals must have positive end-exclusive width")
