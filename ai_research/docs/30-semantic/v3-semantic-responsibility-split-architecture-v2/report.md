# #35 Semantic Responsibility Split Architecture v2

이 결과는 architecture / contract / environment completion이다. Full training, performance selection, socket-candidate 판정, runtime/release integration을 수행하지 않았으며 성능 주장을 하지 않는다.

## 결론

`ARCHITECTURE_READY_FOR_TRAINING=true`. Next: `SEMANTIC_RESPONSIBILITY_SPLIT_TRAINING_V2`.

## 책임 분리 lineage

- #29/#30: 같은 verifier scalar에 scope pressure를 추가해 under/over trade-off와 calibration damage가 발생했다.
- #31: DCE-dominant failure가 아니라 verifier functional attribution이 중심임을 확인했다.
- #32: absolute calibration drift가 특히 boundary path를 따라감을 확인했다.
- #33: boundary-only calibrated adaptation에서도 scope objective 추가 이득은 지지되지 않았다.
- #34: Frozen A와 분리된 scorer에서 강한 scope-learning signal을 확인했다.
- #35: validity와 scope를 supervision, scalar, downstream ownership, gradient 경계까지 물리적으로 분리했다.

## #34 재해석

#34는 final scorer 평가가 아니라 scope-signal feasibility test였다. BOTH-only supervision은 의도적이었고, UNDER_ONLY failure·CORE shortfall·control degradation은 feasibility 신호를 부정하지 않는다. V2는 그 한계를 반영해 BOTH-only를 폐기하고 group utility, relation-aware set context, explicit delta-region을 채택했다.

## 사전등록 질문에 대한 답

1. 기존 A verifier는 candidate semantic validity, span 내부 의미, context, width/outside, RAW/DCE boundary evidence, start/end biaffine를 한 scalar에서 함께 담당했다.
2. ValidityV2는 candidate span 자체가 EVENT/STATEMENT proposition으로 의미적으로 성립 가능한지에 대한 absolute `validity_logit`만 소유한다.
3. ScopeScorerV2는 같은 containment group 안에서 minimal-but-complete boundary인지를 나타내는 group-local utility만 소유한다.
4. A에서 width embedding, outside path, multi-view의 scope-owned boundary 조합, start/end projection과 biaffine를 ValidityV2에서 제거했다. 제거/비재사용 A parameter는 **1,847,073**개다.
5. Boundary biaffine와 start/end boundary projection은 ValidityV2에 존재하지 않는다.
6. Width와 immediate outside evidence는 ScopeV2의 detached candidate/boundary evidence로 이동했다.
7. RAW/DCE inside mean은 Validity semantic side에 남고, RAW/DCE start/end/left/right는 Scope side로 분리했다. Scope가 받는 upstream evidence는 모두 detach된다.
8. `semantic_core`는 ValidityV2가 만든 label-conditioned candidate semantic representation이며 ScopeV2가 read-only(detached) 입력으로 사용한다.
9. Scope gradient가 Validity로 역전파될 수 있는가: **False** (contract상 False).
10. Validity는 EXACT=positive, SEMANTIC_NEGATIVE=negative, STRUCTURAL_SCOPE_ALTERNATIVE/UNKNOWN=masked다.
11. 조금 짧거나 긴 candidate를 validity negative로 학습해 scope pressure가 absolute validity에 다시 섞이는 것을 막기 위해 scope alternative를 mask한다.
12. Scope는 EXACT_PROPOSITION을 positive set, STRUCTURAL_SCOPE_ALTERNATIVE를 negative set으로 사용하며 semantic negative와 UNKNOWN은 사용하지 않는다.
13. #34 BOTH-only policy는 폐기했다.
14. Listwise group loss는 UNDER_ONLY, OVER_ONLY, BOTH와 multi-positive를 같은 contract로 표현한다.
15. ScopeGroupBuilder는 같은 article/sentence/label 안에서 strict containment edge의 connected component를 만든다.
16. group은 article, sentence, label 경계를 넘을 수 없다.
17. multi-positive group을 지원하며 TRAIN196 3-seed 합산 관측치는 **2250**개다.
18. ScopeScorerV2는 candidate별 utility를 출력해 group ranking을 일관되게 만들기 때문에 raw pairwise scorer가 아니다.
19. delta-region은 nested spans 사이에서 추가·제거된 left/right token region의 RAW/DCE_LOCAL mean representation과 empty mask다.
20. candidate 순열을 원래 identity로 되돌리면 utility가 허용오차 안에서 동일하다.
21. 단일 utility ordering이므로 pairwise cycle은 구조적으로 생기지 않는다.
22. Validity와 Scope score는 더하지 않는다.
23. decoder는 validity gate로 alive를 정한 뒤 같은 non-singleton group의 alive alternatives만 scope utility로 순위화하고 singleton은 보존하도록 설계됐다.
24. TRAIN196 3-seed authority 합계는 EXACT **16175**, SCOPE_ALTERNATIVE **315258**, SEMANTIC_NEGATIVE **626775**, UNKNOWN **106558**이다.
25. TRAIN196 3-seed scope group은 총 **13424**, non-singleton **12433**이다.
26. Gold 구조는 singleton **991**, BOTH **10549**, UNDER_ONLY **4102**, OVER_ONLY **463**이며 max group size는 **32**다.
27. 모든 구조·mask·gradient·real-batch smoke 조건을 통과해 #36 학습을 수행할 수 있는가: **True**.
28. ARCHITECTURE_READY_FOR_TRAINING=true.

## 환경 요약

- Current A verifier parameters: **1,880,353**
- ValidityV2 parameters: **624,129**
- ScopeV2 parameters: **1,455,429**
- Total new semantic head parameters: **2,079,558**
- Validity negative pool reduction after masking scope alternatives: **33.6451%** (seed 1008; candidate universe is seed-specific).
- Pathological giant group: **False**; max group size **32**.

## 해석 경계

- Validation24와 Round04는 architecture hyperparameter tuning에 사용하지 않았다.
- 새 ValidityV2 calibration threshold를 정하지 않았다.
- production `models/`, `runtime/`, `release/`는 수정하지 않았다.
- #36에서 처음으로 responsibility-specific training 및 end-to-end 성능을 평가한다.

## Machine-readable summary

```text
WORK_STATUS=SEMANTIC_RESPONSIBILITY_SPLIT_ARCHITECTURE_V2_COMPLETE
FULL_TRAINING=false
OPTIMIZER_STEP_COUNT=0
PERFORMANCE_SELECTION=false
SOCKET_CANDIDATE_DECISION=false
SEPARATE_SCOPE_RESPONSIBILITY_SIGNAL=true
VALIDITY_V2_IMPLEMENTED=true
SCOPE_GROUP_BUILDER_IMPLEMENTED=true
SCOPE_SCORER_V2_IMPLEMENTED=true
DECODER_INTERFACE_DEFINED=true
VALIDITY_V2_WIDTH_FEATURE=false
VALIDITY_V2_OUTSIDE_FEATURE=false
VALIDITY_V2_BOUNDARY_BIAFFINE=false
VALIDITY_V2_SEMANTIC_INSIDE=true
VALIDITY_V2_SENTENCE_CONTEXT=true
VALIDITY_V2_LABEL_FEATURE=true
SCOPE_V2_BOUNDARY_FEATURE=true
SCOPE_V2_OUTSIDE_FEATURE=true
SCOPE_V2_WIDTH_FEATURE=true
SCOPE_V2_DELTA_REGION=true
SCOPE_V2_GROUP_CONTEXT=true
SCOPE_GRADIENT_TO_VALIDITY=false
SCOPE_GRADIENT_TO_DCE=false
SCOPE_GRADIENT_TO_PROPOSER=false
VALIDITY_EXACT_POLICY=POSITIVE
VALIDITY_SCOPE_ALTERNATIVE_POLICY=MASK
VALIDITY_SEMANTIC_NEGATIVE_POLICY=NEGATIVE
VALIDITY_UNKNOWN_POLICY=MASK
SCOPE_PRIMARY_TRAIN_POLICY=ALL_SCOPE_GROUPS_WITH_POSITIVE_AND_NEGATIVE
GROUPING_POLICY=SAME_ARTICLE_SENTENCE_LABEL_STRICT_CONTAINMENT_CONNECTED_COMPONENT
PAIRWISE_SCORER_FINAL_ARCHITECTURE=false
GROUP_UTILITY_SCORER=true
PAIRWISE_CYCLE_BY_CONSTRUCTION=false
VALIDITY_V2_PARAMETER_COUNT=624129
SCOPE_V2_PARAMETER_COUNT=1455429
TOTAL_HEAD_PARAMETER_COUNT=2079558
TRAIN_EXACT_COUNT=16175
TRAIN_SCOPE_ALTERNATIVE_COUNT=315258
TRAIN_SEMANTIC_NEGATIVE_COUNT=626775
TRAIN_UNKNOWN_COUNT=106558
TRAIN_SCOPE_GROUP_COUNT=13424
TRAIN_SCOPE_SINGLETON_COUNT=991
TRAIN_SCOPE_NON_SINGLETON_COUNT=12433
TRAIN_MULTI_POSITIVE_GROUP_COUNT=2250
TRAIN_UNDER_ONLY_GROUP_COUNT=4102
TRAIN_OVER_ONLY_GROUP_COUNT=463
TRAIN_BOTH_GROUP_COUNT=10549
MAX_SCOPE_GROUP_SIZE=32
ARCHITECTURE_READY_FOR_TRAINING=true
NEXT_EXPERIMENT=SEMANTIC_RESPONSIBILITY_SPLIT_TRAINING_V2
```
