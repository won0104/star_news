"""Safety-refined EVENT span-variant policy with semantic-expansion guards."""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

from .contracts import CanonicalizationContext, CanonicalizationDecision, CanonicalizationResult
from .evidence import preserved_evidence_references
from .event_span import _span_overlap, _strict_containment, _triggers_compatible, representative_sort_key
from .event_view import EventIdentityView, build_event_identity_views
from .semantic_expansion import SemanticExpansionGuard
from ..provenance import PolicyProvenance


EVENT_SPAN_VARIANT_POLICY_V2_ID = "EVENT_SPAN_VARIANT_CANONICALIZATION_V2"


def evaluate_event_pair_v2(
    left: EventIdentityView,
    right: EventIdentityView,
    guard: SemanticExpansionGuard,
) -> Mapping[str, Any]:
    """Evaluate one pair using frozen B1 structure plus the B2 safety guard."""

    diagnostic: dict[str, Any] = {
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
        "diagnostic_flags": [],
    }
    reason = "ELIGIBLE_SAFE_SPAN_VARIANT"
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
                reason = "EXPLICIT_ROLE_CONFLICT"
                diagnostic["diagnostic_flags"] = [f"{role}_CONFLICT"]
                diagnostic["conflict_role"] = role
                break
        if reason == "ELIGIBLE_SAFE_SPAN_VARIANT":
            left_times = left.normalized_times()
            right_times = right.normalized_times()
            if left_times and right_times and left_times != right_times:
                reason = "TIME_CONFLICT"
        if reason == "ELIGIBLE_SAFE_SPAN_VARIANT" and (
            left.semantic_score is None
            or left.boundary_score is None
            or right.semantic_score is None
            or right.boundary_score is None
        ):
            reason = "MISSING_V3_SCORE"
        if reason == "ELIGIBLE_SAFE_SPAN_VARIANT":
            expansion = guard.evaluate(left, right)
            diagnostic["semantic_expansion"] = expansion.to_dict()
            diagnostic["diagnostic_flags"] = list(expansion.diagnostic_flags)
            reason = expansion.primary_reason
    return {
        **diagnostic,
        "compatible": reason == "ELIGIBLE_SAFE_SPAN_VARIANT",
        "reason": reason,
    }


def _pass_through_non_events(context: CanonicalizationContext) -> list[CanonicalizationDecision]:
    rows_by_scope = {
        "ENTITY": context.resolved_state.resolved_entities,
        "STATEMENT": context.resolved_state.statements,
        "TIME": context.resolved_state.time_expressions,
    }
    decisions = []
    for scope, rows in rows_by_scope.items():
        for row in rows:
            identity = str(row["node_id"])
            reason = "EVENT-only V2 policy preserves this non-target identity."
            provenance = PolicyProvenance(
                policy_id=EVENT_SPAN_VARIANT_POLICY_V2_ID,
                policy_version="2",
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
                    policy_id=EVENT_SPAN_VARIANT_POLICY_V2_ID,
                    policy_version="2",
                    scope=scope,
                    input_ids=(identity,),
                    output_representative_id=identity,
                    member_ids=(identity,),
                    decision="PASS_THROUGH",
                    reason=reason,
                    preserved_evidence_references=preserved_evidence_references(identity, row),
                    provenance=provenance,
                )
            )
    return decisions


class EventSpanVariantCanonicalizationPolicyV2:
    """Complete-link V2 families guarded against semantic expansion."""

    policy_id = EVENT_SPAN_VARIANT_POLICY_V2_ID
    policy_version = "2"
    target_scopes = ("EVENT",)

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        views = build_event_identity_views(context.resolved_state)
        guard = SemanticExpansionGuard(context.resolved_state)
        pair_diagnostics = [
            evaluate_event_pair_v2(left, right, guard)
            for left, right in combinations(views, 2)
        ]
        compatibility = {
            frozenset((row["left_resolved_event_id"], row["right_resolved_event_id"])): bool(row["compatible"])
            for row in pair_diagnostics
        }

        families: list[list[EventIdentityView]] = []
        for view in views:
            for family in families:
                if all(
                    compatibility.get(frozenset((view.resolved_event_id, member.resolved_event_id)), False)
                    for member in family
                ):
                    family.append(view)
                    break
            else:
                families.append([view])

        decisions = []
        for family in families:
            representative = min(family, key=representative_sort_key) if len(family) >= 2 else family[0]
            members = tuple(sorted(row.resolved_event_id for row in family))
            decision_type = "COLLAPSE" if len(members) >= 2 else "PASS_THROUGH"
            reason = (
                "SAFE_SPAN_VARIANT_SEMANTIC_EXPANSION_GUARD_PASSED"
                if decision_type == "COLLAPSE"
                else "NO_COMPATIBLE_SAFE_SPAN_VARIANT"
            )
            prediction_ids = tuple(
                dict.fromkeys(value for row in family for value in row.member_event_prediction_ids)
            )
            eventframe_ids = tuple(
                dict.fromkeys(value for row in family for value in row.source_eventframe_ids)
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
                    preserved_evidence_references=tuple(dict.fromkeys((*prediction_ids, *eventframe_ids))),
                    provenance=provenance,
                    diagnostics=(("family_size", len(members)), ("representative_ranking", [row.to_dict() for row in sorted(family, key=representative_sort_key)])),
                )
            )
        decisions.extend(_pass_through_non_events(context))
        return CanonicalizationResult(context.resolved_state, tuple(decisions), tuple(pair_diagnostics))
