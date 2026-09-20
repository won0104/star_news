# Full Multitask Baseline v1

실행일은 2026-09-03이다. 이 문서는 Baseline Architecture v1과 Baseline Unblock v1을
변경하지 않고, Construction Gold v2.2 전체 1,000 article로 처음 수행한 frozen-backbone
multitask 학습 결과다. 새로운 Head, loss, threshold calibration, architecture 변경은 하지
않았다.

> Historical baseline: 이 run의 Trigger는 당시의 unweighted BCE와 Cartesian decoder를
> 사용했다. 이후 `Trigger Learning Contract Ablation v1`에서 `pos_weight=4`와 greedy
> one-to-one decoder가 `PRODUCTION_CONTRACT_ADOPTED` 상태로 승격됐다. 이 문서의 multitask
> 수치는 재작성하지 않으며, 새 Trigger contract의 full multitask retraining은 pending이다.

## 1. 전체 판정

**PASS_WITH_WARNINGS**

전체 3 epoch 학습, dev-only checkpoint 선택, checkpoint reload, oracle test,
predicted-cascaded test가 Mac MPS에서 완주했다. 11개 task의 epoch별 loss/primary metric,
class-aware metric, Semantic 3단계 diagnostic, candidate audit, task별 optimum, 5개 decoded
sample이 artifact에 기록됐다. NaN/Inf는 없었고 test는 checkpoint 선택에 사용하지 않았다.

주요 warning은 다음과 같다.

- Relation은 test에서 positive prediction이 하나도 없고, EventCoreference도 MERGE가 0이다.
- Argument는 oracle에서도 ACTOR/PLACE F1이 0이고, cascaded Event feature에는 TIME만 남았다.
- Sentence Presence의 MIX F1은 0이다.
- Semantic boundary proposal recall이 약 49%라 verifier 이전에 recall 상한이 형성된다.
- 기존 128-token alignment에서 Argument Gold link 2,263개 중 16개가 target span 정렬에
  실패했다. 네 target kind 자체는 모두 supervision에 포함됐고 hard eligibility recall은
  모든 task에서 1.0이다.
- P1인 cluster-level graph Gold metric이 없으므로 cascaded graph node/edge 수를 성능 F1로
  표현하지 않는다.

## 2. 실험 계약과 config

| 항목 | 값 |
|---|---|
| Gold | `gnews-1k-construction-gold-v2.2` |
| Gold version | `articlelocal-kg-construction-gold-v2.2` |
| Gold SHA-256 | `428cec4ce1b92ca310a802882f50d1fc9687bd2bccfddfeb22944b136e0a086d` |
| Articles | 1,000 |
| Split | 800 / 100 / 100, article-level |
| Split seed | 41 |
| Training seed | 1008 |
| Sampling seed | 1008 |
| Backbone | `kakaobank/kf-deberta-base` |
| Revision | `363b171d71443b0874b0bf9cea053eb5b1650633` |
| Weight SHA-256 | `3cd6cd7811b3c9190e97cae7eb41571c2bc0076431baae7d41d449a8c1c18c6c` |
| Backbone | frozen |
| Device | Mac MPS |
| Batch | 1 article |
| Tokenization | 전체 문장, 문장당 최대 128 token |
| Epoch | baseline 기본값 3 |
| Optimizer | AdamW, LR `3e-4`, weight decay `0.01`, clip norm `1.0` |
| Presence auxiliary λ | `0.25` |
| Thresholds | Presence/span/verifier/pair 모두 기존 provisional `0.5` |
| Global selection | dev total multitask loss 최소 |
| Test use | dev-selected checkpoint reload 후 oracle/cascaded 각 1회 |

명시된 baseline 기본값이 3 epoch였으므로 20 epoch/early stopping fallback은 사용하지 않았다.
성공한 최종 run 전에 출력 캡처 방식을 확인하려고 첫 launch를 checkpoint 생성 전에 중단했고,
동일 config와 seed로 fresh process/model/optimizer를 다시 시작했다. 최종 artifact에는 재시작한
완결 run만 기록돼 있다.

Artifacts:

- `training/configs/full-baseline-v1-seed1008.json`
- `training/results/full-baseline-v1-seed1008/preflight.json`
- `training/results/full-baseline-v1-seed1008/run.json`
- `training/results/full-baseline-v1-seed1008/checkpoints/dev-selected.pt`
- `training/results/full-baseline-v1-seed1008/decoded-samples.json`

## 3. Trainable parameter

| Module | Total | Trainable |
|---|---:|---:|
| KF backbone | 185,290,752 | 0 |
| Document context | 2,008,832 | 2,008,832 |
| Candidate span encoder | 838,088 | 838,088 |
| Directed pair encoder | 424,408 | 424,408 |
| Event feature encoder | 591,872 | 591,872 |
| Sentence Presence | 67,846 | 67,846 |
| Entity BIO | 200,713 | 200,713 |
| Time BIO | 200,713 | 200,713 |
| Trigger boundary | 198,914 | 198,914 |
| Semantic boundary + verifier | 505,893 | 505,893 |
| Statement Type | 67,075 | 67,075 |
| Assertor branch | 514 | 514 |
| Argument branch | 1,285 | 1,285 |
| Relation branch | 1,028 | 1,028 |
| Entity Coreference | 339,490 | 339,490 |
| Event Coreference | 339,490 | 339,490 |
| **전체** | **191,076,913** | **5,786,161** |

Checkpoint는 trainable tensor 145개만 저장하며 backbone key는 0개다. Checkpoint SHA-256은
`ec82ab9dd208a1de7db968bf7aefc6b6aa15d3bd9c1b6943c9ca03864063c2b9`다.

## 4. Epoch별 total loss

| Epoch | Train total loss | Dev total loss | Global checkpoint 갱신 |
|---:|---:|---:|---|
| 1 | 2.5813 | 1.9491 | yes |
| 2 | 1.8001 | 1.8284 | yes |
| 3 | 1.5483 | **1.8043** | yes, final |

## 5. Task별 train/dev curve

각 cell은 epoch 1/2/3 순서다. Semantic loss는 boundary와 verification loss의 합이다.

| Task | Train loss E1/E2/E3 | Dev loss E1/E2/E3 | Train primary E1/E2/E3 | Dev primary E1/E2/E3 |
|---|---:|---:|---:|---:|
| sentence_presence | 1.1483/0.9395/0.8590 | 0.9874/0.9496/0.9459 | 0.4604/0.5401/0.5557 | 0.5082/0.5162/0.5267 |
| entity | 0.0928/0.0436/0.0359 | 0.0448/0.0369/0.0365 | 0.4311/0.6113/0.6685 | 0.5743/0.6654/0.6701 |
| time | 0.0495/0.0067/0.0050 | 0.0207/0.0193/0.0188 | 0.4272/0.6776/0.7633 | 0.5888/0.7662/0.7928 |
| semantic | 0.5235/0.3805/0.3211 | 0.4188/0.4005/0.4173 | 0.2155/0.4793/0.5401 | 0.3882/0.4748/0.5535 |
| trigger | 0.0703/0.0414/0.0371 | 0.0431/0.0394/0.0387 | 0.2595/0.4466/0.4941 | 0.3526/0.4864/0.4790 |
| statement_type | 0.3099/0.1624/0.1033 | 0.1833/0.1500/0.1623 | 0.8071/0.9137/0.9390 | 0.8857/0.9198/0.9264 |
| assertor | 0.0454/0.0325/0.0249 | 0.0379/0.0375/0.0275 | 0.2177/0.4832/0.6229 | 0.6667/0.6102/0.7308 |
| argument | 0.1131/0.0700/0.0597 | 0.1019/0.0685/0.0570 | 0.3698/0.4285/0.4458 | 0.2707/0.4319/0.4447 |
| relation | 0.0865/0.0681/0.0633 | 0.0588/0.0535/0.0452 | 0.0067/0.0521/0.0474 | 0.0000/0.0000/0.0048 |
| entity_coreference | 0.1182/0.0355/0.0194 | 0.0261/0.0484/0.0310 | 0.8957/0.9768/0.9877 | 0.9925/0.9752/0.9905 |
| event_coreference | 0.0239/0.0201/0.0197 | 0.0262/0.0248/0.0241 | 0.0000/0.0000/0.0000 | 0.0000/0.0000/0.0000 |

Primary metric은 Presence 4-state macro-F1, span exact character+type F1, Statement Type
macro-F1, directed pair positive macro-F1, Coreference MERGE F1이다. 전체 class-aware metric과
confusion matrix는 각 epoch의 run JSON에 보존돼 있다.

## 6. Dev-selected checkpoint와 task optimum

Global checkpoint는 epoch 3, dev total loss `1.8042904347`이다.

| Task | Best epoch | Best dev metric | Global E3 metric | E3 - best |
|---|---:|---:|---:|---:|
| Sentence Presence | 3 | 0.5267 | 0.5267 | +0.0000 |
| Entity | 3 | 0.6701 | 0.6701 | +0.0000 |
| Time | 3 | 0.7928 | 0.7928 | +0.0000 |
| Semantic | 3 | 0.5535 | 0.5535 | +0.0000 |
| Trigger | 2 | 0.4864 | 0.4790 | -0.0074 |
| Statement Type | 3 | 0.9264 | 0.9264 | +0.0000 |
| Assertor | 3 | 0.7308 | 0.7308 | +0.0000 |
| Argument | 3 | 0.4447 | 0.4447 | +0.0000 |
| Relation | 3 | 0.0048 | 0.0048 | +0.0000 |
| Entity Coreference | 1 | 0.9925 | 0.9905 | -0.0020 |
| Event Coreference | 1/2/3 tie | 0.0000 | 0.0000 | +0.0000 |

Trigger와 EntityCoreference만 global epoch와 개별 optimum이 달랐다. 차이는 각각 F1
`0.0074`, `0.0020`으로 현재 3-epoch 범위에서는 큰 multitask interference 신호는 아니다.
EventCoreference의 0 tie는 optimum이 아니라 collapse다.

## 7. Oracle / teacher-forced test

### Sentence와 span

| Task | Precision | Recall | F1 | 비고 |
|---|---:|---:|---:|---|
| Presence EVENT bit | 0.7535 | 0.6537 | 0.7001 | PR-AUC 0.8056 |
| Presence STATEMENT bit | 0.7302 | 0.8057 | 0.7661 | PR-AUC 0.8487 |
| Presence 4-state | - | - | 0.5278 | macro-F1 |
| Presence MIX | 0.0000 | 0.0000 | 0.0000 | support 11 |
| Entity exact char+type | 0.6254 | 0.7359 | 0.6762 | 758 / 1,030 exact TP |
| Time exact char+type | 0.7199 | 0.8458 | 0.7778 | 203 / 240 exact TP |
| Semantic final exact char+type | 0.6772 | 0.4768 | 0.5596 | 925 / 1,940 exact TP |
| Trigger exact char+type | 0.7750 | 0.3771 | 0.5074 | 310 / 822 exact TP |

### Statement, directed pair, coreference

| Task | Primary metric | 세부 결과 |
|---|---:|---|
| Statement Type | macro-F1 0.9324 | FORECAST 0.9457, CLAIM 0.9825, EVALUATION 0.8689 |
| Assertor | ASSERTED_BY F1 0.6667 | P 0.7692, R 0.5882, support 17 |
| Argument | positive macro-F1 0.4394 | positive micro-F1 0.8603, positive macro PR-AUC 0.5069 |
| Relation | positive macro-F1 0.0000 | positive macro PR-AUC 0.2349 |
| Entity Coreference | MERGE F1 0.9867 | P 0.9807, R 0.9928, PR-AUC 0.9981 |
| Event Coreference | MERGE F1 0.0000 | P/R 0/0, PR-AUC 0.0149, support 7 |

Argument class별 결과:

| Role | Precision | Recall | F1 | Test support |
|---|---:|---:|---:|---:|
| ACTOR | 0.0000 | 0.0000 | 0.0000 | 11 |
| TARGET | 0.9065 | 0.9618 | 0.9333 | 131 |
| PLACE | 0.0000 | 0.0000 | 0.0000 | 5 |
| TIME | 0.8293 | 0.8193 | 0.8242 | 83 |

Argument confusion matrix:

| Gold \ Pred | NONE | ACTOR | TARGET | PLACE | TIME |
|---|---:|---:|---:|---:|---:|
| NONE | 2,259 | 0 | 13 | 0 | 14 |
| ACTOR | 11 | 0 | 0 | 0 | 0 |
| TARGET | 5 | 0 | 126 | 0 | 0 |
| PLACE | 5 | 0 | 0 | 0 | 0 |
| TIME | 15 | 0 | 0 | 0 | 68 |

Relation class별 결과:

| Relation | Precision | Recall | F1 | Test support |
|---|---:|---:|---:|---:|
| CAUSES | 0.0000 | 0.0000 | 0.0000 | 43 |
| RESPONDS_TO | 0.0000 | 0.0000 | 0.0000 | 0 |
| ABOUT | 0.0000 | 0.0000 | 0.0000 | 1 |

Relation은 44개 positive를 모두 NONE으로 예측했다. 전체 Gold에는 CAUSES 1,656,
RESPONDS_TO 147, ABOUT 7이 있지만 고정 seed의 test split에는 RESPONDS_TO가 0이고 ABOUT이
1뿐이다. 이는 metric collapse와 별개로 test class coverage warning이다.

## 8. Semantic proposal / verifier / decoder diagnostic

Verifier 수치는 Gold start/end 조합으로 만든 teacher-forced proposal 위의 task-local
classification이고, boundary/final 수치는 실제 decoded exact character span이다.

| Stage | Label | Precision | Recall | F1 | PR-AUC |
|---|---|---:|---:|---:|---:|
| Boundary proposal | EVENT | 0.6293 | 0.4915 | 0.5519 | - |
| Boundary proposal | STATEMENT | 0.6363 | 0.4928 | 0.5554 | - |
| Boundary proposal | ALL | 0.6333 | 0.4923 | 0.5539 | - |
| Pair verifier | EVENT | 0.8569 | 0.7214 | 0.7834 | 0.8921 |
| Pair verifier | STATEMENT | 0.8235 | 0.9016 | 0.8608 | 0.9338 |
| Pair verifier | ALL | 0.8356 | 0.8253 | 0.8304 | 0.9123 |
| Final constrained | EVENT | 0.6854 | 0.4611 | 0.5513 | - |
| Final constrained | STATEMENT | 0.6716 | 0.4884 | 0.5655 | - |
| Final constrained | ALL | 0.6772 | 0.4768 | 0.5596 | - |

Constraint/verifier 적용으로 proposal 대비 precision은 `0.6333 → 0.6772`, F1은
`0.5539 → 0.5596`으로 올랐지만 exact TP 955개 중 30개를 잃어 recall은
`0.4923 → 0.4768`로 낮아졌다. 현재 가장 먼저 생기는 Semantic 병목은 verifier 품질보다
boundary proposal recall이다.

## 9. Predicted / cascaded test

Presence와 네 extraction Head는 두 평가 mode에서 동일한 raw article prediction을 사용하므로
해당 exact metric은 oracle과 같다. 차이는 그 decoded output으로 Gold 없이 candidate와
EventFeatureBundle을 만든 이후다.

| Runtime 단계 | 결과 |
|---|---:|
| Decoded articles | 100 |
| Final graph nodes | 2,165 |
| Final graph edges | 159 |
| Assertor eligible → pruned pairs | 14,676 → 8,834 |
| Argument eligible → pruned pairs | 12,424 → 9,447 |
| Relation eligible → pruned pairs | 25,251 → 13,941 |
| EntityCoref eligible → pruned pairs | 15,602 → 9,728 |
| EventCoref eligible → pruned pairs | 2,280 → 2,264 |

Cascaded Argument prediction과 Event role feature:

| Role/class | Pair predictions | Event role present | Non-zero role representation |
|---|---:|---:|---:|
| NONE | 9,369 | - | - |
| ACTOR | 0 | 0 | 0 |
| TARGET | 0 | 0 | 0 |
| PLACE | 0 | 0 | 0 |
| TIME | 78 | 62 | 62 |

Gold-free decoded Argument가 만든 role별 EventFeatureBundle은 실제로 Relation과
EventCoreference까지 전달됐다. 다만 ACTOR/TARGET/PLACE가 모두 비어 있어 contract 연결은
동작하지만 runtime 정보량은 크게 붕괴했다. 159 graph edge 수는 Gold quality metric이 아니라
단순 materialization count다.

## 10. Oracle ↔ cascaded gap

| Task group | Oracle | Cascaded | Gap 해석 |
|---|---|---|---|
| Presence | 같은 decoded bits | 같은 decoded bits | 0 |
| Entity/Time/Semantic/Trigger | 같은 exact span metric | 같은 exact span metric | 0 |
| Argument | Gold mention/candidate에서 positive micro-F1 0.8603 | decoded candidate에서 TIME 78 외 positive 0 | candidate universe가 달라 직접 F1 차감 불가; 강한 cascade collapse |
| Relation | Gold candidate에서도 positive F1 0 | Gold-free graph metric 미구현 | task-local collapse가 cascade 이전부터 존재 |
| Entity Coreference | Gold mention pair MERGE F1 0.9867 | cluster Gold metric 미구현 | 높은 oracle pair F1을 runtime cluster 성능으로 해석 금지 |
| Event Coreference | Gold candidate에서도 MERGE F1 0 | cluster Gold metric 미구현 | task-local collapse가 cascade 이전부터 존재 |

P1인 backend/cluster-level Gold alignment를 이번 run에서 임의 구현하지 않았으므로 downstream
oracle과 cascaded 수치를 하나의 F1로 섞지 않았다.

## 11. Candidate positive recall과 Argument target sanity

전체 1,000 article preflight 결과다.

| Task | Gold + | Eligible + | Dropped + | Eligibility recall | Eligible - | Sampled - | Tensorized + |
|---|---:|---:|---:|---:|---:|---:|---:|
| Assertor | 244 | 244 | 0 | 1.000 | 244,267 | 13,633 | 242 |
| Argument | 2,263 | 2,263 | 0 | 1.000 | 114,618 | 22,388 | 2,247 |
| Relation | 1,810 | 1,810 | 0 | 1.000 | 359,283 | 27,231 | 1,805 |
| Entity Coreference | 28,030 | 28,030 | 0 | 1.000 | 130,929 | 60,226 | 28,014 |
| Event Coreference | 66 | 66 | 0 | 1.000 | 53,600 | 12,324 | 66 |

Eligibility 단계에서는 positive를 하나도 제거하지 않았다. Tensorized 수가 낮은 것은
candidate policy가 아니라 exact tokenizer alignment 이후의 coverage다.

| Argument target kind | Gold linked | Eligible | Tensorized |
|---|---:|---:|---:|
| LOCAL_ENTITY | 178 | 178 | 176 |
| TIME_EXPRESSION | 983 | 983 | 978 |
| EVIDENCE_SPAN | 1,096 | 1,096 | 1,087 |
| TYPED_LITERAL | 6 | 6 | 6 |

2,263개 link 중 2,247개가 tensorization됐다. 누락 16개는 모두 source Event가 아니라 target
span 정렬 실패다. Split별로 train `1,783/1,796`, dev `234/235`, test `230/232`다.
`LOCATION` 12개는 adapter에서 PLACE로 모두 변환됐다. Gold 파일은 preflight 전후 동일 SHA로
유지됐다.

## 12. 실제 decoded article sample

아래 5개는 test split 순서의 첫 5개이며 cherry-pick하지 않았다. 전체 offset, score, pair,
graph row는 `decoded-samples.json`에 있다.

1. `GNEWS-ae335bac69d19e6cf047500ae26eef4d`
   - “AI 초개인화 장기 재생 플랫폼 … 탈모 치료 소재 전임상…”
   - EVENT 4, STATEMENT 7을 추출했지만 entity/time/positive pair가 없어 graph는 node 11,
     edge 0이다.
2. `GNEWS-162b511957621e13b6c245ed634e220b`
   - “나이가 들수록 신체는 자연스럽게 변화를 겪고…”
   - STATEMENT 15만 추출했고 Event가 없어 graph edge가 0이다. 일부 포함 관계의 Statement가
     함께 남아 containment 오류 사례를 보여준다.
3. `GNEWS-74530c2d11164560b0de66a31d74429b`
   - “김민재… 뮌헨은 … 아스널에 1-3으로 졌다.”
   - Entity 5, Time 1, EVENT 15, STATEMENT 6, Trigger 19를 추출했다. TIME argument 1개가
     살아 `TIME`과 `OCCURRED_ON` edge가 각 1개 materialize됐다.
4. `GNEWS-8c0c50bdd9f70c4e558b36e946e11c35`
   - “애플이 2일 … 아이폰17e와 새로운 아이패드 에어…”
   - Entity prediction 20개, Time 3, EVENT 8, STATEMENT 6, Trigger 11이다. TIME argument
     2개는 살아남았지만 EntityCoref MERGE가 다수 발생해 final Entity cluster는 2개가 됐다.
     cluster Gold metric 전에는 이 결과를 성공으로 해석할 수 없다.
5. `GNEWS-9329785167c24e496aa09c97b9c7f736`
   - “배우 성동일과 아들 성준이 … 유튜브 예능에 동반 출연…”
   - Entity 4, Time 4, EVENT 8, STATEMENT 6, Trigger 4를 추출했다. TIME argument 4개와
     `TIME`/`OCCURRED_ON` edge 각 4개가 생성됐고 다른 role은 비어 있다.

## 13. 병목 판정

최종 runtime의 가장 큰 병목은 **cascade**다. 근거는 oracle Argument가 TARGET/TIME에서는
높은 F1을 보이지만 decoded runtime에서는 TIME만 전달되고, 100개 article 전체에서
ACTOR/TARGET/PLACE Event feature가 0이라는 점이다. Entity/Semantic/Trigger의 낮은 exact
recall과 아직 runtime 추출 책임이 없는 EVIDENCE_SPAN/TYPED_LITERAL이 함께 증폭된다.

(task-local)에서는 **architecture와 data imbalance**가 함께 병목이다. Relation은 Gold
candidate에서도 all-NONE이고 EventCoreference는 all-KEEP이어서 cascade만으로 설명할 수 없다.
전체 Gold support도 Event MERGE 66, PLACE 12, ABOUT 7로 매우 희소하다. 반면 hard candidate
eligibility recall은 모든 task에서 1.0이므로 현재 evidence로 candidate eligibility는 주병목이
아니다. Runtime pruning의 Gold recall은 cluster-level alignment가 없어서 아직 판정하지 않는다.

## 14. 다음 ablation 제안

이번 run에서는 아래 변경을 수행하지 않았다. 다음 실험은 한 번에 하나만 바꾸고 동일
Gold/split/seed/global selection과 oracle/cascaded 분리를 유지한다.

1. **EventCoreference loss/sampling:** CE ↔ focal 또는 positive-aware sampling. 현재 public
   loss strategy 경계로 trainer 변경 없이 비교할 수 있다.
2. **Relation imbalance:** 기존 encoder를 유지한 채 class-weighted/focal loss를 먼저 비교하고,
   이후 P1 결정에 따라 LocalEvent/cluster endpoint representation을 단독 ablation한다.
3. **Semantic boundary:** verifier는 상대적으로 강하므로 verifier 교체보다 boundary recall을
   높이는 proposal/loss ablation을 먼저 한다. Threshold calibration은 dev에서만 별도 수행한다.
4. **Argument role imbalance:** ACTOR/PLACE의 sampling 또는 class-aware loss를 단독 비교한다.
   EVIDENCE_SPAN/TYPED_LITERAL runtime contract는 backend DTO 결정과 함께 P1로 유지한다.
5. **Presence MIX:** MIX support와 confusion을 기준으로 auxiliary λ 또는 rare-state sampling을
   한 요소씩 비교한다.
6. **Trigger full multitask retraining:** task-local ablation에서 채택된 `pos_weight=4`, all
   negatives, greedy one-to-one contract를 다음 full multitask run에서 적용한다. 이 문서의
   과거 checkpoint에는 task-local weight를 병합하지 않는다.

## 15. 검증과 남은 P1

- `compileall`: 통과
- model/training contract unit tests: 17/17 통과
- 8-article MPS instrumentation smoke: train/dev/checkpoint/oracle/cascade 통과
- full preflight: PASS_WITH_WARNINGS, Gold SHA 불변, split과 candidate audit 검증
- full run: 2,400 optimizer steps, NaN/Inf 없음
- checkpoint reload: 성공, backbone tensor 저장 없음

전체 `unittest discover -s tests`는 현재 Git에서 추적되지 않는 별도 viewer 작업이 Python
package name을 가려 viewer import 3건이 실패했다. 이번 run의 model/training 17개 test와는
분리해 실행했으며 viewer 파일은 수정하지 않았다.

의도적으로 유지한 P1:

- Event coreference 이후 LocalEvent/cluster-level Relation
- hard-negative sampler 고도화
- dev threshold calibration
- Gold coverage supervision mask
- backend DTO/schema adapter와 final graph Gold metric
- `EVIDENCE_SPAN`/`TYPED_LITERAL` intermediate ontology 결정
