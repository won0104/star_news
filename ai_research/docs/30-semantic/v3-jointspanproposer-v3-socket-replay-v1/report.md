# #41 JointSpanProposer → Canonical V3 Socket Compatibility Replay

## 결론

사전 동결된 내부 선택 결과는 `ARM_A`이다. 같은 224-article audit pool에서 exact proposal recall은 ARM A `0.921855`, ARM B `0.399283`, ARM C `0.905809`였다. B와 C 모두 A 대비 +0.03 gate를 통과하지 못했으므로 Holdout50에서는 ARM A만 confirmatory replay했다. #40 exact F1 `0.139691`를 오차 0으로 재현했다.

개선 source가 frozen TOP32에서 candidate recall을 회복하지 못했으므로 `CANDIDATE_RECALL_BOTTLENECK_WAS_CANONICAL_A_SPECIFIC=false`다. B의 큰 하락은 head-only transplant가 RUN40 DCE에 portable하지 않음을 보이고, C가 B보다 크게 회복한 것은 improved DCE dependency를 보여 주지만 C도 A보다 `-0.016046` 낮았다. 따라서 현재 증거는 cross-corpus candidate generalization 문제가 남았다는 쪽이다.

## 검증된 계약

- Frozen Canonical V3 architecture signature: `90e6e70d5ced536dba975621dfaeb68e611e77ff64d82e015654175f416686a9`
- D380 checkpoints: seed 1008/2008/3008 selected epoch 7/8/7 그대로 사용
- Semantic/Boundary thresholds: #40 D380 DEV39에서 고정된 값 그대로 사용
- Candidate policy: 모든 arm에서 sentence/label cell별 distinct TOP32
- ARM C의 improved DCE는 후보 identity 생성에만 사용하고 V3 입력에는 넣지 않음
- Holdout50은 preselection artifact와 SHA를 먼저 동결한 뒤 ARM A와 selected arm만 confirmatory 평가
- optimizer step, retraining, checkpoint/threshold reselection, policy sweep 모두 0/false

## 해석

### 직접 질문 답변

1. #40 ARM A proposer exact recall은 `0.921855`이다.
2. ARM B recall은 `0.399283`이다.
3. ARM C recall은 `0.905809`이다.
4. EVENT recall A/B/C는 `0.933269` / `0.316248` / `0.915377`, STATEMENT는 `0.916186` / `0.440522` / `0.901057`이다.
5. candidate total mean은 세 arm 모두 `428358`로 같고 A 대비 ratio는 B `1.000`, C `1.000`이다.
6. ARM B는 RUN40 DCE 위에서 portable하지 않았다.
7. ARM C가 B보다 훨씬 좋으므로 DCE dependency는 드러났지만, C도 A를 넘지 못했다.
8. Holdout 전에 선택된 arm은 `ARM_A`이다.
9. selected arm의 Holdout50 proposal recall은 `0.520675`이다.
10. `PROPOSAL_UNAVAILABLE`는 baseline `1022`에서 selected `1022`로, delta `0`이다.
11. rescued Gold는 `0`개, exact TP 전환은 `0`개, 전환율은 `0.000000`이다.
12. exact precision/recall/F1 delta는 각각 `0.000000` / `0.000000` / `0.000000`이다.
13. exact FP delta는 `0`로 FP inflation은 없다.
14. Semantic score parity는 유지됐다. 최대 차이는 `1.78814e-07`이다.
15. Boundary score parity도 유지됐다. 최대 차이는 `1.19209e-07`이다.
16. current ARM A end-to-end FN에서 가장 큰 항목은 candidate unavailable이며, 개선 proposer replay로는 이를 해결하지 못했다. 즉 현 병목은 candidate recall이고, 원인은 canonical-A만의 특수 한계라기보다 cross-corpus generalization으로 남는다.
17. release v2 socket에는 당분간 `RUN40_CANONICAL_A_TOP32` 유지가 권장된다.

`RELEASE_V2_SOCKET_STATUS=RELEASE_V2_SOCKET_KEEP_CURRENT_PROPOSER_FOR_NOW`이며 이번 작업에서 release/runtime는 수정하지 않았다.

## Machine-readable summary

```text
WORK_STATUS=JOINTSPANPROPOSER_V3_SOCKET_REPLAY_COMPLETE
ARM_A_PROPOSAL_RECALL=0.9218549422336327
ARM_B_PROPOSAL_RECALL=0.39928326914848095
ARM_C_PROPOSAL_RECALL=0.9058087291399229
SELECTED_PROPOSER_ARM=A
SELECTED_ARM_HOLDOUT_PROPOSAL_RECALL=0.520675105485232
ARM_A_HOLDOUT_EXACT_F1=0.13969099139632735
SELECTED_ARM_HOLDOUT_EXACT_F1=0.13969099139632735
PROPOSAL_UNAVAILABLE_BASELINE=1022
PROPOSAL_UNAVAILABLE_SELECTED=1022
RESCUED_GOLD_COUNT=0
RESCUED_EXACT_TP_COUNT=0
RESCUE_TO_EXACT_CONVERSION_RATE=0.0
IMPROVED_PROPOSER_PORTABLE_TO_RUN40_DCE=false
IMPROVED_PROPOSER_BUNDLE_RESCUES_CANDIDATES=false
CANDIDATE_RECALL_BOTTLENECK_WAS_CANONICAL_A_SPECIFIC=false
HOLDOUT_CONFIRMATION_SUPPORTED=false
RELEASE_V2_SOCKET_STATUS=RELEASE_V2_SOCKET_KEEP_CURRENT_PROPOSER_FOR_NOW
NEXT_EXPERIMENT=JOINTSPANPROPOSER_CROSS_CORPUS_GENERALIZATION_REVIEW
SHARED_CANDIDATE_V3_SCORE_PARITY=true
CANDIDATE_IDENTITY_ADAPTER_LOSS_COUNT=0
IMPROVED_PROPOSER_TRAIN_HOLDOUT50_OVERLAP=0
```
