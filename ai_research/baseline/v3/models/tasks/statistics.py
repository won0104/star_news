"""Task adapter가 공유하는 dependency-free class-aware metric primitives."""

from __future__ import annotations

import math
from typing import Mapping, Sequence


def binary_report(
    gold: Sequence[int],
    scores: Sequence[float],
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    if len(gold) != len(scores):
        raise ValueError("gold/scores lengths differ")
    predicted = [int(score >= threshold) for score in scores]
    tp = sum(g == 1 and p == 1 for g, p in zip(gold, predicted))
    fp = sum(g == 0 and p == 1 for g, p in zip(gold, predicted))
    fn = sum(g == 1 and p == 0 for g, p in zip(gold, predicted))
    precision, recall, f1 = _prf(tp, fp, fn)
    return {
        "positive_precision": precision,
        "positive_recall": recall,
        "positive_f1": f1,
        "pr_auc": pr_auc(gold, scores),
        "positive_count": float(sum(gold)),
        "support": float(len(gold)),
    }


def multiclass_report(
    gold: Sequence[int],
    predicted: Sequence[int],
    label_names: Sequence[str],
    *,
    probabilities: Sequence[Sequence[float]] | None = None,
    positive_labels: Sequence[str] = (),
) -> dict[str, float]:
    """정확한 class 일치 기준 P/R/F1, confusion, optional one-vs-rest PR-AUC."""

    if len(gold) != len(predicted):
        raise ValueError("gold/predicted lengths differ")
    if probabilities is not None and len(probabilities) != len(gold):
        raise ValueError("probabilities must align with gold")
    result: dict[str, float] = {
        "support": float(len(gold)),
        "accuracy": sum(left == right for left, right in zip(gold, predicted))
        / max(len(gold), 1),
    }
    per_f1 = []
    counts = {}
    for label_id, label in enumerate(label_names):
        tp = sum(g == label_id and p == label_id for g, p in zip(gold, predicted))
        fp = sum(g != label_id and p == label_id for g, p in zip(gold, predicted))
        fn = sum(g == label_id and p != label_id for g, p in zip(gold, predicted))
        precision, recall, f1 = _prf(tp, fp, fn)
        support = sum(g == label_id for g in gold)
        counts[label] = (tp, fp, fn)
        per_f1.append(f1)
        result[f"per_class/{label}/precision"] = precision
        result[f"per_class/{label}/recall"] = recall
        result[f"per_class/{label}/f1"] = f1
        result[f"per_class/{label}/support"] = float(support)
        if probabilities is not None:
            result[f"per_class/{label}/pr_auc"] = pr_auc(
                [int(item == label_id) for item in gold],
                [float(row[label_id]) for row in probabilities],
            )
    result["macro_f1"] = sum(per_f1) / max(len(per_f1), 1)
    for gold_id, gold_label in enumerate(label_names):
        for predicted_id, predicted_label in enumerate(label_names):
            result[f"confusion/{gold_label}/{predicted_label}"] = float(
                sum(g == gold_id and p == predicted_id for g, p in zip(gold, predicted))
            )

    positive_ids = [label_names.index(label) for label in positive_labels]
    if positive_ids:
        positive_f1 = [result[f"per_class/{label}/f1"] for label in positive_labels]
        result["positive_macro_f1"] = sum(positive_f1) / len(positive_f1)
        tp = sum(counts[label][0] for label in positive_labels)
        fp = sum(counts[label][1] for label in positive_labels)
        fn = sum(counts[label][2] for label in positive_labels)
        precision, recall, f1 = _prf(tp, fp, fn)
        result["positive_micro_precision"] = precision
        result["positive_micro_recall"] = recall
        result["positive_micro_f1"] = f1
        if probabilities is not None:
            aucs = [
                result[f"per_class/{label}/pr_auc"]
                for label in positive_labels
                if not math.isnan(result[f"per_class/{label}/pr_auc"])
            ]
            result["positive_macro_pr_auc"] = (
                sum(aucs) / len(aucs) if aucs else math.nan
            )
    return result


def presence_report(
    gold_bits: Sequence[Sequence[int]],
    bit_scores: Sequence[Sequence[float]],
    *,
    event_threshold: float = 0.5,
    statement_threshold: float = 0.5,
) -> dict[str, float]:
    if len(gold_bits) != len(bit_scores):
        raise ValueError("presence gold/scores lengths differ")
    result = {}
    thresholds = (event_threshold, statement_threshold)
    for bit, label in enumerate(("EVENT", "STATEMENT")):
        bit_metric = binary_report(
            [int(row[bit]) for row in gold_bits],
            [float(row[bit]) for row in bit_scores],
            threshold=thresholds[bit],
        )
        result.update({f"bit/{label}/{name}": value for name, value in bit_metric.items()})
    gold_state = [int(row[0]) + 2 * int(row[1]) for row in gold_bits]
    predicted_state = [
        int(row[0] >= event_threshold) + 2 * int(row[1] >= statement_threshold)
        for row in bit_scores
    ]
    state = multiclass_report(
        gold_state,
        predicted_state,
        ("DROP", "EVENT", "STATEMENT", "MIX"),
    )
    result.update({f"state/{name}": value for name, value in state.items()})
    result["state/MIX/f1"] = state["per_class/MIX/f1"]
    result["state/MIX/support"] = state["per_class/MIX/support"]
    return result


def exact_item_report(
    gold: Sequence[tuple[object, ...]], predicted: Sequence[tuple[object, ...]]
) -> dict[str, float]:
    gold_set, predicted_set = set(gold), set(predicted)
    true_positive = len(gold_set & predicted_set)
    precision = true_positive / max(len(predicted_set), 1)
    recall = true_positive / max(len(gold_set), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "gold": float(len(gold_set)),
        "predicted": float(len(predicted_set)),
        "true_positive": float(true_positive),
    }


def pr_auc(gold: Sequence[int], scores: Sequence[float]) -> float:
    positives = sum(gold)
    if positives == 0:
        return math.nan
    ordered = sorted(zip(scores, gold), key=lambda item: item[0], reverse=True)
    points = [(0.0, 1.0)]
    tp = fp = 0
    for _, label in ordered:
        tp += int(label == 1)
        fp += int(label == 0)
        points.append((tp / positives, tp / max(tp + fp, 1)))
    area = 0.0
    for (left_recall, left_precision), (right_recall, right_precision) in zip(
        points, points[1:]
    ):
        area += (right_recall - left_recall) * (
            left_precision + right_precision
        ) / 2
    return area


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return precision, recall, f1
