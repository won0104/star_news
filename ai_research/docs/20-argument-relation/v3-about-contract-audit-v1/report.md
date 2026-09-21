# V3 Statement ABOUT Contract Audit v1

## 결과 요약 — 계약 미결정

최종 Round 01 Trigger backfill + Round 02/03, **150 articles / 2362 Statements /
2503 ABOUT endpoints**를 감사했다. Event 20 + Entity 14 = 기존 structurally representable 34건,
SPAN은 **2469건(98.6%)**이다. 어떤 endpoint도 변경하거나 새 Gold link로 resolve하지 않았다.

현재 Statement→Event/Entity 계약이 전체 의미를 충분히 표현한다고 입증되지 않았다. 반대로 모든
SPAN이 새 node를 필요로 한다는 결론도 내리지 않는다. SPAN에는 기존 object 후보뿐 아니라 주장 내용,
절, 개념/주제, 정책·사물이 섞여 있다. exact Event/Entity match는 15건이고 focused diagnostic에서
13건의 기존 target 후보를 지지했다. 이것은 전수 semantic resolution 성공률이나 확정 학습 label이 아니다.

## 1. 실제 endpoint와 기존 수치의 정합성

| endpoint 종류 | 수 |
|---|---:|
| Event resolved | 20 |
| Entity resolved | 14 |
| SPAN | 2469 |
| explicit unresolved kind/status | 0 |
| 기타 schema kind | 0 |

현재 schema의 ABOUT kind enum은 EVENT/ENTITY/SPAN뿐이며 `resolution_status`도 없다. 그러므로
explicit unresolved=0은 ‘미해결이 없다’는 뜻이 아니다. SPAN 전체를 UNRESOLVED로 재분류하지도 않았다.
원래 decision.ambiguity flag=12건은 별도다. ABOUT decision 자체에는
decision_status field가 없고 source Statement provenance의 HUMAN_REVIEW_REQUIRED가 연결된 endpoint는
0건이다. 빈 ABOUT 배열은 0개다.

기존 adapter는 원문 58개 endpoint를 source Statement의
표현 제약으로 projection 전에 제외한다. 따라서 기존 adapter의 unrepresentable ABOUT
2411건과 raw SPAN 2469건은 같은 분모가 아니다.
원래 1K split은 모두 train이며 pilot 내부 성능평가나 test tuning은 하지 않았다.

## 2. SPAN 의미 형태 전수 diagnostic

| primary diagnostic form | 수 |
|---|---:|
| EVENT_LIKE_OCCURRENCE | 13 |
| ENTITY_LIKE_REFERENT | 9 |
| PROPOSITION_STATEMENT_LIKE | 992 |
| TOPIC_CONCEPT_LIKE | 97 |
| POLICY_PRODUCT_OBJECT_LIKE | 37 |
| CLAUSE | 666 |
| AMBIGUOUS | 655 |

전수 2469건은 제한된 lexical cue와 기존 Gold boundary 대조로 분류했고, strong 후보 16건만
AI가 원문·source Statement·EventFrame/Entity/cluster를 비교했다. 모든 분류는 diagnostic-only다.
primary는 합계용 우선순위이며 clause/form, modal cue, topic/object cue는 중복 flag로 보존한다.
event-like라는 이름이 실제 occurrence임을 보증하지 않고, entity-like 일반 NP가 네 Entity type에
속한다는 뜻도 아니다. AMBIGUOUS에는 규칙 미포착이 포함된다. confidence 점수를 임의 생성하지 않았다.
구체적으로 규칙 미포착 652건과 집중 검토에서 범위/identity를 보류한
3건을 구분한다. 전수 semantic form을 확정한 것이 아니며, 이 형태별 수치는 검증된 ontology 분포가 아니다.

| diagnostic form의 운영상 의미 | 범위 |
|---|---|
| EVENT_LIKE_OCCURRENCE | exact 기존 Event 또는 사건 명사 표면. 명사 cue만으로 actuality를 확정하지 않음 |
| ENTITY_LIKE_REFERENT | exact 기존 Entity/whole-surface 또는 소수 지시 NP. generic NP를 Entity로 승격하지 않음 |
| PROPOSITION_STATEMENT_LIKE | 기존 Statement와 exact인 내용, 명사화 절, modal cue가 있는 명제 |
| TOPIC_CONCEPT_LIKE | 추상적 주제·가능성·목표 등 명사 head proxy |
| POLICY_PRODUCT_OBJECT_LIKE | 정책·계획·제품·사물 head proxy. 실제 PRODUCT type 여부와 별개 |
| CLAUSE | 서술어/연결어미 표면이 있지만 위의 proposition proxy에 먼저 해당하지 않은 절 |
| AMBIGUOUS | 검색 규칙 미포착 또는 집중 검토의 scope/identity 보류. 자연적 의미 모호성 비율로 해석 금지 |

예를 들어 ‘조기 기상 습관이 오히려 건강을 해칠 수 있다’는 가능성 내용이고, ‘대규모 투자 계획’은
계획 object 표현이다. ‘핵산치료제 영역으로 확장될 가능성’처럼 topic과 proposition 성격이 겹치는
표현도 있다. 이 구분을 EVENT/Entity target으로 강제하는 새 ontology 규칙은 만들지 않았다.

자기 source Statement와 ABOUT이 exact인 412건,
어느 Statement와든 exact인 415건을 따로 기록했다.
이를 Statement→Statement hard edge나 self-edge로 자동 바꾸지 않았다.

## 3. 기존 object resolution의 근거와 한계

| 측정 기준 — 서로 중복 가능 | SPAN evidence 수 |
|---|---:|
| exact_event | 7 |
| exact_entity | 8 |
| exact_event_or_entity | 15 |
| unique_exact_cluster_candidate | 15 |
| contained_event_overlap_excluding_exact | 102 |
| contained_entity_overlap_excluding_exact | 587 |
| same_sentence_semantic_event | 356 |
| same_article_entity_whole_surface | 9 |
| any_statement_exact | 415 |
| own_statement_exact | 412 |
| no_exact_compatible_object | 2454 |
| no_compatible_object_by_tested_search | 1607 |
| clear_existing_cluster_candidate_focused_diagnostic_only | 13 |

exact match는 processed code-point offset으로 비교했다. contained overlap은 ‘ABOUT이 object 안에’와
‘object가 ABOUT 안에’를 구분한다. same sentence는 ABOUT evidence 문장 기준이며 source Statement
문장 기준도 별도로 저장했다. 같은 article에 Entity가 있다는 것 자체는 resolution 근거가 아니므로
같은 whole surface mention을 별도 측정했다. 거리·포함관계·이름 일치만으로 target을 선택하지 않는다.

`no_compatible_object_by_tested_search`는 exact/overlap/same-sentence Event/whole-surface Entity 검색이
근거를 찾지 못한 경우다. 담화 추론으로도 절대 resolve 불가능하다는 판정이 아니다. 반대로 같은 문장의
발표/발언 Event를 주장 내용의 ABOUT으로 대체하면 occurrence와 proposition을 혼동할 수 있다.

### exact/whole-surface strong 후보 16건 집중 검토

기존 cluster 후보를 지지한 13건, 범위/identity 검토 보류 3건이다. 원래 endpoint는 모두 SPAN으로
유지했다. 15 exact + 1 same-surface remote candidate 전체를 대상으로 했으며 weak overlap의 다른
후보들은 전수 adjudication하지 않았다. 원문 전체는 case JSON article_contexts에서 확인 가능하다.

- `r01-wa-c3a2-ab001` “네팔 홍수는 빙하 녹은 물이 원인”: **SCOPE_AMBIGUOUS** — Event는 Trigger ‘홍수’로 occurrence를 식별하지만 ABOUT은 ‘빙하 녹은 물이 원인’이라는 인과 명제 전체다. exact boundary만으로 occurrence로 축소하지 않는다.
- `r01r-3ef127eb-ab-038-01` “관련 제약사들에서 유전자 검사 등의 유관 검사를 지원하고 있다”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 제약사의 유관 검사 지원이라는 동일 진행 행위가 원문과 기존 EventFrame에 명시된다. 인용 source의 Statement와 지원 Event를 구분한 후보 연결이 가능해 보인다.
- `gaced7472-ab-013-02` “47억 원 횡령 사건”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 방송에서 다룰 대상으로 명시된 ‘47억 원 횡령 사건’과 기존 nominal Event가 동일하다. 미래 방송 자체를 발생 Event로 만들지 않는다.
- `gaced7472-ab-013-03` “청소년들 사이에서 확산 중인 ‘픽시 자전거’ 문제”: **SCOPE_AMBIGUOUS** — ABOUT은 픽시 자전거 ‘문제’라는 주제이고 기존 Event는 ‘확산 중인’을 anchor로 삼는다. 확산 occurrence와 문제 topic의 범위가 같은지 보류한다.
- `R02B-d817ca32f5-AB0008` “경북 동해안”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 여행 후 인상적이었다는 평가가 정확한 LOCATION mention ‘경북 동해안’을 가리키며 해당 기존 cluster가 하나다.
- `R02C-A39-AB003` “지난 29일 진행된 티켓 예매”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — ‘전쟁’을 방불케 했다는 평가는 지난 29일의 티켓 예매 occurrence를 대상으로 한다. 기존 첫 티켓 오픈/예매 MERGE cluster가 있다.
- `R02C-A39-AB020` “최재림의 합류”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 히든카드라는 평가는 출연 확정에 해당하는 최재림의 합류를 겨냥한다. 향후 공연과 구분되는 기존 합류 Event 후보가 있다.
- `R02C-A44-AB001` “맘다니”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 뉴욕시장이라는 서술의 맘다니와 동일 위치 PERSON mention 및 조란 맘다니 cluster가 대응한다.
- `R02C-A44-AB005` “맘다니 시장”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 이스라엘 외무부가 비난한 ‘맘다니 시장’이 동일 문장의 PERSON mention과 기존 cluster에 대응한다.
- `adj-76a91404-st-added-06-about-01` “황재균”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 최강창민의 평가 대상 황재균이 exact PERSON mention으로 존재한다. 평가 명제를 Event로 materialize할 필요가 없다.
- `r03-94b87153-about-008` “지구”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 과학 설명의 지구는 exact LOCATION mention과 기존 지구 cluster를 가리킨다. 보편 설명을 독립 occurrence로 바꾸지 않는다.
- `r03-94b87153-about-015` “다누리”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 달 탐사용 우주선이라는 설명은 exact PRODUCT mention 다누리와 기존 cluster를 가리킨다.
- `r03-8c0800f1b784-st-003-about-01` “경찰이 신속히 도착해 용의자를 연행했다”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 경찰의 용의자 연행은 주변의 체포 영상 서술 및 기존 체포/연행 Event MERGE cluster와 대응한다.
- `r03-0469c93d-about-001` “음뵈모”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 공격진 업그레이드라는 평가의 음뵈모와 exact PERSON mention 및 브라이언 음뵈모 cluster가 대응한다.
- `r03-bccc1535-about-010` “Su-57”: **IDENTITY_GRANULARITY_AMBIGUOUS** — Su-57 surface와 기존 PRODUCT cluster는 있으나 해당 문장은 추락한 기체를, 다른 mention은 기종을 설명한다. model/type와 개별 기체 identity를 문자열만으로 확정하지 않는다.
- `r03-bccc1535-about-012` “Su-57 전투기”: **SUPPORTED_EXISTING_TARGET_CANDIDATE** — 세계 최강이라는 평가는 일반 기종 설명의 exact PRODUCT mention Su-57 전투기를 겨냥한다. 기존 Su-57 cluster 후보가 있다.

## 4. 기존 34건과 SPAN의 차이

직접 연결 34건의 source Statement 유형/round/article 집중도와 target 정보는 endpoint_distribution.json
comparison 및 resolved_endpoints에 있다. source Statement char width 평균은 직접 연결
38.2, SPAN 연결
57.9다. SPAN endpoint width 평균은
31.8다. 직접 Entity endpoint는 cluster를
가리키므로 임의로 하나의 mention width를 골라 SPAN 길이와 동등 비교하지 않았다.

| 비교 | 직접 Event/Entity 연결 | SPAN |
|---|---:|---:|
| endpoint 수 | 34 | 2469 |
| 포함 article 수 | 15 | 147 |
| Round 01 / 02 / 03 | 8 / 26 / 0 | 886 / 981 / 602 |
| source CLAIM / EVALUATION / FORECAST | 9 / 22 / 3 | 630 / 1101 / 738 |

34건의 예로 실제 회의에 대한 평가→기존 회의 Event, ‘재력에 비해 검소하다’→손흥민 Entity가 있다.
반면 SPAN에는 같은 종류의 Entity ‘맘다니’도, 미래·가능성 내용 전체도 존재한다.
직접 연결의 round/article 집중은 표현 방식이 혼재할 가능성을 시사하지만, 이것만으로 annotation
방식 차이가 원인이라고 확정하거나 Round 03의 object ABOUT이 의미적으로 없다고 결론낼 수 없다.

34건은 explicit event_id/entity_id로 target identity가 기록돼 있고 원문과 reference parity를 통과한다.
SPAN은 semantic content가 알려져 있어도 object resolution 지위가 기록되지 않는다. annotation mode의
차이이므로 34건이 ‘쉬운 의미’이고 나머지가 ‘어려운 의미’라는 성능 판단으로 해석하지 않는다.

## 5. NONE negative가 안전하지 않은 이유

guideline은 ABOUT을 proposition/entity/phenomenon/state로 정의하고 절 전체도 허용한다. 유효 Statement의
의미 대상과 annotation workflow를 설명하지만, **각 Statement의 허용 target universe를 모두 검토했다는
machine-readable ABOUT completeness 계약은 없다**. articleCoverage.hard_relations=REVIEWED의
hardRelation schema는 CAUSES/SUBEVENT_OF이며 이를 ABOUT pair의 closed-world 검토로 전용할 수 없다.

`ABOUT=UNRESOLVED`라는 guideline 문구와 이를 담을 kind/status field가 없는 schema의 차이를 발견했다.
이는 이번 audit의 contract gap이며 schema/Gold를 수정하지 않았다. PRESENT 역할이 있어도 모든 다른
후보가 negative인 것은 아니며, SPAN이 resolve되면 현재 NONE 후보가 positive가 될 수 있다.

실제 기존 `conservative_v3_pair_supervision`을 projected Statement×Event/Entity cluster proxy universe에
호출했다. 명시 positive 34개와 positive link가 없는 후보
73738개가 모두 mask되어 0개만 남았다.
이 NONE은 builder의 provisional default일 뿐 확정 negative가 아니다. 34 positive도 막는 것은 현재
pilot의 보수적 task-level 정책이지 negative 부족이 개별 confirmed positive의 의미를 무효화한다는 뜻이 아니다.

safe negative를 위한 **제안 조건**(미구현):

1. ABOUT 의미 granularity와 허용 target kind, mention/cluster 단위, article/sentence scope를 먼저 고정한다.
2. Statement별 exhaustive target 검토 상태 또는 명시 pair-negative와 근거·guideline version을 기록한다.
3. pending SPAN/UNKNOWN/HUMAN_REVIEW 범위가 해당 pair의 positive 가능성을 남기면 mask한다.
4. alias/coreference 및 Event occurrence 동일성으로 유효 target을 확장한 뒤 후보를 비교한다.
5. candidate 검출 실패·token alignment 실패·ontology 밖 target·기존 link 없음은 negative 증거로 사용하지 않는다.
6. universe/정책 변경 시 과거 negative의 적용 범위를 재검증한다. 이번에 이러한 새 field나 label은 만들지 않았다.

## 6. 코드 연결과 네 contract 후보

정답 투영(v3 adapter)은 34개 관계를 coverage에 보존하지만 감독 필터는 전부 제외한다. runtime 후보 구성은
STATEMENT×EVENT/ENTITY이며 EVIDENCE/SPAN/STATEMENT target은 eligibility·label mask·hard graph validator가
허용하지 않는다. oracle은 cluster proxy, runtime은 predicted mention을 사용하므로 같은 평가 단위라고
가정하면 안 된다. 현재 pilot은 StatementAboutHead를 disabled하고 graph로 materialize하지 않는다.
기존 함수의 endpoint probe로 이 허용/차단을 확인했고 Head forward·학습·추론은 실행하지 않았다.

네 후보의 semantic fidelity/annotation cost/model complexity/ontology/runtime 요구 비교는
[options.md](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/results/v3-about-contract-audit-v1/options.md)에 있다. A/B/C/D 어느 안도 선택하지 않았다.

## 근거와 재현

- gold_about_endpoint: [ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:448](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:448)
- statement_no_about_completeness: [ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:492](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:492)
- article_coverage_scope: [ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:357](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:357)
- hard_relations_only_event_pairs: [ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:544](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/data/gold/schema/articlelocal-kg-construction-gold-v3.0.schema.json:544)
- meaning_contract: [ArticleLocal-KG/docs/GNews-1K-Construction-Gold-v3.0-Annotation-Guideline.md:333](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/docs/GNews-1K-Construction-Gold-v3.0-Annotation-Guideline.md:333)
- guideline_unresolved_without_schema_slot: [ArticleLocal-KG/docs/GNews-1K-Construction-Gold-v3.0-Annotation-Guideline.md:338](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/docs/GNews-1K-Construction-Gold-v3.0-Annotation-Guideline.md:338)
- entity_ontology_excludes_topics: [ArticleLocal-KG/docs/GNews-1K-Construction-Gold-v3.0-Annotation-Guideline.md:630](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/docs/GNews-1K-Construction-Gold-v3.0-Annotation-Guideline.md:630)
- projection_retains_34: [ArticleLocal-KG-DeBERTa/training/data/v3_pilot_adapter.py:603](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/v3_pilot_adapter.py:603)
- pair_positive_and_negative_mask: [ArticleLocal-KG-DeBERTa/training/data/v3_pilot_adapter.py:244](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/v3_pilot_adapter.py:244)
- default_none_before_filter: [ArticleLocal-KG-DeBERTa/training/data/candidate_builder.py:337](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/candidate_builder.py:337)
- oracle_cluster_proxy_universe: [ArticleLocal-KG-DeBERTa/training/data/candidate_builder.py:459](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/candidate_builder.py:459)
- runtime_mention_universe: [ArticleLocal-KG-DeBERTa/training/data/runtime_candidates.py:252](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/runtime_candidates.py:252)
- hard_endpoint_policy: [ArticleLocal-KG-DeBERTa/models/policies/constraints.py:14](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/policies/constraints.py:14)
- candidate_eligibility: [ArticleLocal-KG-DeBERTa/models/policies/eligibility.py:51](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/policies/eligibility.py:51)
- current_head_disabled: [ArticleLocal-KG-DeBERTa/training/scripts/run_v3_round01_03_pilot.py:91](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/scripts/run_v3_round01_03_pilot.py:91)

```bash
cd ArticleLocal-KG-DeBERTa
conda run --no-capture-output -n model-test-py312 python training/scripts/run_v3_about_contract_audit.py
conda run --no-capture-output -n model-test-py312 python -m unittest tests.test_v3_about_contract_audit -v
```

필수 5개 산출물 외 validation.json, test_results.json, audit_manifest.json도 저장한다. runner는 감사용
테스트 9개와 기존 policy 테스트 4개를 실행한다. 모델용 synthetic data는 생성하지
않았고 Gold/processed/기존 checkpoint/config/기존 audit 파일을 보호했다. Round 04·학습·commit/push는 없다.
GOLD_MODIFIED=false / CONTRACT_DECIDED=false / HEAD_TRAINED=false / PRODUCTION_MODIFIED=false.
완료 후 추가 annotation이나 실험을 자동으로 시작하지 않는다.
