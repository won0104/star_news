"""Precision-first EVENT span-variant canonicalization policy.

This policy does not alter Event coreference. It groups only already resolved
EVENT identities whose representative spans are containment variants with
compatible trigger evidence and no resolved role/time conflict.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

from .contracts import (
    CanonicalizationContext,
    CanonicalizationDecision,
    CanonicalizationResult,
)
from .evidence import preserved_evidence_references
from .event_view import EventIdentityView, build_event_identity_views
from ..provenance import PolicyProvenance


EVENT_SPAN_VARIANT_POLICY_ID = "EVENT_SPAN_VARIANT_CANONICALIZATION_V1"


def _strict_containment(left: EventIdentityView, right: EventIdentityView) -> bool:
    left_contains = (
        left.char_start <= right.char_start
        and left.char_end >= right.char_end
        and (left.char_start, left.char_end) != (right.char_start, right.char_end)
    )
    right_contains = (
        right.char_start <= left.char_start
        and right.char_end >= left.char_end
        and (left.char_start, left.char_end) != (right.char_start, right.char_end)
    )
    return left_contains or right_contains


def _span_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return max(left_start, right_start) < min(left_end, right_end)


def _triggers_compatible(left: EventIdentityView, right: EventIdentityView) -> bool:
    return any(
        left_trigger.normalized_text == right_trigger.normalized_text
        or (
            left_trigger.sentence_index == right_trigger.sentence_index
            and (
                (
                    left_trigger.char_start == right_trigger.char_start
                    and left_trigger.char_end == right_trigger.char_end
                )
                or _span_overlap(
                    left_trigger.char_start,
                    left_trigger.char_end,
                    right_trigger.char_start,
                    right_trigger.char_end,
                )
            )
        )
        for left_trigger in left.triggers
        for right_trigger in right.triggers
    )


def evaluate_event_pair(
    left: EventIdentityView, right: EventIdentityView
) -> Mapping[str, Any]:
    """Return one deterministic pair diagnostic and compatibility decision."""

    base = {
        "left_resolved_event_id": left.resolved_event_id,
        "right_resolved_event_id": right.resolved_event_id,
        "left_span": [left.char_start, left.char_end],
        "right_span": [right.char_start, right.char_end],
        "left_text": left.text,
        "right_text": right.text,
        "left_sentence_index": left.sentence_index,
        "right_sentence_index": right.sentence_index,
        "left_trigger_texts": [row.text for row in left.triggers],
        "right_trigger_texts": [row.text for row in right.triggers],
    }
    reason = "ELIGIBLE"
    if left.article_id != right.article_id:
        reason = "DIFFERENT_ARTICLE"
    elif left.sentence_index != right.sentence_index:
        reason = "DIFFERENT_SENTENCE"
    elif (left.char_start, left.char_end) == (right.char_start, right.char_end):
        reason = "EXACT_BOUNDARY_ALREADY_UPSTREAM"
    elif not _strict_containment(left, right):
        reason = (
            "CROSSING_OVERLAP_ONLY"
            if _span_overlap(left.char_start, left.char_end, right.char_start, right.char_end)
            else "NO_CONTAINMENT"
        )
    elif not left.triggers or not right.triggers:
        reason = "MISSING_TRIGGER"
    elif not _triggers_compatible(left, right):
        reason = "DIFFERENT_TRIGGER"
    else:
        for role in ("ACTOR", "TARGET", "PLACE"):
            left_targets = left.role_targets(role)
            right_targets = right.role_targets(role)
            if left_targets and right_targets and left_targets.isdisjoint(right_targets):
                reason = f"{role}_CONFLICT"
                break
        if reason == "ELIGIBLE":
            left_times = left.normalized_times()
            right_times = right.normalized_times()
            if left_times and right_times and left_times != right_times:
                reason = "TIME_CONFLICT"
        if reason == "ELIGIBLE" and (
            left.semantic_score is None
            or left.boundary_score is None
            or right.semantic_score is None
            or right.boundary_score is None
        ):
            reason = "MISSING_V3_SCORE"
    return {**base, "compatible": reason == "ELIGIBLE", "reason": reason}


def representative_sort_key(view: EventIdentityView) -> tuple[Any, ...]:
    """Frozen TOP1 ordering; only actual V3 scores lead the ranking."""

    if view.boundary_score is None or view.semantic_score is None:
        raise ValueError("canonical family representative requires actual V3 scores")
    return (
        -view.boundary_score,
        -view.semantic_score,
        -int(view.has_usable_trigger),
        -view.grounded_support_richness,
        view.span_length,
        view.char_start,
        view.resolved_event_id,
    )


def _non_event_decisions(
    context: CanonicalizationContext,
) -> list[CanonicalizationDecision]:
    state = context.resolved_state
    rows_by_scope = {
        "ENTITY": state.resolved_entities,
        "STATEMENT": state.statements,
        "TIME": state.time_expressions,
    }
    decisions = []
    for scope, rows in rows_by_scope.items():
        for row in rows:
            identity = str(row["node_id"])
            reason = "EVENT-only policy preserves this non-target identity."
            provenance = PolicyProvenance(
                policy_id=EVENT_SPAN_VARIANT_POLICY_ID,
                policy_version="1",
                decision_type="PASS_THROUGH",
                source_ids=(identity,),
                representative_id=identity,
                member_ids=(identity,),
                reason=reason,
                source_stage="CANONICALIZATION",
                derived=False,
                model_generated=False,
            )
            decisions.append(
                CanonicalizationDecision(
                    policy_id=EVENT_SPAN_VARIANT_POLICY_ID,
                    policy_version="1",
                    scope=scope,
                    input_ids=(identity,),
                    output_representative_id=identity,
                    member_ids=(identity,),
                    decision="PASS_THROUGH",
                    reason=reason,
                    preserved_evidence_references=preserved_evidence_references(
                        identity, row
                    ),
                    provenance=provenance,
                )
            )
    return decisions


class EventSpanVariantCanonicalizationPolicy:
    """Complete-link canonicalization of conservative EVENT boundary variants."""

    policy_id = EVENT_SPAN_VARIANT_POLICY_ID
    policy_version = "1"
    target_scopes = ("EVENT",)

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        views = build_event_identity_views(context.resolved_state)
        pair_diagnostics = [
            evaluate_event_pair(left, right) for left, right in combinations(views, 2)
        ]
        compatibility = {
            frozenset(
                (row["left_resolved_event_id"], row["right_resolved_event_id"])
            ): bool(row["compatible"])
            for row in pair_diagnostics
        }

        families: list[list[EventIdentityView]] = []
        for view in views:
            for family in families:
                if all(
                    compatibility.get(
                        frozenset((view.resolved_event_id, member.resolved_event_id)),
                        False,
                    )
                    for member in family
                ):
                    family.append(view)
                    break
            else:
                families.append([view])

        decisions: list[CanonicalizationDecision] = []
        for family in families:
            representative = (
                min(family, key=representative_sort_key)
                if len(family) >= 2
                else family[0]
            )
            members = tuple(sorted(row.resolved_event_id for row in family))
            decision_type = "COLLAPSE" if len(members) >= 2 else "PASS_THROUGH"
            reason = (
                "SPAN_VARIANT_CONTAINMENT_TRIGGER_COMPATIBLE_NO_CONFLICT"
                if decision_type == "COLLAPSE"
                else "NO_COMPATIBLE_SPAN_VARIANT"
            )
            source_prediction_ids = tuple(
                dict.fromkeys(
                    prediction_id
                    for row in family
                    for prediction_id in row.member_event_prediction_ids
                )
            )
            source_eventframe_ids = tuple(
                dict.fromkeys(
                    eventframe_id
                    for row in family
                    for eventframe_id in row.source_eventframe_ids
                )
            )
            evidence_references = tuple(
                dict.fromkeys((*source_prediction_ids, *source_eventframe_ids))
            )
            provenance = PolicyProvenance(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                decision_type=decision_type,
                source_ids=members,
                representative_id=representative.resolved_event_id,
                member_ids=members,
                reason=reason,
                source_stage="DETERMINISTIC_SPAN_VARIANT_CANONICALIZATION",
                derived=decision_type == "COLLAPSE",
                model_generated=False,
            )
            decisions.append(
                CanonicalizationDecision(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    scope="EVENT",
                    input_ids=members,
                    output_representative_id=representative.resolved_event_id,
                    member_ids=members,
                    decision=decision_type,
                    reason=reason,
                    preserved_evidence_references=evidence_references,
                    provenance=provenance,
                    diagnostics=(
                        ("family_size", len(members)),
                        (
                            "representative_ranking",
                            [
                                row.to_dict()
                                for row in (
                                    sorted(family, key=representative_sort_key)
                                    if len(family) >= 2
                                    else family
                                )
                            ],
                        ),
                    ),
                )
            )
        decisions.extend(_non_event_decisions(context))
        return CanonicalizationResult(
            context.resolved_state,
            tuple(decisions),
            tuple(pair_diagnostics),
        )
