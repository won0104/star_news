# #40 Frozen Canonical Span Representation V3 Gold Scaling Study

## 결론

고정된 #38 V3 architecture와 #39 training core, 동일 DEV39, 동일 SSAFY Holdout50에서 reviewed Gold budget 95→190→285→380을 비교했다. 외부 exact F1은 **0.092346→0.139691**로 증가했고 `PERFORMANCE_SCALING_SUPPORTED=true`다. 그러나 D380 Semantic seed gate는 **1/3**이므로 `SEMANTIC_STABILITY_SCALING_SUPPORTED=false`다. Boundary는 fixed DEV39 intrinsic 축에서 보존됐다. 종합 판정은 `SCALING_HEADROOM_SUPPORTED=true`, `STRONG_V3_SCALING_SUPPORT=false`, 다음 단계는 `V3_SCALING_RESULT_CONSOLIDATION`이다.

## Data / freeze

- Gold380과 새 Holdout50 article/content overlap: **0 / 0**. Holdout50 manifest SHA parity도 PASS다.
- Gold380과 historical Validation24 overlap은 **24**다. 이 때문에 Validation24는 새 평가가 아니라 historical reference로만 유지했다.
- historical TRAIN196은 Gold380에 **196/196** 포함되며, fixed DEV39는 모든 budget에서 동일하다.
- TRAIN count: D95=56, D190=151, D285=246, D380=341. DEV는 모두 39다.
- nested TRAIN: T56⊂T151⊂T157⊂T246⊂T341.
- architecture signature는 exact다. historical #39 protocol signature `946c915...27c0`는 보존했고 training core는 exact parity다. 전체 protocol을 동일하다고 주장하지 않으며, 유일한 차이는 `DATA_ROLE_ASSIGNMENT=FIXED_RUN39_DEV39_NESTED_TRAIN_V1`이다.
- Holdout50은 epoch/checkpoint/threshold/seed/architecture 선택에 사용하지 않았다.

| Budget | Reviewed | EVENT Gold | STATEMENT Gold | Source rounds |
|---|---:|---:|---:|---|
| D95 | 95 | 1325 | 1679 | {"R1_06": 95} |
| D190 | 190 | 2990 | 3628 | {"R1_06": 190} |
| D285 | 285 | 4345 | 5498 | {"R10": 10, "R1_06": 244, "R7": 31} |
| D380 | 380 | 5502 | 7232 | {"R10": 30, "R1_06": 300, "R7": 50} |

## External Holdout50 curve

| Budget | TRAIN | DEV | exact F1 mean | seed std | DEV Semantic PR-AUC | DEV Boundary PR-AUC | Semantic gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| D95 | 56 | 39 | 0.092346 | 0.007695 | 0.510314 | 0.449428 | 0/3 |
| D190 | 151 | 39 | 0.120331 | 0.007481 | 0.592481 | 0.546850 | 2/3 |
| D285 | 246 | 39 | 0.134284 | 0.008731 | 0.613417 | 0.563089 | 0/3 |
| D380 | 341 | 39 | 0.139691 | 0.003829 | 0.615240 | 0.570945 | 1/3 |

RUN39 TRAIN157/DEV39 bridge의 Holdout50 exact F1은 **0.121910**다. D380-D95는 **+0.047345**, D380-RUN39 Holdout50은 **+0.017781**다. budget/F1 Spearman은 **1.000000**, log2-budget slope는 **0.024252**다. Adjacent gain은 **+0.027984, +0.013953, +0.005407**로 양수지만 포화 양상이다.

10,000회 paired article bootstrap에서 D380-D95 CI는 **[+0.034847, +0.061823]**, D380-RUN39 bridge CI는 **[+0.008530, +0.028311]**다. 마지막 D380-D285 CI는 **[-0.000350, +0.011926]**로 0을 포함한다.

## Semantic stability

| Budget | PR-AUC mean | std | range | EVENT PR-AUC | STATEMENT PR-AUC | seed gate | role |
|---|---:|---:|---:|---:|---:|---:|---|
| D95 | 0.510314 | 0.003544 | 0.007857 | 0.487009 | 0.530905 | 0/3 | false |
| D190 | 0.592481 | 0.015280 | 0.036749 | 0.603683 | 0.591214 | 2/3 | true |
| D285 | 0.613417 | 0.007627 | 0.016748 | 0.620384 | 0.608173 | 0/3 | false |
| D380 | 0.615240 | 0.018559 | 0.041007 | 0.642360 | 0.603188 | 1/3 | false |

D380에서는 seed1008이 EVENT/overall recall retention을, seed2008이 EVENT/STATEMENT/overall recall retention을 실패했고 seed3008만 통과했다. 따라서 PR-AUC 평균은 증가했지만 seed stability는 해결되지 않았다. Holdout50에는 explicit semantic-negative authority가 없으므로 Holdout semantic-negative PR-AUC/FPR과 semantic-negative FP는 `NOT_AVAILABLE_NO_EXPLICIT_NEGATIVE_AUTHORITY`다.

## Boundary stability

| Budget | PR-AUC | F1 | UNDER pair | OVER pair | LEFT | RIGHT | PARTIAL | role |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| D95 | 0.449428 | 0.484266 | 0.970825 | 0.780090 | 0.928571 | 0.930837 | 0.930919 | false |
| D190 | 0.546850 | 0.558251 | 0.976515 | 0.833575 | 0.945337 | 0.950186 | 0.955179 | false |
| D285 | 0.563089 | 0.571085 | 0.974108 | 0.868099 | 0.943365 | 0.952372 | 0.960290 | true |
| D380 | 0.570945 | 0.570928 | 0.975152 | 0.861636 | 0.945397 | 0.958154 | 0.964372 | true |

Boundary PR-AUC/F1과 shifted/partial pair discrimination은 D95 대비 D380에서 유지 또는 상승했다. D380의 fixed DEV39 intrinsic boundary role은 **true**다. 다만 DEV39에는 별도 R3/R4/R5 reviewed-pair manifest가 없으므로 CORE/R3/R4/R5 retention은 `NOT_AVAILABLE_NO_FIXED_DEV39_R3_R4_R5_REVIEW_PAIR_MANIFEST`이며, 겹치는 Validation24/Round04 값으로 대신 채우지 않았다.

## Checkpoint / overfit

- selected epochs: D95=1008:9,2008:6,3008:10; D190=1008:6,2008:9,3008:8; D285=1008:10,2008:9,3008:9; D380=1008:7,2008:8,3008:7.
- semantic-best epochs: D95=1008:5,2008:6,3008:8; D190=1008:7,2008:6,3008:5; D285=1008:10,2008:9,3008:9; D380=1008:7,2008:5,3008:8.
- joint-selected epoch range는 **4→3→1→1**, semantic-best epoch range는 **3→2→1→3**이다.
- semantic-best 대비 selected PR-AUC loss 평균은 D95=0.002659, D190=0.012297, D285=0.000000, D380=0.005635이다.
- Semantic best→epoch10 degradation 평균은 D95=0.019275, D190=0.056776, D285=0.029047, D380=0.042884이다. Boundary는 각각 0.010069, 0.023089, 0.042292, 0.033338이다.

`OVERFIT_STABILITY_IMPROVED=true`는 degradation의 단조 감소가 아니라 D380의 joint optimum seed range가 D95의 4에서 1로 감소했고 best epoch 평균이 소폭 뒤로 이동했다는 조건으로 성립했다. D380 semantic degradation 자체는 D95보다 커졌으므로 overfit 증거는 혼합적이다.

132개 epoch0~10 model state는 모두 존재하고 SHA가 검증됐으며 Git ignore 대상이다. checkpoint/threshold 선택에는 fixed DEV39만 사용했다.

## Error attribution and bottleneck

- FN D95→D380: `SEMANTIC_DEAD` **629→517**, `BOUNDARY_REJECTED` **265→208**, `PROPOSAL_UNAVAILABLE` **1022→1022**.
- D380 FN: `{"BOUNDARY_REJECTED": 208, "PROPOSAL_UNAVAILABLE": 1022, "SEMANTIC_DEAD": 517, "SURVIVED": 509}`.
- D380 FP: `{"BOUNDARY_COMPETITOR_SURVIVED_BOUNDARY": 2241, "UNREVIEWED_OR_OTHER": 2288}`. Holdout에는 semantic-negative authority가 없으므로 `UNREVIEWED_OR_OTHER`를 semantic-negative FP라고 재명명하지 않았다.
- D380 oracle exact F1: Oracle Semantic + learned Boundary **0.143885**, learned Semantic + Oracle Boundary **0.464343**, Oracle both **0.684767**.

Recall ceiling의 최대 항목은 frozen proposer의 `PROPOSAL_UNAVAILABLE=1022`다. 정확도 관점에서는 Oracle Boundary의 개선폭과 boundary-competitor FP가 커서 learned boundary discrimination도 주된 병목이다. 즉 하나의 병목으로 축약하면 안 되며, **proposal coverage가 recall 병목, boundary discrimination이 precision/exactness 병목**이다.

## Required questions — direct answers

1. Gold380∩Validation24는 0이 아니라 **24/24**다. 그래서 Validation24를 새 평가에서 제외했다. Gold380∩Holdout50은 article/content 모두 **0**이다.
2. TRAIN196은 Gold380에 **196/196** 포함된다.
3. Reviewed budgets와 TRAIN subsets 모두 exact nested다.
4. TRAIN/DEV는 D95 **56/39**, D190 **151/39**, D285 **246/39**, D380 **341/39**다.
5. EVENT/STATEMENT Gold는 D95 **1325/1679**, D190 **2990/3628**, D285 **4345/5498**, D380 **5502/7232**다.
6. 모든 run의 architecture signature와 parameter count 760,226은 동일하다.
7. #39 training core는 exact parity다. 전체 signature는 data-role override 때문에 동일하다고 주장하지 않는다.
8. selected epochs는 `D95=1008:9,2008:6,3008:10; D190=1008:6,2008:9,3008:8; D285=1008:10,2008:9,3008:9; D380=1008:7,2008:8,3008:7`다.
9. **Yes.** 12×11=132 checkpoint가 SHA까지 검증됐다.
10. D95 exact mean/std는 **0.092346/0.007695**다.
11. D190은 **0.120331/0.007481**다.
12. D285는 **0.134284/0.008731**다.
13. D380은 **0.139691/0.003829**다.
14. D380-D95는 **+0.047345**다.
15. 같은 Holdout50 축의 D380-RUN39 bridge는 **+0.017781**다.
16. Spearman은 **1.000000**다.
17. log2-budget slope는 **0.024252**다.
18. Adjacent gain은 **+0.027984, +0.013953, +0.005407**다.
19. Semantic PR-AUC mean/std는 위 Semantic 표와 같다.
20. PR-AUC range는 **0.007857→0.036749→0.016748→0.041007**로 D380에서 다시 커졌다.
21. seed gate pass count는 **0→2→0→1**이다.
22. D380은 2/3 이상이 아니라 **1/3**이다.
23. D380 Semantic role은 **false**다.
24. EVENT PR-AUC는 **0.487009→0.642360**, STATEMENT는 **0.530905→0.603188**로 증가했지만 D380 seed recall retention은 불안정했다.
25. Boundary PR-AUC/F1은 **0.449428/0.484266→0.570945/0.570928**로 증가했다.
26. UNDER/OVER/SHIFT/PARTIAL pair 성능은 위 표처럼 보존됐다.
27. CORE/R3/R4/R5는 DEV39 권위 부재로 **NOT_AVAILABLE**다.
28. D380 intrinsic Boundary role은 **true**다.
29. joint-selected epoch range는 4에서 1로 줄었다.
30. semantic-best epoch range는 3에서 3으로 최종 감소하지 않았다.
31. joint-selected 대비 semantic-best PR-AUC loss 평균은 D380 **0.005635**다.
32. D380 best→epoch10 degradation은 Semantic **0.042884**, Boundary **0.033338**다.
33. D285에서는 optimum이 뒤로 이동했지만 D380에서는 되돌아가 mixed evidence다.
34. Semantic-dead FN은 **629→517**로 줄었다.
35. Boundary-rejected FN은 **265→208**로 줄었다.
36. Holdout semantic-negative FP는 authority 부재로 **NOT_AVAILABLE**다.
37. boundary-competitor FP는 **2233→2241**로 줄지 않았다.
38. recall 병목은 proposer coverage, precision/exactness 병목은 boundary discrimination이다.
39. `PERFORMANCE_SCALING_SUPPORTED=true`.
40. `SEMANTIC_STABILITY_SCALING_SUPPORTED=false`.
41. `BOUNDARY_PRESERVED_UNDER_SCALING=true`.
42. `OVERFIT_STABILITY_IMPROVED=true`이지만 evidence는 mixed다.
43. `SCALING_HEADROOM_SUPPORTED=true`.
44. `STRONG_V3_SCALING_SUPPORT=false`.
45. 동일 Holdout50 축에서 RUN39 **0.121910**보다 D380 **0.139691**가 높아 구조의 external gain은 유지·개선됐다. historical Validation24 0.419957과는 직접 비교하지 않았다.
46. Reviewed Gold 추가는 성능에 가치가 있었지만 marginal gain은 포화되고 semantic variance가 남았다. 무조건 추가 scaling보다 결과 consolidation이 우선이다.
47. 다음 단계는 **V3_SCALING_RESULT_CONSOLIDATION**이다.

## Decision

- `PERFORMANCE_SCALING_SUPPORTED=true`
- `SEMANTIC_STABILITY_SCALING_SUPPORTED=false`
- `BOUNDARY_PRESERVED_UNDER_SCALING=true`
- `OVERFIT_STABILITY_IMPROVED=true`
- `SCALING_HEADROOM_SUPPORTED=true`
- `STRONG_V3_SCALING_SUPPORT=false`
- `RUN39_V3_READY_FOR_SCALING_STUDY=false` (historical truth preserved)
- `NEXT_EXPERIMENT=V3_SCALING_RESULT_CONSOLIDATION`

## Machine-readable summary

```text
WORK_STATUS=FROZEN_V3_GOLD_SCALING_STUDY_COMPLETE
DATA_ROLE_OVERRIDE_STATUS=FIXED_DEV39_NESTED_TRAIN_PROTOCOL
ARCHITECTURE_FROZEN=true
TRAINING_CORE_PARITY_WITH_RUN39=true
SCALING_EVALUATION_AXIS=SSAFY_ROUND01_HOLDOUT50
HISTORICAL_RUN39_TRAINING_PROTOCOL_SIGNATURE_SHA256=946c9157fa7c6ade322e05e0abbf95d5f3d9320a1c91d5443361e5e6e64327c0
SCALING_DATA_ROLE_PROTOCOL_SIGNATURE_SHA256=b7be2e315feecbc2d8ecacea3e87522e54e640dbbac486abaa1742aa6f081ca2
MODEL_PARAMETER_COUNT=760226
SEEDS=1008,2008,3008
MAX_EPOCHS=10
D95_EXACT_MEAN=0.09234634923378138
D190_EXACT_MEAN=0.12033062771572461
D285_EXACT_MEAN=0.13428366039262105
D380_EXACT_MEAN=0.13969099139632735
D95_EXACT_STD=0.007694575295611805
D190_EXACT_STD=0.007481223105605034
D285_EXACT_STD=0.008730819684395718
D380_EXACT_STD=0.0038290013838889504
D380_MINUS_D95_EXACT=0.04734464216254597
D380_MINUS_RUN39_HOLDOUT50=0.01778090297275811
EXACT_F1_SCALING_SPEARMAN=1.0
EXACT_F1_LOG2_SLOPE=0.024251723923793888
D95_SEMANTIC_SEED_PASS_COUNT=0
D190_SEMANTIC_SEED_PASS_COUNT=2
D285_SEMANTIC_SEED_PASS_COUNT=0
D380_SEMANTIC_SEED_PASS_COUNT=1
D380_SEMANTIC_ROLE_SUPPORTED=false
D380_BOUNDARY_ROLE_SUPPORTED=true
D380_GOLD_REJECTION=0.5878839204802295
D380_SHORT_RECALL=0.2697095435684647
D380_CORE=NOT_AVAILABLE_NO_FIXED_DEV39_R3_R4_R5_REVIEW_PAIR_MANIFEST
PERFORMANCE_SCALING_SUPPORTED=true
SEMANTIC_STABILITY_SCALING_SUPPORTED=false
BOUNDARY_PRESERVED_UNDER_SCALING=true
OVERFIT_STABILITY_IMPROVED=true
SCALING_HEADROOM_SUPPORTED=true
STRONG_V3_SCALING_SUPPORT=false
NEXT_EXPERIMENT=V3_SCALING_RESULT_CONSOLIDATION
```
