# V3 Participant Architecture Fair Comparison v2

최종 판정: **BOTH_LEARNABLE_RUNTIME_DECISION_REQUIRED**. 관측 dev macro-F1 선두: B2. Production 채택/다음 실험 자동 실행 없음.

## 1. 실행 범위와 공통 계약

직전 safe-supervision artifact의 READY_FOR_FAIR_AB, 7개 output SHA, source/implementation SHA를 확인하고 시작했다. 기존 pilot_train120 / pilot_dev15, curated RC, 동일 supervision_view를 사용했다. pilot_test는 사용하지 않았다. 원문/curated Gold/guideline/ABOUT/production/기존 5-way Head를 변경하지 않았다.

- Curated Gold SHA: `0e4d1fa7f1dc0969fb8d8208c67cdd07b037f68b7acef71afd3d02af4ea80002`
- Guideline SHA: `a3c3012750b27b0ab3946a0156e43012e1b95204787deb73f50e4fbbab5030a1`
- Supervision view SHA: `31865f61c123bcd939eef7adbfa3ca3dc4a53ba0c74882e566fcb2c94e7bc5ee`
- Shared compiled tensor SHA: `2ac843a6a8660e444ec7210193ed215ead128a8ae35ef73b7b0251a7310758c6`
- Backbone: `kakaobank/kf-deberta-base` revision `363b171d71443b0874b0bf9cea053eb5b1650633` (frozen)
- Common initial tensor SHA: `9bd4b09c5d08bb06a3476e5015f1791cf9319a95586525d59ba4f30bf51d24fc`

학습 candidate/mask는 한 공통 compiler가 생성하고 A2/B2가 같은 compiled_supervision.pt를 읽었다. 두 architecture가 completeness/negative를 따로 재해석하지 않았다. PARTIAL known positive만 active, UNRESOLVED는 이전 view의 보수적 all-mask 정책 그대로다. negative_scope와 Event/alignment 보류도 동일하다. exact-span task의 nonmatch negative는 semantic identity 부정과 다르다.

Width=49: train 활성 local positive 전체의 최대 token width로 사전에 고정했다. dev에서 변경하지 않았으며 train/dev active positive width loss=0. Event 정렬 실패는 원 view에 남고 입력 Event 목록에서 제외된다. role/context/provenance를 input feature로 쓰지 않고, Gold Event boundary만 공통 조건이다.

| Split | Aligned Events | A Event×candidate | A positive cells | A safe negative cells | B positive endpoints | B safe negative endpoints | Active Event-role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | 1846 | 1356782 | 2989 | 3678352 | 5977 | 347671 | 5031 |
| dev | 272 | 185463 | 478 | 473235 | 956 | 47978 | 747 |

A Event×candidate는 전체 열거된 inference universe다. 학습에서는 두 방식 모두 all-UNKNOWN 기사2개를 동일하게 skip했으며, 그 중1개에 후보2,495개가 있다. 따라서 A2의 실제 training forward는 epoch당 1,354,287개이고 나머지 active 기사에서는 후보를 하나도 sampling/pruning하지 않았다. dev 평가에서는 전체 열거 후보를 실제 forward했다.

## 2. 구조·loss·gradient fairness

A2는 기존 CandidateSpanEncoder/DirectedPairEncoder와 실험용 Linear(H,3) independent binary logits다. 5-way softmax는 없다. B2는 v1의 token+Event+position 단일 additive fusion와 독립 3×start/end branch를 재사용했다. Trigger conditioning, verifier, cross-attention, 새 backbone은 없다.

양쪽 모두 plain BCEWithLogitsLoss, pos_weight/focal/negative subsampling 없음. active unit mean → role mean → Event mean → article mean이며, masked-only role/Event/article는 reduction에서 제외한다. A unit은 candidate span, B unit은 start/end cell이다. BCE를 같게 해도 positive prevalence, factorized pairing 정보와 총 계산량까지 같아지지는 않는다.

A2 전체 후보 forward는 256 pair chunk를 사용한다. 공통 graph 출력을 leaf로 받아 chunk gradient를 축적한 뒤 공통 graph를 한 번 역전파한다. step 사이 trainable feature cache가 아니며 full-graph gradient parity를 검사했다. B2는 reinjected token path도 사용하지만 A2의 기존 span encoder는 sentence context를 사용한다. 공통 모듈의 requires_grad와 초기 tensor는 같고 실제 gradient path 차이는 contract JSON에 기록했다. Dropout RNG 소비 횟수는 topology별로 달라 같다고 주장하지 않는다.

A2 factored span output 최대 오차=0.0, shared gradient parity 최대 오차=7.152557373046875e-07. 양쪽 real optimizer step·finite gradient·parameter update·save/reload·role-field 제거 runtime parity가 PASS다.

## 3. Tiny 6기사 learnability

동일 v1 train6을 재사용했다. seed1008, 각120 optimizer steps로 bounded diagnostic을 수행하고 main은 동일 저장 초기 tensor로 복원한 후 새 optimizer/RNG로 시작했다. tiny checkpoint warm start 없음.

| Variant | Step | Role | Support | TP | Safe FP | FN | P | R | F1 | Positive output | UNKNOWN output |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A2 | 0 | ACTOR | 102 | 87 | 99425 | 15 | 0.00087 | 0.85294 | 0.00175 | 124793 | 25281 |
| A2 | 0 | TARGET | 193 | 27 | 22405 | 166 | 0.0012 | 0.1399 | 0.00239 | 24038 | 1606 |
| A2 | 0 | PLACE | 66 | 37 | 93298 | 29 | 0.0004 | 0.56061 | 0.00079 | 97798 | 4463 |
| A2 | 40 | ACTOR | 102 | 0 | 0 | 102 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| A2 | 40 | TARGET | 193 | 6 | 7 | 187 | 0.46154 | 0.03109 | 0.05825 | 66 | 53 |
| A2 | 40 | PLACE | 66 | 0 | 0 | 66 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| A2 | 80 | ACTOR | 102 | 27 | 6 | 75 | 0.81818 | 0.26471 | 0.4 | 40 | 7 |
| A2 | 80 | TARGET | 193 | 60 | 18 | 133 | 0.76923 | 0.31088 | 0.4428 | 103 | 25 |
| A2 | 80 | PLACE | 66 | 0 | 0 | 66 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| A2 | 120 | ACTOR | 102 | 84 | 21 | 18 | 0.8 | 0.82353 | 0.81159 | 121 | 16 |
| A2 | 120 | TARGET | 193 | 108 | 35 | 85 | 0.75524 | 0.55959 | 0.64286 | 160 | 17 |
| A2 | 120 | PLACE | 66 | 35 | 23 | 31 | 0.60345 | 0.5303 | 0.56452 | 62 | 4 |
| B2 | 0 | ACTOR | 102 | 34 | 21366 | 68 | 0.00159 | 0.33333 | 0.00316 | 28763 | 7363 |
| B2 | 0 | TARGET | 193 | 29 | 39633 | 164 | 0.00073 | 0.15026 | 0.00146 | 41248 | 1586 |
| B2 | 0 | PLACE | 66 | 3 | 14876 | 63 | 0.0002 | 0.04545 | 0.0004 | 15007 | 128 |
| B2 | 40 | ACTOR | 102 | 0 | 0 | 102 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| B2 | 40 | TARGET | 193 | 0 | 0 | 193 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| B2 | 40 | PLACE | 66 | 0 | 0 | 66 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| B2 | 80 | ACTOR | 102 | 4 | 0 | 98 | 1.0 | 0.03922 | 0.07547 | 8 | 4 |
| B2 | 80 | TARGET | 193 | 4 | 2 | 189 | 0.66667 | 0.02073 | 0.0402 | 28 | 22 |
| B2 | 80 | PLACE | 66 | 0 | 0 | 66 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| B2 | 120 | ACTOR | 102 | 55 | 11 | 47 | 0.83333 | 0.53922 | 0.65476 | 75 | 9 |
| B2 | 120 | TARGET | 193 | 23 | 5 | 170 | 0.82143 | 0.11917 | 0.20814 | 48 | 20 |
| B2 | 120 | PLACE | 66 | 9 | 0 | 57 | 1.0 | 0.13636 | 0.24 | 9 | 0 |

초기/중간/최종 loss와 각 optimizer step의 clipping 전 gradient norm은 tiny_a2.json/tiny_b2.json에 있다. 학습 loss 감소와 positive recall/precision의 동반 개선을 구분한다. 실패 시 예산을 늘리거나 threshold를 바꾸지 않았다.

### 같은6기사 v1 historical tiny 비교

v1은 parent listed-Gold precision이고 v2는 curated safe-negative precision이므로 동일 분모의 인과 비교가 아니다. 동일6기사/120 step의 출력 과다·학습 신호를 확인하는 참고치다.

| Transition | Role | V1 listed P | V2 safe P | V1 listed R | V2 safe R | V1 positive output | V2 positive output |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1→A2 | ACTOR | 0.00599 | 0.8 | 0.9375 | 0.82353 | 17537 | 121 |
| A1→A2 | TARGET | 0.00233 | 0.75524 | 0.96023 | 0.55959 | 72574 | 160 |
| A1→A2 | PLACE | 0.00613 | 0.60345 | 0.95455 | 0.5303 | 10276 | 62 |
| B1→B2 | ACTOR | 0.00385 | 0.83333 | 0.9375 | 0.53922 | 27281 | 75 |
| B1→B2 | TARGET | 0.0046 | 0.82143 | 0.96023 | 0.11917 | 36773 | 48 |
| B1→B2 | PLACE | 0.00806 | 1.0 | 0.74242 | 0.13636 | 6082 | 9 |

| Variant | Role | Initial role loss | Final role loss | Global gradient mean | Global gradient max | Status |
| --- | --- | --- | --- | --- | --- | --- |
| A2 | ACTOR | 0.9072390921260628 | 0.002090675598258172 | 0.14869787821856637 | 11.124926567077637 | TRAIN_LEARNABILITY_SIGNAL_OBSERVED |
| A2 | TARGET | 0.5168922023996433 | 0.0037155454795123957 | 0.14869787821856637 | 11.124926567077637 | TRAIN_LEARNABILITY_SIGNAL_OBSERVED |
| A2 | PLACE | 0.7909883370180366 | 0.0026178748693815672 | 0.14869787821856637 | 11.124926567077637 | TRAIN_LEARNABILITY_SIGNAL_OBSERVED |
| B2 | ACTOR | 0.6917966299338881 | 0.03773328639616849 | 0.2034441249445081 | 3.1979761123657227 | TRAIN_LEARNABILITY_SIGNAL_OBSERVED |
| B2 | TARGET | 0.78919289844452 | 0.07077675603530847 | 0.2034441249445081 | 3.1979761123657227 | TRAIN_LEARNABILITY_SIGNAL_OBSERVED |
| B2 | PLACE | 0.682159569209019 | 0.0361578710654891 | 0.2034441249445081 | 3.1979761123657227 | TRAIN_LEARNABILITY_SIGNAL_OBSERVED |

## 4. Main train/dev

AdamW lr3e-4, weight decay0.01, clip1.0, seed1008, 최대8 epoch, patience2. train 기사 순서는 seed+epoch로 동일하게 고정했다. dev의 세 role primary exact F1 평균으로 단일 checkpoint를 선택했다. support0는 평균에서 제외하며 이번 지원 role 목록은 저장 metric에 있다. threshold0.5 고정, 탐색 없음.

| Variant | Epochs | Selected epoch | Dev macro F1 | Optimizer steps | Train seconds | Dev seconds |
| --- | --- | --- | --- | --- | --- | --- |
| A2 | 4 | 2 | 0.185096 | 472 | 244.9 | 19.29 |
| B2 | 8 | 7 | 0.410021 | 944 | 32.84 | 2.08 |

| Variant | Role | Raw local known Gold | Common representable | TP | Confirmed-negative FP | FN | P | R | F1 | UNKNOWN | All positive output |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A2 | ACTOR | 143 | 133 | 41 | 49 | 92 | 0.45556 | 0.30827 | 0.36771 | 25 | 115 |
| A2 | TARGET | 323 | 296 | 77 | 448 | 219 | 0.14667 | 0.26014 | 0.18758 | 85 | 610 |
| A2 | PLACE | 50 | 49 | 0 | 0 | 49 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| B2 | ACTOR | 143 | 133 | 70 | 23 | 63 | 0.75269 | 0.52632 | 0.61947 | 12 | 105 |
| B2 | TARGET | 323 | 296 | 50 | 76 | 246 | 0.39683 | 0.16892 | 0.23697 | 9 | 135 |
| B2 | PLACE | 50 | 49 | 17 | 25 | 32 | 0.40476 | 0.34694 | 0.37363 | 0 | 42 |

primary denominator는 공통 view가 active로 승인한 positive다. raw local known Gold 중 unaligned/HRR/UNRESOLVED 등은 별도 loss count로 남는다. UNKNOWN prediction은 FP에 넣지 않는다. raw_local_exact_hits_diagnostic는 raw listed evidence의 문자열 일치일 뿐 masked annotation을 확정 label로 승인하지 않는다. 전체 raw Gold F1 또는 predicted-Event runtime F1이라고 부르지 않는다.

## 5. V1 대비 precision explosion

아래는 **v1 saved dev predictions를 현재 curated confirmed/negative/unknown scope에서 재집계**한 비교다. 모델 재실행은 없고 test는 읽지 않았다. parent→RC label 및 Event/cap 차이가 있어 개선을 오직 BCE/contract의 인과 효과라고 할 수는 없다.

| Transition | Role | Old positive output | New positive output | Old re-accounted safe FP | New safe FP | Old UNKNOWN/missing Event | New UNKNOWN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1→A2 | ACTOR | 8320 | 115 | 7544 | 49 | 673 | 25 |
| A1→A2 | TARGET | 117240 | 610 | 110229 | 448 | 6743 | 85 |
| A1→A2 | PLACE | 1922 | 0 | 1899 | 0 | 2 | 0 |
| B1→B2 | ACTOR | 3466 | 105 | 3104 | 23 | 241 | 12 |
| B1→B2 | TARGET | 53719 | 135 | 50883 | 76 | 2544 | 9 |
| B1→B2 | PLACE | 22 | 42 | 15 | 25 | 0 | 0 |

## 6. Topology-specific 및 subset 진단

A2 candidate_diagnostic_a2.json은 raw local support/view-active coverage/폭 loss/후보 수/Event/conditional classifier와 negative rejection을 분리한다. B2 boundary_diagnostic_b2.json은 start/end recall, Cartesian pair recall, wrong endpoints, 정답 endpoint 사이 false pair, width/cap/conflict loss를 분리한다. output cap과 endpoint-conflict 제거는 사용하지 않아 해당 cap/conflict loss는0이다.

| Role | B start recall | B end recall | B paired exact recall | Wrong starts | Wrong ends | Cartesian safe FP | Both endpoints Gold but wrong pair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACTOR | 0.6691729323308271 | 0.631578947368421 | 0.5263157894736842 | 24 | 17 | 23 | 1 |
| TARGET | 0.28040540540540543 | 0.40540540540540543 | 0.16891891891891891 | 54 | 79 | 76 | 5 |
| PLACE | 0.42857142857142855 | 0.5306122448979592 | 0.3469387755102041 | 10 | 21 | 25 | 2 |

| Subset (common active positives) | Role | Support | A2 recall | B2 recall |
| --- | --- | --- | --- | --- |
| ENTITY_RESOLVED | ACTOR | 111 | 0.3333333333333333 | 0.5405405405405406 |
| ENTITY_RESOLVED | TARGET | 76 | 0.5394736842105263 | 0.11842105263157894 |
| ENTITY_RESOLVED | PLACE | 17 | 0.0 | 0.5294117647058824 |
| SPAN_ONLY | ACTOR | 9 | 0.0 | 0.2222222222222222 |
| SPAN_ONLY | TARGET | 210 | 0.1619047619047619 | 0.19523809523809524 |
| SPAN_ONLY | PLACE | 31 | 0.0 | 0.25806451612903225 |
| EVENT_INTERNAL | ACTOR | 107 | 0.29906542056074764 | 0.5420560747663551 |
| EVENT_INTERNAL | TARGET | 272 | 0.25 | 0.1801470588235294 |
| EVENT_INTERNAL | PLACE | 40 | 0.0 | 0.375 |
| SAME_SENTENCE_EVENT_OUTSIDE | ACTOR | 26 | 0.34615384615384615 | 0.46153846153846156 |
| SAME_SENTENCE_EVENT_OUTSIDE | TARGET | 24 | 0.375 | 0.041666666666666664 |
| SAME_SENTENCE_EVENT_OUTSIDE | PLACE | 9 | 0.0 | 0.2222222222222222 |
| MULTIPLE_FILLERS_SAME_ROLE | ACTOR | 7 | 0.42857142857142855 | 0.2857142857142857 |
| MULTIPLE_FILLERS_SAME_ROLE | TARGET | 110 | 0.32727272727272727 | 0.13636363636363635 |
| MULTIPLE_FILLERS_SAME_ROLE | PLACE | 14 | 0.0 | 0.5 |
| SAME_SPAN_MULTI_ROLE | ACTOR | 0 | None | None |
| SAME_SPAN_MULTI_ROLE | TARGET | 4 | 0.25 | 0.0 |
| SAME_SPAN_MULTI_ROLE | PLACE | 4 | 0.0 | 0.0 |

Context-only semantic roles는 local positive가 없어 span recall을 정의하지 않는다. subset_metrics.json에 unsupported contextual filler support, local prediction 수를 따로 기록했다. 같은 문장의 Event 밖 positive는 보존했고 Entity resolution 성공 여부를 정답 판정에 요구하지 않았다. subtype별 unmatched prediction의 속성을 Gold에서 추정하지 않아 subset precision을 만들지 않았다.

## 7. 계산량

동일4-thread CPU, 각각 새 프로세스, 고정 dev 첫 기사 warm-up 후 같은15기사 forward/decode를 측정했다. RSS는 feature cache·dataset·model을 포함하는 process high-water mark다. 학습 프로세스 peak는 참고치로 별도 남겼다.

| Variant | Trainable params | Dev binary decisions | Forward seconds | Decode seconds | Peak RSS MiB |
| --- | --- | --- | --- | --- | --- |
| A2 | 3272035 | 556389 | 4.873 | 0.009 | 1441.4 |
| B2 | 2981326 | 55440 | 0.121 | 0.077 | 1355.3 |

위 binary decisions는 valid source 범위의 결정 수다. B2가 실제 생성한 padded logits는 208,896개이며 그 중 valid endpoint는 55,440개다. padding/특수 token은 supervision과 decode에서 제외했다. Event별 후보/decision의 min·median·p95·max와 실제 training forward 누계는 complexity.json에 있다.

A2의 후보는 최대 N(N+1)/2, width 제한이면 O(NW)이며 Event마다 독립 role3개를 평가한다. B2 logits는 O(6N)이지만 positive endpoint가 폭증하면 Cartesian decoding은 O(N²)이다. 이번 시간은 frozen backbone 온라인 forward를 제외한 cache 이후 표현/Head/decode이며, full runtime latency가 아니다.

## 8. Historical A0

production 5-way oracle은 다른 Gold/candidate/negative/unit의 조건부 historical reference이며 승패 평균에서 제외했다.

| Metric | Value |
| --- | --- |
| metric/argument/per_class/NONE/precision | 0.9785670545009185 |
| metric/argument/per_class/NONE/recall | 0.9791666666666666 |
| metric/argument/per_class/NONE/f1 | 0.9788667687595712 |
| metric/argument/per_class/NONE/support | 1632.0 |
| metric/argument/per_class/ACTOR/precision | 0.8354430379746836 |
| metric/argument/per_class/ACTOR/recall | 0.9041095890410958 |
| metric/argument/per_class/ACTOR/f1 | 0.8684210526315789 |
| metric/argument/per_class/ACTOR/support | 146.0 |
| metric/argument/per_class/TARGET/precision | 0.917910447761194 |
| metric/argument/per_class/TARGET/recall | 0.8880866425992779 |
| metric/argument/per_class/TARGET/f1 | 0.9027522935779815 |
| metric/argument/per_class/TARGET/support | 277.0 |
| metric/argument/per_class/PLACE/precision | 0.5925925925925926 |
| metric/argument/per_class/PLACE/recall | 1.0 |
| metric/argument/per_class/PLACE/f1 | 0.7441860465116279 |
| metric/argument/per_class/PLACE/support | 16.0 |

## 9. 요청한 결정 질문에 대한 실측 기반 답

1. **EXHAUSTIVE negative를 넣으니 precision explosion이 얼마나 줄었는가?** A1→A2: 현재 curated scope로 재집계한 safe FP 119,672→497 (99.58% 감소); B1→B2: 현재 curated scope로 재집계한 safe FP 54,002→124 (99.77% 감소). 양쪽 tiny에서 세 role 모두 TP와 precision을 확보해 전부 all-negative로 끝난 것은 아니다. 그러나 A2 main PLACE는 train/dev 모두 TP0·출력0으로 collapse했고, B2도 TARGET recall을 크게 잃었다. Negative 학습 신호는 확인되지만 감소 전체를 계약 하나의 인과 효과로 분리할 수는 없다.

2. **A2 병목은 후보 폭증인가 classification인가?** 공통 활성 train/dev positive의 candidate coverage는100%, width loss0이다. 정답 누락의 첫 손실은 classifier/고정 설정 optimization 단계이며 dev recall은 ACTOR 0.308, TARGET 0.260, PLACE 0.000이다. 계산량 병목은 별개로 train 1,356,782 / dev 185,463 Event×candidate enumeration이다. 높은 negative rejection만으로 성공이라고 평가하지 않는다.

3. **B2 병목은 boundary ranking/pairing인가 role discrimination인가?** TARGET start/end recall이 0.280/0.405, exact pair recall 0.169여서 현재 threshold에서 endpoint 제안 단계가 가장 큰 손실이다. TARGET safe false spans 76개 중 두 endpoint가 각각 Gold인 잘못된 조합은 5개다. Pairing도 문제지만 주원인만으로 설명되지 않는다. 별도 ranking/threshold sweep을 하지 않아 ranking 품질과 calibration을 인과적으로 분리하지 않는다. Role별 discrimination 차이는 ACTOR와 TARGET recall 차이에서 관측된다.

4. **TARGET의 near-complete boundary recall이 precision으로 이어졌는가?** 그대로 이어진 것이 아니다. B2 TARGET precision은 0.397로 개선됐지만 recall은 0.169이며 v1의 높은 boundary recall을 유지하지 못했다. A2 TARGET precision/recall은 0.147/0.260로 recall은 A2가 높다. B2의 더 높은 TARGET F1을 near-complete extraction으로 표현할 수 없다.

5. **PLACE의 낮은 support에도 방향성 신호가 있는가?** active dev support 49에서 B2 TP/FP/FN=17/25/32, F1=0.374으로 신호가 있다. A2는 tiny PLACE F1=0.565까지 배웠지만 main dev는 출력0이다. 따라서 Head의 물리적 불가능보다 이 제한된 main 설정의 최적화/분포 문제가 남는다. 15기사로 일반화 인증은 할 수 없다.

6. **Same-span multi-role 표현력 차이가 성능에 영향을 주었는가?** 표현력 차이는 제거됐다. 두 구조 모두 같은 span의 여러 role을 독립 positive로 보존했다. dev4개 pair의 TARGET recall은 A2 0.25/B2 0.00, PLACE는 양쪽0이다. 완전한 multi-role 성공을 보여주지는 못했고, 작은 support로 우열을 주장하지 않는다.

7. **어느 구조가 semantic truth를 더 직접적으로 보존하는가?** 감독 표현은 둘 다 보존한다. B2는 raw boundary를 직접 내지만 pairing은 factorized, A2는 joint span identity를 직접 분류한다. B2는 SPAN_ONLY recall과 전체 macro-F1에서 유리하지만 Entity-resolved TARGET recall 0.118 vs A2 0.539, same-sentence Event-outside TARGET 0.042 vs 0.375로 중요한 약점이 있다. 따라서 B2 하나가 모든 semantic family를 더 충실히 보존한다고 결론내리지 않는다. context-only extraction은 둘 다 unsupported다.

8. **계산량까지 보면 Event-conditioned 구조를 기본 architecture 후보로 올릴 근거가 생겼는가?** 추가 검토 후보로 우선순위를 높일 근거는 생겼다. B2 dev macro-F1 0.410 vs A2 0.185, cache 이후 dev forward+decode는 0.198s vs 4.882s로 B2가 약 24.7배 빠르다. 그러나 TARGET 경계/문장 밖 filler 약점, sparse support, 서로 다른 active gradient path와 실제 early-stop epoch 수 때문에 기본 production 구조 승격을 승인하지 않는다. 최종 판정은 BOTH_LEARNABLE_RUNTIME_DECISION_REQUIRED이다.

9. **Predicted Event runtime 실험으로 넘어갈 가치가 있는가?** 추가 진단으로는 있다. Gold-Event 조건에서 실제 TP가 있는 ACTOR/PLACE와 계산량 측면에서 B2를 우선 검토할 근거가 있으며 A2는 TARGET recall 비교 기준으로 유지할 가치가 있다. 다만 TARGET miss가 많은 상태에서 runtime을 완성도 검증으로 포장하지 말고, Event boundary 오류가 이미 관측된 role 손실에 얼마나 더해지는지 별도로 측정해야 한다. 실행 승인/범위 결정은 사용자에게 남기며 여기서 자동으로 시작하지 않는다.

## 10. 보호·검증·재현

새 코드 namespace는 training/experiments/v3_participant_fair_v2, 결과는 이번 전용 디렉터리다. 기존 untracked v1 실험/RC, production 모델/Head/설정/checkpoint를 보존했다. 계약 테스트8개와 실제 gradient/update/serialization/runtime-input 검사를 통과했다. 공유 초기 SHA·공통 mask·epoch 기사 순서를 확인했다. 테스트 fixture는 메모리 전용이며 synthetic training data는0이다.

```sh
cd /Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa
conda run -n model-test-py312 python -m unittest training.experiments.v3_participant_fair_v2.test_contracts -v
# 최초 준비 전용: 기존 frozen output 존재 시 거부
conda run --no-capture-output -n model-test-py312 python -m training.experiments.v3_participant_fair_v2.data
# 각 variant는 기존 train artifact가 있으면 재학습을 거부
conda run --no-capture-output -n model-test-py312 python -m training.experiments.v3_participant_fair_v2.run run --variant A2
conda run --no-capture-output -n model-test-py312 python -m training.experiments.v3_participant_fair_v2.run run --variant B2
conda run --no-capture-output -n model-test-py312 python -m training.experiments.v3_participant_fair_v2.run benchmark --variant A2
conda run --no-capture-output -n model-test-py312 python -m training.experiments.v3_participant_fair_v2.run benchmark --variant B2
conda run -n model-test-py312 python -m training.experiments.v3_participant_fair_v2.report
```

```text
GOLD_MODIFIED=false
GUIDELINE_MODIFIED=false
ABOUT_MODIFIED=false
PRODUCTION_MODIFIED=false
ROUND04_RESUMED=false
PILOT_TEST_USED=false
COMMIT_PUSH=false
TRAINING_EXECUTED=true
PRODUCTION_ADOPTED=false
```

Notion/Gold/production 또는 다음 실험으로 자동 진행하지 않고 종료한다.
