# V3 Time Contract Decision Audit v1

## 결과와 결론의 경계

Round 01–03 최종 150 article에서 Time mention **865건 / unique surface 601개**와
Event TIME attachment **1004건**을 확인했다. 최종본·content SHA·exact
offset·reference를 검증했으며 subtype diagnostic은 Gold에 저장하지 않았다.

**Head label 외의 정보 수요는 있으나, 현재 DeBERTa TIME attachment/graph가 4-way neural subtype을
필수 feature로 요구한다는 증거는 없다.** 독립 LQ-FSE에서는 typed DTO와 rule별 정규화가 실행 연결되어
있고 GLiner에서는 subtype을 extraction query/schema confidence 보정과 export/display에 사용한다.
따라서 ‘repository 어디에서도 Head label 외에 사용하지 않는다’는 주장은 틀리다. 다만 DeBERTa extraction Head가 반드시
4 subtype을 예측해야 한다는 결론과 다르다. 추천은 C→B→A, 실제 contract 결정은 보류한다.

## 실제 실행 흐름

시간 표현 추출(TimeBIOHead) → typed BIO decode → `TIME` kind 후보 → Event×TIME pair와 허용 mask
→ ArgumentHead TIME role → graph assembly. subtype은 descriptor.label에 있으나 candidate tensor의
kind embedding/pair feature에는 들어가지 않는다. baseline engine의 Time node는 subtype 없이 text만
전달하며 RelativeTimeNormalizer는 text/published_at만 받는다. 반면 v3 pilot은 subtype supervision이
없어 Time target을 전부 -100으로 mask하고 decode/graph Time 경로를 비활성화했다.

원래 LQ-FSE viewer는 construct_frontend에서 rule extraction/normalization을 호출한다. 날짜/시각/기간/
반복의 의미 구분이 parser rule에 있으며 정규화 분기는 neural subtype이 아닌 `candidate.rule`이다.
DATE는 날짜, TIME은 시각, DURATION은 ISO duration을 만들고 SET은 recurrence 미지원 상태를 남긴다.
정규화 결과의 precision/status/anchor와 분류 subtype은 별개의 계약이다. 최종 Event.occurredAt
결정기나 DURATION/SET subtype별 서비스 분기 요구는 확인하지 못했다. mockup occurredAt은 뉴스 사건
시각이 아니라 사용자 탐색·열람 activity timestamp이며 subtype consumer가 아니다.

## 1. Diagnostic 분포

| 분류 | mention 수 | 비율 |
|---|---:|---:|
| DATE | 325 | 37.6% |
| TIME | 9 | 1.0% |
| DURATION | 53 | 6.1% |
| SET | 9 | 1.0% |
| AMBIGUOUS | 461 | 53.3% |
| OTHER | 8 | 0.9% |

명확한 surface 규칙 **396건**, 추가 검토 **469건**이다. 후자는 의미/정책 검토
423건과 단순 rule 미포착 46건으로 분리했다. 규칙 미포착을 본질적 의미
모호성으로 계산하거나 rule coverage를 자동 annotation 정확도로 해석하면 안 된다. 확정형 diagnostic도
사람이 검수한 subtype Gold가 아니다. AMBIGUOUS는 약한 근거를 강제로 adjudicate하지 않은 결과이며,
OTHER는 좁은 4-way surface taxonomy 밖의 양상/순서 표현이지 기존 textual TIME Gold가 틀렸다는 뜻이 아니다.
모든 865행은 원문 offset/문장/원래 decision·provenance/attachment와 함께 JSON에 보존했다.

규칙은 surface-only다. bare `14일`의 calendar ordinal/14일 duration, bare `32분`의 경기 시점/기간처럼
문장을 읽으면 풀릴 가능성이 있는 사례도 보류했다. 달력으로 고정된 기간은 diagnostic DATE로 처리하되
`지난 13일 하루 동안`처럼 명시적인 기간까지 결합한 span은 보류했다. 날짜+시각은 subtype 우선순위가
v3에 없으므로 AMBIGUOUS다. 학습 label을 맞추려고 span을 둘로 자르지 않았다.

## 2. 요청한 경계 사례

| 표현 | exact corpus mention | diagnostic | 해석 |
|---|---:|---|---|
| 최근 | 51 | AMBIGUOUS | vague recent interval: DATE/DURATION 또는 상대지시 정책 필요 |
| 지난해 | 8 | DATE | DATE subtype은 안정적; 정규화 연도는 별도 anchor 필요 |
| 현재 | 13 | AMBIGUOUS | present instant/ongoing interval: DATE/TIME/DURATION 정책 보류 |
| 장기간 | 1 | DURATION | vague extent DURATION; 수치 길이는 미확정 |
| 매주 | 0 | SET | 명시 recurrence SET; 다음 발생 날짜를 알려주지는 않음 |
| 오전 8시 | 1 | TIME | 명시 clock TIME; 날짜/timezone은 별도 |
| 지난 13일 | 3 | DATE | calendar reference DATE; 어느 달/연도인지는 문맥 필요 |

corpus count=0인 예시는 사용자 제공 계약 probe이며 실제 발견한 데이터로 합산하지 않았다.
`지난해`가 DATE로 안정적이라는 것과 calendar year를 정규화할 anchor가 확정됐다는 것은 다르다.
`장기간`은 extent이므로 DURATION diagnostic이 가능하지만 정확한 길이는 알 수 없다.

## 3. Attachment와 subtype

raw TIME completeness: `{"PRESENT": 939, "ABSENT": 1433, "UNRESOLVED": 2}`.
attachment가 있는 unique mention 784건, Event attachment 없는 mention
81건, 여러 Event가 공유하는 mention 133건이다.
모든 raw time mention의 subtype field는 없으며 normalization 상태는
`{"EXPLICIT_TEXT_ONLY": 853, "NORMALIZED": 12}`이다.
attachment는 time_mention_id/evidence_scope/decision으로 구성되며 subtype을 target feature로 참조하지 않는다.
기존 v3 adapter의 구조적 projection에는 Time mention 865개와
TIME role link 999개가 남는다. Time extraction이 mask되어도
Gold Time 후보를 제공하는 **oracle Argument TIME supervision은 별도로 가능**하다. 이 수는 projection
개수이며 실제 tokenizer/tensorized loss 참여 개수나 이번에 실행한 학습량이 아니다.
projection에서 빠진 raw attachment 5건은 ID와 이유를 JSON에
보존했다. 이를 subtype 부재로 인한 누락이나 NONE negative로 바꾸지 않았다.

865 surface 전부에서 고정된 동일 offset/token index/score를 두고 DATE/TIME/DURATION/SET/generic diagnostic
label만 바꾼 기존 runtime candidate builder의 tensor 불변성 검사는
**865/865 통과**했다. token index는 격리된 test fixture이며 실제
tokenizer 정렬/Head prediction 성능을 측정하지 않았다. 이 검사는 추출 경계가 같을 때만 성립하며,
실제 typed BIO decode에서 subtype 전환은 경계를 바꾸므로 extraction을 subtype 독립이라고 하지 않는다.

기존 graph assembly 함수에서도 label만 바꿔 정규화값/edge가 동일함을 확인했다. generic property를
전달하면 assembler는 이를 그대로 보존할 수 있지만 baseline engine 자체는 type property를 전달하지 않는다.
잘못된 DURATION label에도 TIME→OCCURRED_ON이 생성되는 현재 동작은 **의미 계약 승인 증거가 아니다**.
발행시간을 사건 시각으로 복사하거나 새로운 fallback 정책을 적용하지 않았다.

## 4. 코드 의존성 감사

저장소 전체 rg-visible source 519개를 검색했다. literal TIME role/kind,
Cypher SET, fixture/example를 subtype consumer와 구별했다. `code_dependency.json`에 전체 lexical hit
inventory와 검증된 call-path/file/line/SHA가 있다. 경로 기반 자동 카테고리와 실제 사용처 검증을 구분했다.
외부 배포 서비스나 gitignored vendor/결과물 내부 실행 코드는 검사 범위가 아니다.

- [deberta_label_contract](../../../../ArticleLocal-KG-DeBERTa/models/contracts.py) — training_label, decoder; `execution-connected_baseline_pilot_disabled`. 4 subtype으로 9 BIO label을 구성하고 TimeBIOHead 최종 linear 출력 수를 정한다.
- [deberta_gold_tensor_loss](../../../../ArticleLocal-KG-DeBERTa/training/data/collators.py) — training_label; `execution-connected_baseline_pilot_masked`. time_type을 B/I target으로 변환해 token CE에 사용한다. v3 DATE는 구조 placeholder이며 전부 -100으로 mask한다.
- [deberta_typed_metric](../../../../ArticleLocal-KG-DeBERTa/models/tasks/statistics.py) — metric; `execution-connected_baseline_pilot_untyped_only`. exact span key에 label을 포함한다. v3 typed metric은 비우고 raw untyped mention 분모를 별도 관리한다.
- [deberta_metric_utility](../../../../ArticleLocal-KG-DeBERTa/training/metrics/spans.py) — metric; `implemented_helper_not_baseline_engine_metric_path`. 별도 ExactSpanMetric도 type+offset을 비교하지만 확인한 engine 주 경로는 TaskAdapter.metrics→exact_item_report다. helper 파일의 존재를 실행 연결 증거로 삼지 않는다.
- [deberta_bio_decoder](../../../../ArticleLocal-KG-DeBERTa/models/decoding/spans.py) — decoder; `execution-connected_baseline_pilot_skipped`. argmax B/I subtype의 연속성이 span 경계를 결정한다. subtype 전환은 span을 자르지만 DATE 고유 의미 분기는 없다.
- [deberta_candidate_attachment](../../../../ArticleLocal-KG-DeBERTa/training/data/runtime_candidates.py) — decoder, service_runtime_logic; `execution-connected_structural_probe`. decoded subtype은 descriptor.label에 보관하지만 kind는 모두 TIME이다. eligibility/label mask는 TIME kind, pair feature는 경계/문자열/Entity type/거리를 사용한다. subtype feature는 없다.
- [deberta_graph_baseline](../../../../ArticleLocal-KG-DeBERTa/training/trainers/engine.py) — graph_assembly, occurrence_time_resolution; `execution-connected_baseline_structural_probe`. baseline engine은 TIME node에 text만 전달하고 subtype을 생략한다. normalizer는 text/published_at을 사용하고 TIME edge→OCCURRED_ON은 subtype 조건이 없다. 최종 occurredAt 결정기가 아니다.
- [deberta_pilot_runtime](../../../../ArticleLocal-KG-DeBERTa/training/scripts/run_v3_round01_03_pilot.py) — service_runtime_logic, graph_assembly; `execution-connected_disabled_time_path`. v3 pilot은 Time extraction을 학습하지 않고 decode와 time_expressions를 비운다. 실제 TIME 처리 성공 증거로 취급하지 않는다.
- [deberta_viewer](../../../../ArticleLocal-KG-DeBERTa/viewer/adapters/json_result.py) — service_runtime_logic; `implemented_export_adapter_no_live_runtime_verified`. JSON type/time_type을 표시용 type으로 저장한다. subtype에 따른 업무 판단은 발견하지 못했다.
- [lq_training](../../../../ArticleLocal-KG/model/LQ-FSE/starlight_lq_fse/article_construction_task_heads.py) — training_label, metric, decoder; `execution-connected_training_recipe_static_trace`. 독립 LQ-FSE 9-label BIO 학습·supervision·recipe metric 계약이다. DeBERTa runtime import 경로가 아니다.
- [lq_rule_normalization](../../../../ArticleLocal-KG/viewer/streamlit_app/models/lq_fse/runtime.py) — decoder, occurrence_time_resolution, service_runtime_logic; `execution-connected_viewer_static_trace_not_executed_here`. viewer→pipeline.construct_frontend→rule detector/normalizer로 연결된다. DATE/TIME/DURATION/SET는 detector와 DTO에 필요하지만 normalization은 candidate.time_type 대신 candidate.rule로 분기한다. SET recurrence는 NOT_APPLICABLE, duration은 ISO duration이다.
- [lq_serialization](../../../../ArticleLocal-KG/model/LQ-FSE/starlight_lq_fse/construction_validation.py) — graph_assembly, service_runtime_logic; `execution-connected_construction_serialization_static_trace`. time_type/normalization status/value를 export하고 미완성 정규화 coverage를 기록한다. TIME attachment endpoint는 TimeExpression ID다.
- [gliner_training_metric](../../../../ArticleLocal-KG-GLiner/src/articlelocal_kg_gliner/head_contracts.py) — training_label, metric, decoder; `execution-connected_independent_pipeline_static_trace`. GLiner 독립 9-label contract/loss/typed token confusion/BIO decode 경로다. DeBERTa로 유입되지 않는다.
- [gliner_graph_export](../../../../ArticleLocal-KG-GLiner/src/articlelocal_kg_gliner/decoding.py) — graph_assembly, service_runtime_logic; `execution-connected_demo_export_static_trace`. decoded label→TimeExpression.time_type→Neo4j projection property/viewer 표시로 연결된다. subtype별 Event 시각 선택은 발견하지 못했다.
- [gliner_schema_config](../../../../ArticleLocal-KG-GLiner/config/gliner25-multi-v1.json) — decoder, service_runtime_logic; `execution-connected_extraction_api_static_trace_not_executed_here`. schema label description의 날짜/시각/기간/반복이 model_labels→extract_entities 인자로 전달되는 경로다. 이번에 GLiner 모델이나 서비스는 실행하지 않았다.
- [gliner_schema_confidence](../../../../ArticleLocal-KG-GLiner/src/articlelocal_kg_gliner/decoding.py) — decoder; `execution-connected_conditional_schema_calibration_static_trace`. BIO 외에도 subtype label로 schema query index를 선택하고 동일 exact shared-pool candidate의 confidence를 보정한다. 별도 GLiner 경로의 실제 subtype 소비지만 DeBERTa TIME attachment feature는 아니다.
- [legacy_gold_contract](../../../../ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v2.2.schema.json) — training_label; `contract_only_legacy_not_v3_annotation_source`. v2.x schema/loader는 필수 time_type enum을 갖는다. 이번에는 schema/code만 읽었으며 legacy annotation을 subtype source로 사용하지 않았다.
- [directiontest_experiments](../../../../DirectionTest/probe_kf_learned_layer_mix.py) — training_label, metric, decoder; `experiment_only_not_production_path`. 이전 layer/BIO 및 label-conditioned span 실험은 four-way taxonomy를 label-space로 소비한다. 서비스 의존이나 이번 진단의 모델 선택 근거가 아니다.
- [mockup_occurrence_homonym](../../../../mockup/src/data/repository.js) — service_runtime_logic; `execution-connected_unrelated_user_activity_timestamp`. occurredAt은 열람/탐색 activity fixture 시각이며 기사 Event Time subtype consumer가 아니다. Cypher SET도 taxonomy SET와 다르다.
- [v3_contract](../../../../ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json) — training_label, occurrence_time_resolution; `contract_only_no_subtype_field`. timeMention은 span/normalized_value/normalization_status/decision/provenance를 제공한다. additionalProperties=false이고 subtype field는 없다.

## 5. 세 안의 비교와 남은 불확실성

상세 비교는 [options.md](options.md)에 있다. C는 generic evidence를 보존하면서 필요 consumer에
파생 subtype·uncertainty를 제공할 수 있다는 점에서 우선 검토할 만하다. B는 현재 attachment에 가장
작은 의미 계약을 제공하지만 subtype query 편의를 잃는다. A는 typed API가 강제될 때 유리하나
865개 subtype annotation와 v3에 없는 복합/담화 분류 정책을 요구한다. 어느 안도 이번에 채택하지 않았다.

이번 분류는 classifier 정확도 평가가 아니라 contract 비용의 보수적 탐색이다. 모델 inference, 학습,
test metric/threshold 선택, Gold 재검토·수정, Round 04, production 변경, commit/push는 없다.
원래 provenance는 AI_ADJUDICATED 등 그대로 보존했고 HUMAN_REVIEWED로 바꾸지 않았다.

## 검증과 재현

`validation.json`: article/mention/attachment 수, unique IDs, source parity, reference, 금지 변경 검증.
`audit_manifest.json`: commit·기존 git status·입력/보호 대상 SHA·실측 시간.

```bash
cd ArticleLocal-KG-DeBERTa
conda run --no-capture-output -n model-test-py312 python training/scripts/run_v3_time_contract_audit.py
conda run --no-capture-output -n model-test-py312 python -m unittest tests.test_v3_time_contract_audit -v
```

GOLD_MODIFIED=false / CONTRACT_DECIDED=false / HEAD_MODIFIED=false /
PRODUCTION_MODIFIED=false / ROUND_GENERATION_RESUMED=false. 완료 후 멈춘다.
