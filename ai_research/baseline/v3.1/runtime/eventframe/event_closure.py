"""canonical Event coreference 이후의 compact fact/B3 identity closure.

입력은 scorer용 allowlisted EventFrame, 7단계 Entity/role handoff와 6단계
temporal row뿐이다. raw EntityMention/B2/rescue 또는 legacy graph는 읽지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import time
import re
from typing import Any, Mapping

from ..temporal_identity import TemporalIdentityKey, normalized_temporal_key
from .resolved_contracts import (
    EventConflictSummary, EventIdentityClosure, EventSupportSummary,
    GroundedFact, GroundingRef, LocalEventState,
)


ROLES = ("ACTOR", "TARGET", "PLACE")


def _stable_id(prefix: str, *parts: object) -> str:
    material = "␟".join(str(part) for part in parts).encode("utf-8")
    return prefix + "-" + sha256(material).hexdigest()[:24]


def build_compact_eventframes(
    compatibility_frames: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """legacy EventFrame에서 scorer가 소비할 canonical scalar/attachment만 복제한다."""
    compact = []
    for source in compatibility_frames:
        event = source["event"]
        trigger = source.get("trigger", {}).get("item")
        compact.append({
            "eventframe_id": str(source["eventframe_id"]),
            "event": {
                key: event[key] for key in (
                    "prediction_id", "article_id", "sentence_index",
                    "char_start", "char_end", "text",
                    "semantic_score", "boundary_score", "acceptance_score",
                ) if key in event
            },
            "trigger": {"item": ({
                key: trigger[key] for key in (
                    "trigger_prediction_id", "sentence_index", "char_start",
                    "char_end", "text", "score",
                ) if key in trigger
            } if trigger else None)},
            "time": {"items": tuple({
                "target_time_prediction_id": str(row["target_time_prediction_id"]),
                "score": float(row["score"]),
            } for row in source.get("time", {}).get("items", ()))},
        })
    ids = [row["event"]["prediction_id"] for row in compact]
    if len(ids) != len(set(ids)):
        raise ValueError("compact EventFrame requires unique canonical EventMentions")
    return tuple(compact)


def build_compact_eventframes_from_mentions(
    canonical_events, trigger_by_event, time_by_event,
) -> tuple[dict[str, Any], ...]:
    """9단계 direct 경로: raw B2/resolution EventFrame을 만들지 않고 투영한다."""
    source = tuple({
        "eventframe_id": "EFR-" + str(event["prediction_id"]).split("-", 1)[-1],
        "event": event,
        "trigger": {"item": trigger_by_event.get(str(event["prediction_id"]))},
        "time": {"items": time_by_event.get(str(event["prediction_id"]), ())},
    } for event in canonical_events)
    return build_compact_eventframes(source)


def _grounding(prepared, row: Mapping[str, Any]) -> GroundingRef:
    version = prepared.article.article_version_id
    if row.get("article_version_id") not in (None, version):
        raise ValueError("Event closure grounding source version differs")
    start, end = int(row["char_start"]), int(row["char_end"])
    if not 0 <= start < end <= len(prepared.article.content):
        raise ValueError("Event closure grounding offset is out of source")
    if row.get("text") is not None and prepared.article.content[start:end] != row["text"]:
        raise ValueError("Event closure grounding text differs from source")
    return GroundingRef(
        version, start, end,
        int(row["sentence_index"]) if row.get("sentence_index") is not None else None,
    )


def _unique_refs(rows) -> tuple[GroundingRef, ...]:
    return tuple(sorted(set(rows), key=lambda ref: (
        ref.article_version_id, ref.char_start, ref.char_end,
        ref.sentence_index if ref.sentence_index is not None else -1,
    )))


def _anchor_conflict(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    a = left.get("trigger", {}).get("item")
    b = right.get("trigger", {}).get("item")
    if not a or not b:
        return False
    if int(a["sentence_index"]) != int(b["sentence_index"]):
        return False
    overlap = max(int(a["char_start"]), int(b["char_start"])) < min(
        int(a["char_end"]), int(b["char_end"])
    )
    return not overlap  # 같은 문자열이라도 다른 절대 occurrence는 다른 predicate다.


def _modality(text: str) -> tuple[bool, bool, bool]:
    # 4단계 family와 같은 명시적 source 표현만 B3의 보수적 scope witness로 쓴다.
    return (
        bool(re.search(r"않|못|아니|부정", text)),
        bool(re.search(r"가능|가정|예정|전망|수\s+있|할\s+것", text)),
        bool(re.search(r"밝혔|말했|발언|인용|보도|전했", text)),
    )


@dataclass(frozen=True, slots=True)
class _CompactEventWitness:
    event_id: str
    grounding: GroundingRef
    semantic_score: float | None
    boundary_score: float | None
    modality: tuple[bool, bool, bool]
    clause_scope: tuple[int, int]
    quote_scope: tuple[int, int] | None
    trigger: tuple[object, ...]


def _build_witnesses(prepared, frames):
    from runtime.graph.canonicalization.event_view import (
        TriggerEvidenceView, normalize_trigger_text,
    )
    from .mention_consolidation import _source_scopes

    witnesses = {}
    for frame in frames:
        event = frame["event"]
        event_id = str(event["prediction_id"])
        trigger = frame.get("trigger", {}).get("item")
        trigger_views = ()
        if trigger:
            ref = _grounding(prepared, trigger)
            text = prepared.article.content[ref.char_start:ref.char_end]
            trigger_views = (TriggerEvidenceView(
                text, normalize_trigger_text(text), int(trigger["sentence_index"]),
                ref.char_start, ref.char_end, event_id,
            ),)
        witnesses[event_id] = _CompactEventWitness(
            event_id, _grounding(prepared, event),
            float(event["semantic_score"]) if event.get("semantic_score") is not None else None,
            float(event["boundary_score"]) if event.get("boundary_score") is not None else None,
            _modality(str(event["text"])),
            *_source_scopes(
                prepared, int(event["sentence_index"]),
                trigger_views[0].char_start if trigger_views else int(event["char_start"]),
            ),
            trigger_views,
        )
    return witnesses


def _member_conflicts(member_ids, frame_by_id, role_facts_by_event,
                      time_by_id, witnesses):
    role_conflicts = []
    for role in ROLES:
        observed = [
            {str(fact["local_entity_id"])
             for fact in role_facts_by_event.get(event_id, ())
             if fact["role"] == role}
            for event_id in member_ids
        ]
        nonempty = [values for values in observed if values]
        if any(a.isdisjoint(b) for a, b in combinations(nonempty, 2)):
            role_conflicts.append(role)
    normalized = []
    for event_id in member_ids:
        values = set()
        for attachment in frame_by_id[event_id].get("time", {}).get("items", ()):
            temporal = time_by_id.get(str(attachment["target_time_prediction_id"]))
            if temporal is None:
                continue
            key = normalized_temporal_key(
                temporal["normalization"],
                semantic_type=str(temporal.get("semantic_type", "POINT")),
            )
            if key is not None:
                values.add(key)
        if values:
            normalized.append(values)
    time_conflict = any(a.isdisjoint(b) for a, b in combinations(normalized, 2))
    return EventConflictSummary(
        role_conflicts=tuple(role_conflicts),
        time_conflict=time_conflict,
        predicate_conflict=any(
            _anchor_conflict(frame_by_id[a], frame_by_id[b])
            for a, b in combinations(member_ids, 2)
        ),
        modality_conflict=len({witnesses[event_id].modality
                               for event_id in member_ids}) > 1,
    )


def _aggregate_local_event(
    prepared, *, member_ids, representative_id, local_id, identity_confidence,
    confidence_source, frame_by_id, role_facts_by_event, role_handoff,
    time_by_id, witnesses, missing_feature_reasons=(),
) -> LocalEventState:
    event_refs = [_grounding(prepared, frame_by_id[event_id]["event"])
                  for event_id in member_ids]
    representative = _grounding(prepared, frame_by_id[representative_id]["event"])
    conflict = _member_conflicts(
        member_ids, frame_by_id, role_facts_by_event, time_by_id, witnesses,
    )
    unavailable_time_target = any(
        str(attachment["target_time_prediction_id"]) not in time_by_id
        for event_id in member_ids
        for attachment in frame_by_id[event_id].get("time", {}).get("items", ())
    )
    conflict = EventConflictSummary(
        conflict.role_conflicts, conflict.time_conflict,
        conflict.predicate_conflict, conflict.modality_conflict,
        tuple(sorted(set(missing_feature_reasons) | (
            {"TIME_ATTACHMENT_TARGET_UNAVAILABLE"}
            if unavailable_time_target else set()
        ))),
    )
    trigger_refs = _unique_refs(
        _grounding(prepared, frame_by_id[event_id]["trigger"]["item"])
        for event_id in member_ids
        if frame_by_id[event_id].get("trigger", {}).get("item")
    )

    contributions: dict[tuple[str, str], list[tuple[float, tuple[GroundingRef, ...], str]]] = {}
    resolved_filler_refs: dict[tuple[str, str], set[GroundingRef]] = {}
    for event_id in member_ids:
        source_event = _grounding(prepared, frame_by_id[event_id]["event"])
        for fact in role_facts_by_event.get(event_id, ()):
            role, target = str(fact["role"]), str(fact["local_entity_id"])
            refs = [source_event]
            for field in ("filler_groundings", "entity_groundings", "rescue_groundings"):
                refs.extend(_grounding(prepared, row) for row in fact.get(field, ()))
            if fact.get("representative_entity_grounding"):
                refs.append(_grounding(prepared, fact["representative_entity_grounding"]))
            for witness in fact.get("coreference_witnesses", ()):
                refs.extend((_grounding(prepared, witness["left_grounding"]),
                             _grounding(prepared, witness["right_grounding"])))
            refs = _unique_refs(refs)
            contributions.setdefault((role, target), []).append(
                (float(fact["confidence"]), refs, event_id)
            )
            resolved_filler_refs.setdefault((event_id, role), set()).update(
                _grounding(prepared, row) for row in fact.get("filler_groundings", ())
            )

    unresolved_role = []
    if role_handoff is not None:
        for event_id in member_ids:
            for role in ROLES:
                aggregate = role_handoff.aggregate(event_id, role)
                if aggregate is None:
                    continue
                for row in aggregate.groundings:
                    ref = _grounding(prepared, row)
                    if ref not in resolved_filler_refs.get((event_id, role), set()):
                        unresolved_role.append((role, ref))

    normalized_time_keys: dict[str, TemporalIdentityKey] = {}
    unresolved_time = []
    for event_id in member_ids:
        source_event = _grounding(prepared, frame_by_id[event_id]["event"])
        for attachment in frame_by_id[event_id].get("time", {}).get("items", ()):
            temporal = time_by_id.get(str(attachment["target_time_prediction_id"]))
            if temporal is None:
                continue
            target_ref = _grounding(prepared, temporal)
            key = normalized_temporal_key(
                temporal["normalization"],
                semantic_type=str(temporal.get("semantic_type", "POINT")),
            )
            if key is None:
                target = str(temporal["temporal_occurrence_id"])
                status = "UNRESOLVED"
                unresolved_time.append(target_ref)
            else:
                target = _stable_id("LTIME", prepared.article.article_id, *key.parts())
                normalized_time_keys[target] = key
                status = "EXECUTED"
            contributions.setdefault(("OCCURRED_ON", target), []).append(
                (float(attachment["score"]), _unique_refs((source_event, target_ref)), status)
            )

    facts = []
    for (relation, target), values in sorted(contributions.items()):
        status = "EXECUTED"
        if (relation in conflict.role_conflicts
            or (relation == "OCCURRED_ON" and conflict.time_conflict)
            or conflict.predicate_conflict or conflict.modality_conflict
            or any(value[2] == "UNRESOLVED" for value in values)):
            status = "UNRESOLVED"
        supports = _unique_refs(ref for _score, refs, _source in values for ref in refs)
        facts.append(GroundedFact(
            _stable_id("EFACT", local_id, relation, target), relation,
            local_id, target, supports,
            max(value[0] for value in values), status,
        ))

    # boundary family variants는 입력에 없으며 동일 source/anchor는 하나의 support다.
    independent_occurrences = {
        (ref.article_version_id, ref.char_start, ref.char_end,
         tuple((row.char_start, row.char_end)
               for row in witnesses[event_id].trigger))
        for event_id, ref in zip(member_ids, event_refs)
    }
    all_fact_refs = _unique_refs(
        ref for fact in facts for ref in fact.supports
    )
    summary = EventSupportSummary(
        len(all_fact_refs),
        tuple(sorted(set(unresolved_role), key=lambda row: (
            row[0], row[1].article_version_id, row[1].char_start,
            row[1].char_end,
        ))),
        _unique_refs(unresolved_time),
        tuple(sorted(normalized_time_keys.items(), key=lambda row: row[0])),
    )
    return LocalEventState(
        local_id, str(frame_by_id[representative_id]["event"]["text"]),
        representative, trigger_refs, tuple(facts),
        float(identity_confidence), confidence_source,
        len(independent_occurrences), conflict, summary,
    )


def _b3_view(prepared, entry, witnesses):
    from runtime.graph.canonicalization.event_view import (
        EventIdentityView, NormalizedTimeSupport, ResolvedRoleSupport,
    )

    state = entry["state"]
    representative = witnesses[entry["representative_id"]]
    triggers = tuple(
        trigger for event_id in entry["member_ids"]
        for trigger in witnesses[event_id].trigger
    )
    key_by_time_id = dict(state.support_summary.normalized_time_keys)
    role_support = tuple(
        ResolvedRoleSupport(fact.relation, fact.target_identity_id, (fact.fact_id,))
        for fact in state.facts if fact.relation in ROLES
    )
    time_support = tuple(
        NormalizedTimeSupport(
            fact.target_identity_id,
            "|".join((key.value, key.semantic_type, key.timezone or "")),
            key.granularity, (fact.fact_id,),
        )
        for fact in state.facts if fact.relation == "OCCURRED_ON"
        for key in (key_by_time_id.get(fact.target_identity_id),)
        if key is not None
    )
    return EventIdentityView(
        prepared.article.article_id, state.event_id,
        representative.event_id, tuple(entry["member_ids"]), (), (),
        representative.grounding.sentence_index or 0,
        representative.grounding.char_start, representative.grounding.char_end,
        state.canonical_text, representative.semantic_score,
        representative.boundary_score, "CANONICAL_V3", "CANONICAL_V3",
        triggers, role_support, time_support, len(entry["member_ids"]),
    )


def _strict_b3_families(prepared, entries, witnesses, diagnostic_sink):
    from runtime.graph.canonicalization.event_equivalence_strict import (
        evaluate_event_equivalence,
    )
    from runtime.graph.canonicalization.semantic_expansion import (
        RawAcceptedEventEvidence,
    )

    raw_compact = tuple(
        RawAcceptedEventEvidence(
            row.event_id, row.grounding.sentence_index or 0,
            row.grounding.char_start, row.grounding.char_end, row.trigger,
        )
        for row in sorted(witnesses.values(), key=lambda row: row.event_id)
    )
    views = [_b3_view(prepared, entry, witnesses) for entry in entries]
    compatibility = {}
    proven = 0
    for left, right in combinations(range(len(entries)), 2):
        result = evaluate_event_equivalence(views[left], views[right], raw_compact)
        compatible = bool(result["compatible"])
        left_scope = {(witnesses[event_id].modality,
                       witnesses[event_id].clause_scope,
                       witnesses[event_id].quote_scope)
                      for event_id in entries[left]["member_ids"]}
        right_scope = {(witnesses[event_id].modality,
                        witnesses[event_id].clause_scope,
                        witnesses[event_id].quote_scope)
                       for event_id in entries[right]["member_ids"]}
        anchors_overlap = any(
            a.sentence_index == b.sentence_index
            and max(a.char_start, b.char_start) < min(a.char_end, b.char_end)
            for a in views[left].triggers for b in views[right].triggers
        )
        if compatible and (left_scope != right_scope or not anchors_overlap
                           or not entries[left]["state"].conflict_summary.conflict_free
                           or not entries[right]["state"].conflict_summary.conflict_free
                           or "EVENT_ALIGNMENT_FAILURE" in entries[left]["state"].conflict_summary.missing_feature_reasons
                           or "EVENT_ALIGNMENT_FAILURE" in entries[right]["state"].conflict_summary.missing_feature_reasons):
            compatible = False
            result = {**result, "compatible": False, "reason": (
                "DISTINCT_PREDICATE_OCCURRENCE" if not anchors_overlap
                else "EVENT_ALIGNMENT_FAILURE"
                if ("EVENT_ALIGNMENT_FAILURE" in entries[left]["state"].conflict_summary.missing_feature_reasons
                    or "EVENT_ALIGNMENT_FAILURE" in entries[right]["state"].conflict_summary.missing_feature_reasons)
                else "COMPACT_SCOPE_CONFLICT"
            )}
        compatibility[(left, right)] = compatible
        proven += int(compatible)
        if diagnostic_sink is not None:
            diagnostic_sink.record("decision", {
                "component": "b3_compact_event_equivalence",
                "left_local_event_id": entries[left]["state"].event_id,
                "right_local_event_id": entries[right]["state"].event_id,
                "compatible": compatible, "reason": result["reason"],
                "equivalence_axes": {
                    key: result["equivalence"]["evidence"][key]
                    for key in (
                        "structural_compatibility", "anchor_predicate_proof",
                        "support_equivalence_proof", "delta_silence_proof",
                        "conflict_free",
                    )
                },
            })
    families = []
    for index in range(len(entries)):
        for family in families:
            if all(compatibility.get(tuple(sorted((index, other))), False)
                   for other in family):
                family.append(index)
                break
        else:
            families.append([index])
    return families, proven


def close_event_identity(
    prepared, *, compact_frames, clusters, score_by_pair,
    identity_handoff, role_handoff, temporal_rows,
    diagnostic_sink=None, failure_reason=None, missing_feature_reasons=(),
    alignment_failure_ids=(),
) -> tuple[EventIdentityClosure, dict[str, int]]:
    """learned clusters → 모든 member fact → B3 positive equivalence → final state."""
    frame_by_id = {str(row["event"]["prediction_id"]): row for row in compact_frames}
    frames = tuple(compact_frames)
    event_ids = [str(row["event"]["prediction_id"]) for row in frames]
    if len(event_ids) != len(frame_by_id):
        raise ValueError("duplicate compact Event identity input")
    time_by_id = {str(row["prediction_id"]): row for row in temporal_rows}
    role_facts_by_event = {}
    for fact in identity_handoff.resolved_role_facts:
        role_facts_by_event.setdefault(str(fact["canonical_event_mention_id"]), []).append(fact)
    witnesses = _build_witnesses(prepared, frames)

    entries = []
    for cluster in clusters:
        member_ids = tuple(sorted(event_ids[index] for index in cluster))
        representative_id = max(member_ids, key=lambda event_id: (
            float(frame_by_id[event_id]["event"].get("acceptance_score", 0.0)),
            sum(bool(role_handoff.aggregate(event_id, role)
                     and role_handoff.aggregate(event_id, role).member_count)
                for role in ROLES)
            + bool(frame_by_id[event_id]["trigger"]["item"])
            + bool(frame_by_id[event_id]["time"]["items"]),
            len(frame_by_id[event_id]["event"]["text"]),
            -int(frame_by_id[event_id]["event"]["char_start"]), event_id,
        ))
        internal = [
            score_by_pair[tuple(sorted((a, b)))]
            for a, b in combinations(sorted(cluster), 2)
            if tuple(sorted((a, b))) in score_by_pair
        ]
        confidence = (
            min(internal) if internal else
            float(frame_by_id[representative_id]["event"].get("acceptance_score", 1.0))
        )
        local_id = _stable_id("LEVT", prepared.article.article_id, *member_ids)
        entry = {
            "member_ids": member_ids, "representative_id": representative_id,
            "confidence": confidence,
            "state": _aggregate_local_event(
                prepared, member_ids=member_ids,
                representative_id=representative_id, local_id=local_id,
                identity_confidence=confidence,
                confidence_source=(
                    "LEARNED_COMPLETE_LINK_MIN_PAIR_SCORE" if internal
                    else "CANONICAL_V3_ACCEPTANCE_SCORE"
                ),
                frame_by_id=frame_by_id,
                role_facts_by_event=role_facts_by_event,
                role_handoff=role_handoff, time_by_id=time_by_id,
                witnesses=witnesses,
                missing_feature_reasons=(
                    *missing_feature_reasons,
                    *((failure_reason,) if failure_reason else ()),
                    *(("EVENT_ALIGNMENT_FAILURE",)
                      if any(event_id in alignment_failure_ids
                             for event_id in member_ids) else ()),
                ),
            ),
        }
        entries.append(entry)
    entries.sort(key=lambda row: (
        row["state"].representative.sentence_index or 0,
        row["state"].representative.char_start,
        row["state"].representative.char_end, row["state"].event_id,
    ))
    b3_started = time.perf_counter()
    if failure_reason:
        families, b3_proven = [[index] for index in range(len(entries))], 0
    else:
        families, b3_proven = _strict_b3_families(
            prepared, entries, witnesses, diagnostic_sink,
        )
    b3_seconds = time.perf_counter() - b3_started
    b3_evaluated_pair_count = (
        0 if failure_reason else len(entries) * (len(entries) - 1) // 2
    )

    final_states = []
    identity_remap = {}
    b3_collapses = 0
    for family in families:
        members = tuple(sorted({
            event_id for index in family for event_id in entries[index]["member_ids"]
        }))
        if len(family) > 1:
            from runtime.graph.canonicalization.event_span import representative_sort_key
            representative_entry = min(
                (entries[index] for index in family),
                key=lambda row: representative_sort_key(
                    _b3_view(prepared, row, witnesses)
                ),
            )
        else:
            representative_entry = entries[family[0]]
        representative_id = representative_entry["representative_id"]
        local_id = _stable_id("LEVT", prepared.article.article_id, *members)
        confidence = min(entries[index]["confidence"] for index in family)
        state = _aggregate_local_event(
            prepared, member_ids=members, representative_id=representative_id,
            local_id=local_id, identity_confidence=confidence,
            confidence_source=(
                "B3_PROVEN_EQUIVALENCE_MIN_LEARNED_LOCAL_CONFIDENCE"
                if len(family) > 1 else
                representative_entry["state"].identity_confidence_source
            ),
            frame_by_id=frame_by_id, role_facts_by_event=role_facts_by_event,
            role_handoff=role_handoff, time_by_id=time_by_id,
            witnesses=witnesses,
            missing_feature_reasons=(
                *missing_feature_reasons,
                *((failure_reason,) if failure_reason else ()),
                *(("EVENT_ALIGNMENT_FAILURE",)
                  if any(event_id in alignment_failure_ids
                         for event_id in members) else ()),
            ),
        )
        final_states.append(state)
        identity_remap.update({event_id: local_id for event_id in members})
        b3_collapses += int(len(family) > 1)
        if diagnostic_sink is not None:
            diagnostic_sink.record("decision", {
                "component": "event_identity_closure",
                "local_event_id": local_id,
                "representative_event_prediction_id": representative_id,
                "member_event_prediction_ids": members,
                "identity_confidence": confidence,
                "independent_support_count": state.independent_support_count,
                "fact_count": len(state.facts),
                "b3_positive_family_size": len(family),
                "failure_reason": failure_reason,
            })
    # B3 witness와 member maps는 final LocalEventState에 들어가지 않는다.
    witnesses.clear()
    frame_by_id.clear()
    time_by_id.clear()
    role_facts_by_event.clear()
    return EventIdentityClosure(
        tuple(final_states), identity_remap, failure_reason,
    ), {
        "canonical_event_count": len(event_ids),
        "learned_local_event_count": len(entries),
        "b3_positive_pair_count": b3_proven,
        "b3_evaluated_pair_count": b3_evaluated_pair_count,
        "b3_seconds": b3_seconds,
        "b3_collapsed_family_count": b3_collapses,
        "final_local_event_count": len(final_states),
        "aggregated_fact_count": sum(len(row.facts) for row in final_states),
    }


def canonical_partial_event_closure(prepared, compact_frames, reason: str):
    """optional/identity 오류 때 valid canonical Event만 최소 상태로 보존한다."""
    states = []
    remap = {}
    for frame in compact_frames:
        event = frame["event"]
        event_id = str(event["prediction_id"])
        local_id = _stable_id("LEVT", prepared.article.article_id, event_id)
        representative = _grounding(prepared, event)
        trigger = frame.get("trigger", {}).get("item")
        trigger_refs = (_grounding(prepared, trigger),) if trigger else ()
        states.append(LocalEventState(
            local_id, str(event["text"]), representative, trigger_refs, (),
            float(event.get("acceptance_score", 0.0)),
            "CANONICAL_PARTIAL_NO_IDENTITY_SCORE", 1,
            EventConflictSummary(missing_feature_reasons=(reason,)),
            EventSupportSummary(0),
        ))
        remap[event_id] = local_id
    return EventIdentityClosure(tuple(states), remap, reason)
