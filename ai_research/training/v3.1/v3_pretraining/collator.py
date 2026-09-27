"""Gold target과 raw encoder 입력을 분리해 source window를 무손실 padding한다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch

from runtime.v3_pretraining.source_batch import SourceWindowBatch
from training.v3_pretraining.targets import ArticleTargets


@dataclass(frozen=True, slots=True)
class TargetBatch:
    windows: SourceWindowBatch
    targets: tuple[ArticleTargets, ...]


class TargetCollator:
    """중복 window 근거를 target 수로 반복하지 않는 학습 전용 collator."""

    def __init__(self, *, pad_token_id: int) -> None:
        self.pad_token_id = pad_token_id

    def __call__(self, targets: Sequence[ArticleTargets]) -> TargetBatch:
        if not targets:
            raise ValueError("target batch cannot be empty")
        windows = [(item.article_version_id, item.content_sha256, window)
                   for item in targets for window in item.layout.windows]
        count = len(windows)
        ids = torch.full((count, 128), self.pad_token_id, dtype=torch.long)
        attention = torch.zeros((count, 128), dtype=torch.bool)
        source_mask = torch.zeros((count, 128), dtype=torch.bool)
        offsets = torch.full((count, 128, 2), -1, dtype=torch.long)
        keys = []
        views = []
        hashes = []
        for row, (version, content_sha, window) in enumerate(windows):
            width = len(window.input_ids)
            ids[row, :width] = torch.tensor(window.input_ids, dtype=torch.long)
            attention[row, :width] = True
            for token in window.tokens:
                source_mask[row, token.position] = True
                offsets[row, token.position] = torch.tensor((token.start, token.end), dtype=torch.long)
            keys.append((version, window.window_id))
            views.append(window.view)
            hashes.append(content_sha)
        result = SourceWindowBatch(ids, attention, source_mask, offsets,
                                   tuple(keys), tuple(views), tuple(hashes))
        result.validate()
        return TargetBatch(result, tuple(targets))
