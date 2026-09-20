"""Task adapter lifecycle와 교체 가능한 loss/registry 계약."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Sequence

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True, slots=True)
class AlignedSpanTarget:
    batch_index: int
    sentence_index: int
    token_start: int
    token_end: int
    label: str


@dataclass(frozen=True, slots=True)
class AlignedProposalTarget:
    batch_index: int
    proposal_index: int
    labels: frozenset[str]


@dataclass(slots=True)
class TargetBuildContext:
    batch_shape: tuple[int, int, int]
    source_token_mask: torch.BoolTensor
    sentence_mask: torch.BoolTensor
    aligned_spans: Mapping[str, tuple[AlignedSpanTarget, ...]]
    aligned_proposals: tuple[AlignedProposalTarget, ...]
    semantic_proposal_shape: tuple[int, int]
    prepared_targets: Mapping[str, torch.Tensor]


@dataclass(slots=True)
class TaskLossResult:
    tasks: dict[str, torch.Tensor]
    components: dict[str, torch.Tensor]


class ClassificationLossStrategy(nn.Module, ABC):
    """CE/focal/contrastive 등 pair loss 교체 경계."""

    @abstractmethod
    def forward(
        self,
        logits: torch.Tensor,
        target: torch.LongTensor,
        mask: torch.BoolTensor,
    ) -> torch.Tensor: ...


class CrossEntropyLossStrategy(ClassificationLossStrategy):
    def forward(self, logits, target, mask):
        active = mask & target.ne(-100)
        if not torch.any(active):
            return logits.sum() * 0.0
        return F.cross_entropy(logits[active], target[active])


class FocalCrossEntropyLossStrategy(ClassificationLossStrategy):
    """Coreference ablation용 alternate loss; baseline default는 CE다."""

    def __init__(self, gamma: float = 2.0) -> None:
        super().__init__()
        self.gamma = gamma

    def forward(self, logits, target, mask):
        active = mask & target.ne(-100)
        if not torch.any(active):
            return logits.sum() * 0.0
        ce = F.cross_entropy(logits[active], target[active], reduction="none")
        probability = torch.exp(-ce)
        return (((1 - probability) ** self.gamma) * ce).mean()


class TaskAdapter(nn.Module, ABC):
    """Trainer/collator/model이 구현 family와 무관하게 호출하는 public lifecycle."""

    task_name: str

    @property
    def label_names(self) -> tuple[str, ...]:
        """Decoder/orchestration이 classifier 내부를 보지 않고 쓰는 label contract."""

        return tuple(getattr(self, "labels", ()))

    @abstractmethod
    def build_targets(self, context: TargetBuildContext) -> Mapping[str, torch.Tensor]: ...

    @abstractmethod
    def forward(self, **kwargs): ...

    @abstractmethod
    def compute_loss(
        self,
        output: object,
        targets: Mapping[str, torch.Tensor],
        *,
        options: Mapping[str, float],
    ) -> TaskLossResult: ...

    @abstractmethod
    def decode(self, output: object, **kwargs): ...

    def decode_diagnostics(self, output: object, **kwargs) -> Mapping[str, object]:
        """동일 decoder 호출에서 stage별 진단 출력을 노출하는 optional public hook."""

        return {"final": self.decode(output, **kwargs)}

    def metric_records(
        self,
        output: object,
        targets: Mapping[str, torch.Tensor],
    ) -> Mapping[str, list[object]]:
        """한 batch의 teacher-forced metric record. Span exact는 decoded 경로에서 전달한다."""

        del output, targets
        return {}

    @abstractmethod
    def metrics(self, **records) -> dict[str, float]: ...


class TaskRegistry(nn.Module):
    """Task 이름→adapter의 유일한 registration/dispatch 지점."""

    def __init__(self, adapters: Sequence[TaskAdapter]) -> None:
        super().__init__()
        mapping = {adapter.task_name: adapter for adapter in adapters}
        if len(mapping) != len(adapters):
            raise ValueError("duplicate task adapter name")
        self.adapters = nn.ModuleDict(mapping)

    def __getitem__(self, task_name: str) -> TaskAdapter:
        return self.adapters[task_name]

    def items(self):
        return self.adapters.items()

    def build_targets(self, context: TargetBuildContext) -> dict[str, torch.Tensor]:
        output: dict[str, torch.Tensor] = {}
        for _, adapter in self.items():
            built = adapter.build_targets(context)
            duplicate = set(output) & set(built)
            if duplicate:
                raise ValueError(f"duplicate target ownership: {sorted(duplicate)}")
            output.update(built)
        return output

    def compute_losses(
        self,
        task_outputs: Mapping[str, object],
        targets: Mapping[str, torch.Tensor],
        *,
        options: Mapping[str, float],
    ) -> TaskLossResult:
        tasks: dict[str, torch.Tensor] = {}
        components: dict[str, torch.Tensor] = {}
        for name, adapter in self.items():
            if name not in task_outputs:
                raise ValueError(f"model output lacks registered task {name}")
            result = adapter.compute_loss(task_outputs[name], targets, options=options)
            duplicate = set(tasks) & set(result.tasks)
            if duplicate:
                raise ValueError(f"duplicate loss ownership: {sorted(duplicate)}")
            tasks.update(result.tasks)
            components.update(result.components)
        return TaskLossResult(tasks, components)

    def replace(self, task_name: str, adapter: TaskAdapter) -> None:
        if adapter.task_name != task_name:
            raise ValueError("replacement task_name differs from registry key")
        if task_name not in self.adapters:
            raise KeyError(task_name)
        self.adapters[task_name] = adapter
