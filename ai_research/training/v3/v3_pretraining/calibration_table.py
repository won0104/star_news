"""Selected-checkpoint raw-score contract and model-free threshold replay.

Collection belongs to a separate predicted evaluator. This module accepts only
already scored candidates, then joins existing dev Gold authority and sweeps
thresholds without importing or invoking a model. Structure-changing lanes
remain provisional until one selected-point runtime replay is validated.
"""

from __future__ import annotations

from hashlib import sha256
import inspect
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from runtime.v3_pretraining.source_layout import RawArticle
from training.experiments.v3_posttraining_selected_v1.quality import ranking_quality

from models.v3_pretraining.task_contract import PHASE_TASKS
from training.v3_pretraining.code_snapshot import (relevant_code_snapshot,
                                                   selection_code_snapshot)
from training.v3_pretraining.epoch_selection import SELECTION_CONTRACT_VERSION


SCORE_CONTRACT_VERSION = "v3-selected-checkpoint-raw-score-table-v2-unified-entity"
CALIBRATION_POLICY_VERSION = "v3-offline-threshold-replay-v3-counts-only-curve"
PREDICTED_RAW_VERSION = "v3-selected-phase-prediction-first-raw-v1-unified-entity"
GOLD400_PREDICTED_RAW_VERSION = "v3-gold400-selected-phase-prediction-first-raw-v1"
PHASE_LANES = {
    "entity_role_time_attribution_sources": (
        "ASSERTOR_SOURCE", "EVENT_TIME"),
    "entity_identity": ("ENTITY_COREFERENCE",),
    "entity_role_time_attribution": ("ASSERTOR_ENTITY",),
    "event_identity": ("EVENT_COREFERENCE",),
    "cluster_consumers": ("ABOUT", "CAUSES", "PRIMARY"),
}
CALIBRATION_UNSUPPORTED = {"PRIMARY": "NO_APPROVED_BINARY_GOLD_AUTHORITY"}
FILTER_ONLY = frozenset(("ENTITY_COREFERENCE", "EVENT_COREFERENCE",
                         "ABOUT", "CAUSES"))
STRUCTURE_CHANGING = frozenset(("ASSERTOR_SOURCE",
                                "EVENT_TIME", "ASSERTOR_ENTITY"))
AUTHORITY_STATES = frozenset(("POSITIVE", "NEGATIVE", "IGNORE"))


def _sha(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def calibration_policy_sha256() -> str:
    return _sha({"version": CALIBRATION_POLICY_VERSION,
                 "comparison": "RAW_SCORE_GTE_THRESHOLD",
                 "selection": "MAX_F0.5_THEN_HIGHER_THRESHOLD",
                 "ignored_authority": "EXCLUDED_FROM_METRIC",
                 "curve_storage": "COUNTS_ONLY_SELECTED_POINT_IDS",
                 "structure_changing": "SELECTED_POINT_RUNTIME_REPLAY_REQUIRED"})


def _selected_phase_record(*, phase: str, record: Mapping[str, Any],
                           checkpoint_path: str | Path,
                           dev_ids: Sequence[str],
                           selection_ledger_path: str | Path | None = None) -> str:
    """Bind raw collection to an immutable selected checkpoint and its dev ledger."""
    path = Path(checkpoint_path)
    if not path.is_file():
        raise ValueError("selected phase checkpoint is missing")
    checkpoint_sha = sha256(path.read_bytes()).hexdigest()
    gold400 = record.get("schedule_contract") is not None
    if gold400:
        from training.v3_pretraining.gold400_schedule import CONTRACT, inspect_epochs
        if selection_ledger_path is None:
            raise ValueError("Gold400 calibration requires the selected epoch ledger")
        ledger = json.loads(Path(selection_ledger_path).read_text(encoding="utf-8"))
        if (record.get("schedule_contract") != CONTRACT or
                not isinstance(ledger, dict) or not isinstance(ledger.get("epochs"), list) or
                inspect_epochs(ledger["epochs"], phase=phase) != record):
            raise ValueError("Gold400 selected phase epoch ledger differs")
        chosen = ledger["epochs"][record["selected_epoch"] - 1]
        selection_valid = (chosen.get("dev_ids_sha256") == _sha(tuple(dev_ids)) and
                           chosen.get("selection_code_snapshot_sha256") ==
                           selection_code_snapshot()["sha256"])
        expected_dev, max_epoch = 49, 20
    else:
        selection_valid = (
            record.get("schema_version") == SELECTION_CONTRACT_VERSION and
            record.get("dev_ids_sha256") == _sha(tuple(dev_ids)) and
            record.get("selection_code_snapshot_sha256") ==
            selection_code_snapshot()["sha256"] and
            record.get("predicted_runtime_executed") is False)
        expected_dev, max_epoch = 15, 6
    if (phase not in PHASE_LANES or len(dev_ids) != expected_dev or
            len(set(dev_ids)) != expected_dev or not selection_valid or
            record.get("phase") != phase or
            record.get("selected_epoch") not in range(1, max_epoch + 1) or
            record.get("selected_checkpoint_sha256") != checkpoint_sha or
            Path(record.get("selected_checkpoint_path", "")).resolve() != path.resolve() or
            record.get("calibration_executed") is not False or
            record.get("test_access_count") != 0):
        raise ValueError("predicted score collection needs selected phase checkpoint/dev")
    return checkpoint_sha


def collect_selected_phase_predicted_raw(
        *, phase: str, dev_articles: Sequence[RawArticle],
        predictor: Callable[[RawArticle], tuple[Mapping[str, Sequence[Mapping[str, Any]]], int]],
        access_ledger: Callable[[], Mapping[str, int]],
        selected_checkpoint_record: Mapping[str, Any],
        checkpoint_path: str | Path, source_policy_sha256: str,
        entity_pair_policy_sha256: str | None = None,
        relation_routing_policy_sha256: str | None = None,
        score_producer_sha256: str, output_path: str | Path,
        selection_ledger_path: str | Path | None = None) -> dict[str, Any]:
    """Persist raw dev scores before Gold labels become available to the join."""
    output = Path(output_path)
    ids = tuple(row.article_id for row in dev_articles)
    if (output.exists() or phase not in PHASE_LANES or
            any(not isinstance(row, RawArticle) for row in dev_articles) or
            len(source_policy_sha256) != 64 or len(score_producer_sha256) != 64 or
            ((phase == "entity_role_time_attribution_sources") ==
             (entity_pair_policy_sha256 is not None)) or
            ((phase == "cluster_consumers") !=
             (relation_routing_policy_sha256 is not None)) or
            any(len(value) != 64 for value in (
                entity_pair_policy_sha256,
                relation_routing_policy_sha256) if value is not None)):
        raise ValueError("predicted raw lane/policy/output inventory differs")
    checkpoint_sha = _selected_phase_record(
        phase=phase, record=selected_checkpoint_record,
        checkpoint_path=checkpoint_path, dev_ids=ids,
        selection_ledger_path=selection_ledger_path)
    gold400 = selected_checkpoint_record.get("schedule_contract") is not None
    expected_dev = 49 if gold400 else 15
    producer_source = inspect.getsourcefile(predictor)
    producer_path = Path(producer_source) if producer_source else None
    if (producer_path is None or not producer_path.is_file() or
            sha256(producer_path.read_bytes()).hexdigest() != score_producer_sha256):
        raise ValueError("predicted score provider source bytes differ")
    before = dict(access_ledger())
    if before.get("test") != 0 or before.get("dev") != expected_dev:
        raise ValueError("predicted raw collector needs observed dev15/test ledger"
                         if not gold400 else
                         "predicted raw collector needs observed dev49/test ledger")
    lanes = {lane: [] for lane in PHASE_LANES[phase]}
    forwards = 0
    seen = set()
    for article in dev_articles:
        produced, count = predictor(article)
        if type(count) is not int or count < 1 or set(produced) != set(lanes):
            raise ValueError("predicted raw collector needs one complete phase forward")
        forwards += count
        for lane, candidates in produced.items():
            for row in candidates:
                if (set(row) != {"article_id", "candidate_id", "score", "geometry"} or
                        row["article_id"] != article.article_id or
                        not isinstance(row["candidate_id"], str) or
                        not row["candidate_id"] or (lane, row["candidate_id"]) in seen or
                        not isinstance(row["score"], (int, float)) or
                        isinstance(row["score"], bool) or
                        not math.isfinite(row["score"]) or
                        not isinstance(row["geometry"], dict)):
                    raise ValueError("predicted raw candidate/score contract differs")
                seen.add((lane, row["candidate_id"]))
                lanes[lane].append(dict(row))
    after = dict(access_ledger())
    if after.get("test") != 0 or after.get("dev") != before["dev"]:
        raise ValueError("predicted raw collection crossed the dev/test boundary")
    artifact = {
        "schema_version": (GOLD400_PREDICTED_RAW_VERSION if gold400 else PREDICTED_RAW_VERSION),
        "evaluation_mode": "PREDICTED_RUNTIME_RAW_BEFORE_GOLD_JOIN",
        "phase": phase,
        "checkpoint_sha256": checkpoint_sha,
        "selected_checkpoint_record_sha256": _sha(selected_checkpoint_record),
        "dev_ids": list(ids), "dev_ids_sha256": _sha(ids),
        "dev_article_count": expected_dev,
        "source_policy_sha256": source_policy_sha256,
        "entity_pair_policy_sha256": entity_pair_policy_sha256,
        "relation_routing_policy_sha256": relation_routing_policy_sha256,
        "score_producer_sha256": score_producer_sha256,
        "score_producer_source_path": str(producer_path.resolve()),
        "provider_status": "CALLER_SUPPLIED_SOURCE_DIGEST_BOUND",
        "relevant_code_snapshot_sha256": relevant_code_snapshot()["sha256"],
        "gold_input_passed_to_predictor": False,
        "predictor_input_contract": "RAW_ARTICLE_ONLY",
        "article_access_ledger": after,
        "test_access_count": after["test"],
        "model_forward_count": forwards,
        "phase_predictor_calls": len(dev_articles),
        "lanes": lanes,
    }
    if not gold400:
        artifact["dev15_ids"] = list(ids)
        artifact["dev15_ids_sha256"] = _sha(ids)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, sort_keys=True,
                                 indent=2) + "\n", encoding="utf-8")
    return artifact


def calibrate_selected_phase_raw(
        *, raw_path: str | Path, lane: str,
        selected_checkpoint_record: Mapping[str, Any],
        checkpoint_path: str | Path, gold_sha256: str,
        gold_authority_by_id: Mapping[str, str],
        gold_positive_ids: Sequence[str],
        table_path: str | Path, replay_path: str | Path,
        selection_ledger_path: str | Path | None = None,
        ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Join persisted predicted scores to dev Gold, then replay without inference."""
    raw_file = Path(raw_path)
    table_file, replay_file = Path(table_path), Path(replay_path)
    if not raw_file.is_file() or table_file.exists() or replay_file.exists():
        raise ValueError("prediction-first raw artifact is absent or output already exists")
    raw = json.loads(raw_file.read_text(encoding="utf-8"))
    phase = raw.get("phase")
    gold400 = raw.get("schema_version") == GOLD400_PREDICTED_RAW_VERSION
    ids = tuple(raw.get("dev_ids" if gold400 else "dev15_ids", ()))
    expected_dev = 49 if gold400 else 15
    checkpoint_sha = _selected_phase_record(
        phase=phase, record=selected_checkpoint_record,
        checkpoint_path=checkpoint_path, dev_ids=ids,
        selection_ledger_path=selection_ledger_path)
    if (raw.get("schema_version") != (
            GOLD400_PREDICTED_RAW_VERSION if gold400 else PREDICTED_RAW_VERSION) or
            raw.get("evaluation_mode") != "PREDICTED_RUNTIME_RAW_BEFORE_GOLD_JOIN" or
            lane not in PHASE_LANES.get(phase, ()) or
            lane in CALIBRATION_UNSUPPORTED or
            set(raw.get("lanes", {})) != set(PHASE_LANES[phase]) or
            raw.get("phase_predictor_calls") != expected_dev or
            raw.get("checkpoint_sha256") != checkpoint_sha or
            raw.get("selected_checkpoint_record_sha256") !=
            _sha(selected_checkpoint_record) or
            raw.get("dev_ids_sha256" if gold400 else "dev15_ids_sha256") != _sha(ids) or
            raw.get("relevant_code_snapshot_sha256") !=
            relevant_code_snapshot()["sha256"] or
            raw.get("gold_input_passed_to_predictor") is not False or
            raw.get("predictor_input_contract") != "RAW_ARTICLE_ONLY" or
            raw.get("provider_status") != "CALLER_SUPPLIED_SOURCE_DIGEST_BOUND" or
            raw.get("test_access_count") != 0 or
            raw.get("article_access_ledger", {}).get("dev") != expected_dev or
            raw.get("article_access_ledger", {}).get("test") != 0 or
            not isinstance(raw.get("score_producer_sha256"), str) or
            len(raw["score_producer_sha256"]) != 64 or
            not Path(raw.get("score_producer_source_path", "")).is_file() or
            sha256(Path(raw["score_producer_source_path"]).read_bytes()).hexdigest() !=
            raw["score_producer_sha256"]):
        raise ValueError("prediction-first raw checkpoint/code/Gold boundary differs")
    scored = [{"candidate_id": row["candidate_id"],
               "raw_score": row["score"],
               "authority": gold_authority_by_id[row["candidate_id"]]}
              for row in raw["lanes"][lane]]
    quality = ranking_quality(scored, positive_ids=gold_positive_ids)
    if quality["average_precision_status"] != "DEFINED":
        raise ValueError("calibration needs positive and negative dev support")
    table = build_score_table(
        phase=phase, lane=lane, checkpoint_sha256=checkpoint_sha,
        dev_ids=ids, gold_sha256=gold_sha256, raw_rows=raw["lanes"][lane],
        gold_authority_by_id=gold_authority_by_id,
        gold_positive_ids=gold_positive_ids,
        source_policy_sha256=raw["source_policy_sha256"],
        entity_pair_policy_sha256=raw["entity_pair_policy_sha256"],
        relation_routing_policy_sha256=raw["relation_routing_policy_sha256"],
        selected_checkpoint_record=selected_checkpoint_record,
        checkpoint_path=checkpoint_path,
        score_collection_model_forwards=raw["model_forward_count"],
        selection_ledger_path=selection_ledger_path)
    table["prediction_first_raw_file_sha256"] = sha256(raw_file.read_bytes()).hexdigest()
    table["score_producer_sha256"] = raw["score_producer_sha256"]
    table["policy_artifact_validation"] = "NOT_EXECUTED_BY_THIS_COLLECTOR"
    table["ranking_quality"] = quality
    thresholds = sorted({row["score"] for row in raw["lanes"][lane]
                         if gold_authority_by_id[row["candidate_id"]] != "IGNORE"})
    thresholds.append(math.nextafter(thresholds[-1], math.inf))
    replay = offline_threshold_replay(table, thresholds=thresholds)
    replay["production_threshold_adopted"] = False
    for path, value in ((table_file, table), (replay_file, replay)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   indent=2) + "\n", encoding="utf-8")
    return table, replay


def phase_calibration_plan(phase: str, *, trainable_owners: Sequence[str]
                           ) -> dict[str, Any]:
    """Classify score invalidation from the staged owner inventory."""
    if phase not in PHASE_LANES or set(trainable_owners) != (
            set(PHASE_TASKS[phase]) | (
                {"document_context", "candidate_span", "exact_source_span",
                 "canonical_span"} if phase in (
                    "entity_role_time_attribution_sources",
                    "entity_role_time_attribution") else
                {"primary_adapter"} if phase == "cluster_consumers" else set())):
        raise ValueError("calibration plan needs exact phase owner inventory")
    shared_changed = "document_context" in trainable_owners
    return {
        "phase": phase,
        "raw_score_lanes": list(PHASE_LANES[phase]),
        "new_lanes": [lane for lane in PHASE_LANES[phase]
                      if lane not in CALIBRATION_UNSUPPORTED],
        "calibration_unsupported": {lane: CALIBRATION_UNSUPPORTED[lane]
                                    for lane in PHASE_LANES[phase]
                                    if lane in CALIBRATION_UNSUPPORTED},
        "upstream_score_recertification": (
            "ALL_REPRESENTATION_DEPENDENT_UPSTREAM" if shared_changed else "NONE"),
        "unchanged_upstream_calibration": (
            "REUSE_ONLY_AFTER_CHECKPOINT_AND_SCORE_PRODUCER_SHA_CHECK"
            if not shared_changed else "NO_AUTOMATIC_REUSE"),
        "dce_trainable": shared_changed,
    }


def build_score_table(*, phase: str, lane: str, checkpoint_sha256: str,
                      dev_ids: Sequence[str], gold_sha256: str,
                      raw_rows: Sequence[Mapping[str, Any]],
                      gold_authority_by_id: Mapping[str, str],
                      gold_positive_ids: Sequence[str],
                      source_policy_sha256: str,
                      entity_pair_policy_sha256: str | None = None,
                      relation_routing_policy_sha256: str | None = None,
                      selected_checkpoint_record: Mapping[str, Any],
                      checkpoint_path: str | Path,
                      score_collection_model_forwards: int,
                      final_model_calibration: bool = False,
                      frozen_selection_code_snapshot_sha256: str | None = None,
                      selection_ledger_path: str | Path | None = None,
                      test_access_count: int = 0) -> dict[str, Any]:
    """Join labels only after raw candidate scores and IDs already exist."""
    selected_phase = "cluster_consumers" if final_model_calibration else phase
    gold400 = selected_checkpoint_record.get("schedule_contract") is not None
    selected_valid = (
        _selected_phase_record(
            phase=selected_phase, record=selected_checkpoint_record,
            checkpoint_path=checkpoint_path, dev_ids=dev_ids,
            selection_ledger_path=selection_ledger_path) == checkpoint_sha256
        if gold400 else
        (selected_checkpoint_record.get("schema_version") == SELECTION_CONTRACT_VERSION and
         selected_checkpoint_record.get("phase") == selected_phase and
         selected_checkpoint_record.get("dev_ids_sha256") == _sha(tuple(dev_ids)) and
         selected_checkpoint_record.get("predicted_runtime_executed") is False))
    if (phase not in PHASE_LANES or lane not in PHASE_LANES[phase] or
            lane in CALIBRATION_UNSUPPORTED or
            not selected_valid or
            selected_checkpoint_record.get("selected_checkpoint_sha256") !=
            checkpoint_sha256 or
            (not gold400 and selected_checkpoint_record.get("selection_code_snapshot_sha256") !=
            (frozen_selection_code_snapshot_sha256 if final_model_calibration else
             selection_code_snapshot()["sha256"])) or
            (final_model_calibration and (
                not isinstance(frozen_selection_code_snapshot_sha256, str) or
                len(frozen_selection_code_snapshot_sha256) != 64)) or
            Path(selected_checkpoint_record.get("selected_checkpoint_path", "")).resolve() !=
            Path(checkpoint_path).resolve() or
            selected_checkpoint_record.get("calibration_executed") is not False or
            selected_checkpoint_record.get("test_access_count") != 0 or
            sha256(Path(checkpoint_path).read_bytes()).hexdigest() != checkpoint_sha256 or
            type(score_collection_model_forwards) is not int or
            score_collection_model_forwards < 1 or test_access_count != 0 or
            len(dev_ids) != (49 if gold400 else 15) or
            len(set(dev_ids)) != len(dev_ids) or
            len(checkpoint_sha256) != 64 or len(gold_sha256) != 64 or
            len(source_policy_sha256) != 64 or
            ((entity_pair_policy_sha256 is None or
              relation_routing_policy_sha256 is None)
             if final_model_calibration else
             ((phase != "entity_role_time_attribution_sources") !=
              (entity_pair_policy_sha256 is not None) or
              (phase == "cluster_consumers") !=
              (relation_routing_policy_sha256 is not None))) or
            any(len(value) != 64 for value in (
                entity_pair_policy_sha256,
                relation_routing_policy_sha256) if value is not None)):
        raise ValueError("score table needs selected checkpoint and dev provenance")
    ids = tuple(dev_ids)
    raw_ids = [str(row.get("candidate_id")) for row in raw_rows]
    if (len(raw_ids) != len(set(raw_ids)) or
            set(gold_authority_by_id) != set(raw_ids) or
            any(state not in AUTHORITY_STATES for state in gold_authority_by_id.values()) or
            len(gold_positive_ids) != len(set(gold_positive_ids)) or
            not set(raw_ids).issubset(set(gold_positive_ids) |
                                      {key for key, state in gold_authority_by_id.items()
                                       if state != "POSITIVE"})):
        raise ValueError("score table candidate/Gold authority inventory differs")
    rows = []
    for row in raw_rows:
        if (set(row) != {"article_id", "candidate_id", "score", "geometry"} or
                row["article_id"] not in ids or
                not isinstance(row["candidate_id"], str) or
                not row["candidate_id"] or
                not isinstance(row["score"], (int, float)) or
                not math.isfinite(row["score"]) or
                not isinstance(row["geometry"], dict)):
            raise ValueError("raw score row contract differs")
        rows.append({**row, "score": float(row["score"]),
                     "gold_authority": gold_authority_by_id[row["candidate_id"]]})
    for row in rows:
        if ((row["gold_authority"] == "POSITIVE") !=
                (row["candidate_id"] in gold_positive_ids)):
            raise ValueError("Gold positive authority differs from candidate ID")
    result = {
        "schema_version": SCORE_CONTRACT_VERSION,
        "status": "SCORES_COMPLETE_SWEEP_PENDING",
        "phase": phase, "lane": lane,
        "threshold_class": ("FILTER_ONLY" if lane in FILTER_ONLY else
                            "STRUCTURE_CHANGING"),
        "checkpoint_sha256": checkpoint_sha256,
        "dev_ids_sha256": _sha(ids),
        "dev_article_count": len(ids),
        "gold_sha256": gold_sha256,
        "score_contract_version": SCORE_CONTRACT_VERSION,
        "relevant_code_snapshot_sha256": relevant_code_snapshot()["sha256"],
        "source_policy_sha256": source_policy_sha256,
        "entity_pair_policy_sha256": entity_pair_policy_sha256,
        "relation_routing_policy_sha256": relation_routing_policy_sha256,
        "metric_calibration_policy_sha256": calibration_policy_sha256(),
        "gold_join_after_prediction": True,
        "selected_checkpoint": True,
        "final_model_calibration": final_model_calibration,
        "frozen_selection_code_snapshot_sha256": (
            frozen_selection_code_snapshot_sha256 if final_model_calibration else None),
        "selected_checkpoint_record_sha256": _sha(selected_checkpoint_record),
        "score_collection_model_forward_count": score_collection_model_forwards,
        "test_access_count": 0,
        "model_forward_count": 0,  # this builder consumes precomputed raw rows only
        "dev_ids": list(ids),
        "gold_positive_ids": list(gold_positive_ids),
        "rows": rows,
    }
    if not gold400:
        result["dev15_ids_sha256"] = _sha(ids)
    return result


def offline_threshold_replay(table: Mapping[str, Any], *,
                             thresholds: Sequence[float]) -> dict[str, Any]:
    """Sweep saved scores once; retain accepted IDs only at the selected point."""
    if (table.get("schema_version") != SCORE_CONTRACT_VERSION or
            table.get("status") != "SCORES_COMPLETE_SWEEP_PENDING" or
            table.get("relevant_code_snapshot_sha256") !=
            relevant_code_snapshot()["sha256"] or
            table.get("metric_calibration_policy_sha256") !=
            calibration_policy_sha256() or
            table.get("selected_checkpoint") is not True or
            table.get("gold_join_after_prediction") is not True or
            table.get("test_access_count") != 0 or
            table.get("phase") not in PHASE_LANES or
            table.get("lane") not in PHASE_LANES[table["phase"]] or
            table.get("lane") in CALIBRATION_UNSUPPORTED or
            not thresholds or any(not isinstance(value, (int, float)) or
                                  not math.isfinite(value) for value in thresholds)):
        raise ValueError("offline replay score/policy/checkpoint contract differs")
    rows = table["rows"]
    positive = set(table["gold_positive_ids"])
    if len(positive) != len(table["gold_positive_ids"]):
        raise ValueError("score table Gold positive IDs duplicate")
    # Gold authority contributes to metrics after raw scores exist; it never
    # changes candidate scores, candidate routing, or the threshold grid.
    ranked = sorted(rows, key=lambda row: float(row["score"]), reverse=True)
    grid = sorted(set(float(value) for value in thresholds), reverse=True)
    accepted: set[str] = set()
    tp = fp = cursor = 0
    points = []
    for threshold in grid:
        while cursor < len(ranked) and ranked[cursor]["score"] >= threshold:
            row = ranked[cursor]
            cursor += 1
            candidate_id = row["candidate_id"]
            if row["gold_authority"] == "IGNORE" or candidate_id in accepted:
                continue
            accepted.add(candidate_id)
            if candidate_id in positive:
                tp += 1
            else:
                fp += 1
        fn = len(positive) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
        f05 = 1.25 * tp / (1.25 * tp + 0.25 * fn + fp) if tp + fn + fp else 0.0
        points.append({"threshold": threshold,
                       "tp": tp, "fp": fp, "fn": fn,
                       "precision": precision, "recall": recall,
                       "f0_5": f05, "f1": f1,
                       "precision_denominator": tp + fp,
                       "recall_denominator": tp + fn})
    points.reverse()  # Keep the previous ascending threshold presentation.
    selected = max(points, key=lambda row: (row["f0_5"], row["threshold"]))
    selected_ids = sorted({row["candidate_id"] for row in rows
                           if row["score"] >= selected["threshold"] and
                           row["gold_authority"] != "IGNORE"})
    return {"schema_version": CALIBRATION_POLICY_VERSION,
            "phase": table["phase"], "lane": table["lane"],
            "score_table_sha256": _sha(table),
            "checkpoint_sha256": table["checkpoint_sha256"],
            "selected_threshold": selected["threshold"],
            "selected_point": {**selected, "accepted_candidate_ids": selected_ids},
            "pr_curve": points,
            "pr_curve_storage": "COUNTS_ONLY_SELECTED_POINT_IDS",
            "model_forward_count": 0,
            "runtime_replay_required": table["threshold_class"] == "STRUCTURE_CHANGING",
            "runtime_readiness": "NOT_VALIDATED",
            "test_access_count": 0}
