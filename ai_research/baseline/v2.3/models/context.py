"""기사 단위 문장 상호작용, top-down token 재주입, candidate span 표현.

문장→문서→문장/token의 최소 상호작용은 Hi-Transformer (Wu et al., ACL 2021)의
top-down context propagation 아이디어를 참고했다. 논문의 두 번째 sentence Transformer를
복제하지 않고, document-aware sentence state를 gated residual로 L8 token에 재주입한다.
https://aclanthology.org/2021.acl-short.107/
"""

from __future__ import annotations

import math

import torch
from torch import nn

from .contracts import (
    BackboneOutput,
    CandidateBatch,
    ContextConfig,
    DocumentContextOutput,
    SPAN_KINDS,
    TaskLayerPolicy,
)


class DocumentContextEncoder(nn.Module):
    """L8 ``[B,S,T,768]``을 공유 document-aware ``[B,S,T,H]``로 변환한다."""

    def __init__(self, config: ContextConfig) -> None:
        super().__init__()
        self.config = config
        self.token_projection = nn.Linear(config.input_hidden_size, config.hidden_size)
        self.pool_projection = nn.Linear(config.hidden_size, config.pooling_hidden_size)
        self.pool_score = nn.Linear(config.pooling_hidden_size, 1, bias=False)
        self.relative_position = nn.Sequential(
            nn.Linear(2, config.hidden_size),
            nn.GELU(),
            nn.Linear(config.hidden_size, config.hidden_size),
        )
        layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_size,
            nhead=config.attention_heads,
            dim_feedforward=config.feedforward_size,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.document_encoder = nn.TransformerEncoder(
            layer,
            num_layers=config.document_layers,
            norm=nn.LayerNorm(config.hidden_size),
            enable_nested_tensor=False,
        )
        self.reinjection_gate = nn.Linear(config.hidden_size * 2, config.hidden_size)
        self.token_norm = nn.LayerNorm(config.hidden_size)
        self.sentence_norm = nn.LayerNorm(config.hidden_size)
        self.dropout = nn.Dropout(config.dropout)

    def forward(
        self,
        token_hidden: torch.Tensor,
        source_token_mask: torch.BoolTensor,
        sentence_mask: torch.BoolTensor,
        sentence_positions: torch.LongTensor,
    ) -> DocumentContextOutput:
        if token_hidden.ndim != 4:
            raise ValueError("document context expects token_hidden [B,S,T,H]")
        if source_token_mask.shape != token_hidden.shape[:3]:
            raise ValueError("source_token_mask must align with L8 tokens")
        if sentence_mask.shape != token_hidden.shape[:2]:
            raise ValueError("sentence_mask must align with sentences")
        local_tokens = self.token_projection(token_hidden)
        logits = self.pool_score(torch.tanh(self.pool_projection(local_tokens))).squeeze(-1)
        logits = logits.masked_fill(~source_token_mask, -1e4)
        weights = torch.softmax(logits, dim=-1) * source_token_mask.to(logits.dtype)
        weights = weights / weights.sum(dim=-1, keepdim=True).clamp_min(1e-8)
        pooled = torch.einsum("bst,bsth->bsh", weights, local_tokens)

        relative = sentence_positions.to(local_tokens.dtype)
        denominator = sentence_mask.sum(dim=1, keepdim=True).sub(1).clamp_min(1).to(relative.dtype)
        relative = torch.stack(
            (relative / denominator, (denominator - relative).clamp_min(0) / denominator),
            dim=-1,
        )
        position = _sinusoidal(sentence_positions, self.config.hidden_size, local_tokens.dtype)
        positioned = self.sentence_norm(
            pooled + self.relative_position(relative) + position
        ) * sentence_mask.unsqueeze(-1)
        contextual = self.document_encoder(
            positioned,
            src_key_padding_mask=~sentence_mask,
        ) * sentence_mask.unsqueeze(-1)

        expanded = contextual.unsqueeze(2).expand_as(local_tokens)
        gate = torch.sigmoid(self.reinjection_gate(torch.cat((local_tokens, expanded), dim=-1)))
        document_tokens = self.token_norm(
            local_tokens + gate * self.dropout(expanded)
        )
        attended = source_token_mask & sentence_mask.unsqueeze(-1)
        document_tokens = document_tokens * attended.unsqueeze(-1)
        gate = gate * attended.unsqueeze(-1)
        document_state = contextual.sum(dim=1) / sentence_mask.sum(
            dim=1, keepdim=True
        ).clamp_min(1)
        return DocumentContextOutput(
            sentence_states=contextual,
            token_states=document_tokens,
            document_state=document_state,
            token_attention=weights,
            reinjection_gate=gate,
        )


class CandidateSpanEncoder(nn.Module):
    """kind별 static KF layer와 L8 document context로 공유 span 표현을 만든다.

    Entity/Time/Event/Statement/Trigger가 요청하는 layer는 서로 다르며 하나의 final layer로
    치환하지 않는다. 출력 ``[B,N,H]``는 attributes와 pair Head가 공유한다.
    """

    def __init__(self, config: ContextConfig, layer_policy: TaskLayerPolicy) -> None:
        super().__init__()
        self.config = config
        self.layer_policy = layer_policy
        layer_values = sorted({layer_policy.for_span_kind(kind) for kind in SPAN_KINDS})
        self.layer_values = tuple(layer_values)
        layer_to_stack = {layer: index for index, layer in enumerate(layer_values)}
        self.register_buffer(
            "kind_layer_indices",
            torch.tensor(
                [layer_to_stack[layer_policy.for_span_kind(kind)] for kind in SPAN_KINDS],
                dtype=torch.long,
            ),
            persistent=False,
        )
        self.span_attention = nn.Sequential(
            nn.Linear(config.input_hidden_size, config.pooling_hidden_size),
            nn.Tanh(),
            nn.Linear(config.pooling_hidden_size, 1, bias=False),
        )
        self.width_embedding = nn.Embedding(
            config.max_span_width + 1,
            config.width_embedding_size,
        )
        self.kind_embedding = nn.Embedding(len(SPAN_KINDS), config.kind_embedding_size)
        input_size = (
            config.input_hidden_size * 3
            + config.hidden_size
            + config.width_embedding_size
            + config.kind_embedding_size
        )
        self.output = nn.Sequential(
            nn.Linear(input_size, config.hidden_size),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size, config.hidden_size),
            nn.LayerNorm(config.hidden_size),
        )

    def forward(
        self,
        backbone: BackboneOutput,
        context: DocumentContextOutput,
        candidates: CandidateBatch,
        source_token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        return self.forward_prepared(
            self.prepare_backbone_layers(backbone),
            context,
            candidates,
            source_token_mask,
        )

    def prepare_backbone_layers(self, backbone: BackboneOutput) -> torch.Tensor:
        """Stack immutable backbone layers once for bounded candidate chunks."""

        return torch.stack(
            [backbone.layer(layer) for layer in self.layer_values],
            dim=2,
        )

    def forward_prepared(
        self,
        stacked: torch.Tensor,
        context: DocumentContextOutput,
        candidates: CandidateBatch,
        source_token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        """Encode one candidate chunk from a shared prepared layer tensor."""

        batch_size, candidate_count = candidates.span_indices.shape[:2]
        if candidate_count == 0:
            return context.token_states.new_zeros(batch_size, 0, self.config.hidden_size)
        sentence_tokens = self.select_prepared_backbone_sentences(stacked, candidates)
        return self._forward_selected_sentences(
            sentence_tokens,
            context,
            candidates,
            source_token_mask,
        )

    def forward_runtime_direct(
        self,
        backbone: BackboneOutput,
        context: DocumentContextOutput,
        candidates: CandidateBatch,
        source_token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        """Encode a runtime chunk without an article-global layer stack.

        The layer route is still the frozen ``TaskLayerPolicy`` used to build
        ``kind_layer_indices``.  Only candidate-local sentence rows are gathered;
        the legacy stack path remains available to training and parity fixtures.
        """

        batch_size, candidate_count = candidates.span_indices.shape[:2]
        if candidate_count == 0:
            return context.token_states.new_zeros(batch_size, 0, self.config.hidden_size)
        sentence_tokens = self.select_runtime_backbone_sentences(backbone, candidates)
        return self._forward_selected_sentences(
            sentence_tokens,
            context,
            candidates,
            source_token_mask,
        )

    def select_prepared_backbone_sentences(
        self,
        stacked: torch.Tensor,
        candidates: CandidateBatch,
    ) -> torch.Tensor:
        """Select candidate sentence rows from the legacy prepared stack."""

        indices = candidates.span_indices
        batch_size, candidate_count = indices.shape[:2]
        if candidate_count == 0:
            return stacked.new_empty(batch_size, 0, stacked.shape[3], stacked.shape[4])
        safe = self._safe_span_indices(candidates, stacked.shape[1], stacked.shape[3])
        kinds = candidates.span_kind_ids.clamp(0, len(SPAN_KINDS) - 1)
        layer_indices = self.kind_layer_indices[kinds]
        batch_indices = torch.arange(batch_size, device=indices.device).unsqueeze(1)
        sentence_indices = safe[..., 0]
        return stacked[
            batch_indices,
            sentence_indices,
            layer_indices,
        ]  # [B,N,T,H]

    def select_runtime_backbone_sentences(
        self,
        backbone: BackboneOutput,
        candidates: CandidateBatch,
    ) -> torch.Tensor:
        """Gather one runtime chunk through its routed layer topology.

        Every materialized row participates in topology resolution, including
        masked rows.  A homogeneous chunk can return the advanced-indexing
        result directly; a heterogeneous chunk retains the ordered assembly
        used by the original direct-gather implementation.
        """

        indices = candidates.span_indices
        batch_size, candidate_count = indices.shape[:2]
        first_layer = backbone.layer(self.layer_values[0])
        if first_layer.ndim != 4:
            raise ValueError("backbone layer must have shape [B,S,T,H]")
        if first_layer.shape[0] != batch_size:
            raise ValueError("candidate batch differs from backbone batch")
        if candidate_count == 0:
            return first_layer.new_empty(
                batch_size, 0, first_layer.shape[2], first_layer.shape[3]
            )
        sentence_count, token_count, hidden_size = first_layer.shape[1:]
        safe = self._safe_span_indices(candidates, sentence_count, token_count)
        kinds = candidates.span_kind_ids.clamp(0, len(SPAN_KINDS) - 1)
        flat_layer_indices = self.kind_layer_indices[kinds].reshape(-1)
        single_layer_index = self._single_runtime_layer_index(flat_layer_indices)
        if single_layer_index is not None:
            return self._gather_single_layer_sentences(
                backbone,
                safe,
                single_layer_index,
                tuple(first_layer.shape),
            )
        return self._gather_mixed_layer_sentences(
            backbone,
            safe,
            flat_layer_indices,
            first_layer,
        )

    def _single_runtime_layer_index(
        self,
        flat_layer_indices: torch.LongTensor,
    ) -> int | None:
        """Return one layer slot when every materialized row routes there.

        ``aminmax`` encodes the minimum and maximum into one scalar so a CUDA
        caller incurs one explicit device-to-host synchronization per non-empty
        chunk instead of separate topology and layer-id synchronizations.
        """

        minimum, maximum = torch.aminmax(flat_layer_indices)
        base = len(self.layer_values)
        dispatch_code = minimum * base + maximum
        host_code = int(dispatch_code.item())
        minimum_index, maximum_index = divmod(host_code, base)
        return minimum_index if minimum_index == maximum_index else None

    def _gather_single_layer_sentences(
        self,
        backbone: BackboneOutput,
        safe: torch.LongTensor,
        layer_index: int,
        expected_shape: tuple[int, ...],
    ) -> torch.Tensor:
        """Return the sole candidate-local advanced-indexing allocation."""

        source = backbone.layer(self.layer_values[layer_index])
        if tuple(source.shape) != expected_shape:
            raise ValueError("routed backbone layers must share [B,S,T,H]")
        batch_size = safe.shape[0]
        batch_indices = torch.arange(batch_size, device=safe.device).unsqueeze(1)
        return source[batch_indices, safe[..., 0]]

    def _gather_mixed_layer_sentences(
        self,
        backbone: BackboneOutput,
        safe: torch.LongTensor,
        flat_layer_indices: torch.LongTensor,
        first_layer: torch.Tensor,
    ) -> torch.Tensor:
        """Assemble heterogeneous layer rows in original candidate order."""

        batch_size, candidate_count = safe.shape[:2]
        token_count, hidden_size = first_layer.shape[2:]
        flat_sentence_indices = safe[..., 0].reshape(-1)
        flat_tokens = first_layer.new_empty(
            batch_size * candidate_count,
            token_count,
            hidden_size,
        )
        for layer_index, layer in enumerate(self.layer_values):
            positions = torch.nonzero(
                flat_layer_indices == layer_index,
                as_tuple=False,
            ).flatten()
            if positions.numel() == 0:
                continue
            source = backbone.layer(layer)
            if tuple(source.shape) != tuple(first_layer.shape):
                raise ValueError("routed backbone layers must share [B,S,T,H]")
            batch_indices = torch.div(
                positions,
                candidate_count,
                rounding_mode="floor",
            )
            sentence_indices = flat_sentence_indices.index_select(0, positions)
            selected = source[batch_indices, sentence_indices]
            flat_tokens.index_copy_(0, positions, selected)
        return flat_tokens.view(batch_size, candidate_count, token_count, hidden_size)

    @staticmethod
    def _safe_span_indices(
        candidates: CandidateBatch,
        sentence_count: int,
        token_count: int,
    ) -> torch.Tensor:
        safe = candidates.span_indices.clone()
        safe[..., 0] = safe[..., 0].clamp(0, sentence_count - 1)
        safe[..., 1] = safe[..., 1].clamp(0, token_count - 1)
        safe[..., 2] = safe[..., 2].clamp(1, token_count)
        return safe

    def _forward_selected_sentences(
        self,
        sentence_tokens: torch.Tensor,
        context: DocumentContextOutput,
        candidates: CandidateBatch,
        source_token_mask: torch.BoolTensor,
    ) -> torch.Tensor:
        """Apply the shared frozen span feature computation to selected rows."""

        indices = candidates.span_indices
        mask = candidates.span_mask
        batch_size, candidate_count = indices.shape[:2]
        token_count = sentence_tokens.shape[2]
        hidden_size = self.config.input_hidden_size
        safe = self._safe_span_indices(
            candidates,
            source_token_mask.shape[1],
            token_count,
        )
        kinds = candidates.span_kind_ids.clamp(0, len(SPAN_KINDS) - 1)
        batch_indices = torch.arange(batch_size, device=indices.device).unsqueeze(1)
        sentence_indices = safe[..., 0]
        sentence_source_mask = source_token_mask[batch_indices, sentence_indices]
        starts, ends = safe[..., 1], safe[..., 2]
        start_states = sentence_tokens.gather(
            2, starts[..., None, None].expand(-1, -1, 1, hidden_size)
        ).squeeze(2)
        end_states = sentence_tokens.gather(
            2, (ends - 1)[..., None, None].expand(-1, -1, 1, hidden_size)
        ).squeeze(2)
        positions = torch.arange(token_count, device=indices.device).view(1, 1, -1)
        inside = (
            (positions >= starts.unsqueeze(-1))
            & (positions < ends.unsqueeze(-1))
            & sentence_source_mask
            & mask.unsqueeze(-1)
        )
        scores = self.span_attention(sentence_tokens).squeeze(-1).masked_fill(~inside, -1e4)
        weights = torch.softmax(scores, dim=-1) * inside.to(scores.dtype)
        weights = weights / weights.sum(dim=-1, keepdim=True).clamp_min(1e-8)
        pooled = torch.einsum("bnt,bnth->bnh", weights, sentence_tokens)
        document_sentence = context.sentence_states[batch_indices, sentence_indices]
        widths = (ends - starts).clamp(0, self.config.max_span_width)
        features = torch.cat(
            (
                start_states,
                end_states,
                pooled,
                document_sentence,
                self.width_embedding(widths),
                self.kind_embedding(kinds),
            ),
            dim=-1,
        )
        return self.output(features) * mask.unsqueeze(-1)


def _sinusoidal(
    positions: torch.LongTensor,
    hidden_size: int,
    dtype: torch.dtype,
) -> torch.Tensor:
    half = (hidden_size + 1) // 2
    frequencies = torch.exp(
        torch.arange(half, device=positions.device, dtype=torch.float32)
        * (-math.log(10000.0) / max(half - 1, 1))
    )
    angles = positions.to(torch.float32).unsqueeze(-1) * frequencies
    encoded = torch.cat((angles.sin(), angles.cos()), dim=-1)[..., :hidden_size]
    return encoded.to(dtype)
