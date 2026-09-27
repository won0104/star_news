# V3 본학습 이전 구현 상태

기준 문서: `V3_Pretraining_Codex_Master.md` (`ARTICLELOCAL_V3_PRETRAINING_CODEX_PLAN_V1`). 지시서가 검토한 시작 기준 HEAD는 `d756efb1953619a4a1a9b0e1d01c2f98e23eebbf`다. 상태의 기계 판독 원본은 `execution-state.json`이다.

## 보완 B — GROUNDED_CANONICAL_R2_VERIFIED

16번 이후 표시 계층 보완으로 `v3-grounded-canonical-r2`를 구현했다. exact source evidence와 표시문을 분리하고, 안전한 연결/관형 어미 정리, request-local clause 확장, final EventCluster의 호환 member/role을 이용한 작은 frame 보완을 PUBLIC projection r2에 연결했다. `canonical_provenance`가 grounding과 edit rule을 schema/viewer/Neo4j dry-run까지 전달한다. canonicalizer mode를 바꿔도 identity, relation, Primary, 선택 및 persistence 상태는 유지된다. 본학습 준비/데이터 gate 판정은 바꾸지 않았다. 범위와 검증은 `followup-b-canonical-text.md`에 있다.

## 단계 16 / 16 — V3_CODE_READY_FOR_MAIN_TRAINING, MAIN_TRAINING_DATA_GATE_BLOCKED

15번 완료 HEAD `f320f50e`의 산출물 13개를 byte 비교하고, pinned producer·guideline·schema·source·split·현재 Gold 500개 hash를 확인했다. 15번 실행을 반복하지 않고 `step16-readiness-bundle.json`에 13개 영역별 READY/PROVISIONAL/BLOCKED/OUT_OF_SCOPE matrix, 19 task/20 loss·281 parameter manifest, checkpoint 형식, cross-window optimizer moment 4개, 50기사 runtime·isolated memory·tiny-fit·accumulation 기록을 연결했다. 지시서 상태 lane은 `training-readiness.json`에 구분했다. 격리된 `UNTRAINED_NOT_FOR_PRODUCTION` 진단 package는 새 프로세스에서 158개 project module의 staging 내부 import와 raw 기사→PUBLIC 직렬화를 확인했다. `step16-readiness-report.md`에 최초 7항목/추가 task 추적표, 최종 preflight 순서와 본학습 후 dev 선택→dev calibration→최종 test를 고정했다.

학습 핵심 모듈은 준비되었지만 현재 Gold는 500/1000, 유효 499이고 dev `136.json` quarantine이 남는다. seed-41 split은 최종 승인되지 않았다. `main-train` CLI는 optimizer 생성 전에 차단하며 본학습 config도 동결되지 않았다. 따라서 현재 본학습 실행은 불가하고 Stage13/15 checkpoint의 warm-start·production 사용도 불가하다. PUBLIC persistence, backend UUID/EntityType 매핑, zero-event 저장, service threshold는 별도 gate다. 16번에서 optimizer step·serving 재실행·dev/test tuning·원격 게시·DB write는 없었다.

## 단계 15 / 16 — ENGINEERING_VERIFIED, 전체 Gold gate는 BLOCKED

14.5 이후 Gold-free serving을 engineering50의 train 소속 processed 원문 50기사에 기본 budget으로 실행했다. 모두 backbone/DCE 각 1회, L8/L10/L12·direct gather, generic endpoint request 공유, PUBLIC endpoint 연결성 및 요청 후 tensor weakref 회수를 확인했다. 전체 latency p50/p95/max는 2,627.722/7,921.082/14,236.945ms, source extraction은 1,371.637/4,061.417/5,688.525ms였다. 최장 7,604자/223-window 기사가 가장 느렸고 pair-heavy 기사는 별도 1,038자/18-window 기사였다. 대표 네 기사를 각각 새 프로세스에서 메모리 측정했다. 모든 기사가 provisional 기본 budget에서 partial이라 diagnostic smoke 결과를 품질로 해석하지 않는다.

fit40 후보 4기사로 seed 1008 fresh-init tiny-fit 4 optimizer step을 실행했다. cross-window Gold span이 있는 fit 기사도 넣어 20/20 활성 loss·24/24 gradient owner·281/281 optimizer state를 확인했다. 시작/종료 평균 loss는 모두 finite이고 낮아졌으며 frozen backbone SHA는 불변이다. 같은 fresh 초기화와 고정 8기사에서 physical micro-batch 1, accumulation 1/2/4/8을 기사별 backward로 비교했다. 각 설정이 OOM 없이 통과했고 4~8을 **본학습 후보 범위**로만 제안한다. 상세 수치·isolated memory·checkpoint 정책은 `step15-engineering-report.md`, 기계 판독 결과는 `step15-engineering-summary.json`에 있다. Stage14/14.5 baseline은 변경하지 않았다. dev/test 사용·본학습·production calibration·HF publish·DB write는 없고 dev `136.json` blocker는 유지된다. 16번은 시작하지 않았다.

## 단계 14 / 16 — IMPLEMENTED_DIAGNOSTIC_VERIFIED, 전체 Gold gate는 BLOCKED

Gold-free `V3ServingWorker`와 raw article JSON CLI를 연결했다. pinned KF-DeBERTa selective L8/L10/L12 1회, shared DCE 1회, candidate-local direct gather를 사용해 extraction → Entity/Time → final EventCluster → Assertor/ASSERTED_BY/ABOUT/CAUSES → Primary → canonical text → PUBLIC v3를 한 요청에서 실행한다. Stage 13 smoke checkpoint는 엄격한 startup 검사로만 로드하고 `UNTRAINED_FRESH_WEIGHT_DIAGNOSTIC`/`PERSISTENCE_NOT_READY`를 유지한다. Gold ID, teacher forcing, Gold membership, optimizer, DB writer는 serving request에 없다. 학습된 semantic boundary/validity 및 Trigger/Entity/Time 전용 extraction 점수를 predicted decoder에 연결했다.

Entity mixed member type은 5-type model log probability를 cluster별 결정적으로 집계하여 canonical type을 하나 선택하고, 충돌·member evidence·role endpoint는 유지한다. ACTOR/TARGET과 Assertor를 같은 Entity 후보 경로로 닫고 SPAN_ONLY PLACE/Assertor, unresolved/FY/interval Time, zero-event, 관계 endpoint 선택 필터를 확인했다. shared·Event/Time·Event member·final cluster lease의 마지막 소비자와 예외 cleanup을 검사한다. 세부 producer/consumer DAG와 provisional policy는 `serving-integration-contract.md`에 있다.

실제 로컬 smoke checkpoint의 Gold-free 짧은 fixture에서 final Event·Statement, SPAN_ONLY·Time·zero-event를 검증했다. 별도 대표 측정은 engineering50 train 기사 `GNEWS-78d586610b9d7bc0008f37d79e823c0c`의 **processed 원문 1,102자만** 사용했다(Gold 미사용). 이 입력에서 PUBLIC 13 node/22 edge, EventCluster 3·Statement 3, dangling endpoint 0, raw tensor carrier 0, backbone/DCE 추가 호출 0, capture hook 3개 및 request 후 context 0을 확인했다. 동일 source representation과 direct gather를 instrumentation으로 검증했으며 Primary on/off 모두 backbone/DCE 1회, final Event identity 동일이다. fresh-loaded worker의 PUBLIC 결과가 일치했다. CPU/FP32 4-thread warmup 뒤 3회씩의 중앙값은 Primary on 1,820.098ms, off 1,811.573ms이며, on 경로의 backbone/shared 1,085.272ms·source extraction 712.492ms·Entity 12.509ms·Time 8.614ms·Event identity 2.188ms·relation 0.559ms·Primary 0.841ms·PUBLIC 3.289ms다. 프로세스 high-water RSS는 1,360,543,744 byte였고 model-load 이후 baseline high-water보다 24,494,080 byte 높았다. Python `tracemalloc` 1,059,448 byte는 native PyTorch tensor를 포함하지 않는다. 수치는 `serving-audit-report.json`에 있다. v3 semantic stage의 실행 비용을 기록했으며, 추가 backbone/DCE 또는 global hidden stack 회귀는 관측되지 않았다. 과거 rc2 72기사 수치와 입력·범위가 달라 절대 비교하지 않는다.

신규 10개 포함 관련 v3/harness/PUBLIC/rc2 경로 unittest 85개 통과. rc2 selective capture/dynamic fixture 7개 통과. 전체 rc2 정적 package 스크립트는 5번 구현 때 변경된 `models/context.py`의 역사적 source SHA mapping에서 중단됐다. 현재 수정 파일과 무관한 byte 동일성 검사 실패이며 현 코드의 selective capture/direct gather는 별도로 정적·동적 확인했다. 본학습·tiny-fit·dev/test tuning·production threshold/calibration·HF publish·실제 Neo4j/MySQL write는 0이다. dev `136.json` Gold blocker는 유지되며 15번은 시작하지 않았다.

## 단계 13 / 16 — IMPLEMENTED_SMOKE_VERIFIED, 전체 Gold gate는 BLOCKED

19개 fresh task와 공유 DCE·representation을 하나의 train Gold harness에 연결했다. Frozen pinned backbone은 L8/L10/L12 producer로만 사용하고 task checkpoint는 초기값으로 읽지 않는다. 20개 loss 채널(`entity_mention`의 추가 typing 포함)의 가중치·learning rate·teacher-forced engineering stage를 명시 config로 고정했다. 24개 optimizer owner의 281개 tensor/10,211,761 parameter를 이름·shape·identity로 감사하고 누락·중복을 실패시킨다. `validate-data`가 기본인 안전 CLI, single-step smoke, 엄격한 checkpoint 저장/재로딩, train exposure·parameter manifest, 향후 분리된 metric lane API를 마련했다. 사용법과 범위는 `training-harness-usage.md`에 있다.

최종 검증 run은 기존 train Gold 1기사에서 pinned pretrained KF-DeBERTa로 optimizer 1 step을 수행했다. 구현 수정 중 독립 fresh-init smoke를 총 5회 재실행했으며 각 run은 1 step으로 종료했다. 20개 활성 loss 모두 finite, 24 owner에 gradient, 271개 parameter tensor 변경, frozen backbone 198 tensor의 SHA 불변이었다. 별도 fresh process에서 checkpoint를 `weights_only`/strict로 로드한 뒤 eval loss 20개, Primary scalar 15개, final Event ID와 exact span·pair·Primary target 계약 SHA가 허용 오차 `1e-5` 안에서 같았다. 다른 검증 train 기사에서 Time normalization masked 상태와 마지막 불완전 accumulation group을 확인하고, 2기사 full accumulation도 1 optimizer step으로 검증했다. 구버전·부분·다른 run/config checkpoint 및 optimizer 중복/누락을 거부했다. 단계 1~12 및 rc2 경로 포함 82개 unittest 통과. checkpoint는 Git 제외 로컬 `training/results/v3-pretraining-step13-smoke/smoke.pt`에 있으며 Gold/백본 원본과 split은 수정하지 않았다.

본학습·tiny-fit·dev/test tuning·서비스 threshold 선택·원격 모델 게시·실제 DB write는 0이다. 단계 2 dev `136.json` Gold blocker는 유지된다. 14번은 시작하지 않았다.

## 단계 12 / 16 — IMPLEMENTED_PURE_PROJECTION, 전체 Gold gate는 BLOCKED

`V3ConstructionResult`의 scalar Event/Entity/Statement/Time/Assertor/relation/Primary 결과를 선택 후 `articlelocal-kg-public-v3`로 투영한다. 외부 ID 선택 또는 외부 threshold만 받으며 기본값은 전 proposition이다. 선택된 ACTOR/TARGET/PLACE/ASSERTED_BY가 가리키는 Entity, 선택된 Event의 실제 attachment를 가진 유효 calendar Time만 보존한다. ABOUT/CAUSES의 미선택 endpoint는 부활시키지 않는다. Event/Statement의 `primary_score`와 status/producer를 분리해 전달하며, 학습 완료 score의 최대 Event를 COVERS `isPrimary`로 지정한다. zero-event·fresh/누락 score는 `PERSISTENCE_NOT_READY`다. v3 allowlist validator, JSON schema/pretty serializer, viewer, 별도 package hash mapping, 순수 Neo4j dry-run adapter를 구현했다. 자세한 선택·저장 경계는 `public-v3-projection-contract.md`에 있다.

합성 final-local fixture에서 새 관계 9종, exact evidence, GENERIC 등 Entity type, FORECAST canonical, Time precision, dangling edge 0, schema/viewer/dry-run, 3개·10개 Event quota 부재, Statement-only, SPAN_ONLY PLACE, 미정규화/FY/interval Time, score 누락·미학습을 검증했다. 새 테스트 7개 및 11·10·9·7·기존 v2.2 경로 포함 39개 unittest 통과. 모델 load/본학습/optimizer step/service threshold 선발/실제 DB write는 0이다. 단계 2의 dev `136.json` Gold blocker는 유지된다. 13번은 시작하지 않았다.

## 단계 11 / 16 — IMPLEMENTED_DETERMINISTIC, 전체 Gold gate는 BLOCKED

EventCluster와 Statement의 원문 근거 표시문을 순수 deterministic 규칙으로 구현했다. 완결 source span은 보존하고, 짧은 trigger/미완결 표현은 같은 원문 clause 안에서만 확대한다. Event cluster의 다른 member role을 결합하거나 Statement의 forecast/조건/부정을 factual 문장으로 바꾸지 않는다. 안전하지 않은 경우 fallback/context 부족 상태로 원문 span을 돌려준다. 반환값은 text/status/rule version/used grounding ID/audit이며 원문 evidence offset은 수정하지 않는다. identity merge에는 canonical text를 사용하지 않는다. 규칙과 실패 상태는 `canonical-text-policy.md`에 있다.

검증된 기존 train 400기사의 final EventCluster 3,908개와 Statement 6,164개 모두 출력이 원문 부분문자열이고 evidence offset이 유지됐다. 합성 fixture와 선택된 실제 train Gold에서 수치·부정·연도·forecast·조건·nested quote·원격 role·충돌 cluster·원문 말미·반복 입력을 검사했다. 새 테스트 7개 및 선행 단계 포함 51개 unittest 통과. canonical 학습 target/생성형 호출/optimizer step은 0이다. 전체 Gold intake의 dev `136.json` blocker는 유지되며, 12번은 이 커밋 시점에 시작하지 않았다.

## 단계 10 / 16 — IMPLEMENTED_TARGET_CONNECTED, 전체 Gold gate는 BLOCKED

final EventCluster member gate·unique role summary와 Statement/Assertor adapter를 기존 공통 Primary adapter 및 하나의 scalar scorer에 연결했다. 기사 내 strict ordinal pair의 방향만 pairwise softplus로 학습하고 tie는 무시한다. cross-kind pair를 sampling에 남겨 두 kind의 score를 같은 축에서 비교한다. predicted 경로는 모든 final cluster와 Statement의 raw score를 반환하며 quota/Top-K/service threshold는 없다. relation과 Primary가 final lease를 소비하고 release한 뒤에도 loss의 backward가 성립한다. 세부 설계·논문 차용 범위·owner/비용은 `primary-design-and-paper-adaptation.md`에 있다.

검증된 기존 train 400기사 정적 census: final EventCluster 3,908개, Statement 6,164개, strict pair 103,114개, tie 56,859개, cross-kind strict 44,274개. 전체 registry 19개 task가 fresh 등록되고 parameter 10,211,761개다. `tests.test_v3_primary`의 실제 train Gold/synthetic backbone과 Gold 없는 shared-source predicted fixture에서 loss/gradient, rank-gap 불변, tie·empty·singleton·event-only·statement-only, permutation, 큰 segment 안정성, 공통 score, context interaction, quota 부재를 확인했다. rc2/선행 단계 포함 44개 unittest 통과. 본학습·optimizer step·서비스 threshold 선택·dev/test tuning은 0회다. 11번은 시작하지 않았다.

## 단계 9 / 16 — IMPLEMENTED_TARGET_CONNECTED, 전체 Gold gate는 BLOCKED

Statement-conditioned Assertor exact source/existence/residual head를 fresh 등록하고, resolved source를 6번 동일 Entity union·typing·coreference·resolution 경로에 합쳤다. Gold unresolved source는 SPAN_ONLY로 남고 fake Entity edge를 만들지 않는다. ABOUT은 Statement→final EventCluster, CAUSES는 final EventCluster의 ordered distinct 방향쌍을 각각의 directed head로 평가한다. 학습 음성은 3번 compiler universe의 미기록 eligible pair에서만 재현 가능하게 뽑는다. 예측 실행은 Gold ID 없이 final local ID만 쓴다. 세부 계약과 기존 source-first 실험 실패 기록은 `attribution-relation-contract.md`에 있다.

검증된 기존 train 400기사 정적 census: Assertor source 3,347개, SPAN_ONLY 315개, resolved ASSERTED_BY 3,032개, ABOUT 1,772개, CAUSES 615개. `tests.test_v3_attribution`은 실제 train Gold 네 finite loss/gradient와 predicted source·Entity·local relation path를 확인했다. fresh registry 준비 18개/미구현 Primary 1개, parameter 9,250,330개. 단계별 커밋 `634bf5e6`을 push했다. 실제 pretrained model load·본학습·optimizer step·service threshold selection은 0회다.

## 단계 8 / 16 — IMPLEMENTED_TARGET_CONNECTED, 전체 Gold gate는 BLOCKED

Gold same-event pair를 fresh 대칭 Event head의 CE/gradient에 연결하고, Gold 없는 예측 점수→complete-link→최종 article-local Event ID 경로를 구현했다. 미평가 pair와 unaligned Event는 partial/singleton으로 남고, 외부에서 입증된 strict equivalence witness 입력은 최종 ID를 다시 닫는다. 모든 member의 Trigger·ACTOR/TARGET/PLACE·Time 근거를 `LocalEventState`에 scalar로 보존한다. final cluster의 8채널 sum/count·availability/conflict mask·parameter-free mean reference는 `FinalClusterFeatureLease`가 관계와 Primary 두 소비자가 release할 때까지 보유한다. 자세한 생산자/소비자 수명은 `cluster-representation-contract.md`에 있다.

기존 train 400기사 정적 감사: EventMention 4,422, final cluster 3,908, multi-member 401, same-event positive pair 675. member role 6,656/6,656, Time attachment 2,302/2,302를 최종 identity에 remap했다. `tests.test_v3_event_identity` 8개에서 실제 기존 train Gold 양·음 pair/gradient, Time lease 공유, predicted branch, B3 witness interface, budget partial, all-member facts, zero/unaligned Event, 두 consumer 뒤 tensor release를 검사했다. fresh registry 준비 14개/미구현 5개, parameter 7,726,861개. 실제 pretrained checkpoint, optimizer step, tiny-fit·본학습, ABOUT/CAUSES/Primary, 서비스 threshold는 실행하지 않았다. 단계 2 blocker가 남고 9번은 시작하지 않았다.

## 단계 7 / 16 — IMPLEMENTED_TARGET_CONNECTED, 전체 Gold gate는 BLOCKED

5번 TimeMention exact extraction에 Gold-only value 문자/format loss와 Event×Time directed attachment loss를 연결했다. null value Time도 extraction·attachment truth에 남긴다. 보수적 원문/명시적 timezone anchor 정규화와 내부 FY·동일 granularity interval 보존, 단일 calendar eligibility를 `temporal-contract.md`에 정의했다. Event-Time 표현은 요청 범위 lease에서 마지막 tensor consumer까지 유지하며 미연결 정규화 Time은 PUBLIC 후보로 자동 승격하지 않는다.

기존 train 400기사 정적 검사: Time 3,257개, normalized 1,733개, null 1,524개, Event-Time 양성 2,302개(값 null인 양성 900개). fresh registry는 준비 task 13개, 미구현 6개, parameter 6,995,699개다. `tests.test_v3_time` 5개 통과: 윤년/범위/FY/interval/상대일자/timezone/null/missing anchor, 공유 Time, 미연결 Time, Gold loss·gradient, 예측 pair scoring을 검사했다. 실제 pretrained checkpoint, optimizer step, tiny-fit·본학습, 서비스 threshold 선정, PUBLIC materialization은 수행하지 않았다. 단계 2 blocker는 유지된다.

## 단계 6 / 16 — IMPLEMENTED_TARGET_CONNECTED, 전체 Gold gate는 BLOCKED

5번의 Entity/Participant exact source span을 동일한 article-local Entity 후보 집합으로 합쳤다. NER/ROLE/ASSERTOR origin, 좌표·타입·문맥 충돌, 역할의 확정/예측/SPAN_ONLY 상태를 분리한다. 필수 role 후보를 먼저 예산에 예약하고, 예산 부족은 partial로 남긴다. Gold 없는 bounded scoring은 같은 live backbone/DCE lease에서 5타입 typing·priority·대칭 동일성·방향 역할 해소 head를 사용하고 scalar closure만 돌려준다. Assertor의 실제 추출 producer와 기존 rc2 서비스 연결은 아직 9번/14번 범위다. 세부 계약은 `entity-union-closure-contract.md`에 있다.

검증된 기존 train 400기사의 oracle 구조에서 ACTOR/TARGET endpoint 6,307개 모두 보존했다. Gold cluster 하나에 `PRODUCT`/`ORGANIZATION` mention이 함께 있어도 타입 충돌을 기록하고 local endpoint를 남긴다(해당 endpoint 3개). engineering50의 NER-only/role-only/both 후보는 1,244/1/1,063, ACTOR/TARGET 1,187/1,187, PLACE SPAN_ONLY 52, 낙관적 후보 cap 탈락 0이다. 이는 Gold 주입 구조 검사이며 predicted 품질 수치가 아니다. fresh registry는 준비된 task 11개, 미구현 8개, 6,517,653 parameter다.

검증: `conda run -n model-test-py312 python -m unittest tests.test_v3_entity_union -v` — 13 PASS. 실제 기존 train Gold에서 타입 혼재 endpoint, coreference 양·음 pair와 role loss gradient, Gold 없는 예측 구조, 불확실성/중복/중첩/SPAN_ONLY/예산 부족을 검사했다. 실제 pretrained checkpoint load, optimizer step, tiny-fit·본학습, 서비스 threshold 선정은 0회다. 단계 2의 dev Gold blocker는 유지되고 7번은 시작하지 않았다.

## 단계 5 / 16 — IMPLEMENTED_TARGET_CONNECTED, 전체 Gold gate는 BLOCKED

8개 extraction/attribute task를 fresh registry에서 실제 r05.3 train Gold target/loss/gradient에 연결했다. 기존 proposer, canonical semantic boundary/validity, Trigger, Event-conditioned Participant, nested Entity, generic Time, StatementType 구조를 재사용한다. signed character residual과 cross-window span은 공유 source endpoint·link 경로로 학습하며 Gold target을 truncate/round/mask로 누락하지 않는다. raw decoder는 같은 backbone/DCE 표현에서 bounded 후보를 평가하고 예산에 걸리면 `partial`을 반환한다. `extraction-head-migration.md`에 head별 목적·loss·decode·consumer를 기록했다.

기존 train engineering50의 정적 census: 추출 target 6,906개, signed residual 204개, cross-window 1개, 학습 target 누락 0. 임시 decoder의 64/64/256 예산은 50기사 중 Entity 10기사와 semantic 4기사에서 전체 Gold endpoint를 구조적으로 담지 못할 수 있다. 이는 낙관적인 oracle cardinality 비교이고 predicted recall/threshold 평가가 아니다. 기계 판독 결과는 `extraction-coverage-report.json`에 있다.

검증: `conda run -n model-test-py312 python -m unittest tests.test_v3_extraction -v` — 7 PASS. synthetic backbone으로 8개 finite Gold loss/gradient, 검증된 기존 train Gold 1기사, nested GENERIC, cross-sentence/cross-window signed decode, Statement-only head fixture, Event-conditioned ACTOR, Primary adapter 변경 불변성을 확인했다. prior/rc2 회귀 17 PASS. `v3_extraction_manifest.py`에서 fresh parameter와 label/shape를 기록했다. 실제 pretrained model load·optimizer step·tiny-fit·본학습은 0회다. 단계 2의 dev Gold blocker는 유지된다.

## 단계 4 / 16 — IMPLEMENTED_STATIC, 전체 Gold gate는 BLOCKED

`V3ArchitectureFactory.fresh_core`가 고정 pretrained backbone을 외부 producer로 두고 단일 DCE, candidate projection, semantic proposer/canonical verifier, Primary adapter를 새로 생성한다. 현재 준비된 task는 공유 forward가 있는 `semantic_proposer` 하나이며 나머지 18개는 명시적으로 미구현이다. full-model 생성 요청은 `UnimplementedTaskError`로 실패한다. 단계별 registry는 dependency·동일 run ID·parameter 중복 소유를 검사한다. `initialization-manifest.json`은 생성된 87개 parameter tensor, 3,772,012개 scalar의 owner와 SHA를 기록했고 weight 파일은 만들지 않았다.

단계 3 `TargetCollator`의 Gold 없는 source windows를 `ArticleBatch`로 연결하고, 주입된 고정 backbone의 L8/L10/L12를 `no_grad` 일반 tensor로 받는 경계를 구현했다. synthetic backbone 출력에서 단일 DCE→proposer의 finite forward/backward와 gradient를 확인했다. 실제 KF checkpoint load, Gold supervised loss, optimizer step, tiny-fit, 본학습은 실행하지 않았다. v2.3-rc2 selective capture/all-valid/direct gather 원본은 변경하지 않았다.

요청 범위 `CompactRepresentationBundle`은 article/content/producer/config/revision/layer·mix/context/dtype/tokenizer/window 정렬, ordered IDs, mask를 검증하고 마지막 consumer 뒤 tensor 참조를 해제한다. `public_scalar_projection`은 tensor·training batch·bundle을 거절한다. frozen source key는 window 단위 스트리밍 digest를 사용하며 trainable key는 model revision/optimizer step/mode와 train-mode 호출 ID가 없으면 재사용할 수 없다. 실제 activation cache를 새로 만들지 않았다. 책임·수명·gradient 경계와 19 task별 target/loss 목표는 `representation-and-gradient-contract.md`, `task-contract-matrix.md`에 기록했다.

검증: `conda run -n model-test-py312 python -m unittest tests.test_v3_target_compiler tests.test_v3_architecture -v` — 10 PASS(단계 4 신규 5). `conda run -n model-test-py312 python -m training.scripts.v3_architecture_manifest` — manifest 생성, 미구현 task 18. `conda run -n model-test-py312 python -m training.scripts.v3_target_coverage` — 단계 3의 train 400기사/42,132 source span 동일. dev/test Gold는 architecture·checkpoint 판단에 사용하지 않았다. 단계 2의 dev `136.json` 혼합 granularity 오류는 그대로이므로 전체 Gold readiness는 `BLOCKED`다. 단계 5는 시작하지 않았다.

## 단계 3 / 16 — IMPLEMENTED_STATIC, 전체 Gold gate는 BLOCKED

현재 r05.3/v1.3의 검증 통과한 **기존 train Gold 400기사만** `ValidatedGoldArticle`로 읽어 task target을 만들었다. `RawArticle`/source window는 Gold 없이 생성되며 compiler는 raw runtime 입력을 받지 않는다. 기존 128-token sentence view에 source-preserving 128-token bridge view(stride 64)를 추가하고 token 내부·공백 경계는 부호 있는 문자 잔차로 보존한다. window 중복은 절대 원문 좌표로 닫는다. Gold source span을 반올림하거나 훈련 mask로 숨기지 않는다.

`target-coverage-report.json`에서 source span 42,132개의 정확한 문자 왕복을 확인했다. 문장 경계 교차 161개, token 내부/공백 경계 1,118개, 단일 window에 담기지 않는 span 11개, 128-token을 넘는 문장 16개가 있었다. 모든 컴파일 target의 원문 좌표를 보존했지만, 현재 rc2/미구현 head가 signed boundary와 cross-window link를 학습·복원하는지는 검증하지 않았다. 이는 단계 5 이후 실제 head 연결의 필수 조건이다.

semantic proposer/boundary/validity, Trigger, role·Entity resolution, 5-type Entity, Time/attachment/normalization mask, coreference, StatementType, Assertor, ABOUT/CAUSES, Primary rank/tie target을 분리했다. 임의의 미기록 semantic span을 음성으로 만들지 않는다. ABOUT는 Statement×EventCluster, CAUSES는 서로 다른 EventCluster의 방향쌍 전체를 lazy 순회한다. null Time/PLACE/Assertor는 추출 양성과 resolution/normalization 무시를 분리했다. 평가 matcher는 Gold 주입·Gold span·predicted span cohort를 명시한다.

검증: `conda run -n model-test-py312 python -m unittest tests.test_v3_target_compiler -v` — 5 PASS. `conda run -n model-test-py312 python -m training.scripts.v3_target_coverage` — 400기사 정적 census. 모델 load/forward/backward/optimizer step는 각 0이다. 기존 dev/test Gold를 compiler나 subset에 사용하지 않았다. 단계 2의 dev `136.json` 문제로 전체 Gold readiness는 여전히 `BLOCKED`다.

## 단계 2 / 16 — BLOCKED

현재 `gold_verified/` 500개 파일의 500 article row / 500 고유 `article_id`를 processed 1,000기사와 결합했다. 이전 seed-41 split은 소속 확인에만 사용했고 현재 Gold coverage는 train 400, dev 51, test 49기사다. 이 수치는 부분 Gold의 현재 보유량이며 1K 최종 label 분포나 split 승인 근거가 아니다. 이전 Gold/annotation label은 새 target으로 쓰지 않았다.

신규 `training/scripts/v3_gold_intake.py`로 v1.3 JSON Schema, 실제 본문 SHA, 파일 번호/processed index/ID, exact offset, cluster membership, role endpoint, relation endpoint, 순위와 Time 달력·구간을 다시 검사했다. 499기사가 통과했고 `gold_verified/136.json`의 dev 기사 `GNEWS-16483dcf7e12279c6e2333af4e335fa7` 한 건이 격리됐다. `TM6.normalized_value = "2025-11/2026-01-23"`은 월/일 granularity를 섞어 r05.3의 같은 granularity 구간 규칙을 위반한다. 스키마 문자열 패턴은 허용하지만 guideline의 cross-object/semantic validator 규칙은 허용하지 않는다. Gold를 자동 수정하지 않았고 이 상태에서 `GOLD_INTAKE_READY`를 선언하지 않는다. 의미적 ABOUT/CAUSES relation completeness도 기계 검사만으로 인증되지 않는다.

검증 통과한 기존 train Gold에서 `engineering_fit40` 40기사와 `engineering_canary10` 10기사를 선정했다. 소스 번호와 `article_id`를 split manifest에 대조했으며 선정 dev/test는 각각 0기사다. GENERIC role endpoint, PLACE SPAN_ONLY, Assertor, normalized/unresolved Time, multi EventCluster, tie, ABOUT/CAUSES, 길이와 source category의 지원 사례를 `coverage-matrix.md`에 기록했다. 진정한 “기존 NER 없이 role에서만 파생” provenance는 현재 Gold에서 기계적으로 분리할 수 없어 GENERIC role exact span으로 대리 관찰했다. tiny-fit 후보 ID는 fit40 안에서만 기록했으며 tiny-fit은 실행하지 않았다.

검증: `conda run -n model-test-py312 python -m unittest tests.test_v3_gold_intake -v` — 8 PASS. `conda run -n model-test-py312 python training/scripts/v3_gold_intake.py` — 500개 정적 검사 실행, 격리 1, 상태 `BLOCKED`. 입력 processed/split/schema/Gold 파일의 단계 1 SHA와 실행 전후 SHA가 일치한다. 모델 load, forward/backward, optimizer step, 본학습, 서비스 threshold 선발, 원격 게시, 실제 DB write는 각 0회다. 단계 3은 시작하지 않았다.

해결 조건: 현재 Gold의 `136.json`을 담당자가 r05.3 계약에 맞게 검토·정정하고 변경된 byte hash를 새 입력 provenance로 기록한 뒤 전체 검사를 재실행해 quarantine 0을 확인해야 한다. 현재 Gold가 더 완성된 뒤 새 task 분포로 기존 split 유지/재설계를 별도 판단한다. 기존 split은 이번 단계에서 변경하지 않았다.

## 단계 1 / 16 — VERIFIED_PRETRAINING

현재 소스·rc2·범위를 고정했다. `source-manifest.json`은 현재 Gold 500개 JSON의 개별 SHA-256과 집계 hash, rc2 package/12 weight/config/schema, R1–R9 로컬 자료, HEAD/작업 트리 기준을 기록한다. `baseline-map.md`는 실제 진입→runtime→identity→compact PUBLIC 흐름과 각 head의 실행 연결을 구분한다. `task-contract-matrix.md`는 REUSE/ADAPT/NEW/OUT_OF_SCOPE 초안이다. `decisions.md`는 namespace와 N1 DB 경계를 기록한다.

착수 시 `git status --short`는 추적 파일 `.gitignore` 수정 1건과 미추적 항목 61건이었다. 모두 기존 사용자 작업으로 취급해 수정·삭제하지 않았다. 이 단계의 변경은 `docs/v3-pretraining/` 신규 파일뿐이다.

### 새로 실행한 검증

- `conda run -n model-test-py312 python scripts/validate_bcr_v23_rc2_static.py` — PASS: 154-file exact inventory, manifest 대상 153개 byte SHA, 12 checkpoint parity, 150 source mapping, policy/config/schema, isolated import. model load=0, article inference=0.
- `conda run -n model-test-py312 python -m unittest tests.test_goldfree_article_kg_pipeline tests.test_bcr_step9_5_capture -v` — 7 tests PASS. fixture/mock 및 scalar capture 검증이며 실제 pretrained model 추론은 아니다.
- `source-manifest.json`의 현재 processed/guideline/schema/lineage/Gold/rc2 SHA를 현재 파일 bytes에서 계산했다. pinned HF cache snapshot 6개 SHA가 rc2 manifest와 모두 일치함을 읽기 전용으로 확인했다. 원격 HF의 현재 bytes는 재검증하지 않았다.

### 환경과 측정 범위

`model-test-py312`: Python 3.12.13, torch 2.13.0, transformers 4.57.6, tokenizers 0.22.2, huggingface-hub 0.36.2; macOS 26.6.2 arm64, CPU, CUDA 0/불가, MPS 불가, default dtype `torch.float32`, torch threads 6. rc2 runtime config의 실행 thread는 4, dtype은 FP32다. 기본 shell Python 3.11.9에는 해당 ML package가 없어 검증에는 conda 환경을 사용했다. 로컬 HF pinned snapshot은 존재하고 6개 SHA가 일치한다.

실제 model load, raw article inference, forward/backward, optimizer step는 모두 0이다. 새 timing/memory 측정은 하지 않았다. rc2 72기사 CPU latency/RSS는 과거 `docs/release-v2.3/final-validation-summary.md`에만 기록된 값이다. Gold semantic correctness/전체 유효 article 수는 검사하지 않았다.

### 현재 blocker와 다음 전제

단계 1 완료를 막는 항목은 없다. 단계 2는 아직 `NOT_STARTED`다. 단계 2에서 Gold 전체 기계 검사와 기존 train split 기반 engineering50 선정이 필요하다. N1의 PRODUCT/GENERIC type 및 zero-event persistence mapping은 후속 DB adapter 결정으로 남긴다. v3 본학습 준비 상태는 아직 아니다.

본학습 실행: 0. 서비스 threshold 선발: 0. 원격 게시: 0. 실제 DB write: 0. 다음 단계 자동 실행: 하지 않음.
