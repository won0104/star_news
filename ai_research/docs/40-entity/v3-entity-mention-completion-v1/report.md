# V3 Entity Mention Completion — Nested-Capable Span Extraction v1

## 최종 판정

**ENTITY_MENTION_RUNTIME_READY_WITH_LIMITATIONS**

- `READY_FOR_TIME_EXPRESSION_COMPLETION=true`
- `READY_FOR_ENTITY_IDENTITY_RESOLUTION_AFTER_TIME=false`
- `ENTITY_RELEASE_STAGING_UPDATED=true`

Curated Entity Gold를 flat BIO에 맞춰 줄이지 않고 `SPAN_NATIVE_MULTILABEL`로 migration했다.
raw Article만 입력받는 canonical runtime에서 `EntityMention[]`가 실행되며 Entity Coreference와
Participant Resolution은 `NOT_RUN`이다. dev15 exact typed P/R/F1은
0.1425/0.8684/0.2448,
macro-F1 0.2420, macro PR-AUC 0.4677다.
18 nested pair 중 13쌍을 동시에 회복했다.

제한은 precision과 출력 밀도다. dev 평균 206.8 mentions/article,
false exact typed span 177.3/article로 evidence carrier로는 실행
가능하지만 바로 LocalEntity/coreference 입력으로 승격하기에는 과다하다. Gold 삭제, dev 재튜닝,
output cap 도입으로 이를 숨기지 않았다.

## Source of truth와 Gold geometry

- Curated RC Entity mentions: 4,817
- taxonomy: `{'LOCATION': 1144, 'ORGANIZATION': 1612, 'PERSON': 1525, 'PRODUCT': 536}`
- strict nested pairs: 103
  (same type 63, cross type 40)
- partial overlap / same-boundary pairs: 0 / 0
- character width min/median/p90/p95/p99/max: 1/
  3/8/
  11/19/
  56
- covering-token alignment: 4,816/4,817
- exact tokenizer endpoint alignment: 4,731/4,817
- model sentence representability failure / truncation / cross-sentence: 1/0/1

전체 150 Curated RC는 요청된 geometry audit에만 읽었다. sealed pilot_test의 cache, forward,
prediction, metric, selection, case review는 수행하지 않았다. model 작업은 pilot_train120과
최종 secondary sanity인 pilot_dev15만 사용했다.

## Flat BIO representation ceiling

기존 `EntityBIOHead`의 문제가 checkpoint 성능이 나빠서가 아니라 현재 output representation이
semantic Gold를 표현하지 못한다는 점을 계산했다. 최대-cardinality flat witness는
4,718/4,817
(97.94%)이며 최소 99 mentions를
동시에 잃는다. strict nested pair 두 mention의 동시 회복 ceiling은 0%다.
canonical manifest에는 Curated RC provenance를 가진 selected legacy EntityBIO checkpoint가 없어
실제 checkpoint 비교는 수행하지 않았고, incompatible parent checkpoint를 current performance로
오인하지 않도록 structural ceiling만 reference로 남겼다.

## 선택 architecture와 supervision

L12 routing, 기존 `DocumentContextEncoder`, `CandidateSpanEncoder`를 유지하고 contiguous span마다
PERSON/ORGANIZATION/LOCATION/PRODUCT independent logit을 냈다. 후보 identity는 absolute char
`[start,end)`이고, tokenizer token 내부 Gold endpoint도 covering token + deterministic character
boundary feature로 보존한다. 최대 token/character width는 20/56이고 width drop은 0이다.

모든 positive를 먼저 보존했다. exact Gold boundary의 wrong type은 `SAFE_NEGATIVE`,
`coverage.entity_annotation=REVIEWED`인 model-representable train sentence의 non-Gold span/type만
`PROVISIONAL_CLOSED_WORLD_NEGATIVE`로 사용했다. ambiguity/HRR touch 1830
candidates는 `UNKNOWN`으로 mask했다. N2–N6 support와 fixed sampling 결과는
`negative_sampling_audit.json`에 있다.

## Tiny learnability

동일 train 6기사 120-step에서 loss 0.8199→0.0032,
Gold score mean 0.5570→0.9790,
negative score mean 0.5570→0.0015였다.
flat/nested recall은 1.0000/1.0000,
nested pair joint recovery는 1.0000이고 네 type 모두 출력했다.
tiny checkpoint는 승격하지 않았다.

## Main, selection, release training

- internal split: train96 / validation24, article-level, seed1008
- maximum epoch: 8 (dev를 보고 연장하지 않음)
- selected epoch: 8
- primary selection: typed exact-span macro PR-AUC
- selected global threshold: 0.7 (checkpoint 선택 후 fixed grid)
- internal exact typed F1 / nested recall / joint recovery: 0.3191 /
  0.8261 / 0.6957
- release-purpose: 동일 epoch로 pilot_train120 fresh training
- selected checkpoint SHA: `6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`

pilot_dev는 이 모든 선택 후 한 번만 평가했고 feedback으로 architecture/objective/sampling/epoch/
threshold를 바꾸지 않았다. type별 F1은 PERSON 0.3372, ORGANIZATION
0.2653, LOCATION 0.2154, PRODUCT
0.1503다. FIRST LOSS는 `{'ENTITY_TRUE_POSITIVE': 442, 'TYPE_SCORE_REJECT': 67}`다.

## Runtime, graph, release

- runtime config: `eventframe_runtime_candidate_v3_entity_mention_freeze`
- Entity Mention: `ACTIVE`; Entity Coreference/Resolution: `NOT_RUN`
- prior Event/Statement/Trigger/StatementType/B2 exact parity: 15/15
- graph Entity evidence preservation: 3102/3102
- raw participant preserved: 163; fake Entity/dangling: 0/0
- release self-containment smoke: PASS; training-results dependency=false
- Entity-only cached-feature dev inference: 0.905s/article
- integrated online total runtime: 1.230s/article
- Entity activation runtime delta: 0.758s/article
- process peak RSS: 2.03 GiB
- GPU peak allocated: 3.56 GiB
- canonical unittest suite: 248 PASS, failures/errors 0, skipped 2

EntityMention evidence는 ⑧ assembler의 `unmaterialized_evidence.entity_mentions`에 그대로 전달한다.
ARTICLE/EVENT/STATEMENT node 외 Entity node나 MENTIONS edge를 만들지 않는다.
`EntityMention exists != LocalEntity exists`를 유지한다.

## 보호 상태

- CURATED_GOLD_MODIFIED=false
- GUIDELINE_MODIFIED=false
- ROUND04_RESUMED=false
- ENTITY_REPRESENTATION_MIGRATED=true
- ENTITY_MODEL_TRAINED=true
- ENTITY_RUNTIME_ACTIVATED=true
- ENTITY_RELEASE_CHECKPOINT_SELECTED=true
- ENTITY_COREFERENCE_EXECUTED=false
- PARTICIPANT_ENTITY_RESOLUTION_EXECUTED=false
- LOCATION_ENTITY_USED_AS_PLACE_GATE=false
- ENTITY_USED_AS_B2_FEATURE=false
- TIME_EXPRESSION_MODIFIED=false
- EVENT_COREFERENCE_MODIFIED=false
- RELATION_TRAINING_EXECUTED=false
- HF_REMOTE_PUSH_EXECUTED=false
- NOTION_MODIFIED=false
- PILOT_TEST_USED=false
- ORIGINAL_1K_DEV_TEST_USED=false

다음 roadmap은 별도 prompt의 generic TimeExpression completion이다. precision/density limitation 때문에
Entity identity resolution은 Time 이후에도 이 Entity operating point를 그대로 무비판적으로 입력하지
말고 별도 gate에서 candidate pruning/calibration 영향을 먼저 검토해야 한다.
