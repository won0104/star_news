"""Gold-free structural guard against semantic expansion across EVENT spans.

The guard consumes only immutable runtime predictions and resolved support.  It
does not score, tune, or infer identity; it conservatively rejects containment
pairs whose larger span carries additional grounded or predicate evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .event_view import EventIdentityView, TriggerEvidenceView, normalize_trigger_text
from ..assembly_input import ResolvedAssemblyState


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


@dataclass(frozen=True, slots=True)
class RawAcceptedEventEvidence:
    prediction_id: str
    sentence_index: int
    char_start: int
    char_end: int
    triggers: tuple[TriggerEvidenceView, ...]


@dataclass(frozen=True, slots=True)
class SemanticExpansionDecision:
    safe_variant: bool
    primary_reason: str
    diagnostic_flags: tuple[str, ...]
    small_resolved_event_id: str
    large_resolved_event_id: str
    delta_intervals: tuple[tuple[int, int], ...]
    large_only_support: tuple[tuple[str, tuple[Any, ...]], ...]
    small_only_support: tuple[tuple[str, tuple[Any, ...]], ...]
    delta_trigger_prediction_ids: tuple[str, ...]
    delta_event_prediction_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["large_only_support"] = dict(self.large_only_support)
        payload["small_only_support"] = dict(self.small_only_support)
        return payload


def _trigger_from_mapping(
    value: Mapping[str, Any] | None,
    *,
    default_sentence: int,
    source_eventframe_id: str,
) -> TriggerEvidenceView | None:
    if not value or value.get("char_start") is None or value.get("char_end") is None:
        return None
    text = str(value.get("text", ""))
    if not text:
        return None
    return TriggerEvidenceView(
        text=text,
        normalized_text=normalize_trigger_text(text),
        sentence_index=int(value.get("sentence_index", default_sentence)),
        char_start=int(value["char_start"]),
        char_end=int(value["char_end"]),
        source_eventframe_id=source_eventframe_id,
    )


def build_raw_accepted_event_evidence(
    state: ResolvedAssemblyState,
) -> tuple[RawAcceptedEventEvidence, ...]:
    """Index accepted raw EVENT and trigger offsets without Gold or score fallback."""

    nodes = {str(row["node_id"]): row for row in state.source_graph.get("nodes", ())}
    rows = []
    for frame in state.source_graph.get("eventframes", ()):
        event = frame.get("event", {})
        if event.get("prediction_id") is None or event.get("char_start") is None:
            continue
        frame_id = str(frame.get("eventframe_id", ""))
        trigger_values = []
        if frame.get("trigger"):
            trigger_values.append(frame["trigger"])
        node_trigger = nodes.get(frame_id, {}).get("properties", {}).get("trigger")
        if node_trigger:
            trigger_values.append(node_trigger)
        triggers = []
        for value in trigger_values:
            trigger = _trigger_from_mapping(
                value,
                default_sentence=int(event["sentence_index"]),
                source_eventframe_id=frame_id,
            )
            if trigger is not None:
                triggers.append(trigger)
        keyed = {
            (
                row.sentence_index,
                row.char_start,
                row.char_end,
                row.normalized_text,
                row.source_eventframe_id,
            ): row
            for row in triggers
        }
        rows.append(
            RawAcceptedEventEvidence(
                prediction_id=str(event["prediction_id"]),
                sentence_index=int(event["sentence_index"]),
                char_start=int(event["char_start"]),
                char_end=int(event["char_end"]),
                triggers=tuple(keyed[key] for key in sorted(keyed)),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.sentence_index,
                row.char_start,
                row.char_end,
                row.prediction_id,
            ),
        )
    )


class SemanticExpansionGuard:
    """Reject larger spans that add grounded support or independent predicates."""

    def __init__(self, state: ResolvedAssemblyState) -> None:
        self.raw_events = build_raw_accepted_event_evidence(state)

    @staticmethod
    def _small_large(
        left: EventIdentityView, right: EventIdentityView
    ) -> tuple[EventIdentityView, EventIdentityView]:
        if (
            left.char_start <= right.char_start
            and left.char_end >= right.char_end
        ):
            return right, left
        return left, right

    @staticmethod
    def _delta_intervals(
        small: EventIdentityView, large: EventIdentityView
    ) -> tuple[tuple[int, int], ...]:
        values = []
        if large.char_start < small.char_start:
            values.append((large.char_start, small.char_start))
        if small.char_end < large.char_end:
            values.append((small.char_end, large.char_end))
        return tuple(values)

    @staticmethod
    def _compatible_anchor_triggers(
        small: EventIdentityView, large: EventIdentityView
    ) -> tuple[TriggerEvidenceView, ...]:
        anchors = []
        for small_trigger in small.triggers:
            for large_trigger in large.triggers:
                compatible = (
                    small_trigger.normalized_text == large_trigger.normalized_text
                    or (
                        small_trigger.sentence_index == large_trigger.sentence_index
                        and _overlap(
                            small_trigger.char_start,
                            small_trigger.char_end,
                            large_trigger.char_start,
                            large_trigger.char_end,
                        )
                    )
                )
                if compatible:
                    anchors.extend((small_trigger, large_trigger))
        keyed = {
            (
                row.sentence_index,
                row.char_start,
                row.char_end,
                row.normalized_text,
                row.source_eventframe_id,
            ): row
            for row in anchors
        }
        return tuple(keyed[key] for key in sorted(keyed))

    @staticmethod
    def _is_anchor_trigger(
        trigger: TriggerEvidenceView, anchors: tuple[TriggerEvidenceView, ...]
    ) -> bool:
        return any(
            trigger.normalized_text == anchor.normalized_text
            or (
                trigger.sentence_index == anchor.sentence_index
                and _overlap(
                    trigger.char_start,
                    trigger.char_end,
                    anchor.char_start,
                    anchor.char_end,
                )
            )
            for anchor in anchors
        )

    def evaluate(
        self, left: EventIdentityView, right: EventIdentityView
    ) -> SemanticExpansionDecision:
        small, large = self._small_large(left, right)
        delta = self._delta_intervals(small, large)
        large_only: dict[str, tuple[Any, ...]] = {}
        small_only: dict[str, tuple[Any, ...]] = {}
        flags = []
        for role in ("ACTOR", "TARGET", "PLACE"):
            small_targets = small.role_targets(role)
            large_targets = large.role_targets(role)
            if large_targets - small_targets:
                key = f"NEW_GROUNDED_{role}_SUPPORT"
                large_only[role] = tuple(sorted(large_targets - small_targets))
                flags.append(key)
            if small_targets - large_targets:
                small_only[role] = tuple(sorted(small_targets - large_targets))
        small_times = small.normalized_times()
        large_times = large.normalized_times()
        if large_times - small_times:
            large_only["TIME"] = tuple(sorted(large_times - small_times, key=lambda row: (row[0], str(row[1]))))
            flags.append("NEW_NORMALIZED_TIME_SUPPORT")
        if small_times - large_times:
            small_only["TIME"] = tuple(sorted(small_times - large_times, key=lambda row: (row[0], str(row[1]))))

        anchors = self._compatible_anchor_triggers(small, large)
        pair_prediction_ids = set(small.member_event_prediction_ids) | set(
            large.member_event_prediction_ids
        )
        delta_trigger_ids = set()
        delta_event_ids = set()
        for event in self.raw_events:
            if event.prediction_id in pair_prediction_ids:
                continue
            if event.sentence_index != small.sentence_index:
                continue
            event_inside_delta = any(
                start <= event.char_start and event.char_end <= end
                for start, end in delta
            )
            non_anchor_delta_trigger = any(
                any(_overlap(trigger.char_start, trigger.char_end, start, end) for start, end in delta)
                and not self._is_anchor_trigger(trigger, anchors)
                for trigger in event.triggers
            )
            if non_anchor_delta_trigger:
                delta_trigger_ids.add(event.prediction_id)
            if event_inside_delta or non_anchor_delta_trigger:
                delta_event_ids.add(event.prediction_id)
        if delta_trigger_ids:
            flags.append("DELTA_TRIGGER_EVIDENCE")
        if delta_event_ids:
            flags.append("DELTA_EVENT_EVIDENCE")

        reason_order = (
            "NEW_GROUNDED_ACTOR_SUPPORT",
            "NEW_GROUNDED_TARGET_SUPPORT",
            "NEW_GROUNDED_PLACE_SUPPORT",
            "NEW_NORMALIZED_TIME_SUPPORT",
            "DELTA_TRIGGER_EVIDENCE",
            "DELTA_EVENT_EVIDENCE",
        )
        primary = next((reason for reason in reason_order if reason in flags), "ELIGIBLE_SAFE_SPAN_VARIANT")
        return SemanticExpansionDecision(
            safe_variant=not flags,
            primary_reason=primary,
            diagnostic_flags=tuple(flags),
            small_resolved_event_id=small.resolved_event_id,
            large_resolved_event_id=large.resolved_event_id,
            delta_intervals=delta,
            large_only_support=tuple(sorted(large_only.items())),
            small_only_support=tuple(sorted(small_only.items())),
            delta_trigger_prediction_ids=tuple(sorted(delta_trigger_ids)),
            delta_event_prediction_ids=tuple(sorted(delta_event_ids)),
        )
