"""Stage ⑥ article-local Event identity over immutable EventFrame evidence.

The feature builder migrates the current EventFrame contract into the existing
``EventFeatureBundle``. Missing optional upstream evidence is represented by a
zero tensor plus an explicit availability mask; it is never treated as a
semantic mismatch or a prerequisite for an Event MERGE.
"""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from itertools import combinations, islice
import time

import torch

from models.contracts import PairIndexBatch, SPAN_KINDS
from models.events import (
    CURRENT_EVENT_FEATURE_CHANNELS,
    CURRENT_EVENT_OPTIONAL_CHANNELS,
    EventFeatureBundle,
)
from .resolution import (
    DEFAULT_PARTICIPANT_STATE_CHUNK_SIZE,
    encode_candidate_states_bounded,
)
from .event_closure import close_event_identity
from ..temporal_identity import normalized_temporal_key


ROLES = ("ACTOR", "TARGET", "PLACE")
POLICY_FEATURE_SIZE = 12


def _stable_id(prefix: str, *parts: object) -> str:
    material = "\u241f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{sha256(material).hexdigest()[:24]}"


@lru_cache(maxsize=16384)
def _norm(text: str) -> str:
    return "".join(str(text).casefold().split())


@lru_cache(maxsize=16384)
def _ngrams(text: str):
    value = _norm(text)
    if len(value) < 2:
        return {value} if value else set()
    return {value[index : index + 2] for index in range(len(value) - 1)}


def _jaccard(left: str, right: str) -> float:
    a, b = _ngrams(left), _ngrams(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def _align(prepared, start: int, end: int):
    for sentence in prepared.sentences:
        if not (int(sentence["start"]) <= start and end <= int(sentence["end"])):
            continue
        tokens = [
            token
            for token in sentence["tokens"]
            if int(token["end"]) > start and int(token["start"]) < end
        ]
        if tokens:
            return [
                int(sentence["sentence_index"]),
                int(tokens[0]["token_index"]),
                int(tokens[-1]["token_index"]) + 1,
            ]
    return None


def _span(value):
    if value is None:
        return None
    return value.get("span", value)


def _score(value, default: float = 1.0) -> float:
    if value is None:
        return 0.0
    decision = value.get("decision", {})
    for key in ("score", "acceptance_score", "confidence"):
        if value.get(key) is not None:
            return float(value[key])
        if decision.get(key) is not None:
            return float(decision[key])
    return default


def _encode_specs(model, context, backbone, batch, specs):
    if not specs:
        return {}
    rows = [spec[1] for spec in specs]
    kinds = [SPAN_KINDS.index(spec[2]) for spec in specs]
    states = encode_candidate_states_bounded(
        model,
        backbone,
        context,
        batch.source_token_mask,
        rows,
        kinds,
        device=batch.input_ids.device,
        chunk_size=DEFAULT_PARTICIPANT_STATE_CHUNK_SIZE,
    )[0]
    return {spec[0]: states[index].detach() for index, spec in enumerate(specs)}


def _mean(states, hidden, device):
    if not states:
        return torch.zeros(hidden, dtype=torch.float32, device=device)
    return torch.stack(states).mean(0)


@torch.inference_mode()
def _build_legacy_event_feature_bundle(
    prepared,
    backbone,
    *,
    eventframes,
    entity_mentions,
    local_entities,
    time_expressions,
    participant_span_model,
    entity_span_model,
    time_span_model,
    feature_source: str,
):
    """Build a source-ID-aligned current-contract ``EventFeatureBundle``."""

    started = time.perf_counter()
    device = next(participant_span_model.parameters()).device
    batch = prepared.batch.to(device)
    participant_context = participant_span_model.document_context(
        backbone.layer(8),
        batch.source_token_mask,
        batch.sentence_mask,
        batch.sentence_positions,
    )
    entity_context = entity_span_model.encode_context(batch, backbone)
    time_context = time_span_model.encode_context(batch, backbone)

    mention_by_id = {str(row["prediction_id"]): row for row in entity_mentions}
    local_by_id = {str(row["local_entity_id"]): row for row in local_entities}
    time_by_id = {str(row["prediction_id"]): row for row in time_expressions}

    participant_specs = []
    entity_specs = []
    time_specs = []
    per_event = []
    alignment_failures = []
    for event_index, frame in enumerate(eventframes):
        proposition = _span(frame["event"])
        aligned = _align(
            prepared, int(proposition["char_start"]), int(proposition["char_end"])
        )
        if aligned is None:
            alignment_failures.append(
                {"event_id": frame["event"]["prediction_id"], "channel": "proposition"}
            )
            continue
        row = {
            "frame": frame,
            "event_id": str(frame["event"]["prediction_id"]),
            "eventframe_id": str(frame["eventframe_id"]),
            "aligned": aligned,
            "participant_keys": {role: [] for role in ROLES},
            "entity_keys": [],
            "time_keys": [],
            "trigger_key": None,
        }
        proposition_key = (event_index, "proposition", 0)
        participant_specs.append((proposition_key, aligned, "EVENT"))
        row["proposition_key"] = proposition_key

        trigger = _span(frame.get("trigger", {}).get("item"))
        if trigger:
            trigger_aligned = _align(
                prepared, int(trigger["char_start"]), int(trigger["char_end"])
            )
            if trigger_aligned is not None:
                key = (event_index, "trigger", 0)
                participant_specs.append((key, trigger_aligned, "TRIGGER"))
                row["trigger_key"] = key
        for role in ROLES:
            for ordinal, filler in enumerate(
                frame.get("participants", {}).get(role, {}).get("items", ())
            ):
                value = _span(filler)
                filler_aligned = _align(
                    prepared, int(value["char_start"]), int(value["char_end"])
                )
                if filler_aligned is None:
                    continue
                key = (event_index, role, ordinal)
                participant_specs.append((key, filler_aligned, "EVIDENCE"))
                row["participant_keys"][role].append((key, filler))

        resolved_ids = {
            str(item["target_local_entity_id"])
            for item in frame.get("resolution", {}).get("items", ())
            if item.get("resolution_status") == "ENTITY_RESOLVED"
            and item.get("target_local_entity_id")
        }
        entity_ordinal = 0
        for local_id in sorted(resolved_ids):
            local = local_by_id.get(local_id)
            if local is None:
                continue
            for prediction_id in local.get("member_entity_prediction_ids", ()):
                mention = mention_by_id.get(str(prediction_id))
                if mention is None:
                    continue
                mention_aligned = _align(
                    prepared, int(mention["char_start"]), int(mention["char_end"])
                )
                if mention_aligned is None:
                    continue
                key = (event_index, "resolved_entity", entity_ordinal)
                entity_ordinal += 1
                entity_specs.append((key, mention_aligned, "ENTITY"))
                row["entity_keys"].append((key, mention))

        for ordinal, attachment in enumerate(frame.get("time", {}).get("items", ())):
            temporal = time_by_id.get(str(attachment.get("target_time_prediction_id")))
            if temporal is None:
                continue
            temporal_aligned = temporal.get("aligned") or _align(
                prepared, int(temporal["char_start"]), int(temporal["char_end"])
            )
            if temporal_aligned is None:
                continue
            key = (event_index, "time", ordinal)
            time_specs.append((key, temporal_aligned, "TIME"))
            row["time_keys"].append((key, temporal, attachment))
        per_event.append(row)

    participant_states = _encode_specs(
        participant_span_model,
        participant_context,
        backbone,
        batch,
        participant_specs,
    )
    entity_states = _encode_specs(
        entity_span_model, entity_context, backbone, batch, entity_specs
    )
    time_states = _encode_specs(
        time_span_model, time_context, backbone, batch, time_specs
    )
    hidden = int(participant_context.document_state.shape[-1])
    values = {name: [] for name in (
        "semantic", "trigger", "actor", "target", "place", "time",
        "sentence", "document", "resolved",
    )}
    availability = []
    counts = []
    confidence = []
    event_ids = []
    eventframe_ids = []
    event_spans = []
    channel_nonzero = {name: 0 for name in CURRENT_EVENT_FEATURE_CHANNELS}
    for row in per_event:
        frame = row["frame"]
        event_ids.append(row["event_id"])
        eventframe_ids.append(row["eventframe_id"])
        event_spans.append(row["aligned"])
        values["semantic"].append(participant_states[row["proposition_key"]])
        trigger_states = (
            [participant_states[row["trigger_key"]]] if row["trigger_key"] is not None else []
        )
        values["trigger"].append(_mean(trigger_states, hidden, device))
        role_states = {}
        role_counts = {}
        role_confidence = {}
        for role in ROLES:
            members = row["participant_keys"][role]
            role_states[role] = _mean(
                [participant_states[key] for key, _ in members], hidden, device
            )
            role_counts[role] = len(members)
            role_confidence[role] = (
                sum(_score(item) for _, item in members) / len(members) if members else 0.0
            )
            values[role.lower()].append(role_states[role])
        resolved_states = [entity_states[key] for key, _ in row["entity_keys"]]
        values["resolved"].append(_mean(resolved_states, hidden, device))
        temporal_states = [time_states[key] for key, _, _ in row["time_keys"]]
        values["time"].append(_mean(temporal_states, hidden, device))
        sentence_index = row["aligned"][0]
        values["sentence"].append(participant_context.sentence_states[0, sentence_index])
        values["document"].append(participant_context.document_state[0])
        optional_counts = [
            len(trigger_states), role_counts["ACTOR"], role_counts["TARGET"],
            role_counts["PLACE"], len(resolved_states), len(temporal_states),
        ]
        optional_confidence = [
            _score(frame.get("trigger", {}).get("item")),
            role_confidence["ACTOR"], role_confidence["TARGET"], role_confidence["PLACE"],
            max((_score(item) for _, item in row["entity_keys"]), default=0.0),
            max((_score(attachment) for _, _, attachment in row["time_keys"]), default=0.0),
        ]
        mask = [
            True,
            bool(trigger_states),
            bool(role_counts["ACTOR"]),
            bool(role_counts["TARGET"]),
            bool(role_counts["PLACE"]),
            bool(resolved_states),
            bool(temporal_states),
            True,
        ]
        availability.append(mask)
        counts.append(optional_counts)
        confidence.append(optional_confidence)
        for name, present in zip(CURRENT_EVENT_FEATURE_CHANNELS, mask):
            channel_nonzero[name] += int(present)

    count = len(per_event)
    if count:
        stack = lambda name: torch.stack(values[name]).unsqueeze(0)
        role_presence = torch.tensor(
            [[row[1], row[2], row[3], row[6]] for row in availability],
            dtype=torch.bool,
            device=device,
        ).unsqueeze(0)
        event_mask = torch.ones(1, count, dtype=torch.bool, device=device)
        bundle = EventFeatureBundle(
            semantic_span_rep=stack("semantic"),
            trigger_rep=stack("trigger"),
            actor_rep=stack("actor"),
            target_rep=stack("target"),
            place_rep=stack("place"),
            time_rep=stack("time"),
            role_presence_mask=role_presence,
            sentence_context=stack("sentence"),
            document_context=stack("document"),
            event_mask=event_mask,
            feature_source=feature_source,
            resolved_entity_rep=stack("resolved"),
            channel_availability_mask=torch.tensor(
                [availability], dtype=torch.bool, device=device
            ),
            channel_counts=torch.tensor(
                [counts], dtype=torch.float32, device=device
            ).clamp_max(8.0) / 8.0,
            channel_confidence=torch.tensor(
                [confidence], dtype=torch.float32, device=device
            ),
        )
    else:
        empty = torch.zeros(1, 0, hidden, dtype=torch.float32, device=device)
        bundle = EventFeatureBundle(
            empty, empty.clone(), empty.clone(), empty.clone(), empty.clone(),
            empty.clone(), torch.zeros(1, 0, 4, dtype=torch.bool, device=device),
            empty.clone(), empty.clone(),
            torch.zeros(1, 0, dtype=torch.bool, device=device), feature_source,
            empty.clone(),
            torch.zeros(1, 0, 8, dtype=torch.bool, device=device),
            torch.zeros(1, 0, 6, device=device),
            torch.zeros(1, 0, 6, device=device),
        )
    bundle.validate()
    return bundle, event_ids, eventframe_ids, torch.tensor(
        [event_spans], dtype=torch.long, device=device
    ).reshape(1, -1, 3), {
        "event_count": count,
        "alignment_failures": alignment_failures,
        "channel_nonzero_event_count": channel_nonzero,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _member_weighted_entity_representation(local_aggregates, hidden, device):
    """LocalEntity별 member sum/count를 합쳐 원 Entity member 평균을 재현한다."""
    member_count = sum(item.member_count for item in local_aggregates)
    if not member_count:
        return torch.zeros(hidden, dtype=torch.float32, device=device), 0
    return (
        torch.stack([item.member_sum for item in local_aggregates]).sum(0)
        / member_count,
        member_count,
    )


def _compact_role_present(role_handoff, event_id: str, role: str) -> bool:
    aggregate = role_handoff.aggregate(event_id, role)
    return bool(aggregate is not None and aggregate.member_count)


@torch.inference_mode()
def build_current_event_feature_bundle(
    prepared, backbone, *, eventframes, identity_handoff, role_handoff,
    time_expressions, participant_span_model, time_span_model,
    feature_source: str,
):
    """v2.2 compact Entity/role/temporal handoff만으로 현재 EventFeatureBundle을 만든다.

    EventFrame의 canonical Event/Trigger/Time attachment는 읽지만 raw
    EntityMention/B2 filler/RESCUE_ONLY inventory는 feature 입력이 아니다.
    """
    started = time.perf_counter()
    device = next(participant_span_model.parameters()).device
    batch = prepared.batch.to(device)
    participant_context = participant_span_model.document_context(
        backbone.layer(8), batch.source_token_mask,
        batch.sentence_mask, batch.sentence_positions,
    )
    time_context = time_span_model.encode_context(batch, backbone)
    time_by_id = {str(row["prediction_id"]): row for row in time_expressions}
    resolved_ids_by_event = {}
    for fact in identity_handoff.resolved_role_facts:
        resolved_ids_by_event.setdefault(fact["canonical_event_mention_id"], set()).add(
            fact["local_entity_id"]
        )

    participant_specs = []
    time_specs = []
    per_event = []
    alignment_failures = []
    for event_index, frame in enumerate(eventframes):
        proposition = _span(frame["event"])
        aligned = _align(prepared, int(proposition["char_start"]),
                         int(proposition["char_end"]))
        if aligned is None:
            alignment_failures.append({
                "event_id": frame["event"]["prediction_id"], "channel": "proposition",
            })
            continue
        event_id = str(frame["event"]["prediction_id"])
        proposition_key = (event_index, "proposition", 0)
        participant_specs.append((proposition_key, aligned, "EVENT"))
        row = {
            "frame": frame, "event_id": event_id,
            "eventframe_id": str(frame["eventframe_id"]), "aligned": aligned,
            "proposition_key": proposition_key, "trigger_key": None,
            "time_keys": [],
            "resolved_local_ids": tuple(sorted(resolved_ids_by_event.get(event_id, ()))),
        }
        trigger = _span(frame.get("trigger", {}).get("item"))
        if trigger:
            trigger_aligned = _align(
                prepared, int(trigger["char_start"]), int(trigger["char_end"]),
            )
            if trigger_aligned is not None:
                key = (event_index, "trigger", 0)
                participant_specs.append((key, trigger_aligned, "TRIGGER"))
                row["trigger_key"] = key
        for ordinal, attachment in enumerate(frame.get("time", {}).get("items", ())):
            temporal = time_by_id.get(str(attachment.get("target_time_prediction_id")))
            if temporal is None:
                continue
            temporal_aligned = temporal.get("aligned") or _align(
                prepared, int(temporal["char_start"]), int(temporal["char_end"]),
            )
            if temporal_aligned is None:
                continue
            key = (event_index, "time", ordinal)
            time_specs.append((key, temporal_aligned, "TIME"))
            row["time_keys"].append((key, attachment))
        per_event.append(row)

    participant_states = _encode_specs(
        participant_span_model, participant_context, backbone, batch,
        participant_specs,
    )
    time_states = _encode_specs(time_span_model, time_context, backbone, batch,
                                time_specs)
    hidden = int(participant_context.document_state.shape[-1])
    values = {name: [] for name in (
        "semantic", "trigger", "actor", "target", "place", "time",
        "sentence", "document", "resolved",
    )}
    availability, counts, confidence = [], [], []
    event_ids, eventframe_ids, event_spans = [], [], []
    channel_nonzero = {name: 0 for name in CURRENT_EVENT_FEATURE_CHANNELS}
    for row in per_event:
        frame = row["frame"]
        event_id = row["event_id"]
        event_ids.append(event_id)
        eventframe_ids.append(row["eventframe_id"])
        event_spans.append(row["aligned"])
        values["semantic"].append(participant_states[row["proposition_key"]])
        trigger_states = (
            [participant_states[row["trigger_key"]]]
            if row["trigger_key"] is not None else []
        )
        values["trigger"].append(_mean(trigger_states, hidden, device))
        role_counts = {}
        role_confidence = {}
        for role in ROLES:
            aggregate = role_handoff.aggregate(event_id, role)
            role_count = aggregate.member_count if aggregate is not None else 0
            role_counts[role] = role_count
            role_confidence[role] = (
                aggregate.confidence_mean if aggregate is not None else 0.0
            )
            values[role.lower()].append(
                aggregate.representation_sum / role_count
                if role_count and aggregate.representation_sum is not None
                else torch.zeros(hidden, dtype=torch.float32, device=device)
            )
        local_aggregates = [
            identity_handoff.entity_by_local_id[local_id]
            for local_id in row["resolved_local_ids"]
            if local_id in identity_handoff.entity_by_local_id
        ]
        resolved_rep, resolved_count = _member_weighted_entity_representation(
            local_aggregates, hidden, device,
        )
        values["resolved"].append(resolved_rep)
        temporal_states = [time_states[key] for key, _attachment in row["time_keys"]]
        values["time"].append(_mean(temporal_states, hidden, device))
        sentence_index = row["aligned"][0]
        values["sentence"].append(participant_context.sentence_states[0, sentence_index])
        values["document"].append(participant_context.document_state[0])
        optional_counts = [
            len(trigger_states), role_counts["ACTOR"], role_counts["TARGET"],
            role_counts["PLACE"], resolved_count, len(temporal_states),
        ]
        optional_confidence = [
            _score(frame.get("trigger", {}).get("item")),
            role_confidence["ACTOR"], role_confidence["TARGET"],
            role_confidence["PLACE"],
            max((item.max_member_score for item in local_aggregates), default=0.0),
            max((_score(attachment) for _key, attachment in row["time_keys"]),
                default=0.0),
        ]
        mask = [
            True, bool(trigger_states), bool(role_counts["ACTOR"]),
            bool(role_counts["TARGET"]), bool(role_counts["PLACE"]),
            bool(resolved_count), bool(temporal_states), True,
        ]
        availability.append(mask)
        counts.append(optional_counts)
        confidence.append(optional_confidence)
        for name, present in zip(CURRENT_EVENT_FEATURE_CHANNELS, mask):
            channel_nonzero[name] += int(present)

    count = len(per_event)
    if count:
        stack = lambda name: torch.stack(values[name]).unsqueeze(0)
        role_presence = torch.tensor(
            [[row[1], row[2], row[3], row[6]] for row in availability],
            dtype=torch.bool, device=device,
        ).unsqueeze(0)
        bundle = EventFeatureBundle(
            semantic_span_rep=stack("semantic"), trigger_rep=stack("trigger"),
            actor_rep=stack("actor"), target_rep=stack("target"),
            place_rep=stack("place"), time_rep=stack("time"),
            role_presence_mask=role_presence,
            sentence_context=stack("sentence"), document_context=stack("document"),
            event_mask=torch.ones(1, count, dtype=torch.bool, device=device),
            feature_source=feature_source, resolved_entity_rep=stack("resolved"),
            channel_availability_mask=torch.tensor(
                [availability], dtype=torch.bool, device=device,
            ),
            channel_counts=torch.tensor(
                [counts], dtype=torch.float32, device=device,
            ).clamp_max(8.0) / 8.0,
            channel_confidence=torch.tensor(
                [confidence], dtype=torch.float32, device=device,
            ),
        )
    else:
        empty = torch.zeros(1, 0, hidden, dtype=torch.float32, device=device)
        bundle = EventFeatureBundle(
            empty, empty.clone(), empty.clone(), empty.clone(), empty.clone(),
            empty.clone(), torch.zeros(1, 0, 4, dtype=torch.bool, device=device),
            empty.clone(), empty.clone(),
            torch.zeros(1, 0, dtype=torch.bool, device=device), feature_source,
            empty.clone(), torch.zeros(1, 0, 8, dtype=torch.bool, device=device),
            torch.zeros(1, 0, 6, device=device), torch.zeros(1, 0, 6, device=device),
        )
    bundle.validate()
    return bundle, event_ids, eventframe_ids, torch.tensor(
        [event_spans], dtype=torch.long, device=device,
    ).reshape(1, -1, 3), {
        "event_count": count,
        "alignment_failures": alignment_failures,
        "channel_nonzero_event_count": channel_nonzero,
        "feature_carrier": "COMPACT_ENTITY_ROLE_TEMPORAL_HANDOFF_V22_V1",
        "elapsed_seconds": time.perf_counter() - started,
    }


def _sets_for_frame(frame, identity_handoff=None):
    if identity_handoff is not None:
        event_id = str(frame["event"]["prediction_id"])
        roles = identity_handoff.role_feature_sets.get(event_id, {})
        return {role: set(roles.get(role, ())) for role in ROLES}
    roles = {
        role: {
            (
                str(item.get("target_local_entity_id")),
                str(item.get("target_entity_prediction_id")),
            )
            for item in frame.get("resolution", {}).get("items", ())
            if item.get("role") == role and item.get("resolution_status") == "ENTITY_RESOLVED"
        }
        for role in ROLES
    }
    return roles


def _literal_index(texts):
    """같은 bigram 집합을 한 번 보존하고 공통 gram pair만 정확히 비교한다."""
    bags = tuple({frozenset(_ngrams(text)) for text in texts})
    postings = {}
    for index, bag in enumerate(bags):
        for gram in bag:
            postings.setdefault(gram, []).append(index)
    return frozenset(bags), bags, {gram: tuple(ids) for gram, ids in postings.items()}


def _max_literal_jaccard(left_index, right_index):
    left_set, left_bags, _ = left_index
    right_set, right_bags, right_postings = right_index
    if (left_set & right_set) - {frozenset()}:
        return 1.0
    best = 0.0
    for left in left_bags:
        possible = set()
        for gram in left:
            possible.update(right_postings.get(gram, ()))
        for index in possible:
            right = right_bags[index]
            shared = len(left & right)
            score = shared / (len(left) + len(right) - shared)
            if score > best:
                best = score
    # Gram이 겹치지 않은 pair는 기존 Jaccard와 똑같이 0이다.
    return best


def _role_similarity(left, right, role, resolved_left, resolved_right,
                     role_handoff=None, literal_indexes=None):
    if resolved_left[role] & resolved_right[role]:
        return 1.0
    if literal_indexes is not None:
        left_index = literal_indexes[(str(left["event"]["prediction_id"]), role)]
        right_index = literal_indexes[(str(right["event"]["prediction_id"]), role)]
        return _max_literal_jaccard(left_index, right_index)
    if role_handoff is not None:
        left_aggregate = role_handoff.aggregate(str(left["event"]["prediction_id"]), role)
        right_aggregate = role_handoff.aggregate(str(right["event"]["prediction_id"]), role)
        left_texts = left_aggregate.literal_texts if left_aggregate else ()
        right_texts = right_aggregate.literal_texts if right_aggregate else ()
    else:
        left_texts = [item.get("text", "") for item in
                      left.get("participants", {}).get(role, {}).get("items", ())]
        right_texts = [item.get("text", "") for item in
                       right.get("participants", {}).get(role, {}).get("items", ())]
    return _max_literal_jaccard(_literal_index(left_texts),
                                _literal_index(right_texts))


def _normalized_times(frame, time_by_id):
    output = set()
    for item in frame.get("time", {}).get("items", ()):
        temporal = time_by_id.get(str(item.get("target_time_prediction_id")))
        normalized = (temporal or {}).get("normalization", {})
        key = normalized_temporal_key(
            normalized,
            semantic_type=(temporal or {}).get("semantic_type",
                                             (temporal or {}).get("temporal_semantic_type", "POINT")),
        )
        if key is not None:
            output.add(key.parts())
    return output


def event_pair_policy_features(left, right, time_by_id, *,
                               identity_handoff=None, role_handoff=None,
                               literal_indexes=None):
    left_roles = _sets_for_frame(left, identity_handoff)
    right_roles = _sets_for_frame(right, identity_handoff)
    left_times = _normalized_times(left, time_by_id)
    right_times = _normalized_times(right, time_by_id)
    time_same = bool(left_times & right_times)
    time_conflict = bool(left_times and right_times and not time_same)
    left_time_ids = {
        str(item.get("target_time_prediction_id"))
        for item in left.get("time", {}).get("items", ())
        if item.get("target_time_prediction_id")
    }
    right_time_ids = {
        str(item.get("target_time_prediction_id"))
        for item in right.get("time", {}).get("items", ())
        if item.get("target_time_prediction_id")
    }
    raw_time_same = bool(left_time_ids & right_time_ids)
    left_trigger = left.get("trigger", {}).get("item")
    right_trigger = right.get("trigger", {}).get("item")
    left_score = _score(left.get("event"))
    right_score = _score(right.get("event"))
    return [
        _jaccard(left["event"]["text"], right["event"]["text"]),
        float(
            _norm(left["event"]["text"]) in _norm(right["event"]["text"])
            or _norm(right["event"]["text"]) in _norm(left["event"]["text"])
        ),
        _jaccard(
            left_trigger.get("text", "") if left_trigger else "",
            right_trigger.get("text", "") if right_trigger else "",
        ),
        _role_similarity(left, right, "ACTOR", left_roles, right_roles,
                         role_handoff, literal_indexes),
        _role_similarity(left, right, "TARGET", left_roles, right_roles,
                         role_handoff, literal_indexes),
        _role_similarity(left, right, "PLACE", left_roles, right_roles,
                         role_handoff, literal_indexes),
        float(time_conflict),
        float(time_same or raw_time_same),
        min(abs(int(left["event"]["sentence_index"]) - int(right["event"]["sentence_index"])), 32) / 32.0,
        min(left_score, right_score),
        float(bool(left_trigger and right_trigger)),
        float(bool(left_time_ids and right_time_ids)),
    ]


def pack_event_pairs(frames, time_expressions, device, *,
                     identity_handoff=None, role_handoff=None):
    time_by_id = {str(row["prediction_id"]): row for row in time_expressions}
    indices = list(combinations(range(len(frames)), 2))
    features = [event_pair_policy_features(
        frames[a], frames[b], time_by_id,
        identity_handoff=identity_handoff, role_handoff=role_handoff,
    ) for a, b in indices]
    return indices, PairIndexBatch(
        source_indices=torch.tensor([[a for a, _ in indices]], dtype=torch.long, device=device).reshape(1, -1),
        target_indices=torch.tensor([[b for _, b in indices]], dtype=torch.long, device=device).reshape(1, -1),
        mask=torch.ones(1, len(indices), dtype=torch.bool, device=device),
        policy_features=torch.tensor([features], dtype=torch.float32, device=device).reshape(1, len(indices), POLICY_FEATURE_SIZE),
    )


def iter_event_pair_batches(frames, time_expressions, device, *, batch_size,
                            identity_handoff, role_handoff, audit_sink=None,
                            audit_timing=None):
    """기존 article pair 순서/feature를 유지하며 pair tensor만 bounded하게 만든다."""
    if batch_size <= 0:
        raise ValueError("Event pair batch_size must be positive")
    time_by_id = {str(row["prediction_id"]): row for row in time_expressions}
    reusable_started = time.perf_counter() if audit_timing is not None else None
    literal_indexes = None if role_handoff is None else {
        (str(frame["event"]["prediction_id"]), role): _literal_index(
            aggregate.literal_texts if (aggregate := role_handoff.aggregate(
                str(frame["event"]["prediction_id"]), role
            )) is not None else ()
        )
        for frame in frames for role in ROLES
    }
    if audit_timing is not None:
        audit_timing["event_literal_index_preparation_seconds"] = (
            time.perf_counter() - reusable_started
        )
    iterator = combinations(range(len(frames)), 2)
    while (indices := tuple(islice(iterator, batch_size))):
        feature_started = time.perf_counter() if audit_timing is not None else None
        features = [event_pair_policy_features(
            frames[left], frames[right], time_by_id,
            identity_handoff=identity_handoff, role_handoff=role_handoff,
            literal_indexes=literal_indexes,
        ) for left, right in indices]
        if audit_timing is not None:
            audit_timing["pair_policy_feature_construction_seconds"] += (
                time.perf_counter() - feature_started
            )
        if audit_sink is not None:
            audit_sink.capture_pair_features(indices, features)
        packing_started = time.perf_counter() if audit_timing is not None else None
        packed = PairIndexBatch(
            source_indices=torch.tensor(
                [[left for left, _ in indices]], dtype=torch.long, device=device,
            ),
            target_indices=torch.tensor(
                [[right for _, right in indices]], dtype=torch.long, device=device,
            ),
            mask=torch.ones(1, len(indices), dtype=torch.bool, device=device),
            policy_features=torch.tensor(
                [features], dtype=torch.float32, device=device,
            ),
        )
        if audit_timing is not None:
            audit_timing["pair_tensor_packing_seconds"] += (
                time.perf_counter() - packing_started
            )
        yield indices, packed, tuple(feature[6] > 0.5 for feature in features)


def iter_selected_event_pair_batches(signals, selected_indices, device, *,
                                     batch_size, audit_sink=None,
                                     audit_timing=None):
    """Pack exact policy features only for routed fine pairs; never enumerate ALL."""
    from runtime.candidate_routing.event_blocks import prepared_pair_policy_features

    if batch_size <= 0 or len(selected_indices) != len(set(selected_indices)):
        raise ValueError("selected Event fine pair batch contract is invalid")
    if any(not 0 <= left < right < len(signals) for left, right in selected_indices):
        raise ValueError("selected Event pair index is outside aligned Event signals")
    iterator = iter(selected_indices)
    while (indices := tuple(islice(iterator, batch_size))):
        feature_started = time.perf_counter() if audit_timing is not None else None
        features = [prepared_pair_policy_features(signals[left], signals[right])
                    for left, right in indices]
        if audit_timing is not None:
            audit_timing["pair_policy_feature_construction_seconds"] += (
                time.perf_counter() - feature_started
            )
        if audit_sink is not None:
            audit_sink.capture_pair_features(indices, features)
        packing_started = time.perf_counter() if audit_timing is not None else None
        packed = PairIndexBatch(
            source_indices=torch.tensor([[left for left, _ in indices]],
                                        dtype=torch.long, device=device),
            target_indices=torch.tensor([[right for _, right in indices]],
                                        dtype=torch.long, device=device),
            mask=torch.ones(1, len(indices), dtype=torch.bool, device=device),
            policy_features=torch.tensor([features], dtype=torch.float32,
                                         device=device),
        )
        if audit_timing is not None:
            audit_timing["pair_tensor_packing_seconds"] += (
                time.perf_counter() - packing_started
            )
        yield indices, packed, tuple(feature[6] > 0.5 for feature in features)


def _complete_link_clusters(event_ids, scores, conflicts, threshold):
    clusters = [{index} for index in range(len(event_ids))]
    accepted = []
    for score, left, right in sorted(
        ((score, *pair) for pair, score in scores.items() if score >= threshold),
        key=lambda row: (-row[0], event_ids[row[1]], event_ids[row[2]]),
    ):
        li = next(i for i, cluster in enumerate(clusters) if left in cluster)
        ri = next(i for i, cluster in enumerate(clusters) if right in cluster)
        if li == ri:
            continue
        if any(
            tuple(sorted((a, b))) not in scores
            or scores[tuple(sorted((a, b)))] < threshold
            or tuple(sorted((a, b))) in conflicts
            for a in clusters[li]
            for b in clusters[ri]
        ):
            continue
        clusters[li] |= clusters[ri]
        del clusters[ri]
        accepted.append((left, right, score))
    return clusters, accepted


class FixedEventIdentityRuntime:
    """Inference-only symmetric scorer plus safe complete-link clustering."""

    def __init__(self, model, config, checkpoint_sha) -> None:
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha

    @torch.inference_mode()
    def run(
        self,
        prepared,
        backbone,
        eventframes,
        entity_mentions,
        local_entities,
        time_expressions,
        participant_span_model,
        entity_span_model,
        time_span_model,
        *, identity_handoff=None, role_handoff=None, diagnostic_sink=None,
        routing_observer=None,
        event_identity_audit_sink=None,
        event_identity_bounded_policy=None,
        missing_feature_reasons=(),
    ):
        started = time.perf_counter()
        if (identity_handoff is None) != (role_handoff is None):
            raise ValueError("compact Event feature handoffs must be supplied together")
        compact = identity_handoff is not None
        if event_identity_bounded_policy is not None:
            from runtime.candidate_routing.event_policy import EventIdentityBoundedContract
            if not compact or not isinstance(event_identity_bounded_policy,
                                             EventIdentityBoundedContract):
                raise ValueError("Event bounded mode requires compact handoff and frozen contract")
        if compact:
            if entity_mentions or local_entities or any(
                "participants" in frame or "resolution" in frame
                for frame in eventframes
            ):
                raise ValueError("compact Event identity cannot consume raw Entity/B2 inventory")
            if any("text" in row for row in time_expressions):
                raise ValueError("compact Event identity requires stage-6 temporal handoff")
            bundle, event_ids, eventframe_ids, spans, feature_trace = (
                build_current_event_feature_bundle(
                    prepared, backbone, eventframes=eventframes,
                    identity_handoff=identity_handoff, role_handoff=role_handoff,
                    time_expressions=time_expressions,
                    participant_span_model=participant_span_model,
                    time_span_model=time_span_model,
                    feature_source="predicted_cascaded",
                )
            )
        else:
            bundle, event_ids, eventframe_ids, spans, feature_trace = (
                _build_legacy_event_feature_bundle(
                    prepared, backbone, eventframes=eventframes,
                    entity_mentions=entity_mentions, local_entities=local_entities,
                    time_expressions=time_expressions,
                    participant_span_model=participant_span_model,
                    entity_span_model=entity_span_model,
                    time_span_model=time_span_model,
                    feature_source="predicted_cascaded",
                )
            )
        device = next(self.model.parameters()).device
        alignment_failure_ids = set()
        if compact:
            aligned_ids = set(event_ids)
            aligned_frames = [frame for frame in eventframes
                              if str(frame["event"]["prediction_id"]) in aligned_ids]
            if [str(frame["event"]["prediction_id"]) for frame in aligned_frames] != event_ids:
                raise ValueError("compact Event feature order differs from canonical frames")
            unaligned_frames = [frame for frame in eventframes
                                if str(frame["event"]["prediction_id"]) not in aligned_ids]
            alignment_failure_ids = {
                str(frame["event"]["prediction_id"]) for frame in unaligned_frames
            }
            frames = aligned_frames + unaligned_frames
            scored_frame_count = len(aligned_frames)
            event_ids.extend(str(frame["event"]["prediction_id"])
                             for frame in unaligned_frames)
            eventframe_ids.extend(str(frame["eventframe_id"])
                                  for frame in unaligned_frames)
        else:
            frames = list(eventframes)
            scored_frame_count = len(frames)
        audit_timing = None
        if event_identity_audit_sink is not None or event_identity_bounded_policy is not None:
            if not compact:
                raise ValueError("Event pair capture/timing requires compact A+B Event identity")
            audit_timing = {
                "event_signal_preparation_seconds": 0.0,
                "posting_index_seconds": 0.0,
                "multi_channel_seed_retrieval_seconds": 0.0,
                "clique_completion_seconds": 0.0,
                "event_literal_index_preparation_seconds": 0.0,
                "pair_policy_feature_construction_seconds": 0.0,
                "pair_tensor_packing_seconds": 0.0,
                "learned_pair_head_forward_seconds": 0.0,
                "score_materialization_seconds": 0.0,
            }
            if (event_identity_audit_sink is not None
                and event_identity_bounded_policy is None):
                event_identity_audit_sink.capture_events(
                    prepared, frames, time_expressions, identity_handoff,
                    role_handoff, bundle, event_ids, eventframe_ids,
                    scored_frame_count, audit_timing,
                )
        scoring_started = time.perf_counter()
        batch_size = int(self.config.get("pair_batch_size", 4096))
        score_by_pair = {}
        conflicts = set()
        pair_count = 0
        bounded_route_census = None
        if compact:
            if event_identity_bounded_policy is not None:
                from runtime.candidate_routing.event_blocks import prepare_event_signals
                from runtime.candidate_routing.event_monotonic import route_monotonic_events

                signal_started = time.perf_counter()
                signals = prepare_event_signals(
                    frames[:scored_frame_count], time_expressions,
                    identity_handoff=identity_handoff, role_handoff=role_handoff,
                )
                audit_timing["event_signal_preparation_seconds"] = (
                    time.perf_counter() - signal_started
                )
                if [item.event_id for item in signals] != event_ids[:scored_frame_count]:
                    raise ValueError("Event bounded signal/fine feature order mismatch")
                route = route_monotonic_events(
                    signals, event_identity_bounded_policy.router_policy,
                    timing=audit_timing,
                )
                by_id = {event_id: index for index, event_id in enumerate(
                    event_ids[:scored_frame_count])}
                selected_indices = tuple(sorted(
                    tuple(sorted((by_id[left], by_id[right])))
                    for left, right in route.selected_pairs
                ))
                if len(selected_indices) != len(route.selected_pairs):
                    raise ValueError("Event bounded selected pair deduplication failed")
                bounded_route_census = dict(route.census)
                bounded_route_census["multi_channel_seed_pair_count"] = sum(
                    len(grounds) > 1 for grounds in route.provenance.values()
                )
                bounded_route_census["avoided_exact_feature_pair_count"] = (
                    bounded_route_census["full_possible_pair_count"]
                    - len(selected_indices)
                )
                bounded_route_census["ground_unique_seed_pair_count"] = {
                    ground: sum(ground in grounds for grounds in route.provenance.values())
                    for ground in sorted({ground for grounds in route.provenance.values()
                                          for ground in grounds})
                }
                if event_identity_audit_sink is not None:
                    event_identity_audit_sink.capture_bounded_route(
                        event_ids, route, audit_timing,
                    )
                del route, by_id
                iterator = iter_selected_event_pair_batches(
                    signals, selected_indices, device, batch_size=batch_size,
                    audit_sink=event_identity_audit_sink,
                    audit_timing=audit_timing,
                )
            else:
                iterator = iter_event_pair_batches(
                    frames[:scored_frame_count], time_expressions, device,
                    batch_size=batch_size,
                    identity_handoff=identity_handoff, role_handoff=role_handoff,
                    audit_sink=event_identity_audit_sink, audit_timing=audit_timing,
                )
            for indices, sub, conflict_flags in iterator:
                head_started = time.perf_counter() if audit_timing is not None else None
                logits = self.model(bundle, spans, sub).logits[0]
                if audit_timing is not None:
                    audit_timing["learned_pair_head_forward_seconds"] += (
                        time.perf_counter() - head_started
                    )
                material_started = time.perf_counter() if audit_timing is not None else None
                probabilities = torch.softmax(logits, -1)[:, 1].cpu().tolist()
                if audit_timing is not None:
                    audit_timing["score_materialization_seconds"] += (
                        time.perf_counter() - material_started
                    )
                if event_identity_audit_sink is not None:
                    event_identity_audit_sink.capture_pair_scores(indices, probabilities)
                score_by_pair.update(
                    (pair, float(score)) for pair, score in zip(indices, probabilities)
                )
                conflicts.update(pair for pair, flag in zip(indices, conflict_flags) if flag)
                pair_count += len(indices)
                del sub, logits, probabilities
            if event_identity_bounded_policy is not None:
                del signals, selected_indices, iterator
        else:
            pair_indices, pairs = pack_event_pairs(
                frames, time_expressions, device,
                identity_handoff=identity_handoff, role_handoff=role_handoff,
            )
            scores = []
            for offset in range(0, len(pair_indices), batch_size):
                stop = min(len(pair_indices), offset + batch_size)
                sub = PairIndexBatch(
                    pairs.source_indices[:, offset:stop],
                    pairs.target_indices[:, offset:stop],
                    pairs.mask[:, offset:stop],
                    pairs.policy_features[:, offset:stop],
                )
                logits = self.model(bundle, spans, sub).logits[0]
                scores.extend(torch.softmax(logits, -1)[:, 1].cpu().tolist())
            score_by_pair = {pair: float(score)
                             for pair, score in zip(pair_indices, scores)}
            time_by_id = {str(row["prediction_id"]): row for row in time_expressions}
            conflicts = {
                pair for pair in pair_indices
                if event_pair_policy_features(
                    frames[pair[0]], frames[pair[1]], time_by_id,
                    identity_handoff=identity_handoff, role_handoff=role_handoff,
                )[6] > 0.5
            }
            pair_count = len(pair_indices)
            del pairs, scores, pair_indices
        scoring_seconds = time.perf_counter() - scoring_started
        del bundle, spans
        clustering_started = time.perf_counter()
        complete_link_started = time.perf_counter() if audit_timing is not None else None
        clusters, accepted = _complete_link_clusters(
            event_ids, score_by_pair, conflicts, float(self.config["threshold"])
        )
        if audit_timing is not None:
            audit_timing["complete_link_seconds"] = (
                time.perf_counter() - complete_link_started
            )
        local_events = []
        member_cluster = {}
        for cluster in clusters:
            members = sorted(cluster, key=lambda index: event_ids[index])
            local_id = _stable_id(
                "LEVT", prepared.article.article_id, *[event_ids[index] for index in members]
            )
            for index in members:
                member_cluster[index] = local_id
            representative = max(
                members,
                key=lambda index: (
                    _score(frames[index]["event"]),
                    sum(
                        _compact_role_present(role_handoff, event_ids[index], role)
                        if compact else
                        bool(frames[index].get("participants", {}).get(role, {}).get("items"))
                        for role in ROLES
                    )
                    + bool(frames[index].get("trigger", {}).get("item"))
                    + bool(frames[index].get("time", {}).get("items")),
                    len(frames[index]["event"]["text"]),
                    -int(frames[index]["event"]["char_start"]),
                    event_ids[index],
                ),
            )
            internal = [
                score_by_pair[tuple(sorted(pair))]
                for pair in combinations(members, 2)
                if tuple(sorted(pair)) in score_by_pair
            ]
            local_events.append({
                "local_event_id": local_id,
                "article_id": prepared.article.article_id,
                "canonical_text": frames[representative]["event"]["text"],
                "representative_event_prediction_id": event_ids[representative],
                "member_event_prediction_ids": [event_ids[index] for index in members],
                "member_eventframe_ids": [eventframe_ids[index] for index in members],
                "confidence": min(internal) if internal else _score(frames[representative]["event"]),
                "cluster_size": len(members),
                "checkpoint_sha": self.checkpoint_sha,
                "runtime_config_id": self.config["runtime_config_id"],
                "responsibility": "⑥ 동일성 판정부",
                "cross_article": False,
            })
        coreference_rows = [
            {
                "left_event_prediction_id": event_ids[left],
                "right_event_prediction_id": event_ids[right],
                "decision": "MERGE",
                "score": float(score),
                "left_local_event_id": member_cluster[left],
                "right_local_event_id": member_cluster[right],
                "checkpoint_sha": self.checkpoint_sha,
                "responsibility": "⑥ 동일성 판정부",
            }
            for left, right, score in accepted
        ]
        closure = None
        closure_trace = {}
        if compact:
            closure_started = time.perf_counter() if audit_timing is not None else None
            closure, closure_trace = close_event_identity(
                prepared, compact_frames=frames, clusters=clusters,
                score_by_pair=score_by_pair,
                identity_handoff=identity_handoff, role_handoff=role_handoff,
                temporal_rows=time_expressions, diagnostic_sink=diagnostic_sink,
                missing_feature_reasons=missing_feature_reasons,
                alignment_failure_ids=alignment_failure_ids,
            )
            if audit_timing is not None:
                audit_timing["b3_and_compact_closure_seconds"] = (
                    time.perf_counter() - closure_started
                )
        if event_identity_audit_sink is not None:
            if event_identity_bounded_policy is None:
                event_identity_audit_sink.capture_broad_result(
                    event_ids, clusters, accepted, closure_trace, audit_timing,
                    pair_count, len(conflicts), float(self.config["threshold"]),
                    scoring_seconds, feature_trace["elapsed_seconds"],
                )
            else:
                event_identity_audit_sink.capture_bounded_result(
                    event_ids, clusters, accepted, closure_trace, audit_timing,
                    pair_count, len(conflicts), float(self.config["threshold"]),
                    scoring_seconds, feature_trace["elapsed_seconds"],
                )
        if routing_observer is not None and event_identity_bounded_policy is None:
            positive_count = 0
            positive_top = []
            for (left, right), score in score_by_pair.items():
                if score < float(self.config["threshold"]):
                    continue
                positive_count += 1
                positive_top.append((
                    float(score), event_ids[left], event_ids[right],
                    "TIME_CONFLICT" if (left, right) in conflicts else "SCORED_POSITIVE",
                ))
                if len(positive_top) > 16:
                    positive_top.sort(key=lambda row: (-row[0], row[1], row[2]))
                    del positive_top[16:]
            positive_top.sort(key=lambda row: (-row[0], row[1], row[2]))
            routing_observer.observe_reference_scalar("phase_c_census", {
                "lane": "EVENT_IDENTITY",
                "article_version_id": prepared.article.article_version_id,
                "event_count": len(event_ids),
                "possible_pair_count": len(event_ids) * (len(event_ids) - 1) // 2,
                "actually_scored_pair_count": pair_count,
                "positive_score_pair_count": positive_count,
                "time_conflict_pair_count": len(conflicts),
                "positive_pair_witness_top": [
                    {"left_event_id": left, "right_event_id": right,
                     "score": score, "status": status}
                    for score, left, right, status in positive_top
                ],
                "accepted_merge_count": len(accepted),
                "accepted_merge_top": [
                    {"left_event_id": event_ids[left],
                     "right_event_id": event_ids[right], "score": float(score)}
                    for left, right, score in accepted[:16]
                ],
                "cluster_members": [
                    [event_ids[index] for index in sorted(cluster)]
                    for cluster in clusters
                ],
                "alignment_failure_singleton_count": len(alignment_failure_ids),
                "b3_positive_pair_count": closure_trace.get("b3_positive_pair_count", 0),
                "b3_collapsed_family_count": closure_trace.get("b3_collapsed_family_count", 0),
                "complete_pair_score_dump": False,
            })
        conflict_count = len(conflicts)
        input_count = len(frames)
        score_by_pair.clear()  # complete-link/B3/fact 종료 뒤 numeric adjacency 종료.
        conflicts.clear()
        member_cluster.clear()
        frames.clear()
        clustering_seconds = time.perf_counter() - clustering_started
        trace = {
            "stage": "⑥ 동일성 판정부",
            "component": "Event identity/coreference",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": input_count,
            "candidate_count": pair_count,
            "bounded_policy_id": (
                event_identity_bounded_policy.policy_id
                if event_identity_bounded_policy is not None else None
            ),
            "bounded_route_census": bounded_route_census,
            "bounded_timing_breakdown_seconds": (
                dict(audit_timing) if event_identity_bounded_policy is not None else None
            ),
            "output_count": {
                "merge_decisions": len(coreference_rows),
                "local_events": len(local_events),
            },
            "feature_bundle_seconds": feature_trace["elapsed_seconds"],
            "scoring_seconds": scoring_seconds,
            "clustering_seconds": clustering_seconds,
            "time_conflict_block_count": conflict_count,
            "alignment_failure_singleton_count": len(alignment_failure_ids),
            "compact_closure": closure_trace if compact else None,
            "feature_trace": {
                key: value
                for key, value in feature_trace.items()
                if key != "elapsed_seconds" and not key.endswith("_seconds")
            },
            "elapsed_seconds": time.perf_counter() - started,
            "warnings": [
                "Missing optional Event features are availability-masked, not conflicts.",
                "Compact feature carrier excludes raw EntityMention/B2/rescue inventory."
                if compact else "Legacy EventFrame evidence is preserved.",
            ],
        }
        if (event_identity_audit_sink is not None
            and event_identity_bounded_policy is not None):
            event_identity_audit_sink.capture_bounded_trace(trace)
        result = (tuple(local_events), tuple(coreference_rows), trace)
        return (*result, closure) if compact else result
