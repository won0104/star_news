"""D8 active-article reduction and gradient clipping observability helpers."""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

import torch

from training.v3_pretraining.selection_contract import (
    GRADIENT_CLIP_CONTRACT_VERSION, LOSS_REDUCTION_CONTRACT_VERSION)


def active_task_counts(articles: Sequence[object], channels: Sequence[str]) -> dict[str, int]:
    return {name: sum(bool(row.active[name]) for row in articles) for name in channels}


def article_weighted_loss(article: object, *, active_counts: Mapping[str, int],
                          weights: Mapping[str, float], channels: Sequence[str]) -> torch.Tensor:
    """One article's exact contribution to the active-article task mean."""
    terms = []
    for name in channels:
        if article.active[name]:
            count = active_counts[name]
            if count <= 0:
                raise ValueError(f"{name}: active article has a zero denominator")
            terms.append(weights[name] * article.losses[name] / count)
    if terms:
        return sum(terms)
    return article.losses[channels[0]] * 0


def reduce_active_task_losses(articles: Sequence[object], *,
                              weights: Mapping[str, float],
                              channels: Sequence[str]) -> torch.Tensor:
    """sum_task weight * mean(loss over active articles), with no extra /group-size."""
    if not articles:
        raise ValueError("loss reduction needs at least one article")
    counts = active_task_counts(articles, channels)
    total = sum(article_weighted_loss(row, active_counts=counts, weights=weights,
                                      channels=channels) for row in articles)
    if not torch.isfinite(total):
        raise ValueError("combined v3 loss is non-finite")
    return total


def parameter_owner(name: str) -> str:
    return name.split(".", 2)[1] if name.startswith("task_modules.") else name.split(".", 1)[0]


def _norm(rows: Iterable[torch.Tensor]) -> float:
    squares = [torch.sum(row.detach().float() ** 2) for row in rows]
    if not squares:
        return 0.0
    return math.sqrt(float(torch.stack(squares).sum()))


def clip_gradients_with_observability(
        named_parameters: Iterable[tuple[str, torch.nn.Parameter]], *,
        max_grad_norm: float = 1.0, cumulative_clipped_count: int = 0,
        expected_owners: Iterable[str] = ()) -> dict[str, object]:
    """Apply global clipping once and report actual global/owner pre/post norms."""
    if max_grad_norm != 1.0 or cumulative_clipped_count < 0:
        raise ValueError("D8 fixes max_grad_norm=1.0 and a nonnegative clip count")
    parameters = list(named_parameters)
    identities = [id(parameter) for _name, parameter in parameters]
    if len(identities) != len(set(identities)):
        raise ValueError("a parameter is assigned to more than one gradient owner")
    owner_gradients: dict[str, list[torch.Tensor]] = {
        owner: [] for owner in sorted(set(expected_owners))}
    grad_parameters = []
    nonfinite_owners = set()
    for name, parameter in parameters:
        owner = parameter_owner(name)
        owner_gradients.setdefault(owner, [])
        if parameter.grad is None:
            continue
        if not torch.isfinite(parameter.grad).all():
            nonfinite_owners.add(owner)
        owner_gradients[owner].append(parameter.grad)
        grad_parameters.append(parameter)
    if nonfinite_owners:
        raise ValueError(f"non-finite gradient owners: {sorted(nonfinite_owners)}")
    pre_owner = {owner: _norm(grads) for owner, grads in owner_gradients.items()}
    pre = _norm(parameter.grad for parameter in grad_parameters)
    if not math.isfinite(pre):
        raise ValueError("non-finite global gradient norm")
    coefficient = min(1.0, max_grad_norm / (pre + 1e-6)) if grad_parameters else 1.0
    if grad_parameters:
        torch.nn.utils.clip_grad_norm_(grad_parameters, max_grad_norm,
                                       error_if_nonfinite=True)
    post_owner = {owner: _norm(grads) for owner, grads in owner_gradients.items()}
    post = _norm(parameter.grad for parameter in grad_parameters)
    clipped = coefficient < 1.0
    # Float32 accumulation can land a few ulps above the mathematical clip bound.
    tolerance = 1e-4
    if post > max_grad_norm + tolerance:
        raise ValueError("post-clip norm exceeds the D8 bound")
    return {
        "contract_version": GRADIENT_CLIP_CONTRACT_VERSION,
        "max_grad_norm": max_grad_norm,
        "global_grad_norm_pre": pre,
        "global_grad_norm_post": post,
        "clip_coefficient": coefficient,
        "clipped": clipped,
        "cumulative_clipped_count": cumulative_clipped_count + int(clipped),
        "owner_grad_norm_pre": pre_owner,
        "owner_grad_norm_post": post_owner,
        "zero_gradient_owners": sorted(owner for owner, norm in pre_owner.items()
                                       if norm == 0.0),
        "nonfinite_owners": [],
        "loss_reduction_contract_version": LOSS_REDUCTION_CONTRACT_VERSION,
    }


def summarize_gradient_clipping(reports: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Reduce group-level clip observations into strict epoch checkpoint metadata."""
    if not reports:
        return {"groups": 0, "cumulative_clipped_count": 0,
                "max_global_grad_norm_pre": 0.0,
                "max_global_grad_norm_post": 0.0,
                "nonfinite_owner_count": 0,
                "zero_gradient_owner_observations": 0}
    for row in reports:
        if row.get("contract_version") != GRADIENT_CLIP_CONTRACT_VERSION:
            raise ValueError("gradient clipping report contract differs")
    return {
        "groups": len(reports),
        "cumulative_clipped_count": int(reports[-1]["cumulative_clipped_count"]),
        "max_global_grad_norm_pre": max(float(row["global_grad_norm_pre"])
                                        for row in reports),
        "max_global_grad_norm_post": max(float(row["global_grad_norm_post"])
                                         for row in reports),
        "nonfinite_owner_count": sum(len(row["nonfinite_owners"])
                                     for row in reports),
        "zero_gradient_owner_observations": sum(len(row["zero_gradient_owners"])
                                                for row in reports),
    }
