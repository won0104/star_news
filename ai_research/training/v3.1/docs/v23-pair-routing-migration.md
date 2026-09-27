# V23 pair routing 및 문자 경계 이관 기록

> Historical migration record. Participant→Entity K64/K32/K16 and `role_entity`
> are retired from active unified identity execution; see
> [unified-entity-identity-v1.md](unified-entity-identity-v1.md).

## 실행 계약

`V23_BASELINE`에서 source extraction은 기존 source funnel이 완료한다. 그 뒤
`serving.py`가 v2.3 release의 immutable scalar router를 호출하여 pair ID를
선택한다. `entity_scoring.py`, `temporal_scoring.py`, `event_scoring.py`의 기존
v3 PairContext head는 선택된 pair만 점수화한다. Acceptance, Entity/Event
complete-link, relation graph는 router 밖에 있다. `V3_WINDOW`의 기존 pair
입력과 relation 경로는 변경하지 않았다. 누락 pair는 `NOT_EVALUATED`이며
음성 레이블이 아니다. 이 이관에는 Gold 후보, Gold pair, 새 source cap이 없다.

| lane | v2.3 실제 실행 정책 | v3 연결 / 차이 |
| --- | --- | --- |
| Participant→Entity | `participant_entity.py`의 기사별 PRIMARY index, overlap/sentence, ±1·±2 near, alias/ngram/salience global. K64 retrieval 32/16/16, K32 primary 16/8/8, visit·cheap 88, posting 32. Primary fine 실패 시 별도 K16 RESCUE_ONLY | 같은 scalar index·tier·budget을 사용한다. 선택 mention을 v3 Entity cluster ID로 접어 D6 fine input을 만든다. v2.3 promotion 기반 eligibility·salience는 **V3_ENTITY_SEMANTIC_ADAPTATION**으로 분리했다. 현행 v3에는 RESCUE_ONLY boundary family가 없어 rescue는 아직 미연결이다. |
| Event→Time | `temporal.py`의 clause/sentence LOCAL 8, ±2 sentence NEAR 8, finite Time score top64 GLOBAL 64, 총 K80, visit·cheap 192, posting 64 | 동일 router를 Time occurrence에 적용한다. 정규화 미해결 occurrence도 후보이며, 여러 attachment를 허용한다. Time source score를 scalar sigmoid 값으로 전달하는 것은 v3 schema adaptation이다. |
| Entity↔Entity | `resolution.py`에서 same type 및 적어도 하나의 `TIER1_PROMOTED` mention pair를 scorer에 전달한다. pair K는 없다. 미평가 pair는 complete-link의 음성이 아니다. | 현행 v3는 cluster membership·final type을 결정한 뒤 명시 mention, final type 일치, source order, span/ID 순으로 대표자를 고른다. v3 closure는 교차 type 병합도 표현할 수 있으므로 현행 all-pair fine 입력을 유지한다. 옛 promotion tier/score나 `entity_priority`로 TIER1/TIER2를 재구성하지 않는다. 이 lane의 old eligibility는 **RESTORED_V23_PAIR_ROUTING 아님**, **V3_ENTITY_SEMANTIC_ADAPTATION**이다. 비용 감소는 미해결이다. |
| Event↔Event | `event_monotonic.py`의 LOCAL/LEXICAL/TRIGGER/ENTITY/TEMPORAL posting, retain 3/5/2/3/2, visit 24/64/24/48/24, seed 보호, neighborhood 12, clique completion, hard cap min(3072, 32×Event 수) | 같은 scalar router를 v3 EventMember ID와 role/Time handoff에 적용한다. 선택 pair만 기존 Event fine head와 complete-link에 전달한다. 임의의 4096 cap은 baseline router로 쓰지 않는다. |

v2.3 근거는 `runtime/candidate_routing/integrated.py`가 읽는
`runtime/configs/bcr-integrated-v23-rc1.json`(SHA-256
`2c212672a204a2e083683bdea44fc69b4d40aa796a31de4301c3dbd21d07d14a`),
`runtime/eventframe/resolution.py`, `runtime/candidate_routing/temporal.py`,
`runtime/candidate_routing/event_monotonic.py`이다. v3 adaptation은
`runtime/v3_pretraining/pair_routing.py`에 있다. phase manifest는 downstream
`V23_BASELINE`에서 integrated policy SHA와 Entity semantic adapter SHA를
기록하며 불일치한 checkpoint resume을 거부한다. 기존 V23 phase checkpoint는
새 manifest와 일치하지 않으면 재사용할 수 없다.

각 선택 pair trace에는 query/candidate ID, lane, tier, matched scalar key,
cheap score 또는 명시적 ordinal, rank, policy ID/SHA, source inventory lineage,
`SELECTED_FOR_FINE_SCORING`이 있다. Router는 fine status를 기록하지 않으며,
fine 결과는 별도의 acceptance trace에 집계된다. Participant trace는
candidate cluster ID와 선택된 mention ID를 모두 남긴다. Event coreference
completion pair는 `BOUNDED_CLIQUE` 출처를 남긴다.

## 문자 경계

r06 Gold train 73 + dev 15에서 Participant role span 815개를 census했다.
ACTOR 531개 중 partial-char 25개, TARGET 219개 중 3개, PLACE 65개 중 2개다.
전체 30개 모두 한쪽 boundary만 partial이고, 양쪽 partial 0개, sentence cell
부재 0개, cross-window 0개다. token boundary와 exact char가 일치한 것은
785개다. 기존 B2 token cell에 reachable한 것은 716개이며 그중 exact char가
다른 것은 29개다. test split 접근은 0회다. 결과와 Gold/tokenizer SHA는
[EOT의 Participant boundary census](../../../EOT/v3-runtime-optimization-2026-09/results/originals/training/results/v3-v23-pair-routing-audit-v1/participant-boundary-census.json)에
있다. 이 수치는 **후보 생성 recall이 아니라 Gold 좌표 구조 census**다.

`extraction_decode.py`의 Trigger 및 Participant native owner 후보는 그대로
보존한다. 같은 sentence token cell 안에서 학습 대상 exact residual이 다른
문자 좌표를 가리키면 `V23_TRIGGER_CHAR_EXTENSION` 또는
`V23_PARTICIPANT_CHAR_EXTENSION` 좌표를 추가한다. residual은 각각 기존
Trigger/Participant teacher-forced loss에서 감독된다. 부모 좌표와 producer
provenance를 남긴다. 확장 후보는 부모와 ranking 경쟁하거나 두 번째 gate를
거치지 않는다. 기존 Trigger 8개 partial-char Gold에 대한 **실제 predicted
survival은 아직 측정하지 않았다**. Gold는 census에서만 읽고 runtime에는 주입하지
않는다. EVENT/STATEMENT additive TOP32 correction과 ENTITY/TIME native exact
enumeration은 유지한다.

## 검증과 제한

작은 deterministic fixture는 native Trigger/B2 owner 보존, 추가 좌표,
pair selection 순서와 lineage, Time 다중 attachment, routing 선택과 fine
거절의 구분, Event channel provenance, Entity cluster 입력 dedup,
`V3_WINDOW` 회귀를 확인한다. `Ada ran.` fresh synthetic smoke에서는
Entity 9,730/9,730, Event→Time 420/420, Event coreference 83/105
fine pair를 선택했다. 각 lane의 선택 수와 fine scorer 입력 수가 일치했고
backbone/DCE는 각각 1회였다. 해당 warm-process 요청 시간은 약 0.15초,
process peak RSS는 570,343,424 bytes였다. 측정 환경과 policy SHA를 포함한
원본은 [EOT의 pair-routing smoke](../../../EOT/v3-runtime-optimization-2026-09/results/originals/training/results/v3-v23-pair-routing-audit-v1/pair-routing-smoke.json)에
있다. 이 수치는 품질·Gold survival 지표가 아니다.
별도의 Participant 활성 fixture에서는 naive 1,001 pair 중 56개를 선택해
56개를 fine scorer에 전달했다. 7개 query에서 방문/선택 budget이 소진됐다.
기록은 `pair-routing-role-smoke.json`에 있다. 두 fixture는 source gate가
달라 latency/RSS를 서로 품질 비교에 사용하지 않는다.

train73+dev15의 Gold pair routing survival/latency/RSS census는 실행하지
않았다. 현재 fresh/open-gate fixture는 source inventory가 비정상적으로 커
Entity all-pair 비용이 높으며, checkpoint-bound acceptance를 갖춘 동일 환경
비교가 필요하다. Participant char extension과 source inventory가 확정된 뒤
Gold를 predicted 실행 **후에만** join하여 routing miss와 fine reject를 분리해야
한다. K16/K32/K64 또는 새 budget의 채택·품질 판정은 그 census 전에는 하지 않는다.
ABOUT, CAUSES, ASSERTED_BY의 새 v3 relation routing은 **NOT_STARTED**다.
v2.3 Event identity/Participant 라우터와 eligible pair 의미를 공유한다고
가정하지 않는다. RESCUE_ONLY 부재, Entity all-pair 비용, v3 shared DCE와
CandidateSpanEncoder, 새 schema scalar score 적응은 후속 미검증 항목이다.
