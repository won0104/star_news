"""고정 backbone 한 번의 source view 실행과 학습 core의 autograd 경계."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter
from typing import Mapping
from weakref import ReferenceType, ref

import torch
from torch import nn

from models.contracts import ArticleBatch, BackboneOutput
from runtime.v3_pretraining.handoff import (FrozenSourceViewKey,
                                            frozen_article_input_mask_sha256)


@dataclass(frozen=True, slots=True)
class FrozenFeatureCacheEntry:
    """CPU-owned frozen tensors plus the masks needed to validate a cache hit."""

    key: FrozenSourceViewKey
    hidden_by_layer: Mapping[int, torch.Tensor]
    input_ids: torch.Tensor
    attention_mask: torch.Tensor
    source_token_mask: torch.Tensor
    sentence_mask: torch.Tensor
    sentence_positions: torch.Tensor
    token_offsets: torch.Tensor
    sentence_char_offsets: torch.Tensor

    @property
    def byte_count(self) -> int:
        tensors = (*self.hidden_by_layer.values(), self.input_ids,
                   self.attention_mask, self.source_token_mask,
                   self.sentence_mask, self.sentence_positions,
                   self.token_offsets, self.sentence_char_offsets)
        return sum(value.numel() * value.element_size() for value in tensors)


class RunLocalFrozenFeatureCache:
    """Run-local CPU backend for frozen KF-DeBERTa source representations.

    Only detached L8/L10/L12 and their validation masks are retained.  DCE and
    every downstream activation remain request-local and are never admitted.
    """

    def __init__(self) -> None:
        self._entries: dict[FrozenSourceViewKey, FrozenFeatureCacheEntry] = {}
        self._stats: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float))
        self._scope_keys: dict[str, set[FrozenSourceViewKey]] = defaultdict(set)
        self._producer: ReferenceType[nn.Module] | None = None
        self._released = False

    def bind_producer(self, producer: nn.Module) -> None:
        """Reject reuse across different backbone objects inside one run."""
        current = None if self._producer is None else self._producer()
        if current is not None and current is not producer:
            raise ValueError("run-local frozen cache is bound to another backbone")
        self._producer = ref(producer)

    @staticmethod
    def _copy_cpu(value: torch.Tensor) -> torch.Tensor:
        copied = value.detach().to(device="cpu").contiguous().clone()
        if copied.requires_grad or copied.grad_fn is not None or copied.is_inference():
            raise ValueError("frozen cache tensor retained an autograd/inference graph")
        return copied

    @staticmethod
    def _copy_device(value: torch.Tensor, device: torch.device) -> torch.Tensor:
        copied = value.to(device=device)
        if copied.device.type == "cpu":
            copied = copied.clone()
        if copied.requires_grad or copied.grad_fn is not None or copied.is_inference():
            raise ValueError("cached frozen tensor became graph-connected")
        return copied

    @staticmethod
    def _validate_request_identity(key: FrozenSourceViewKey,
                                   batch: ArticleBatch) -> None:
        if (len(batch.contents) != 1
                or sha256(batch.contents[0].encode("utf-8")).hexdigest()
                != key.content_sha256
                or frozen_article_input_mask_sha256(batch) != key.input_mask_sha256):
            raise ValueError("frozen cache key differs from actual source-view tensors")

    def lookup(self, key: FrozenSourceViewKey, batch: ArticleBatch, *,
               scope: str) -> BackboneOutput | None:
        if self._released:
            raise RuntimeError("run-local frozen feature cache was released")
        self._validate_request_identity(key, batch)
        self._scope_keys[scope].add(key)
        started = perf_counter()
        entry = self._entries.get(key)
        if entry is None:
            self._stats[scope]["cache_misses"] += 1
            self._stats[scope]["cache_lookup_time_ms"] += (
                perf_counter() - started) * 1000
            return None
        expected_shape = (*batch.input_ids.shape, 768)
        valid = (
            torch.equal(entry.input_ids, batch.input_ids.detach().cpu())
            and torch.equal(entry.attention_mask, batch.attention_mask.detach().cpu())
            and torch.equal(entry.source_token_mask,
                            batch.source_token_mask.detach().cpu())
            and torch.equal(entry.sentence_mask, batch.sentence_mask.detach().cpu())
            and torch.equal(entry.sentence_positions,
                            batch.sentence_positions.detach().cpu())
            and torch.equal(entry.token_offsets, batch.token_offsets.detach().cpu())
            and torch.equal(entry.sentence_char_offsets,
                            batch.sentence_char_offsets.detach().cpu())
            and set(entry.hidden_by_layer) == set(key.required_layers)
            and all(tuple(value.shape) == expected_shape
                    and str(value.dtype).removeprefix("torch.") == key.dtype
                    and value.device.type == "cpu"
                    and not value.requires_grad and value.grad_fn is None
                    for value in entry.hidden_by_layer.values()))
        self._stats[scope]["cache_lookup_time_ms"] += (
            perf_counter() - started) * 1000
        if not valid:
            del self._entries[key]
            self._stats[scope]["cache_contract_rejections"] += 1
            self._stats[scope]["cache_misses"] += 1
            return None
        transfer_started = perf_counter()
        hidden = {layer: self._copy_device(value, batch.input_ids.device)
                  for layer, value in entry.hidden_by_layer.items()}
        self._stats[scope]["cache_transfer_time_ms"] += (
            perf_counter() - transfer_started) * 1000
        self._stats[scope]["cache_hits"] += 1
        return BackboneOutput(hidden, batch.attention_mask, batch.sentence_mask)

    def store(self, key: FrozenSourceViewKey, batch: ArticleBatch,
              output: BackboneOutput) -> None:
        if self._released:
            raise RuntimeError("run-local frozen feature cache was released")
        entry = FrozenFeatureCacheEntry(
            key=key,
            hidden_by_layer={layer: self._copy_cpu(output.layer(layer))
                             for layer in key.required_layers},
            input_ids=self._copy_cpu(batch.input_ids),
            attention_mask=self._copy_cpu(output.attention_mask),
            source_token_mask=self._copy_cpu(batch.source_token_mask),
            sentence_mask=self._copy_cpu(output.sentence_mask),
            sentence_positions=self._copy_cpu(batch.sentence_positions),
            token_offsets=self._copy_cpu(batch.token_offsets),
            sentence_char_offsets=self._copy_cpu(batch.sentence_char_offsets),
        )
        self._entries[key] = entry

    def record_forward(self, scope: str, elapsed_ms: float) -> None:
        self._stats[scope]["backbone_forward_count"] += 1
        self._stats[scope]["backbone_feature_build_time_ms"] += elapsed_ms

    def record_downstream(self, scope: str, elapsed_ms: float) -> None:
        self._stats[scope]["downstream_train_time_ms"] += elapsed_ms

    def snapshot(self) -> dict[str, object]:
        rows = {}
        for scope, values in sorted(self._stats.items()):
            rows[scope] = {
                name: (int(value) if name in {
                    "cache_hits", "cache_misses", "cache_contract_rejections",
                    "backbone_forward_count"} else float(value))
                for name, value in sorted(values.items())}
            rows[scope]["unique_source_views"] = len(self._scope_keys[scope])
        total_bytes = sum(entry.byte_count for entry in self._entries.values())
        return {
            "backend": "RUN_LOCAL_CPU_FROZEN_FEATURE_V1",
            "released": self._released,
            "producer_bound": self._producer is not None and self._producer() is not None,
            "unique_source_views": len(self._entries),
            "cpu_cache_bytes": total_bytes,
            "average_cached_source_view_bytes": (
                total_bytes / len(self._entries) if self._entries else 0.0),
            "mps_resident_cache_entries": sum(
                any(value.device.type == "mps"
                    for value in entry.hidden_by_layer.values())
                for entry in self._entries.values()),
            "scopes": rows,
        }

    def clear(self) -> None:
        self._entries.clear()
        self._scope_keys.clear()
        self._released = True


class FrozenBackboneFeatureBuilder:
    """주입된 고정 backbone을 no_grad로 실행하고 일반 tensor만 넘긴다.

    실제 model load/cache는 이 객체의 책임이 아니다. 서빙용 inference_mode
    carrier를 학습 core에 넘기는 사용은 빠르게 거절한다.
    """

    def __init__(self, backbone: nn.Module, *,
                 cache: RunLocalFrozenFeatureCache | None = None) -> None:
        if not isinstance(backbone, nn.Module):
            raise TypeError("frozen feature producer must be nn.Module")
        if any(parameter.requires_grad for parameter in backbone.parameters()):
            raise ValueError("v3 backbone producer must be frozen")
        self.backbone = backbone
        self.cache = cache
        if self.cache is not None:
            self.cache.bind_producer(backbone)

    def build(self, batch: ArticleBatch, *,
              cache_key: FrozenSourceViewKey | None = None,
              scope: str = "uncached") -> BackboneOutput:
        batch.validate()
        if self.cache is not None and cache_key is None:
            raise ValueError("cache-enabled frozen builder requires a source-view key")
        if self.cache is None and cache_key is not None:
            raise ValueError("source-view cache key requires a cache backend")
        if cache_key is not None:
            cached = self.cache.lookup(cache_key, batch, scope=scope)
            if cached is not None:
                return cached
        self.backbone.eval()
        started = perf_counter()
        with torch.no_grad():
            output = self.backbone(batch)
        if not isinstance(output, BackboneOutput):
            raise TypeError("frozen backbone must return BackboneOutput")
        if (not torch.equal(output.attention_mask, batch.attention_mask)
                or not torch.equal(output.sentence_mask, batch.sentence_mask)):
            raise ValueError("backbone masks differ from source batch")
        for layer in (8, 10, 12):
            hidden = output.layer(layer)
            if hidden.shape != (*batch.input_ids.shape, 768):
                raise ValueError(f"L{layer} does not align with source windows")
            if hidden.is_inference() or hidden.requires_grad:
                raise ValueError("frozen output must be a regular no_grad tensor")
        if cache_key is not None:
            if set(output.hidden_by_layer) != set(cache_key.required_layers):
                raise ValueError("backbone output layer set differs from cache identity")
            self.cache.store(cache_key, batch, output)
        if self.cache is not None:
            self.cache.record_forward(scope, (perf_counter() - started) * 1000)
        return output

    def record_downstream(self, scope: str, elapsed_ms: float) -> None:
        if self.cache is not None:
            self.cache.record_downstream(scope, elapsed_ms)
