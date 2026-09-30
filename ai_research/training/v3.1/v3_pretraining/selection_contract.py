"""D8 checkpoint selection, support manifest, and bounded rehearsal contracts.

This module is deliberately independent of model training.  It consumes scored
Gold-conditioned component rows, validates them against a pre-frozen support
manifest, and selects only after all six immutable epoch checkpoints exist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Callable, Iterable, Mapping, Sequence


SELECTION_POLICY_VERSION = "v3-max6-weakest-group-lexicographic-v3-unified-entity"
SELECTION_METRIC_VERSION = "v3-selection-metrics-epoch-model-score-authority-v4-unified-entity"
SUPPORT_MANIFEST_VERSION = "v3-selection-support-manifest-v3-unified-entity"
SELECTION_ARTIFACT_VERSION = "v3-epoch-selection-artifact-v3-unified-entity"
SELECTION_LEDGER_VERSION = "v3-selection-ledger-v3-unified-entity"
LOSS_REDUCTION_CONTRACT_VERSION = "v3-active-article-task-mean-v1"
GRADIENT_CLIP_CONTRACT_VERSION = "v3-global-clip-observability-v1"
REHEARSAL_POLICY_VERSION = "v3-stage10-bounded-rehearsal-v1"
SELECTION_TOLERANCE = 1e-6
MAX_EPOCHS = 6

E_COMPONENTS = (
    "EVENT", "STATEMENT", "TRIGGER", "ENTITY", "TIME", "PARTICIPANT",
)
PARTICIPANT_ROLES = ("ACTOR", "TARGET", "PLACE")
R_COMPONENTS = (
    "EVENT_TIME", "ENTITY_COREFERENCE_MERGE",
    "EVENT_COREFERENCE_MERGE", "ASSERTED_BY", "ABOUT", "CAUSES",
)
E_SCORE_RESPONSIBILITY = {
    "EVENT": "EXACT_SEMANTIC_VALIDITY_DECISION_LOGIT",
    "STATEMENT": "EXACT_SEMANTIC_VALIDITY_DECISION_LOGIT",
    "TRIGGER": "TRIGGER_EXACT_DECISION_SPAN_LOGIT",
    "ENTITY": "ENTITY_MENTION_EXISTENCE_DECISION_LOGIT",
    "TIME": "TIME_MENTION_DECISION_SPAN_LOGIT",
    "PARTICIPANT": "EVENT_CONDITIONED_ROLE_DECISION_LOGIT",
}
R_SCORE_RESPONSIBILITY = {
    "EVENT_TIME": "RAW_ATTACHMENT_LOGIT_BEFORE_THRESHOLD",
    "ENTITY_COREFERENCE_MERGE": "MERGE_SCORE_OR_MARGIN_BEFORE_THRESHOLD",
    "EVENT_COREFERENCE_MERGE": "MERGE_MARGIN_BEFORE_THRESHOLD",
    "ASSERTED_BY": "D5_RAW_DIRECTED_LOGIT_BEFORE_THRESHOLD",
    "ABOUT": "D6_PAIR_CONTEXT_V1_RAW_LOGIT_BEFORE_THRESHOLD",
    "CAUSES": "D6_PAIR_CONTEXT_V1_RAW_LOGIT_BEFORE_THRESHOLD",
}
AP_SUPPORT_COMPONENTS = tuple(
    [f"E.{name}" for name in E_COMPONENTS[:-1]]
    + [f"E.PARTICIPANT.{role}" for role in PARTICIPANT_ROLES]
    + [f"R.{name}" for name in R_COMPONENTS]
)
SELECTION_TUPLE_DEFINITION = (
    "(min(E,R),0.5*(E+R),P,-dev_total_multitask_loss,-epoch)"
)

REHEARSAL_ARTICLE_IDS = (
    "GNEWS-1f1212c0d511aaa022a3a9d874348631",
    "GNEWS-598dee5f72fc045b4897c5de765cf64a",
    "GNEWS-8c0800f1b784e233bfc2a72a5d729e41",
    "GNEWS-7a4d4d31f391a244226ad49fc8c6f205",
    "GNEWS-74a9baedb9c04ab2199f5e5acd26f870",
    "GNEWS-63543c51f3d13108f1efb2882f8201d2",
)


def json_digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _sha(value: object, *, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError(f"{field} must be a lowercase sha256")
    return value


@dataclass(frozen=True, slots=True)
class D8SelectionPolicy:
    version: str = SELECTION_POLICY_VERSION
    planned_epochs: tuple[int, ...] = tuple(range(1, MAX_EPOCHS + 1))
    max_epochs: int = MAX_EPOCHS
    early_stopping: bool = False
    patience: None = None
    tuple_definition: str = SELECTION_TUPLE_DEFINITION
    tolerance: float = SELECTION_TOLERANCE
    predicted_dev_cascade_limit: int = 1
    test_access_policy: str = "CLOSED_UNTIL_EXPLICIT_APPROVAL"

    def validate(self) -> None:
        if (self.version != SELECTION_POLICY_VERSION
                or self.planned_epochs != tuple(range(1, 7))
                or self.max_epochs != 6 or self.early_stopping is not False
                or self.patience is not None
                or self.tuple_definition != SELECTION_TUPLE_DEFINITION
                or self.tolerance != SELECTION_TOLERANCE
                or self.predicted_dev_cascade_limit != 1
                or self.test_access_policy != "CLOSED_UNTIL_EXPLICIT_APPROVAL"):
            raise ValueError("D8 selection policy differs from the approved contract")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["planned_epochs"] = list(self.planned_epochs)
        return value


def selection_policy() -> dict[str, Any]:
    return D8SelectionPolicy().to_dict()


def build_support_manifest(*, split_identity: str,
                           articles: Sequence[Mapping[str, Any]],
                           component_support: Mapping[str, Mapping[str, int]],
                           primary_strict_non_tie_support: int,
                           test_access_count: int) -> dict[str, Any]:
    """Freeze model-independent selection support before any optimizer step."""
    if not split_identity or not articles or test_access_count != 0:
        raise ValueError("support manifest requires a nonempty split and zero test access")
    if set(component_support) != set(AP_SUPPORT_COMPONENTS):
        raise ValueError("support manifest component inventory differs")
    normalized_articles = []
    for row in articles:
        required = {"article_id", "source_sha256", "content_sha256",
                    "target_contract_sha256"}
        if set(row) != required or not row["article_id"]:
            raise ValueError("support manifest article provenance differs")
        normalized_articles.append({
            "article_id": str(row["article_id"]),
            "source_sha256": _sha(row["source_sha256"], field="source_sha256"),
            "content_sha256": _sha(row["content_sha256"], field="content_sha256"),
            "target_contract_sha256": _sha(
                row["target_contract_sha256"], field="target_contract_sha256"),
        })
    normalized_articles.sort(key=lambda row: row["article_id"])
    if len({row["article_id"] for row in normalized_articles}) != len(normalized_articles):
        raise ValueError("support manifest article IDs must be unique")
    normalized_support = {}
    for name in AP_SUPPORT_COMPONENTS:
        row = component_support[name]
        if set(row) != {"positive", "negative"}:
            raise ValueError(f"{name}: support schema differs")
        positive, negative = row["positive"], row["negative"]
        if (not isinstance(positive, int) or not isinstance(negative, int)
                or positive < 0 or negative < 0):
            raise ValueError(f"{name}: support must be nonnegative integers")
        normalized_support[name] = {"positive": positive, "negative": negative,
                                    "total": positive + negative}
    if (not isinstance(primary_strict_non_tie_support, int)
            or primary_strict_non_tie_support < 0):
        raise ValueError("Primary strict support must be a nonnegative integer")
    body = {
        "schema_version": SUPPORT_MANIFEST_VERSION,
        "selection_contract_version": SELECTION_POLICY_VERSION,
        "selection_metric_version": SELECTION_METRIC_VERSION,
        "split_identity": split_identity,
        "article_ids": [row["article_id"] for row in normalized_articles],
        "articles": normalized_articles,
        "metric_component_inventory": {
            "E": list(E_COMPONENTS), "participant_roles": list(PARTICIPANT_ROLES),
            "R": list(R_COMPONENTS), "P": "PRIMARY_STRICT_NON_TIE_PAIRWISE_ACCURACY",
        },
        "component_support": normalized_support,
        "primary_strict_non_tie_support": primary_strict_non_tie_support,
        "test_access_count": test_access_count,
        "test_ledger_state": "CLOSED_UNREAD",
    }
    return {**body, "manifest_sha256": json_digest(body)}


def validate_support_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or "manifest_sha256" not in value:
        raise ValueError("selection support manifest is missing")
    body = {key: item for key, item in value.items() if key != "manifest_sha256"}
    if (value.get("schema_version") != SUPPORT_MANIFEST_VERSION
            or value.get("selection_contract_version") != SELECTION_POLICY_VERSION
            or value.get("selection_metric_version") != SELECTION_METRIC_VERSION
            or value.get("test_access_count") != 0
            or value.get("test_ledger_state") != "CLOSED_UNREAD"
            or value.get("manifest_sha256") != json_digest(body)):
        raise ValueError("selection support manifest policy/digest differs")
    rebuilt = build_support_manifest(
        split_identity=value["split_identity"], articles=value["articles"],
        component_support={name: {"positive": row["positive"],
                                  "negative": row["negative"]}
                           for name, row in value["component_support"].items()},
        primary_strict_non_tie_support=value["primary_strict_non_tie_support"],
        test_access_count=value["test_access_count"])
    if rebuilt != dict(value):
        raise ValueError("selection support manifest canonical form differs")
    return rebuilt


def average_precision_with_retrieval_misses(
        rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Integrate only retrieved score groups while misses stay in the recall denominator."""
    finite_groups: dict[float, list[bool]] = {}
    missed_positive = 0
    negative = 0
    seen_ids = set()
    for row in rows:
        if set(row) != {"pair_id", "label", "score", "retrieval_miss"}:
            raise ValueError("selection AP row schema differs")
        pair_id = str(row["pair_id"])
        if pair_id in seen_ids:
            raise ValueError("selection AP pair IDs must be unique")
        seen_ids.add(pair_id)
        label, miss, score = row["label"], row["retrieval_miss"], row["score"]
        if not isinstance(label, bool) or not isinstance(miss, bool):
            raise ValueError("selection AP labels/miss flags must be boolean")
        negative += int(not label)
        if miss:
            if score is not None:
                raise ValueError("retrieval misses must have a null score")
            missed_positive += int(label)
        else:
            if not isinstance(score, (float, int)) or not math.isfinite(score):
                raise ValueError("retrieved selection scores must be finite")
            finite_groups.setdefault(float(score), []).append(label)
    positive = missed_positive + sum(sum(group) for group in finite_groups.values())
    tp = fp = 0
    previous_recall = 0.0
    ap = 0.0
    for score in sorted(finite_groups, reverse=True):
        group = finite_groups[score]
        tp += sum(group)
        fp += len(group) - sum(group)
        if positive:
            recall = tp / positive
            ap += (recall - previous_recall) * (tp / (tp + fp))
            previous_recall = recall
    return {
        "status": "DEFINED" if positive and negative else "UNDEFINED",
        "value": float(ap) if positive and negative else None,
        "reason": None if positive and negative else "AP_REQUIRES_BOTH_CLASSES",
        "support": {"positive": positive, "negative": negative,
                    "total": positive + negative},
        "retrieval_miss_positive": missed_positive,
        "score_encoding": "FINITE_RETRIEVED_ONLY_MISSES_IN_RECALL_DENOMINATOR",
        "metric_version": SELECTION_METRIC_VERSION,
    }


def primary_strict_ordering_metric(
        gold_pairs: Iterable[tuple[str, str, bool | None]],
        scores: Mapping[str, float]) -> dict[str, int]:
    """All Gold strict non-tie pairs; score ties are wrong, missing scores invalidate."""
    correct = wrong = ignored = missing = 0
    for left, right, preferred in gold_pairs:
        if preferred is None:
            ignored += 1
            continue
        if left not in scores or right not in scores:
            missing += 1
            continue
        left_score, right_score = scores[left], scores[right]
        if (not math.isfinite(left_score) or not math.isfinite(right_score)):
            missing += 1
            continue
        is_correct = ((left_score > right_score) == preferred
                      and left_score != right_score)
        correct += int(is_correct)
        wrong += int(not is_correct)
    return {"strict_correct": correct, "strict_wrong": wrong,
            "strict_total": correct + wrong + missing,
            "ties_ignored": ignored, "missing_score_count": missing}


def _valid_ap(row: Mapping[str, Any], *, name: str,
              expected: Mapping[str, int]) -> tuple[float | None, str | None]:
    support = row.get("support")
    if support != expected:
        return None, f"{name}:SUPPORT_MISMATCH"
    if expected["positive"] <= 0 or expected["negative"] <= 0:
        return None, f"{name}:MANIFEST_REQUIRES_BOTH_CLASSES"
    value = row.get("value")
    misses = row.get("retrieval_miss_positive", 0)
    if (not isinstance(misses, int) or isinstance(misses, bool)
            or misses < 0 or misses > expected["positive"]):
        return None, f"{name}:RETRIEVAL_MISS_PROVENANCE_MISMATCH"
    if row.get("status") != "DEFINED" or not isinstance(value, (float, int)) \
            or isinstance(value, bool) or not math.isfinite(value) \
            or not 0.0 <= float(value) <= 1.0 or row.get("reason") is not None:
        return None, f"{name}:MISSING_OR_NONFINITE_AP"
    return float(value), None


def _canonical_ap_component(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep enough JSON-safe evidence for a reader to recompute E/R exactly."""
    row = row or {}
    value = row.get("value")
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        value = None
    support = row.get("support")
    support = dict(support) if isinstance(support, Mapping) else None
    misses = row.get("retrieval_miss_positive", 0)
    if not isinstance(misses, int) or misses < 0:
        misses = None
    return {
        "status": row.get("status"),
        "value": float(value) if value is not None else None,
        "reason": row.get("reason"),
        "support": support,
        "retrieval_miss_positive": misses,
    }


def build_epoch_selection_artifact(*, epoch: int, checkpoint_sha256: str,
                                   support_manifest: Mapping[str, Any],
                                   ap_components: Mapping[str, Mapping[str, Any]],
                                   primary: Mapping[str, Any],
                                   dev_total_multitask_loss: float,
                                   test_access_count: int = 0) -> dict[str, Any]:
    """Validate E/R/P and build one JSON-safe epoch selection sidecar."""
    manifest = validate_support_manifest(support_manifest)
    _sha(checkpoint_sha256, field="epoch_checkpoint_sha256")
    if (not isinstance(test_access_count, int) or isinstance(test_access_count, bool)
            or test_access_count < 0):
        raise ValueError("epoch test access count must be a nonnegative integer")
    reasons: list[str] = []
    if epoch not in range(1, 7):
        reasons.append("EPOCH_OUTSIDE_PLANNED_RANGE")
    if test_access_count != 0:
        reasons.append("TEST_ACCESS_OCCURRED")
    if set(ap_components) != set(AP_SUPPORT_COMPONENTS):
        reasons.append("AP_COMPONENT_INVENTORY_MISMATCH")
    values: dict[str, float] = {}
    for name in AP_SUPPORT_COMPONENTS:
        if name not in ap_components:
            continue
        expected = manifest["component_support"][name]
        value, reason = _valid_ap(ap_components[name], name=name, expected=expected)
        if reason:
            reasons.append(reason)
        else:
            values[name] = value  # type: ignore[assignment]
    participant_values = [values.get(f"E.PARTICIPANT.{role}")
                          for role in PARTICIPANT_ROLES]
    participant = (sum(participant_values) / 3
                   if all(value is not None for value in participant_values) else None)
    e_values = [values.get(f"E.{name}") for name in E_COMPONENTS[:-1]] + [participant]
    r_values = [values.get(f"R.{name}") for name in R_COMPONENTS]
    e = sum(e_values) / 6 if all(value is not None for value in e_values) else None
    r = sum(r_values) / 7 if all(value is not None for value in r_values) else None
    required_primary = {"strict_correct", "strict_wrong", "strict_total",
                        "ties_ignored", "missing_score_count"}
    if set(primary) != required_primary:
        reasons.append("PRIMARY_SCHEMA_MISMATCH")
        p = None
    else:
        total = primary["strict_total"]
        counts_valid = all(isinstance(primary[name], int) and primary[name] >= 0
                           for name in required_primary)
        if (not counts_valid or not isinstance(total, int) or total <= 0
                or total != manifest["primary_strict_non_tie_support"]
                or primary["strict_correct"] + primary["strict_wrong"]
                + primary["missing_score_count"] != total
                or primary["missing_score_count"] != 0):
            reasons.append("PRIMARY_SUPPORT_OR_SCORE_MISMATCH")
            p = None
        else:
            p = primary["strict_correct"] / total
    if not isinstance(dev_total_multitask_loss, (float, int)) \
            or not math.isfinite(dev_total_multitask_loss):
        reasons.append("DEV_TOTAL_MULTITASK_LOSS_NONFINITE")
    raw_tuple = (None if e is None or r is None or p is None or reasons else
                 [min(e, r), .5 * (e + r), p,
                  -float(dev_total_multitask_loss), -epoch])
    return {
        "schema_version": SELECTION_ARTIFACT_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "selection_metric_version": SELECTION_METRIC_VERSION,
        "epoch": epoch,
        "epoch_checkpoint_sha256": checkpoint_sha256,
        "support_manifest_sha256": manifest["manifest_sha256"],
        "component_metrics": {name: _canonical_ap_component(ap_components.get(name))
                              for name in AP_SUPPORT_COMPONENTS},
        "primary_counts": ({name: primary[name] for name in sorted(required_primary)}
                           if set(primary) == required_primary else None),
        "participant_role_macro_ap": participant,
        "E": e, "R": r, "P": p,
        "dev_total_multitask_loss": (float(dev_total_multitask_loss)
                                      if isinstance(dev_total_multitask_loss, (int, float))
                                      and math.isfinite(dev_total_multitask_loss) else None),
        "raw_selection_tuple": raw_tuple,
        "selectable": raw_tuple is not None,
        "reasons": sorted(set(reasons)),
        "tolerance": SELECTION_TOLERANCE,
        "service_ready": False,
        "production_approved": False,
        "test_access_count": test_access_count,
    }


def validate_epoch_selection_artifact(
        value: Mapping[str, Any], *, support_manifest: Mapping[str, Any],
        expected_epoch: int | None = None,
        expected_checkpoint_sha256: str | None = None) -> dict[str, Any]:
    """Rebuild an epoch artifact; never trust caller-provided flags or tuple values."""
    manifest = validate_support_manifest(support_manifest)
    required = {
        "schema_version", "selection_policy_version", "selection_metric_version",
        "epoch", "epoch_checkpoint_sha256", "support_manifest_sha256",
        "component_metrics", "primary_counts", "participant_role_macro_ap",
        "E", "R", "P", "dev_total_multitask_loss", "raw_selection_tuple",
        "selectable", "reasons", "tolerance", "service_ready",
        "production_approved", "test_access_count",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("epoch selection artifact schema differs")
    if (value.get("schema_version") != SELECTION_ARTIFACT_VERSION
            or value.get("selection_policy_version") != SELECTION_POLICY_VERSION
            or value.get("selection_metric_version") != SELECTION_METRIC_VERSION
            or value.get("support_manifest_sha256") != manifest["manifest_sha256"]):
        raise ValueError("epoch selection artifact policy/manifest differs")
    epoch = value.get("epoch")
    checkpoint_sha = _sha(value.get("epoch_checkpoint_sha256"),
                          field="epoch_checkpoint_sha256")
    if expected_epoch is not None and epoch != expected_epoch:
        raise ValueError("epoch selection artifact epoch differs")
    if (expected_checkpoint_sha256 is not None
            and checkpoint_sha != expected_checkpoint_sha256):
        raise ValueError("epoch selection artifact checkpoint SHA differs")
    metrics = value.get("component_metrics")
    primary = value.get("primary_counts")
    if not isinstance(metrics, Mapping) or not isinstance(primary, Mapping):
        raise ValueError("epoch selection artifact metric evidence is missing")
    rebuilt = build_epoch_selection_artifact(
        epoch=epoch, checkpoint_sha256=checkpoint_sha,
        support_manifest=manifest, ap_components=metrics, primary=primary,
        dev_total_multitask_loss=value.get("dev_total_multitask_loss"),
        test_access_count=value.get("test_access_count"))
    if rebuilt != dict(value):
        raise ValueError("epoch selection artifact derived fields are inconsistent")
    return rebuilt


def compare_selection_artifacts(left: Mapping[str, Any],
                                right: Mapping[str, Any]) -> dict[str, Any]:
    """Return a tolerance-aware comparison trace; winner is left/right/tie."""
    if not left.get("selectable") or not right.get("selectable"):
        raise ValueError("only selectable epochs may be compared")
    a, b = left["raw_selection_tuple"], right["raw_selection_tuple"]
    trace = []
    names = ("weakest_group", "group_mean", "primary", "negative_dev_loss",
             "negative_epoch")
    winner = "tie"
    for index, name in enumerate(names):
        difference = float(a[index]) - float(b[index])
        tied = abs(difference) <= SELECTION_TOLERANCE
        trace.append({"component": name, "left": float(a[index]),
                      "right": float(b[index]), "difference": difference,
                      "tolerance_tie": tied})
        if not tied:
            winner = "left" if difference > 0 else "right"
            break
    return {"winner": winner, "tolerance": SELECTION_TOLERANCE, "trace": trace}


def select_best_epoch(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selectable = [dict(row) for row in artifacts if row.get("selectable")]
    if not selectable:
        return {"status": "NO_SELECTABLE_CHECKPOINT", "selected_epoch": None,
                "selected_checkpoint_sha256": None, "comparison_trace": [],
                "latest_fallback_used": False}
    best = selectable[0]
    traces = []
    for candidate in selectable[1:]:
        comparison = compare_selection_artifacts(candidate, best)
        traces.append({"challenger_epoch": candidate["epoch"],
                       "incumbent_epoch": best["epoch"], **comparison})
        if comparison["winner"] == "left":
            best = candidate
    return {"status": "SELECTED", "selected_epoch": best["epoch"],
            "selected_checkpoint_sha256": best["epoch_checkpoint_sha256"],
            "comparison_trace": traces, "latest_fallback_used": False}


def build_selection_ledger(
        artifacts: Sequence[Mapping[str, Any]], *, run_status: str,
        predicted_dev_cascade_count: int,
        support_manifest: Mapping[str, Any],
        checkpoint_sha_by_epoch: Mapping[int, str]) -> dict[str, Any]:
    """Validate every epoch sidecar and derive run contamination monotonically."""
    manifest = validate_support_manifest(support_manifest)
    if run_status not in ("COMPLETE", "INCOMPLETE_SAFETY_STOP"):
        raise ValueError("unknown D8 run status")
    validated = [validate_epoch_selection_artifact(
        row, support_manifest=manifest, expected_epoch=row.get("epoch"),
        expected_checkpoint_sha256=checkpoint_sha_by_epoch.get(row.get("epoch")))
        for row in artifacts]
    if set(checkpoint_sha_by_epoch) != {row["epoch"] for row in validated}:
        raise ValueError("checkpoint inventory differs from epoch artifacts")
    if run_status == "COMPLETE" and [row.get("epoch") for row in artifacts] != list(range(1, 7)):
        raise ValueError("normal D8 selection requires all six epoch artifacts")
    if run_status != "COMPLETE":
        selection = {"status": "INCOMPLETE_SAFETY_STOP", "selected_epoch": None,
                     "selected_checkpoint_sha256": None,
                     "comparison_trace": [], "latest_fallback_used": False}
    else:
        selection = select_best_epoch(validated)
    test_access_count = sum(row["test_access_count"] for row in validated)
    if test_access_count != 0:
        selection = {"status": "RUN_INVALID_TEST_ACCESS", "selected_epoch": None,
                     "selected_checkpoint_sha256": None,
                     "comparison_trace": [], "latest_fallback_used": False}
    allowed_cascades = 1 if selection["status"] == "SELECTED" else 0
    if predicted_dev_cascade_count < 0 or predicted_dev_cascade_count > allowed_cascades:
        raise ValueError("predicted dev cascade count violates D8 ordering/budget")
    return {"schema_version": SELECTION_LEDGER_VERSION,
            "selection_policy": selection_policy(),
            "selection_metric_version": SELECTION_METRIC_VERSION,
            "support_manifest_sha256": manifest["manifest_sha256"],
            "run_status": run_status,
            "epoch_artifacts": validated, **selection,
            "best_materialization_contract":
                "BYTE_FOR_BYTE_COPY_OR_EXPLICIT_REFERENCE_TO_SELECTED_EPOCH_SHA",
            "predicted_dev_cascade_count": predicted_dev_cascade_count,
            "test_access_count": test_access_count, "test_evaluation_count": 0,
            "service_ready": False, "production_approved": False}


def validate_selection_ledger(
        value: Mapping[str, Any], *, support_manifest: Mapping[str, Any],
        checkpoint_sha_by_epoch: Mapping[int, str],
        previous_ledger: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Reader-side canonical validation, including persisted contamination/cascade count."""
    required = {
        "schema_version", "selection_policy", "selection_metric_version",
        "support_manifest_sha256", "run_status", "epoch_artifacts", "status",
        "selected_epoch", "selected_checkpoint_sha256", "comparison_trace",
        "latest_fallback_used", "best_materialization_contract",
        "predicted_dev_cascade_count", "test_access_count",
        "test_evaluation_count", "service_ready", "production_approved",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("selection ledger schema differs")
    if (value.get("schema_version") != SELECTION_LEDGER_VERSION
            or value.get("selection_policy") != selection_policy()
            or value.get("selection_metric_version") != SELECTION_METRIC_VERSION):
        raise ValueError("selection ledger policy differs")
    rebuilt = build_selection_ledger(
        value["epoch_artifacts"], run_status=value["run_status"],
        predicted_dev_cascade_count=value["predicted_dev_cascade_count"],
        support_manifest=support_manifest,
        checkpoint_sha_by_epoch=checkpoint_sha_by_epoch)
    if rebuilt != dict(value):
        raise ValueError("selection ledger derived fields are inconsistent")
    if previous_ledger is not None:
        previous_cascades = previous_ledger.get("predicted_dev_cascade_count")
        previous_test_access = previous_ledger.get("test_access_count")
        if (not isinstance(previous_cascades, int)
                or not isinstance(previous_test_access, int)
                or value["predicted_dev_cascade_count"] < previous_cascades
                or value["test_access_count"] < previous_test_access):
            raise ValueError("selection ledger monotonic audit state was reset")
    return rebuilt


def execute_selection_orchestration(*, epochs: Sequence[int],
                                    support_manifest: Mapping[str, Any],
                                    save_checkpoint: Callable[[int], str],
                                    evaluate_checkpoint: Callable[[int, str], Mapping[str, Any]],
                                    save_selection_artifact: Callable[[Mapping[str, Any]], None],
                                    predicted_dev_cascade: Callable[[int, str], None],
                                    existing_ledger: Mapping[str, Any] | None = None,
                                    run_status: str = "COMPLETE") -> dict[str, Any]:
    """Immutable-checkpoint order plus fail-closed artifact/ledger validation."""
    frozen_manifest = validate_support_manifest(support_manifest)
    if tuple(epochs) != tuple(range(1, 7)):
        raise ValueError("D8 normal orchestration requires epochs 1..6")
    artifacts = []
    checkpoint_shas: dict[int, str] = {}
    for epoch in epochs:
        checkpoint_sha = _sha(save_checkpoint(epoch), field="epoch_checkpoint_sha256")
        checkpoint_shas[epoch] = checkpoint_sha
        artifact = validate_epoch_selection_artifact(
            evaluate_checkpoint(epoch, checkpoint_sha),
            support_manifest=frozen_manifest, expected_epoch=epoch,
            expected_checkpoint_sha256=checkpoint_sha)
        save_selection_artifact(artifact)
        artifacts.append(artifact)
    ledger = build_selection_ledger(
        artifacts, run_status=run_status, predicted_dev_cascade_count=0,
        support_manifest=frozen_manifest,
        checkpoint_sha_by_epoch=checkpoint_shas)
    if existing_ledger is not None:
        persisted = validate_selection_ledger(
            existing_ledger, support_manifest=frozen_manifest,
            checkpoint_sha_by_epoch=checkpoint_shas)
        if (persisted["epoch_artifacts"] != ledger["epoch_artifacts"]
                or persisted["status"] != ledger["status"]):
            raise ValueError("persisted selection ledger belongs to another run")
        if persisted["predicted_dev_cascade_count"] == 1:
            return persisted
    if ledger["status"] == "SELECTED":
        predicted_dev_cascade(ledger["selected_epoch"],
                              ledger["selected_checkpoint_sha256"])
        ledger = build_selection_ledger(
            artifacts, run_status=run_status, predicted_dev_cascade_count=1,
            support_manifest=frozen_manifest,
            checkpoint_sha_by_epoch=checkpoint_shas)
    return ledger


def checkpoint_selection_contract(*, support_manifest_sha256: str,
                                  epoch: int,
                                  test_access_count: int,
                                  gradient_clipping_summary: Mapping[str, Any] | None = None
                                  ) -> dict[str, Any]:
    """Metadata embedded in an immutable pre-evaluation epoch checkpoint."""
    _sha(support_manifest_sha256, field="support_manifest_sha256")
    if epoch not in range(1, 7):
        raise ValueError("D8 epoch checkpoint must be in 1..6")
    if (not isinstance(test_access_count, int) or isinstance(test_access_count, bool)
            or test_access_count != 0):
        raise ValueError("D8 epoch checkpoint requires observed zero test access")
    summary = dict(gradient_clipping_summary or {
        "groups": 0, "cumulative_clipped_count": 0,
        "max_global_grad_norm_pre": 0.0, "max_global_grad_norm_post": 0.0,
        "nonfinite_owner_count": 0, "zero_gradient_owner_observations": 0,
    })
    if (set(summary) != {"groups", "cumulative_clipped_count",
                         "max_global_grad_norm_pre", "max_global_grad_norm_post",
                         "nonfinite_owner_count", "zero_gradient_owner_observations"}
            or any(not isinstance(summary[name], int) or summary[name] < 0
                   for name in ("groups", "cumulative_clipped_count",
                                "nonfinite_owner_count",
                                "zero_gradient_owner_observations"))
            or any(not isinstance(summary[name], (int, float))
                   or not math.isfinite(summary[name]) or summary[name] < 0
                   for name in ("max_global_grad_norm_pre",
                                "max_global_grad_norm_post"))):
        raise ValueError("D8 gradient clipping summary schema differs")
    body = {
        "selection_policy": selection_policy(),
        "support_manifest_sha256": support_manifest_sha256,
        "epoch": epoch,
        "checkpoint_role": "IMMUTABLE_PRE_EVALUATION_EPOCH",
        "selection_metrics_present": False,
        "final_selected_epoch": None,
        "service_ready": False,
        "production_approved": False,
        "predicted_dev_cascade_count": 0,
        "test_access_count": test_access_count,
        "loss_reduction_contract_version": LOSS_REDUCTION_CONTRACT_VERSION,
        "gradient_clipping_contract": {
            "version": GRADIENT_CLIP_CONTRACT_VERSION, "max_grad_norm": 1.0,
            "pre_post_owner_observability_required": True,
        },
        "gradient_clipping_summary": summary,
    }
    return {**body, "metadata_sha256": json_digest(body)}


def validate_checkpoint_selection_contract(value: Mapping[str, Any], *,
                                           expected_manifest_sha256: str | None = None,
                                           expected_epoch: int | None = None) -> dict[str, Any]:
    required = {"selection_policy", "support_manifest_sha256", "epoch",
                "checkpoint_role", "selection_metrics_present", "final_selected_epoch",
                "service_ready", "production_approved", "predicted_dev_cascade_count",
                "test_access_count", "loss_reduction_contract_version",
                "gradient_clipping_contract", "metadata_sha256"}
    required.add("gradient_clipping_summary")
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("D8 checkpoint selection metadata schema differs")
    try:
        policy = D8SelectionPolicy(**{
            **value["selection_policy"],
            "planned_epochs": tuple(value["selection_policy"]["planned_epochs"]),
        })
    except (KeyError, TypeError) as error:
        raise ValueError("D8 checkpoint selection policy schema differs") from error
    policy.validate()
    manifest_sha = _sha(value["support_manifest_sha256"], field="support_manifest_sha256")
    if (expected_manifest_sha256 is not None and manifest_sha != expected_manifest_sha256):
        raise ValueError("D8 checkpoint support manifest digest differs")
    if expected_epoch is not None and value["epoch"] != expected_epoch:
        raise ValueError("D8 checkpoint epoch differs")
    expected = checkpoint_selection_contract(
        support_manifest_sha256=manifest_sha, epoch=value["epoch"],
        test_access_count=value["test_access_count"],
        gradient_clipping_summary=value["gradient_clipping_summary"])
    if dict(value) != expected:
        raise ValueError("D8 checkpoint selection policy/state/digest differs")
    return expected


def bounded_rehearsal_policy() -> dict[str, Any]:
    return {
        "version": REHEARSAL_POLICY_VERSION,
        "article_ids": list(REHEARSAL_ARTICLE_IDS),
        "fresh_weights": True, "warm_start": False, "resume": False,
        "seed": 1008, "required_device": "mps", "cpu_fallback": False,
        "max_optimizer_steps": 32, "hard_wall_time_seconds": 1800,
        "test49_reads": 0, "new500_reads": 0, "dev_tuning": False,
        "execution_authorized": False,
        "authorization_status": "REQUIRES_EXPLICIT_STAGE10_AUTHORIZATION",
    }


def validate_bounded_rehearsal_policy(value: Mapping[str, Any]) -> None:
    if dict(value) != bounded_rehearsal_policy():
        raise ValueError("bounded rehearsal policy differs from approved static limits")
