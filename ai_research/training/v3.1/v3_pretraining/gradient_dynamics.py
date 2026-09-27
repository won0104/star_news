"""Disposable P1 gradient observations around the existing staged optimizer step.

The observer only reads losses, gradients, and the parameter snapshot already
made by ``StagedTrainer.step``. It never changes the total loss or optimizer.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import torch

from training.v3_pretraining.optimization_contract import parameter_owner


PRODUCER_PREFIXES = {
    "semantic.canonical": "canonical_span.semantic_head.",
    "semantic.exact": "task_modules.semantic_validity.classifier.",
    "trigger.boundary": "task_modules.trigger.boundary.",
    "trigger.span_score": "task_modules.trigger.span_score.",
    "participant.boundary_B2": "task_modules.participant.boundary.",
    "participant.span_score": "task_modules.participant.span_score.",
    "entity_mention.typing": "task_modules.entity_mention.typing.",
    "time_mention.span": "task_modules.time_mention.span.",
    "statement_type": "task_modules.statement_type.",
    "shared.document_context": "document_context.",
    "shared.candidate_span": "candidate_span.",
    "shared.exact_source_span": "exact_source_span.",
}


def _square_norm(tensors) -> float:
    return math.fsum(float(t.detach().float().square().sum()) for t in tensors)


def _norm(tensors) -> float:
    return math.sqrt(_square_norm(tensors))


class GradientDynamicsObserver:
    """Record a staged step without replacing backward, clipping, or optimizer.step."""

    def __init__(self, *, probe_steps: int) -> None:
        if probe_steps < 0:
            raise ValueError("probe_steps must be nonnegative")
        self.probe_steps = probe_steps
        self.rows: list[dict] = []
        self.probes: list[dict] = []
        self._pending: dict | None = None

    def before_backward(self, *, core, oracle_rows: Sequence[object], phase,
                        total: torch.Tensor, step: int) -> None:
        if self._pending is not None:
            raise ValueError("gradient audit requires one staged step at a time")
        if any(parameter.grad is not None for parameter in core.parameters()):
            raise ValueError("diagnostic task probes require clean .grad fields")
        tasks = {}
        task_tensors = {}
        for task in phase.active_losses:
            active = [row.losses[task] for row in oracle_rows if row.active[task]]
            if not active:
                continue
            raw = sum(active) / len(active)
            weight = float(phase.loss_weights[task])
            weighted = raw * weight * phase.oracle_weight
            tasks[task] = {
                "active_article_count": len(active), "raw_loss": float(raw.detach()),
                "loss_weight": weight, "weighted_contribution": float(weighted.detach())}
            task_tensors[task] = weighted
        if not math.isclose(sum(row["weighted_contribution"] for row in tasks.values()),
                            float(total.detach()), rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("audit task contributions differ from actual total loss")
        self._pending = {"step": step, "tasks": tasks,
                         "total_loss": float(total.detach())}
        if step <= self.probe_steps:
            self._probe_shared(core, task_tensors, step)
        if any(parameter.grad is not None for parameter in core.parameters()):
            raise ValueError("diagnostic autograd.grad contaminated optimizer gradients")

    def _probe_shared(self, core, task_tensors: Mapping[str, torch.Tensor],
                      step: int) -> None:
        shared = [parameter for name, parameter in core.named_parameters()
                  if name.startswith("document_context.") and parameter.requires_grad]
        if not shared:
            raise ValueError("P1 shared DCE has no trainable parameters")
        vectors = {}
        norms = {}
        for task, loss in task_tensors.items():
            if not loss.requires_grad:
                continue
            grads = torch.autograd.grad(
                loss, shared, retain_graph=True, allow_unused=True)
            # CPU copies keep the pair calculation off the live training graph.
            vector = tuple(None if grad is None else grad.detach().float().cpu()
                           for grad in grads)
            norm = _norm(grad for grad in vector if grad is not None)
            if norm > 0:
                vectors[task], norms[task] = vector, norm
        matrix = {task: {task: 1.0} for task in vectors}
        names = sorted(vectors)
        for index, left in enumerate(names):
            for right in names[index + 1:]:
                dot = math.fsum(float((a * b).sum())
                                for a, b in zip(vectors[left], vectors[right])
                                if a is not None and b is not None)
                cosine = max(-1.0, min(1.0, dot / (norms[left] * norms[right])))
                matrix[left][right] = cosine
                matrix[right][left] = cosine
        self.probes.append({"step": step, "shared_parameter_owner": "document_context",
                            "task_shared_grad_norm": norms,
                            "pairwise_cosine": matrix,
                            "dominant_task": (max(norms, key=norms.get) if norms else None)})

    def after_backward(self, *, core) -> None:
        if self._pending is None:
            raise ValueError("gradient audit has no active step")
        named = tuple(core.named_parameters())
        producer_norms = {}
        producer_missing = {}
        for producer, prefix in PRODUCER_PREFIXES.items():
            parameters = [parameter for name, parameter in named
                          if name.startswith(prefix) and parameter.requires_grad]
            if not parameters:
                continue
            producer_norms[producer] = _norm(parameter.grad for parameter in parameters
                                             if parameter.grad is not None)
            producer_missing[producer] = sum(parameter.grad is None for parameter in parameters)
        self._pending["producer_grad_norm_pre"] = producer_norms
        self._pending["producer_grad_missing_tensors"] = producer_missing
        self._pending["owner_grad_norm_pre"] = {
            owner: _norm(parameter.grad for name, parameter in named
                         if parameter_owner(name) == owner and parameter.grad is not None)
            for owner in sorted({parameter_owner(name) for name, parameter in named
                                 if parameter.requires_grad})}

    def after_step(self, *, core, before: Mapping[str, torch.Tensor],
                   clip: Mapping[str, object], result: Mapping[str, object]) -> None:
        if self._pending is None or self._pending["step"] != result["optimizer_steps"]:
            raise ValueError("gradient audit step order differs")
        named = tuple(core.named_parameters())
        groups = {**{owner: (lambda name, owner=owner: parameter_owner(name) == owner)
                     for owner in sorted({parameter_owner(name) for name in before})},
                  **{producer: (lambda name, prefix=prefix: name.startswith(prefix))
                     for producer, prefix in PRODUCER_PREFIXES.items()}}
        updates = {}
        for group, contains in groups.items():
            members = [(name, parameter) for name, parameter in named
                       if name in before and contains(name)]
            if not members:
                continue
            pre = _norm(before[name] for name, _ in members)
            delta = _norm(parameter.detach() - before[name] for name, parameter in members)
            updates[group] = {"parameter_norm_pre": pre, "update_norm": delta,
                              "relative_update": delta / (pre + 1e-12)}
        row = {**self._pending,
               "article_ids": list(result["articles"]),
               "decision_path_gradients": dict(result["decision_producer_gradient_l1"]),
               "owner_update": {name: value for name, value in updates.items()
                                if name in result["optimizer"]["owners"]},
               "producer_update": {name: value for name, value in updates.items()
                                   if name in PRODUCER_PREFIXES},
               "gradient_clip": dict(clip),
               "gradient_owners": list(result["gradient_owners"]),
               "changed_owners": list(result["changed_owners"])}
        self.rows.append(row)
        self._pending = None
