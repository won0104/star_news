"""학습 step에서 runtime decision producer별 loss gradient 도달을 검증한다.

Gold loss의 세부 경로가 활성일 때만 검사한다. 검사 대상은 실제 runtime에서
acceptance/ranking에 쓰이는 parameter이며, task owner 전체 gradient로 대체하지 않는다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import torch


_DECISION_PRODUCERS = {
    "V23_BASELINE": (
        ("semantic:canonical", "semantic_validity:CANONICAL_DECISION",
         "canonical_span.semantic_head.network.3.weight"),
        ("semantic:exact", "semantic_validity:EXACT_DECISION",
         "task_modules.semantic_validity.classifier.3.weight"),
        ("trigger:span_score", "trigger:EXACT_SPAN_FITNESS",
         "task_modules.trigger.span_score.weight"),
        ("participant:span_score", "participant:ROLE_FILLER_EXISTENCE",
         "task_modules.participant.span_score.2.weight"),
        ("entity:typing", "entity_mention:MENTION_EXISTENCE",
         "task_modules.entity_mention.typing.classifier.4.weight"),
        ("time:span", "time_mention:MENTION_EXISTENCE",
         "task_modules.time_mention.span.classifier.4.weight"),
    ),
    "V3_WINDOW": (
        ("semantic:exact", "semantic_validity:KIND_DECISION",
         "task_modules.semantic_validity.classifier.3.weight"),
        ("trigger:span_score", "trigger:EXACT_SPAN_FITNESS",
         "task_modules.trigger.span_score.weight"),
        ("participant:span_score", "participant:ROLE_FILLER_EXISTENCE",
         "task_modules.participant.span_score.2.weight"),
        ("entity:existence", "entity_mention:MENTION_EXISTENCE",
         "task_modules.entity_mention.existence.classifier.4.weight"),
        ("time:span", "time_mention:MENTION_EXISTENCE",
         "task_modules.time_mention.span.classifier.4.weight"),
    ),
}

_ENTITY_IDENTITY_PRODUCER = (
    "entity_identity", "entity_coreference", "entity_coreference:KEEP_MERGE",
    "task_modules.entity_coreference.classifier.3.weight")


def _parameter_gradient_norm(core: torch.nn.Module, producer: str,
                             parameter_name: str) -> float:
    parameter = dict(core.named_parameters()).get(parameter_name)
    if parameter is None or not parameter.requires_grad or parameter.grad is None:
        raise ValueError(f"{producer}: active runtime decision producer has no gradient")
    norm = float(parameter.grad.detach().abs().sum())
    if not torch.isfinite(parameter.grad).all() or norm <= 0:
        raise ValueError(f"{producer}: active runtime decision gradient is zero/non-finite")
    return norm


def assert_extraction_decision_reachability(
        core: torch.nn.Module, *, profile: str,
        article_censuses: Sequence[Mapping[str, object]]) -> dict[str, float]:
    """Fail before optimizer.step if an active decision producer has no gradient.

    Each census must come from the extraction adapter in the current backward pass.
    The result records L1 gradient norms for the checked producer parameters.
    """
    if profile not in _DECISION_PRODUCERS or not article_censuses:
        raise ValueError("known extraction profile and article censuses are required")
    available_rows = []
    for census in article_censuses:
        extraction = census.get("extraction")
        available = extraction.get("available") if isinstance(extraction, Mapping) else None
        if not isinstance(available, Mapping):
            raise ValueError("extraction decision census is missing")
        available_rows.append(available)
    checked = {}
    for producer, census_key, parameter_name in _DECISION_PRODUCERS[profile]:
        if not all(census_key in available for available in available_rows):
            raise ValueError(f"{producer}: decision path census is missing")
        count = sum(available[census_key][label] for available in available_rows
                    for label in ("positive", "negative"))
        if count == 0:
            continue
        checked[producer] = _parameter_gradient_norm(core, producer, parameter_name)
    return checked


def assert_entity_identity_decision_reachability(
        core: torch.nn.Module, *, phase: str,
        article_active: Sequence[Mapping[str, bool]],
        article_censuses: Sequence[Mapping[str, object]]) -> dict[str, float]:
    """Gate P3 classifier for the sampled MERGE/hard KEEP/random KEEP paths."""
    required_phase, loss_term, producer, parameter_name = _ENTITY_IDENTITY_PRODUCER
    if (phase != required_phase or not article_active or
            len(article_active) != len(article_censuses) or any(
            loss_term not in row for row in article_active)):
        raise ValueError("Entity identity phase/loss inventory differs")
    paths = ("MERGE", "HARD_KEEP", "RANDOM_KEEP")
    path_counts = {path: 0 for path in paths}
    for active, census in zip(article_active, article_censuses):
        entity = census.get("entity")
        counts = (entity.get("entity_coreference_pair_paths")
                  if isinstance(entity, Mapping) else None)
        if (not isinstance(counts, Mapping) or set(counts) != set(paths) or
                any(type(counts[path]) is not int or counts[path] < 0
                    for path in paths) or
                active[loss_term] != (sum(counts.values()) > 0)):
            raise ValueError("Entity identity path-specific pair census differs")
        for path in paths:
            path_counts[path] += counts[path]
    if not any(path_counts.values()):
        return {}
    norm = _parameter_gradient_norm(core, producer, parameter_name)
    return {producer: norm, **{f"{producer}:{path}": norm
                               for path in paths if path_counts[path]}}
