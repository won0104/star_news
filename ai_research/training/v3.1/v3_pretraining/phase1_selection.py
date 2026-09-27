"""Phase 1 extraction-only checkpoint selection, before source calibration.

Evaluation support is external, fixed before training, and independent of model
scores. Missing retrieved Gold positives remain in the AP denominator.
"""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping

from runtime.v3_pretraining.acceptance import V23_TRIGGER_FINE_RAW_SCORE_VERSION
from training.v3_pretraining.max6_schedule import MAX_EPOCHS, schedule_sha256
from training.v3_pretraining.selection_contract import (
    E_COMPONENTS, PARTICIPANT_ROLES, SELECTION_TOLERANCE,
    average_precision_with_retrieval_misses)
from training.v3_pretraining.selection_evaluation import (
    EXTRACTION_EVAL_AUTHORITY_VERSION, ExtractionEvaluationAuthority)


POLICY_VERSION = "PHASE1_EXTRACTION_MAX6_TRIGGER_EXACT_SCORE_V2"
GOLD400_POLICY_VERSION = "GOLD400_PHASE1_TRIGGER_EXACT_RAW_E_V2"
AUTHORITY_VERSION = "v23-phase1-extraction-dev15-eval-authority-v1"
RAW_CANDIDATE_POLICY_VERSION = "v23-phase1-threshold-free-candidates-v3"
SUPPORT_MANIFEST_VERSION = "v23-phase1-selection-support-manifest-v1"
COMPONENTS = tuple(f"E.{name}" for name in E_COMPONENTS[:-1]) + tuple(
    f"E.PARTICIPANT.{role}" for role in PARTICIPANT_ROLES)


def file_sha256(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def selection_retrieval_budget():
    """Frozen raw-score candidate topology; chunk size changes memory only."""
    from runtime.v3_pretraining.extraction_decode import RetrievalBudget
    return RetrievalBudget(candidate_profile="V23_BASELINE",
                           proposal_top_k=32, max_span_tokens=96,
                           chunk_size=128)


def policy_manifest() -> dict[str, Any]:
    from dataclasses import asdict
    retrieval = selection_retrieval_budget()
    return {"version": POLICY_VERSION, "schedule_sha256": schedule_sha256(),
            "planned_epochs": list(range(1, MAX_EPOCHS + 1)),
            "selection_tuple": "(E,-dev_phase1_extraction_loss,-epoch)",
            "tolerance": SELECTION_TOLERANCE,
            "components": list(E_COMPONENTS),
            "participant_roles": list(PARTICIPANT_ROLES),
            "retrieval_miss": "positive remains in AP denominator",
            "score_source": "RAW_MODEL_SCORE_BEFORE_CALIBRATION",
            "raw_candidate_policy_version": RAW_CANDIDATE_POLICY_VERSION,
            "raw_candidate_retrieval": asdict(retrieval),
            "trigger_candidate_topology":
                "ALL_STRUCTURALLY_VALID_ENDPOINTS_GREEDY_ONE_TO_ONE_WIDTH64_MAX4_PER_SENTENCE",
            "participant_candidate_topology":
                "GOLD_EVENT_OWNER_CONDITIONED_INDEPENDENT_CARTESIAN_WIDTH49_NO_OUTPUT_CAP",
            "selection_only_endpoint_threshold": None,
            "v23_raw_score_responsibility": {
                "EVENT": "CANONICAL_SEMANTIC_RAW_LOGIT",
                "STATEMENT": "CANONICAL_SEMANTIC_RAW_LOGIT",
                "TRIGGER": V23_TRIGGER_FINE_RAW_SCORE_VERSION,
                "ENTITY": "NATIVE_FIVE_TYPE_MAX_RAW_LOGIT",
                "TIME": "NATIVE_TIME_RAW_LOGIT",
                "PARTICIPANT": "V23_EVENT_OWNER_B2_ENDPOINT_RAW_LOGIT"},
            "calibrated_thresholds_used": False,
            "selection_after_all_epochs": True}


def policy_sha256() -> str:
    return sha256(json.dumps(policy_manifest(), sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def gold400_policy_manifest() -> dict[str, Any]:
    """Selection-only raw candidate topology for the separate Gold400 schedule."""
    from training.v3_pretraining.gold400_schedule import (
        MAX_EPOCHS as GOLD400_MAX, schedule_sha256 as gold400_sha)
    result = policy_manifest()
    result.update({"version": GOLD400_POLICY_VERSION,
                   "schedule_sha256": gold400_sha(),
                   "planned_epochs": list(range(1, GOLD400_MAX + 1)),
                   "selection_after_all_epochs": False,
                   "early_stopping_patience": 3})
    return result


def gold400_policy_sha256() -> str:
    return sha256(json.dumps(gold400_policy_manifest(), sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def load_dev_authority(path: str | Path, *, gold_sha256: str,
                       split_sha256: str, dev_ids: tuple[str, ...],
                       gold400: bool = False
                       ) -> dict[str, ExtractionEvaluationAuthority]:
    """Load separately approved, frozen dev15 candidate labels; never infer negatives."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or set(data) != {
            "schema_version", "selection_status", "gold_sha256", "split_sha256",
            "article_ids", "articles", "provenance"}
            or data["schema_version"] != ("v23-gold400-phase1-dev49-eval-authority-v1"
                                           if gold400 else AUTHORITY_VERSION)
            or data["selection_status"] != "APPROVED_EXTERNAL"
            or data["gold_sha256"] != gold_sha256
            or data["split_sha256"] != split_sha256
            or data["article_ids"] != list(dev_ids)
            or not isinstance(data["provenance"], dict)
            or data["provenance"].get("approval_basis") != (
                "USER_FROZEN_GOLD400_EXPLICIT_LABELS_AFTER_CONFLICT_AUDIT"
                if gold400 else "USER_APPROVED_DEV_SELECTION_AFTER_GOLD_CONFLICT_AUDIT")
            or data["provenance"].get("gold_conflicts") != 0
            or data["provenance"].get("test_article_loads") != 0
            or not isinstance(data["articles"], dict)
            or set(data["articles"]) != set(dev_ids)):
        raise ValueError("Phase 1 dev15 evaluation authority absent, unapproved, or drifted")
    output = {}
    for article_id in dev_ids:
        row = data["articles"][article_id]
        if not isinstance(row, dict) or set(row) != {"authority_id", "component_rows"}:
            raise ValueError("Phase 1 dev evaluation row schema differs")
        authority = ExtractionEvaluationAuthority(
            EXTRACTION_EVAL_AUTHORITY_VERSION, row["authority_id"],
            "APPROVED_EXTERNAL", article_id,
            {key: tuple(value) for key, value in row["component_rows"].items()})
        authority.validate()
        output[article_id] = authority
    return output


def load_support_manifest(path: str | Path, *, authority_path: str | Path,
                          gold_sha256: str, split_sha256: str,
                          gold400: bool = False,
                          expected_policy: dict | None = None) -> dict:
    row = json.loads(Path(path).read_text(encoding="utf-8"))
    policy = (expected_policy if expected_policy is not None else
              (gold400_policy_manifest() if gold400 else policy_manifest()))
    policy_digest = sha256(json.dumps(policy, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()
    if (not isinstance(row, dict) or set(row) != {
            "schema_version", "selection_status", "authority_sha256",
            "selection_policy", "selection_policy_sha256", "gold_sha256",
            "split_sha256", "dev_article_count", "test_access_count"}
            or row["schema_version"] != ("v23-gold400-phase1-selection-support-v1"
                                          if gold400 else SUPPORT_MANIFEST_VERSION)
            or row["selection_status"] != "FROZEN_BEFORE_EPOCH1"
            or row["authority_sha256"] != file_sha256(authority_path)
            or row["selection_policy"] != policy
            or row["selection_policy_sha256"] != policy_digest
            or row["gold_sha256"] != gold_sha256
            or row["split_sha256"] != split_sha256
            or row["dev_article_count"] != (49 if gold400 else 15)
            or row["test_access_count"] != 0):
        raise ValueError("Phase 1 selection support manifest/policy bytes drifted")
    return row


def validate_gold_positive_coverage(
        authorities: Mapping[str, ExtractionEvaluationAuthority],
        dev_articles: tuple) -> None:
    """Require every dev Gold positive in fixed E support before any model score."""
    if set(authorities) != {article.raw.article_id for article in dev_articles}:
        raise ValueError("dev authority/article inventory differs")
    for article in dev_articles:
        gold = article.annotations
        expected: dict[str, set[tuple[str | None, int, int]]] = {
            name: set() for name in COMPONENTS}
        for kind, key in (("EVENT", "events"), ("STATEMENT", "statements"),
                          ("ENTITY", "entity_mentions"), ("TIME", "time_mentions")):
            for item in gold[key]:
                span = item["span"]
                expected[f"E.{kind}"].add((None, span["start"], span["end"]))
        for event in gold["events"]:
            owner = event["event_id"]
            span = event["trigger"]
            expected["E.TRIGGER"].add((None, span["start"], span["end"]))
            for role, key in (("ACTOR", "actors"), ("TARGET", "targets"),
                              ("PLACE", "places")):
                for item in event[key]:
                    span = item["span"]
                    expected[f"E.PARTICIPANT.{role}"].add(
                        (owner, span["start"], span["end"]))
        for component, rows in authorities[article.raw.article_id].component_rows.items():
            actual = {(row["owner_id"], row["start"], row["end"])
                      for row in rows if row["label"]}
            if actual != expected[component]:
                raise ValueError(f"{article.raw.article_id}:{component}: Gold positive support differs")


def extraction_components(rows: Mapping[str, list[Mapping[str, Any]]]) -> dict:
    if set(rows) != set(COMPONENTS):
        raise ValueError("Phase 1 Extraction component inventory differs")
    metrics = {name: average_precision_with_retrieval_misses(rows[name])
               for name in COMPONENTS}
    if any(row["status"] != "DEFINED" for row in metrics.values()):
        raise ValueError("Phase 1 Extraction AP support is undefined")
    participant = sum(metrics[f"E.PARTICIPANT.{role}"]["value"]
                      for role in PARTICIPANT_ROLES) / len(PARTICIPANT_ROLES)
    values = {name: metrics[f"E.{name}"]["value"] for name in E_COMPONENTS[:-1]}
    values["PARTICIPANT"] = participant
    return {"component_ap": metrics, "participant_macro_ap": participant,
            "E": sum(values.values()) / len(E_COMPONENTS),
            "retrieval_miss_positive": {name: row["retrieval_miss_positive"]
                                        for name, row in metrics.items()}}


def select_completed_epochs(records: list[Mapping[str, Any]], *,
                            expected_epochs: int = MAX_EPOCHS,
                            expected_policy: dict | None = None,
                            schedule_contract: str | None = None) -> dict:
    """Recheck immutable checkpoint bytes, then apply the pre-frozen Phase 1 key."""
    policy = expected_policy if expected_policy is not None else policy_manifest()
    policy_digest = sha256(json.dumps(policy, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()
    if (expected_epochs < 1 or len(records) != expected_epochs or
            [row.get("epoch") for row in records] != list(range(1, expected_epochs + 1))):
        raise ValueError("all six epoch selection records are required" if
                         expected_epochs == MAX_EPOCHS else
                         "complete rehearsal epoch selection records are required")
    best = None
    for row in records:
        path = Path(row["checkpoint_path"])
        if (file_sha256(path) != row.get("checkpoint_sha256")
                or row.get("selection_policy_sha256") != policy_digest
                or row.get("checkpoint_selection_used_calibrated_thresholds") is not False
                or row.get("test_access_count") != 0):
            raise ValueError("epoch checkpoint/selection/test binding differs")
        score = row.get("E")
        loss = row.get("dev_phase1_extraction_loss")
        if (not isinstance(score, (int, float)) or not math.isfinite(score)
                or not isinstance(loss, (int, float)) or not math.isfinite(loss)):
            raise ValueError("NO_SELECTABLE_PHASE1_CHECKPOINT")
        if best is None or score > best["E"] + SELECTION_TOLERANCE or (
                abs(score - best["E"]) <= SELECTION_TOLERANCE and
                (loss < best["dev_phase1_extraction_loss"] - SELECTION_TOLERANCE or
                 abs(loss - best["dev_phase1_extraction_loss"]) <= SELECTION_TOLERANCE
                 and row["epoch"] < best["epoch"])):
            best = row
    selected = {"phase": "extraction", "selection_policy": policy,
            "selection_policy_sha256": policy_digest,
            "selected_epoch": best["epoch"],
            "selected_checkpoint_path": best["checkpoint_path"],
            "selected_checkpoint_sha256": best["checkpoint_sha256"],
            "E": best["E"],
            "dev_phase1_extraction_loss": best["dev_phase1_extraction_loss"],
            "checkpoint_selection_used_calibrated_thresholds": False,
            "all_six_epochs_complete": True, "test_access_count": 0}
    if expected_epochs != MAX_EPOCHS:
        selected.pop("all_six_epochs_complete")
        selected["completed_epochs"] = expected_epochs
        if schedule_contract is None:
            raise ValueError("nonstandard epoch selection needs schedule contract")
        selected["schedule_contract"] = schedule_contract
    return selected
