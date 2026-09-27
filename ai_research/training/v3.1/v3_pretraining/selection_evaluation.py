"""B5 Gold selection metric assembly with explicit evaluation-label authority.

Extraction candidate/label rows must be supplied by a separately approved authority;
model scores are supplied separately by the current epoch's retrieval/head output.
Relation/identity rows come from the compiler's closed pair universes and actual task
heads.  This module never turns missing Gold annotations into training negatives.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from training.v3_pretraining.selection_contract import (
    AP_SUPPORT_COMPONENTS, E_COMPONENTS, PARTICIPANT_ROLES, R_COMPONENTS,
    average_precision_with_retrieval_misses,
)


EXTRACTION_EVAL_AUTHORITY_VERSION = "v3-extraction-eval-candidate-label-authority-v2"
APPROVED_AUTHORITY_STATES = frozenset(("APPROVED_EXTERNAL", "APPROVED_SYNTHETIC_FIXTURE"))


@dataclass(frozen=True, slots=True)
class ExtractionEvaluationAuthority:
    """Externally approved fixed E candidates/labels, never epoch model scores.

    ``owner_id`` is null for the five generic source lanes and the Gold Event ID for
    an event-conditioned PARTICIPANT lane.  The authority fixes only evaluation
    membership and labels; current-epoch retrieval decides whether a candidate has a
    finite score.
    """

    version: str
    authority_id: str
    approval_state: str
    article_id: str
    component_rows: Mapping[str, tuple[Mapping[str, Any], ...]]

    def validate(self) -> None:
        expected = tuple([f"E.{name}" for name in E_COMPONENTS[:-1]]
                         + [f"E.PARTICIPANT.{role}" for role in PARTICIPANT_ROLES])
        if (self.version != EXTRACTION_EVAL_AUTHORITY_VERSION
                or not self.authority_id or not self.article_id
                or self.approval_state not in APPROVED_AUTHORITY_STATES
                or set(self.component_rows) != set(expected)):
            raise ValueError("extraction evaluation authority is absent or unapproved")
        for component, rows in self.component_rows.items():
            seen_ids: set[str] = set()
            seen_candidates: set[tuple[str | None, int, int]] = set()
            participant = component.startswith("E.PARTICIPANT.")
            for row in rows:
                if set(row) != {"pair_id", "label", "start", "end", "owner_id"}:
                    raise ValueError("extraction authority must not contain model scores")
                pair_id = row["pair_id"]
                label = row["label"]
                start, end, owner_id = row["start"], row["end"], row["owner_id"]
                if (not isinstance(pair_id, str) or not pair_id
                        or not isinstance(label, bool)
                        or not isinstance(start, int) or isinstance(start, bool)
                        or not isinstance(end, int) or isinstance(end, bool)
                        or not 0 <= start < end
                        or (participant and (not isinstance(owner_id, str) or not owner_id))
                        or (not participant and owner_id is not None)):
                    raise ValueError("extraction authority candidate schema differs")
                key = (owner_id, start, end)
                if pair_id in seen_ids or key in seen_candidates:
                    raise ValueError("extraction authority candidates must be unique")
                seen_ids.add(pair_id)
                seen_candidates.add(key)


def bind_extraction_epoch_scores(
        authority: ExtractionEvaluationAuthority,
        epoch_scores: Mapping[str, Mapping[tuple[str | None, int, int], float]],
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Join fixed authority rows with current-epoch retrieval/head scores.

    Missing candidates retain their fixed support but do not receive a fabricated
    score.  Positive misses therefore remain in the AP recall denominator, while
    non-retrieved negatives never become an invented finite prediction.
    """
    authority.validate()
    if set(epoch_scores) != set(authority.component_rows):
        raise ValueError("extraction epoch score component inventory differs")
    bound: dict[str, tuple[dict[str, Any], ...]] = {}
    for component, rows in authority.component_rows.items():
        scores = epoch_scores[component]
        if not isinstance(scores, Mapping):
            raise ValueError("extraction epoch scores must be candidate-key mappings")
        normalized_scores: dict[tuple[str | None, int, int], float] = {}
        for key, value in scores.items():
            if (not isinstance(key, tuple) or len(key) != 3
                    or (key[0] is not None and not isinstance(key[0], str))
                    or not isinstance(key[1], int) or isinstance(key[1], bool)
                    or not isinstance(key[2], int) or isinstance(key[2], bool)
                    or not isinstance(value, (int, float))
                    or isinstance(value, bool)):
                raise ValueError("extraction epoch score key/value differs")
            score = float(value)
            if not math.isfinite(score):
                raise ValueError("extraction epoch scores must be finite")
            normalized_scores[key] = score
        output = []
        for row in rows:
            key = (row["owner_id"], row["start"], row["end"])
            score = normalized_scores.get(key)
            output.append({
                "pair_id": row["pair_id"],
                "label": row["label"],
                "score": score,
                "retrieval_miss": score is None,
            })
        bound[component] = tuple(output)
    return bound


def score_extraction_authority(
        authority: ExtractionEvaluationAuthority,
        epoch_scores: Mapping[str, Mapping[tuple[str | None, int, int], float]],
) -> tuple[dict[str, Mapping[str, Any]],
           dict[str, tuple[dict[str, Any], ...]]]:
    """Score fixed E support with the current epoch's actual model outputs."""
    rows = bind_extraction_epoch_scores(authority, epoch_scores)
    return ({name: average_precision_with_retrieval_misses(component_rows)
             for name, component_rows in rows.items()}, rows)


def ap_from_full_universe(report: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a D7 full-universe report without applying sampler or serving cap."""
    if report.get("sampling_applied") is not False \
            or report.get("serving_pair_cap_applied") is not False:
        raise ValueError("selection relation metrics require an uncapped full universe")
    metrics = report.get("micro_pooled")
    if not isinstance(metrics, Mapping):
        raise ValueError("full-universe report lacks pooled metrics")
    ap = metrics.get("average_precision")
    support = metrics.get("support")
    if not isinstance(ap, Mapping) or not isinstance(support, Mapping):
        raise ValueError("full-universe report lacks AP/support")
    return {
        "status": ap.get("status"), "value": ap.get("value"),
        "reason": ap.get("reason"), "support": dict(support),
        "retrieval_miss_positive": 0,
    }


def assemble_selection_components(
        *, extraction: ExtractionEvaluationAuthority,
        extraction_epoch_scores: Mapping[
            str, Mapping[tuple[str | None, int, int], float]],
        entity_reports: Mapping[str, Mapping[str, Any]],
        time_report: Mapping[str, Any], event_report: Mapping[str, Any],
        attribution_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Bind current AP components to their lane-specific score reports."""
    extraction_components, _rows = score_extraction_authority(
        extraction, extraction_epoch_scores)
    components = dict(extraction_components)
    sources = {
        "R.EVENT_TIME": time_report,
        "R.ENTITY_COREFERENCE_MERGE": entity_reports["entity_coreference"],
        "R.EVENT_COREFERENCE_MERGE": event_report,
        "R.ASSERTED_BY": attribution_report["lanes"]["assertor_entity"],
        "R.ABOUT": attribution_report["lanes"]["about"],
        "R.CAUSES": attribution_report["lanes"]["causes"],
    }
    components.update({name: ap_from_full_universe(report)
                       for name, report in sources.items()})
    if set(components) != set(AP_SUPPORT_COMPONENTS):
        raise AssertionError("selection component inventory differs")
    return components


def selection_wiring_contract() -> dict[str, Any]:
    """Machine-readable distinction between executable wiring and missing E authority."""
    return {
        "E": {
            "caller": ("fixed ExtractionEvaluationAuthority + current-epoch "
                       "decode_source_spans -> score_extraction_authority"),
            "actual_dev_authority": "BLOCKED_BY_DECISION",
            "synthetic_fixture_authority": "APPROVED_SYNTHETIC_FIXTURE",
            "authority_contains_model_scores": False,
        },
        "R": {name: "ACTUAL_FULL_UNIVERSE_SCORE_PRODUCER" for name in R_COMPONENTS},
        "P": "ACTUAL_PRIMARY_SCORE_INVENTORY_ALL_STRICT_NON_TIE_PAIRS",
        "backbone_forwards_per_article": 1,
        "shared_dce_forwards_per_article": 1,
    }
