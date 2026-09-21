"""Read-only resolved EVENT views for public span-variant canonicalization."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping
import unicodedata

from ..assembly_input import ResolvedAssemblyState


def normalize_trigger_text(value: str) -> str:
    """Apply meaning-preserving Unicode/case/whitespace normalization only."""

    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _score(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("EVENT V3 score must be finite")
    return score


def _evidence_references(values) -> tuple[str, ...]:
    references = []
    for row in values:
        provenance = row.get("provenance", {})
        for key in (
            "participant_evidence_id",
            "source_prediction_id",
            "source_time_prediction_id",
        ):
            if provenance.get(key) is not None:
                references.append(str(provenance[key]))
        references.append(str(row.get("edge_id", "")))
    return tuple(value for value in dict.fromkeys(references) if value)


@dataclass(frozen=True, slots=True)
class TriggerEvidenceView:
    text: str
    normalized_text: str
    sentence_index: int
    char_start: int
    char_end: int
    source_eventframe_id: str


@dataclass(frozen=True, slots=True)
class ResolvedRoleSupport:
    role: str
    target_identity_id: str
    evidence_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NormalizedTimeSupport:
    target_time_id: str
    normalized_value: str
    granularity: str | None
    evidence_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EventIdentityView:
    """Immutable, score-audited view of one already resolved EVENT identity."""

    article_id: str
    resolved_event_id: str
    representative_event_prediction_id: str
    member_event_prediction_ids: tuple[str, ...]
    source_eventframe_ids: tuple[str, ...]
    source_local_event_ids: tuple[str, ...]
    sentence_index: int
    char_start: int
    char_end: int
    text: str
    semantic_score: float | None
    boundary_score: float | None
    semantic_score_source: str | None
    boundary_score_source: str | None
    triggers: tuple[TriggerEvidenceView, ...]
    role_support: tuple[ResolvedRoleSupport, ...]
    time_support: tuple[NormalizedTimeSupport, ...]
    existing_local_event_cluster_size: int

    @property
    def span_length(self) -> int:
        return self.char_end - self.char_start

    @property
    def has_usable_trigger(self) -> bool:
        return bool(self.triggers)

    @property
    def grounded_support_richness(self) -> int:
        role_keys = {(row.role, row.target_identity_id) for row in self.role_support}
        time_keys = {
            (row.target_time_id, row.normalized_value, row.granularity)
            for row in self.time_support
        }
        return len(role_keys) + len(time_keys)

    def role_targets(self, role: str) -> frozenset[str]:
        return frozenset(
            row.target_identity_id for row in self.role_support if row.role == role
        )

    def normalized_times(self) -> frozenset[tuple[str, str | None]]:
        return frozenset(
            (row.normalized_value, row.granularity) for row in self.time_support
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "resolved_event_id": self.resolved_event_id,
            "representative_event_prediction_id": self.representative_event_prediction_id,
            "member_event_prediction_ids": list(self.member_event_prediction_ids),
            "source_eventframe_ids": list(self.source_eventframe_ids),
            "source_local_event_ids": list(self.source_local_event_ids),
            "sentence_index": self.sentence_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "text": self.text,
            "semantic_score": self.semantic_score,
            "boundary_score": self.boundary_score,
            "semantic_score_source": self.semantic_score_source,
            "boundary_score_source": self.boundary_score_source,
            "triggers": [
                {
                    "text": row.text,
                    "normalized_text": row.normalized_text,
                    "sentence_index": row.sentence_index,
                    "char_start": row.char_start,
                    "char_end": row.char_end,
                    "source_eventframe_id": row.source_eventframe_id,
                }
                for row in self.triggers
            ],
            "role_support": [
                {
                    "role": row.role,
                    "target_identity_id": row.target_identity_id,
                    "evidence_references": list(row.evidence_references),
                }
                for row in self.role_support
            ],
            "time_support": [
                {
                    "target_time_id": row.target_time_id,
                    "normalized_value": row.normalized_value,
                    "granularity": row.granularity,
                    "evidence_references": list(row.evidence_references),
                }
                for row in self.time_support
            ],
            "existing_local_event_cluster_size": self.existing_local_event_cluster_size,
        }


def build_event_identity_views(
    state: ResolvedAssemblyState,
) -> tuple[EventIdentityView, ...]:
    """Resolve V3 scores and grounded support without fallback or mutation."""

    graph = state.source_graph
    article_id = str(state.article["article_id"])
    nodes_by_id = {str(row["node_id"]): row for row in graph.get("nodes", ())}
    eventframes = tuple(graph.get("eventframes", ()))
    proposition_by_prediction = {
        str(row["event"]["prediction_id"]): row["event"]
        for row in eventframes
        if row.get("event", {}).get("prediction_id") is not None
    }
    event_node_by_prediction = {
        str(row["properties"]["source_prediction_id"]): row
        for row in graph.get("nodes", ())
        if row.get("kind") == "EVENT"
        and row.get("properties", {}).get("source_prediction_id") is not None
    }
    time_nodes = {
        str(row["node_id"]): row
        for row in graph.get("nodes", ())
        if row.get("kind") == "TIME"
    }
    semantic_edges = tuple(state.semantic_edges)
    views = []
    for resolved in state.resolved_events:
        resolved_id = str(resolved["node_id"])
        properties = resolved.get("properties", {})
        if resolved.get("kind") == "LOCAL_EVENT":
            prediction_ids = tuple(
                str(value) for value in properties.get("member_event_prediction_ids", ())
            )
            eventframe_ids = tuple(
                str(value) for value in properties.get("member_eventframe_ids", ())
            )
            representative_prediction_id = str(
                properties["representative_event_prediction_id"]
            )
            local_event_ids = (resolved_id,)
            cluster_size = int(properties.get("cluster_size", len(prediction_ids)))
        else:
            representative_prediction_id = str(properties["source_prediction_id"])
            prediction_ids = (representative_prediction_id,)
            eventframe_ids = (resolved_id,)
            local_event_ids = ()
            cluster_size = 1

        proposition = proposition_by_prediction.get(representative_prediction_id)
        score_source = "source_graph.eventframes[].event"
        if proposition is None:
            event_node = event_node_by_prediction.get(representative_prediction_id)
            proposition = event_node.get("properties", {}) if event_node else None
            score_source = "source_graph.nodes[EVENT].properties"
        if proposition is None:
            raise ValueError("resolved EVENT representative prediction is unavailable")

        event_node = event_node_by_prediction.get(representative_prediction_id)
        evidence = tuple(event_node.get("evidence", ())) if event_node else ()
        representative_evidence = evidence[0] if evidence else {}

        def proposition_value(key: str):
            """Prefer the raw proposition while supporting legacy evidence carriers."""

            value = proposition.get(key)
            if value is not None:
                return value
            return representative_evidence.get(key)

        sentence_index = proposition_value("sentence_index")
        char_start = proposition_value("char_start")
        char_end = proposition_value("char_end")
        text = proposition_value("text")
        if None in (sentence_index, char_start, char_end, text):
            raise ValueError("resolved EVENT representative span is unavailable")

        semantic_score = _score(proposition.get("semantic_score"))
        boundary_score = _score(proposition.get("boundary_score"))
        semantic_source = (
            f"{score_source}.semantic_score" if semantic_score is not None else None
        )
        boundary_source = (
            f"{score_source}.boundary_score" if boundary_score is not None else None
        )

        triggers = []
        for eventframe_id in eventframe_ids:
            event_node = nodes_by_id.get(eventframe_id)
            trigger = (
                event_node.get("properties", {}).get("trigger") if event_node else None
            )
            if not trigger:
                continue
            text = str(trigger.get("text", ""))
            if not text or trigger.get("char_start") is None or trigger.get("char_end") is None:
                continue
            triggers.append(
                TriggerEvidenceView(
                    text=text,
                    normalized_text=normalize_trigger_text(text),
                    sentence_index=int(
                        trigger.get("sentence_index", sentence_index)
                    ),
                    char_start=int(trigger["char_start"]),
                    char_end=int(trigger["char_end"]),
                    source_eventframe_id=eventframe_id,
                )
            )
        trigger_key = lambda row: (
            row.sentence_index,
            row.char_start,
            row.char_end,
            row.normalized_text,
            row.source_eventframe_id,
        )
        triggers = list({trigger_key(row): row for row in triggers}.values())

        role_support = []
        time_support = []
        for edge in semantic_edges:
            if str(edge.get("source_id")) not in eventframe_ids:
                continue
            edge_type = str(edge.get("edge_type"))
            if edge_type in {"ACTOR", "TARGET", "PLACE"}:
                role_support.append(
                    ResolvedRoleSupport(
                        role=edge_type,
                        target_identity_id=str(edge["target_id"]),
                        evidence_references=_evidence_references((edge,)),
                    )
                )
            elif edge_type == "OCCURRED_ON":
                time = time_nodes.get(str(edge["target_id"]))
                if time is None or time.get("properties", {}).get("normalized_value") is None:
                    continue
                time_support.append(
                    NormalizedTimeSupport(
                        target_time_id=str(edge["target_id"]),
                        normalized_value=str(time["properties"]["normalized_value"]),
                        granularity=(
                            str(time["properties"]["granularity"])
                            if time["properties"].get("granularity") is not None
                            else None
                        ),
                        evidence_references=_evidence_references((edge,)),
                    )
                )
        role_support = list(
            {
                (row.role, row.target_identity_id, row.evidence_references): row
                for row in role_support
            }.values()
        )
        time_support = list(
            {
                (
                    row.target_time_id,
                    row.normalized_value,
                    row.granularity,
                    row.evidence_references,
                ): row
                for row in time_support
            }.values()
        )
        views.append(
            EventIdentityView(
                article_id=article_id,
                resolved_event_id=resolved_id,
                representative_event_prediction_id=representative_prediction_id,
                member_event_prediction_ids=prediction_ids,
                source_eventframe_ids=eventframe_ids,
                source_local_event_ids=local_event_ids,
                sentence_index=int(sentence_index),
                char_start=int(char_start),
                char_end=int(char_end),
                text=str(text),
                semantic_score=semantic_score,
                boundary_score=boundary_score,
                semantic_score_source=semantic_source,
                boundary_score_source=boundary_source,
                triggers=tuple(sorted(triggers, key=trigger_key)),
                role_support=tuple(
                    sorted(role_support, key=lambda row: (row.role, row.target_identity_id))
                ),
                time_support=tuple(
                    sorted(
                        time_support,
                        key=lambda row: (
                            row.normalized_value,
                            str(row.granularity),
                            row.target_time_id,
                        ),
                    )
                ),
                existing_local_event_cluster_size=cluster_size,
            )
        )
    return tuple(
        sorted(
            views,
            key=lambda row: (
                row.sentence_index,
                row.char_start,
                row.char_end,
                row.resolved_event_id,
            ),
        )
    )
