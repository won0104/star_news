# V3/V23 최적화 역사

범위: 2026-09-24~27의 확인 가능한 변경과 선행 Phase 1/shadow 기록. Git 조사 HEAD `1d02b429`. `adopted`는 당시 실행 코드 연결, `shadow`는 read-only 실험, `rejected/deferred`는 미승격, `result-preservation`은 과거 결과 보존이다. 측정 조건과 원값은 [벤치마크 원장](benchmark-ledger.md), 원본은 [artifact 색인](artifact-index.md)에 있다.

## Chronology anchor

| 시기 | 사건 | 해석 경계 |
| --- | --- | --- |
| 09-24 | `8a0644a2` frozen cache; `2eb07a91 → ba1e34e1 → e85fa14b` v2.3 source/pair 이관; `d1e35259` P1 evaluator | 첫 이관의 192 guard 혼입은 `ba1e34e1`에서 정정. |
| 09-25 | P1 epoch-6 선택; Entity/Participant shadow; Batch 1/3/2/4/5 | Batch 번호는 commit 순서가 아님. K2/Top32와 H2 정책은 production 미승격. |
| 09-26 오전 | `7ee2a158` P5→P6 feature 공유; 임시 B CPU PUBLIC 22초대 원인 계측 | B는 provisional shadow. 이후 후보·threshold·cap이 변한다. |
| 09-26 오후 | PUBLIC audit/lifecycle, Assertor·Time, relation 지연, native type dedup, feature reuse, safety | 순수 계산 재사용과 출력·후보 의미 변경을 분리. |
| 09-26 저녁 | C1/C2 → D1/D2 → E1/E2 shadow; 사용자 D2/E1 선택; `fd3f5ffc` dev49 계측 | 운영 정책 실험. dev49는 후반 세 code commit 이전. |
| 09-26 밤~09-27 새벽 | `3d4e003d → ff6994ea → 906037d8`; 1,728자 CPU 재계측 | 실제 수치는 대화에 있으나 각 commit별 추적된 기사 결과 JSON 없음. |
| 09-27 | trained Primary provenance, PUBLIC edge/role, bundle freeze | 이전 exact PUBLIC 비교를 후속 출력 의미 변경에 자동 확장하지 않음. |

## 1. Phase 1 evaluation / frozen feature optimization

- **Frozen backbone cache** (`8a0644a2`, adopted): frozen KF-DeBERTa L8/L10/L12 source view를 run-local CPU cache로 저장하고 trainable DCE는 매 step 새로 계산했다. synthetic 3-view×4-sweep backbone 호출 `12 → 3`, pinned MPS 단일-view cold miss/hit `1204.26 ms`/`645.33 ms`, 20 active loss 차이 0. 전체 기사 서비스 시간이나 train73 실제 epoch speedup이 아니다. [원본](../results/originals/docs/v3-pretraining/v3-frozen-feature-cache-benchmark.json).
- **Runtime/predicted replay source 공유** (`522b3879`, adopted/provisional): 두 실행이 서로 다른 source selection을 재구현하지 않도록 같은 executor와 checkpoint·policy·acceptance SHA binding을 사용했다. [dev15 parity summary](../results/originals/training/results/v3-r06-shared-source-funnel-parity-v1/summary.json)는 당시 15기사의 lane·budget·trace mismatch 0을 기록한다. 이 wiring parity는 Gold 품질 또는 최종 threshold 승인과 별개다.
- **Epoch dev 평가 fast path** (`d1e35259`, adopted): P1 raw-score용 공통 representation과 active dev loss를 한 article forward로 수집하고 downstream unused loss를 제거했다. 고정 기사 두 건 old→optimized `115.009 s → 17.705 s`, `74.538 s → 51.248 s`; backbone 1회, DCE `2 → 1`, 후보 좌표·raw digest·active loss·Extraction E parity. 두 기사 비교를 dev15 전체 시간으로 바꾸지 않는다. [선택 run report](../results/originals/training/results/v3-gold100-phase1-max6-v4/report.md).
- **Checkpoint selection과 calibration 분리** (`ce935d00` 근방): fresh seed 1008의 train73 6 epoch checkpoint 전부를 쓴 뒤 raw dev15로 epoch 6 선택. immutable checkpoint SHA `97fae4720bdd820395f17fff79f23d15fe41501203fb43a74788b1ea40fa0563`. source calibration은 선택 이후에만 실행. 중단된 v2/v3 run을 warm start하지 않았다.

인과 순서는 **v2 epoch-01의 비정상 dev 평가 → 중단/diagnostic 격리 → active-loss와 공통 forward fast path → v3 owner representation mismatch 중단 → fresh v4 max-six 완료 → raw E로 epoch 6 선택 → 선택 후 calibration → predicted source/K 진단**이었다. [5번 packet](../evidence/chat-5-source-packet.md)의 v2/v3 abort 기록은 실패한 checkpoint가 selection에 재사용되지 않았음을 확인한다. v4 E는 epoch 1~6 `0.553881/0.593301/0.609139/0.630934/0.642821/0.645689`였다. 첫 914자 기사 K8/16/32/64는 Gold `5/28,6/28,8/28,10/28`, ready 모두 `0/3`; 사용자의 당시 K32 승인은 `PROVISIONAL_ENGINEERING`에 한정됐고 Phase 2 ready 판정은 false였다. 이는 다음 scale/shadow 실험을 촉발했으며 K32의 production-optimal 증거가 아니다.

## 2. Entity/Participant shadow experiments

서로 다른 고정 입력의 수치를 덮어쓰지 않는다. 초기 dev15 frozen Entity routing 자료는 첫 기사만 actual typed, 나머지 14개는 scalar/untyped proxy다. 나중의 Participant threshold shadow는 actual typed 15기사이며 그 H2 `144/259`를 이전 frozen proxy H2 `152/259`로 덮지 않는다. prospective fine pairs는 fine head 결과가 아닌 route 출력 수다.

실험의 흐름은 **ROLE/Entity 후보 폭증과 K32 miss 확인 → source 후보를 줄이는 family·threshold·K 방식의 Gold 손실 검증 → 후보를 보존하는 routing-only family·cosine·heuristic의 rank/cost 상한 검증 → H2의 같은-policy 구현 비용 최적화**였다. 각 실험은 앞 실험의 문제를 좁히는 shadow였고, 불채택이 모든 signal의 부재를 뜻하지는 않는다. `ROLE family` F1에서 첫 기사 exact pair `28→27`을 감수할 수 있다는 사용자 발언도 있었지만, 이후 중단과 구조 재설계로 production 채택은 이루어지지 않았다. [5번 packet](../evidence/chat-5-source-packet.md).

| 실험·상태 | 연구 질문 | 확인된 결과 |
| --- | --- | --- |
| Entity scale/K32 visit, diagnostic-only | 7,780 후보 기사에서 Gold 28쌍 중 왜 8쌍만 fine에 가는가? | dev15 235,892 후보, 첫 기사 ROLE-only 5,921/7,780. Query/posting 256/64→2048/512에서 28쌍 전부 visit돼도 K32 `8/28`, ready `0/3`; miss rank 56~550. `MIXED_BOTTLENECK`, K32 `PROVISIONAL_ENGINEERING`. [report](../results/originals/training/results/v3-gold100-phase1-entity-scale-audit-v1/report.md). |
| Participant threshold 0.6430121660232544→0.75, shadow/rejected | ROLE evidence를 endpoint acceptance만으로 줄일 수 있는가? | actual typed MPS dev15 accepted 755,193→593,941, Entity 235,892→231,861, owner Gold role hit 71/142→60/142, exact Entity 231/238→228/238. Fixed coref source 259/259·cluster 37/37 유지. **0.80/0.90 미실행**. [report](../results/originals/training/results/v3-gold100-phase1-participant-threshold-shadow-v1/report.md). |
| Event×role K2, shadow/rejected | 전량 ROLE promotion을 K2로 줄여도 Gold가 사는가? | role filler 593,941→1,625, Entity 231,861→97,560, prospective H2 fine 6,009,034→2,296,322, router 122.33→43.56 s; Gold Participant 60/142→12/142. 비용만으로 채택하지 않음. [report](../results/originals/training/results/v3-gold100-phase1-participant-forwarding-k2-shadow-v1/report.md). |
| B2 Top32/K16·K32, shadow/rejected | decoder object와 forwarding 상한을 분리하면 K2보다 안전한가? | materialized span 593,941→24,606, Gold uncapped/K16/K32 60/142, 22/142, 28/142. 무제한 B2 source 의미를 대체하지 못함. [report](../results/originals/training/results/v3-gold100-phase1-participant-top32-shadow-v3/report.md). |
| ROLE candidate family F1~F4, shadow/rejected | Cartesian boundary를 source에서 대표 span으로 줄일 수 있는가? | F2 dev15 235,892→174,406 후보, exact Gold Entity 231/238→228/238, source coref 259→255. evidence rebind가 exact coordinate를 보존하지 못했다. `FAMILY_CONSOLIDATION_HARMS_GOLD_REACHABILITY`. [report](../results/originals/training/results/v3-gold100-phase1-role-family-shadow-v1/report.md). |
| Routing-only family V1/V2, shadow/rejected | source 후보를 삭제하지 않고 routing competition만 family로 압축할 수 있는가? | source denominator 235,892/259/37 고정. V1 MAX+E1 all은 routed 122→134, ready 9→13이나 fine 6,737,247→52,047,801; 가장 싼 V1 E3 top2도 8,505,340 pairs. TYPE-only 여섯 miss 잔존. [report](../results/originals/training/results/v3-gold100-phase1-entity-family-route-shadow-v1/report.md). |
| Raw 256d state cosine, shadow/rejected | existing state cosine이 학습 없이 K32를 대체하는가? | deterministic K32 122/259·9/37·6,737,247 pairs. semantic top32 72/259·8/37·5,016,647; top64 135/259·11/37·10,303,509. Hybrid top32 138/259·12/37·10,877,807. Signal은 있으나 retrieval-ready 아님; ANN/head 미구현. [report](../results/originals/training/results/v3-gold100-phase1-entity-raw-cosine-shadow-v1/report.md). |
| H1/H2/H3, shadow/not promoted | lexical rarity·geometry·RRF, TYPE multi-view·NER anchor, bounded clique의 Gold-free routing 가치? | V0/H1/H2/H3 routed `122/143/152/152` /259, ready `9/15/16/16` /37, pairs `6,737,247/6,452,595/6,494,098/6,494,098`, CPU router `47.11/160.56/159.26/170.07 s`. H3 rescue gain 0; H2 첫 기사 TYPE-only 여섯 pair 미해결. [report](../results/originals/training/results/v3-gold100-phase1-entity-heuristic-h123-shadow-v1/report.md). |
| H2 O1~O6 exact-parity profile, shadow/not promoted | H2 자체를 같은 선택으로 더 싸게 만들 수 있는가? | 같은 frozen H2 original audit `159.81 s`, optimized audit `94.92 s`, production-shaped shadow `88.76 s`; ordered K32/pair/pool/posting exact, 6,494,098 pairs 동일. RSS 개선 없음. H2와 V0의 정책 parity가 아니다. [report](../results/originals/training/results/v3-gold100-phase1-h2-exact-parity-profile-v1/report.md). |

## 3. Batch 1~5 runtime optimization

Batch 3(`7d0b45f8`)이 Batch 2(`cc29f1fb`)보다 먼저다. 당시 Batch 3 parity를 Batch 2의 새 Entity 계약으로 소급하지 않는다.

| 날짜·commit | 전→후 구조와 목적 | 증거·결정 |
| --- | --- | --- |
| 09-25 `e2ad73e3` 기준 read-only 감사 | R1~R9로 Participant forwarding, native retyping, Event feature all-Entity 인코딩, Assertor option 이전 full mean, PUBLIC audit 비용을 분리. | 계획/진단, Batch 실행 결과 아님. |
| `e5c02497`, `bd21aaa0` Batch 1 | K2, 이후 Top32/K16/K32 B2/ROLE cardinality shadow. | Gold 손실로 rejected. |
| `7d0b45f8` Batch 3 R3 | Event feature가 모든 Entity exact feature를 생성 → role-referenced distinct Entity만. | 선택 P1·짧은 synthetic CPU feature row **`14→1`**, median **`2.493→1.158 ms`**, logits/IDs/closure/PUBLIC exact. `CHAT_ONLY`, 독립 JSON 없음. 당시 adopted. |
| 같은 commit R4 | 전체 Entity mean 선집계 → Assertor/role option cheap 선택 후 필요한 Entity만 집계·재사용. | 같은 fixture 집계 Entity **`14→8`**, median **`0.0822→0.0575 ms`**, 당시 exact parity·25 tests. `CHAT_ONLY`, 독립 JSON 없음. 후속 Entity 계약에서 별도 재확인 필요. |
| `cc29f1fb` Batch 2 | Native type/ID 보존과 unified mention/closure. K cap이 아니라 identity 의미 계약을 수정. | 코드 채택, 당시 새 dev15 inventory/A·B·D 검증은 일부 미완료. 의미 변경. |
| `f1fcf0ca` 평가 보조 | Raw score collection/offline replay 분리, threshold 후보마다 forward 반복 방지. | `CODE_ONLY`, serving 시간과 합산 금지. |
| `1a0f3140 → dfd72793` Batch 4 | `analyze_public()`의 rejection/audit/census/unused Time normalization 진단 지연; `analyze()` 전체 진단 유지. | 8자 합성 fixture diagnostic/public median `83.244/83.187 ms` 10 paired, PUBLIC/closure/logit exact. 서비스 speedup 아님. |
| `74c56914` Batch 5 | route duplicate score/SHA, pair별 host read, CAUSES reverse membership 비용 제거. | CPU engineering fixture 1/2/3문장 paired median `129.23→117.75`, `306.22→280.96`, `768.44→706.06 ms`, ordered PUBLIC/route/logit exact. R9 Event-Time article cap 4096 변경 deferred. |

## 4. v2.3 front/source/pair-routing migration

- `2eb07a91`(09-24 14:06): `V23_BASELINE` 첫 이관. EVENT/STATEMENT TOP32·96 token, ENTITY T14/C6, TIME T16/C8, Trigger greedy one-to-one, Event-conditioned Participant B2. 다만 V3_WINDOW 192 guard/route cap 혼입으로 bounded Entity/Time 9,649/9,781 중 fine 각 192. Fresh-weight synthetic source-only V23 `2.22초` vs V3_WINDOW `0.51초`는 **왜곡된 첫 baseline**의 문서 기록이다. 정확한 당시 문서는 `git show 2eb07a91:ArticleLocal-KG-DeBERTa/docs/v3-pretraining/v23-front-baseline-migration.md`로 복원한다.
- `ba1e34e1`(09-24 15:35): v2.3 bounded 후보를 모두 chunk fine scoring하고 V23에서 192 guard/cap 제거. 같은 synthetic seed111/0.0 gate source-only Entity/Time 9,649/9,781 전량 fine, guard drop 0, backbone/DCE 1/1; 약 `6.88초`, peak RSS 약 `1.50GB`. workload가 달라 첫 2.22초와 pure regression 비교 불가. Time normalization 실패 제외는 별도 의미 변경.
- `e85fa14b`(09-24 16:28): v2.3 scalar coarse router에서 선택한 pair만 v3 fine scorer로 전달. Event→Time K80 등은 adaptation; v2.3 TIER1 Entity eligibility를 ROLE-derived Entity가 있는 v3에 그대로 적용하지 않았다. routing miss=`NOT_EVALUATED`. Synthetic `Ada ran.` selected/fine Entity 9,730/9,730, Event-Time 420/420, Event coref 83/83(naive105), request `0.14994704199489206 s`는 선택 P6 latency가 아니다. [smoke](../results/originals/training/results/v3-v23-pair-routing-audit-v1/pair-routing-smoke.json).

## 5. PUBLIC runtime optimization

| commit | 당시 반복·낭비와 변경 | 분류 |
| --- | --- | --- |
| `d85fb147`, `15bba931`, `31cf24ca`, `349ba8b4` | Participant exact char residual, sentence window lookup, PUBLIC Entity pair audit, B2 Event row scan을 재사용/index/지연 생성. | adopted `CODE_ONLY`, 단독 latency 없음. |
| `25e1406c` | PUBLIC Event role endpoint 제한, 미선택 fact 해제. | adopted, **output contract change**. |
| `010b7fb2` | Assertor source/options와 Event→Time 중복 work 감소; 정규화 실패 Time 제외는 선택 의미에도 닿음. | adopted `CODE_ONLY`, 단독 paired article 없음. |
| `ce09c30d` | full Relation→Primary를 PUBLIC-only Primary→limited CAUSES discovery→final selection→selected-only ABOUT/CAUSES로 재배치. route와 intersection, `analyze()` full diagnostic 유지. | 작은 fixture PUBLIC exact; 독립 기사 결과 없음. |
| `9ba1c83b` | 같은 좌표 Native Entity 5 type candidate 대신 type evidence 가진 argmax mention 하나; Event-Time exact reuse. | **candidate universe change**, B 후보 과거 시간과 pure-code 비교 금지. |
| `b9ca6702`, `e2e65534`, `90158ac5` | sentence/span 공유, Entity resolution profiler, pair/fine tensor·Event-Time cache reuse. | 구현 adopted; profiler diagnostic-only. |
| `4b8b07df` | dangling connective Event canonical text 정정. | output semantic edit, latency 최적화 아님. |
| `aa980569` | P6 trained Primary provenance, PUBLIC persistence, allowed relation pair 정상화. | release correctness/status change. 뒤의 `b65a0b9c`/`ad3b8080`가 edge confidence/role을 변경. |

## 6. Operational cap / threshold experiments

`28e27eb8`는 pathological article용 emergency ceiling을 도입했다: ENTITY/TIME expensive 각 65,536; accepted EVENT/STATEMENT 각 128, ENTITY_NATIVE/TIME/TRIGGER 각 256; unified Entity 128. 미도달 exact, 초과 deterministic partial과 reason. 정책/출력 영향이지 순수 code speedup이 아니다. `963bf204`, `ace16467`은 guard audit·operational 적용을 정리했다.

Provisional 후보 B의 1,728자 dev 기사에서 C1/C2 cap → D1/D2 threshold → E1/E2 cap을 shadow로 따로 비교했다. C/D manifest HEAD `963bf204`, E manifest HEAD `7da60581`; HEAD만으로 미커밋 working-tree bytes는 고정할 수 없다. C1/C2 출력은 달랐고 D1/D2·E1/E2의 output SHA 일치는 그 기사 한 건에 한한다. 원본은 [결과 snapshot](../results/originals/training/results/)에 있다.

사용자 선택 `fd3f5ffc`: D2 `PARTICIPANT_ENDPOINT=0.8`, `EVENT_COREFERENCE=-0.5`, `ENTITY_NATIVE=0.75`, `TIME=0.5`, `EVENT_TIME=0.5`와 E1 EVENT accepted96, TIME accepted128, ENTITY expensive20,480, TIME expensive24,576. [설정 snapshot](../configs/originals/training/configs/v3-gold400-runtime-d2-e1-selection-v1.json). 당시 `service_ready=false`는 **그때의 config provenance**이며 후속 project-final release status와 혼동하지 않는다. `7da60581`, `0b924a77`, `abf65634`는 결과 보존/측정 커밋이지 구현 최적화가 아니다.

## 7. 후반 pooling / candidate transport / source-feature reuse

세 코드는 D2/E1 선택 및 `fd3f5ffc` dev49 측정 **뒤**에 들어왔다. 아래 수치는 [2번 packet](../evidence/chat-2-source-packet.md)의 당시 1,728자 기사 CPU `CHAT_ONLY` 보고이며 dev49 측정이 아니다.

| 순서 | 바뀐 반복 계산 | parity 및 당시 한 기사 관찰 |
| --- | --- | --- |
| `3d4e003d` | CandidateSpanEncoder prefix pooling, Participant B2 Cartesian vectorization. | prefix vector/logit 수치 tolerance, 최종 candidate/threshold/PUBLIC 구조 exact; B2 좌표/score/provenance/order exact. D2/E1 bare `5.749초`, profiled `5.864초`; tracked 기사 결과 없음. |
| `ff6994ea` | Entity/Time 공통 source geometry, lightweight recipe→cap, indexed `SourceLayout.align()`. | 후보 좌표/order/score/provenance/trace/alignment fixture exact. 같은 기사 CPU 4 threads bare `5.219초`; tracked 기사 결과 없음. |
| `906037d8` | Native geometry carrier, Assertor batch+winner state, Participant 세 role 좌표 공유, Event-Time direct feature handoff. | Assertor score `1e-7` tolerance·winner/threshold/ASSERTED_BY exact; 나머지 feature/route/PUBLIC fixture parity. 같은 기사 first `5.01초`, profiled warm `4.98초`, bare warm `5.11초`; source profiled `3.014초`. tracked 기사 결과 없음. |

세 commit의 기여를 `22.90→5.11` 총차로 배분하지 않는다. bare/profiled 호출은 다르며 작은 역전은 단일 실행 변동이다.

## 8. P5→P6 Event feature reuse

`7ee2a158`(09-26 10:23)은 P5가 모든 retained Event member를 pair routing 전에 한 번 `EventFeatureEncoder`로 인코딩하고 request-local lease로 P6 Primary에 넘기게 했다. P6 별도 member encoder를 제거하고 cluster aggregation/final score만 남겼다. ABOUT/CAUSES final-cluster 입력은 유지했다. [계약 문서](../../../ArticleLocal-KG-DeBERTa/docs/v3-pretraining/p5-p6-event-head-split-v1.md)와 `tests/test_v3_p6_precomputed_event_features.py`가 코드/fixture 근거다.

이것은 v2.3 head의 수치 복사가 아니다. P5 pair schema가 달라졌고 예전 Event coreference threshold/AP를 재사용할 수 없다. 동일 기사 전후 latency·RSS와 새 migration artifact는 확인되지 않았다. 기존 `v3-p4-p5-event-channel-head-migration-v2` 파일은 **옛 encoder ownership**이므로 이 재사용의 완료 증거가 아니다.
