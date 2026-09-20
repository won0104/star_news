# V3 Event Coreference Calibration & Prior Recovery v1

## 사람이 읽는 최종 답변

1. 현재 interaction checkpoint의 fine threshold만으로 gate를 넘는 지점이 있었다. 0.620, 0.630–0.670 범위의 10개 operating point가 precision 0.50과 F1 0.40을 동시에 만족했다.
2. 사전 고정 selection rule은 **0.640**을 선택했다. Internal TP/FP/FN/TN은 46/29/100/5,450이고 P/R/F1은 **0.6133/0.3151/0.4163**이다.
3. Phase A가 통과했으므로 PRIOR_A/B/C retraining은 실행하지 않았다. Checkpoint tensor와 epoch8 PR-AUC 0.3943259295는 그대로다.
4. PRIOR_A/B/C는 모두 `NOT_RUN_FINE_THRESHOLD_PASS`다. 가장 좋은 prior config를 선정하지 않았다.
5. MERGE weight 4 제거 효과는 이번 work unit에서 측정하지 않았다.
6. KEEP exposure 8→16→32 효과도 측정하지 않았다.
7. PR-AUC는 #4.2의 **0.3943259295**를 numerical delta 0으로 유지했다.
8. Precision 0.6133과 F1 0.4163으로 두 gate를 동시에 넘었다. Coarse 0.6 대비 precision은 +0.1376, F1은 +0.0227다.
9. Frozen pilot Gold/Gold도 PR-AUC **0.6800**, P/R/F1 **0.6923/0.6000/0.6429**로 non-zero signal을 유지했다. Pilot은 설정 변경에 사용하지 않았다.
10. Complete-link는 deterministic하며 bridge catastrophe가 없었다. Internal B³ F1 0.9178, pairwise F1 0.3438, split/merge error 113/13, 최대 cluster 5다.
11. Event Identity를 article-local limited runtime으로 승격했다. Pilot 15개 실제 release replay에서 raw EventFrame 185개를 100% 유지하면서 LocalEvent 136개와 member edge 185개를 만들었고 fake/dangling/duplicate lifted Event는 0이다.
12. Calibration/prior blocker는 해소됐다. 남은 핵심 제한은 fully predicted cascade의 Event upstream recovery와 internal-validation threshold의 외부 일반화다. Production certification으로 해석하지 않는다.

## 실행 계약과 근거

Phase A는 SHA256 `be70dfaf8a4643f73f63bc348f879f997ef746e563d322b6b3697a0fbbc5b72f`인 #4.2 checkpoint를 strict-load해 MPS로 수행했다. Interaction architecture, 7개 channel, scalar policy, candidate universe, complete-link, Gold/guideline과 모든 upstream model을 바꾸지 않았다. Release에는 동일 byte를 Git LFS 대상으로 복사했고 runtime config가 calibration threshold 0.64를 별도로 기록한다.

Fully predicted pilot FIRST LOSS는 Event upstream miss 26, candidate miss 0, exact-recovered pair classification miss 0, identity success 4다. Gold/Gold cluster diagnostic의 split/merge error는 12/8이며 서로 다른 evaluation universe임을 분리해 기록했다.

Task-targeted tests는 80개를 모두 통과했다. Canonical suite는 318개를 실행했고 기존 viewer package shadowing import error 3건과 historical runtime config의 `entity_candidate_restriction` 누락 error 1건 때문에 FAIL이다. 이번 Event identity 변경에서 발생했던 결정성 및 historical status 회귀는 수정 후 targeted suite에서 통과했다. Release bundle strict-load, pilot15 runtime→graph replay와 deterministic serialization을 별도로 확인했다.

## Machine-readable

WORK_STATUS=EVENT_IDENTITY_RUNTIME_READY_WITH_LIMITATIONS
PHASE_A_FINE_THRESHOLD_EXECUTED=true
PHASE_A_FINE_THRESHOLD_PASS=true
PHASE_A_SELECTED_THRESHOLD=0.64
PHASE_A_PR_AUC=0.39432592949996154
PHASE_A_PRECISION=0.6133333333333333
PHASE_A_RECALL=0.3150684931506849
PHASE_A_F1=0.416289592760181
PHASE_B_PRIOR_TUNING_EXECUTED=false
SELECTED_PRIOR_CONFIG=NOT_RUN_FINE_THRESHOLD_PASS
SELECTED_KEEP_PER_MERGE=8
SELECTED_MERGE_WEIGHT=4
SELECTED_EPOCH=8
SELECTED_THRESHOLD=0.64
FINAL_INTERNAL_PR_AUC=0.39432592949996154
FINAL_INTERNAL_PRECISION=0.6133333333333333
FINAL_INTERNAL_RECALL=0.3150684931506849
FINAL_INTERNAL_F1=0.416289592760181
DELTA_PR_AUC_VS_PAIR_INTERACTION=0.0
DELTA_PRECISION_VS_PAIR_INTERACTION=0.13760517799352745
DELTA_F1_VS_PAIR_INTERACTION=0.022715295571425986
PILOT_GOLD_GOLD_PR_AUC=0.6800444823250829
PILOT_GOLD_GOLD_PRECISION=0.6923076923076923
PILOT_GOLD_GOLD_RECALL=0.6
PILOT_GOLD_GOLD_F1=0.6428571428571429
EVENT_CLUSTER_B3_F1=0.9178371291120689
EVENT_CLUSTER_PAIRWISE_F1=0.34375
EVENT_CLUSTER_SPLIT_ERROR=113
EVENT_CLUSTER_MERGE_ERROR=13
EVENT_CLUSTER_MAX_SIZE=5
FALSE_MERGE_CATASTROPHE=false
EVENT_IDENTITY_RUNTIME_PROMOTED=true
EVENT_IDENTITY_STATUS=EVENT_IDENTITY_RUNTIME_READY_WITH_LIMITATIONS
GRAPH_REPLAY_STATUS=PASS
FAKE_EVENT_COUNT=0
DANGLING_EVENT_REFERENCE_COUNT=0
READY_FOR_ASSERTOR=true
CURATED_GOLD_MODIFIED=false
GUIDELINE_MODIFIED=false
BACKBONE_MODIFIED=false
EVENT_PROPOSITION_MODIFIED=false
TRIGGER_MODIFIED=false
B2_MODIFIED=false
ENTITY_LANES_MODIFIED=false
TIME_LANES_MODIFIED=false
PAIR_INTERACTION_ARCHITECTURE_MODIFIED=false
PAIR_INTERACTION_CHANNELS_MODIFIED=false
PAIR_CANDIDATE_UNIVERSE_MODIFIED=false
EVENT_CLUSTERING_POLICY_MODIFIED=false
SYNTHETIC_EVENT_COREFERENCE_USED=false
PILOT_TEST_USED=false
ORIGINAL_1K_DEV_TEST_USED=false
