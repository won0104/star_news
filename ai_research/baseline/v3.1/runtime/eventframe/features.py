"""One frozen backbone pass with validated cache reuse or online extraction."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import time
from typing import Any

import torch

from models.backbone import KFDeBERTaBackbone
from models.contracts import BackboneConfig, BackboneOutput

from .config import RuntimeConfig, digest
from .contracts import CheckpointMismatchError


def tensor_digest(value: torch.Tensor) -> str:
    return sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RepresentationKey:
    """같은 기사 요청에서 같은 producer·tokenized input에만 공유 표현을 재사용한다."""

    producer: tuple[str, str, str, str, int, tuple[int, ...], str]
    article_version_id: str
    content_sha256: str
    input_ids_sha256: str
    source_token_mask_sha256: str


class SharedBackboneProvider:
    """Builds one shared L8/L10/L12 object per Article runtime call."""

    def __init__(self, config: RuntimeConfig, device: torch.device,
                 *, tokenizer_sha256: str | None = None) -> None:
        self.config = config
        self.device = device
        payload = config.payload["backbone"]
        self.tokenizer_sha256 = tokenizer_sha256 or str(
            payload.get("files_sha256", {}).get("tokenizer.json", payload["revision"])
        )
        feature_root = payload.get("feature_cache_root")
        self.cache_root = config.resolve(feature_root) if feature_root else None
        self.cache_manifest = (
            __import__("json").loads(config.artifact("backbone_cache_manifest").read_text())
            if feature_root and "backbone_cache_manifest" in config.payload.get("artifacts", {})
            else None
        )
        self.online: KFDeBERTaBackbone | None = None
        self.cache_hits = 0
        self.online_runs = 0

    def request_key(self, prepared) -> RepresentationKey:
        source = self.config.payload["backbone"]
        preprocessing = self.config.payload["preprocessing"]
        return RepresentationKey(
            producer=(
                str(source["model_id"]), str(source["revision"]),
                str(source["weight_sha256"]), self.tokenizer_sha256,
                int(preprocessing["max_sentence_tokens"]),
                tuple(int(layer) for layer in source["required_layers"]),
                "float32",
            ),
            article_version_id=str(prepared.article.article_version_id),
            content_sha256=sha256(prepared.article.content.encode("utf-8")).hexdigest(),
            input_ids_sha256=tensor_digest(prepared.batch.input_ids),
            source_token_mask_sha256=tensor_digest(prepared.batch.source_token_mask),
        )

    def _cached(self, prepared, key: RepresentationKey) -> BackboneOutput | None:
        if self.cache_root is None or self.cache_manifest is None:
            return None
        contract = self.cache_manifest.get("contract", {})
        if (contract.get("model_id") != key.producer[0]
            or contract.get("revision") != key.producer[1]
            or contract.get("weights_sha256") != key.producer[2]
            or int(contract.get("max_sentence_tokens", -1)) != key.producer[4]
            or tuple(contract.get("layers", ())) != key.producer[5]):
            return None
        path = self.cache_root / f"{prepared.article.article_id}.pt"
        expected = self.cache_manifest["feature_files_sha256"].get(
            prepared.article.article_id
        )
        if expected is None or not path.is_file():
            return None
        if digest(path) != expected:
            raise CheckpointMismatchError(
                f"backbone cache SHA mismatch for {prepared.article.article_id}"
            )
        data = torch.load(path, map_location="cpu", weights_only=True)
        if data["content_sha256"] != key.content_sha256:
            return None
        if data["input_ids_sha256"] != key.input_ids_sha256:
            return None
        if data["source_token_mask_sha256"] != key.source_token_mask_sha256:
            return None
        self.cache_hits += 1
        return BackboneOutput(
            hidden_by_layer={
                int(layer): value.float().to(self.device)
                for layer, value in data["hidden_by_layer"].items()
            },
            attention_mask=prepared.batch.attention_mask.to(self.device),
            sentence_mask=prepared.batch.sentence_mask.to(self.device),
        )

    def _online_model(self) -> KFDeBERTaBackbone:
        if self.online is None:
            source = self.config.payload["backbone"]
            backbone = BackboneConfig(
                model_id=source["model_id"],
                revision=source["revision"],
                expected_weights_sha256=source["weight_sha256"],
                required_layers=tuple(source["required_layers"]),
                trainable=False,
                local_files_only=True,
            )
            snapshot = self.config.backbone_snapshot()
            from transformers import AutoModel

            encoder = AutoModel.from_pretrained(snapshot, local_files_only=True)
            self.online = KFDeBERTaBackbone(encoder, backbone).to(
                device=self.device, dtype=torch.float32
            )
            self.online.eval()
        return self.online

    @torch.inference_mode()
    def get(self, prepared, *, scope=None) -> tuple[BackboneOutput, dict[str, Any]]:
        started = time.perf_counter()
        key = self.request_key(prepared)
        if scope is not None and key in scope.representations:
            return scope.representations[key], {
                "source": "REQUEST_LOCAL_IDENTICAL_PRODUCER_INPUT",
                "elapsed_seconds": time.perf_counter() - started,
            }
        cached = self._cached(prepared, key)
        if cached is not None:
            if scope is not None:
                scope.representations[key] = cached
            return cached, {
                "source": "VALIDATED_FLOAT16_CACHE_RESTORED_FLOAT32",
                "elapsed_seconds": time.perf_counter() - started,
            }
        model = self._online_model()
        output = model(prepared.batch.to(self.device))
        if scope is not None:
            scope.representations[key] = output
        self.online_runs += 1
        return output, {
            "source": "ONLINE_FROZEN_BACKBONE_FLOAT32",
            "elapsed_seconds": time.perf_counter() - started,
        }
