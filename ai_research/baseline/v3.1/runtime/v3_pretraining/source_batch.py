"""Gold 비의존 window tensor batch; 요청에서만 보유하고 기존 backbone view로 전달한다."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from models.contracts import ArticleBatch
from runtime.v3_pretraining.source_layout import RawArticle, SourceLayout


@dataclass(frozen=True, slots=True)
class SourceWindowBatch:
    input_ids: torch.Tensor
    attention_mask: torch.Tensor
    source_token_mask: torch.Tensor
    token_offsets: torch.Tensor
    keys: tuple[tuple[str, str], ...]
    views: tuple[str, ...]
    content_hashes: tuple[str, ...]

    def validate(self) -> None:
        if self.input_ids.ndim != 2 or self.input_ids.shape[1] != 128:
            raise ValueError("window batch must be [windows,128]")
        if self.attention_mask.shape != self.input_ids.shape or self.source_token_mask.shape != self.input_ids.shape:
            raise ValueError("window masks differ from input shape")
        if self.token_offsets.shape != (*self.input_ids.shape, 2):
            raise ValueError("window source offsets differ from input shape")
        if len(self.keys) != self.input_ids.shape[0] or len(set(self.keys)) != len(self.keys):
            raise ValueError("window keys must be unique and ordered")
        if len(self.views) != len(self.keys) or any(view not in ("sentence", "bridge") for view in self.views):
            raise ValueError("window views must align with ordered keys")
        if len(self.content_hashes) != len(self.keys) or any(len(value) != 64 for value in self.content_hashes):
            raise ValueError("window content hashes must align with ordered keys")
        if (self.attention_mask.dtype is not torch.bool or self.source_token_mask.dtype is not torch.bool
                or self.input_ids.dtype is not torch.long or self.token_offsets.dtype is not torch.long):
            raise ValueError("source window tensor dtypes differ from model contract")
        if torch.any(self.source_token_mask & ~self.attention_mask):
            raise ValueError("source mask cannot include padding")

    def article_view(self, article: RawArticle, *, view: str = "sentence") -> ArticleBatch:
        """한 기사 view를 기존 all-valid backbone shape로 감싼다; Gold를 참조하지 않는다."""
        if view not in ("sentence", "bridge", "all"):
            raise ValueError("unknown source view")
        indices = [index for index, (key, kind) in enumerate(zip(self.keys, self.views))
                   if key[0] == article.article_version_id and (kind == view or view == "all")]
        if not indices:
            raise ValueError("requested article view has no windows")
        if any(self.content_hashes[index] != article.content_sha256 for index in indices):
            raise ValueError("source windows have a different article content hash")
        contiguous = indices == list(range(indices[0], indices[0] + len(indices)))
        def rows(tensor: torch.Tensor) -> torch.Tensor:
            if contiguous:
                selected = tensor.narrow(0, indices[0], len(indices))
                # 단일 기사면 storage를 공유하고, 일부 기사만 고르면 다른 기사의 storage를 붙들지 않는다.
                return (selected if len(indices) == tensor.shape[0] else selected.clone()).unsqueeze(0)
            selected = torch.tensor(indices, dtype=torch.long, device=tensor.device)
            return tensor.index_select(0, selected).unsqueeze(0)
        ids = rows(self.input_ids)
        attention = rows(self.attention_mask)
        source = rows(self.source_token_mask)
        offsets = rows(self.token_offsets)
        bounds = []
        for row in offsets[0]:
            valid = row[row[:, 0] >= 0]
            if valid.numel() == 0:
                raise ValueError("source window has no character offsets")
            bounds.append((int(valid[0, 0]), int(valid[-1, 1])))
        batch = ArticleBatch(ids, attention, source, torch.ones(1, len(indices), dtype=torch.bool, device=ids.device),
                             torch.arange(len(indices), dtype=torch.long, device=ids.device).unsqueeze(0), offsets,
                             torch.tensor([bounds], dtype=torch.long, device=ids.device), (article.article_id,),
                             (article.content,), (article.published_at,))
        batch.validate()
        return batch


def source_windows_from_layout(layout: SourceLayout, *, pad_token_id: int) -> SourceWindowBatch:
    """Gold 없이 layout의 sentence·bridge window를 동일한 순서의 128-token batch로 만든다."""
    count = len(layout.windows)
    if count == 0:
        raise ValueError("source layout has no windows")
    ids = torch.full((count, 128), pad_token_id, dtype=torch.long)
    attention = torch.zeros((count, 128), dtype=torch.bool)
    source_mask = torch.zeros((count, 128), dtype=torch.bool)
    offsets = torch.full((count, 128, 2), -1, dtype=torch.long)
    for row, window in enumerate(layout.windows):
        width = len(window.input_ids)
        ids[row, :width] = torch.tensor(window.input_ids, dtype=torch.long)
        attention[row, :width] = True
        for token in window.tokens:
            source_mask[row, token.position] = True
            offsets[row, token.position] = torch.tensor((token.start, token.end), dtype=torch.long)
    result = SourceWindowBatch(ids, attention, source_mask, offsets,
                               tuple((layout.article.article_version_id, window.window_id)
                                     for window in layout.windows),
                               tuple(window.view for window in layout.windows),
                               tuple(layout.article.content_sha256 for _ in layout.windows))
    result.validate()
    return result
