"""Checkpoint-bound Primary acceptance 이후 PUBLIC proposition 표시 대상을 고른다.

관계는 이미 승인된 CAUSES의 출력 완결성에만 사용한다. Head 점수, acceptance,
PUBLIC graph 투영은 이 모듈에서 변경하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import math
from typing import Mapping, Sequence

from runtime.v3_pretraining.attribution_scoring import RelationFact
from runtime.v3_pretraining.primary_scoring import PrimaryScore


@dataclass(frozen=True, slots=True)
class PublicSelection:
    event_ids: frozenset[str]
    statement_ids: frozenset[str]
    causes_completion_event_id: str | None


@dataclass(frozen=True, slots=True)
class PublicBaseSelection:
    """Relation scoring 전에 확정 가능한 Primary 순위와 kind별 상위 3개."""

    ranked_events: tuple[PrimaryScore, ...]
    ranked_statements: tuple[PrimaryScore, ...]
    ranked_all: tuple[PrimaryScore, ...]
    event_ids: frozenset[str]
    statement_ids: frozenset[str]


def select_public_base(*, accepted_scores: Sequence[PrimaryScore],
                       event_spans: Mapping[str, tuple[int, int]],
                       statement_spans: Mapping[str, tuple[int, int]]) -> PublicBaseSelection:
    """기존 동점 규칙으로 Primary 통과 Event/Statement의 기본 3+3을 정한다."""
    seen: set[tuple[str, str]] = set()
    for row in accepted_scores:
        spans = event_spans if row.kind == "EVENT_CLUSTER" else statement_spans if row.kind == "STATEMENT" else None
        key = (row.kind, row.local_id)
        if (spans is None or row.local_id not in spans or key in seen or
                not math.isfinite(row.primary_score)):
            raise ValueError("PUBLIC selection has unknown/duplicate/nonfinite Primary row")
        seen.add(key)

    def rank(row: PrimaryScore) -> tuple[float, int, int, str, str]:
        start, end = (event_spans if row.kind == "EVENT_CLUSTER" else statement_spans)[row.local_id]
        return (-row.primary_score, start, end, row.kind, row.local_id)

    events = tuple(sorted((row for row in accepted_scores if row.kind == "EVENT_CLUSTER"), key=rank))
    statements = tuple(sorted((row for row in accepted_scores if row.kind == "STATEMENT"), key=rank))
    return PublicBaseSelection(
        events, statements, tuple(sorted(accepted_scores, key=rank)),
        frozenset(row.local_id for row in events[:3]),
        frozenset(row.local_id for row in statements[:3]))


def causes_discovery_pairs(base: PublicBaseSelection) -> frozenset[tuple[str, str]]:
    """기본 Event와 나머지 Primary 통과 Event 사이의 양방향 ordered pair."""
    remaining = (row.local_id for row in base.ranked_events
                 if row.local_id not in base.event_ids)
    return frozenset(pair for candidate in remaining for seed in base.event_ids
                     for pair in ((seed, candidate), (candidate, seed)))


def complete_public_selection(*, base: PublicBaseSelection,
                              accepted_relations: Sequence[RelationFact]) -> PublicSelection:
    """승인된 CAUSES 한 자리와 통합 Primary 순위의 나머지 자리를 채운다."""
    selected_events = set(base.event_ids)
    selected_statements = set(base.statement_ids)

    # CAUSES는 방향을 판단하지 않는다. 이미 표시되는 Event의 상대 endpoint만
    # 후보이며, 관계 점수 대신 그 Event의 Primary 순위로 하나를 고른다.
    cause_neighbors: set[str] = set()
    for relation in accepted_relations:
        if relation.relation != "CAUSES":
            continue
        if relation.source_id in selected_events:
            cause_neighbors.add(relation.target_id)
        if relation.target_id in selected_events:
            cause_neighbors.add(relation.source_id)
    cause_extension = next((row.local_id for row in base.ranked_events
                            if row.local_id not in selected_events and
                            row.local_id in cause_neighbors), None)
    if cause_extension is not None:
        selected_events.add(cause_extension)

    remaining = (row for row in base.ranked_all
                 if row.local_id not in (selected_events if row.kind == "EVENT_CLUSTER"
                                         else selected_statements))
    flex_count = 1 if cause_extension is not None else 2
    for row in islice(remaining, flex_count):
        (selected_events if row.kind == "EVENT_CLUSTER" else selected_statements).add(row.local_id)
    return PublicSelection(frozenset(selected_events), frozenset(selected_statements),
                           cause_extension)


def public_relation_pairs(selection: PublicSelection) -> tuple[frozenset[tuple[str, str]],
                                                                 frozenset[tuple[str, str]]]:
    """최종 PUBLIC proposition 양끝이 살아남은 ABOUT/CAUSES pair만 반환한다."""
    about = frozenset((sid, eid) for sid in selection.statement_ids
                      for eid in selection.event_ids)
    causes = frozenset((left, right) for left in selection.event_ids
                       for right in selection.event_ids if left != right)
    return about, causes


def select_public_propositions(*, accepted_scores: Sequence[PrimaryScore],
                               accepted_relations: Sequence[RelationFact],
                               event_spans: Mapping[str, tuple[int, int]],
                               statement_spans: Mapping[str, tuple[int, int]]) -> PublicSelection:
    """kind별 3개와 추가 2개를 고른다. CAUSES에는 추가 자리 하나만 허용한다."""
    base = select_public_base(accepted_scores=accepted_scores,
                              event_spans=event_spans,
                              statement_spans=statement_spans)
    return complete_public_selection(base=base, accepted_relations=accepted_relations)
