# V3 Generic TimeExpression Completion + Event Attachment + Article-relative Normalization v1

## Decision

`WORK_STATUS=GENERIC_TIME_EXPRESSION_RUNTIME_READY_WITH_LIMITATIONS`.

The canonical bundle now accepts raw Article text and produces subtype-free, span-native
`TimeExpression[]`, directed Event→TimeExpression attachments, and conservative
deterministic normalization. It preserves unresolved raw evidence and materializes a
canonical `TIME` node and `OCCURRED_ON` edge only when both attachment and normalization
contracts are satisfied. Existing Event, Statement, Trigger, StatementType, B2,
EntityMention, and Entity soft-priority output remained at exact parity.

## Source and immutable scope

The source of truth is Construction Gold v3 Round01–03 Curated RC1
(`0e4d1fa7f1dc0969fb8d8208c67cdd07b037f68b7acef71afd3d02af4ea80002`) and guideline
`v3-guideline-r02-curated-rc1`
(`a3c3012750b27b0ab3946a0156e43012e1b95204787deb73f50e4fbbab5030a1`).
Gold, guideline, Round04, pilot_test, and original 1K dev/test were not changed or used.
The frozen KF-DeBERTa backbone, all existing runtime lanes, Entity checkpoint/threshold,
and Entity soft-priority contract were unchanged.

Training reused the seed-1008 article-level pilot_train split: 96 internal-train and 24
internal-validation articles. pilot_dev15 was evaluated once only after architecture,
checkpoint, epochs, and thresholds had been frozen; it did not feed selection.

## ③ Generic TimeExpression extraction

The selected representation is `SPAN_NATIVE_BINARY_TIME_EXPRESSION`, using frozen
KF-DeBERTa L10, the existing document context and span encoder, independent binary
scores, and deterministic character-aware decoding. DATE/TIME/DURATION/SET neural
subtypes were not introduced. Extraction does not consume `publishedAt`, Presence,
Entity, Entity priority, B2, or normalization output.

The full geometry audit found 865 mentions over 150 articles and 601 unique surfaces.
All 865 are in the candidate universe: 858 align to exact token boundaries and 7 require
character-internal boundaries; alignment failure, truncation loss, and cross-sentence
mentions are all zero. Maximum width is 21 covering tokens / 44 characters. Four strict
nested pairs and one identical-boundary duplicate establish that a flat exclusive BIO
contract is not truth-preserving.

Bounded tiny overfit reduced loss, reached 46 TP / 141 FP / 2 FN, retained all 6 nested
mentions and jointly recovered all 3 nested pairs in its selected diagnostic. This
confirms simultaneous nested representation and learnability. The main model was fresh
trained for at most 8 epochs with unweighted BCE and the predeclared negative sampling
contract. Internal-validation PR-AUC selected epoch 7, then the fixed grid selected
threshold 0.8.

Internal validation produced TP/FP/FN 93/90/54, P/R/F1
0.5082/0.6327/0.5636 and PR-AUC 0.5235. The frozen pilot_dev reference produced
84/184/36, P/R/F1 0.3134/0.7000/0.4330. pilot_dev contains one recoverable nested pair;
the final release-purpose model recovered neither member. Thus the representation and
tiny proof are nested-capable, but final nested generalization is an explicit limitation.

The release-purpose model was freshly trained on pilot_train120 for the selected seven
epochs. Its staged checkpoint is `weights/time_expression.pt`, SHA256
`38bcffd9012c2550d5c447aacc0850630ec5f4b0a4cb23b3898def43753c9b18`.

## ⑤ Event→TimeExpression attachment

The selected directed binary pair model uses the existing `DirectedPairEncoder`. It is
trained independently of normalization and `publishedAt`, with UNKNOWN masking for
non-exhaustive or unresolved supervision. Internal-validation oracle PR-AUC selected
epoch 8, followed by fixed threshold 0.4.

Gold Event + Gold TimeExpression oracle F1 was 0.8142 internally and 0.7821 on the frozen
pilot_dev reference (P/R 0.7278/0.8452 there). The four pilot_dev cascade diagnostics
separate upstream effects. The fully predicted Event + predicted TimeExpression cascade
was TP/FP/FN 31/144/124, P/R/F1 0.1771/0.2000/0.1879. FIRST LOSS attributes 109 Gold
links to Event upstream misses, 11 to TimeExpression upstream misses, 4 to attachment
misses after both upstream items were available, and 31 to full success.

The release-purpose attachment model was freshly trained on pilot_train120 for eight
epochs. Its staged checkpoint is `weights/event_time_attachment.pt`, SHA256
`75deb17ce8cbefd025fcfe9e42a1b2f399a6e7c240242f3e75483caec4b21bfb`.

## ⑧ Normalization and graph assembly

Normalization uses only deterministic rules and article `publishedAt` when a relative
rule requires a reference. The system clock is never consulted. Among 786 reviewed
training/dev expressions, normalized Gold exists for only 8 (1.02% coverage). The rules
resolved 156 expressions and left 630 unresolved. On the 8 labeled examples, exact
accuracy was 7/8 (87.5%): absolute forms were 7/7, while the sole relative example
conflicted with processed `publishedAt` provenance. These sparse labels do not certify
unlabeled rule outputs, so the lane remains `ACTIVE_WITH_LIMITATIONS`.

pilot_dev graph replay preserved all 268 raw TimeExpression rows and 175 attachments.
Only 16 canonical `TIME` nodes and 21 `OCCURRED_ON` edges met materialization conditions;
248 unresolved or unattached mentions remained raw evidence. Fake Time nodes, dangling
references, and duplicate Time edges were all zero. Serialization was deterministic and
all prior-lane outputs had exact parity.

## Time candidate / Event-Time pair density audit

The additional audit was performed after all model and threshold choices were frozen.
Stage ⑤ uses predicted Event × stage-③ decoded/accepted TimeExpression only; it never
forms a Cartesian product against raw span candidates.

| pilot_dev per article | mean | median | p90 | max |
| --- | ---: | ---: | ---: | ---: |
| Raw Time span candidates | 27,847.4 | 19,632 | 46,238 | 78,398 |
| Accepted TimeExpressions | 17.87 | 13 | 38 | 43 |
| Predicted Events | 12.33 | 9 | 29 | 31 |
| Eligible Event→Time pairs | 250.6 | 169 | 744 | 1,015 |

Time extraction cost 0.5661 s/article and attachment cost 0.00966 s/article. Gold
attachment sentence-distance cumulative coverage (1,004 links) is 90.94% same-sentence,
96.41% within ±1, 98.51% within ±2, and 98.80% within ±3; 1.20% are farther.

`PAIR_EXPLOSION_CONFIRMED=false`: the typical eligible pair universe is hundreds rather
than thousands. The isolated max of 1,015 does not meet the predeclared systemic p90
criterion. The large raw search space remains explicit ③ inference optimization debt;
no architecture, checkpoint, training setting, or threshold was changed in response.

## Release and continuation

Canonical runtime ID is `eventframe_runtime_candidate_v3_generic_time_freeze`.
TimeExpression, Event-Time attachment, and deterministic normalization are all staged as
`ACTIVE_WITH_LIMITATIONS`. The isolated release-only copy passed import, config load,
checkpoint SHA validation, external pinned base load, sample inference, nested-capable
serialization contract, and deterministic JSON without access to `training/results` or
experiment code.

This milestone is ready to hand off to Work Bundle #3 Entity Identity + Participant
Resolution. It does not execute that work. Entity Coreference, Participant Resolution,
Event Coreference, Assertor, ABOUT, CAUSES, and SUBEVENT_OF remain NOT_RUN.

The implementation/result commit is `bce438c`. A normal `git push origin master` was
attempted after the commit, but the environment's security review rejected external
egress because ownership of the configured GitHub remote could not be verified while
the push included model weights. No force push or workaround was attempted.
`PUSH_STATUS=UNPUSHED`; cross-device continuation is not complete until that commit and
its Git LFS objects are pushed from an authorized environment.

## Artifact map

- Geometry and representation: `gold_geometry_audit.json`,
  `candidate_universe_audit.json`, `overlap_nested_diagnostics.json`
- Supervision and training: `negative_policy.json`,
  `extraction_negative_sampling_audit.json`, `train_config.json`, `epoch_metrics.json`
- Selection and evaluation: `checkpoint_selection.json`, `threshold_metrics.json`,
  `internal_validation_metrics.json`, `pilot_dev_reference_metrics.json`
- Attachment: `time_attachment_candidate_audit.json`,
  `time_attachment_oracle_metrics.json`, `time_attachment_cascade_metrics.json`
- Normalization and failure analysis: `normalization_contract.md`,
  `normalization_metrics.json`, `first_loss.json`
- Runtime/release: `runtime_integration.json`, `graph_replay.json`,
  `regression_results.json`, `candidate_density.json`, `latency_metrics.json`,
  `release_manifest.json`, `release_self_containment_smoke.json`
