"""L8 document-aware semantic boundary proposal과 span-pair verification.

start/end 역할 투영과 label별 bilinear score는 Yu et al. (ACL 2020)의 start-end
biaffine scoring 아이디어를, 한 번에 label별 span score를 만드는 계약은 GlobalPointer
계열의 joint start-end 관점을 참고했다. 두 논문의 전체 구조나 loss를 복제하지 않는다.
https://aclanthology.org/2020.acl-main.577/
https://arxiv.org/abs/2208.03054
"""

from __future__ import annotations

import torch
from torch import nn

from ..contracts import BoundaryHeadOutput, SemanticSpanOutput


class BoundaryProposalHead(nn.Module):
    """독립 label별 start/end logits ``[B,S,T,L]``로 high-recall 후보를 제안한다."""

    def __init__(self, hidden_size: int, labels: int, dropout: float) -> None:
        super().__init__()
        self.labels = labels
        self.network = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, labels * 2),
        )

    def forward(self, states: torch.Tensor, mask: torch.BoolTensor) -> BoundaryHeadOutput:
        logits = self.network(states)
        start, end = logits.split(self.labels, dim=-1)
        return BoundaryHeadOutput(start, end, mask)


class SpanPairVerifier(nn.Module):
    """``(start,end,pooled,width,document,label) -> [B,Q,L]`` validity logits.

    label 축은 sigmoid/BCE용이며 softmax 상호배타를 강제하지 않는다. 따라서 동일 exact
    boundary가 EVENT와 STATEMENT 양쪽 target인 현재 Gold도 그대로 학습할 수 있다.
    """

    def __init__(
        self,
        hidden_size: int,
        labels: int,
        biaffine_size: int,
        max_span_width: int,
        width_size: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.labels = labels
        self.max_span_width = max_span_width
        self.start_projection = nn.Sequential(nn.Linear(hidden_size, biaffine_size), nn.GELU())
        self.end_projection = nn.Sequential(nn.Linear(hidden_size, biaffine_size), nn.GELU())
        self.biaffine = nn.Parameter(torch.empty(labels, biaffine_size, biaffine_size))
        nn.init.xavier_uniform_(self.biaffine)
        self.span_attention = nn.Sequential(
            nn.Linear(hidden_size, biaffine_size), nn.Tanh(), nn.Linear(biaffine_size, 1, bias=False)
        )
        self.width_embedding = nn.Embedding(max_span_width + 1, width_size)
        self.label_embedding = nn.Embedding(labels, biaffine_size)
        feature_size = hidden_size * 4 + width_size + biaffine_size
        self.validity = nn.Sequential(
            nn.Linear(feature_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 1),
        )

    def forward(
        self,
        token_states: torch.Tensor,
        sentence_states: torch.Tensor,
        proposals: torch.LongTensor,
        proposal_mask: torch.BoolTensor,
        token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        if proposals.ndim != 3 or proposals.shape[-1] != 3:
            raise ValueError("semantic proposals must have shape [B,Q,3]")
        batch, proposal_count = proposals.shape[:2]
        hidden = token_states.shape[-1]
        if proposal_count == 0:
            return token_states.new_zeros(batch, 0, self.labels)
        safe = proposals.clone()
        safe[..., 0] = safe[..., 0].clamp(0, token_states.shape[1] - 1)
        safe[..., 1] = safe[..., 1].clamp(0, token_states.shape[2] - 1)
        safe[..., 2] = safe[..., 2].clamp(1, token_states.shape[2])
        batch_indices = torch.arange(batch, device=proposals.device).unsqueeze(1)
        sentence_indices = safe[..., 0]
        sentence_tokens = token_states[batch_indices, sentence_indices]
        sentence_token_mask = token_mask[batch_indices, sentence_indices]
        starts, ends = safe[..., 1], safe[..., 2]
        start = sentence_tokens.gather(
            2, starts[..., None, None].expand(-1, -1, 1, hidden)
        ).squeeze(2)
        end = sentence_tokens.gather(
            2, (ends - 1)[..., None, None].expand(-1, -1, 1, hidden)
        ).squeeze(2)
        positions = torch.arange(token_states.shape[2], device=proposals.device).view(1, 1, -1)
        inside = (
            (positions >= starts.unsqueeze(-1))
            & (positions < ends.unsqueeze(-1))
            & sentence_token_mask
            & proposal_mask.unsqueeze(-1)
        )
        attention_logits = self.span_attention(sentence_tokens).squeeze(-1).masked_fill(~inside, -1e4)
        attention = torch.softmax(attention_logits, dim=-1) * inside.to(token_states.dtype)
        attention = attention / attention.sum(dim=-1, keepdim=True).clamp_min(1e-8)
        pooled = torch.einsum("bqt,bqth->bqh", attention, sentence_tokens)
        document = sentence_states[batch_indices, sentence_indices]
        widths = (ends - starts).clamp(0, self.max_span_width)
        base = torch.cat((start, end, pooled, document, self.width_embedding(widths)), dim=-1)
        label_ids = torch.arange(self.labels, device=proposals.device)
        label_features = self.label_embedding(label_ids).view(1, 1, self.labels, -1).expand(
            batch, proposal_count, -1, -1
        )
        expanded = base.unsqueeze(2).expand(-1, -1, self.labels, -1)
        linear_score = self.validity(torch.cat((expanded, label_features), dim=-1)).squeeze(-1)
        start_role = self.start_projection(start)
        end_role = self.end_projection(end)
        bilinear_score = torch.einsum("bqd,ldh,bqh->bql", start_role, self.biaffine, end_role)
        return (linear_score + bilinear_score) * proposal_mask.unsqueeze(-1)


class SemanticSpanHead(nn.Module):
    """Boundary proposal과 proposal verification을 결합하되 decoding은 소유하지 않는다."""

    def __init__(
        self,
        *,
        hidden_size: int,
        labels: int,
        biaffine_size: int,
        max_span_width: int,
        width_size: int,
        dropout: float,
        verifier: nn.Module | None = None,
    ) -> None:
        super().__init__()
        self.boundary = BoundaryProposalHead(hidden_size, labels, dropout)
        self.verifier = verifier or SpanPairVerifier(
            hidden_size,
            labels,
            biaffine_size,
            max_span_width,
            width_size,
            dropout,
        )

    def forward(
        self,
        token_states: torch.Tensor,
        sentence_states: torch.Tensor,
        token_mask: torch.BoolTensor,
        *,
        proposals: torch.LongTensor | None = None,
        proposal_mask: torch.BoolTensor | None = None,
    ) -> SemanticSpanOutput:
        boundaries = self.boundary(token_states, token_mask)
        if proposals is None:
            if proposal_mask is not None:
                raise ValueError("proposal_mask requires proposals")
            return SemanticSpanOutput(boundaries, None, None)
        if proposal_mask is None:
            raise ValueError("semantic proposals require proposal_mask")
        scores = self.verifier(
            token_states,
            sentence_states,
            proposals,
            proposal_mask,
            token_mask,
        )
        return SemanticSpanOutput(boundaries, scores, proposal_mask)

    def score_proposals(
        self,
        token_states: torch.Tensor,
        sentence_states: torch.Tensor,
        proposals: torch.LongTensor,
        proposal_mask: torch.BoolTensor,
        token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        """Decoder/ablation이 verifier 구현을 몰라도 호출하는 public boundary API."""

        return self.verifier(
            token_states,
            sentence_states,
            proposals,
            proposal_mask,
            token_mask,
        )
