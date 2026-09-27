"""요청 범위 compact handoff와 frozen source-view cache identity 계약.

이 모듈은 PUBLIC 출력에 model activation을 저장하지 않는다. Trainable bundle은
마지막 consumer 뒤 닫고, frozen cache key는 source/backbone/layout identity만 담는다.
실제 run-local CPU tensor 보유 정책은 ``frozen_features``가 소유한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping

import torch

from models.contracts import (DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION,
                              ArticleBatch, BackboneConfig)
from runtime.v3_pretraining.source_batch import SourceWindowBatch
from runtime.v3_pretraining.source_layout import (LAYOUT_POLICY,
                                                  SENTENCE_SPLIT_CONTRACT,
                                                  SOURCE_PREPROCESSING_CONTRACT,
                                                  RawArticle)


FROZEN_SOURCE_VIEW_CONTRACT = "v3-frozen-source-window-tensors-v1"


def frozen_article_input_mask_sha256(batch: ArticleBatch) -> str:
    """Digest the actual one-article tensors admitted by the frozen producer."""
    batch.validate()
    if batch.input_ids.shape[0] != 1:
        raise ValueError("frozen source cache only accepts one-article views")
    digest = sha256()
    for window_index in range(batch.input_ids.shape[1]):
        for tensor in (batch.input_ids[0, window_index],
                       batch.attention_mask[0, window_index],
                       batch.source_token_mask[0, window_index],
                       batch.token_offsets[0, window_index]):
            digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RepresentationProvenance:
    article_version_id: str
    content_sha256: str
    backbone_weights_sha256: str
    task_run_id: str
    task_config_sha256: str
    model_revision: str
    layer_mix_policy: str
    context_id: str
    dtype: str
    tokenizer_sha256: str
    ordered_window_sha256: str
    input_mask_sha256: str
    layout_policy: str = LAYOUT_POLICY

    def __post_init__(self) -> None:
        values = tuple(getattr(self, name) for name in self.__dataclass_fields__)
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError("representation provenance must be fully specified")
        if self.layout_policy != LAYOUT_POLICY:
            raise ValueError("representation source layout differs")


class CompactRepresentationBundle:
    """한 article의 정렬된 ID→tensor 행; 마지막 consumer 이후 close한다.

    States는 backward 전 detach하지 않는다. PUBLIC serializer 입력으로 허용되지 않는다.
    """

    def __init__(self, provenance: RepresentationProvenance, *, ordered_ids: tuple[str, ...],
                 states: torch.Tensor, mask: torch.Tensor) -> None:
        if not ordered_ids or len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("bundle needs nonempty unique ordered IDs")
        if states.ndim != 2 or states.shape[0] != len(ordered_ids) or states.shape[1] == 0:
            raise ValueError("bundle states must be [IDs,H]")
        if mask.shape != (len(ordered_ids),) or mask.dtype is not torch.bool:
            raise ValueError("bundle mask must be bool [IDs]")
        if str(states.dtype).removeprefix("torch.") != provenance.dtype:
            raise ValueError("bundle tensor dtype differs from provenance")
        self.provenance = provenance
        self.ordered_ids = ordered_ids
        self.states: torch.Tensor | None = states
        self.mask: torch.Tensor | None = mask

    def require(self, expected: RepresentationProvenance, *, ordered_ids: tuple[str, ...] | None = None
                ) -> tuple[torch.Tensor, torch.Tensor]:
        if self.states is None or self.mask is None:
            raise RuntimeError("representation bundle was released")
        if self.provenance != expected:
            raise ValueError("representation producer/config/article/window policy mismatch")
        if ordered_ids is not None and self.ordered_ids != ordered_ids:
            raise ValueError("representation IDs differ in order or membership")
        return self.states, self.mask

    def index(self, item_id: str) -> int:
        if self.states is None:
            raise RuntimeError("representation bundle was released")
        try:
            return self.ordered_ids.index(item_id)
        except ValueError as error:
            raise KeyError(item_id) from error

    def close(self) -> None:
        self.states = None
        self.mask = None

    def __enter__(self) -> "CompactRepresentationBundle":
        if self.states is None:
            raise RuntimeError("representation bundle was released")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class FrozenSourceViewKey:
    """고정 backbone/source view의 완전한 run-local cache identity."""

    article_version_id: str
    content_sha256: str
    backbone_model_id: str
    backbone_revision: str
    backbone_weights_sha256: str
    required_layers: tuple[int, ...]
    tokenizer_sha256: str
    preprocessing_contract: str
    layout_policy: str
    sentence_split_contract: str
    source_view_contract: str
    source_view: str
    ordered_window_sha256: str
    input_mask_sha256: str
    dtype: str = "float32"

    def __post_init__(self) -> None:
        strings = (
            self.article_version_id, self.content_sha256,
            self.backbone_model_id, self.backbone_revision,
            self.backbone_weights_sha256, self.tokenizer_sha256,
            self.preprocessing_contract, self.layout_policy,
            self.sentence_split_contract,
            self.source_view_contract, self.source_view,
            self.ordered_window_sha256, self.input_mask_sha256, self.dtype,
        )
        if (not all(isinstance(value, str) and value for value in strings)
                or self.source_view not in ("sentence", "bridge", "all")
                or not self.required_layers
                or tuple(sorted(set(self.required_layers))) != self.required_layers):
            raise ValueError("frozen source cache identity is incomplete")
        if (self.preprocessing_contract != SOURCE_PREPROCESSING_CONTRACT
                or self.layout_policy != LAYOUT_POLICY
                or self.sentence_split_contract != SENTENCE_SPLIT_CONTRACT
                or self.source_view_contract != FROZEN_SOURCE_VIEW_CONTRACT):
            raise ValueError("frozen source cache contract differs")

    @classmethod
    def from_batch(cls, article: RawArticle, batch: SourceWindowBatch, *,
                   backbone_weights_sha256: str, tokenizer_sha256: str,
                   backbone_model_id: str = DEFAULT_MODEL_ID,
                   backbone_revision: str = DEFAULT_MODEL_REVISION,
                   required_layers: tuple[int, ...] = (8, 10, 12),
                   dtype: str = "float32", source_view: str = "all",
                   preprocessing_contract: str = SOURCE_PREPROCESSING_CONTRACT,
                   sentence_split_contract: str = SENTENCE_SPLIT_CONTRACT,
                   source_view_contract: str = FROZEN_SOURCE_VIEW_CONTRACT,
                   ) -> "FrozenSourceViewKey":
        batch.validate()
        if source_view not in ("sentence", "bridge", "all"):
            raise ValueError("unknown frozen source view")
        selected = [index for index, key in enumerate(batch.keys)
                    if key[0] == article.article_version_id
                    and (batch.views[index] == source_view or source_view == "all")]
        if not selected:
            raise ValueError("article has no cacheable source windows")
        if any(batch.content_hashes[index] != article.content_sha256 for index in selected):
            raise ValueError("source cache input content hash mismatch")
        ordered = [(batch.keys[index][1], batch.views[index]) for index in selected]
        key_bytes = json.dumps(ordered, separators=(",", ":")).encode()
        digest = sha256()
        for index in selected:
            for tensor in (batch.input_ids, batch.attention_mask,
                           batch.source_token_mask, batch.token_offsets):
                digest.update(tensor[index].detach().cpu().contiguous().numpy().tobytes())
        return cls(
            article.article_version_id, article.content_sha256,
            backbone_model_id, backbone_revision, backbone_weights_sha256,
            tuple(required_layers), tokenizer_sha256, preprocessing_contract,
            LAYOUT_POLICY,
            sentence_split_contract, source_view_contract, source_view,
            sha256(key_bytes).hexdigest(), digest.hexdigest(), dtype)

    @classmethod
    def from_config(cls, article: RawArticle, batch: SourceWindowBatch, *,
                    backbone: BackboneConfig, tokenizer_sha256: str,
                    dtype: str = "float32", source_view: str = "all",
                    ) -> "FrozenSourceViewKey":
        """Bind an actual backbone config to the canonical source-view digest."""
        return cls.from_batch(
            article, batch,
            backbone_model_id=backbone.model_id,
            backbone_revision=backbone.revision,
            backbone_weights_sha256=backbone.expected_weights_sha256,
            required_layers=backbone.required_layers,
            tokenizer_sha256=tokenizer_sha256,
            dtype=dtype, source_view=source_view)


@dataclass(frozen=True, slots=True)
class TrainableViewKey:
    """DCE/task activation을 재사용하려면 revision·step·mode까지 달라야 한다."""

    frozen: FrozenSourceViewKey
    task_run_id: str
    task_config_sha256: str
    model_revision: str
    optimizer_step: int
    mode: str
    context_id: str = "shared-dce"
    layer_mix_policy: str = "L8+DCE"
    call_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.task_run_id, self.task_config_sha256, self.model_revision,
                    self.context_id, self.layer_mix_policy)):
            raise ValueError("trainable cache needs exact model identity")
        if self.optimizer_step < 0 or self.mode not in ("train", "eval"):
            raise ValueError("trainable cache needs valid optimizer step and mode")
        if self.mode == "train" and not self.call_id:
            raise ValueError("dropout training calls require distinct invocation IDs")


@dataclass(frozen=True, slots=True)
class ScalarSemanticRecord:
    """장기 semantic carrier에 허용하는 원문 근거·scalar 식별자."""

    local_id: str
    kind: str
    start: int
    end: int
    text: str
    score: float | None = None

    def __post_init__(self) -> None:
        if not self.local_id or not self.kind or not 0 <= self.start < self.end:
            raise ValueError("semantic record identity or source offsets invalid")
        if self.score is not None and not math.isfinite(self.score):
            raise ValueError("semantic score must be finite")

    def public_fields(self) -> dict[str, str | int | float | None]:
        return {"id": self.local_id, "kind": self.kind, "start": self.start,
                "end": self.end, "text": self.text, "score": self.score}


def public_scalar_projection(value: Any) -> Any:
    """tensor/training object가 PUBLIC·진단 JSON carrier로 새지 않도록 fail-loud한다."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("PUBLIC scalar must be finite")
        return value
    if isinstance(value, ScalarSemanticRecord):
        return public_scalar_projection(value.public_fields())
    if isinstance(value, (list, tuple)):
        return [public_scalar_projection(item) for item in value]
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return {key: public_scalar_projection(item) for key, item in value.items()}
    raise TypeError(f"PUBLIC carrier rejects training/tensor state: {type(value).__name__}")
