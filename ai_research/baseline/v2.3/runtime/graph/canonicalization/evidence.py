"""Stable references to evidence already present in immutable assembly input."""

from __future__ import annotations

from typing import Any, Mapping


def preserved_evidence_references(
    identity: str, row: Mapping[str, Any]
) -> tuple[str, ...]:
    """Reference existing member/source evidence without changing its payload."""

    properties = row.get("properties", {})
    references: list[str] = []
    for key in (
        "member_event_prediction_ids",
        "member_entity_prediction_ids",
        "source_time_prediction_ids",
    ):
        references.extend(str(value) for value in properties.get(key, ()))
    for key in (
        "source_prediction_id",
        "representative_event_prediction_id",
        "representative_entity_prediction_id",
    ):
        if properties.get(key) is not None:
            references.append(str(properties[key]))
    for evidence in row.get("evidence", ()):
        if evidence.get("prediction_id") is not None:
            references.append(str(evidence["prediction_id"]))
            continue
        fields = (
            evidence.get("article_id"),
            evidence.get("sentence_index"),
            evidence.get("char_start"),
            evidence.get("char_end"),
        )
        if all(value is not None for value in fields):
            references.append("SPAN:" + ":".join(str(value) for value in fields))
    return tuple(dict.fromkeys(references)) or (identity,)
