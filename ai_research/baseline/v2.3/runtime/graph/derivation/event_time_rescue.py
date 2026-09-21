"""Positive-proof projection and conservative Event-to-Time rescue."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any, Mapping

from .contracts import (
    DerivationContext,
    DerivationDecision,
    DerivationResult,
    DerivedFact,
)
from ..provenance import PolicyProvenance


EVENT_TIME_RESCUE_POLICY_ID = "EVENT_TIME_RESCUE_V1"


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\u241f".join(parts).encode("utf-8")
    return f"{prefix}-{sha256(material).hexdigest()[:24]}"


def _event_prediction_to_canonical(context: DerivationContext) -> dict[str, str]:
    state = context.canonical_state.resolved_state
    graph = state.source_graph
    member_to_local = {
        str(edge["source_id"]): str(edge["target_id"])
        for edge in graph.get("edges", ())
        if edge.get("edge_type") == "MEMBER_OF_EVENT"
    }
    values = {}
    for node in graph.get("nodes", ()):
        if node.get("kind") != "EVENT":
            continue
        prediction_id = node.get("properties", {}).get("source_prediction_id")
        if not prediction_id:
            continue
        frame_id = str(node["node_id"])
        resolved_id = member_to_local.get(frame_id, frame_id)
        values[str(prediction_id)] = context.canonical_state.identity_index.representative_for(
            "EVENT", resolved_id
        )
    return values


def _canonical_event_evidence(context: DerivationContext) -> dict[str, tuple[Mapping[str, Any], ...]]:
    state = context.canonical_state.resolved_state
    by_id = {str(row["node_id"]): row for row in state.resolved_events}
    values = {}
    for representative, members in context.canonical_state.identity_index.groups("EVENT"):
        evidence = []
        for member in members:
            evidence.extend(by_id[member].get("evidence", ()))
        values[representative] = tuple(evidence)
    return values


def _normalization_facts(context: DerivationContext) -> tuple[DerivedFact, ...]:
    return tuple(
        fact for fact in context.prior_facts if fact.derived_kind == "TIME_NORMALIZATION"
    )


class EventTimeRescuePolicy:
    """Materialize learned attachments and add only unique contained-time rescues."""

    policy_id = EVENT_TIME_RESCUE_POLICY_ID
    policy_version = "1"

    def apply(self, context: DerivationContext) -> DerivationResult:
        state = context.canonical_state.resolved_state
        article_id = str(state.article["article_id"])
        event_by_prediction = _event_prediction_to_canonical(context)
        event_evidence = _canonical_event_evidence(context)
        normalizations = _normalization_facts(context)
        normalization_by_prediction = {
            str(fact.value["source_time_prediction_id"]): fact
            for fact in normalizations
        }
        raw_attachments = state.unmaterialized_evidence.get("event_time_attachments", ())
        learned_by_event = defaultdict(list)
        learned_pairs = set()
        facts = []
        decisions = []

        for attachment in raw_attachments if isinstance(raw_attachments, (tuple, list)) else ():
            event_id = event_by_prediction.get(str(attachment.get("source_event_prediction_id")))
            normalization = normalization_by_prediction.get(
                str(attachment.get("target_time_prediction_id"))
            )
            if event_id is None or normalization is None:
                continue
            time_id = str(normalization.value["canonical_time_identity_id"])
            learned_pairs.add((event_id, time_id))
            learned_by_event[event_id].append(normalization)
            source_ids = (
                event_id,
                str(normalization.value["source_time_prediction_id"]),
                str(attachment.get("attachment_id", "")),
            )
            provenance = PolicyProvenance(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                decision_type="DERIVED",
                source_ids=source_ids,
                representative_id=None,
                member_ids=(),
                reason="LEARNED_ATTACHMENT_WITH_V2_NORMALIZATION",
                source_stage="DETERMINISTIC_DERIVATION",
                derived=True,
                model_generated=False,
            )
            facts.append(
                DerivedFact(
                    derived_kind="LEARNED_EVENT_TIME_MATERIALIZATION",
                    source_ids=source_ids,
                    value={
                        "fact_id": _stable_id("DFACT", *source_ids),
                        "article_id": article_id,
                        "source_event_identity_id": event_id,
                        "target_time_identity_id": time_id,
                        "normalized_value": normalization.value["normalized_value"],
                        "granularity": normalization.value["granularity"],
                        "temporal_semantic_type": normalization.value.get("temporal_semantic_type", "POINT"),
                        "timezone": normalization.value.get("timezone"),
                        "source_time_prediction_id": normalization.value[
                            "source_time_prediction_id"
                        ],
                        "source_attachment_id": attachment.get("attachment_id"),
                        "confidence": float(attachment.get("score", 1.0)),
                        "source_evidence": normalization.value["source_evidence"],
                        "proof_type": "LEARNED_EVENT_TIME_ATTACHMENT",
                        "source_attachment": dict(attachment),
                    },
                    provenance=provenance,
                )
            )
            decisions.append(
                DerivationDecision(
                    self.policy_id,
                    self.policy_version,
                    source_ids,
                    "LEARNED_EVENT_TIME_MATERIALIZATION",
                    "DERIVED",
                    "LEARNED_ATTACHMENT_WITH_V2_NORMALIZATION",
                    provenance,
                )
            )

        candidate_events = defaultdict(list)
        for fact in normalizations:
            evidence = fact.value["source_evidence"]
            for event_id, spans in event_evidence.items():
                if any(
                    int(span["sentence_index"]) == int(evidence["sentence_index"])
                    and int(span["char_start"]) <= int(evidence["char_start"])
                    and int(evidence["char_end"]) <= int(span["char_end"])
                    for span in spans
                ):
                    candidate_events[str(fact.value["source_time_prediction_id"])].append(event_id)

        facts_by_event = defaultdict(list)
        for fact in normalizations:
            prediction_id = str(fact.value["source_time_prediction_id"])
            matched = sorted(set(candidate_events[prediction_id]))
            if len(matched) == 1:
                facts_by_event[matched[0]].append(fact)

        for fact in normalizations:
            prediction_id = str(fact.value["source_time_prediction_id"])
            time_id = str(fact.value["canonical_time_identity_id"])
            matched = sorted(set(candidate_events[prediction_id]))
            reason = None
            event_id = matched[0] if len(matched) == 1 else None
            if not matched:
                reason = "TIME_NOT_CONTAINED_IN_EVENT_EVIDENCE"
            elif len(matched) > 1:
                reason = "TIME_AMBIGUOUS_ACROSS_CANONICAL_EVENTS"
            elif (event_id, time_id) in learned_pairs:
                reason = "LEARNED_ATTACHMENT_ALREADY_EXISTS"
            else:
                # identity ID가 value·granularity·semantic type·timezone을 포함한다.
                competing = {
                    str(row.value["canonical_time_identity_id"])
                    for row in facts_by_event[event_id]
                }
                learned_values = {
                    str(row.value["target_time_identity_id"])
                    for row in learned_by_event[event_id]
                }
                current = time_id
                if len(competing) != 1:
                    reason = "COMPETING_NORMALIZED_TIME_VALUES_IN_EVENT"
                elif learned_values and learned_values != {current}:
                    reason = "CONFLICTING_LEARNED_ATTACHMENT"
            source_ids = (event_id or "UNRESOLVED_EVENT", prediction_id)
            if reason is None:
                reason = "UNIQUE_CONTAINED_NORMALIZED_TIME"
                provenance = PolicyProvenance(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    decision_type="DERIVED",
                    source_ids=source_ids,
                    representative_id=None,
                    member_ids=(),
                    reason=reason,
                    source_stage="DETERMINISTIC_DERIVATION",
                    derived=True,
                    model_generated=False,
                )
                facts.append(
                    DerivedFact(
                        derived_kind="EVENT_TIME_RESCUE",
                        source_ids=source_ids,
                        value={
                            "fact_id": _stable_id("DFACT", self.policy_id, *source_ids),
                            "article_id": article_id,
                            "source_event_identity_id": event_id,
                            "target_time_identity_id": time_id,
                            "normalized_value": fact.value["normalized_value"],
                            "granularity": fact.value["granularity"],
                            "source_time_prediction_id": prediction_id,
                            "confidence": 1.0,
                            "source_evidence": fact.value["source_evidence"],
                            "proof_type": "UNIQUE_TIME_FULLY_CONTAINED_IN_ONE_CANONICAL_EVENT",
                            "competing_event_ids": matched,
                            "competing_time_value_count": 1,
                            "learned_attachment_already_existed": False,
                        },
                        provenance=provenance,
                    )
                )
                decision_type = "DERIVED"
            else:
                provenance = PolicyProvenance(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    decision_type="NOT_DERIVED",
                    source_ids=source_ids,
                    representative_id=None,
                    member_ids=(),
                    reason=reason,
                    source_stage="DETERMINISTIC_DERIVATION",
                    derived=False,
                    model_generated=False,
                )
                decision_type = "NOT_DERIVED"
            decisions.append(
                DerivationDecision(
                    self.policy_id,
                    self.policy_version,
                    source_ids,
                    "EVENT_TIME_RESCUE",
                    decision_type,
                    reason,
                    provenance,
                    diagnostics=(
                        ("candidate_event_ids", tuple(matched)),
                        ("time_identity_id", time_id),
                    ),
                )
            )
        return DerivationResult(context.canonical_state, tuple(facts), tuple(decisions))
