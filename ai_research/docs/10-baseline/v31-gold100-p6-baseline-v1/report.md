# v3.1 Gold100 P6 베이스라인 동결 기록

## 결론

Gold100 train73/dev15/test12에서 V23 경로의 v3.1 변경을 P1–P6까지 3 epoch씩
미니 리허설했다. 선택된 P6는 epoch 1이며, 해당 checkpoint와 dev15 source
threshold·Entity margin을 묶은 코드 베이스라인이
[`baseline/v3.1`](../../../baseline/v3.1/README.md)에 보존돼 있다. 원본 번들의
파일 192개 SHA, 독립 import, CPU PUBLIC smoke 및 405번 기사 MPS PUBLIC 2회가
통과했다는 기록이 있다. E206 사본은 인접한 v3.0 베이스라인처럼 weight를 제외한
코드 열람본이다.

판정 범위는 **베이스라인 코드 동결과 Gold100 미니 리허설·단일 기사 실행 관통**이다.
v3.0과 동일 조건의 성능 비교나 전체 dev15 predicted graph 품질, 서비스 지연 시간
승인을 이 결과로 주장하지 않는다. 원본 manifest의
`FROZEN_GOLD100_REHEARSAL_CANDIDATE`와 `service_ready=false`는 이 검증 범위를
기록한 값이다.

## 실험 계약과 변경된 실행 경로

| 항목 | 기록 |
|---|---|
| Gold / split | Gold100 train73 / dev15 / test12; 학습·선정·보정의 test 접근 0 |
| 리허설 실행 | MPS, seed 1008, 6개 phase 각각 3 epoch 학습; Gold SHA-256 `bd2db2b39a9a8d9d601d204688dd515b38ea5683353944fd18643e9cab2d95ac`, split SHA-256 `613f6a2add082ac71589633a78396ea1175088acf03b216ad3d3ce251b94ceed` |
| 단계 | P1 `extraction` → P2 `entity_role_time_attribution_sources` → P3 `entity_identity` → P4 `entity_role_time_attribution` → P5 `event_identity` → P6 `cluster_consumers` |
| 선택 epoch | P1–P6 순서로 3, 3, 3, 2, 2, 1 |
| P6 checkpoint | Phase `cluster_consumers`, 1 epoch / 37 optimizer step, SHA-256 `6441484865c2c020e0a808b056eb9d991e0195d30c8342d6ff4789c01453c36f` |
| 번들 출처 | `release/kf-deberta-base-kg-extractor-v3.1-gold100-mini-candidate-v3`; `WORKING_TREE_SNAPSHOT`, SHA-256 `69106c0ccdaa3326b9d28513fa0bc46b1b9fe1e903328a996c5c0508883f127e`; `source_git_commit`만으로 파일 바이트를 식별하지 않음 |

기사 입력은 bounded source 후보 제안 뒤 Trigger·Participant exact span 결정,
Native/ROLE Entity mention의 단일 identity 경로, PUBLIC graph 투영으로 이어진다.
v3.0과 비교해 Trigger boundary는 proposal/초기 gate로 남고
`trigger.span_score`가 최종 점수를 만든다. Participant도 endpoint gate 뒤
`participant.span_score`로 ACTOR/TARGET/PLACE를 수락한다. 수락된 ROLE_ONLY
mention은 Entity coreference에 참여하고, merge되지 않아도 singleton Entity로
남을 수 있다. Entity pair head는 학습·서빙에서 같은 대칭 source feature를 쓰며
`MERGE − KEEP` margin으로 결정한다. PUBLIC projection은
`r9-participant-accepted-role-only`로 바뀌었다. Entity resolution 후 Event별
역할 edge를 confidence 순으로 ACTOR 2개, TARGET 2개, PLACE 1개까지 표시한다.
자세한 설계 계약은
[`v31-trigger-entity-head-contract.md`](../../../training/v3.1/docs/v31-trigger-entity-head-contract.md)와
[`unified-entity-identity-v1.md`](../../../training/v3.1/docs/unified-entity-identity-v1.md)에 있다.

## 학습·선정 관찰

원본 미니 리허설의 최종 판정은 `MINI_REHEARSAL_PASSED_WITH_DYNAMICS_WARNINGS`다.
P1 Gold dev raw-score AP에서 Trigger는 epoch 1→3에 **0.2869→0.4411**,
Participant macro는 **0.6446→0.7402**였다. 이는 component raw-score 지표이며
predicted-cascade graph 품질 지표가 아니다. P6는 train loss가 감소하는 동안
dev 선택 metric이 epoch 1 이후 하락해 epoch 1이 선택됐다. P1·P2·P6의 모든
optimizer step에서 gradient clipping이 발생했다. 이 관찰만으로 원인을 특정하거나
1K 학습 결과를 예측하지 않는다.

P6 checkpoint 선택 후 dev15에서 아래 raw decision threshold를 골랐다.
P1 리허설 중 별도로 기록된 Trigger fine 보정값 대신, 이 동결본에는 P6
checkpoint에 결합된 값을 사용한다.

| 결정 | 점수·역할 | D2 값 |
|---|---|---:|
| `TRIGGER_ENDPOINT` | boundary endpoint proposal gate | 0.436429 |
| `TRIGGER_FINE` | `trigger.span_score` 최종 raw logit | 1.403719 |
| `PARTICIPANT_ENDPOINT` | B2 endpoint proposal gate | 0.409408 |
| `PARTICIPANT_FINE` | `participant.span_score` 최종 raw logit | 0.087154 |
| `ENTITY_COREFERENCE` | `MERGE_logit − KEEP_logit` margin | -1.112733 |

보정 접근 기록은 train 0/dev 15/test 0이다. Entity margin은 dev15에서 검색된
명시적 MERGE 81쌍·KEEP 9쌍에 근거한 **잠정 선정**이다. 판단 근거가 없는
36,640쌍은 제외됐고, Gold positive retrieval miss와 complete-link cluster merge
error는 이 점수의 검증 범위에 포함되지 않았다. E1 운영 cap은 v3.0 값을 고정했으며
현재 checkpoint의 지연 시간 재검증 결과가 아니다. 원본 수치는
[`config/d2.json`](../../../baseline/v3.1/config/d2.json),
[`config/e1.json`](../../../baseline/v3.1/config/e1.json),
[`entity-margin-selection.json`](../../../baseline/v3.1/config/entity-margin-selection.json)에
결합돼 있다.

## PUBLIC 실행 관통과 해석

원본 번들은 CPU PUBLIC smoke와 독립 import를 통과했다. 405번 기사 MPS 추론
2회는 각각 6.223초, 2.836초였고 동일한 PUBLIC SHA-256
`cbee27b17ac7a27b63af670c297c95970b786889d04325cc51b9dbe91e583385`를
남겼다. 두 번째 출력은 Article 1, Event 5, Statement 1, Entity 6, edge 24개다.
다섯 Event가 같은 문장을 중첩 구간으로 반복하고 일부 Entity 이름이 잘려 있어,
이 단일 smoke를 품질 승인으로 해석하지 않는다. PUBLIC의 `PERSISTENCE_READY`는
그 그래프의 구조적 저장 가능성을 뜻하며 번들 서비스 검증과 다르다.

## 보존 근거

- 원본 학습 기록: `project-free/ArticleLocal-KG-DeBERTa/training/results/v3-gold100-p1-p6-3epoch-mini-rehearsal-v2/report.md`
- 원본 번들·smoke 기록: `project-free/ArticleLocal-KG-DeBERTa/training/results/v31-gold100-mini-bundle-v1/report.md`와 `summary.json`
- E206의 [release manifest](../../../baseline/v3.1/release-manifest.json) SHA-256: `03236d9ce9f6eb08196f6e3a9a6a739814747559c88d2c990b4d05dc703fe9a7`
- E206의 [선택 checkpoint 기록](../../../baseline/v3.1/config/selected-checkpoint.json), [source calibration 기록](../../../baseline/v3.1/config/source-calibration-report.json), [학습·설계 자료](../../../training/v3.1/README.md)

원본 보고서는 52개 관련 unit test PASS를 기록한다. E206 이관 작업에서는
복사된 파일의 manifest SHA와 weight 제외 상태를 확인했으며, E206 사본에서
모델 추론을 실행하지 않았다.
