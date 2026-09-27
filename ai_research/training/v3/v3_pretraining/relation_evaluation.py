"""Sampling·serving cap과 분리된 Gold-conditioned relation full-universe 평가.

지표는 tie score를 하나의 ``score >= threshold`` group으로 처리한다. Empty 또는
single-class universe의 정의되지 않는 값은 JSON-safe ``None``과 reason으로 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable, Mapping, Sequence

import torch

from training.v3_pretraining.targets import PairTarget, PairUniverse


FULL_UNIVERSE_EVALUATION_VERSION = "relation-gold-full-universe-v1"


@dataclass(frozen=True, slots=True)
class ScoredPair:
    article_id: str
    left_id: str
    right_id: str
    label: bool
    score: float
    cohort: str | None = None


def _undefined(reason: str) -> dict[str, object]:
    return {"status": "UNDEFINED", "value": None, "reason": reason}


def _defined(value: float) -> dict[str, object]:
    return {"status": "DEFINED", "value": float(value), "reason": None}


def binary_ranking_metrics(rows: Sequence[ScoredPair]) -> dict[str, object]:
    """Tie-invariant AP/ROC와 모든 finite observed threshold의 >= operating point."""
    positive = sum(row.label for row in rows)
    negative = len(rows) - positive
    grouped: dict[float, list[ScoredPair]] = {}
    for row in rows:
        if not math.isfinite(row.score):
            raise ValueError("relation evaluation score must be finite")
        grouped.setdefault(float(row.score), []).append(row)
    thresholds = sorted(grouped, reverse=True)
    tp = fp = 0
    previous_recall = 0.0
    ap = 0.0
    curve = []
    for threshold in thresholds:
        group = grouped[threshold]
        tp += sum(row.label for row in group)
        fp += sum(not row.label for row in group)
        recall = tp / positive if positive else None
        precision = tp / (tp + fp) if tp + fp else None
        coverage = (tp + fp) / len(rows) if rows else None
        if recall is not None and precision is not None:
            ap += (recall - previous_recall) * precision
            previous_recall = recall
        curve.append({"threshold": threshold, "true_positive": tp,
                      "false_positive": fp, "precision": precision,
                      "recall": recall, "coverage": coverage})
    if positive and negative:
        wins = ties = negative_below = 0
        for score in sorted(grouped):
            group_positive = sum(row.label for row in grouped[score])
            group_negative = len(grouped[score]) - group_positive
            wins += group_positive * negative_below
            ties += group_positive * group_negative
            negative_below += group_negative
        roc = (wins + 0.5 * ties) / (positive * negative)
        roc_metric = _defined(roc)
    else:
        roc_metric = _undefined("ROC_AUC_REQUIRES_BOTH_CLASSES")
    ap_metric = (_defined(ap) if positive
                 else _undefined("AVERAGE_PRECISION_REQUIRES_POSITIVE"))
    accepted_zero = [row for row in rows if row.score >= 0.0]
    zero_tp = sum(row.label for row in accepted_zero)
    zero_fp = len(accepted_zero) - zero_tp
    zero_fn = positive - zero_tp
    zero_precision = zero_tp / len(accepted_zero) if accepted_zero else None
    zero_recall = zero_tp / positive if positive else None
    zero_f1_denominator = 2 * zero_tp + zero_fp + zero_fn
    zero_f1 = (2 * zero_tp / zero_f1_denominator
               if zero_f1_denominator > 0 else None)
    return {
        "support": {"total": len(rows), "positive": positive, "negative": negative},
        "average_precision": ap_metric,
        "roc_auc": roc_metric,
        "threshold_zero": {"comparison": "score >= threshold",
                           "accepted": len(accepted_zero),
                           "precision": zero_precision, "recall": zero_recall,
                           "f1": zero_f1,
                           "f1_reason": (None if zero_f1 is not None else
                                         "F1_REQUIRES_NONZERO_2TP_FP_FN_DENOMINATOR"),
                           "coverage": len(accepted_zero) / len(rows) if rows else None},
        "pr_threshold_curve": curve,
    }


def score_full_universe(
        *, article_id: str, universe: PairUniverse, chunk_size: int,
        score_chunk: Callable[[tuple[PairTarget, ...]], torch.Tensor],
        cohort_for: Callable[[PairTarget], str | None] | None = None,
        cohort_names: Sequence[str] = (),
) -> dict[str, object]:
    """Serving max-pair cap이나 train sampler 없이 eligible iterator 전체를 score한다."""
    if chunk_size <= 0:
        raise ValueError("full-universe evaluation chunk size must be positive")
    rows: list[ScoredPair] = []
    chunk: list[PairTarget] = []

    def flush() -> None:
        if not chunk:
            return
        frozen = tuple(chunk)
        logits = score_chunk(frozen)
        if logits.shape != (len(frozen),):
            raise ValueError("relation evaluation scorer returned wrong shape")
        values = logits.detach().cpu().tolist()
        rows.extend(ScoredPair(article_id, pair.left_id, pair.right_id,
                               pair.positive, float(score),
                               cohort_for(pair) if cohort_for else None)
                    for pair, score in zip(frozen, values))
        chunk.clear()

    with torch.no_grad():
        for pair in universe:
            if pair.supervision_mask == "IGNORE":
                continue
            chunk.append(pair)
            if len(chunk) == chunk_size:
                flush()
        flush()
    expected = universe.counts()
    support = {"positive": sum(row.label for row in rows),
               "negative": sum(not row.label for row in rows)}
    if (len(rows) != expected["positive"] + expected["negative"] or
            support["positive"] != expected["positive"]
            or support["negative"] != expected["negative"]):
        raise AssertionError("full-universe scored support differs from compiler universe")
    observed_cohorts = {row.cohort for row in rows if row.cohort is not None}
    if observed_cohorts - set(cohort_names) and cohort_names:
        raise ValueError("full-universe scorer returned unknown sentence cohort")
    cohorts = {}
    for name in sorted(set(cohort_names) | observed_cohorts):
        cohorts[name] = binary_ranking_metrics([row for row in rows if row.cohort == name])
    return {
        "evaluation_version": FULL_UNIVERSE_EVALUATION_VERSION,
        "article_id": article_id,
        "task": universe.task,
        "universe_shape": universe.shape,
        "sampling_applied": False,
        "serving_pair_cap_applied": False,
        "chunk_size": chunk_size,
        "scored_count": len(rows),
        "compiler_support": expected,
        "micro_pooled": binary_ranking_metrics(rows),
        "sentence_cohorts": cohorts,
        "scored_pairs": [
            {"article_id": row.article_id, "left_id": row.left_id,
             "right_id": row.right_id, "label": row.label,
             "score": row.score, "cohort": row.cohort}
            for row in rows],
        "article_macro": {
            "status": "SINGLE_ARTICLE_COMPONENT",
            "article_count": 1,
            "aggregation_contract": "mean each defined per-article metric; never pool denominators",
        },
    }


def aggregate_article_reports(reports: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """전체 score의 pooled metric과 per-article metric mean을 분리한다."""
    reports = tuple(reports)
    by_metric = {"average_precision": [], "roc_auc": [],
                 "threshold_zero_precision": [], "threshold_zero_recall": [],
                 "threshold_zero_f1": [], "threshold_zero_coverage": []}
    score_rows = []
    for report in reports:
        metrics = report["micro_pooled"]
        for name in ("average_precision", "roc_auc"):
            row = metrics[name]
            if row["status"] == "DEFINED":
                by_metric[name].append(float(row["value"]))
        for name in ("precision", "recall", "f1", "coverage"):
            value = metrics["threshold_zero"][name]
            if value is not None:
                by_metric["threshold_zero_" + name].append(float(value))
        score_rows.extend(ScoredPair(**row) for row in report["scored_pairs"])
    cohort_names = sorted({row.cohort for row in score_rows if row.cohort is not None})
    return {
        "article_count": len(reports),
        "micro_pooled": binary_ranking_metrics(score_rows),
        "sentence_cohorts_micro_pooled": {
            name: binary_ranking_metrics(
                [row for row in score_rows if row.cohort == name])
            for name in cohort_names},
        "article_macro": {
            name: {"value": sum(values) / len(values) if values else None,
                   "defined_article_count": len(values),
                   "total_article_count": len(reports),
                   "reason": None if values else "NO_DEFINED_ARTICLE_METRIC"}
            for name, values in by_metric.items()},
    }
