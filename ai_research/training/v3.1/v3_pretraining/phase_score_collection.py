"""Selected-checkpoint Gold-dev raw scores for the active downstream DAG.

This is an oracle endpoint diagnostic. It scores the complete supervised pair
universe without train sampling or serving caps; it cannot calibrate predicted
runtime thresholds. The selected model and dev cohort are checked before any
forward, and the resulting artifact is written once. It reuses the prepared
dev layouts and frozen cache from the optimized epoch evaluator (the same
shared-forward and run-local cache pattern used by Phase 1 in d1e35259 and
a5b84835): one backbone miss or hit, one DCE, and active head chunks per article.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import resource
from time import perf_counter
from typing import Any, Callable, Mapping

import torch

from models.v3_pretraining.task_contract import PHASE_TASKS, TRAINING_PHASES
from models.v3_pretraining.pair_context import summarize_statements
from models.v3_pretraining.event_heads import EVENT_PAIR_POLICY_VERSION
from runtime.v3_pretraining.attribution_features import ASSERTOR_ENTITY_STATE_PREFIX
from runtime.v3_pretraining.event_features import finalize_cluster_features
from training.v3_pretraining.calibration_table import PHASE_LANES
from training.v3_pretraining.code_snapshot import (selection_code_snapshot,
                                                   training_code_snapshot)
from training.v3_pretraining.epoch_selection import (SELECTION_CONTRACT_VERSION,
                                                    PhaseEpochSelectionEvaluator)
from training.experiments.v3_posttraining_selected_v1.quality import ranking_quality
from training.v3_pretraining.attribution import (
    _sentence_cohort, gold_cluster_local_ids, gold_entity_local_ids)
from training.v3_pretraining.relation_evaluation import score_full_universe
from training.v3_pretraining.staged import (GOLD_ONLY_DAG_EXECUTION_VERSION,
                                            GOLD_ONLY_FORMAT_VERSION,
                                            EVENT_HEAD_FORMAT_VERSION,
                                            EVENT_HEAD_EXECUTION_CONTRACT)


SCORE_ARTIFACT_VERSION = "v3-selected-phase-gold-dev-raw-v1-unified-entity"
GOLD400_SCORE_ARTIFACT_VERSION = "v3-gold400-selected-phase-gold-dev-raw-v2-event-feature-pair-15"
LANE_TASK = {
    "ASSERTOR_SOURCE": "assertor_source", "EVENT_TIME": "event_time",
    "ENTITY_COREFERENCE": "entity_coreference",
    "ASSERTOR_ENTITY": "assertor_entity",
    "EVENT_COREFERENCE": "event_coreference",
    "ABOUT": "about", "CAUSES": "causes", "PRIMARY": "primary",
}
NON_AP_HEADS = {"entity_role_time_attribution_sources": {
    "time_normalization": "SEQUENCE_OUTPUT_NO_BINARY_THRESHOLD",
}}
if any({LANE_TASK[lane] for lane in lanes} | set(NON_AP_HEADS.get(phase, {})) !=
       set(PHASE_TASKS[phase]) for phase, lanes in PHASE_LANES.items()):
    raise AssertionError("phase raw-score lanes differ from the active head DAG")

ENTITY_ORIGIN_COHORTS = ("NATIVE_NATIVE", "NATIVE_ROLE_VIEW",
                         "ROLE_VIEW_ROLE_VIEW")


def _entity_origin_cohort(left, right) -> str:
    # An exact Native+ROLE use is one Native mention, not an independent ROLE view.
    left_role = left.origins == ("ROLE",)
    right_role = right.origins == ("ROLE",)
    if left_role and right_role:
        return "ROLE_VIEW_ROLE_VIEW"
    if left_role or right_role:
        return "NATIVE_ROLE_VIEW"
    return "NATIVE_NATIVE"


def _check_gold_only_checkpoint(payload: Any, *, phase: str,
                                gold_sha256: str) -> None:
    """Reject historical DAG/authority bytes before any selected score forward."""
    manifest = payload.get("phase_manifest", {}) if isinstance(payload, dict) else {}
    authority = manifest.get("training_authority_binding_sha256") if isinstance(manifest, dict) else None
    losses = manifest.get("active_losses") if isinstance(manifest, dict) else None
    contract = manifest.get("training_contract") if isinstance(manifest, dict) else None
    snapshot = payload.get("data_snapshot") if isinstance(payload, dict) else None
    if (not isinstance(payload, dict) or
            payload.get("format_version") != (
                EVENT_HEAD_FORMAT_VERSION if phase in ("event_identity", "cluster_consumers")
                else GOLD_ONLY_FORMAT_VERSION) or
            payload.get("phase") != phase or
            not isinstance(manifest, dict) or
            manifest.get("phase") != phase or
            manifest.get("phase_manifest_contract_version") !=
            "v3-gold-only-phase-manifest-v5-unified-entity-no-priority" or
            manifest.get("dag_execution_version") != GOLD_ONLY_DAG_EXECUTION_VERSION or
            manifest.get("training_phase_order") != list(TRAINING_PHASES) or
            not isinstance(losses, (list, tuple)) or
            set(losses) != set(PHASE_TASKS[phase]) or
            (phase in ("event_identity", "cluster_consumers") and
             (manifest.get("event_head_execution_contract") !=
              EVENT_HEAD_EXECUTION_CONTRACT or
              manifest.get("event_pair_input_schema") != EVENT_PAIR_POLICY_VERSION or
              not isinstance(manifest.get("event_head_migration_sha256"), str) or
              len(manifest["event_head_migration_sha256"]) != 64)) or
            not isinstance(contract, dict) or
            contract.get("loss") != "GOLD_ORACLE_ONLY" or
            not isinstance(authority, str) or len(authority) != 64 or
            any(char not in "0123456789abcdef" for char in authority) or
            not isinstance(snapshot, dict) or
            snapshot.get("gold_file_sha256") != gold_sha256 or
            payload.get("relevant_code_snapshot") != training_code_snapshot()):
        raise ValueError("selected Gold score checkpoint DAG/authority/code differs")


def _pair_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (report.get("sampling_applied") is not False or
            report.get("serving_pair_cap_applied") is not False):
        raise ValueError("Gold raw scores require complete supervised pair universe")
    rows = []
    for pair in report["scored_pairs"]:
        article_id = pair["article_id"]
        left, right = pair["left_id"], pair["right_id"]
        rows.append({"article_id": article_id,
                     "candidate_id": json.dumps((article_id, left, right),
                                                separators=(",", ":")),
                     "score": pair["score"],
                     "geometry": {"left_id": left, "right_id": right,
                                  "cohort": pair["cohort"]},
                     "gold_authority": "POSITIVE" if pair["label"] else "NEGATIVE"})
    return rows


def _source_rows(trainer, article, target, lease) -> list[dict[str, Any]]:
    if any(row.source_mask not in ("SUPERVISE", "NO_EXPLICIT_SOURCE", "IGNORE")
           for row in target.assertors):
        raise ValueError("Assertor source Gold authority differs")
    assertors = [row for row in target.assertors if row.source_mask != "IGNORE"]
    if not assertors:
        return []
    states = lease.extra_states
    if states is None:
        raise RuntimeError("Assertor source scores lost their exact Statement states")
    batch = torch.stack([states["STATEMENT:" + row.statement_id]
                         for row in assertors])
    logits = trainer.core.task_modules["assertor_source"].exists(batch).squeeze(-1)
    if logits.shape != (len(assertors),):
        raise ValueError("Assertor source scorer returned wrong shape")
    return [{"article_id": article.raw.article_id,
             "candidate_id": json.dumps((article.raw.article_id, row.statement_id),
                                        separators=(",", ":")),
             "score": float(score),
             "geometry": {"statement_id": row.statement_id,
                          "source_span": ([row.alignment.start, row.alignment.end]
                                          if row.alignment is not None else None)},
             "gold_authority": ("POSITIVE" if row.source_mask == "SUPERVISE"
                                else "NEGATIVE")}
            for row, score in zip(assertors, logits.detach().cpu().tolist())]


def _primary_rows(article, target, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    ranks = dict(target.primary.nodes)
    if not ranks:
        return []
    return [{"article_id": article.raw.article_id,
             "candidate_id": json.dumps((article.raw.article_id, node_id),
                                        separators=(",", ":")),
             "score": float(report["score_inventory"][node_id]),
             "geometry": {"proposition_id": node_id, "importance_rank": rank}}
            for node_id, rank in target.primary.nodes]


def _selected_attribution_reports(trainer, article, target, features, final,
                                  names: tuple[str, ...]) -> dict[str, dict]:
    """Reuse the Gold pair scorer while invoking only this phase's heads."""
    view = final.view_for("RELATION")
    extras = features.time.extra_states
    if extras is None:
        raise RuntimeError("selected attribution scores lost exact source states")
    statements = {row.owner_id: extras["STATEMENT:" + row.owner_id]
                  for row in target.spans["semantic_proposer"] if row.label == "STATEMENT"}
    spans = {row.owner_id: (row.alignment.start, row.alignment.end)
             for row in target.spans["semantic_proposer"] if row.label == "STATEMENT"}
    summaries = summarize_statements(
        view.original_sentence_states, view.original_sentence_spans, spans)
    cluster_map = gold_cluster_local_ids(article, features)
    entity_map = gold_entity_local_ids(article, features)
    cluster_index = {cid: index for index, cid in enumerate(view.cluster_ids)}
    entity_states = {eid: extras[ASSERTOR_ENTITY_STATE_PREFIX + eid]
                     for eid in entity_map.values()}
    reports = {}
    for name in names:
        def score(chunk, lane=name):
            return trainer.attribution._score_pairs(
                lane, tuple((row.left_id, row.right_id) for row in chunk),
                statements=statements, extras=extras,
                entity_states=entity_states, entity_map=entity_map,
                cluster_map=cluster_map, cluster_index=cluster_index,
                view=view, statement_summaries=summaries,
                doc=view.document_state)

        def cohort(row, lane=name):
            left = (summaries[row.left_id] if lane == "about" else
                    view.event_sentence_summaries[
                        cluster_index[cluster_map[row.left_id]]])
            right = view.event_sentence_summaries[
                cluster_index[cluster_map[row.right_id]]]
            return _sentence_cohort(left.anchor_index, right.anchor_index).upper()

        reports[name] = score_full_universe(
            article_id=article.raw.article_id, universe=target.pairs[name],
            chunk_size=trainer.attribution.chunk_size, score_chunk=score,
            cohort_for=cohort if name != "assertor_entity" else None,
            cohort_names=(("SAME_SENTENCE", "ADJACENT_SENTENCE", "NON_ADJACENT")
                          if name != "assertor_entity" else ()))
    return reports


def _article_scores(evaluator: PhaseEpochSelectionEvaluator, prepared, frozen,
                    shared) -> tuple[dict[str, list[dict[str, Any]]], dict | None]:
    trainer, phase = evaluator.trainer, evaluator.phase
    article, target, batch = prepared.article, prepared.target, prepared.batch
    if phase == "entity_role_time_attribution_sources":
        extra = [("STATEMENT:" + row.owner_id, row.alignment, "STATEMENT")
                 for row in target.spans["semantic_proposer"] if row.label == "STATEMENT"]
        extra.extend(("ASSERTOR:" + row.statement_id, row.alignment, "STATEMENT")
                     for row in target.assertors if row.alignment is not None)
        with trainer.time.encode(target, batch, frozen, shared,
                                 extra_rows=tuple(extra)) as lease:
            return ({"ASSERTOR_SOURCE": _source_rows(trainer, article, target, lease),
                     "EVENT_TIME": _pair_rows(trainer.time.evaluate_full_universe(
                         target, lease, article_id=article.raw.article_id))}, None)
    if phase == "entity_identity":
        reports = trainer.entity.evaluate_full_universe(
            article, target, batch, frozen, shared)
        mentions = {row.mention_id: row for row in target.entity_mentions}
        rows = _pair_rows(reports["entity_coreference"])
        for row in rows:
            geometry = row["geometry"]
            geometry["origin_cohort"] = _entity_origin_cohort(
                mentions[geometry["left_id"]], mentions[geometry["right_id"]])
        return {"ENTITY_COREFERENCE": rows}, None
    with trainer.event.prepare(
            article, target, batch, frozen, shared,
            include_relations=phase != "event_identity") as features:
        if phase == "event_identity":
            return {"EVENT_COREFERENCE": _pair_rows(
                trainer.event.evaluate_full_universe(
                    target, features, article_id=article.raw.article_id))}, None
        final = finalize_cluster_features(features.member, features.closure)
        try:
            if phase == "entity_role_time_attribution":
                reports = _selected_attribution_reports(
                    trainer, article, target, features, final,
                    ("assertor_entity",))
                return {"ASSERTOR_ENTITY": _pair_rows(reports["assertor_entity"])}, None
            if phase == "cluster_consumers":
                reports = _selected_attribution_reports(
                    trainer, article, target, features, final, ("about", "causes"))
                primary = trainer.primary.evaluate_full_universe(
                    article, target, features, final)
                return ({"ABOUT": _pair_rows(reports["about"]),
                         "CAUSES": _pair_rows(reports["causes"]),
                         "PRIMARY": _primary_rows(article, target, primary)},
                        primary["metric"])
            raise ValueError("unknown downstream phase")
        finally:
            for consumer in tuple(sorted(final.pending_consumers)):
                final.release(consumer)


def collect_selected_gold_phase_scores(
        *, evaluator: PhaseEpochSelectionEvaluator,
        selected_checkpoint_record: Mapping[str, Any],
        checkpoint_path: str | Path, gold_sha256: str,
        access_ledger: Callable[[], Mapping[str, int]],
        output_path: str | Path,
        selection_ledger_path: str | Path | None = None) -> dict[str, Any]:
    """Write phase raw-score/AP diagnostics after a selected checkpoint exists."""
    path, output = Path(checkpoint_path), Path(output_path)
    if output.exists() or not path.is_file() or len(gold_sha256) != 64:
        raise ValueError("selected Gold raw-score output/checkpoint/Gold differs")
    selected = selected_checkpoint_record
    checkpoint_sha = sha256(path.read_bytes()).hexdigest()
    gold400 = selected.get("schedule_contract") is not None
    if gold400:
        from training.v3_pretraining.gold400_schedule import (
            CONTRACT, MAX_EPOCHS, inspect_epochs)
        if selection_ledger_path is None:
            raise ValueError("Gold400 selected raw score collection requires its epoch ledger")
        ledger = json.loads(Path(selection_ledger_path).read_text(encoding="utf-8"))
        if (selected.get("schedule_contract") != CONTRACT or
                not isinstance(ledger, dict) or not isinstance(ledger.get("epochs"), list) or
                inspect_epochs(ledger["epochs"], phase=evaluator.phase) != selected):
            raise ValueError("Gold400 selected checkpoint/epoch ledger differs")
        chosen = ledger["epochs"][selected["selected_epoch"] - 1]
        expected_dev_count, expected_passes = 49, MAX_EPOCHS
        selection_binding_valid = (
            chosen.get("dev_ids_sha256") == evaluator.dev_ids_sha256 and
            chosen.get("selection_code_snapshot_sha256") ==
            selection_code_snapshot()["sha256"])
    else:
        expected_dev_count, expected_passes = 15, 6
        selection_binding_valid = (
            selected.get("schema_version") == SELECTION_CONTRACT_VERSION and
            selected.get("dev_ids_sha256") == evaluator.dev_ids_sha256 and
            selected.get("selection_code_snapshot_sha256") ==
            selection_code_snapshot()["sha256"] and
            selected.get("predicted_runtime_executed") is False)
    if (evaluator.phase not in PHASE_LANES or
            len(evaluator.prepared) != expected_dev_count or
            selected.get("phase") != evaluator.phase or
            selected.get("selected_epoch") not in range(1, expected_passes + 1) or
            selected.get("selected_checkpoint_sha256") != checkpoint_sha or
            Path(selected.get("selected_checkpoint_path", "")).resolve() != path.resolve() or
            not selection_binding_valid or
            selected.get("calibration_executed") is not False or
            selected.get("test_access_count") != 0):
        raise ValueError("selected phase checkpoint/dev boundary differs")
    before = dict(access_ledger())
    if before.get("dev") != expected_dev_count or before.get("test") != 0:
        raise ValueError("Gold raw collector needs observed dev/test ledger")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    _check_gold_only_checkpoint(checkpoint, phase=evaluator.phase,
                                gold_sha256=gold_sha256)
    current = evaluator.trainer.core.state_dict()
    saved = checkpoint.get("model_state") if isinstance(checkpoint, dict) else None
    progress = checkpoint.get("training_state", {}) if isinstance(checkpoint, dict) else {}
    if (not isinstance(checkpoint, dict) or
            checkpoint.get("phase") != evaluator.phase or
            progress.get("completed_passes") != selected["selected_epoch"] or
            progress.get("target_passes") != expected_passes or
            progress.get("article_position") != 0 or
            not isinstance(progress.get("optimizer_steps"), int) or
            progress["optimizer_steps"] < 1 or
            not isinstance(saved, dict) or set(saved) != set(current) or any(
            not torch.equal(current[name].detach().cpu(), saved[name]) for name in current)):
        raise ValueError("collector model weights differ from selected checkpoint")
    trainer = evaluator.trainer
    trainer.core.eval()
    trainer.backbone.eval()
    lanes = {lane: [] for lane in PHASE_LANES[evaluator.phase]}
    primary_metrics = []
    execution_rows = []
    with torch.no_grad():
        for prepared in evaluator.prepared:
            started = perf_counter()
            calls = {"backbone": 0, "dce": 0}
            head_calls: dict[str, int] = {}
            handles = [
                trainer.backbone.register_forward_hook(
                    lambda *_: calls.__setitem__("backbone", calls["backbone"] + 1)),
                trainer.core.document_context.register_forward_hook(
                    lambda *_: calls.__setitem__("dce", calls["dce"] + 1)),
            ]
            for name, module in trainer.core.task_modules.items():
                handles.append(module.register_forward_hook(
                    lambda *_args, name=name: head_calls.__setitem__(
                        name, head_calls.get(name, 0) + 1)))
            if evaluator.phase == "entity_role_time_attribution_sources":
                handles.append(trainer.core.task_modules[
                    "assertor_source"].exists.register_forward_hook(
                        lambda *_: head_calls.__setitem__(
                            "assertor_source", head_calls.get("assertor_source", 0) + 1)))
            try:
                frozen = evaluator.features.build(
                    prepared.batch,
                    cache_key=prepared.cache_key if evaluator.use_backbone_cache else None,
                    scope="selected-phase-gold-scores")
                with trainer.core.forward_shared(prepared.batch, frozen) as shared:
                    article_rows, primary_metric = _article_scores(
                        evaluator, prepared, frozen, shared)
            finally:
                for handle in handles:
                    handle.remove()
            if (calls["dce"] != 1 or calls["backbone"] not in (0, 1) or
                    not set(head_calls) <= set(PHASE_TASKS[evaluator.phase])):
                raise RuntimeError("selected raw scores duplicated forward or ran inactive head")
            execution_rows.append({"article_id": prepared.article.raw.article_id,
                                   "backbone_calls": calls["backbone"],
                                   "frozen_backbone_cache_hit": calls["backbone"] == 0,
                                   "dce_calls": calls["dce"],
                                   "active_head_calls": head_calls,
                                   "wall_seconds": perf_counter() - started,
                                   "peak_rss_bytes": resource.getrusage(
                                       resource.RUSAGE_SELF).ru_maxrss})
            if set(article_rows) != set(lanes):
                raise ValueError("selected phase score lane inventory differs")
            if primary_metric is not None:
                primary_metrics.append(primary_metric)
            for lane, rows in article_rows.items():
                lanes[lane].extend(rows)
    after = dict(access_ledger())
    if after.get("dev") != before["dev"] or after.get("test") != 0:
        raise ValueError("Gold raw collection crossed the dev/test boundary")
    summaries = {}
    for lane, rows in lanes.items():
        ids = [row["candidate_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("selected phase raw candidate IDs repeat")
        if lane == "PRIMARY":
            summaries[lane] = {
                "raw_rows": rows,
                "metric_name": "STRICT_NON_TIE_PAIR_ORDERING",
                "per_article_strict_ordering": primary_metrics,
                "average_precision": None,
                "average_precision_status": "NOT_APPLICABLE_NO_APPROVED_BINARY_AUTHORITY",
                "threshold_calibration_status": "UNSUPPORTED"}
            continue
        ranked = ranking_quality([
            {"candidate_id": row["candidate_id"], "raw_score": row["score"],
             "authority": row["gold_authority"]} for row in rows])
        summaries[lane] = {"raw_rows": rows, "ranking_quality": ranked}
        if lane == "ENTITY_COREFERENCE":
            ignored = 0
            span_only = 0
            for prepared in evaluator.prepared:
                ignored += sum(pair.supervision_mask == "IGNORE" for pair in
                               prepared.target.pairs["entity_coreference"])
                span_only += sum(row.origins == ("ROLE",) and
                                 row.gold_entity_id is None
                                 for row in prepared.target.entity_mentions)
            summaries[lane]["origin_cohorts"] = {
                name: ranking_quality([
                    {"candidate_id": row["candidate_id"], "raw_score": row["score"],
                     "authority": row["gold_authority"]}
                    for row in rows if row["geometry"]["origin_cohort"] == name])
                for name in ENTITY_ORIGIN_COHORTS}
            summaries[lane]["span_only_ignore"] = {
                "span_only_mention_count": span_only,
                "ignore_pair_count": ignored, "average_precision": None,
                "average_precision_status": "NOT_SCORED_IGNORE"}
    result = {"schema_version": (GOLD400_SCORE_ARTIFACT_VERSION if gold400
                                  else SCORE_ARTIFACT_VERSION),
              "evaluation_mode": "GOLD_ORACLE_FULL_ELIGIBLE_UNIVERSE",
              "calibration_eligible": False,
              "phase": evaluator.phase,
              "lane_tasks": {lane: LANE_TASK[lane] for lane in lanes},
              "non_ap_heads": NON_AP_HEADS.get(evaluator.phase, {}),
              "checkpoint_sha256": checkpoint_sha,
              "selected_checkpoint_record_sha256": sha256(json.dumps(
                  selected, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
              "dev_ids_sha256": evaluator.dev_ids_sha256,
              "dev_article_count": expected_dev_count,
              "gold_sha256": gold_sha256,
              "selection_code_snapshot_sha256": selection_code_snapshot()["sha256"],
              "score_collector_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "model_forward_count": len(evaluator.prepared),
              "execution_profile": {
                  "prepared_dev_articles_reused": True,
                  "run_local_frozen_backbone_cache": evaluator.backbone_cache.snapshot()
                  if evaluator.backbone_cache is not None else None,
                  "one_dce_forward_per_article": True,
                  "only_phase_heads_called": True,
                  "full_supervised_pairs_scored_in_chunks": True,
                  "articles": execution_rows},
              "article_access_ledger": after,
              "test_access_count": after["test"],
              "predicted_runtime_executed": False,
              "lanes": summaries}
    if not gold400:
        result["dev15_ids_sha256"] = evaluator.dev_ids_sha256
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the read-only Gold-dev collector on one selected phase checkpoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=tuple(PHASE_LANES))
    parser.add_argument("--selected-record", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--r06-gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    args = parser.parse_args(argv)
    if args.output.exists() or not args.selected_record.is_file() or not args.r06_gold.is_file():
        raise ValueError("selected score collector input/output artifact differs")
    selected = json.loads(args.selected_record.read_text(encoding="utf-8"))
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if (not isinstance(payload, dict) or payload.get("phase") != args.phase or
            payload.get("format_version") != (
                EVENT_HEAD_FORMAT_VERSION if args.phase in ("event_identity", "cluster_consumers")
                else GOLD_ONLY_FORMAT_VERSION) or
            not isinstance(payload.get("base_config"), dict) or
            not isinstance(payload.get("model_state"), dict) or
            not isinstance(payload.get("phase_manifest"), dict) or
            payload["phase_manifest"].get("source_profile") not in
            ("V23_BASELINE", "V3_WINDOW")):
        raise ValueError("selected score collector checkpoint shape differs")

    from training.v3_pretraining.corpus import R06GoldReader
    from training.v3_pretraining.harness import (
        HarnessConfig, V3Trainer, fresh_full_core, load_pinned_backbone)

    config = HarnessConfig(**payload["base_config"])
    config.validate()
    reader = R06GoldReader(args.r06_gold)
    reader.validate_inventory()
    dev_ids = tuple(aid for aid in reader.gold if reader.membership[aid] == "dev")
    articles = reader.load(dev_ids, split="dev")
    core = fresh_full_core(config, device=args.device)
    core.load_state_dict(payload["model_state"], strict=True)
    backbone = load_pinned_backbone(core, device=args.device)
    trainer = V3Trainer(core, backbone, config, extraction_profile=
                        payload["phase_manifest"]["source_profile"])
    evaluator = PhaseEpochSelectionEvaluator(trainer, args.phase, articles)
    result = collect_selected_gold_phase_scores(
        evaluator=evaluator, selected_checkpoint_record=selected,
        checkpoint_path=args.checkpoint,
        gold_sha256=sha256(args.r06_gold.read_bytes()).hexdigest(),
        access_ledger=lambda: {name: reader.access_count(name)
                               for name in ("train", "dev", "test")},
        output_path=args.output,
        selection_ledger_path=(args.selected_record.parent / "selection-ledger.json"
                               if selected.get("schedule_contract") is not None else None))
    print(json.dumps({"phase": result["phase"],
                      "checkpoint_sha256": result["checkpoint_sha256"],
                      "lanes": {lane: row.get("ranking_quality", {}).get(
                          "average_precision_status", row.get("average_precision_status"))
                          for lane, row in result["lanes"].items()},
                      "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
