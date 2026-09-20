# 20. Argument ACTOR Gold Coverage & Generation Audit v1

- `ACTOR_GOLD_COVERAGE_STATUS = STRONGLY_UNDER_ANNOTATED`
- `ACTOR_PRIMARY_ATTRITION_STAGE = ARGUMENT_LINK_GENERATION`
- `ACTOR_TENSORIZATION_LOSS = PRESENT`
- `GOLD_MODIFIED = false`
- `GOLD_REGENERATED = false`
- `TRAINING_EXECUTED = false`
- `DIAGNOSTIC_ONLY_NOT_GOLD = true`
- Primary scope: train 800 articles, split seed 41
- Gold v2.2 SHA-256: `428cec4ce1b92ca310a802882f50d1fc9687bd2bccfddfeb22944b136e0a086d`
- Processed SHA-256: `d25a6e8d0c73e31c931832d211b1c094f57a6de16ecdb81bceb4c413f4304767`
- Dev/test semantic review 및 metric evaluation 없음
- `test_enabled = false`, `test_tensorized = false`, `test_evaluation_count = 0`, `test_used_for_selection = false`

## 1. 핵심 Event-level coverage

| Metric | Count | Ratio |
|---|---|---|
| Total Event | 6870 | 1.000000 |
| Events with ACTOR | 111 | 0.016157 |
| Events with TARGET | 518 | 0.075400 |
| Events with ACTOR+TARGET | 87 | 0.012664 |
| ACTOR only | 24 | 0.003493 |
| TARGET only | 431 | 0.062737 |
| Neither | 6328 | 0.921106 |

Positive links total=1796; multiple-ACTOR Events=6; multiple-TARGET Events=259.

## 2. ACTOR/TARGET target-kind 분해

| Role | LOCAL_ENTITY | EVIDENCE_SPAN | TYPED_LITERAL | TIME_EXPRESSION | Total |
|---|---|---|---|---|---|
| ACTOR | 117 | 0 | 0 | 0 | 117 |
| TARGET | 17 | 871 | 4 | 0 | 892 |
| PLACE | 7 | 0 | 0 | 0 | 7 |
| TIME | 0 | 0 | 0 | 780 | 780 |

ACTOR_LOCAL_ENTITY:TARGET_LOCAL_ENTITY = 117:17 (ratio=6.882353).

TARGET 중 non-LOCAL_ENTITY는 875개 (98.094%)다. 따라서 tensorized ACTOR 115 대 TARGET 884는 동일 target universe 비교가 아니다.

## 3. ACTOR generation funnel

| ACTOR funnel stage | Event count | Previous-stage retention | Total-event ratio |
|---|---|---|---|
| F0_TOTAL_EVENT | 6870 | 1.000000 | 1.000000 |
| F1_ENTITY_CANDIDATE_EXISTS | 2488 | 0.362154 | 0.362154 |
| F2_RESOLVABLE_LOCAL_ENTITY_TARGET_EXISTS | 2488 | 1.000000 | 0.362154 |
| F3_LOCAL_ENTITY_IN_ARGUMENT_TARGET_POOL | 2488 | 1.000000 | 0.362154 |
| F4_ACTOR_LINKED | 111 | 0.044614 | 0.016157 |

F2 means an Event entity_candidate_id resolves through entity_clusters to an existing LOCAL_ENTITY ArgumentTarget. F3 requires that resolved target_id to be present in the Event argument_target_ids pool. The materializer normally creates F2/F3 together.

## 4. Gold lineage

`ARGUMENT_GOLD_LINEAGE = gnews-1k-v1.0 -> complete_gnews_1k_gold.py -> Gold v2.0; AutoGold v2.1 is independently regenerated and comparison-only for v2.2; build_gnews_1k_gold_v2_2.py deep-copies v2.0, applies bounded Event/Statement repairs, cascade-removes links owned by deleted Events, and does not regenerate arguments for newly created Events`

v2.2의 직접 parent는 v2.0이다. AutoGold v2.1은 v2.2 decision manifest에서 이전 판단 비교용으로만 사용되며, v2.2 graph의 Argument source가 아니다. v2.2는 v2.0 graph를 deep-copy한 뒤 semantic repair를 적용한다. 삭제 Event의 ArgumentLink는 cascade 삭제하지만 새 Event의 argument pool/link를 재생성하지 않는다.

Train diff: Event +47/-67, ArgumentLink +0/-25; 새 Event 47개 중 empty argument pool=47개. 삭제 link role={"ACTOR": 4, "TARGET": 14, "TIME": 7}.

## 5. Generator rule audit

코드에서 확인된 ACTOR 조건:

1. Target kind must be LOCAL_ENTITY
2. No PERSON/ORGANIZATION-only whitelist is applied; any resolved LOCAL_ENTITY type can be selected
3. Entity detection and local entity resolution must have succeeded
4. The EntityMention evidence must be fully inside the Event semantic span
5. Predicate must match the small PASSIVE_ACTION, AGENTIVE_ACTION, or VALUE_SETTING regex classes
6. PASSIVE_ACTION: only an entity followed by 에 의해/의하여 becomes ACTOR
7. AGENTIVE_ACTION/VALUE_SETTING: subject particle 이/가, supported coordinated subject, or a guarded topic 은/는 becomes ACTOR
8. Omitted subjects, pronouns/common nouns not detected as Entity, and contextual actors are not inferred

코드에서 확인된 TARGET 조건:

1. LOCAL_ENTITY target: supported active object 을/를, passive patient subject/topic, or guarded topicalized object
2. EVIDENCE_SPAN target: non-entity object regex inside supported agentive/passive/value-setting Event
3. TYPED_LITERAL target: percent literal for VALUE_SETTING Event
4. TARGET therefore has a wider allowed target-kind universe than ACTOR

특히 Event candidate pool은 같은 sentence Entity를 받지만 실제 linker는 Event semantic span 내부 Entity만 검토한다. 이전 sentence, 생략 주어, Entity로 검출되지 않은 대명사/일반명사 actor는 지원하지 않는다.

검증한 실행 지점: `complete_gnews_1k_gold.py:460,545,807,1092,1368`, `event_candidates.py:150`, `entity_argument_construction.py:153`, `argument_linking.py:229-267,279,547-608,721-744`, `build_gnews_1k_gold_v2_2.py:727,852,1719`.

## 6. ACTOR missing structural taxonomy

| Missing reason | Structural count | Semantic sample estimate |
|---|---|---|
| A_NO_ENTITY_CANDIDATE | 4382 | reviewed=100 |
| B_ENTITY_CANDIDATE_WITHOUT_LOCAL_TARGET | 0 | reviewed=0 |
| C_LOCAL_TARGET_NOT_IN_ARGUMENT_POOL | 0 | reviewed=0 |
| D_LOCAL_TARGET_POOL_WITHOUT_ACTOR_LINK | 2377 | reviewed=100 |
| E_OTHER | 0 | reviewed=0 |

Semantic sample cause estimate (raw sample count와 structural-stratum post-stratified population estimate를 함께 표시):

| Cause | Sample count | Post-stratified estimated Events | Post-stratified share |
|---|---|---|---|
| AMBIGUOUS | 7 | 227 | 0.033517 |
| ARGUMENT_LINK_RULE_MISS | 19 | 452 | 0.066819 |
| CONTEXT_INHERITANCE_NOT_SUPPORTED | 13 | 469 | 0.069450 |
| ENTITY_DETECTION_MISS | 40 | 1252 | 0.185168 |
| SEMANTIC_SPAN_BOUNDARY_EFFECT | 25 | 1015 | 0.150215 |
| TRUE_NO_EXPLICIT_ACTOR | 96 | 3345 | 0.494832 |

| Missing reason | Structural count / proxy | Semantic sample estimate |
|---|---|---|
| TRUE_NO_EXPLICIT_ACTOR | N/A (semantic-only) | 3345 |
| ENTITY_DETECTION_MISS | A_NO_ENTITY_CANDIDATE=4382 | 1252 |
| ENTITY_TO_ARGUMENT_TARGET_MISS | B+C=0 | 0 |
| ARGUMENT_LINK_RULE_MISS | D_LOCAL_TARGET_POOL_WITHOUT_ACTOR_LINK=2377 | 452 |
| CONTEXT_INHERITANCE_NOT_SUPPORTED | PREVIOUS_SENTENCE_ENTITY=948 | 469 |
| SEMANTIC_SPAN_BOUNDARY_EFFECT | SAME_SENTENCE_OUTSIDE_ENTITY=267 | 1015 |
| OTHER / AMBIGUOUS | N/A (semantic-only) | 227 |

## 7. Entity upstream 연결

ACTOR 없는 Event의 exclusive context 분포: `{"INSIDE_EVENT_SPAN": 2135, "NO_ENTITY_IN_EVENT_OR_PREVIOUS_SENTENCE": 3409, "PREVIOUS_SENTENCE": 948, "SAME_SENTENCE_AFTER_OUTSIDE_SPAN": 54, "SAME_SENTENCE_BEFORE_OUTSIDE_SPAN": 213}`.

Context별 Entity type 분포: `{"INSIDE_EVENT_SPAN": {"LOCATION": 1589, "ORGANIZATION": 1009, "PERSON": 590, "PRODUCT": 34}, "NO_ENTITY_IN_EVENT_OR_PREVIOUS_SENTENCE": {}, "PREVIOUS_SENTENCE": {"LOCATION": 662, "ORGANIZATION": 422, "PERSON": 228, "PRODUCT": 13}, "SAME_SENTENCE_AFTER_OUTSIDE_SPAN": {"LOCATION": 19, "ORGANIZATION": 25, "PERSON": 23, "PRODUCT": 1}, "SAME_SENTENCE_BEFORE_OUTSIDE_SPAN": {"LOCATION": 138, "ORGANIZATION": 110, "PERSON": 73}}`.

## 8. ACTOR positive pattern

Entity type: `{"LOCATION": 23, "ORGANIZATION": 76, "PERSON": 17, "PRODUCT": 1}`.

Trigger-relative position: `{"BEFORE_TRIGGER": 117}`.

Span relation: `{"SEMANTIC_SPAN_INSIDE": 117}`; same-Event TARGET coexistence: `{"WITHOUT_TARGET": 26, "WITH_TARGET": 91}`; passive-like: `{"NO": 99, "YES": 18}`; reporting/performative-like: `{"NO": 83, "YES": 34}`.

Top actor surfaces: `{"정부": 12, "삼성전자": 11, "이란": 9, "미국": 6, "현대차": 5, "엔비디아": 4, "구글": 4, "현대차그룹": 3, "연준": 3, "SK하이닉스": 3, "오픈AI": 3, "애플": 3, "한국": 2, "백악관": 2, "중국": 2, "질병관리청": 2, "KB국민은행": 2, "시상위원회": 1, "현대자동차그룹": 1, "이재명 대통령": 1}`.

## 9. ACTOR vs TARGET_LOCAL_ENTITY

| Metric | ACTOR | TARGET_LOCAL_ENTITY |
|---|---|---|
| positive links | 117 | 17 |
| source Events | 111 | 15 |
| unique target entities | 101 | 16 |
| PERSON | 17 | 3 |
| ORGANIZATION | 76 | 3 |
| LOCATION | 23 | 10 |
| PRODUCT | 1 | 1 |
| semantic-span-inside | 117 | 17 |
| same-sentence-outside-span | 0 | 0 |
| cross-sentence | 0 | 0 |
| mean candidates/source Event | 3.090090 | 3.133333 |

## 10. Semantic review — train only

Stratified packet=200, reviewed=200, unreviewed=0. 모든 판정은 `DIAGNOSTIC_ONLY_NOT_GOLD=true`이다.

Semantic labels: `{"AMBIGUOUS": 7, "CONTEXTUAL_ACTOR_OUTSIDE_EVENT_SPAN": 38, "EXPLICIT_ACTOR_PRESENT_ENTITY_FOUND": 19, "EXPLICIT_ACTOR_PRESENT_ENTITY_MISSED": 40, "NO_EXPLICIT_ACTOR": 96}`.

Raw balanced-sample explicit rate=0.295000; post-stratified actorless-Event explicit rate=0.251987; post-stratified context 포함 actor-available rate=0.471651; 전체 Event explicit-actor 추정치=0.264073; observed Gold Event ACTOR rate=0.016157.

이 추정치는 Codex 단일 diagnostic 판독이며 annotation이나 새 Gold가 아니다. 사람의 독립 검토와 inter-annotator agreement 없이 절대 prevalence로 확정해서는 안 된다.

## 11. Tensorization audit

ACTOR funnel: Gold 117 → eligible 117 → sampled 117 → tensorized 115.

Positive alignment failures by role: `{"ACTOR": 2, "TARGET": 8, "TIME": 3}`. ACTOR 두 건은 모두 `질병관리청` target span의 exact tokenizer alignment 실패다.

`ACTOR_TENSORIZATION_LOSS = PRESENT`.

다만 117→115의 2건 손실은 전체 Gold 희소성의 주원인이 아니다. 표본을 population ratio로 보정한 pipeline attrition 추정에서 link-rule/context/span-boundary 계열은 1,936 Event, Entity detection은 1,252 Event이며 tensorization loss는 2 positive다. 따라서 primary stage는 Argument link generation으로 판정했다.

## 12. Final verdict

- `ACTOR_GOLD_COVERAGE_STATUS = STRONGLY_UNDER_ANNOTATED`
- `ACTOR_PRIMARY_ATTRITION_STAGE = ARGUMENT_LINK_GENERATION`
- `ACTOR_TARGET_IMBALANCE_EXPLANATION = TARGET 892개 중 LOCAL_ENTITY는 17개이므로 TARGET 전체와 ACTOR를 직접 비교하는 것은 비동종 비교다. LOCAL_ENTITY끼리는 ACTOR 117개 대 TARGET 17개로 격차 방향이 반대다. Generator는 ACTOR를 narrow Entity gazetteer, Event-span 내부 조건, 작은 predicate regex, 제한된 조사 규칙의 교집합에서만 생성하며 context/생략 주어를 지원하지 않는다. stratum-weighted semantic sample의 전체 Event explicit-actor 추정치는 0.264이다. Gold Event-level ACTOR coverage는 0.016이다.`
- `GOLD_MODIFIED = false`
- `GOLD_REGENERATED = false`
- `TRAINING_EXECUTED = false`

### 마지막 질문에 대한 답

현재 train Gold의 ACTOR 117개를 자연스러운 Event 의미 분포라고 단정할 수 없다. Gold Event-level ACTOR coverage는 1.616%이고, 구조 category 비율로 보정한 semantic train sample의 전체 Event explicit-actor 추정치는 26.407%이다. Generator에서 ACTOR는 LOCAL_ENTITY 검출, Event-span 내부 포함, 좁은 predicate class, 조사 기반 role rule을 모두 통과해야 하며 context/생략 주어를 지원하지 않는다. TARGET 892개 중 LOCAL_ENTITY는 17개라 TARGET 전체는 ACTOR와 동종 비교가 아니지만, LOCAL_ENTITY끼리 제한하면 ACTOR 117 vs TARGET 17로 격차의 방향이 오히려 뒤집힌다. 현재 판정은 STRONGLY_UNDER_ANNOTATED/ARGUMENT_LINK_GENERATION이다. Participant Head 후속 실험 전에 Gold를 자동 수정하지 말고, review packet을 사람이 확인한 뒤 ACTOR annotation/generation contract의 보강 또는 재정의를 결정해야 한다.
