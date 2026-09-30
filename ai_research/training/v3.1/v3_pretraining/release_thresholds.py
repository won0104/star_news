"""Dev-only raw-logit threshold selection for a frozen v3 checkpoint.

This module evaluates labelled, routed candidates after prediction. It never
changes the candidate universe, runs a model, or reads the test split.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Iterable


# Gold400 release preference: ambiguous Event pairs may merge. F4 weights
# recall sixteen times as strongly as precision during selected-checkpoint dev
# calibration; the resulting threshold still needs predicted-cascade review.
EVENT_COREFERENCE_BETA = 4.0
EVENT_COREFERENCE_POLICY = "V3_EVENT_COREF_DEV_F4_MERGE_FORWARD_V1"


@dataclass(frozen=True, slots=True)
class LabelledRawScore:
    candidate_id: str
    score: float
    authority: str


def select_raw_threshold(rows: Iterable[LabelledRawScore], *,
                         positive_denominator: int, beta: float,
                         policy_id: str) -> dict:
    """Select one dev threshold, retaining routing misses in recall denominator.

    IGNORE is excluded from precision. A positive absent from ``rows`` is
    counted through ``positive_denominator`` and cannot become a true positive.
    """
    materialized = tuple(rows)
    if (not policy_id or not math.isfinite(beta) or beta <= 0 or
            type(positive_denominator) is not int or positive_denominator < 1 or
            len({row.candidate_id for row in materialized}) != len(materialized) or
            any(row.authority not in {"POSITIVE", "NEGATIVE", "IGNORE"} or
                not math.isfinite(row.score) for row in materialized)):
        raise ValueError("raw threshold selection requires unique finite dev authority")
    labelled = tuple(row for row in materialized if row.authority != "IGNORE")
    reachable = sum(row.authority == "POSITIVE" for row in labelled)
    if reachable > positive_denominator or not labelled or not any(
            row.authority == "NEGATIVE" for row in labelled):
        raise ValueError("positive denominator or negative authority differs")
    groups: dict[float, list[int]] = defaultdict(lambda: [0, 0])
    for row in labelled:
        groups[row.score][0 if row.authority == "POSITIVE" else 1] += 1
    beta2 = beta * beta
    tp = fp = 0
    curve = []
    for threshold, (positive, negative) in sorted(groups.items(), reverse=True):
        tp += positive
        fp += negative
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / positive_denominator
        score = ((1 + beta2) * precision * recall /
                 (beta2 * precision + recall)
                 if precision or recall else 0.0)
        curve.append({"threshold": threshold, "tp": tp, "fp": fp,
                      "fn": positive_denominator - tp,
                      "precision": precision, "recall": recall,
                      "f_beta": score})
    selected = max(curve, key=lambda row: (
        row["f_beta"], row["recall"], row["precision"], row["threshold"]))
    return {"policy_id": policy_id, "beta": beta,
            "selection_status": "DEV_RAW_SCORE_CANDIDATE",
            "positive_denominator": positive_denominator,
            "reachable_positive": reachable,
            "not_evaluated_positive": positive_denominator - reachable,
            "labelled_negative": sum(row.authority == "NEGATIVE" for row in labelled),
            "ignored_count": len(materialized) - len(labelled),
            "selected": selected, "curve": curve}
