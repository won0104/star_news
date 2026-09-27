# V23 Trigger · Entity identity 학습/서빙 계약

현재 master의 `V23_BASELINE` 학습·서빙 경로에 적용한다. 별도 v3.1 model mode,
병렬 head, Gold/schema/guideline 변경은 없다. 기존 EventIdentityHead와
complete-link closure는 이번 변경 대상이 아니다.

## 구현 전 확인한 충돌 지점

| 위치 | 기존 실행 의미 | 현재 계약 |
|---|---|---|
| `training/v3_pretraining/extraction.py` | V23 in-window Trigger의 `span_score` 학습이 빠지고 endpoint가 양성 위주였다 | 모든 Gold Trigger exact span을 양성으로, N1 boundary mismatch만 구조적 음성으로 학습한다. 잘못된 N1 start/end는 boundary 음성이다 |
| `runtime/v3_pretraining/extraction_decode.py` | V23 in-window Trigger 최종 점수는 boundary rank였고 exact state 대신 0 state를 보관했다 | boundary는 후보 제안과 cheap gate만 담당한다. bounded 후보의 exact feature를 한 번 얻어 `trigger.span_score`가 최종 점수와 순위를 담당한다 |
| `runtime/v3_pretraining/serving.py` | V23 Trigger는 fine threshold 없이 cap만 적용했다 | `TRIGGER_FINE`은 raw `trigger.span_score`에 적용한다. endpoint gate와 별개다 |
| `models/v3_pretraining/entity_heads.py`, `training/v3_pretraining/entity.py`, `runtime/v3_pretraining/entity_scoring.py` | fine pair head는 대칭 3개 representation channel과 4개 수동 policy scalar를 받았고 학습·서빙 feature 구성은 중복됐다 | 대칭 `left+right`, `abs(left-right)`, `left*right`, document channel과 공유 source-only primitive feature를 사용한다 |
| `training/v3_pretraining/entity.py` | DISTINCT_KNOWN_GOLD_ENTITY_IDS 음성을 거의 균일 표집했다 | 같은 label authority를 유지하고 실제 source router 후보, 표면 유사성, 같은 type·근접성, Native/ROLE 혼합 순으로 어려운 음성을 우선한다. 나머지는 결정적 random 표집이다 |

## 실행 책임

Trigger boundary는 proposal/cheap gate다. 좌표 dedup과 bounded routing 후
`trigger.span_score`가 exact span의 final rank/acceptance producer다. 두 점수를
합산하지 않는다. raw logit의 `[0,1]` confidence 변환은 기존 clamped sigmoid를
한 번 적용한다. V23 문자 보정으로 다른 exact 좌표가 생긴 경우에는 그 extension의
exact feature를 다시 얻어 같은 head로 점수화한다. `TRIGGER_FINE`은 재학습 후 dev에서 고를 때까지 미선정이며
서빙은 fail closed다. 기존 P6 checkpoint는 변경된 Entity head 입력 크기와
학습 책임을 충족하지 않는다.

Entity pair feature 순서와 버전은
`runtime/v3_pretraining/entity_pair_features.py`의
`ENTITY_PAIR_FEATURE_NAMES` 및 `ENTITY_PAIR_FEATURE_VERSION`이 소유한다.
Gold 학습, predicted-source replay, 서빙이 같은 함수를 호출한다. Gold Entity ID는 label authority로만 쓰며,
router의 aggregate rank는 fine feature가 아니다. type unknown과 type conflict를
구별하고 conflict를 hard rejection으로 사용하지 않는다. ROLE_ONLY singleton과
Native/ROLE 혼합 candidate는 기존 lifecycle대로 남는다. runtime decision은
`MERGE_logit - KEEP_logit >= margin`이고 margin은 재학습 후 dev에서
MERGE precision과 cluster merge error를 기준으로 다시 선정한다.
Hard-negative 표집은 source router 후보와 유사 pair를 우선하되, 가능한 경우
negative budget의 최소 10%를 결정적 random remainder에 남긴다.

## Trigger 부착 정책의 실제 경로

현재 V23 serving은 `V3ServingWorker._analyze_owned`에서
`attach_optional_triggers`를 호출한다. 이 함수는 Event에 포함된 후보 중
`(-row.score, row.start, row.end)` 최소값, 즉 최고 점수를 선택한다.
`row.score`와 `DecodedSourceSpan.extraction_score`는 같은 exact decision
logit이며, accepted 후보만 부착 함수에 전달된다.
`runtime/eventframe/trigger.py`의 nearest-start와
`v3-trigger-attachment-diagnostic-v1`의 `_nearest_trigger`는 별도 과거 경로다.
이번 패치는 부착 함수와 EventIdentityHead를 바꾸지 않는다. 다만 최종
Trigger score producer가 boundary에서 exact decision으로 바뀌므로 최고 점수
규칙의 입력 점수도 바뀐다. 재학습 후 동일 후보 집합에서
`CURRENT_HIGHEST_EXACT_SCORE`, `NEAREST_EVENT_START`, `NEAREST_EVENT_END`를
고정 정책으로 비교하고 하나를 선택한다. learned attachment head는 추가하지 않는다.
현재 V23 부착 함수는 same-sentence를 별도로 검사하지 않고 Event 포함 좌표만
검사한다. 이는 알려진 geometry 한계이며 이번 패치에서는 변경하지 않는다.

## 재학습과 선정 전 남은 작업

- Phase 1–6 재학습에서 Trigger exact/boundary 및 기존 Participant fine loss의
  optimizer gradient와 checkpoint provenance를 확인한다.
- 1K main training 이후 dev에서 `TRIGGER_FINE`, `PARTICIPANT_FINE`, Entity
  `MARGIN_GTE` threshold를 선정하고 D2를 새 checkpoint SHA에 결합한다.
- E1을 재검증한 뒤 번들 생성기와 loader의 checkpoint/source SHA binding을
  새 선택 artifact에 맞춘다. 현재 v3.0 SHA를 가진 기본 생성 인자는 사용하지 않는다.
- EventIdentityHead의 GOLD_ORACLE→predicted feature shift와 hard-negative
  coverage는 별도 감사 대상으로 남긴다.
