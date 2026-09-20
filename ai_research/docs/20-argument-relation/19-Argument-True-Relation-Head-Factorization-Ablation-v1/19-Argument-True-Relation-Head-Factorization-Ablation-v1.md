# 19. Argument True Relation-Head Factorization Ablation v1

- `TRUE_HEAD_ISOLATED_SIGNAL = MIXED`
- `TRUE_HEAD_END_TO_END = INCONCLUSIVE`
- `ARGUMENT_RELATION_HEAD_ARCHITECTURE = INCONCLUSIVE`
- `PARAMETER_MATCHED_CAPACITY_CONTROL_RECOMMENDED = false`
- `MULTI_SEED_CONFIRMATION_RECOMMENDED = false`
- `TRAINING_STREAM_FACTORIZATION = NOT_PERFORMED`
- `GOLD_ACTOR_COVERAGE_AUDIT_REQUIRED = true`
- Gold-only seed1008, 동일 MPS backend, Phase/branch 순차 학습; production adoption 아님
- Test: `test_enabled=false`, `test_tensorized=false`, `test_evaluation_count=0`, `test_used_for_selection=false`

## 1. Architecture boundary

공유 경계는 frozen KF-DeBERTa cache → DocumentContextEncoder → CandidateSpanEncoder의 object representation까지다. TRUE branch는 그 다음 Event↔Candidate 해석의 첫 learned parameter인 kind/distance/order/task embedding과 projection을 포함한 `DirectedPairEncoder` 전체를 relation/family별로 복제했다. 공통 learned pair vector는 만들지 않았다. Trigger conditioning, typed eligibility, sampler, threshold, loss weight는 변경하지 않았다.

Pair universe parity=`PASS`; train/dev combined SHA `564ae95fbf910ab1aac2d37236fef4a91b9d553f19fc72471794dbab65433b54` / `99e9c377d2f56c6c6eba92cd1532550c34dba21d6739411ecba15d4647e9edfd`.

### 판정 정정: parameter 분리와 학습 분리는 다르다

이 실험은 PairEncoder와 classifier parameter만 relation별로 분리했다. 학습 데이터와 sampling stream은 분리하지 않았다. 실제 구현에서 모든 relation Head는 동일한 sampled pair mask를 사용하며, 각 binary loss는 그 전체 active pair에 대해 계산된다. 따라서 ACTOR Head도 ACTOR 중심의 별도 학습 population을 받은 것이 아니라, train 기준 ACTOR 115개와 나머지 대량의 non-ACTOR가 섞인 동일 분포를 그대로 받았다. TRUE_FACTORIZED의 Participant/Temporal/Place Head에도 동일한 문제가 남아 있다.

그러므로 이 결과는 `relation-specific PairEncoder가 불필요하다`거나 `shared pair representation이 충분하다`는 근거가 아니다. 확인된 것은 **parameter isolation만 수행하고 Head별 dataset/sampling을 분리하지 않으면 희소 relation의 학습 분포가 그대로 유지된다**는 점뿐이다. 아래 수치표는 실행 결과로 보존하되 architecture 우열에 대한 인과 판정에는 사용하지 않는다.

### Gold ACTOR coverage 의심

관측된 natural train pair label은 ACTOR=115, TARGET=884로 약 7.7배 차이가 난다. 그러나 현재 보고서에는 source Event별 ACTOR annotation coverage가 없다. `Event마다 명시적 ACTOR가 존재해야 한다`는 task 가정이 Gold annotation policy와 일치한다면 이 차이는 단순 class imbalance보다 Gold 누락 또는 변환 손실을 먼저 의심해야 하는 신호다. 반대로 implicit/unknown actor를 Gold에서 생략하는 annotation policy라면 일부 차이는 정상일 수 있다. 이 구분은 아직 검증하지 않았다.

후속 학습 전에 최소한 raw Gold → processed Gold → tensorized pair 단계별로 다음을 감사해야 한다.

- source Event 수와 Event별 ACTOR/TARGET 보유 여부: ACTOR only, TARGET only, both, neither
- raw Gold에 ACTOR가 없는 Event 수와 annotation policy상 허용 여부
- raw Gold ACTOR가 processed/tensorized 단계에서 사라진 수와 사유
- ACTOR span의 candidate universe 포함률 및 unmatched/filtered count
- article/Event type별 ACTOR coverage와 소수 annotation pattern 편중

이 audit 전에는 현재 ACTOR 희소성을 정상적인 자연 분포로 전제하지 않는다.

## 2. Parameter isolation audit

B의 4개와 C의 3개 PairEncoder를 Phase I/II 각각 검사했다. Python object, parameter namespace, `Parameter` identity, storage pointer가 모두 분리됐고 clone 직후 숫자 SHA만 동일했다.

| Phase | Branch | Object distinct | Namespace distinct | Parameter unshared | Storage unshared | Initial numeric clone equal |
|---|---|---:|---:|---:|---:|---:|
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | true | true | true | true | true |
| PHASE_I_ISOLATED | TRUE_FACTORIZED | true | true | true | true | true |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | true | true | true | true | true |
| PHASE_II_END_TO_END | TRUE_FACTORIZED | true | true | true | true | true |

## 3. Gradient isolation audit

Gate status=`PASS`. 공통 upstream을 freeze한 real train article 하나에서 각 component loss를 단독 backward했다.

| Branch | Loss namespace | Intended PairEncoder grad | Intended classifier grad | Other paths zero/None | Upstream zero/None |
|---|---|---:|---:|---:|---:|
| TRUE_FOUR_INDEPENDENT | actor | 1.520320 | 0.581239 | true | true |
| TRUE_FOUR_INDEPENDENT | target | 1.431623 | 0.620912 | true | true |
| TRUE_FOUR_INDEPENDENT | place | 1.257290 | 0.466663 | true | true |
| TRUE_FOUR_INDEPENDENT | time | 10.462003 | 4.442275 | true | true |
| TRUE_FACTORIZED | participant | 2.574176 | 0.976180 | true | true |
| TRUE_FACTORIZED | temporal | 10.462003 | 4.442275 | true | true |
| TRUE_FACTORIZED | place | 1.221188 | 0.468211 | true | true |

## 4. Phase I isolated-head result

DocumentContextEncoder와 CandidateSpanEncoder는 historical Gold-only selected state로 고정했다. 동일 object cache를 세 branch가 공유했고, TRUE branch는 relation/family별 optimizer와 clipping을 사용했다. Official selection은 PLACE를 제외한 ACTOR/TARGET/TIME macro F1이다.

| Metric | FIVE_WAY | TRUE_FOUR_INDEPENDENT | TRUE_FACTORIZED |
|---|---:|---:|---:|
| ACTOR TP | 1 | 1 | 1 |
| ACTOR FP | 4 | 3 | 3 |
| ACTOR FN | 14 | 14 | 14 |
| ACTOR precision | 0.200000 | 0.250000 | 0.250000 |
| ACTOR recall | 0.066667 | 0.066667 | 0.066667 |
| ACTOR F1 | 0.100000 | 0.105263 | 0.105263 |
| ACTOR PR-AUC | 0.097341 | 0.101392 | 0.101931 |
| TARGET F1 | 0.956522 | 0.970000 | 0.965517 |
| TARGET PR-AUC | 0.984357 | 0.991109 | 0.989542 |
| TIME F1 | 0.838983 | 0.842553 | 0.846473 |
| TIME PR-AUC | 0.906869 | 0.884825 | 0.868893 |
| EVALUABLE_RELATION_MACRO_F1 | 0.631835 | 0.639272 | 0.639084 |
| EVALUABLE_RELATION_MACRO_PR_AUC | 0.662856 | 0.659109 | 0.653455 |
| PLACE train PR-AUC | 1 | 0.944161 | 0.958759 |
| PLACE dev prediction count | 0 | 0 | 0 |

### SHARED_FIVE_WAY epoch trajectory

| Epoch | ACTOR TP/FP/FN | ACTOR Recall | ACTOR F1 | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/0/15 | 0 | 0 | 0.107790 | 0.935961 | 0.858369 | 0.598110 |
| 2 | 0/0/15 | 0 | 0 | 0.086805 | 0.839827 | 0.801527 | 0.547118 |
| 3 | 0/0/15 | 0 | 0 | 0.093780 | 0.946860 | 0.855932 | 0.600931 |
| 4 | 0/2/15 | 0 | 0 | 0.108033 | 0.956098 | 0.837607 | 0.597901 |
| 5 | 0/0/15 | 0 | 0 | 0.100195 | 0.877778 | 0.851064 | 0.576281 |
| 6 | 0/2/15 | 0 | 0 | 0.110716 | 0.965517 | 0.848739 | 0.604752 |
| 7 | 1/4/14 | 0.066667 | 0.100000 | 0.097341 | 0.956522 | 0.838983 | 0.631835 |
| 8 | 0/3/15 | 0 | 0 | 0.101601 | 0.960396 | 0.848980 | 0.603125 |
| 9 | 0/1/15 | 0 | 0 | 0.113965 | 0.959596 | 0.843882 | 0.601159 |
| 10 | 0/0/15 | 0 | 0 | 0.091503 | 0.956098 | 0.839506 | 0.598535 |
| 11 | 0/2/15 | 0 | 0 | 0.063192 | 0.960784 | 0.859438 | 0.606741 |

### TRUE_FOUR_INDEPENDENT epoch trajectory

| Epoch | ACTOR TP/FP/FN | ACTOR Recall | ACTOR F1 | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/0/15 | 0 | 0 | 0.104969 | 0.653333 | 0.842912 | 0.498748 |
| 2 | 0/0/15 | 0 | 0 | 0.075011 | 0.946341 | 0.839506 | 0.595283 |
| 3 | 0/0/15 | 0 | 0 | 0.098297 | 0.980392 | 0.832579 | 0.604324 |
| 4 | 1/3/14 | 0.066667 | 0.105263 | 0.101392 | 0.970000 | 0.842553 | 0.639272 |
| 5 | 0/0/15 | 0 | 0 | 0.082871 | 0.965517 | 0.852459 | 0.605992 |
| 6 | 0/2/15 | 0 | 0 | 0.102847 | 0.945813 | 0.842975 | 0.596263 |
| 7 | 0/3/15 | 0 | 0 | 0.081971 | 0.979798 | 0.852321 | 0.610706 |
| 8 | 0/0/15 | 0 | 0 | 0.103261 | 0.955665 | 0.843882 | 0.599849 |

### TRUE_FACTORIZED epoch trajectory

| Epoch | ACTOR TP/FP/FN | ACTOR Recall | ACTOR F1 | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/0/15 | 0 | 0 | 0.109244 | 0.783133 | 0.858268 | 0.547133 |
| 2 | 0/0/15 | 0 | 0 | 0.079605 | 0.955224 | 0.845528 | 0.600251 |
| 3 | 0/0/15 | 0 | 0 | 0.098622 | 0.975369 | 0.819820 | 0.598396 |
| 4 | 0/1/15 | 0 | 0 | 0.112552 | 0.965174 | 0.838983 | 0.601386 |
| 5 | 0/0/15 | 0 | 0 | 0.095552 | 0.975124 | 0.859504 | 0.611543 |
| 6 | 1/3/14 | 0.066667 | 0.105263 | 0.101931 | 0.965517 | 0.846473 | 0.639084 |
| 7 | 1/4/14 | 0.066667 | 0.100000 | 0.108066 | 0.951923 | 0.840336 | 0.630753 |
| 8 | 0/2/15 | 0 | 0 | 0.095681 | 0.956098 | 0.834008 | 0.596702 |
| 9 | 0/2/15 | 0 | 0 | 0.110694 | 0.955665 | 0.730964 | 0.562210 |
| 10 | 0/0/15 | 0 | 0 | 0.095806 | 0.974874 | 0.838983 | 0.604619 |

## 5. Phase II end-to-end result

세 branch 모두 historical initialization state에서 fresh start했다. DocumentContextEncoder/CandidateSpanEncoder는 trainable이고 TRUE relation PairEncoder는 계속 독립이다.

| Metric | FIVE_WAY | TRUE_FOUR_INDEPENDENT | TRUE_FACTORIZED |
|---|---:|---:|---:|
| ACTOR TP | 4 | 0 | 0 |
| ACTOR FP | 13 | 0 | 0 |
| ACTOR FN | 11 | 15 | 15 |
| ACTOR precision | 0.235294 | 0 | 0 |
| ACTOR recall | 0.266667 | 0 | 0 |
| ACTOR F1 | 0.250000 | 0 | 0 |
| ACTOR PR-AUC | 0.153856 | 0.119951 | 0.142762 |
| TARGET F1 | 0.974874 | 0.980000 | 0.979798 |
| TARGET PR-AUC | 0.976959 | 0.992371 | 0.992915 |
| TIME F1 | 0.848739 | 0.864865 | 0.869919 |
| TIME PR-AUC | 0.867329 | 0.883812 | 0.868192 |
| EVALUABLE_RELATION_MACRO_F1 | 0.691205 | 0.614955 | 0.616572 |
| EVALUABLE_RELATION_MACRO_PR_AUC | 0.666048 | 0.665378 | 0.667956 |
| PLACE train PR-AUC | 0.893053 | 0.029453 | 0.172191 |
| PLACE dev prediction count | 1 | 0 | 0 |

### SHARED_FIVE_WAY epoch trajectory

| Epoch | ACTOR TP/FP/FN | ACTOR Recall | ACTOR F1 | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/0/15 | 0 | 0 | 0.142671 | 0.931937 | 0.837945 | 0.589961 |
| 2 | 0/0/15 | 0 | 0 | 0.095487 | 0.960784 | 0.854902 | 0.605229 |
| 3 | 0/0/15 | 0 | 0 | 0.134655 | 0.970874 | 0.842857 | 0.604577 |
| 4 | 0/0/15 | 0 | 0 | 0.179202 | 0.975369 | 0.856089 | 0.610486 |
| 5 | 0/0/15 | 0 | 0 | 0.114955 | 0.980198 | 0.846442 | 0.608880 |
| 6 | 0/0/15 | 0 | 0 | 0.084115 | 0.942308 | 0.801527 | 0.581278 |
| 7 | 0/2/15 | 0 | 0 | 0.090517 | 0.956938 | 0.861423 | 0.606120 |
| 8 | 1/4/14 | 0.066667 | 0.100000 | 0.107276 | 0.931373 | 0.854626 | 0.628666 |
| 9 | 0/3/15 | 0 | 0 | 0.131986 | 0.980198 | 0.868085 | 0.616094 |
| 10 | 0/10/15 | 0 | 0 | 0.120113 | 0.975369 | 0.891667 | 0.622345 |
| 11 | 4/13/11 | 0.266667 | 0.250000 | 0.153856 | 0.974874 | 0.848739 | 0.691205 |
| 12 | 0/2/15 | 0 | 0 | 0.146158 | 0.965517 | 0.881633 | 0.615717 |

### TRUE_FOUR_INDEPENDENT epoch trajectory

| Epoch | ACTOR TP/FP/FN | ACTOR Recall | ACTOR F1 | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/0/15 | 0 | 0 | 0.114499 | 0.975369 | 0.828070 | 0.601147 |
| 2 | 0/0/15 | 0 | 0 | 0.089118 | 0.953368 | 0.779817 | 0.577728 |
| 3 | 0/0/15 | 0 | 0 | 0.119951 | 0.980000 | 0.864865 | 0.614955 |
| 4 | 0/0/15 | 0 | 0 | 0.165154 | 0.970297 | 0.865079 | 0.611792 |
| 5 | 0/1/15 | 0 | 0 | 0.106286 | 0.974874 | 0.851711 | 0.608862 |
| 6 | 0/0/15 | 0 | 0 | 0.101145 | 0.892857 | 0.854839 | 0.582565 |
| 7 | 0/0/15 | 0 | 0 | 0.155066 | 0.974874 | 0.850000 | 0.608291 |

### TRUE_FACTORIZED epoch trajectory

| Epoch | ACTOR TP/FP/FN | ACTOR Recall | ACTOR F1 | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/0/15 | 0 | 0 | 0.102437 | 0.469697 | 0.876404 | 0.448700 |
| 2 | 0/0/15 | 0 | 0 | 0.101771 | 0.847458 | 0.792793 | 0.546750 |
| 3 | 0/0/15 | 0 | 0 | 0.100762 | 0.960784 | 0.860465 | 0.607083 |
| 4 | 0/0/15 | 0 | 0 | 0.142762 | 0.979798 | 0.869919 | 0.616572 |
| 5 | 0/0/15 | 0 | 0 | 0.125298 | 0.956098 | 0.845283 | 0.600460 |
| 6 | 0/0/15 | 0 | 0 | 0.115751 | 0.984925 | 0.852590 | 0.612505 |
| 7 | 0/0/15 | 0 | 0 | 0.106009 | 0.961538 | 0.859504 | 0.607014 |
| 8 | 0/4/15 | 0 | 0 | 0.100829 | 0.953846 | 0.858369 | 0.604072 |

### TRUE_FOUR_INDEPENDENT Phase II gradient norms

각 값은 epoch 내 pre-clip norm의 mean이다. 전체 mean/median/p90/max는 history artifact에 보존했다.

| Epoch | DocumentContextEncoder | CandidateSpanEncoder | ACTORPairEncoder | TARGETPairEncoder | PLACEPairEncoder | TIMEPairEncoder | GLOBAL |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.009380 | 0.124615 | 0.015741 | 0.091196 | 0.002058 | 0.104854 | 0.268359 |
| 2 | 0.003491 | 0.073883 | 0.009860 | 0.046556 | 0.000369 | 0.058121 | 0.159053 |
| 3 | 0.002439 | 0.062401 | 0.008324 | 0.023380 | 0.000269 | 0.042407 | 0.118242 |
| 4 | 0.002249 | 0.060575 | 0.007602 | 0.028909 | 0.000254 | 0.032340 | 0.111946 |
| 5 | 0.001979 | 0.059773 | 0.006197 | 0.016370 | 0.000213 | 0.031194 | 0.098108 |
| 6 | 0.001739 | 0.056767 | 0.005668 | 0.009569 | 0.000307 | 0.022582 | 0.081671 |
| 7 | 0.002032 | 0.055742 | 0.005059 | 0.010125 | 0.000281 | 0.025124 | 0.081177 |

### TRUE_FACTORIZED Phase II gradient norms

각 값은 epoch 내 pre-clip norm의 mean이다. 전체 mean/median/p90/max는 history artifact에 보존했다.

| Epoch | DocumentContextEncoder | CandidateSpanEncoder | PARTICIPANTPairEncoder | TEMPORALPairEncoder | PLACEPairEncoder | GLOBAL |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.014291 | 0.190772 | 0.156177 | 0.155617 | 0.004728 | 0.404613 |
| 2 | 0.004807 | 0.119282 | 0.081635 | 0.090410 | 0.000735 | 0.245417 |
| 3 | 0.003420 | 0.098265 | 0.051700 | 0.063362 | 0.000539 | 0.186323 |
| 4 | 0.002907 | 0.089802 | 0.045569 | 0.047308 | 0.000424 | 0.161997 |
| 5 | 0.002417 | 0.087552 | 0.028017 | 0.041318 | 0.000492 | 0.137591 |
| 6 | 0.002222 | 0.079307 | 0.024060 | 0.036620 | 0.000635 | 0.125359 |
| 7 | 0.002651 | 0.081762 | 0.028295 | 0.032290 | 0.000580 | 0.123113 |
| 8 | 0.002827 | 0.074650 | 0.029518 | 0.021972 | 0.000709 | 0.107724 |

## 6. 5-way vs true four-independent vs true factorized

- PHASE_I_ISOLATED: 관측된 evaluable macro F1 기준 최고 branch는 `TRUE_FOUR_INDEPENDENT`이며 selected epoch는 4이다.
- PHASE_II_END_TO_END: 관측된 evaluable macro F1 기준 최고 branch는 `SHARED_FIVE_WAY`이며 selected epoch는 11이다.
- 단, B/C도 A와 동일한 sampled pair population을 각 Head의 학습 데이터로 사용했다. 따라서 위 순위는 해당 실행의 metric 순위일 뿐, Head 분리 architecture 자체의 우열 판정이 아니다.

Conflict는 raw 0.5/argmax output에 대해 계산했으며 후처리하지 않았다.

| Phase/Branch | ACTOR+TARGET | ACTOR+TIME | ACTOR+PLACE | TARGET+TIME | TARGET+PLACE | TIME+PLACE | Any multi-positive |
|---|---:|---:|---:|---:|---:|---:|---:|
| PHASE_I_ISOLATED/TRUE_FOUR_INDEPENDENT | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PHASE_I_ISOLATED/TRUE_FACTORIZED | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PHASE_II_END_TO_END/TRUE_FOUR_INDEPENDENT | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PHASE_II_END_TO_END/TRUE_FACTORIZED | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 7. Shallow factorization vs true-head factorization

직전 shallow artifact는 수정하지 않고 read-only reference로 사용했다. TRUE_5WAY는 이번 Phase II의 수치 비교 기준이다. 그러나 shallow/true 양쪽 모두 Head별 training population 분리를 검증하지 않았으므로, 이 표만으로 `output 분리`와 `PairEncoder 분리`의 효과를 인과적으로 비교하지 않는다.

| Architecture | ACTOR F1 | ACTOR TP | ACTOR PR-AUC | TARGET F1 | TIME F1 | Evaluable Macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| SHALLOW_5WAY | 0.105263 | 1 | 0.088711 | 0.942408 | 0.861925 | 0.636532 |
| SHALLOW_4_INDEPENDENT | 0 | 0 | 0.100335 | 0.964103 | 0.891566 | 0.618556 |
| SHALLOW_FACTORIZED | 0.272727 | 3 | 0.146535 | 0.955665 | 0.869919 | 0.699437 |
| TRUE_5WAY | 0.250000 | 4 | 0.153856 | 0.974874 | 0.848739 | 0.691205 |
| TRUE_4_INDEPENDENT | 0 | 0 | 0.119951 | 0.980000 | 0.864865 | 0.614955 |
| TRUE_FACTORIZED | 0 | 0 | 0.142762 | 0.979798 | 0.869919 | 0.616572 |

True minus shallow delta:

- `FOUR_INDEPENDENT`: `{"EVALUABLE_RELATION_MACRO_F1": -0.003601321432646687, "per_relation/ACTOR/f1": 0.0, "per_relation/ACTOR/pr_auc": 0.019616487090662785, "per_relation/ACTOR/tp": 0.0, "per_relation/TARGET/f1": 0.015897435897435752, "per_relation/TIME/f1": -0.026701400195376035}`
- `FACTORIZED`: `{"EVALUABLE_RELATION_MACRO_F1": -0.08286477251994495, "per_relation/ACTOR/f1": -0.27272727272727276, "per_relation/ACTOR/pr_auc": -0.0037731096580378154, "per_relation/ACTOR/tp": -3.0, "per_relation/TARGET/f1": 0.024132955167437964, "per_relation/TIME/f1": 0.0}`

## 8. ACTOR raw TP/FP/FN analysis

- `PHASE_I_ISOLATED`: SHARED_FIVE_WAY=TP/FP/FN 1/4/14, PR-AUC 0.097341; TRUE_FOUR_INDEPENDENT=TP/FP/FN 1/3/14, PR-AUC 0.101392; TRUE_FACTORIZED=TP/FP/FN 1/3/14, PR-AUC 0.101931
- `PHASE_II_END_TO_END`: SHARED_FIVE_WAY=TP/FP/FN 4/13/11, PR-AUC 0.153856; TRUE_FOUR_INDEPENDENT=TP/FP/FN 0/0/15, PR-AUC 0.119951; TRUE_FACTORIZED=TP/FP/FN 0/0/15, PR-AUC 0.142762

Historical CUDA reference는 TP/FP/FN=2/5/13, recall=0.133333, F1=0.181818, PR-AUC=0.109842이며 공식 same-backend comparator가 아니다.

## 9. TARGET/TIME preservation

- `TRUE_FOUR_INDEPENDENT` vs Phase II 5-way: TARGET F1 delta=0.005126, TIME F1 delta=0.016125.
- `TRUE_FACTORIZED` vs Phase II 5-way: TARGET F1 delta=0.004924, TIME F1 delta=0.021179.

## 10. PLACE diagnostic

모든 real dev branch에서 `PLACE_REAL_DEV_STATUS = UNEVALUABLE`이다. PLACE는 official selection과 architecture verdict에서 제외했다.

- `PHASE_I_ISOLATED/SHARED_FIVE_WAY`: train support=7, loss=N/A (5-way에서 분리 불가), PR-AUC=1, recall=0.714286, prediction count=5; dev FP/pred=0/0.
- `PHASE_I_ISOLATED/TRUE_FOUR_INDEPENDENT`: train support=7, loss=0.000306, PR-AUC=0.944161, recall=0.571429, prediction count=4; dev FP/pred=0/0.
- `PHASE_I_ISOLATED/TRUE_FACTORIZED`: train support=7, loss=0.000152, PR-AUC=0.958759, recall=0.714286, prediction count=5; dev FP/pred=0/0.
- `PHASE_II_END_TO_END/SHARED_FIVE_WAY`: train support=7, loss=N/A (5-way에서 분리 불가), PR-AUC=0.893053, recall=0.857143, prediction count=8; dev FP/pred=1/1.
- `PHASE_II_END_TO_END/TRUE_FOUR_INDEPENDENT`: train support=7, loss=0.002355, PR-AUC=0.029453, recall=0, prediction count=0; dev FP/pred=0/0.
- `PHASE_II_END_TO_END/TRUE_FACTORIZED`: train support=7, loss=0.002244, PR-AUC=0.172191, recall=0, prediction count=0; dev FP/pred=0/0.

## 11. Representation specialization

Selected dev active pair의 relation-specific pair state cosine이다. 낮아질수록 geometry가 달라졌다는 진단 신호지만 adoption metric은 아니다.

| Phase | Branch | Pair | Mean | Median | P10 | P90 | N |
|---|---|---|---:|---:|---:|---:|---:|
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | ACTOR vs TARGET | 0.048746 | 0.050406 | 0.001764 | 0.087096 | 2503 |
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | ACTOR vs PLACE | 0.044086 | 0.035217 | 0.011798 | 0.087670 | 2503 |
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | ACTOR vs TIME | -0.060150 | -0.090442 | -0.145842 | 0.111561 | 2503 |
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | TARGET vs PLACE | 0.084743 | 0.092850 | 0.054379 | 0.115101 | 2503 |
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | TARGET vs TIME | 0.001082 | -0.004443 | -0.027882 | 0.034059 | 2503 |
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | PLACE vs TIME | 0.061273 | 0.069021 | 0.018457 | 0.091171 | 2503 |
| PHASE_I_ISOLATED | TRUE_FACTORIZED | PARTICIPANT vs TEMPORAL | 0.068229 | 0.070662 | 0.012201 | 0.132107 | 2503 |
| PHASE_I_ISOLATED | TRUE_FACTORIZED | PARTICIPANT vs PLACE | 0.027807 | 0.031382 | -0.007808 | 0.057970 | 2503 |
| PHASE_I_ISOLATED | TRUE_FACTORIZED | TEMPORAL vs PLACE | 0.003263 | -0.001957 | -0.028482 | 0.038130 | 2503 |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | ACTOR vs TARGET | 0.105669 | 0.099954 | 0.062238 | 0.150981 | 2503 |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | ACTOR vs PLACE | 0.027280 | 0.024334 | 0.007292 | 0.050802 | 2503 |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | ACTOR vs TIME | 0.026944 | -0.003604 | -0.060631 | 0.201191 | 2503 |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | TARGET vs PLACE | 0.094980 | 0.097819 | 0.066726 | 0.123706 | 2503 |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | TARGET vs TIME | 0.035943 | 0.033593 | -0.046798 | 0.130225 | 2503 |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | PLACE vs TIME | 0.040870 | 0.046459 | -0.005825 | 0.072329 | 2503 |
| PHASE_II_END_TO_END | TRUE_FACTORIZED | PARTICIPANT vs TEMPORAL | 0.159275 | 0.143013 | 0.013782 | 0.335827 | 2503 |
| PHASE_II_END_TO_END | TRUE_FACTORIZED | PARTICIPANT vs PLACE | 0.102273 | 0.097699 | 0.074773 | 0.139928 | 2503 |
| PHASE_II_END_TO_END | TRUE_FACTORIZED | TEMPORAL vs PLACE | 0.068222 | 0.061856 | -0.036128 | 0.173132 | 2503 |

## 12. Parameter-count caveat

B/C는 PairEncoder 복제로 A보다 capacity가 크다. 이번 v1은 parameter-matched wide 5-way control을 실행하지 않았다.

| Phase | Branch | Total trainable | Shared object total | Shared object trainable | Relation-specific | Head breakdown |
|---|---|---:|---:|---:|---:|---|
| PHASE_I_ISOLATED | SHARED_FIVE_WAY | 425693 | 2846920 | 0 | 425693 | `{"SHARED_FIVE_WAY": 425693}` |
| PHASE_I_ISOLATED | TRUE_FOUR_INDEPENDENT | 1698660 | 2846920 | 0 | 1698660 | `{"ACTOR": 424665, "PLACE": 424665, "TARGET": 424665, "TIME": 424665}` |
| PHASE_I_ISOLATED | TRUE_FACTORIZED | 1274509 | 2846920 | 0 | 1274509 | `{"PARTICIPANT": 425179, "PLACE": 424665, "TEMPORAL": 424665}` |
| PHASE_II_END_TO_END | SHARED_FIVE_WAY | 3272613 | 2846920 | 2846920 | 425693 | `{"SHARED_FIVE_WAY": 425693}` |
| PHASE_II_END_TO_END | TRUE_FOUR_INDEPENDENT | 4545580 | 2846920 | 2846920 | 1698660 | `{"ACTOR": 424665, "PLACE": 424665, "TARGET": 424665, "TIME": 424665}` |
| PHASE_II_END_TO_END | TRUE_FACTORIZED | 4121429 | 2846920 | 2846920 | 1274509 | `{"PARTICIPANT": 425179, "PLACE": 424665, "TEMPORAL": 424665}` |

## 13. Final verdict

- `TRUE_HEAD_ISOLATED_SIGNAL = MIXED`
- `TRUE_HEAD_END_TO_END = INCONCLUSIVE`
- `ARGUMENT_RELATION_HEAD_ARCHITECTURE = INCONCLUSIVE`
- `PARAMETER_MATCHED_CAPACITY_CONTROL_RECOMMENDED = false`
- `MULTI_SEED_CONFIRMATION_RECOMMENDED = false`
- `TRAINING_STREAM_FACTORIZATION = NOT_PERFORMED`
- `GOLD_ACTOR_COVERAGE_AUDIT_REQUIRED = true`

### 마지막 질문에 대한 답

이번 실험으로는 shared learned pair representation이 충분한지, relation-specific PairEncoder가 필요한지 판정할 수 없다. PairEncoder parameter와 gradient는 실제로 분리됐지만, relation별 학습 dataset/sampling stream은 분리되지 않았다. 따라서 Phase II에서 TRUE_FACTORIZED의 ACTOR TP가 0이 된 결과는 Head 분리의 실패가 아니라, ACTOR 115개가 대량의 non-ACTOR와 섞인 기존 분포를 각 Head가 그대로 학습한 결과일 수 있다.

또한 ACTOR=115와 TARGET=884의 큰 격차가 실제 Gold 의미 분포인지, annotation policy상 implicit actor 생략인지, raw→processed→tensorized 과정의 누락인지 아직 확인하지 않았다. 먼저 Event별 ACTOR/TARGET coverage와 단계별 보존율을 감사해야 한다. 그 뒤 inference candidate universe는 고정하되 Head별 training population과 negative stream을 의미적으로 분리한 실험을 해야 `TRUE_FOUR_INDEPENDENT`와 `TRUE_FACTORIZED`를 유효하게 비교할 수 있다. 현재 architecture verdict는 `INCONCLUSIVE`이며 production 변경 근거가 아니다.

이 결과로 production Argument Head/config/checkpoint, eligibility, sampler, threshold, Trigger, synthetic data를 변경하지 않았다.
