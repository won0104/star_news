"""Calibrate V23 source gates only after immutable Phase 1 checkpoint selection.

The dev authority supplies explicit labels. Missing Gold positives stay in the
denominator; unreviewed candidates never become negative labels. This runner
does not update weights or reuse historical v2.3 thresholds.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, replace
from hashlib import sha256
import json
import math
from pathlib import Path
import resource
from time import perf_counter

import torch

from runtime.v3_pretraining.acceptance import (SCORE_CONTRACT_VERSION,
                                                V23_TRIGGER_ENDPOINT_PRODUCER,
                                                V23_TRIGGER_FINE_PRODUCER)
from runtime.v3_pretraining.extraction_decode import (
    DecodeBudget, decode_source_spans, event_source_state, source_decode_context)
from runtime.v3_pretraining.serving import ServingBudget
from runtime.v3_pretraining.source_funnel import (
    SourceFunnelPolicy, V23_ARTIFACT_EXECUTION_ORDER,
    V23_SOURCE_FUNNEL_EXECUTION_VERSION)
from runtime.v3_pretraining.v23_features import sentence_cell
from training.v3_pretraining.corpus import R06GoldReader, SPLIT
from training.v3_pretraining.harness import (
    HarnessConfig, V3Trainer, fresh_full_core, load_pinned_backbone)
from training.v3_pretraining.negative_authority import ReviewedNegativeAuthority
from training.v3_pretraining.phase1_selection import (
    file_sha256, load_dev_authority, select_completed_epochs,
    selection_retrieval_budget)
from training.v3_pretraining.epoch_selection import SELECTION_CONTRACT_VERSION
from training.v3_pretraining.phase_lifecycle import refresh_phase_lifecycle
from training.v3_pretraining.gold400_schedule import inspect_epochs as inspect_gold400_epochs


PROJECT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT / "training/configs/v3-harness-engineering-v1.json"
NEGATIVE_AUTHORITY = PROJECT / "docs/v3-pretraining/r06-train73-negative-authority.json"
VERSION = "v23-phase1-selected-source-calibration-v2-trigger-fine"
KINDS = ("EVENT", "STATEMENT", "ENTITY", "TIME", "TRIGGER")
ROLES = ("ACTOR", "TARGET", "PLACE")


def _write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise ValueError(f"calibration artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                               indent=2) + "\n", encoding="utf-8")


def _thresholds(rows: list[dict], field: str, *, probability: bool = False
                ) -> list[float]:
    values = sorted({float(row[field]) for row in rows if row[field] is not None})
    if not values:
        raise ValueError(f"{field}: no retrieved labelled candidates")
    if len(values) > 256:
        values = sorted({values[round(i * (len(values) - 1) / 100)]
                         for i in range(101)} |
                        {float(row[field]) for row in rows
                         if row["label"] and row[field] is not None})
    terminal = 1.0 if probability else math.nextafter(values[-1], math.inf)
    return sorted(set(values + [terminal] + ([0.0] if probability else [])))


def _quality(rows: list[dict], *, decision: float, boundary: float | None = None,
             field: str = "score") -> tuple[tuple[float, float, float, int, float, float], dict]:
    positives = sum(bool(row["label"]) for row in rows)
    negatives = len(rows) - positives
    if positives < 5 or negatives < 5:
        raise ValueError("source calibration lacks explicit positive/negative authority")
    accepted = [row for row in rows if row[field] is not None and
                row[field] >= decision and
                (boundary is None or row["boundary"] is not None and
                 row["boundary"] >= boundary)]
    tp = sum(bool(row["label"]) for row in accepted)
    fp = len(accepted) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / positives
    f05 = 1.25 * precision * recall / (0.25 * precision + recall) if (precision or recall) else 0.0
    key = (f05, precision, recall, -len(accepted), decision,
           boundary if boundary is not None else 0.0)
    return key, {"F0.5": f05, "precision": precision, "recall": recall,
                 "positive_support": positives, "negative_support": negatives,
                 "retrieval_miss_positives": sum(row["label"] and row[field] is None
                                                    for row in rows),
                 "true_positive": tp, "false_positive": fp,
                 "accepted_reviewed": len(accepted)}


def _select(rows: list[dict], *, field: str = "score", joint: bool = False,
            probability: bool = False) -> dict:
    decisions = _thresholds(rows, field, probability=probability)
    boundaries = _thresholds(rows, "boundary") if joint else [None]
    best = None
    for decision in decisions:
        for boundary in boundaries:
            key, metrics = _quality(rows, decision=decision, boundary=boundary,
                                    field=field)
            if best is None or key > best[0]:
                best = (key, {"decision_threshold": decision,
                              "boundary_threshold": boundary, **metrics})
    return {"policy": "DEV15_EXPLICIT_AUTHORITY_F0.5_PRECISION_RECALL_COUNT_THRESHOLD_V1",
            "decision_grid_size": len(decisions),
            "boundary_grid_size": len(boundaries), **best[1]}


def _best_spans(spans) -> dict[tuple[int, int], object]:
    output = {}
    for span in spans:
        key = span.start, span.end
        old = output.get(key)
        if old is None or span.score > old.score:
            output[key] = span
    return output


def _frozen_mini_final_selection(rows: list[dict]) -> dict:
    """Verify a completed P6 ledger using its frozen selector identity.

    The current selection-code snapshot may change after rehearsal. Selection
    is replayed from immutable epoch records without pretending the new code
    produced the old checkpoint.
    """
    if (len(rows) != 3 or [row.get("epoch") for row in rows] != [1, 2, 3]):
        raise ValueError("Gold100 final selection epoch inventory differs")
    code_sha = rows[0].get("selection_code_snapshot_sha256")
    dev_sha = rows[0].get("dev_ids_sha256")
    if (not isinstance(code_sha, str) or len(code_sha) != 64 or
            any(row.get("schema_version") != SELECTION_CONTRACT_VERSION or
                row.get("phase") != "cluster_consumers" or
                row.get("dev_ids_sha256") != dev_sha or
                row.get("selection_code_snapshot_sha256") != code_sha or
                row.get("calibrated_thresholds_used") is not False or
                row.get("predicted_runtime_executed") is not False or
                row.get("test_access_count") != 0 or
                not isinstance(row.get("selection_metric"), (int, float)) or
                not math.isfinite(row["selection_metric"]) or
                file_sha256(Path(row["checkpoint_path"])) != row["checkpoint_sha256"]
                for row in rows)):
        raise ValueError("Gold100 final selection ledger differs")
    best = max(rows, key=lambda row: (row["selection_metric"], -row["epoch"]))
    return {"schema_version": SELECTION_CONTRACT_VERSION,
            "phase": "cluster_consumers", "selected_epoch": best["epoch"],
            "selected_checkpoint_path": best["checkpoint_path"],
            "selected_checkpoint_sha256": best["checkpoint_sha256"],
            "selection_metric": best["selection_metric"],
            "dev_ids_sha256": dev_sha, "calibration_executed": False,
            "selection_code_snapshot_sha256": code_sha,
            "predicted_runtime_executed": False, "test_access_count": 0}


def _endpoint_min(logits, cell, *, role_index: int | None = None,
                  local_row: int | None = None) -> float:
    if role_index is None:
        start = logits.start_logits[0, cell[0], cell[1], 0]
        end = logits.end_logits[0, cell[0], cell[2] - 1, 0]
    else:
        start = logits[local_row, cell[1], role_index, 0]
        end = logits[local_row, cell[2] - 1, role_index, 1]
    return min(float(torch.sigmoid(start)), float(torch.sigmoid(end)))


def _trigger_proposal_endpoint_min(logits, layout, span) -> float:
    """Read the parent proposal gate when a Trigger was character corrected."""
    components = dict(span.score_components)
    start = int(components.get("char_extension_parent_start", span.start))
    end = int(components.get("char_extension_parent_end", span.end))
    cell = sentence_cell(layout, start, end)
    if cell is None:
        raise ValueError("retrieved Trigger has no sentence proposal endpoint")
    if ("trigger_span_decision" not in components or
            not math.isclose(span.extraction_score,
                             components["trigger_span_decision"],
                             rel_tol=0.0, abs_tol=1e-6)):
        raise ValueError("Trigger calibration score is not its exact span decision")
    return _endpoint_min(logits, cell)


@torch.no_grad()
def run(*, selected: Path, ledger: Path, checkpoint: Path, gold: Path,
        support_path: Path, output_dir: Path, device: str = "mps",
        negative_authority_path: Path = NEGATIVE_AUTHORITY) -> dict:
    """Write a checkpoint-bound source policy after selected-checkpoint dev calibration.

    Gold400 permits the selected final phase checkpoint and dev49 authority;
    Gold100 retains the original Phase 1/dev15 contract.
    """
    if any((output_dir / name).exists() for name in (
            "score-table.json", "report.json", "source-acceptance.json",
            "source-policy.json")):
        raise ValueError("calibration output already exists")
    selected_row = json.loads(selected.read_text(encoding="utf-8"))
    ledger_row = json.loads(ledger.read_text(encoding="utf-8"))
    gold400 = len(json.loads(gold.read_text(encoding="utf-8"))["articles"]) == 400
    gold100_final = not gold400 and selected_row.get("phase") == "cluster_consumers"
    if gold400:
        selected_from_ledger = inspect_gold400_epochs(
            ledger_row["epochs"], phase="cluster_consumers")
    elif gold100_final:
        from training.v3_pretraining.mini_rehearsal_contract import (
            MAX_EPOCHS, SCHEDULE_CONTRACT, schedule_sha256)
        if (ledger_row.get("schedule_contract") != SCHEDULE_CONTRACT or
                ledger_row.get("schedule_sha256") != schedule_sha256() or
                len(ledger_row.get("epochs", ())) != MAX_EPOCHS):
            raise ValueError("unknown Gold100 final calibration schedule")
        selected_from_ledger = _frozen_mini_final_selection(
            ledger_row["epochs"])
        selected_from_ledger.update({"schedule_contract": SCHEDULE_CONTRACT,
                                     "completed_epochs": MAX_EPOCHS})
    elif ledger_row.get("schedule_contract") is not None:
        from training.v3_pretraining.mini_rehearsal_contract import (
            MAX_EPOCHS, SCHEDULE_CONTRACT, selection_policy_manifest)
        if ledger_row["schedule_contract"] != SCHEDULE_CONTRACT:
            raise ValueError("unknown Gold100 calibration schedule")
        selected_from_ledger = select_completed_epochs(
            ledger_row["epochs"], expected_epochs=MAX_EPOCHS,
            expected_policy=selection_policy_manifest(),
            schedule_contract=SCHEDULE_CONTRACT)
    else:
        selected_from_ledger = select_completed_epochs(ledger_row["epochs"])
    if (selected_row != selected_from_ledger or
            selected_row["selected_checkpoint_sha256"] != file_sha256(checkpoint) or
            Path(selected_row["selected_checkpoint_path"]).resolve() != checkpoint.resolve() or
            (not gold400 and not gold100_final and
             selected_row["checkpoint_selection_used_calibrated_thresholds"] is not False) or
            ledger_row["test_access_count"] != 0):
        raise ValueError("selected checkpoint or all-six raw selection binding differs")
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if (payload.get("phase") != ("cluster_consumers" if gold400 or gold100_final
                                  else "extraction") or
            payload.get("phase_manifest", {}).get("source_profile") != "V23_BASELINE"):
        raise ValueError("selected checkpoint is not the expected V23 phase")
    reader = R06GoldReader(gold)
    reader.validate_inventory()
    dev_ids = tuple(aid for aid in reader.gold if reader.membership[aid] == "dev")
    support = load_dev_authority(
        support_path, gold_sha256=file_sha256(gold),
        split_sha256=file_sha256(SPLIT), dev_ids=dev_ids, gold400=gold400)
    authority = ReviewedNegativeAuthority.from_json(negative_authority_path)
    base = replace((HarnessConfig(**payload["base_config"]) if gold400 or gold100_final else
                    HarnessConfig.from_json(CONFIG)),
                   negative_authority_path=str(negative_authority_path.resolve()),
                   negative_authority_sha256=authority.sha256)
    torch.set_num_threads(4)
    core = fresh_full_core(base, device=device)
    core.load_state_dict(payload["model_state"], strict=True)
    backbone = load_pinned_backbone(core, device=device)
    core.eval()
    backbone.eval()
    trainer = V3Trainer(core, backbone, base, extraction_profile="V23_BASELINE")
    retrieval = selection_retrieval_budget()
    table = {f"E.{kind}": [] for kind in KINDS}
    table.update({f"E.PARTICIPANT.{role}": [] for role in ROLES})
    started = perf_counter()
    for article_id in dev_ids:
        article = reader.load((article_id,), split="dev")[0]
        target = trainer.compiler.compile(article)
        batch, frozen = trainer._frozen_article_view(
            article, target, cache_scope="selected-calibration")
        fixed = support[article_id]
        with core.forward_shared(batch, frozen) as shared:
            context = source_decode_context(target.layout, shared, core)
            try:
                decoded = {}
                for kind in KINDS:
                    outcome = decode_source_spans(
                        kind=kind, layout=target.layout, batch=batch,
                        backbone=frozen, shared=shared, core=core,
                        budget=DecodeBudget(), context=context, retrieval=retrieval,
                        selection_only_threshold_free=(kind == "TRIGGER"))
                    decoded[kind] = _best_spans(outcome.spans)
                trigger_logits = core.task_modules["trigger"].boundary(
                    frozen.layer(8), batch.source_token_mask)
                for kind in KINDS:
                    component = f"E.{kind}"
                    for row in fixed.component_rows[component]:
                        span = decoded[kind].get((row["start"], row["end"]))
                        endpoint = None
                        if kind == "TRIGGER" and span is not None:
                            endpoint = _trigger_proposal_endpoint_min(
                                trigger_logits, target.layout, span)
                        table[component].append({"article_id": article_id,
                            "pair_id": row["pair_id"], "label": row["label"],
                            "score": None if span is None else span.extraction_score,
                            "boundary": None if span is None else span.boundary_fitness_score,
                            "endpoint_min": endpoint})
                event_rows = {row.owner_id: row for row in target.spans["semantic_proposer"]
                              if row.label == "EVENT"}
                for event_id, event in sorted(event_rows.items()):
                    alignment = event.alignment
                    state = event_source_state(
                        alignment=alignment, layout=target.layout, batch=batch,
                        backbone=frozen, shared=shared, core=core,
                        profile="V23_BASELINE")
                    sentence_rows = [index for index, window in enumerate(target.layout.windows)
                                     if window.view == "sentence" and any(
                                         token.start <= alignment.start < token.end
                                         for token in window.tokens)]
                    if sentence_rows:
                        positions = []
                        for index in sentence_rows:
                            cell = sentence_cell(target.layout, alignment.start,
                                                 alignment.end,
                                                 target.layout.windows[index].window_id)
                            positions.append((index, cell[1], cell[2]) if cell is not None
                                             else (index, 0, 0))
                        logits = core.task_modules["participant"].boundary(
                            state.unsqueeze(0).expand(len(sentence_rows), -1),
                            shared.token_states[0, sentence_rows],
                            torch.tensor(positions, dtype=torch.long,
                                         device=shared.token_states.device),
                            batch.source_token_mask[0, sentence_rows])
                    for role_index, role in enumerate(ROLES):
                        component = f"E.PARTICIPANT.{role}"
                        owner_rows = [row for row in fixed.component_rows[component]
                                      if row["owner_id"] == event_id]
                        if not owner_rows:
                            continue
                        outcome = decode_source_spans(
                            kind="PARTICIPANT", layout=target.layout, batch=batch,
                            backbone=frozen, shared=shared, core=core,
                            budget=DecodeBudget(12, 12, 24, 16), context=context,
                            event_alignment=alignment, event_state=state, role=role,
                            retrieval=retrieval, selection_only_threshold_free=True)
                        spans = _best_spans(outcome.spans)
                        for row in owner_rows:
                            span = spans.get((row["start"], row["end"]))
                            endpoint = None
                            if span is not None and sentence_rows:
                                for local_row, window_index in enumerate(sentence_rows):
                                    cell = sentence_cell(
                                        target.layout, row["start"], row["end"],
                                        target.layout.windows[window_index].window_id)
                                    if cell is not None:
                                        endpoint = _endpoint_min(
                                            logits, cell, role_index=role_index,
                                            local_row=local_row)
                                        break
                            table[component].append({"article_id": article_id,
                                "pair_id": row["pair_id"], "label": row["label"],
                                "score": None if span is None else span.score,
                                "boundary": None, "endpoint_min": endpoint})
            finally:
                context.close()
    ledger_access = {split: reader.access_count(split) for split in ("train", "dev", "test")}
    if ledger_access != {"train": 0, "dev": (49 if gold400 else 15), "test": 0}:
        raise ValueError("selected calibration accessed an unexpected split")
    scores = {kind: _select(table[f"E.{kind}"], joint=kind in ("EVENT", "STATEMENT"))
              for kind in KINDS}
    scores["TRIGGER_ENDPOINT"] = _select(
        table["E.TRIGGER"], field="endpoint_min", probability=True)
    scores["TRIGGER_FINE"] = scores["TRIGGER"]
    participant_rows = [row for role in ROLES
                        for row in table[f"E.PARTICIPANT.{role}"]]
    scores["PARTICIPANT"] = _select(participant_rows, field="endpoint_min",
                                      probability=True)
    scores["PARTICIPANT_FINE"] = _select(participant_rows, field="score")
    threshold_map = {kind: scores[kind]["decision_threshold"]
                     for kind in ("EVENT", "STATEMENT", "ENTITY", "TIME")}
    threshold_map.update({"TRIGGER": scores["TRIGGER"]["decision_threshold"],
                          "PARTICIPANT": None})
    acceptance = {
        "schema_version": VERSION, "status": "PROVISIONAL_ENGINEERING_ONLY",
        "mode": "CALIBRATION_CANDIDATE",
        "scope": "SOURCE_ACCEPTANCE_ONLY_NO_FULL_CASCADE",
        "service_ready": False, "test_access": 0,
        "checkpoint_sha256": file_sha256(checkpoint),
        "score_contract_version": SCORE_CONTRACT_VERSION,
        "gold_sha256": file_sha256(gold),
        ("dev49_ids_sha256" if gold400 else "dev15_ids_sha256"):
            sha256(json.dumps(dev_ids).encode()).hexdigest(),
        "selection_record_sha256": file_sha256(selected),
        "selection_policy_sha256": (ledger_row["epochs"][selected_row["selected_epoch"] - 1]
                                     ["selection_code_snapshot_sha256"] if gold400 or gold100_final else
                                     selected_row["selection_policy_sha256"]),
        "checkpoint_selection_used_calibrated_thresholds": False,
        "calibration_executed_after_checkpoint_selection": True,
        "thresholds": threshold_map,
        "boundary_thresholds": {kind: scores[kind]["boundary_threshold"]
                                for kind in ("EVENT", "STATEMENT")},
        "threshold_status": {kind: ("INACTIVE_V23_ENDPOINT_ONLY"
                                    if kind == "PARTICIPANT" else "SELECTED")
                             for kind in (*KINDS, "PARTICIPANT")},
        "v23_proposal_endpoint_thresholds": {
            "TRIGGER": scores["TRIGGER_ENDPOINT"]["decision_threshold"],
            "PARTICIPANT": scores["PARTICIPANT"]["decision_threshold"]},
        "trigger_endpoint_score_producer": V23_TRIGGER_ENDPOINT_PRODUCER,
        "trigger_final_score_producer": V23_TRIGGER_FINE_PRODUCER,
        "v23_calibration_provenance": {
            "source_profile": "V23_BASELINE",
            "legacy_release_thresholds_reused": False,
            "new_gold_dev_calibrated": True,
            "authority_sha256": file_sha256(support_path),
            "selected_epoch": selected_row["selected_epoch"]}}
    acceptance_path = output_dir / "source-acceptance.json"
    acceptance_bytes = (json.dumps(acceptance, ensure_ascii=False, sort_keys=True,
                                   indent=2) + "\n").encode("utf-8")
    policy = {
        "schema_version": VERSION,
        "status": "PROVISIONAL_ENGINEERING_ONLY",
        "checkpoint_sha256": file_sha256(checkpoint),
        "score_contract_version": SCORE_CONTRACT_VERSION,
        "acceptance_artifact_sha256": sha256(acceptance_bytes).hexdigest(),
        "retrieval_budget": asdict(retrieval),
        "source_execution_version": V23_SOURCE_FUNNEL_EXECUTION_VERSION,
        "execution_order": list(V23_ARTIFACT_EXECUTION_ORDER),
        "article_guard": None, "route_quota": None,
        "borrowing_dedup_policy": None, "per_kind_cap": None,
        "entity_candidate_budget": None,
        "trigger_containment_policy": "OPTIONAL_CONTAINED_TRIGGER_ATTACHMENT",
        "per_kind_retrieval_override": [], "test_access": 0}
    policy_path = output_dir / "source-policy.json"
    policy_bytes = (json.dumps(policy, ensure_ascii=False, sort_keys=True,
                               indent=2) + "\n").encode("utf-8")
    SourceFunnelPolicy.from_artifacts(
        policy_bytes, acceptance_bytes,
        checkpoint_sha256=file_sha256(checkpoint),
        budget=ServingBudget(retrieval=retrieval))
    _write_once(acceptance_path, acceptance)
    _write_once(policy_path, policy)
    report = {"schema_version": VERSION,
              "selection_status": ("SELECTED_CHECKPOINT_DEV49_CALIBRATED" if gold400 else
                                   "SELECTED_CHECKPOINT_DEV15_CALIBRATED"),
              "selected_epoch": selected_row["selected_epoch"],
              "selection_record_sha256": file_sha256(selected),
              "checkpoint_sha256": file_sha256(checkpoint),
              "gold_sha256": file_sha256(gold),
              "support_sha256": file_sha256(support_path),
              "selection_ledger_sha256": file_sha256(ledger),
              "calibration_code_sha256": file_sha256(__file__),
              "source_policy_sha256": file_sha256(policy_path),
              "source_acceptance_sha256": file_sha256(acceptance_path),
              "score_contract_version": SCORE_CONTRACT_VERSION,
              "trigger_endpoint_status": "SELECTED",
              "trigger_fine_status": "SELECTED",
              "trigger_endpoint_threshold": scores["TRIGGER_ENDPOINT"]["decision_threshold"],
              "trigger_fine_threshold": scores["TRIGGER_FINE"]["decision_threshold"],
              "participant_fine_threshold": scores["PARTICIPANT_FINE"]["decision_threshold"],
              "thresholds": scores, "split_access_ledger": ledger_access,
              "checkpoint_selection_used_calibrated_thresholds": False,
              "calibration_executed_after_checkpoint_selection": True,
              "elapsed_seconds": perf_counter() - started,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "mps_allocated_bytes": (torch.mps.current_allocated_memory()
                                      if device == "mps" else None)}
    _write_once(output_dir / "score-table.json", {
        "schema_version": VERSION, "checkpoint_sha256": file_sha256(checkpoint),
        "split_access_ledger": ledger_access, "rows": table})
    _write_once(output_dir / "report.json", report)
    lifecycle_path = selected.parent / "phase-lifecycle.json"
    if (not gold100_final and
            (lifecycle_path.exists() or selected_row.get("phase") == "extraction")):
        refresh_phase_lifecycle(
            output_path=lifecycle_path, selected_record_path=selected,
            calibration_acceptance_path=acceptance_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("selected", "ledger", "checkpoint", "gold", "support", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--negative-authority", type=Path,
                        default=NEGATIVE_AUTHORITY)
    args = parser.parse_args()
    row = run(selected=args.selected, ledger=args.ledger,
              checkpoint=args.checkpoint, gold=args.gold,
              support_path=args.support, output_dir=args.output_dir,
              device=args.device,
              negative_authority_path=args.negative_authority)
    print(json.dumps({key: row[key] for key in (
        "selection_status", "selected_epoch", "checkpoint_sha256",
        "source_policy_sha256", "source_acceptance_sha256", "elapsed_seconds")},
        sort_keys=True))


if __name__ == "__main__":
    main()
