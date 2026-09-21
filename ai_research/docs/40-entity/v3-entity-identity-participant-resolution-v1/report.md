# V3 Entity Identity + Participant Resolution Completion v1

## 결론

`WORK_STATUS=ENTITY_IDENTITY_PARTICIPANT_RESOLUTION_RUNTIME_READY_WITH_LIMITATIONS`

현재 `SPAN_NATIVE_MULTILABEL` EntityMention을 입력으로 article-local Entity identity를 학습하고, deterministic `LocalEntity`를 materialize하며, B2의 raw ACTOR/TARGET/PLACE를 선택적으로 `LocalEntity`에 연결하는 stage ⑥ runtime을 완성했다. 기존 EntityMention, TIER1/TIER2 priority, raw participant 및 다른 canonical lane은 그대로 보존된다.

제한점은 두 가지다. 첫째, full predicted identity cascade의 recall은 upstream EntityMention/priority coverage와 보수적인 complete-link materialization 때문에 낮다. 둘째, full predicted participant cascade의 가장 큰 FIRST LOSS는 resolver가 아니라 upstream B2/Event miss다. 따라서 stage ⑥ 자체는 승격 가능하지만 end-to-end 결과는 `READY_WITH_LIMITATIONS`이다.

## 질문별 답변

1. **학습 가능성:** 가능했다. Entity coreference tiny sanity에서 loss가 `0.87745 → 0.24440`, PR-AUC가 `0.99464`, F1이 `0.95336`까지 도달했고, fresh main training도 non-trivial signal을 보였다.
2. **TIER coverage:** train+internal-validation Gold MERGE 중 upstream-recovered pair를 기준으로 strict TIER1-TIER1 coverage는 `88.64%`였다. TIER1-anchored bounded TIER2 rescue를 포함한 selected policy는 `99.24%`를 보존했다. Repository artifact의 `T1_ONLY` label은 "둘 다 TIER1"이 아니라 "적어도 한 쪽이 TIER1인 anchored pair"를 뜻한다.
3. **Entity Coreference 성능:** internal validation MERGE PR-AUC/P/R/F1은 `0.94753 / 0.91373 / 0.83674 / 0.87354`, frozen pilot_dev reference는 `0.95989 / 0.98414 / 0.81543 / 0.89187`이다. checkpoint epoch 8, threshold 0.6은 internal validation에서만 고정했다.
4. **Cluster 품질:** pair signal은 cluster 품질로 이어졌다. internal B³ F1은 `0.85841`, CoNLL F1은 `0.83857`; pilot_dev B³ F1은 `0.77708`, CoNLL F1은 `0.71260`이다. pilot_dev exact Gold-cluster match는 `106/164 = 64.63%`였다. CEAF-e는 SciPy가 없는 release 환경에서도 재현되도록 deterministic greedy assignment를 사용했다.
5. **TIER2 rescue 가치:** 있었다. TIER1-TIER1만으로는 internal Gold MERGE conditional coverage가 `88.64%`였지만 bounded rescue로 `99.24%`가 됐다. pilot_dev graph에서는 TIER2 mention 395개가 보존된 LocalEntity에 들어갔고, 361개는 TIER1 coreference cluster 경유, 34개는 participant-resolution rescue였다.
6. **LocalEntity 안전성:** pilot_dev 15개 기사에서 LocalEntity 472개와 MENTIONS 472개를 materialize했다. fake Entity 0, dangling reference 0, duplicate edge 0이며 deterministic serialization과 schema validation이 통과했다.
7. **Participant resolution:** 가능했다. frozen pilot_dev Gold-participant/Gold-entity pair P/R/F1은 `0.96472 / 0.56966 / 0.71633`, target accuracy는 `0.92361`이었다. predicted-participant/Gold-entity reference F1은 `0.71864`; full predicted cascade에서는 exact-Gold `ENTITY_RESOLVED` filler 27개 중 22개가 올바른 LocalEntity에 연결되어 conditional accuracy `0.81481`이었다.
8. **Role 강약:** Gold/Gold target accuracy 기준 ACTOR `0.98462`가 가장 강하고 PLACE `0.82192`가 가장 약하며 TARGET은 `0.91765`였다. 이 값은 role별 F1이 아니라 resolved-filler target accuracy다.
9. **Raw evidence 보존:** `SPAN_ONLY`, `CONTEXTUAL/UNRESOLVED`, `VALUE_RESOLVED`를 Entity negative로 강제하지 않았다. pilot_dev graph replay에서 raw EntityMention 3,102개와 raw participant 163개가 100% 보존됐다.
10. **FIRST LOSS:** pilot_dev `ENTITY_RESOLVED` Gold participant 기준 최대 손실은 `PARTICIPANT_UPSTREAM_MISS=261`이다. 그 뒤로 EntityMention upstream miss 2, candidate-universe miss 2, resolver-head miss 1이며 full success는 22다.
11. **다음 bundle:** stage ⑥ runtime/release/graph contract가 고정됐으므로 Work Bundle #4 Event Identity / Coreference로 진행할 수 있다. 이 작업에서는 해당 후속 작업을 시작하지 않았다.

## 고정 source와 Gold audit

- 시작 HEAD: `54ebe63d03822687f61d5f55026e4d91ab074349`
- Curated Gold SHA256: `0e4d1fa7f1dc0969fb8d8208c67cdd07b037f68b7acef71afd3d02af4ea80002`
- guideline SHA256: `a3c3012750b27b0ab3946a0156e43012e1b95204787deb73f50e4fbbab5030a1`
- EntityMention checkpoint SHA256: `6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`; threshold `0.7`
- soft-priority checkpoint SHA256: `7ae7813979d2fa30d56dbd915fa8446b0d01b7c39679c5b4fec58e34cb11f0f6`; threshold `0.3`
- Gold EntityMention 4,817개, LocalEntity cluster 1,753개, singleton 1,016개, multi-mention 737개, 최대 cluster size 54
- explicit cluster membership에서 파생된 MERGE 18,078쌍; reviewed scope에서 파생한 provisional KEEP 120,146쌍
- same-surface MERGE 14,320, different-surface MERGE 3,758, same-sentence 376, cross-sentence 17,702
- nested same-cluster 43쌍, nested different-cluster 60쌍

Gold와 guideline은 수정하지 않았고 Round04는 재개하지 않았다. pilot_test와 original 1K dev/test는 사용하지 않았다.

## Architecture와 supervision

Entity coreference는 unordered pair task다. frozen EntityMention representation과 deterministic lexical/distance/type/priority evidence를 사용하며, symmetric pair adapter가 `pair(A,B) == pair(B,A)`를 보장한다. pair score는 threshold 0.6으로 MERGE/KEEP를 판정하고, complete-link constrained clustering이 단일 low-confidence bridge로 대형 cluster가 폭발하는 것을 막는다. cluster는 article-local이며 cross-article merge는 허용하지 않는다.

Participant resolution은 directed `(participant, EntityMention)` task다. TIER1을 기본 universe로 쓰고, exact/containment/partial boundary overlap이 있는 TIER2만 bounded rescue한다. selected policy는 upstream-recoverable Gold target의 `99.94%`를 포함하면서 pair 수를 all-raw 503,932개에서 111,566개로 줄였다. Entity type은 hard gate가 아니며 raw participant는 해소 여부와 무관하게 유지한다.

## Training과 selection

- split: 기존 pilot_train120 article split 재사용, train 96 / internal validation 24 / seed 1008
- Entity coreference: fresh initialization, selected epoch 8, threshold-independent internal MERGE PR-AUC 우선, threshold 0.6
- Participant resolver: fresh initialization, selected epoch 8, internal PR-AUC 우선, threshold 0.3
- release-purpose: pilot_train120 전체에서 두 head를 fresh epoch 8 학습; validation reselection이나 pilot_dev feedback 없음
- Entity coreference release SHA256: `29e47da8976d2b315b310bde4731b3c8b6bb2088bec2e13ef131072277f089d9`
- Participant resolution release SHA256: `03be6024245e6c00164912fe011612385e9f1a91c3c3597b5ae5205b8c17c44e`

## Runtime과 graph replay

- runtime config ID: `eventframe_runtime_candidate_v3_entity_identity_participant_resolution_freeze`
- graph assembly config ID: `eventframe_partial_kg_assembly_v2_entity_identity`
- pilot_dev raw EntityMention 3,102 = TIER1 646 + TIER2 2,456; frozen pre-stage-⑥ output과 exact parity
- LocalEntity 472 = singleton 92 + multi-mention 380
- role edge 122 = ACTOR 75 + TARGET 36 + PLACE 11
- unresolved predicted participant 41개는 raw evidence로 남고 Entity edge를 생성하지 않음
- Event, Statement, Trigger, StatementType, B2, EntityMention, priority, TimeExpression, Event-Time attachment exact parity: `true`

Full predicted Entity identity의 pilot_dev upstream-recovered Gold-pair 기준 P/R/F1은 `0.99852 / 0.36946 / 0.53935`다. 이는 oracle-like pair-head reference보다 보수적인 end-to-end materialization 결과이며, raw evidence는 삭제하지 않는다.

## 성능

39개 internal-validation+pilot_dev 기사에서 stage ⑥ 평균 latency는 `0.10564 s/article`였다: span encoding `0.00782`, entity coreference `0.05137`, clustering `0.01379`, participant resolution `0.03265`. Entity pair candidates/article는 mean 7,169, median 2,371, p90 20,719, max 47,953이며, all-same-type upper bound 대비 `62.89%` 감소했다. Participant pair candidates/article는 mean 765, median 227, p90 1,642, max 6,917이다. peak RSS는 1,681,035,264 bytes, GPU peak memory는 2,104,626,176 bytes였다.

## Verification

- task-specific: 6/6 PASS
- canonical `tests/` suite: 291 tests, 0 failures/errors, 2 skipped
- release-only smoke: PASS, isolated bundle 58 files, checkpoint SHA/load/inference/serialization 검증
- broad repository discovery: 303 tests 중 이번 변경과 무관한 historical experiment error 1개. `v3_participant_fair_v2`가 ignored `compiled_supervision.pt`를 요구하지만 현재 checkout에 없어서 발생한다. 해당 cache-like artifact를 조작하거나 force-add하지 않았다.

상세 수치와 per-item diagnostics는 이 directory의 JSON artifact를 source of truth로 한다.

## 보호 상태

```text
CURATED_GOLD_MODIFIED=false
GUIDELINE_MODIFIED=false
ROUND04_RESUMED=false
BACKBONE_MODIFIED=false
ENTITY_MENTION_MODIFIED=false
ENTITY_CANDIDATE_PRIORITIZATION_MODIFIED=false
TIME_EXPRESSION_MODIFIED=false
B2_MODIFIED=false
EVENT_COREFERENCE_EXECUTED=false
ASSERTOR_TRAINING_EXECUTED=false
ABOUT_TRAINING_EXECUTED=false
CAUSES_TRAINING_EXECUTED=false
SUBEVENT_TRAINING_EXECUTED=false
GLOBAL_ENTITY_LINKING_EXECUTED=false
HF_REMOTE_PUSH_EXECUTED=false
NOTION_MODIFIED=false
PILOT_TEST_USED=false
ORIGINAL_1K_DEV_TEST_USED=false
```
