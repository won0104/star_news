# v3 dependency DAG staged training

> Historical v1 contract. The current Phase 2–6 Gold-only training and separate
> predicted diagnostic gate are documented in
> [gold-train-predicted-eval-refactor-audit.md](gold-train-predicted-eval-refactor-audit.md).
> The active unified Entity DAG and checkpoint format are described in
> [unified-entity-identity-v1.md](unified-entity-identity-v1.md).
> The `role_entity` phase ownership below is historical.

Status: executable engineering training path. It does not select a service
checkpoint, approve thresholds, or establish graph quality. The historical
19-head/20-loss `training.scripts.v3_train` and r06 four-coverage rehearsal
remain separate and reproducible. No post-DAG joint fine-tune runs here.

## Execution and loss ownership

`training.scripts.v3_staged_train` calls `start_phase`, constructs a full v3
model, freezes nonowners, builds an optimizer with only active parameter groups,
and calls `StagedTrainer.step` on verified train Gold. The existing Gold adapters
still compute the full inventory; reduction includes only the phase's channels.
Gold positives never depend on source acceptance. Source replay is selected by
`V3ServingWorker.analyze_source_funnel` on an independent, frozen predecessor
checkpoint. The student re-gathers selected coordinates for any replay loss.

| Phase | Oracle loss channels | Shared model | Predicted loss contribution |
| --- | --- | --- | --- |
| `extraction` | eight Extraction heads, `entity_typing_union` | DCE and source bridges train | none |
| `entity_role_time_attribution_sources` | `entity_priority`, `role_entity`, `event_time`, `time_normalization`, `assertor_source` | DCE and source bridges train | `entity_priority`, weight 0.25 when Gold-matched candidates exist |
| `entity_identity` | `entity_coreference` | shared DCE frozen | `entity_coreference`, weight 0.25 for pairs of two Gold-matched candidates |
| `entity_role_time_attribution` | `assertor_entity` | DCE and source bridges train | zero; source replay is an upstream availability audit |
| `event_identity` | `event_coreference` | shared DCE frozen | `event_coreference`, weight 0.25 for pairs of Gold-matched predicted Events, with frozen-producer Entity resolution and Time channels |
| `cluster_consumers` | `about`, `causes`, `primary` on closed oracle EventClusters | shared DCE frozen; `primary_adapter` trains | zero; the full producer's closed predicted EventClusters are audited |

Entity identity starts after the source/role/Time phase. The trained Entity
identity checkpoint then supports predicted ASSERTED_BY option validation
before the `assertor_entity` phase. Event identity starts after that phase.
`primary_adapter` is trained
only with Primary. Every report lists active/inactive losses, owner groups and
learning rates, DCE state, gradients, parameter updates, and lane loss values.
When a group has no active supervision it is logged as skipped without an
optimizer step.

The order follows the verified runtime path: `score_and_close_entity` scores
Entity coreference and builds a preliminary closure before D5 constructs
Assertor→Entity options. Phase 3's predicted Entity replay uses the frozen
source funnel and the student Entity states; it does not consume a trained
`assertor_entity` result. Event feature construction uses ACTOR/TARGET/PLACE
endpoints and the selected Entity representative mention for its Entity
channel. It does not use the ASSERTED_BY all-member carrier as an Event feature.
The final Entity closure may still change indirectly when Assertor resolution
retains an Entity candidate; Event identity runs after Phase 4 and consumes
that final closure. `TaskDefinition` dependencies remain head/Gold ontology;
the trained Entity identity prerequisite for D5 option validation is enforced
at the phase boundary. The `entity_identity` replay loss remains active and
the `assertor_entity` predicted replay loss remains absent.

Phase 4 still trains the shared DCE under its existing ownership policy, after
Phase 3 trained Entity identity. Phase 5 now requires a checkpoint-bound
predicted-cascade Entity stability artifact and report to check this
representation drift. The gate does not change the freeze policy or claim a
training result.

The replay matcher never adds a missing Gold candidate. It counts exact-span
retrieval misses. An unknown predicted candidate has no supervised label;
Entity identity pairs are labelled only when both candidates resolve to known
Gold mentions. The existing compiler and reviewed negative authority still own
oracle negatives. The replay source path does not contain retrieval, cap,
acceptance, containment, or Entity-union copies.

## Phase boundary and producer snapshot

Each downstream invocation requires the immediately preceding phase checkpoint
and a source funnel/acceptance artifact pair bound to that checkpoint SHA.
`start_phase` loads predecessor weights twice into **different** model objects:
the student is mutable, and the producer is eval, frozen, and parameter-disjoint.
The pinned backbone is also separately loaded. Source selection, downstream
Entity resolution, and EventCluster membership therefore remain stable during
student optimizer steps. A policy SHA alone would not provide that guarantee.

The checkpoint records predecessor SHA, artifact SHA pair and binding, exact
Gold/source/split exposure, base config and active loss weights, optimizer group
names/shapes/LRs, optimizer state, sampler cursor, and RNG. Resume rejects
config, data, phase, policy, or optimizer ownership drift. Policy values are
fixed for the whole phase; this code never retunes them per optimizer step.
`v3_staged_train --passes N` now repeats the fixed train ID list N times within
one phase (default 1). One frozen predecessor and one policy pair serve every
pass. Checkpoint format `v3-dag-phase-checkpoint-v4` records the DAG order and target pass
count, completed passes, current-pass article position, cumulative article
exposures, optimizer steps, and skipped steps. Resume requires the same N and
exact article order. A checkpoint is saved at every pass boundary; use
`--checkpoint-every-steps N` for mid-pass recovery. The next phase rejects an
unfinished predecessor. Reports include pass/exposure/optimizer/skip totals.
The next phase needs a new source artifact pair bound to its predecessor. For
V23, Phase 3 retains the Entity/Participant routing policy and mode used in
Phase 2, with a fresh artifact bound to the Phase 2 checkpoint/source policy.
Phase 4 requires predicted ASSERTED_BY option validation against the trained
Phase 3 Entity identity checkpoint. Its option artifact byte SHA is carried
through Phases 5 and 6 without repeating validation. Phase 5 requires the
predicted Entity stability artifact after Phase 4, and Phase 6 carries its SHA.
Phase 6 requires predicted
ABOUT/CAUSES routing validation against Phase 5. Old checkpoint formats and
the old phase order are rejected. The
existing r06 fresh73 source artifacts bind only step73 and cannot be used as
new phase artifacts. The current fresh73 calibration command is checkpoint
specific; a new checkpoint's thresholds need a separate dev calibration before
a quality comparison. Copying its numeric thresholds and changing its SHA is
acceptable only as a **wiring fixture**, never as a calibrated 100-article run.

The runtime request semaphore, bounded source/pair budgets, and tensor lease
cleanup remain in `V3ServingWorker`. The added `predicted_structure` audit is
scalar only; it supplies frozen Entity resolution and Event membership for
training diagnostics without exporting request tensors.
Its Entity representative candidate IDs and Time evidence IDs/coordinates also
let Event replay use the same channel inputs as runtime: the representative
mention for each Entity and the mean evidence state for each Time occurrence.
The frozen producer supplies those IDs and coordinates; the student re-encodes
them with its current weights.

## Small verification performed

- Eight staged unit tests cover the phase inventory, active optimizer owners,
  six phase oracle gradient/update paths, source-positive retention, replay
  miss/no-backfill behavior, two-known-endpoint identity supervision, predicted
  Event pair gradients, producer alias rejection, and checkpoint/data boundary
  rejection.
- One r05.3 article completed all six CLI phases under the **previous** order
  with one optimizer update each. All policy artifacts for that historical
  chain were temporary synthetic fixtures in `/private/tmp`; they provide no
  evidence for the revised order or quality.
- One r06 Gold100 **train** article completed Extraction and the first phase-2
  interval with the reviewed train negative authority. One matching all-head
  joint-baseline step also ran. No 100-article or 1K optimization ran.
- A distinct frozen step73 producer and mutable student had stable source
  selections before and after a student update. The source parity script on
  one dev article had zero source mismatches and a trainable re-gather graph.
  Its aggregate status is `PARTIAL_OR_FAIL` solely because the script's full
  success criterion requires all 15 dev articles.

The one-article stage fixture yielded zero exact Entity/Event replay hits, so
those runs verify routing and miss accounting, not predicted-loss convergence.
Historical checkpoints and acceptance reports are provenance/wiring references,
not evidence for staged-learning performance.

## Later Gold100 comparison commands

Use the same verified r06 Gold100 file, fixed train73 IDs, train-only negative
authority, seed, base config, source budget, and dev15 selection protocol in
both runs. Keep test12 closed. For six staged article passes, run the joint
baseline for six passes too. Compare actual optimizer steps and wall time as
well as the equal 73 × 6 article exposures. The fresh joint baseline command is
separate from an optional post-DAG joint fine-tune.

```bash
cd ArticleLocal-KG-DeBERTa
GOLD=/absolute/path/to/verified-r06-gold100.json
AUTH=docs/v3-pretraining/r06-train73-negative-authority.json
OUT=training/results/v3-dag-gold100-comparison
mkdir -p "$OUT"
GOLD="$GOLD" python -c 'import json,os; from training.v3_pretraining.corpus import R06GoldReader; r=R06GoldReader(os.environ["GOLD"]); r.validate_inventory(); ids=[a for a in r.gold if r.membership[a]=="train"]; assert len(ids)==73; print(json.dumps(ids))' > "$OUT/train73-ids.json"
conda run -n model-test-py312 python -m training.scripts.v3_joint_comparison \
  --ids-file "$OUT/train73-ids.json" --r06-gold "$GOLD" \
  --negative-authority "$AUTH" --passes 6 \
  --checkpoint "$OUT/joint.pt" --report "$OUT/joint.json"
conda run -n model-test-py312 python -m training.scripts.v3_staged_train \
  --phase extraction --ids-file "$OUT/train73-ids.json" --r06-gold "$GOLD" \
  --negative-authority "$AUTH" --checkpoint "$OUT/extraction.pt" \
  --report "$OUT/extraction.json"
# At each next phase boundary, calibrate and supply a new checkpoint-bound
# funnel.json plus source-acceptance.json. The runner refuses mismatched SHAs.
conda run -n model-test-py312 python -m training.scripts.v3_staged_train \
  --phase entity_role_time_attribution_sources --ids-file "$OUT/train73-ids.json" \
  --r06-gold "$GOLD" --negative-authority "$AUTH" \
  --parent "$OUT/extraction.pt" --funnel-policy "$OUT/extraction-funnel.json" \
  --source-acceptance "$OUT/extraction-source-acceptance.json" \
  --checkpoint "$OUT/phase2-sources.pt" --report "$OUT/phase2-sources.json"
# Repeat with each immediate predecessor and its newly bound artifacts for
# entity_identity, entity_role_time_attribution, event_identity,
# cluster_consumers. V23 Phase 4 requires predicted ASSERTED_BY option
# validation against the trained Phase 3 Entity identity checkpoint.
```

Compare exact source span F1 and retrieval recall/miss by kind, Entity union
candidate coverage, role/time/assertor attachment precision and recall, Entity
and Event coreference positive F1 and cluster metrics, ABOUT/CAUSES positive F1
and PR-AUC, Primary pairwise ordering, and end-to-end graph exact nodes/edges.
Report oracle metrics and predicted cascade metrics separately; include
checkpoint/policy SHA, matched predicted replay support, actual optimizer
steps, article exposures, peak memory, and latency. Use the same dev selection
rule and reserve test for one final locked evaluation.

Post-DAG joint fine-tuning is intentionally unimplemented. B3 witness and
TIER2 restoration are outside this training change; their only connection
impact is that full-cascade quality cannot be inferred from the phase smoke.
