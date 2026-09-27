"""ASSERTED_BY가 학습·추론에서 공유하는 source/Entity option 계약.

이 모듈은 Gold label을 받지 않는다. exact source 표현의 결합, Entity member
평균, runtime-style option 발견만 담당하며 acceptance나 정답 보정은 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence

import torch

from runtime.v3_pretraining.entity_identity import EntityClosure, LocalEntity
from runtime.v3_pretraining.entity_union import EntityCandidateUniverse, RoleBinding
from runtime.v3_pretraining.source_layout import SourceLayout
from runtime.v3_pretraining.relation_routing import ASSERTED_BY_POLICY_ID


ASSERTOR_OPTION_LIMIT = 8
ASSERTOR_OPTION_CONTRACT = "assertor-gold-free-options-v1"
ASSERTOR_ENTITY_STATE_PREFIX = "ASSERTOR_ENTITY:"
EVENT_ENTITY_STATE_PREFIX = "ENTITY:"
ENTITY_MEMBER_STATE_PREFIX = "ENTITY_MEMBER:"


def assertor_option_policy_sha256() -> str:
    return sha256((ASSERTED_BY_POLICY_ID + ":" + ASSERTOR_OPTION_CONTRACT +
                   ":distance-local-id:max8").encode()).hexdigest()


def load_predicted_asserted_by_option_binding(
        path: str | Path, *, checkpoint_sha256: str,
        source_policy_sha256: str, source_acceptance_sha256: str,
        entity_identity_policy_sha256: str,
        entity_pair_validation_artifact_sha256: str) -> str:
    """Return artifact byte SHA only after trained-identity option validation."""
    data = Path(path).read_bytes()
    row = json.loads(data)
    required = {"schema_version", "source_profile", "selection_status",
                "option_policy_id", "option_policy_sha256", "checkpoint_sha256",
                "source_policy_sha256", "source_acceptance_sha256",
                "entity_identity_policy_sha256",
                "entity_pair_validation_artifact_sha256",
                "predicted_validation_report_sha256"}
    report_sha = row.get("predicted_validation_report_sha256") if isinstance(row, dict) else None
    if (not isinstance(row, dict) or set(row) != required or
            row["schema_version"] != "v23-asserted-by-option-binding-v2" or
            row["source_profile"] != "V23_BASELINE" or
            row["selection_status"] != "PREDICTED_VALIDATED" or
            row["option_policy_id"] != ASSERTED_BY_POLICY_ID or
            row["option_policy_sha256"] != assertor_option_policy_sha256() or
            row["checkpoint_sha256"] != checkpoint_sha256 or
            row["source_policy_sha256"] != source_policy_sha256 or
            row["source_acceptance_sha256"] != source_acceptance_sha256 or
            row["entity_identity_policy_sha256"] != entity_identity_policy_sha256 or
            row["entity_pair_validation_artifact_sha256"] !=
            entity_pair_validation_artifact_sha256 or
            not isinstance(entity_pair_validation_artifact_sha256, str) or
            len(entity_pair_validation_artifact_sha256) != 64 or
            any(char not in "0123456789abcdef"
                for char in entity_pair_validation_artifact_sha256) or
            not isinstance(report_sha, str) or len(report_sha) != 64 or
            any(char not in "0123456789abcdef" for char in report_sha)):
        raise ValueError("ASSERTED_BY option routing needs predicted-validated binding")
    return sha256(data).hexdigest()


def assertor_relation_left(statement_state: torch.Tensor,
                           source_state: torch.Tensor) -> torch.Tensor:
    """STATEMENT L8과 Assertor exact STATEMENT/L8을 기존 head 차원으로 결합한다."""
    if statement_state.ndim != 1 or source_state.shape != statement_state.shape:
        raise ValueError("Assertor left states must be equal-width vectors")
    return statement_state + source_state


def aggregate_entity_member_states(
        entities: Sequence[LocalEntity],
        candidate_states: Mapping[str, torch.Tensor], *,
        candidate_sort_keys: Mapping[str, tuple[int, int, str]] | None = None,
) -> dict[str, torch.Tensor]:
    """각 Entity의 모든 ENTITY/L12 member state를 순서와 무관하게 평균한다."""
    output: dict[str, torch.Tensor] = {}
    for entity in entities:
        if candidate_sort_keys is not None and any(
                candidate_id not in candidate_sort_keys
                for candidate_id in entity.candidate_ids):
            raise ValueError("Entity aggregation needs every source-only member sort key")
        member_ids = tuple(sorted(
            entity.candidate_ids,
            key=(lambda candidate_id: candidate_sort_keys[candidate_id])
            if candidate_sort_keys is not None else None))
        if not member_ids or any(candidate_id not in candidate_states for candidate_id in member_ids):
            raise ValueError("Entity aggregation requires every cluster member state")
        states = [candidate_states[candidate_id] for candidate_id in member_ids]
        if any(state.ndim != 1 or state.shape != states[0].shape for state in states):
            raise ValueError("Entity member states must be equal-width vectors")
        output[entity.local_id] = torch.stack(states).mean(dim=0)
    return output


@dataclass(frozen=True, slots=True)
class EntityRepresentationViews:
    """동일 L12 member tensor에서 consumer별 기존/신규 표현을 분리한다."""

    event_representative: dict[str, torch.Tensor]
    assertor_all_member_mean: dict[str, torch.Tensor]


def build_entity_representation_views(
        entities: Sequence[LocalEntity],
        candidate_states: Mapping[str, torch.Tensor], *,
        candidate_sort_keys: Mapping[str, tuple[int, int, str]] | None = None,
) -> EntityRepresentationViews:
    """Event 대표 mention과 ASSERTED_BY all-member mean을 서로 덮어쓰지 않는다."""
    aggregates = aggregate_entity_member_states(
        entities, candidate_states, candidate_sort_keys=candidate_sort_keys)
    representatives = {}
    for entity in entities:
        if entity.representative_candidate_id not in candidate_states:
            raise ValueError("Event Entity representation needs its representative member")
        representatives[entity.local_id] = candidate_states[entity.representative_candidate_id]
    return EntityRepresentationViews(representatives, aggregates)


@dataclass(frozen=True, slots=True)
class AssertorEntityOptions:
    """Gold 없이 발견한 bounded Entity option과 발견 provenance."""

    entity_ids: tuple[str, ...]
    exact_binding_ids: tuple[str, ...]
    same_sentence_ids: tuple[str, ...]
    eligible_count: int
    truncated_count: int
    status: str
    contract: str = ASSERTOR_OPTION_CONTRACT


def _span_distance(source_start: int, source_end: int,
                   target_start: int, target_end: int) -> int:
    if target_end <= source_start:
        return source_start - target_end
    if source_end <= target_start:
        return target_start - source_end
    return 0


def _containing_sentence(layout: SourceLayout, start: int, end: int) -> int | None:
    return next((index for index, (left, right) in enumerate(layout.sentence_spans)
                 if left <= start and end <= right), None)


@dataclass(frozen=True, slots=True)
class AssertorEntityOptionIndex:
    """One article's source coordinates for repeated Statement option queries."""

    article_version_id: str
    content_sha256: str
    universe: EntityCandidateUniverse
    preliminary: EntityClosure
    members: tuple[tuple[str, tuple[tuple[int, int, int | None], ...]], ...]


def build_assertor_entity_option_index(*, layout: SourceLayout,
                                       universe: EntityCandidateUniverse,
                                       preliminary: EntityClosure) -> AssertorEntityOptionIndex:
    """Index Entity member geometry once; ranking remains source distance/local ID."""
    if (universe.article_version_id != layout.article.article_version_id or
            universe.content_sha256 != layout.article.content_sha256):
        raise ValueError("Assertor option index needs matching article source")
    candidates = universe.candidate_by_id()
    members = []
    for entity in preliminary.entities:
        if not entity.candidate_ids or any(cid not in candidates for cid in entity.candidate_ids):
            raise ValueError("Assertor option index has missing Entity member")
        members.append((entity.local_id, tuple(
            (candidates[cid].start, candidates[cid].end,
             _containing_sentence(layout, candidates[cid].start, candidates[cid].end))
            for cid in entity.candidate_ids)))
    return AssertorEntityOptionIndex(universe.article_version_id,
                                     universe.content_sha256, universe,
                                     preliminary, tuple(members))


def build_assertor_entity_options(*, layout: SourceLayout,
                                  universe: EntityCandidateUniverse,
                                  preliminary: EntityClosure,
                                  binding: RoleBinding,
                                  max_options: int = ASSERTOR_OPTION_LIMIT,
                                  index: AssertorEntityOptionIndex | None = None
                                  ) -> AssertorEntityOptions:
    """exact binding·same sentence·거리 후보를 하나의 Gold-free 순서로 제한한다."""
    if max_options <= 0 or max_options > ASSERTOR_OPTION_LIMIT:
        raise ValueError("Assertor option budget must be in [1, 8]")
    if (binding.role != "ASSERTOR" or binding.owner_id == "" or
            universe.article_version_id != layout.article.article_version_id or
            universe.content_sha256 != layout.article.content_sha256):
        raise ValueError("Assertor option builder needs matching source-only inputs")
    if index is None:
        index = build_assertor_entity_option_index(
            layout=layout, universe=universe, preliminary=preliminary)
    elif (index.universe is not universe or index.preliminary is not preliminary or
          (index.article_version_id, index.content_sha256) !=
          (universe.article_version_id, universe.content_sha256)):
        raise ValueError("Assertor option index differs from Entity closure")
    exact = tuple(sorted({preliminary.candidate_to_entity[candidate_id]
                          for candidate_id in binding.candidate_ids
                          if candidate_id in preliminary.candidate_to_entity}))
    source_sentence = _containing_sentence(layout, binding.start, binding.end)
    same_sentence = []
    ranking = []
    for entity_id, member_rows in index.members:
        distance = min(_span_distance(binding.start, binding.end, start, end)
                       for start, end, _ in member_rows)
        if source_sentence is not None and any(
                sentence == source_sentence for _, _, sentence in member_rows):
            same_sentence.append(entity_id)
        ranking.append((distance, entity_id))
    # nearest cohort는 모든 preliminary Entity를 포함한다. exact/same-sentence provenance는
    # 별도 보존하되 최종 정렬은 승인된 source distance, local ID만 사용한다.
    ordered = tuple(entity_id for _, entity_id in sorted(ranking))
    selected = ordered[:max_options]
    return AssertorEntityOptions(
        selected, exact, tuple(sorted(same_sentence)), len(ordered),
        max(0, len(ordered) - len(selected)), "READY" if selected else "NO_OPTIONS")


def assertor_option_routing_trace(*, layout: SourceLayout,
                                  universe: EntityCandidateUniverse,
                                  preliminary: EntityClosure,
                                  binding: RoleBinding,
                                  options: AssertorEntityOptions) -> dict[str, object]:
    """Expose D5 option provenance without adding a second route or fine score."""
    candidates = universe.candidate_by_id()
    entities = {entity.local_id: entity for entity in preliminary.entities}
    if any(eid not in entities for eid in options.entity_ids):
        raise ValueError("Assertor route target differs from preliminary Entity inventory")
    lineage = sha256(json.dumps({
        "article_version_id": layout.article.article_version_id,
        "content_sha256": layout.article.content_sha256,
        "entities": sorted((entity.local_id, sorted(entity.candidate_ids))
                           for entity in preliminary.entities),
        "source": (binding.owner_id, binding.start, binding.end, binding.text),
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    policy_sha = assertor_option_policy_sha256()
    records = []
    for rank, entity_id in enumerate(options.entity_ids, 1):
        entity = entities[entity_id]
        distance = min(_span_distance(binding.start, binding.end,
                                      candidates[cid].start, candidates[cid].end)
                       for cid in entity.candidate_ids)
        source = ("EXACT_BINDING" if entity_id in options.exact_binding_ids else
                  "SAME_SENTENCE" if entity_id in options.same_sentence_ids else
                  "NEAREST")
        records.append({"statement_id": binding.owner_id,
                        "candidate_entity_local_id": entity_id,
                        "option_source": source, "source_distance": distance,
                        "candidate_rank": rank, "routing_status": "ROUTING_SELECTED",
                        "fine_status": "NOT_RUN", "policy_id": ASSERTED_BY_POLICY_ID,
                        "policy_sha256": policy_sha,
                        "source_inventory_lineage": lineage})
    return {"statement_id": binding.owner_id, "records": records,
            "eligible": options.eligible_count, "selected": len(records),
            "not_evaluated_routing": options.truncated_count,
            "missing_pair_status": "NOT_EVALUATED_ROUTING",
            "policy_id": ASSERTED_BY_POLICY_ID,
            "policy_sha256": policy_sha,
            "source_inventory_lineage": lineage}


def assertor_option_target_status(options: AssertorEntityOptions,
                                  target_local_entity_id: str) -> str:
    """Gold target은 discovery 뒤 감독 판정에만 사용하며 option을 변경하지 않는다."""
    if not target_local_entity_id:
        raise ValueError("resolved Assertor supervision needs a target Entity")
    return ("TARGET_PRESENT" if target_local_entity_id in options.entity_ids
            else "OPTION_MISS")
