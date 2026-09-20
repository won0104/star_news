"""한 번의 KF-DeBERTa forward에서 task가 요청한 hidden layer만 노출한다."""

from __future__ import annotations

from contextvars import ContextVar
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any

import torch
from torch import nn

from .contracts import ArticleBatch, BackboneConfig, BackboneOutput


class BackboneCaptureError(RuntimeError):
    """Raised when selective encoder-layer capture violates its frozen contract."""


class _RequiredLayerCapture:
    """Request-local hooks around the existing Hugging Face encoder forward.

    DebertaV2Model in the pinned Transformers build asks its inner encoder for
    every hidden state even when the public call requests none.  The two control
    hooks suppress that internal tuple and provide only the final-layer reference
    expected by the unchanged outer forward.  Three layer hooks capture the
    configured runtime layers without copying their tensors.
    """

    def __init__(self, model: nn.Module, required_layers: tuple[int, ...]) -> None:
        self.required_layers = tuple(required_layers)
        self.layer_container_path, layer_modules = self._resolve_layer_modules(model)
        parent_path, _, _name = self.layer_container_path.rpartition(".")
        if not parent_path:
            raise BackboneCaptureError("encoder layer container must have a parent module")
        inner_encoder = model.get_submodule(parent_path)
        parameters = inspect.signature(inner_encoder.forward).parameters
        if "output_hidden_states" not in parameters:
            raise BackboneCaptureError(
                "resolved encoder does not expose output_hidden_states"
            )
        if int(getattr(model, "z_steps", 0) or 0) > 1:
            raise BackboneCaptureError("selective capture does not support z_steps > 1")
        self.inner_encoder_path = parent_path
        self.runtime_to_module_index = {
            layer: self._module_index(layer, len(layer_modules))
            for layer in self.required_layers
        }
        self._context: ContextVar[dict[int, torch.Tensor] | None] = ContextVar(
            f"kf_required_layers_{id(self)}",
            default=None,
        )
        self._capture_handles = tuple(
            layer_modules[index].register_forward_hook(self._layer_hook(layer))
            for layer, index in self.runtime_to_module_index.items()
        )
        self._control_handles = (
            inner_encoder.register_forward_pre_hook(
                self._inner_pre_hook,
                with_kwargs=True,
            ),
            inner_encoder.register_forward_hook(
                self._inner_post_hook,
                with_kwargs=True,
            ),
        )

    @staticmethod
    def _module_index(runtime_layer: int, layer_count: int) -> int:
        index = int(runtime_layer) - 1
        if index < 0 or index >= layer_count:
            raise BackboneCaptureError(
                f"runtime L{runtime_layer} has no encoder module"
            )
        return index

    @staticmethod
    def _resolve_layer_modules(model: nn.Module) -> tuple[str, nn.ModuleList]:
        layer_count = int(getattr(getattr(model, "config", None), "num_hidden_layers", 0))
        candidates = [
            (name, module)
            for name, module in model.named_modules()
            if isinstance(module, nn.ModuleList) and len(module) == layer_count
        ]
        if len(candidates) != 1:
            names = [name for name, _module in candidates]
            raise BackboneCaptureError(
                "expected exactly one encoder ModuleList matching num_hidden_layers; "
                f"found {names}"
            )
        return candidates[0]

    def _layer_hook(self, runtime_layer: int):
        def capture(_module, _args, output):
            active = self._context.get()
            if active is None:
                return None
            if runtime_layer in active:
                raise BackboneCaptureError(
                    f"duplicate selective capture for L{runtime_layer}"
                )
            value = output[0] if isinstance(output, (tuple, list)) else output
            if not isinstance(value, torch.Tensor):
                raise BackboneCaptureError(
                    f"encoder L{runtime_layer} hook did not return a Tensor"
                )
            active[runtime_layer] = value
            return None

        return capture

    def _inner_pre_hook(self, _module, args, kwargs):
        if self._context.get() is None:
            return None
        args = list(args)
        kwargs = dict(kwargs)
        if len(args) > 2:
            args[2] = False
        else:
            kwargs["output_hidden_states"] = False
        return tuple(args), kwargs

    def _inner_post_hook(self, _module, _args, _kwargs, output):
        if self._context.get() is None:
            return None
        if getattr(output, "hidden_states", None) is not None:
            raise BackboneCaptureError("inner encoder retained a full hidden tuple")
        last_hidden = getattr(output, "last_hidden_state", None)
        if not isinstance(last_hidden, torch.Tensor):
            raise BackboneCaptureError("inner encoder did not return last_hidden_state")
        from transformers.modeling_outputs import BaseModelOutput

        return BaseModelOutput(
            last_hidden_state=last_hidden,
            hidden_states=(last_hidden,),
            attentions=getattr(output, "attentions", None),
        )

    def run(self, function) -> tuple[Any, dict[int, torch.Tensor]]:
        if self._context.get() is not None:
            raise BackboneCaptureError("nested selective backbone capture is unsupported")
        active: dict[int, torch.Tensor] = {}
        token = self._context.set(active)
        try:
            output = function()
            missing = set(self.required_layers) - set(active)
            unexpected = set(active) - set(self.required_layers)
            if missing or unexpected:
                raise BackboneCaptureError(
                    f"selective capture mismatch: missing={sorted(missing)}, "
                    f"unexpected={sorted(unexpected)}"
                )
            captured = {layer: active[layer] for layer in self.required_layers}
            return output, captured
        finally:
            active.clear()
            self._context.reset(token)

    @property
    def capture_hook_count(self) -> int:
        return len(self._capture_handles)

    @property
    def control_hook_count(self) -> int:
        return len(self._control_handles)

    @property
    def current_context_tensor_count(self) -> int:
        active = self._context.get()
        return 0 if active is None else len(active)


class KFDeBERTaBackbone(nn.Module):
    """Static layer router를 위한 KF-DeBERTa wrapper.

    ``hidden_states[0]``은 embedding이고 L8/L10/L12는 encoder layer 번호 그대로다.
    learned layer mix나 암묵적인 final-layer fallback은 이 모듈의 책임이 아니다.
    테스트에서는 동일 contract의 encoder를 주입할 수 있다.
    """

    def __init__(self, encoder: nn.Module, config: BackboneConfig) -> None:
        super().__init__()
        self.encoder = encoder
        self.runtime_config = config
        model_hidden = int(getattr(getattr(encoder, "config", None), "hidden_size", 0))
        model_layers = int(getattr(getattr(encoder, "config", None), "num_hidden_layers", 0))
        if model_hidden <= 0 or model_layers < max(config.required_layers):
            raise ValueError("encoder config cannot satisfy requested KF hidden layers")
        self.hidden_size = model_hidden
        self.num_hidden_layers = model_layers
        self.encoder.requires_grad_(config.trainable)
        self.required_layer_capture = _RequiredLayerCapture(
            self.encoder,
            config.required_layers,
        )

    @classmethod
    def from_pretrained(
        cls,
        config: BackboneConfig,
        *,
        cache_dir: str | Path,
    ) -> "KFDeBERTaBackbone":
        from transformers import AutoModel

        encoder = AutoModel.from_pretrained(
            config.model_id,
            revision=config.revision,
            cache_dir=str(cache_dir),
            local_files_only=config.local_files_only,
        )
        _verify_cached_weights(config, cache_dir)
        return cls(encoder, config)

    def forward(self, batch: ArticleBatch) -> BackboneOutput:
        batch.validate()
        batch_size, sentence_count, token_count = batch.input_ids.shape
        flat_sentence_mask = batch.sentence_mask.reshape(-1)
        flat_indices = torch.nonzero(flat_sentence_mask, as_tuple=False).flatten()
        flat_ids = batch.input_ids.reshape(-1, token_count).index_select(0, flat_indices)
        flat_attention = batch.attention_mask.reshape(-1, token_count).index_select(
            0, flat_indices
        )
        outputs, selected_layers = self.required_layer_capture.run(
            lambda: self.encoder(
                input_ids=flat_ids,
                attention_mask=flat_attention,
                output_hidden_states=False,
                return_dict=True,
            )
        )
        if getattr(outputs, "hidden_states", None) is not None:
            raise BackboneCaptureError("production backbone returned hidden_states")
        if self.required_layer_capture.current_context_tensor_count:
            raise BackboneCaptureError("selective capture context escaped encoder forward")

        flat_row_count = batch_size * sentence_count
        all_rows_in_order = (
            bool(torch.all(flat_sentence_mask).item())
            and flat_indices.numel() == flat_row_count
            and torch.equal(
                flat_indices,
                torch.arange(flat_row_count, device=flat_indices.device),
            )
        )
        hidden_by_layer: dict[int, torch.Tensor] = {}
        for layer in self.runtime_config.required_layers:
            selected = selected_layers[layer]
            expected = (flat_indices.numel(), token_count, self.hidden_size)
            if tuple(selected.shape) != expected:
                raise ValueError(f"L{layer} shape mismatch: {tuple(selected.shape)} != {expected}")
            if all_rows_in_order:
                # A single PUBLIC article has no padded sentence rows.  Preserve the
                # encoder storage instead of reconstructing an identical dense tensor.
                hidden_by_layer[layer] = selected.view(
                    batch_size,
                    sentence_count,
                    token_count,
                    self.hidden_size,
                )
                continue
            padded = selected.new_zeros(
                flat_row_count,
                token_count,
                self.hidden_size,
            )
            hidden_by_layer[layer] = padded.index_copy(0, flat_indices, selected).reshape(
                batch_size,
                sentence_count,
                token_count,
                self.hidden_size,
            )
        return BackboneOutput(
            hidden_by_layer=hidden_by_layer,
            attention_mask=batch.attention_mask,
            sentence_mask=batch.sentence_mask,
        )

    def train(self, mode: bool = True) -> "KFDeBERTaBackbone":
        super().train(mode)
        if not self.runtime_config.trainable:
            self.encoder.eval()
        return self


def backbone_artifact_manifest(
    config: BackboneConfig,
    cache_dir: str | Path,
) -> dict[str, object]:
    snapshot = _snapshot_directory(config, cache_dir)
    files = {}
    for name in (
        "config.json",
        "pytorch_model.bin",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
    ):
        path = snapshot / name
        if path.is_file():
            files[name] = sha256(path.read_bytes()).hexdigest()
    return {
        "model_id": config.model_id,
        "revision": config.revision,
        "expected_weights_sha256": config.expected_weights_sha256,
        "snapshot": str(snapshot.resolve()),
        "file_sha256": files,
    }


def _verify_cached_weights(
    config: BackboneConfig,
    cache_dir: str | Path,
) -> None:
    weights = _snapshot_directory(config, cache_dir) / "pytorch_model.bin"
    if not weights.is_file():
        raise FileNotFoundError("pinned KF pytorch_model.bin is absent from project cache")
    actual = sha256(weights.read_bytes()).hexdigest()
    if actual != config.expected_weights_sha256:
        raise ValueError(
            f"KF weight SHA-256 mismatch: expected {config.expected_weights_sha256}, got {actual}"
        )


def _snapshot_directory(config: BackboneConfig, cache_dir: str | Path) -> Path:
    escaped = config.model_id.replace("/", "--")
    return Path(cache_dir) / f"models--{escaped}" / "snapshots" / config.revision
