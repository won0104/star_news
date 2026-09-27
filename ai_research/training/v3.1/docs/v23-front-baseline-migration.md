# V23_BASELINE 앞단 실행 계약 정정

## 실행 경로와 원본 근거

v2.3 release의 근거는 `runtime/candidate_routing/integrated.py` →
`runtime/pipeline.py` → `runtime/eventframe/runtime.py` 및
`runtime/configs/article-local-runtime-v22.json`이다. Entity/TIME의 bounded
selector 출력은 `runtime/eventframe/entity.py` 등의 `fine_candidate_rows`에서
chunk 단위 native scorer로 전달됐다. 기사 전체 192 guard는 없었다.

현재 단계별 학습의 predicted lane은 `v3_staged_train.py` → `StagedTrainer` →
동결 producer의 `V3ServingWorker.analyze_source_funnel()` →
`decode_source_spans()`다. runtime과 replay는 같은 worker를 호출한다. Gold
oracle 양성 손실은 predicted source gate와 독립이다. 새 기준선은 checkpoint에
묶인 `V23_BASELINE` 정책에서 아래 순서로 실행한다.

| lane | `V23_BASELINE` 후보 → fine decision → 수락 |
| --- | --- |
| EVENT / STATEMENT | 문장×종류 TOP32 (96 token) → local Canonical V3 semantic·boundary → 두 점수 AND. 원본 후보는 보존하고 학습 대상인 문자 residual이 같은 token cell 안에서 좌표를 보정하면 별도 후보로 추가 |
| ENTITY | T14/C6 bounded token·문자 후보 전부 → 256개 단위 direct CandidateSpanEncoder·5개 type 독립 native logit → 새 Gold/checkpoint 정책의 native threshold |
| TIME | T16/C8 bounded 후보 전부 → 1024개 단위 direct native Time logit → 새 Gold/checkpoint 정책의 native threshold. 수락된 source 후보는 진단에 남기되, V23 runtime에서는 source 정규화에 실패한 Time을 Event→Time 표현·라우팅·PUBLIC 이전에 제외 |
| TRIGGER | 새 Gold/checkpoint endpoint gate → greedy one-to-one → 문장당 4개. Event에 없으면 attachment만 비움 |
| PARTICIPANT | accepted Event 조건부 B2 endpoint gate → 역할별 독립 start/end Cartesian → exact duplicate closure. `output_cap=null` |

`max_scored_candidates`와 `ServingBudget`의 v3 수치는 현재 자료 구조에 남지만
`V23_BASELINE` 실행의 후보·수락·union 수를 제한하지 않는다. `V3_WINDOW`는
기존 quota 96/96, guard 192, kind cap 64, Trigger containment hard gate,
Participant K2, Entity 128 budget을 유지한다. 이전 V23 정책의 v3 budget 혼합
실행 순서는 `v23-baseline-source-funnel-v2`에서 거부된다. checkpoint·정책 SHA,
profile, phase manifest, 데이터 경계 검사는 그대로 fail-closed다.

Time 정규화 실패분 제외는 source extraction의 T16/C8 후보 또는 native acceptance를
줄이는 cap이 아니다. V23 downstream Time inventory에만 적용되는 별도 실행 의미
변경이며, 기존 checkpoint-bound validation 결과가 새 runtime의 품질을 증명하지
않는다. 배포 artifact는 이 코드로 재검증한 뒤 다시 동결해야 한다.

## 항목별 소속

| 범주 | 항목 | 상태 |
| --- | --- | --- |
| RESTORED_V23 | TOP32, Canonical V3, T14/C6, T16/C8, Trigger greedy 4, Participant B2 Cartesian | local 후보·판별·수락의 기준 경로 |
| NEW_GOLD_EXTENSION | GENERIC, 원문 exact char boundary, cross-window exact extension, role/Assertor-derived Entity union | bounded/local owner 후보를 제거하지 않고 별도 출처로 추가. `V23_CHAR_EXTENSION`·`V23_EXACT_EXTENSION` provenance 기록 |
| V3_EXPERIMENTAL_NOT_IN_BASELINE | 96/96 route quota, 192 guard, 64 per-kind cap, Trigger containment hard gate, Participant K2, Entity 128 budget | `V3_WINDOW`에만 적용 |
| V3_EXPERIMENTAL_NOT_IN_BASELINE | shared DCE, shared CandidateSpanEncoder | 모델 구조에는 남아 있으나 v2.3의 task별 DCE와 다름. 새 Gold 품질 이득 미검증 |
| V3_EXPERIMENTAL_NOT_IN_BASELINE | ExactSourceSpanBridge | local native/Canonical decision을 대체하지 않음. v2.3 local 표현이 불가능한 좌표의 확장에 사용. downstream feature regather에는 별도 사용 |

cross-window extension은 `sentence_cell`과 native 폭 계약으로 local 표현 가능성을
먼저 확인한다. local 후보는 구조적 rank와 v3 endpoint rank를 경쟁시키지 않는다.
중복 좌표에서는 v2.3 producer가 owner다. `GENERIC`은 새 5-type 계약에만
추가됐으며 옛 4-type 가중치·임계값을 자동 재사용하지 않는다.
문자 보정 후보는 TOP32 parent의 Canonical 점수를 사용하며, 이 점수가
보정된 문자 범위에서 별도로 검증됐다고 주장하지 않는다. Gold oracle의
semantic boundary residual 감독은 이 보정 경로와 연결된다.

## 작은 무학습 진단

동일한 이전 기사 `GNEWS-cd62da87b3b7f539bf205f9df7db8ff1`, seed 111,
합성 backbone, fresh core, 합성 0.0 source 정책으로 source-only 실행했다.
순서는 **Gold 수 / retrieval / fine scorer 입력 / fine 결과 / acceptance /
source inventory**다. Gold 좌표는 실행 뒤에만 join했다.

| 종류 | Gold | retrieval | fine 입력 | fine 결과 | acceptance | source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EVENT | 11 | 1 | 1 | 1 | 0 | 0 |
| STATEMENT | 8 | 0 | 0 | 0 | 0 | 0 |
| ENTITY | 12 | 12 | 12 | 12 | 5 | 5 |
| TIME | 6 | 6 | 6 | 6 | 6 | 6 |
| TRIGGER | 11 | 0 | 0 | 0 | 0 | 0 |

ENTITY는 bounded 9,649개, TIME은 9,781개를 모두 fine scorer에 전달했다.
두 lane의 article guard drop, source cap drop은 각각 0이다. Entity union은
28,811개 후보를 만들었고 앞뒤 후보 수가 같았다. 이 합성 gate에서 역할
37,899개와 Entity evidence 64,446개가 발생했다. source-only 요청은 약
6.88초, process peak RSS 약 1.50GB였고 backbone/DCE는 각 1회였다.
이 시간·메모리는 이 fixture와 이 실행 환경의 값이며 과거 v2.3 3.5초와
동등 비교할 수 없다. fresh weight의 최종 F1이나 0.0 gate 결과는 품질 근거가 아니다.
과거 같은 기사의 192 guard 경로에서 ENTITY가 12/12 → 1/12로 줄었던
손실은 새 실행에서 사라졌다. 남은 ENTITY 12 → 5 손실은 native acceptance 뒤다.

## 검증 경계와 후속 비교

`tests/test_v3_v23_source_baseline.py`는 source/replay 동일 결과, Gold 미주입,
local bounded 후보의 native 입력 전량 전달, cap·guard 부재, Trigger 없는
Event의 full runtime 존속, Trigger 없는 Event replay channel, Participant
무제한 forwarding, policy mismatch를 확인한다. `V3_WINDOW` 정책 및 D3 guard
회귀도 기존 fixture에서 확인한다. 문자 보정의 additive 후보와 원본 TOP32
보존을 포함해 관련 unittest 27개가 통과했다. 이 수정에서 학습, backward, optimizer step,
checkpoint 선택, threshold calibration은 하지 않았다.

read-only Gold 좌표 census는 train 73기사와 dev 15기사만 읽었다(test 접근 0).
EVENT 627개 중 sentence cell 부재 17개·cell 내 partial char 10개,
STATEMENT 808개 중 각각 64개·34개, ENTITY 1,492개 중 2개·50개,
TIME 1,358개 중 0개·13개, TRIGGER 627개 중 0개·8개였다.
이는 후보 도달률이 아니다. Trigger partial char 8개와 Participant role
partial char 30개를 위한 additive exact correction이 후속 작업에서 연결됐다.
원본 greedy/B2 후보는 유지되며 실제 predicted survival은 아직 측정하지
않았다. 자세한 census와 pair routing 적응은
`v23-pair-routing-migration.md`에 기록했다.

무학습 0.0 endpoint gate에서 생긴 매우 큰 Participant/Entity inventory는
downstream pair 계산량과 peak memory 위험을 보여 준다. 이 결과만으로 새
threshold 또는 guard를 채택하지 않는다. 새 Gold dev에서 checkpoint별 정책을
보정하고 동일 split·기사 순서·학습 노출량·후보 예산·시간 조건으로
`V23_BASELINE`과 `V3_WINDOW`를 비교해야 한다. shared DCE, shared
CandidateSpanEncoder, cross-window exact representation의 독립적 품질 이득도
미검증이다. 생성된 정책 artifact는 V23 v2 실행 순서와 endpoint provenance를
명시해야 하며 이전 V23 v1 artifact는 재사용할 수 없다.

## Participant forwarding K2 shadow 계약 (2026-09-25)

위 표의 무제한 Participant forwarding은 기존 `v23-baseline-source-funnel-v2`
artifact의 실행 의미다. B2 endpoint 수락 뒤 exact 좌표 중복을 제거하고
Event×role별 `extraction_score` 내림차순·좌표 오름차순으로 최대 2개만
전달하는 별도 `v23-baseline-source-funnel-v3-role-forwarding-k2` 실행 경로를
추가했다. 두 번째 Participant 수락 threshold는 없다. 선택된 filler만 ROLE
evidence와 Entity union에 들어간다. 새 경로는 별도 policy SHA가 있어야
실행되며 기존 v2 artifact를 같은 이름으로 재해석하지 않는다. 일반 요청은
raw B2 및 K 탈락 후보의 상세 trace를 만들지 않는다. 명시적 진단 요청에서만
별도 trace를 생성하고 PUBLIC projection에는 포함하지 않는다.

이 경로는 현재 **shadow 전용**이다. Phase 1 selected checkpoint와
Participant endpoint 0.75 shadow threshold의 dev15 비교에서 K2는 Entity
후보를 231,861→97,560개, H2 prospective fine pair를
6,009,034→2,296,322개로 줄였지만, Event owner가 일치하는 Gold
Participant exact hit도 60/142→12/142로 줄였다. 고정 Gold Entity pair
259개 중 source-reachable 10개와 complete-link cluster 37개 중 5개를
잃었다. 따라서 K2는 production V23 정책으로 채택하지 않았다. 상세
fixed-denominator 결과와 lineage는
[EOT의 K2 shadow report](../../../EOT/v3-runtime-optimization-2026-09/results/originals/training/results/v3-gold100-phase1-participant-forwarding-k2-shadow-v1/report.md)에 있다.
