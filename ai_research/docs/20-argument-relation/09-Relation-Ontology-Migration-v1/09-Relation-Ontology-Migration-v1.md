# Relation Ontology Migration v1

## 1. 목적과 판정

이 작업은 Relation F1 개선 실험이 아니다. Construction Gold v2.2를 수정하지 않고
서로 다른 의미 문제를 독립 supervision/model/runtime contract로 분리한 migration이다.

판정은 **CONTRACT MIGRATED / NO TRAINING RUN**이다.

- CAUSES, SUBEVENT_OF, ABOUT은 하나의 softmax에서 경쟁하지 않는다.
- RESPONDS_TO는 `LEGACY_ONLY`이며 production hard KG 학습과 materialization에서 제외된다.
- v2.2에 없는 SUBEVENT_OF를 NONE negative로 만들지 않는다.
- Story builder, synthetic data, 재학습, threshold tuning은 실행하지 않았다.
- 원본 Gold SHA-256은 실행 전후
  `428cec4ce1b92ca310a802882f50d1fc9687bd2bccfddfeb22944b136e0a086d`로 같다.

## 2. 확인된 기존 Relation 구조

기존 구조는 **실행 연결 (`execution-connected`)** 상태였다.

1. Gold adapter가 v2.x `relations`의 label을 `NONE / CAUSES / RESPONDS_TO / ABOUT`으로
   발견한다.
2. `GoldCandidateBuilder`가 Event/Statement source와 Event/Entity target을 하나의
   `relation` candidate universe로 만든다.
3. 공통 방향 pair 표현기(`DirectedPairEncoder`)가 `relation` task embedding으로 pair를
   표현한다.
4. 공통 Relation 분류기(`RelationHead`)가 4-class softmax를 출력한다.
5. 공통 pair adapter가 CE loss, multiclass metric, argmax decode를 담당한다.
6. Runtime graph assembler가 Relation 출력을 hard edge로 승격한다.

즉 Event→Event의 CAUSES/RESPONDS_TO와 Statement→Event/Entity의 ABOUT이 class mask로
구분되기는 했지만 같은 Head와 metric namespace에 있었다.

## 3. 새 Relation 구조

Production mode 이름은 `production_v1`이다. 역사 재현 mode는 `legacy_v2_2`다.

```text
DirectedPairEncoder
├─ assertor          Statement → Entity             NONE / ASSERTED_BY
├─ argument          Event → Entity/Time/Literal    NONE / ACTOR/TARGET/PLACE/TIME
├─ causal            Event → Event                  NONE / CAUSES
├─ subevent          Event → Event                  NONE / SUBEVENT_OF
└─ statement_about   Statement → Event/Entity       NONE / ABOUT

EntityCoreference / EventCoreference
└─ symmetric encoder, KEEP / MERGE
```

`causal`, `subevent`, `statement_about`은 각자 classifier parameter, target tensor, loss,
metric, decode namespace를 가진다. 같은 pair가 CAUSES와 SUBEVENT_OF 양쪽에서 positive일
수 있는 독립 binary contract이며, 두 label은 상호 배타 softmax가 아니다.

PART_OF는 Event→Story hard KG contract만 추가했다. Story builder나 PART_OF 학습 Head는
이번 범위에 없다.

## 4. Endpoint matrix

| Family/task | Source | Target | Label space | v2.2 supervision | Runtime 상태 |
|---|---|---|---|---|---|
| Assertor (`assertor`) | Statement | Entity | NONE / ASSERTED_BY | 기존 244건 | 기존 실행 연결 |
| Argument (`argument`) | Event | Entity / Time / typed literal | NONE / ACTOR / TARGET / PLACE / TIME | 기존 2,263건 | 기존 실행 연결 |
| Causal (`causal`) | Event | Event | NONE / CAUSES | legacy CAUSES에서 view 생성 | contract 실행 연결, 재학습 안 함 |
| Subevent (`subevent`) | child Event | parent Event | NONE / SUBEVENT_OF | 없음 | Head/candidate/graph contract만 연결, materialization 비활성 |
| StatementAbout (`statement_about`) | Statement | Event / Entity | NONE / ABOUT | legacy ABOUT에서 view 생성 | contract 실행 연결, 재학습 안 함 |
| Story membership | Event | Story | PART_OF | 없음 | graph endpoint contract only |

현재 Gold의 `LOCATION` argument role은 기존 adapter 정책대로 `PLACE`로 투영된다.
코드의 Value 표현은 현재 `TYPED_LITERAL` candidate다.

## 5. Legacy Gold v2.2 실제 relation audit

입력은
`../ArticleLocal-KG/data/gold/gnews/gnews-1k-construction-gold-v2.2.json`이고,
고정 split은 article 단위 seed 41, 800/100/100이다. Tensorized 수치는
`kakaobank/kf-deberta-base` tokenizer revision
`363b171d71443b0874b0bf9cea053eb5b1650633`, 문장당 최대 128 token으로 전체 1,000건을
실제 collator에 통과시켜 얻었다.

| Legacy label | Endpoint | Gold | 포함 article | Train | Dev | Test | Eligible + | Tensorized + | Production view |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| CAUSES | Event→Event | 1,656 | 150 | 1,474 | 139 | 43 | 1,656 | 1,651 | `causal` |
| RESPONDS_TO | Event→Event | 147 | 15 | 146 | 1 | 0 | 147 | 147 | `LEGACY_ONLY` |
| ABOUT | Statement→Event | 7 | 6 | 4 | 2 | 1 | 7 | 7 | `statement_about` |
| 합계 |  | 1,810 | - | 1,624 | 142 | 44 | 1,810 | 1,805 |  |

v2.2의 ABOUT은 실제로 7건 모두 Event target이었다. 새 contract는 향후 Entity target도
허용한다. CAUSES 5건은 endpoint eligibility에는 들어왔지만 token/candidate alignment 뒤
tensorize되지 않았다. 해당 article과 alignment 사유는 `legacy-gold-audit.json`의
`tensorization_gap_articles`에 보존한다. 이 migration은 기존 alignment 정책을 넓히지 않는다.

Source category별 count와 article당 relation histogram도 audit JSON에 포함했다. 주요 희소성은
RESPONDS_TO가 test 0건, ABOUT이 전체 7건이라는 점이다.

## 6. Supervision migration 결과

### CAUSES

Legacy row를 수정하지 않고 `(source LocalEvent, target LocalEvent)`를 `causal` view로 옮겼다.
Gold 1,656건과 structurally eligible 1,656건이 보존됐다. Actual tensorized positive는 기존과
같이 1,651건이다. 재라벨링·재학습·threshold 조정은 하지 않았다.

### ABOUT

Legacy ABOUT 7건을 `statement_about` view로 옮겼다. `relation` Event label space에서는
완전히 제거했다. ASSERTED_BY와 Head/target/loss/metric을 공유하지 않는다. 7건 모두 eligible,
7건 모두 tensorized됐다.

### RESPONDS_TO

147건은 원본과 audit에 그대로 남지만 migration status는 `LEGACY_ONLY`다.
`production_v1` positive map, task registry, class mask, hard edge endpoint contract에 없다.
CAUSES로 자동 변환한 건수는 0이다. response-like 정보는 향후 Story coherence feature이며
이번 작업에서 학습 target이나 hard edge로 만들지 않았다.

### SUBEVENT_OF

v2.2 supervision은 0건이다. Production collator는 SUBEVENT_OF candidate absence를 NONE으로
학습하지 않고 빈 supervised tensor와 `UNAVAILABLE_IN_GOLD_V2_2` status를 낸다.
전체 v2.2의 same-article canonical ordered Event pair는 105,670개지만 이들을 negative Gold로
간주하지 않는다. 따라서 새 데이터 전에는 loss는 0이고 materialization은 비활성이다.

## 7. Candidate universe 변경

Legacy `relation` universe:

- eligible positive 1,810
- eligible negative 359,283
- sampled negative 27,231

Production training view:

| Task | Eligible + | Eligible - | Sampled - | 범위 |
|---|---:|---:|---:|---|
| causal | 1,656 | 104,014 | 20,415 | same article, Gold coreference 후 LocalEvent ordered pair |
| statement_about | 7 | 255,416 | 15,551 | same article Statement→LocalEvent/LocalEntity |
| subevent | 0 | 0 | 0 | v2.2 supervision 미존재로 training universe 비활성 |

Runtime 1차 candidate는 한 article 안의 decoded Event mention pair만 만든다. 이후 predicted
Event Coreference 결과로 canonical Event에 lift한다. 전체 KG의 모든 Event pair를 만들지
않는다. Same bounded episode 후보군은 parent grounding/compatibility metadata와 새 annotation이
준비된 뒤 2차 policy로 좁혀야 한다.

## 8. SUBEVENT_OF 의미와 안전 정책

### 정의와 방향

`A SUBEVENT_OF B` iff A와 B는 서로 다른 실제 Event이고, B는 경계가 있는 현실 episode이며,
A는 B를 실제로 구성하는 부분 행위/단계이고 B의 시간적·상황적 범위 안에 포함된다.

방향은 `child Event → SUBEVENT_OF → parent Event`다.

다음 조건만으로는 SUBEVENT_OF가 아니다.

- 같은 Event의 다른 표현
- 같은 기사, 주제, Actor 또는 Story
- 시간적 연속, semantic similarity, participant continuity 또는 co-participation
- CAUSES 또는 response 관계

같은 현실 Event는 Event Coreference의 MERGE 대상이다.

### Hard safety constraint

- self-edge를 제거한다.
- cycle을 거부한다.
- 초기 hierarchy depth가 2를 넘으면 거부한다.
- parent node의 `grounded=true`, `bounded_episode=true`를 요구한다.
- `synthetic=true` parent를 거부한다.
- edge evidence의 `temporal_compatible=true`, `situational_compatible=true`를 요구한다.
- Coreference lift 뒤 child와 parent가 같은 canonical Event면 SUBEVENT_OF를 materialize하지 않는다.

## 9. Coreference / SUBEVENT_OF / PART_OF 경계

| Contract | 의미 | Runtime action |
|---|---|---|
| Event Coreference | same real-world Event | MERGE |
| SUBEVENT_OF | 서로 다른 Event지만 child가 bounded parent episode의 구성 단계 | child→parent hard edge |
| PART_OF | Event가 장기적으로 이어지는 Story에 속함 | Event→Story hard edge |

따라서 `Event Coreference ≠ SUBEVENT_OF`, `SUBEVENT_OF ≠ PART_OF`다.

## 10. Model / task registry / metric 변경

- `ModelConfig.relation_ontology_mode`가 `legacy_v2_2`와 `production_v1`을 분리한다.
- `ProductionTaskRegistry`는 기존 non-relation adapter를 재사용하고 legacy `relation` adapter를
  `causal`, `subevent`, `statement_about`으로 교체한다.
- `DirectedPairEncoder`는 mode별 task-name vocabulary를 명시적으로 받는다.
- 세 production relation task는 각각 2-class classifier와 CE/positive metric namespace를 가진다.
- `CandidateBatch.pair_task_names`가 tensor와 ontology task order 불일치를 fail-loud 처리한다.
- 학습 entry point는 config의 `relation_ontology.mode`를 model/builder/runtime에 함께 전달한다.

새 config는 `training/configs/relation-ontology-production-v1.json`이다. 이 config의 존재는
학습 승인이 아니며 이번 작업에서는 실행하지 않았다.

## 11. Graph assembly / serialization / viewer 변경

- Production graph는 RESPONDS_TO와 Story-only soft relation을 hard edge로 받지 않는다.
- CAUSES, SUBEVENT_OF, ASSERTED_BY, ABOUT, PART_OF endpoint를 명시적으로 검증한다.
- SUBEVENT_OF는 coreference lift 후 self-edge 제거와 cycle/depth/parent/compatibility를 검증한다.
- PART_OF를 위한 optional Story node endpoint는 받지만 Story를 생성하지 않는다.
- Model config serialization에 ontology mode와 SUBEVENT materialization gate가 기록된다.
- Viewer run contract에 `relation_ontology_mode`가 추가됐고 production payload의 RESPONDS_TO는
  `LEGACY_ONLY_RELATION` warning이다.
- Audit와 migration summary는 JSON으로 재생성 가능하다.

## 12. Backward reproducibility

- 기존 `RelationHead`, `BaselineTaskRegistry`, `PAIR_TASKS` alias, default `ModelConfig()`는
  `legacy_v2_2` 그대로다.
- Legacy `DirectedPairEncoder` task embedding은 5행으로 유지된다.
- 기존 config에 ontology mode가 없으면 legacy mode로 해석한다.
- Production pair vocabulary는 7행이고 Head key/shape도 다르다.
- Contract test에서 legacy state dict의 legacy→legacy strict load는 통과하고,
  legacy→production strict load는 실패한다.
- 실제 `full-baseline-v1-seed1008` checkpoint도 legacy trainable key 145/145,
  unexpected key 0으로 load됐고 production model에는 key mismatch로 거부됐다.
- 따라서 기존 checkpoint를 새 Head에 부분/강제 load하지 않는다.

이는 기존 baseline을 production ontology로 승인한다는 뜻이 아니라 역사 실험 재현 경로만
보존한다는 뜻이다.

## 13. Test와 재현 명령

```bash
conda run -n model-test-py312 python -m unittest \
  tests.test_augmentation \
  tests.test_checkpoint_warm_start \
  tests.test_gold_training_contracts \
  tests.test_metrics_graph \
  tests.test_model_contracts \
  tests.test_policies_decoding \
  tests.test_relation_ontology_migration \
  tests.test_task_local_convergence \
  tests.test_unblock_contracts \
  tests.viewer.test_contracts \
  tests.viewer.test_diagnostics \
  tests.viewer.test_ui_smoke

conda run -n model-test-py312 python \
  training/scripts/audit_relation_ontology_migration.py \
  --local-files-only \
  --cache-dir training/checkpoints/huggingface \
  --legacy-checkpoint \
  training/results/full-baseline-v1-seed1008/checkpoints/dev-selected.pt
```

위 named suite는 60개 test가 통과했다. `unittest discover -s tests`는 현재
`tests/viewer`가 runtime `viewer` package를 shadow해 import 단계에서 실패하므로 검증 명령으로
사용하지 않았다. 이 package discovery 구조는 이번 Relation migration 범위에서 수정하지 않았다.

Contract test는 다음을 검사한다.

- endpoint matrix와 Story soft/hard 경계
- 독립 Causal/Subevent positive 가능성
- legacy vs production registry/encoder/checkpoint shape 분리
- RESPONDS_TO 미변환/production 제외
- v2.2 derived supervision과 SUBEVENT unavailable 상태
- article-local candidate와 self-pair 금지
- graph RESPONDS_TO 차단, SUBEVENT cycle/grounding/coreference 경계
- PART_OF Event→Story 방향
- viewer legacy-only warning

## 14. 아직 필요한 새 데이터와 다음 학습 요구사항

필수 새 데이터:

1. 명시적 child/parent Event와 두 Event가 서로 다른 현실 Event임을 검수한 SUBEVENT_OF positive
2. hard negative: coreference, causal-only, response-only, temporal-only, topic/Actor/Story-only,
   high-similarity non-subevent
3. grounded/bounded parent flag와 temporal/situational compatibility evidence
4. hierarchy/cycle 검증이 가능한 article/episode 단위 annotation
5. Statement→Entity ABOUT 사례(현재 v2.2에는 0건)
6. PART_OF와 Story coherence는 별도 Story dataset/contract

다음 학습은 새 데이터 version과 provenance를 고정한 뒤 task별로 독립 수행해야 한다.
CAUSES, StatementAbout, Subevent는 같은 split/seed에서 각각 positive F1/PR-AUC와 candidate
recall을 보고하고, Subevent는 canonical Event 기준 graph cycle/depth violation 0을 추가 gate로
둔다. Calibration은 dev에서만 하고 기존 legacy checkpoint warm start는 허용하지 않는다.

## 15. 산출물과 commit 후보

- `docs/09-Relation-Ontology-Migration-v1.md`
- `training/results/relation-ontology-migration-v1/legacy-gold-audit.json`
- `training/results/relation-ontology-migration-v1/migration-summary.json`
- `training/scripts/audit_relation_ontology_migration.py`
- `tests/test_relation_ontology_migration.py`

Commit 후보:

```text
feat: split production relation ontology task contracts
```
