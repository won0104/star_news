"""EVENT canonicalization that collapses only proven positive equivalence."""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

from .contracts import CanonicalizationContext, CanonicalizationDecision, CanonicalizationResult
from .equivalence import EquivalenceDecision, EquivalenceEvidence, EventSupportSignature
from .evidence import preserved_evidence_references
from .event_span import _span_overlap, _strict_containment, _triggers_compatible, representative_sort_key
from .event_view import EventIdentityView, TriggerEvidenceView, build_event_identity_views
from .semantic_expansion import RawAcceptedEventEvidence, build_raw_accepted_event_evidence
from ..provenance import PolicyProvenance


EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID = "EVENT_SPAN_EQUIVALENCE_STRICT_V1"


def _trigger_matches_anchor(
    trigger: TriggerEvidenceView, anchors: tuple[TriggerEvidenceView, ...]
) -> bool:
    return any(
        trigger.normalized_text == anchor.normalized_text
        or (
            trigger.sentence_index == anchor.sentence_index
            and _span_overlap(
                trigger.char_start,
                trigger.char_end,
                anchor.char_start,
                anchor.char_end,
            )
        )
        for anchor in anchors
    )


def _anchor_triggers(
    left: EventIdentityView, right: EventIdentityView
) -> tuple[TriggerEvidenceView, ...]:
    values = []
    for left_trigger in left.triggers:
        for right_trigger in right.triggers:
            if (
                left_trigger.normalized_text == right_trigger.normalized_text
                or (
                    left_trigger.sentence_index == right_trigger.sentence_index
                    and _span_overlap(
                        left_trigger.char_start,
                        left_trigger.char_end,
                        right_trigger.char_start,
                        right_trigger.char_end,
                    )
                )
            ):
                values.extend((left_trigger, right_trigger))
    keyed = {
        (
            row.sentence_index,
            row.char_start,
            row.char_end,
            row.normalized_text,
            row.source_eventframe_id,
        ): row
        for row in values
    }
    return tuple(keyed[key] for key in sorted(keyed))


def _small_large(
    left: EventIdentityView, right: EventIdentityView
) -> tuple[EventIdentityView, EventIdentityView]:
    if left.char_start <= right.char_start and left.char_end >= right.char_end:
        return right, left
    return left, right


def _delta_intervals(
    small: EventIdentityView, large: EventIdentityView
) -> tuple[tuple[int, int], ...]:
    values = []
    if large.char_start < small.char_start:
        values.append((large.char_start, small.char_start))
    if small.char_end < large.char_end:
        values.append((small.char_end, large.char_end))
    return tuple(values)


def _inside_delta(event: RawAcceptedEventEvidence, delta: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= event.char_start and event.char_end <= end for start, end in delta)


def _trigger_in_delta(
    event: RawAcceptedEventEvidence,
    delta: tuple[tuple[int, int], ...],
    anchors: tuple[TriggerEvidenceView, ...],
) -> bool:
    return any(
        any(_span_overlap(trigger.char_start, trigger.char_end, start, end) for start, end in delta)
        and not _trigger_matches_anchor(trigger, anchors)
        for trigger in event.triggers
    )


def _anchor_member_ids(
    view: EventIdentityView,
    raw_by_prediction: Mapping[str, RawAcceptedEventEvidence],
    anchors: tuple[TriggerEvidenceView, ...],
) -> tuple[str, ...]:
    values = []
    for prediction_id in view.member_event_prediction_ids:
        event = raw_by_prediction.get(prediction_id)
        if event is None or event.sentence_index != view.sentence_index:
            continue
        compatible_trigger = any(
            _trigger_matches_anchor(trigger, anchors) for trigger in event.triggers
        )
        trigger_grounded_in_event = any(
            event.char_start <= trigger.char_start < trigger.char_end <= event.char_end
            for trigger in event.triggers
            if _trigger_matches_anchor(trigger, anchors)
        )
        relevant_span = _span_overlap(
            event.char_start,
            event.char_end,
            view.char_start,
            view.char_end,
        )
        if compatible_trigger and trigger_grounded_in_event and relevant_span:
            values.append(prediction_id)
    return tuple(sorted(values))


def _shared_support_witnesses(
    left: EventSupportSignature, right: EventSupportSignature
) -> tuple[str, ...]:
    witnesses = []
    ambiguous = set(left.ambiguous_role_ids) | set(right.ambiguous_role_ids)
    left_values = dict(left.semantic_values())
    right_values = dict(right.semantic_values())
    for role in ("ACTOR", "TARGET", "PLACE", "TIME"):
        for value in sorted(
            set(left_values[role]) & set(right_values[role]), key=str
        ):
            if role != "TIME" and value in ambiguous:
                continue
            witnesses.append(f"{role}:{value}")
    return tuple(witnesses)


def evaluate_event_equivalence(
    left: EventIdentityView,
    right: EventIdentityView,
    raw_events: tuple[RawAcceptedEventEvidence, ...],
) -> Mapping[str, Any]:
    """Return a complete proof ledger; KEEP_SEPARATE is the default."""

    left_signature = EventSupportSignature.from_view(left)
    right_signature = EventSupportSignature.from_view(right)
    structural = (
        left.article_id == right.article_id
        and left.sentence_index == right.sentence_index
        and _strict_containment(left, right)
    )
    anchors = _anchor_triggers(left, right) if left.triggers and right.triggers else ()
    anchor_proof = bool(anchors)
    shared_support = _shared_support_witnesses(left_signature, right_signature)
    left_semantic = dict(left_signature.semantic_values())
    right_semantic = dict(right_signature.semantic_values())
    asymmetric_dimensions = tuple(
        role for role in ("ACTOR", "TARGET", "PLACE", "TIME")
        if left_semantic[role] != right_semantic[role]
    )
    ambiguous_role_support = tuple(
        sorted(set(left_signature.ambiguous_role_ids) | set(right_signature.ambiguous_role_ids))
    )
    support_proof = (
        bool(shared_support)
        and not asymmetric_dimensions
        and not ambiguous_role_support
    )
    role_conflicts = tuple(
        role for role in ("ACTOR", "TARGET", "PLACE")
        if left_semantic[role]
        and right_semantic[role]
        and set(left_semantic[role]).isdisjoint(right_semantic[role])
    )
    time_conflict = bool(
        left_semantic["TIME"]
        and right_semantic["TIME"]
        and left_semantic["TIME"] != right_semantic["TIME"]
    )
    conflict_free = not role_conflicts and not time_conflict and bool(
        left.semantic_score is not None
        and left.boundary_score is not None
        and right.semantic_score is not None
        and right.boundary_score is not None
    )

    internal_member_ids = set(left.member_event_prediction_ids) | set(
        right.member_event_prediction_ids
    )
    raw_by_prediction = {row.prediction_id: row for row in raw_events}
    anchor_members = tuple(
        sorted(
            set(_anchor_member_ids(left, raw_by_prediction, anchors))
            | set(_anchor_member_ids(right, raw_by_prediction, anchors))
        )
    )
    small, large = _small_large(left, right)
    delta = _delta_intervals(small, large) if structural else ()
    internal_expansion = set()
    delta_events = set()
    delta_triggers = set()
    for event in raw_events:
        # Without an established shared anchor, "non-anchor" evidence is not
        # defined; the pair remains insufficient rather than being relabeled
        # as semantic expansion.
        if not anchor_proof:
            break
        if event.sentence_index != left.sentence_index:
            continue
        event_in_delta = _inside_delta(event, delta)
        trigger_in_delta = _trigger_in_delta(event, delta, anchors)
        if event.prediction_id in internal_member_ids:
            if event.prediction_id in anchor_members:
                continue
            has_distinct_predicate = any(
                not _trigger_matches_anchor(trigger, anchors) for trigger in event.triggers
            )
            if event_in_delta or trigger_in_delta or has_distinct_predicate:
                internal_expansion.add(event.prediction_id)
            continue
        if trigger_in_delta:
            delta_triggers.add(event.prediction_id)
        if event_in_delta or trigger_in_delta:
            delta_events.add(event.prediction_id)
    delta_silence = not internal_expansion and not delta_events and not delta_triggers

    flags = []
    if left.article_id != right.article_id:
        flags.append("DIFFERENT_ARTICLE")
    elif left.sentence_index != right.sentence_index:
        flags.append("DIFFERENT_SENTENCE")
    elif (left.char_start, left.char_end) == (right.char_start, right.char_end):
        flags.append("EXACT_BOUNDARY_ALREADY_UPSTREAM")
    elif not _strict_containment(left, right):
        flags.append(
            "CROSSING_OVERLAP_ONLY"
            if _span_overlap(left.char_start, left.char_end, right.char_start, right.char_end)
            else "NO_CONTAINMENT"
        )
    if not left.triggers or not right.triggers:
        flags.append("MISSING_TRIGGER")
    elif not _triggers_compatible(left, right):
        flags.append("DIFFERENT_TRIGGER")
    if role_conflicts:
        flags.append("ROLE_CONFLICT")
    if time_conflict:
        flags.append("TIME_CONFLICT")
    if not shared_support:
        flags.append("NO_SHARED_GROUNDED_SUPPORT")
    if ambiguous_role_support:
        flags.append("AMBIGUOUS_ROLE_SUPPORT")
    if asymmetric_dimensions:
        flags.append("ASYMMETRIC_GROUNDED_SUPPORT")
    if internal_expansion:
        flags.append("INTERNAL_MEMBER_PREDICATE_EXPANSION")
    if delta_triggers:
        flags.append("DELTA_TRIGGER_EVIDENCE")
    if delta_events:
        flags.append("DELTA_EVENT_EVIDENCE")
    if not conflict_free and not role_conflicts and not time_conflict:
        flags.append("MISSING_V3_SCORE")

    evidence = EquivalenceEvidence(
        structural_compatibility=structural,
        anchor_predicate_proof=anchor_proof,
        support_equivalence_proof=support_proof,
        delta_silence_proof=delta_silence,
        conflict_free=conflict_free,
        shared_support_witnesses=shared_support,
        anchor_member_prediction_ids=anchor_members,
        internal_member_predicate_witness_ids=tuple(sorted(internal_expansion)),
        delta_event_witness_ids=tuple(sorted(delta_events)),
        delta_trigger_witness_ids=tuple(sorted(delta_triggers)),
        diagnostic_flags=tuple(flags),
        left_support_signature=left_signature,
        right_support_signature=right_signature,
    )
    if evidence.proven:
        decision = EquivalenceDecision("PROVEN_EQUIVALENT", "PROVEN_EQUIVALENT", evidence)
    elif role_conflicts or time_conflict or "DIFFERENT_TRIGGER" in flags:
        primary = next(
            reason for reason in ("DIFFERENT_TRIGGER", "ROLE_CONFLICT", "TIME_CONFLICT")
            if reason in flags
        )
        decision = EquivalenceDecision("SEMANTIC_CONFLICT", primary, evidence)
    elif internal_expansion or delta_events or delta_triggers:
        primary = next(
            reason for reason in (
                "INTERNAL_MEMBER_PREDICATE_EXPANSION",
                "DELTA_TRIGGER_EVIDENCE",
                "DELTA_EVENT_EVIDENCE",
            )
            if reason in flags
        )
        decision = EquivalenceDecision("SEMANTIC_EXPANSION", primary, evidence)
    else:
        primary = next(
            (
                reason for reason in (
                    "DIFFERENT_ARTICLE",
                    "DIFFERENT_SENTENCE",
                    "EXACT_BOUNDARY_ALREADY_UPSTREAM",
                    "CROSSING_OVERLAP_ONLY",
                    "NO_CONTAINMENT",
                    "MISSING_TRIGGER",
                    "AMBIGUOUS_ROLE_SUPPORT",
                    "NO_SHARED_GROUNDED_SUPPORT",
                    "ASYMMETRIC_GROUNDED_SUPPORT",
                    "MISSING_V3_SCORE",
                )
                if reason in flags
            ),
            "INSUFFICIENT_EQUIVALENCE_EVIDENCE",
        )
        decision = EquivalenceDecision("INSUFFICIENT_EVIDENCE", primary, evidence)

    return {
        "left_resolved_event_id": left.resolved_event_id,
        "right_resolved_event_id": right.resolved_event_id,
        "left_span": [left.char_start, left.char_end],
        "right_span": [right.char_start, right.char_end],
        "compatible": decision.proven_equivalent,
        "reason": decision.reason,
        "equivalence": decision.to_dict(),
    }


def _non_event_decisions(context: CanonicalizationContext) -> list[CanonicalizationDecision]:
    decisions = []
    for scope, rows in {
        "ENTITY": context.resolved_state.resolved_entities,
        "STATEMENT": context.resolved_state.statements,
        "TIME": context.resolved_state.time_expressions,
    }.items():
        for row in rows:
            identity = str(row["node_id"])
            reason = "EVENT-only strict equivalence policy preserves this identity."
            provenance = PolicyProvenance(
                policy_id=EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID,
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
                    policy_id=EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID,
                    policy_version="1",
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


class EventSpanEquivalenceStrictPolicy:
    """Complete-link families whose every pair has positive equivalence proof."""

    policy_id = EVENT_SPAN_EQUIVALENCE_STRICT_POLICY_ID
    policy_version = "1"
    target_scopes = ("EVENT",)

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        views = build_event_identity_views(context.resolved_state)
        raw_events = build_raw_accepted_event_evidence(context.resolved_state)
        pair_diagnostics = [
            evaluate_event_equivalence(left, right, raw_events)
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
            prediction_ids = tuple(dict.fromkeys(value for row in family for value in row.member_event_prediction_ids))
            eventframe_ids = tuple(dict.fromkeys(value for row in family for value in row.source_eventframe_ids))
            family_pair_proofs = [
                row["equivalence"] for row in pair_diagnostics
                if row["left_resolved_event_id"] in members and row["right_resolved_event_id"] in members
            ]
            reason = "POSITIVE_EQUIVALENCE_PROVEN_COMPLETE_LINK" if decision_type == "COLLAPSE" else "INSUFFICIENT_POSITIVE_EQUIVALENCE"
            provenance = PolicyProvenance(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                decision_type=decision_type,
                source_ids=members,
                representative_id=representative.resolved_event_id,
                member_ids=members,
                reason=reason,
                source_stage="DETERMINISTIC_POSITIVE_EQUIVALENCE_CANONICALIZATION",
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
                    diagnostics=(
                        ("family_size", len(members)),
                        ("representative_ranking", [row.to_dict() for row in sorted(family, key=representative_sort_key)]),
                        ("positive_equivalence_pair_proofs", family_pair_proofs),
                    ),
                )
            )
        decisions.extend(_non_event_decisions(context))
        return CanonicalizationResult(context.resolved_state, tuple(decisions), tuple(pair_diagnostics))
