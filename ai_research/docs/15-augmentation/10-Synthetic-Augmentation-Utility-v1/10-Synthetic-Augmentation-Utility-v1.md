# Synthetic Augmentation Utility Experiment v1

## 1. 결론

세 synthetic warm-up 모두 현재 방식으로는 real `gnews-1k-construction-gold-v2.2`
dev 일반화를 개선하지 못했다.

| Task | Control dev | Augmented dev | Rare-class delta | 강한 class regression | Verdict |
|---|---:|---:|---:|---|---|
| Sentence Presence | 4-state macro-F1 0.5729 | 0.5708 | MIX F1 -0.0367 | 없음 | `NO_GENERALIZATION` |
| Argument | positive macro-F1 0.4543 | 0.4642 | ACTOR F1 +0.0000, PLACE 판정 불가 | TARGET/TIME은 오히려 개선 | `NO_GENERALIZATION` |
| Event Coreference | MERGE F1 0.0000, PR-AUC 0.3254 | MERGE F1 0.0000, PR-AUC 0.0068 | MERGE F1 +0.0000 | KEEP F1 변화 없음 | `NO_GENERALIZATION` |

따라서 다음 full multitask retraining에는 이 실험의 synthetic warm-up policy를
반영하지 않는다. Trigger의 별도 확정 production contract에는 영향이 없다.

## 2. 승인 및 provenance

Presence v1.2는 사용자의 release-level 승인을 다음과 같이 기록했다.

- `machine_ready=true`
- `human_release_ready=true`
- `human_decision=APPROVED_FOR_AUGMENTATION_TRAINING`
- `approval_type=HUMAN_RELEASE_APPROVAL`
- `approval_scope=AUGMENTATION_TRAINING_ONLY`
- `approval_date=2026-09-04`
- 근거: focused review + machine audit
- `row_level_gold_adjudication=false`

이는 synthetic을 train-only augmentation으로 사용할 수 있다는 승인이다. 200개 focused
review 행을 개별 Gold로 adjudication했다는 뜻이 아니며, 어떤 synthetic row도 Gold로
승격하지 않았다. 원본 행의 `SYNTHETIC` source, generation seed, generator version,
source article lineage는 그대로 유지했다.

검증한 immutable dataset SHA-256은 다음과 같다.

| Dataset | Rows | SHA-256 |
|---|---:|---|
| Presence v1.2 | 4,000 | `ca20fa4e86e757bf54bc6b53ee3d4000c1615acccc6750a1d4835771e5d82f7b` |
| Argument ACTOR/PLACE v1.1 | 4,250 | `856663e867ddd8c73f746a3541860f35a18062b3dda2bad2f6582c3888413054` |
| Event Coreference v1.1 | 5,800 | `27f2b45bcd608f8a3fa063e516a30de7b8c49b36b60587b63a31b407c8c18c1d` |
| Gold v2.2 | 1,000 articles | `428cec4ce1b92ca310a802882f50d1fc9687bd2bccfddfeb22944b136e0a086d` |

모든 synthetic source article ID는 800개 Gold train split에만 속했고 Gold dev/test ID
참조는 0건이었다.

## 3. 실험 계약

- Gold: `gnews-1k-construction-gold-v2.2`, 1,000 articles
- article split: 800/100/100, split seed 41
- training/sampling seed: 1008/1008
- backbone: frozen `kakaobank/kf-deberta-base`
- revision: `363b171d71443b0874b0bf9cea053eb5b1650633`
- max sentence tokens: 128
- architecture/loss/sampling: 현재 production/task-local default 유지
- config SHA-256: `ae47d8e0df503b3cddcdfc1293d5a34383043ae12c65c96a07dd90a0c8c9ab6b`
- CONTROL: fresh shared initialization → real train adaptation
- AUGMENTED: 동일 initialization → synthetic warm-up 3 epochs → optimizer reset → 동일 real adaptation
- real adaptation: 최대 8 epochs, patience 3, min delta 0.0001
- selection: real Gold dev only
- test evaluation: 0회, `test_used_for_selection=false`
- GPU execution: Presence → Argument → EventCoreference 단일 process 순차 실행

Argument와 Event Coreference의 real dev는 synthetic data utility를 Head 단위로 분리하기
위한 Gold candidate/oracle upstream task-local 평가다. predicted-cascaded runtime 평가는
이번 utility probe의 범위가 아니며, 이 결과를 end-to-end graph 성능으로 해석하지 않는다.

Frozen KF source-token cache는 비교 조건 사이에서 공유했지만 모든 trainable module은
task별 fresh initialization을 저장하고 CONTROL/AUGMENTED 시작 전에 같은 parameter SHA로
복구했다. task별 실행 시간은 Presence 9분 44초, Argument 12분 8초, Event Coreference
15분 9초였다.

## 4. Trainable parameter

| Task | Trainable production modules | Parameters | Backbone trainable |
|---|---|---:|---:|
| Presence | document context + Sentence Presence adapter/Head | 2,076,678 | 0 |
| Argument | document context + candidate span encoder + directed pair encoder + Argument adapter/Head | 3,272,613 | 0 |
| Event Coreference | document context + candidate span encoder + EventFeatureEncoder + Event Coreference adapter/Head | 3,778,282 | 0 |

Head architecture, loss strategy, label taxonomy, candidate policy는 조건 사이에서 바꾸지 않았다.

## 5. Presence

Selection metric은 real dev 4-state macro-F1이다. CONTROL은 epoch 3,
AUGMENTED는 epoch 7이 선택됐다.

| Metric | CONTROL | AUGMENTED | Delta |
|---|---:|---:|---:|
| EVENT bit P/R/F1 | 0.7640 / 0.6921 / 0.7263 | 0.7735 / 0.7125 / 0.7417 | F1 +0.0154 |
| STATEMENT bit P/R/F1 | 0.7500 / 0.8133 / 0.7804 | 0.7749 / 0.7971 / 0.7858 | F1 +0.0055 |
| 4-state macro-F1 | 0.5729 | 0.5708 | -0.0021 |
| DROP F1 | 0.6833 | 0.6891 | +0.0059 |
| EVENT-only F1 | 0.7255 | 0.7422 | +0.0167 |
| STATEMENT-only F1 | 0.7746 | 0.7805 | +0.0058 |
| MIX F1 | 0.1081 | 0.0714 | **-0.0367** |
| MIX Gold support / predicted | 22 / 15 | 22 / 6 | predicted -9 |

Confusion matrix(row=Gold, column=prediction):

| CONTROL | DROP | EVENT | STATEMENT | MIX |
|---|---:|---:|---:|---:|
| DROP | 452 | 84 | 139 | 0 |
| EVENT | 71 | 530 | 155 | 8 |
| STATEMENT | 123 | 79 | 885 | 5 |
| MIX | 2 | 4 | 14 | 2 |

| AUGMENTED | DROP | EVENT | STATEMENT | MIX |
|---|---:|---:|---:|---:|
| DROP | 470 | 79 | 126 | 0 |
| EVENT | 82 | 550 | 130 | 2 |
| STATEMENT | 136 | 82 | 871 | 3 |
| MIX | 1 | 7 | 13 | 1 |

Synthetic warm-up loss는 0.1365 → 0.000003 → 약 0으로 급감했다. 이는 synthetic
template를 매우 쉽게 기억했지만 real-news MIX boundary로 일반화하지 못했다는 증거다.
ordinary bit/class는 유지됐으나 핵심 MIX는 악화되어 `NO_GENERALIZATION`으로 판정한다.

## 6. Argument

Selection metric은 real dev positive macro-F1이다. CONTROL은 epoch 2,
AUGMENTED는 epoch 3이 선택됐다.

| Role | Gold support | CONTROL P/R/F1 | AUGMENTED P/R/F1 | F1 delta |
|---|---:|---:|---:|---:|
| ACTOR | 15 | 0 / 0 / 0 | 0 / 0 / 0 | +0.0000 |
| TARGET | 101 | 0.9429 / 0.9802 / 0.9612 | 0.9615 / 0.9901 / 0.9756 | +0.0144 |
| PLACE | **0** | 0 / 0 / 0 | 0 / 0 / 0 | 판정 불가 |
| TIME | 118 | 0.8320 / 0.8814 / 0.8560 | 0.8042 / 0.9746 / 0.8812 | +0.0253 |

| Aggregate | CONTROL | AUGMENTED | Delta |
|---|---:|---:|---:|
| positive macro-F1 | 0.4543 | 0.4642 | +0.0099 |
| positive micro-F1 | 0.8750 | 0.8940 | +0.0190 |
| positive macro PR-AUC | 0.6588 | 0.6619 | +0.0031 |
| predicted ACTOR / PLACE | 0 / 0 | 0 / 0 | 0 / 0 |

Confusion matrix의 핵심 행은 다음과 같다.

| Gold row | CONTROL prediction | AUGMENTED prediction |
|---|---|---|
| ACTOR (15) | NONE 15 | NONE 15 |
| TARGET (101) | NONE 2, TARGET 99 | NONE 1, TARGET 100 |
| TIME (118) | NONE 14, TIME 104 | NONE 3, TIME 115 |
| PLACE | dev support 0 | dev support 0 |

Synthetic warm-up loss는 0.0591 → 0.0211 → 0.0138로 감소했으나 ACTOR decision
boundary는 real dev에서 전혀 살아나지 않았다. PLACE는 split seed 41의 Gold dev 원본에
positive가 없으므로 dev-only 계약에서 augmentation utility를 판정할 수 없다. 참고로 원본
Gold role support는 train PLACE 7, dev 0, test 5이며 test는 확인 목적으로도 평가하지 않았다.
ACTOR 실패만으로도 목표가 달성되지 않았으므로 task verdict는 `NO_GENERALIZATION`이다.

## 7. Event Coreference

Selection metric은 MERGE F1이다. 두 조건 모두 모든 epoch에서 F1 0이어서 tie-break 없이
최초 epoch가 선택됐다.

| Metric | CONTROL | AUGMENTED | Delta |
|---|---:|---:|---:|
| MERGE P/R/F1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| MERGE PR-AUC | 0.3254 | 0.0068 | **-0.3185** |
| KEEP P/R/F1 | 0.9908 / 1.0000 / 0.9954 | 0.9908 / 1.0000 / 0.9954 | F1 0 |
| macro-F1 | 0.4977 | 0.4977 | 0 |
| Gold MERGE support | 12 | 12 | 0 |
| predicted MERGE / candidate pairs | 0 / 1,307 | 0 / 1,307 | 0 |

CONTROL의 epoch별 MERGE PR-AUC는 0.3254, 0.3721, 0.3414, 0.0576이고 AUGMENTED는
0.0068, 0.0127, 0.0322, 0.0469다. 따라서 F1 tie 때문에 선택된 epoch만의 우연이 아니라
관찰된 모든 real adaptation epoch에서 augmented ranking이 control보다 낮았다.
Synthetic warm-up loss는 0.5567 → 0.2363 → 0.2142였지만 real MERGE collapse를 해결하지
못해 `NO_GENERALIZATION`으로 판정한다.

## 8. Candidate audit

Eligibility positive recall은 세 task의 train/dev/test 모두 1.0이었다. Presence는 pair
candidate task가 아니므로 all-Gold-sentence supervision universe를 같은 형식으로 기록했다.

| Split / Task | Gold positive | Eligible positive | Dropped positive | Eligible recall | Sampled negative | Tensorized positive |
|---|---:|---:|---:|---:|---:|---:|
| train / Presence | 16,006 | 16,006 | 0 | 1.0000 | 6,279 | 16,006 |
| dev / Presence | 1,878 | 1,878 | 0 | 1.0000 | 675 | 1,878 |
| train / Argument | 1,796 | 1,796 | 0 | 1.0000 | 17,794 | 1,783 |
| dev / Argument | 235 | 235 | 0 | 1.0000 | 2,300 | 234 |
| train / Event Coreference | 47 | 47 | 0 | 1.0000 | 9,836 | 47 |
| dev / Event Coreference | 12 | 12 | 0 | 1.0000 | 1,302 | 12 |

Argument의 eligibility 이후 tensorization에서 train 13건, dev 1건이 tokenizer exact
alignment 때문에 빠졌다. Eligibility recall 1.0과 별개인 이 손실은 후속 Gold coverage
supervision-mask/audit에서 계속 추적해야 한다.

## 9. 실행 curve

아래 값은 `(train loss / dev loss / dev primary metric)`이다.

| Task / condition | Epoch curve |
|---|---|
| Presence CONTROL | e1 1.0924/0.9876/0.5269; e2 0.9042/0.9356/0.5709; e3 0.8425/0.9790/0.5729; e4 0.7904/1.0448/0.5544; e5 0.7229/0.9331/0.5512; e6 0.6533/1.0454/0.5585 |
| Presence AUGMENTED | e1 1.4587/1.1042/0.5058; e2 0.9479/0.9897/0.5240; e3 0.8601/0.9295/0.5496; e4 0.8112/1.0612/0.5347; e5 0.7569/0.9265/0.5449; e6 0.6955/1.0169/0.5666; e7 0.6387/1.0384/0.5708; e8 0.5920/1.1209/0.5408 |
| Argument CONTROL | e1 0.1163/0.0622/0.4393; e2 0.0649/0.0573/0.4543; e3 0.0521/0.0675/0.4512; e4 0.0437/0.0659/0.4490; e5 0.0355/0.0646/0.4424 |
| Argument AUGMENTED | e1 0.1891/0.0608/0.4421; e2 0.0769/0.0534/0.4614; e3 0.0588/0.0560/0.4642; e4 0.0499/0.1044/0.4221; e5 0.0391/0.0737/0.4458; e6 0.0345/0.0884/0.4463 |
| EventCoref CONTROL | e1 0.0235/0.0352/0; e2 0.0206/0.0275/0; e3 0.0205/0.0233/0; e4 0.0183/0.0319/0 |
| EventCoref AUGMENTED | e1 0.0722/0.0315/0; e2 0.0205/0.0278/0; e3 0.0214/0.0283/0; e4 0.0207/0.0308/0 |

## 10. 답변 및 다음 단계

1. Presence augmentation은 real-news MIX를 살리지 못했다. MIX F1이 0.1081에서
   0.0714로 하락했다.
2. Argument augmentation은 ACTOR를 살리지 못했다. PLACE는 real dev support가 0이라
   이번 계약으로 판단할 수 없다.
3. EventCoreference augmentation은 MERGE collapse를 해결하지 못했고 ranking도 악화했다.
4. Argument는 rare-role class-aware loss/sampling과 Gold coverage 진단이 필요하다.
   EventCoreference는 positive-pair sampling/hard-negative 및 CE 대체 loss의 분리 실험이
   필요하다. Presence는 loss 변경보다 synthetic diversity, warm-up epoch/learning-rate,
   real adaptation ratio를 먼저 분리해야 한다.
5. Presence의 현재 architecture와 ordinary class 경로는 유지할 수 있지만 v1.2 warm-up
   policy는 닫을 수 없다. Argument/EventCoreference도 한 번의 data-only probe만으로
   architecture 문제라고 결론내리지 않으며 다음 training-contract 실험 전까지 유지한다.
6. 다음 full multitask retraining에는 세 synthetic augmentation을 모두 비활성화한다.
   각각 `NEXT_EXPERIMENT_REQUIRED`로 남기며 성능 ablation과 섞지 않는다.

## 11. Artifact 및 검증

- local result: `training/results/augmentation-utility-v1/summary.json`
- task artifacts: `presence/`, `argument/`, `event-coreference/`
- 각 condition: `history.json`, `dev-result.json`, `run.json`, dev-selected checkpoint
- 총 local artifact 크기: 약 11 GB (대부분 재사용 가능한 frozen-feature cache)
- config: `training/configs/augmentation-utility-v1.json`
- 회귀 테스트: model/training/augmentation 48 tests passed
- 전체 discovery의 별도 viewer tests 3개는 현재 checkout에 `viewer.adapters`와
  `viewer.ui`가 없어 import 실패했으며 이 experiment에서는 viewer를 수정하지 않았다.
- Gold/original synthetic/full baseline/Trigger/stable-task artifact hash는 실행 전후 동일했다.

실험 결과 checkpoint는 task-local utility artifact이며 full multitask checkpoint에 merge하지
않았다. Architecture, Gold, synthetic dataset, Trigger contract도 변경하지 않았다.
