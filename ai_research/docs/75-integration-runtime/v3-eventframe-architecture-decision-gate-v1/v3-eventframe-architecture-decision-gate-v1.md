# V3 EventFrame Architecture Decision Gate v1

## 1. 판정: 의미 중심의 전환 근거와 실행 교체 승인을 구별한다

**EVENTFRAME_CENTERED_ARCHITECTURE_PROMISING_BUT_NOT_READY**

EventFrame을 semantic source of truth와 conceptual architecture의 중심으로 설명할 근거는 충분하다. 그러나 제안된 전체 topology가 predicted proposition부터 최종 KG까지 실행·검증됐다는 근거는 부족하다. 따라서 **설계 문서의 목표 방향으로 제안하되, production 기본 구조로 승격·교체하지 않는다.** `PROMISING_BUT_NOT_READY`는 semantic contract를 다시 미결정으로 돌리는 판정이 아니다.

| 결정 층위 | 이 gate의 판단 | 승인하지 않는 해석 |
| --- | --- | --- |
| 개념적 중심 | Event/Statement proposition과 raw semantic filler 중심을 지지 | 모든 task를 하나의 Event vector/Head에 압축 |
| Participant topology | B2를 우선 runtime 검증 후보로 볼 실측 근거 있음 | A2 전면 폐기, B2가 모든 role/subset에서 우월 |
| 통합 runtime | 미준비: proposition, contextual evidence, Time, ABOUT, resolution/materialization 연결이 남음 | Gold-Event 조건부 F1을 end-to-end KG 성능으로 사용 |
| Production migration | 보류; 기존 5-way ArgumentHead와 checkpoint 유지 | 코드 삭제·default 변경·기존 checkpoint의 의미 재해석 |
| Notion migration | 이 문서의 계획만 제안 | Notion 반영 완료 또는 사용자 채택 승인 |

CURRENT_ARCHITECTURE_RETAIN은 현 배포 보호 조치이지 장기적인 Entity-first 의미 계약을 지지하는 최종 판정이 아니다. MIXED_HYBRID_RECOMMENDED도 선택하지 않는다. 병렬 Entity/Time resolution lane은 필요한 책임 분리지만, A2/B2 ensemble이나 role별 혼합 runtime은 실험하지 않았다.

## 2. 증거의 기준시점·범위·신뢰 경계

기준 commit: `aaaf2885653b584108e915e06da788b7da4503ea`. 기존 미추적 v1/v2 실험 코드와 curated RC는 보존했다. 산출물은 기존 model-project convention에 따라 `ArticleLocal-KG-DeBERTa/docs/`와 `training/results/` 아래 이번 이름으로만 생성한다. 새 실행 실험은 없다.

| 입력 | 실제 범위와 상태 | 이번 판단에서의 용도 |
| --- | --- | --- |
| [Curated RC / guideline][S1], [RC report][S2] | 150 articles; Event 2,374 / Statement 2,387 / Entity mention 4,817 / Time mention 865. `CURATED_RC_WITH_REVIEW_QUEUE` | 현재 의미 계약과 Gold representation의 우선 근거 |
| [Safe supervision][S3] | `READY_FOR_FAIR_AB`; 기존 pilot train120/dev15; explicit mask | exact-evidence positive/negative/UNKNOWN의 공통 범위 |
| [Fair comparison v2][S4] | 같은 Gold Event, train120/dev15; A2/B2 실제 학습·평가 | Participant 조건부 learnability·계산량 근거 |
| [Semantic boundary][S5] | parent r01 + 기존 selected checkpoint, train/dev 진단 | 앞단 proposition 병목의 역사적 근거; RC 재평가 수치 아님 |
| [Time audit][S6] | parent 150개, generic mention865/attachment1004 | subtype의 실제 downstream 의존성과 파생 정보 경계 |
| [기존 ABOUT][S7], [proposition][S8], [Entity][S9] | parent snapshot의 진단 | RC 이전 문제의 설명. 현재 의미·건수는 RC를 우선 |
| [Event–Trigger][S10] | parent + 고정 checkpoint, pilot_dev15 | extraction과 attachment를 분리하는 보조 증거 |

RC release manifest 22개, safe manifest 7개, fair-v2 manifest 32개의 기록 SHA를 현재 파일과 대조해 모두 일치했다. `summary.json`에 읽은 증거/코드 54개 경로와 SHA, manifest 검사 결과를 남긴다. 이는 과거 semantic review나 학습을 다시 실행한 검증이 아니다.

- Curated Gold SHA: `0e4d1fa7f1dc0969fb8d8208c67cdd07b037f68b7acef71afd3d02af4ea80002`
- Guideline `v3-guideline-r02-curated-rc1` SHA: `a3c3012750b27b0ab3946a0156e43012e1b95204787deb73f50e4fbbab5030a1`
- Supervision view SHA: `31865f61c123bcd939eef7adbfa3ca3dc4a53ba0c74882e566fcb2c94e7bc5ee`

RC는 AI-curated이며 사람 검수 완료가 아니다. curation queue 1,445건과 명시 HRR 9건은 다른 집계다. 전체 proposition 재annotation도 아니며 targeted55 밖의 의심과 Assertor UNRESOLVED998개가 남는다. 원래 1K의 train150에 대해 수행된 과거 annotation audit가 pilot_test 소속 article을 포함했던 사실과, 이번에 test 예측·지표로 구조를 선택하는 것은 구별한다. **이번에는 저장된 train/dev 지표와 annotation 감사 결과만 종합하며, pilot_test 성능 파일·예측·새 평가를 사용하지 않는다.** [S2] [S3]

## 3. 여섯 책임을 섞지 않는다

| 층위 | 정의 및 현재 근거 | 남은 간극 / FIRST LOSS | Gate 판단 |
| --- | --- | --- | --- |
| SEMANTIC_CONTRACT | 실제 Event / 비실현 Statement, 충분한 Trigger anchor, agent ACTOR, patient/object/theme/phenomenon TARGET, spatial PLACE, generic Time, proposition-directed ABOUT | HRR와 completeness를 확정 truth/negative로 승격하면 의미 손실 | RC 계약 지지; 새 ontology 제안 없음 |
| GOLD_REPRESENTATION | proposition과 외부 evidence 분리, raw role span+resolution, status+coverage, ABOUT EVENT/STATEMENT endpoint | 현재 splitter/토큰 경계가 일부 span을 못 담음. 모든 role·관계가 exhaustive는 아님 | 원본 보존, 명시 mask/lineage 필요 |
| MODEL_TOPOLOGY | A2 joint span binary vs B2 factorized endpoint binary; 기존 Presence/Semantic/Entity/Time 등 독립 task | B2 TARGET endpoint recall, A2 classifier/PLACE collapse. ABOUT·generic Time 통합 미학습 | 부분 증거만 있음; 단일 전역 bottleneck 채택 근거 아님 |
| RUNTIME_CANDIDATE | 실제 원문에서 생성되는 후보의 집합; 허용 kind enum과 다름 | production builder가 EVIDENCE/TYPED_LITERAL을 생성하지 않음. proposition boundary에서 이미 큰 누락 | Participant discovery의 Entity 종속 제거 방향 지지 |
| RESOLUTION | textual role/mention을 article-local identity·TimeExpression·antecedent로 연결 | non-Entity, pronoun/contextual evidence, nested identity, Assertor998 unresolved | 병렬/후행 책임; discovery 실패로 치환 금지 |
| GRAPH_MATERIALIZATION | mention evidence·cluster identity·검증된 edge를 일관된 graph로 직렬화 | current ABOUT endpoint 제한, raw filler 보존 경로, TIME/OCCURRED_ON 의미, 미학습 Head 출력 차단 | RC-compatible end-to-end 경로 미검증 |

현재 코드의 핵심 흐름은 `forward_from_backbone → 독립 extraction → DecodedCandidateBuilder → _construction/pair → graph assembly`다. Presence는 span mask로 쓰이지 않는다. 이미 `EventFeatureBundle`에 proposition/Trigger/role별/context 표현을 갖고 있으므로 CURRENT가 EventFrame을 전혀 모르는 구조라고 묘사하면 틀리다. 차이는 **Participant를 먼저 어디서 발견하고 무엇에 의존시키는가**다. [C1] [C2] [C6]

## 4. 비교할 conceptual flow

CURRENT / CANDIDATE-FIRST의 검증된 기준 흐름:

```text
Article → shared representation
        → Entity / Time / Trigger / Event·Statement extraction
        → decoded candidate universe → pair classification
        → EventFeatureBundle → coreference / relation → KG assembly
```

PROPOSED / EVENTFRAME-CENTERED의 목표 책임 흐름(전체 미구현):

```text
Article → shared representation + article context
  ├─ sentence EVENT/STATEMENT presence ── soft prior only ─┐
  ├─ local Event / Statement proposition extraction ◀─────┘
  │    ├─ Event → primary Trigger identification + attachment
  │    │         → Event-conditioned ACTOR / TARGET / PLACE raw spans
  │    │         → Event ↔ textual TimeExpression attachment
  │    └─ Statement → Type / textual Assertor
  │                  → ABOUT → another Event or Statement
  ├─ parallel Entity mention / identity-resolution lane
  └─ parallel generic TimeExpression lane
            ↓ evidence-based resolution / conservative contextual references
       article-local Entity/Event coreference + CAUSES/SUBEVENT_OF
            ↓ mention-to-cluster lifting + source evidence preservation
       validated EventFrame / KG materialization
       + unresolved/unmaterializable evidence retained separately
```

화살표는 semantic responsibility와 dependency이지 모든 모듈을 직렬 재계산하라는 scheduler 설계가 아니다. Time span은 attachment 전에 병렬로 추출할 수 있고 Entity resolution도 discovery와 병행할 수 있다. “for each Event: Trigger”는 Trigger를 Event-conditioned 새 Head로 학습하라는 결정이 아니다. 기존 전역 Trigger 추출+귀속도 이 책임을 수행할 수 있다.

### 질문별 계약 판단

1. **Entity는 EventFrame의 선행조건인가?** 아니다. Entity 검출 실패와 Event/role 부재는 다르다. Entity/Time lane은 discovery와 병렬이며 identity 해소는 후행·상호참조할 수 있다. 현재 semantic extraction 자체는 Entity를 기다리지 않지만, production ACTOR/PLACE 후보에는 Entity coupling이 남는다. [C1] [C2] [C3]
2. **Participant discovery는 Entity candidate에 종속돼야 하는가?** 아니다. A2도 Entity 없이 generic span으로 동작했고 B2도 raw span을 냈다. B2만이 유일한 탈결합 방법이라는 증거는 없다. unresolved resolution 때문에 확정 role span을 삭제하거나 fake Entity로 바꾸지 않는다. [S1] [S4]
3. **Sentence Presence는 hard gate인가?** 아니다. 현재 코드도 two-bit 결과로 Semantic 입력을 가리지 않는다. 제안 구조에서도 낮은 Presence가 proposition 탐색을 영구 차단하면 안 된다. 현재 soft score fusion/우선순위 scheduler가 이미 연결됐다고 주장하지 않는다. 선택적으로 prior로 사용할 연결은 별도 검증 대상이다. [C1]
4. **MIX는 proposition label인가?** 아니다. 문장 안 EVENT bit=1, STATEMENT bit=1의 동시 존재 상태다. proposition label은 EVENT/STATEMENT이며 독립 복수 proposition과 적법한 overlap을 보존한다. MIX 전용 proposition node/5-way 통합 Head를 만들지 않는다. [C4]
5. **Proposition local / context global이 유지되는가?** 유지한다. local은 model splitter가 정한 한 segment와 동의어가 아니다. 외부 participant/Assertor evidence를 읽되 proposition 자체에 합치거나 local evidence를 복제하지 않는다. DocumentContextEncoder의 기사 문맥 사용이 모든 cross-sentence span/antecedent 출력을 해결했다는 뜻은 아니다. [S1] [S3]
6. **generic Time이 단순화하는가?** neural semantic 계약은 단순해진다. subtype annotation을 필수로 하지 않아도 Event↔TimeExpression은 정의된다. 그러나 normalization/precision/interval/recurrence 책임은 사라지지 않으며 production TimeBIO는 아직 typed다. [S6] [C4]
7. **ABOUT 축소가 Statement branch를 명확히 하는가?** topic/entity/content와 다른 proposition에 대한 논평 관계를 분리한다는 점에서 그렇다. 여기서 ‘축소’는 허용 의미 범위의 축소이지 target capacity 감소가 아니다. Statement target 추가로 현재 candidate/validator와 새 불일치가 생겼다. [S1] [C2] [C3]
8. **Event-conditioned v2는 실제 근거인가?** 공통 mask·Gold Event 아래 semantic role span learnability와 비용의 근거다. 모든 role, context resolution, predicted Event, 전체 KG의 우월성 근거는 아니다. [S4]
9. **현재 5-way Head를 즉시 제거할 것인가?** 아니다. production와 historical/reference로 유지한다. A2/B2 실험 모듈은 별도 경로이고 서로 checkpoint를 혼합하거나 5-way를 3-binary로 이름만 바꿔 로드하지 않는다. 이후 제거 여부는 명시 migration 승인과 end-to-end 회귀 검증 뒤의 별도 결정이다.

## 5. 핵심 증거와 반증 가능성

### 5.1 Participant: 의미 계약은 맞췄지만 topology의 모든 차이를 제거하지는 못했다

Safe view의 `EXHAUSTIVE`는 선언한 **exact evidence extraction 범위**에서 complete positive set과 local nonmatch negative를 허용한다. semantic PRESENT지만 context-only인 경우 local positive는0이며 safe local negative가 가능하다. PARTIAL은 known positive만, UNRESOLVED/HRR/alignment 보류는 기존 mask를 따른다. UNKNOWN output은 FP가 아니다. 이 permission을 ABOUT/coreference negative로 전파하지 않는다. [S3]

양쪽 shared initialization SHA는 `9bd4b09c5d08bb06a3476e5015f1791cf9319a95586525d59ba4f30bf51d24fc`로 같다. 동일6기사 tiny120 step, main 최대8epoch/patience2/seed1008/plain BCE, 공통 article→Event→role reduction이다. A2는4epoch 중2, B2는8epoch 중7을 선택했다. 동일 stopping rule이지 실제 optimizer step 수가 같은 실험은 아니다. 공통 모듈 초기화는 같지만 B2가 reinjected token path를 추가로 사용하고 A2는 기존 span encoder의 raw-token pooling+sentence context를 사용한다. 따라서 성능 차이를 topology만의 완전히 통제된 인과 효과로 부르지 않는다. [S4]

| Role | Raw local listed / active | A2 TP/FP/FN | A2 P/R/F1 | B2 TP/FP/FN | B2 P/R/F1 |
| --- | --- | --- | --- | --- | --- |
| ACTOR | 143 / 133 | 41/49/92 | .456/.308/.368 | 70/23/63 | .753/.526/.619 |
| TARGET | 323 / 296 | 77/448/219 | .147/.260/.188 | 50/76/246 | .397/.169/.237 |
| PLACE | 50 / 49 | 0/0/49 | .000/.000/.000 | 17/25/32 | .405/.347/.374 |

macro-F1: A2 **.1851**, B2 **.4100**. FP는 confirmed-negative에 한정한다. 별도 UNKNOWN output은 A2 110 / B2 21이다. raw local 516개 중 active478개를 평가했으며 나머지38개를 성능 분모에서 조용히 삭제한 raw-Gold F1이 아니다. context-only와 미정렬 Event도 별도 unsupported 범위다. 이 dev15는 checkpoint 선택과 여러 진단에 반복 사용된 내부 split이며 독립 generalization benchmark가 아니다.

- 양쪽 tiny는 세 role 모두 학습 신호가 있다. A2 PLACE tiny F1 .565인데 main은 train/dev 모두 출력0이다. main 실패를 표현 불가능이라고 단정하지 않는다.
- B2는 SPAN_ONLY에서 더 높은 recall을 보였다. 그러나 Entity-resolved TARGET은 A2 .539 / B2 .118, 같은 문장 Event 밖 TARGET은 .375 / .042, 복수 TARGET은 .327 / .136으로 A2가 앞선다.
- 같은 span multi-role은 양쪽 모두 표현한다. active local train22/dev4 pair만으로 효과를 일반화하지 않으며 dev에서 완전한 multi-role 성공은 관측되지 않았다.
- B2 TARGET start/end recall .280/.405, paired recall .169. false span76개 중 두 endpoint가 각기 Gold인 cross-pair는5개다. fixed operating point에서 endpoint 손실이 크지만 ranking/calibration을 분리하는 sweep은 이 v2에서 하지 않았다.
- Safe audit의 허용 universe에는 **519개** non-Gold pair가 각각 positive endpoint를 공유한다. A는 이를 span negative로 배울 수 있지만 B의 독립 endpoint objective는 pair 자체의 부정을 직접 표현하지 못한다. 같은 semantic negative 계약과 같은 supervision 정보량은 다르다.
- 현재 scope로 v1 saved predictions를 재집계한 safe FP는 A 119,672→497, B 54,002→124. 큰 감소를 보였지만 parent→RC·후보·objective 변경이 함께 있어 EXHAUSTIVE 하나의 순수 효과로 단정할 수 없다. [S3] [S4]

### 5.2 계산량: B2를 우선 검토할 실측 근거

| 같은15 dev / CPU4 threads | A2 | B2 |
| --- | --- | --- |
| Trainable parameters | 3,272,035 | 2,981,326 |
| 실제 후보 / valid binary decisions | 185,463 spans / 556,389 cells | 55,440 endpoint cells; padded logits208,896 |
| Forward+decode | 4.882s | 0.198s |
| Peak process RSS | 1,441.4 MiB | 1,355.3 MiB |

B2는 **약24.7배 빠른 cache 이후 구간**을 보였다. backbone online forward, resolution, 전체 KG 조립을 포함한 latency가 아니다. RSS는 dataset/cache/model을 포함한다. A2 width49는 train positive 최대 폭이며 active train/dev candidate coverage100%, 폭 손실0이다. 실제 train forward는 epoch당1,354,287 candidates, dev는 전체185,463개였다. A2는 후보 폭증 비용과 classifier miss를 따로 가진다. B2는 logits O(Event×N)이지만 endpoint가 폭증하면 Cartesian decode는 O(Event×N²)가 될 수 있다. [S4]

### 5.3 Proposition discovery: EventFrame 중심에서도 사라지지 않는 최우선 runtime 병목

기존 Semantic diagnostic의 parent strict dev Gold407개 중352개가 boundary threshold에서 먼저 탈락했다. Cartesian recall은 threshold .5에서 .118, .05에서 .740, top8×8에서 .892였다. 가장 강한 진단은 `THRESHOLD_CALIBRATION_FAILURE`지만, top1×1 recall .295와 verifier/fusion/conflict 잔여 손실도 있다. .05에서 proposal/article은11.467→349로30.4배 증가했고 final F1은 .157→.323이었다. 이 값으로 production threshold를 고르지 않는다. [S5]

Gold exact proposal verifier F1 .833과 확대된 predicted proposal의 verifier 성능은 다른 모집단이다. .05 순수 conditional verifier precision .064가 보여주듯 경계만 넓히면 충분하지 않다. 이 진단은 **curated RC 이후 재측정이 아니며**, B2가 이 병목을 해결했다는 근거도 아니다. 옛 Semantic recall과 새 Participant recall을 곱해 가상의 end-to-end 점수를 만들지 않는다.

### 5.4 Proposition/Entity 재검토: 오래된 진단 숫자를 현재 정답처럼 사용하지 않는다

| 주제 | Parent diagnostic | 최신 RC 재검토 | 판정 영향 |
| --- | --- | --- | --- |
| 지정 cross-sentence55 | B13/C22/D19/E1, true cross0 | local+context16 / merged19 / segmentation18 / true cross1 / ambiguous1 | ‘실제 cross0%’는 현재 결론이 아님 |
| Proposition 수정 | 권고만 존재 | Event6 same-ID 수정; Statement13 수정+16 parent를41개로 split; HRR2 보존 | local proposition 계약은 반영됐지만 현재 splitter 완전 호환은 아님 |
| Entity 의심17쌍 | artifact 의심16+ambiguous1 | artifact6 / valid distinct4 / same-identity nesting3 / ambiguous4 | nested 전체 삭제가 아니라 확정 artifact만 수정 |

RC의 true cross1/55=1.8%는 targeted packet 내 확정 분류이며 HRR로 보존됐다. ambiguous까지 고려한 미결정 범위는 별도로 남는다. **1.8%가 새 long-context neural architecture가 반드시 필요한 비율이라는 뜻은 아니다.** 문장 재구성·입력 범위·보류 등 대안을 검증하지 않았다. 150개 전체 또는 다음 round의 모집단 비율로 외삽하지 않는다. Safe train/dev에는 Event NO_SINGLE_MODEL_SENTENCE가11/1개, train non-exact token Event가15개 남는다. [S2] [S3] [S8]

기존 Entity audit의 nested109쌍/flat 최소손실104 mention/실제 BIO mask201 mention은 parent snapshot 수치다. 그때 mask된 mention과 직접 연결된 role/assertor103개 중102개, MERGE pair973개는 oracle tensor에 남았다. 이를 이미 발생한 runtime edge loss로 세면 안 된다. RC는 mention6개만 제거해4,817개이며 **RC 전체 overlap/BIO mask 손실은 이번에 재계산하지 않았다**. CandidateSpanEncoder가 nested rows를 받는 것과 flat extraction이 둘 다 찾는 것은 다른 문제다. discovery를 Entity와 분리하면 role 손실 전파를 줄일 수 있지만 identity/coref 문제까지 제거되지는 않는다. [S2] [S9]

### 5.5 Time·Statement·Trigger·graph: 개념 정합성과 실행 미연결

**Time:** 865 mention/1004 attachment는 RC에서도 보존됐다. 기존 audit에서 subtype만 바꾼 고정경계 candidate tensor 불변성865/865를 확인했으며 DeBERTa attachment feature에4-way subtype을 요구하는 근거는 없다. 다만 독립 LQ-FSE/GLiner의 typed consumer는 존재한다. generic extraction은 normalization 전체 삭제가 아니다. production taxonomy는 아직 DATE/TIME/DURATION/SET이고 기존 v3 pilot은 Time extraction을 mask/disable했다. RC TIME coverage는 EXHAUSTIVE1501/PARTIAL80/UNRESOLVED793, 보존 범위 밖 attachment 의심 row837개가 남아 ‘Time이 해결됐다’고 할 수 없다. [S2] [S6] [C4]

**ABOUT:** old broad2503 endpoint 중 SPAN2469/structurally representable34는 과거다. RC는 모든2387 Statement를 재검토해 새 ABOUT779개(EVENT495 / STATEMENT284), NONE1640/PRESENT650/UNRESOLVED97이다. legacy self-content1862개 제거 판정 등을 새 link와1:1 migration 수로 섞지 않는다. 현재 runtime builder·eligibility·graph endpoint table은 여전히 Statement→Event/Entity다. 새 Statement target284개는 kind 단계에서 막히고 Entity topic은 RC에서 금지되므로 단순 loader 변경으로 연결되지 않는다. ABOUT negative는 `NOT_AUTHORIZED`; NONE1640개를 pair negative로 쓸 수 없다. [S1] [S2] [S7] [C2] [C3]

**Assertor:** semantic source는 textual participant일 수 있다. 현재 runtime은 Statement×Entity candidate만 만든다. RC Assertor UNRESOLVED998개는 Entity-independent Participant 결과만으로 해소되지 않는다. Statement Type/Assertor/ABOUT은 서로 다른 책임이며 Type 예측 성공으로 attribution/reference를 자동 승인하지 않는다. [S2] [C2]

**Trigger:** minimal semantically sufficient anchor와 Event→Trigger 귀속은 별개다. parent dev GE+GT264/272 정답, GE+PT108, PE+GT20, PE+PT9였다. 완전 예측에서 현재 후보만의 완벽 선택 상한은13TP다. nearest-end 대안은13에 도달했지만 다른 조건에서 회귀도 있었다. learned attachment가 필요하다는 증거는 아직 부족하다. proposition/Trigger 후보 recall 개선 후 잔여 선택 오류를 다시 분리하는 것이 우선이다. [S10]

**Graph:** 현재 assembler는 Entity/Event cluster와 evidence offset을 다루지만 generic raw Participant를 final node로 받는 계약은 없다. EVIDENCE를 fake Entity로 바꾸지 않고 EventFrame filler/evidence와 미materialized prediction을 보존하는 경계가 필요하다. 이는 구현 완료 사실이 아니라 **별도 serialization 결정/검증 항목**이다. TIME→OCCURRED_ON 생성은 현 동작일 뿐 모든 duration/set을 사건 발생시각으로 바꿔도 된다는 의미 승인이 아니다. ABOUT EVENT/STATEMENT kind·self-link, coref 이후 reference, CAUSES/SUBEVENT_OF의 endpoint/cycle를 함께 검증해야 한다. RESPONDS_TO 복원·Story/PART_OF 확장은 하지 않는다. [C3] [C5]

## 6. 다음 승격 gate — 실행 계획이 아니라 승인 전 체크리스트

숫자 하나로 PASS를 만들지 않는다. 아래 필요조건과 평가 범위를 먼저 고정하고, 허용 오차·성능 기준은 후속 실험 승인 시 사전 명시해야 한다. 이 문서가 새 threshold·topology·학습을 승인하지 않는다.

| 우선 | Gate / 왜 먼저인가 | 필요한 증거 | 현 상태 |
| --- | --- | --- | --- |
| P0 | G1 RC/negative→task 계약 | 동일 SHA view, HRR/UNRESOLVED/alignment mask, exact/identity 구별, multi-role | Participant local subset은 충족. ABOUT/Time 등에는 확장 불가 |
| P1 | G2 proposition/Trigger 후보와 attachment | curated 기준 raw/eligible/tensor/runtime 분모, Presence 비삭제, boundary/fusion/conflict 분리 | parent 진단만 있음; RC runtime 미검증 |
| P1 | G3 predicted-Event Participant | 기존 Gold-Event 결과와 분리된 role evidence TP/FP/FN, UNKNOWN, contextual unsupported, SOURCE ID 정렬 | 미실행; B2 우선 후보지만 A2 TARGET 참고 유지 |
| P1 | G4 RC-compatible graph boundary | raw unresolved filler 보존, EVENT/STATEMENT ABOUT, TIME evidence와 파생 occurredAt 구별, 미학습 출력 차단 | 현 production endpoint/DTO와 gap |
| P2 | G5 Entity/Time/Assertor resolution lane | nested 정확 경계와 identity, contextual antecedent 경쟁, Time completeness mask, Assertor ambiguity | 부분/미검증 |
| P2 | G6 Statement/관계 감독과 평가 | ABOUT completeness/negative 승인, Type/Assertor/reference 별도 평가, coref pair/cluster 및 hard relation 범위 | ABOUT negative 미승인; RC full-graph 지표 없음 |
| Final | G7 end-to-end 회귀·migration | 단일 fixed configuration의 Gold-free article→graph, 비용·실패·raw missing support, 기존 호환성 | 미충족; production 교체 보류 |

순위 근거: G2는 모든 downstream frame을 잃게 하는 선행 병목이고, G4는 맞는 예측도 의미를 바꿔 저장할 위험이 있다. G3에는 이미 조건부 learnability/계산량 근거가 있다. Entity nested 문제는 role discovery에서 탈결합할 수 있으나 resolution lane에서는 남는다. ABOUT은 새 positive779개가 있으므로 과거34개만 보고 low-support hold라 부르지 않는다. 대신 negative/endpoint 계약이 직접 blocker다.

Gold annotation의 의미와 모델 gap은 분리한다. generic Time·narrow ABOUT·local proposition/coverage는 RC에 반영된 계약이다. 모델을 B2로 바꾸기 위해 Gold를 다시 단순화할 필요는 없다. 반대로 RC review queue, TIME 범위 밖 보정, ABOUT negative는 별도 권한/결정이 필요하다. **Round04는 이 gate와 무관하게 사용자 재개 승인 전까지 중지 상태다.**

## 7. Notion migration plan — 내용 변경안만, 실행0

Notion live page/section/block ID는 이번에 읽지 않았다. 아래 ①~⑧은 로컬 [기준 감사의 ‘8개 책임별 구현 위치’][C7]에서 확인한 명칭이다. **현재 Notion에 똑같은 heading이 존재한다고 주장하지 않는다.** 실행 전에 대상 페이지의 최신 본문을 read-only로 대조하고, 위치가 다르면 section mapping과 diff를 사용자에게 다시 제시해야 한다. 여기서는 바꿀 책임·제안 제목·정확한 핵심 문구를 고정한다.

| 논리적 변경 대상 → 제안 섹션 제목 | 제안할 구체적 변경 / 삽입 문구 | 유지할 것 / 채택 전 경계 |
| --- | --- | --- |
| 상단 개요 → `Architecture status: current implementation vs EventFrame target` | CURRENT와 PROPOSED 흐름을 나란히 두고 “개념 방향은 EventFrame 중심을 지지하나 전체 runtime 승격은 PROMISING_BUT_NOT_READY” 삽입 | 현재 구현도를 삭제하지 않고 날짜·commit·checkpoint 범위를 유지 |
| 의미 계약 → `EventFrame / Statement semantic source of truth` | “한 node는 독립 proposition. Trigger는 minimal semantically sufficient anchor. ACTOR/TARGET/PLACE는 Entity와 독립된 textual role. TARGET은 patient/object/theme/phenomenon.” | parent r01은 역사 문서로 남기고 curated RC/guideline SHA 링크. HUMAN 승격 금지 |
| ① 공통 표현부 → `공통 표현과 병렬 resolution lane` | “shared representation에서 Event/Statement discovery와 Entity/Time lane이 병렬 분기한다. EventFrame은 semantic 중심이지 모든 task를 한 벡터로 압축하는 강제 bottleneck이 아니다.” | frozen revision·task representation·독립 coreference branch 유지; 새 encoder 승인 없음 |
| ② 문장 판정부 → `EVENT/STATEMENT presence: non-destructive routing` | “EVENT와 STATEMENT는 독립 존재 bit. MIX=[1,1]의 문장 상태이며 proposition label이 아니다. Presence는 extraction hard deletion gate가 아니다.” | auxiliary state와 현재 비삭제 구현을 보존. 새 soft-prior fusion은 미구현이라고 표시 |
| ③ 구간 추출부 → `Local proposition / Trigger / raw Participant / Entity / TimeExpression` | “proposition의 local 핵심과 global context evidence를 분리한다. Event별 raw Participant extraction은 B2 후보, Entity/Time은 병렬 lane. Trigger extraction과 attachment는 별도 책임.” | B2는 EXPERIMENT_ONLY; splitter artifact와 true-cross/HRR 예외 보존. Time subtype Head 교체 완료라고 쓰지 않음 |
| ④ 속성 판정부 → `Statement Type와 파생 Time 정보의 경계` | “Statement Type은 FORECAST/CLAIM/EVALUATION. Time subtype·normalized value는 generic textual truth와 별개인 optional derived data.” | Assertor를 Type에 흡수하지 않음. normalization/precision/interval은 neural truth로 되돌리지 않음 |
| ⑤ 방향 관계 판정부 → `EventFrame attachment와 proposition reference` | “ACTOR/TARGET/PLACE는 independent multi-role raw span; TIME은 Event→TimeExpression. ASSERTED_BY는 발화 주체, ABOUT은 다른 Event/Statement 직접 참조. CAUSES/SUBEVENT_OF는 Event↔Event.” | 현재5-way는 PRODUCTION_LEGACY_REFERENCE로 보존. ABOUT NONE을 negative로 만들지 않음. Statement endpoint 연결은 TODO/gate |
| ⑥ 동일성 판정부 → `Article-local resolution / Entity·Event coreference` | “Participant discovery 후 identity를 해소하며 unresolved evidence는 보존한다. 같은 occurrence MERGE와 구성 관계 SUBEVENT_OF를 구별한다.” | candidate ontology로 raw filler 삭제 금지. Event/Entity 독립 branch, valid nesting, 보수적 antecedent 유지 |
| ⑦ 후보 제한부 → `Task-specific candidate scope, completeness and coverage` | “공통 모든-Entity 후보 pool을 semantic 선행조건으로 삼지 않는다. exact positive/safe negative/UNKNOWN, structural eligibility, sampling, runtime pruning을 분리한다.” | width/cap/truncation별 raw denominator 공개. A2 full candidate vs B2 boundary/cross-pair 차이, Presence hard gate 금지. mask를 runtime feature로 전달 금지 |
| ⑧ 그래프 조립부 → `Evidence-preserving EventFrame → article-local KG` | “raw filler·해소 상태와 canonical edge를 분리한다. 미materialized evidence를 보존하고 fake Entity fallback은 금지한다. ABOUT target은 EVENT/STATEMENT, TIME normalization은 파생 정보다.” | 이 문구는 목표 계약. 실제 DTO/validator migration은 별도 승인. 미학습 Head edge·RESPONDS_TO·새 Story/PART_OF 금지 |
| 검증/실험 부록 → `Promotion gates and conditional evidence` | 본 문서 §5의 A2/B2 표, denominator, 24.7×의 측정 범위, §6 G1~G7 및 source SHA를 삽입 | old oracle A0를 별도 historical 표로 유지; 서로 다른 snapshot의 지표 혼합 금지 |

제안 실행 순서(미실행): **대상 페이지/section read-only 식별 → 기존 본문 snapshot 및 사용자 확인용 diff → semantic contract/상태 문구 → ①~⑧ 책임·미연결 표시 → 실험 근거/한계/gate 링크 → 문서 교차 참조 검증**. 페이지 이동·삭제·archiving·DB schema 변경은 계획에 포함하지 않는다. 기존 현재 구현 설명은 역사/현재 상태로 보존하고 proposed와 명확히 분리한다.

사용자에게 남길 결정은 “이 목표 구조를 Notion의 proposed conceptual architecture로 기록할 것인가”와 “다음 G2/G3/G4 중 어떤 범위를 승인할 것인가”다. 본 문서는 그 결정을 대신 실행하거나 생산 설정 채택을 선언하지 않는다.

## 8. 검증·산출물·종료 상태

이번 검증은 입력 manifest SHA 대조, 문서·JSON 구조/수치 일치, 링크 존재, source SHA 전후 불변, Git tracked diff 확인이다. 과거 보고서의 unit test/학습 결과는 인용했을 뿐 이번에 학습·추론·tokenization·semantic 재검토를 실행하지 않았다. machine-readable source inventory와 gate·migration 항목은 [summary.json][OUT]에 있다.

```text
DECISION=EVENTFRAME_CENTERED_ARCHITECTURE_PROMISING_BUT_NOT_READY
SEMANTIC_EVENTFRAME_DIRECTION_SUPPORTED=true
FULL_RUNTIME_PROMOTION_APPROVED=false
NEW_TRAINING_EXECUTED=false
NEW_MODEL_INFERENCE_EXECUTED=false
GOLD_GUIDELINE_ABOUT_MODIFIED=false
PRODUCTION_MODIFIED=false
NOTION_READ=false
NOTION_MODIFIED=false
ROUND04_RESUMED=false
PILOT_TEST_METRICS_OR_PREDICTIONS_USED=false
COMMIT_PUSH=false
```

문서와 machine-readable 요약만 생성하고 종료한다. 후속 학습·Gold 생성·Notion 반영은 자동으로 시작하지 않는다.

[S1]: ../../ArticleLocal-KG/data/gold/v3_work/round01-03-curated-rc1/guideline_rc.md
[S2]: ../../ArticleLocal-KG/data/gold/v3_work/round01-03-curated-rc1/report.md
[S3]: ../training/results/v3-participant-safe-supervision-contract-v1/report.md
[S4]: ../training/results/v3-participant-architecture-fair-comparison-v2/report.md
[S5]: ../training/results/v3-semantic-boundary-diagnostic-v1/report.md
[S6]: ../training/results/v3-time-contract-audit-v1/report.md
[S7]: ../training/results/v3-about-contract-audit-v1/report.md
[S8]: ../training/results/v3-cross-sentence-audit-v1/report.md
[S9]: ../training/results/v3-entity-overlap-audit-v1/report.md
[S10]: ../training/results/v3-trigger-attachment-diagnostic-v1/report.md
[C1]: ../models/model.py#L132
[C2]: ../training/data/runtime_candidates.py#L106
[C3]: ../models/policies/constraints.py#L10
[C4]: ../models/contracts.py#L20
[C5]: ../models/decoding/graph.py#L91
[C6]: 04-Baseline-Architecture-v1.md
[C7]: 07-Baseline-Unblock-v1-Audit.md#L72
[OUT]: ../training/results/v3-eventframe-architecture-decision-gate-v1/summary.json
