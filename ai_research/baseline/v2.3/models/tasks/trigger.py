"""Trigger boundary 학습의 class-balance와 negative-sampling 계약.

이 모듈은 Trigger neural Head를 소유하지 않는다. 동일 logits/target에 적용할 학습 목적만
교체하며, production 기본값은 full-source all-negative BCE와 ``pos_weight=4``다.
"""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from ..contracts import TriggerTrainingConfig


class TriggerBoundaryLossStrategy(nn.Module):
    """동일 boundary logits에 weighted BCE와 deterministic negative sampling을 적용한다."""

    def __init__(self, config: TriggerTrainingConfig | None = None) -> None:
        super().__init__()
        self.config = config or TriggerTrainingConfig()

    def forward(
        self,
        start_logits: torch.Tensor,
        end_logits: torch.Tensor,
        start_target: torch.Tensor,
        end_target: torch.Tensor,
        token_mask: torch.BoolTensor,
        *,
        sample_step: int = 0,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        if (
            start_logits.shape != end_logits.shape
            or start_target.shape != start_logits.shape
            or end_target.shape != end_logits.shape
            or token_mask.shape != start_logits.shape[:-1]
        ):
            raise ValueError("Trigger boundary loss tensor shapes differ")
        if sample_step < 0:
            raise ValueError("Trigger sample_step must be non-negative")

        valid = token_mask.unsqueeze(-1).expand_as(start_logits)
        start_loss, start_stats = self._one_boundary(
            start_logits,
            start_target,
            valid,
            sample_step=sample_step,
            stream=0,
        )
        end_loss, end_stats = self._one_boundary(
            end_logits,
            end_target,
            valid,
            sample_step=sample_step,
            stream=1,
        )
        diagnostics = {
            "trigger/start_loss": start_loss,
            "trigger/end_loss": end_loss,
            "trigger/effective_pos_weight": start_logits.new_tensor(
                self.config.pos_weight
            ),
        }
        diagnostics.update(
            {f"trigger/start_{name}": value for name, value in start_stats.items()}
        )
        diagnostics.update(
            {f"trigger/end_{name}": value for name, value in end_stats.items()}
        )
        diagnostics["trigger/positive_boundary_count"] = (
            start_stats["positive_count"] + end_stats["positive_count"]
        )
        diagnostics["trigger/negative_boundary_count"] = (
            start_stats["negative_count"] + end_stats["negative_count"]
        )
        diagnostics["trigger/sampled_negative_count"] = (
            start_stats["sampled_negative_count"]
            + end_stats["sampled_negative_count"]
        )
        return start_loss + end_loss, diagnostics

    def _one_boundary(
        self,
        logits: torch.Tensor,
        target: torch.Tensor,
        valid: torch.BoolTensor,
        *,
        sample_step: int,
        stream: int,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        positive = valid & target.gt(0.5)
        negative = valid & ~positive
        selected_negative = self._sample_negative(
            negative,
            positive_count=int(positive.sum().item()),
            sample_step=sample_step,
            stream=stream,
        )
        selected = positive | selected_negative
        if not torch.any(selected):
            loss = logits.sum() * 0.0
        else:
            arguments: dict[str, object] = {}
            if self.config.pos_weight != 1.0:
                arguments["pos_weight"] = logits.new_tensor(self.config.pos_weight)
            loss = F.binary_cross_entropy_with_logits(
                logits[selected],
                target[selected].to(logits.dtype),
                **arguments,
            )
        return loss, {
            "positive_count": logits.new_tensor(float(positive.sum().item())),
            "negative_count": logits.new_tensor(float(negative.sum().item())),
            "sampled_negative_count": logits.new_tensor(
                float(selected_negative.sum().item())
            ),
        }

    def _sample_negative(
        self,
        negative: torch.BoolTensor,
        *,
        positive_count: int,
        sample_step: int,
        stream: int,
    ) -> torch.BoolTensor:
        ratio = self.config.negative_to_positive_ratio
        if ratio is None:
            return negative
        negative_flat = torch.nonzero(
            negative.detach().to(device="cpu").reshape(-1), as_tuple=False
        ).flatten()
        # Zero-positive batches still contribute a small, deterministic negative signal.
        requested = math.ceil(ratio * max(positive_count, 1))
        count = min(int(negative_flat.numel()), requested)
        selected_cpu = torch.zeros(negative.numel(), dtype=torch.bool)
        if count:
            generator = torch.Generator(device="cpu")
            mixed_seed = (
                self.config.sampling_seed
                + 1_000_003 * sample_step
                + 97_409 * stream
            ) % (2**63 - 1)
            generator.manual_seed(mixed_seed)
            order = torch.randperm(
                negative_flat.numel(), generator=generator
            )[:count]
            selected_cpu[negative_flat[order]] = True
        return selected_cpu.reshape(negative.shape).to(device=negative.device)
