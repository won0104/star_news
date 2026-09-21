"""고정 backbone 한 번의 source view 실행과 학습 core의 autograd 경계."""

from __future__ import annotations

import torch
from torch import nn

from models.contracts import ArticleBatch, BackboneOutput


class FrozenBackboneFeatureBuilder:
    """주입된 고정 backbone을 no_grad로 실행하고 일반 tensor만 넘긴다.

    실제 model load/cache는 이 객체의 책임이 아니다. 서빙용 inference_mode
    carrier를 학습 core에 넘기는 사용은 빠르게 거절한다.
    """

    def __init__(self, backbone: nn.Module) -> None:
        if not isinstance(backbone, nn.Module):
            raise TypeError("frozen feature producer must be nn.Module")
        if any(parameter.requires_grad for parameter in backbone.parameters()):
            raise ValueError("v3 backbone producer must be frozen")
        self.backbone = backbone

    def build(self, batch: ArticleBatch) -> BackboneOutput:
        batch.validate()
        self.backbone.eval()
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
        return output
