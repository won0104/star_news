# ArticleLocal-KG v3.1 동결본의 학습·설계 자료

v3.1 동결 코드 베이스라인은 `../../baseline/v3.1/`에 있습니다. 이 경로는 그 사본에 포함되지 않은
학습 하네스, 설계 계약, 후보 생성·보정 스크립트를 함께 보존합니다. 복사한 파일의 SHA-256과
출처는 `snapshot-manifest.json`에 기록했습니다.

- `v3_pretraining/`과 기본 `docs/`는 `project-free/ArticleLocal-KG-DeBERTa`
  커밋 `f3ba31074d6234f59f9f8a390c67c85187c8f9f9`의 추적 파일입니다.
- `scripts/`의 후보 생성기·Gold100 P6 calibration 스크립트와
  `docs/v31-release-build.md`는 번들 생성에 사용된 원본 작업 트리의 바이트를
  별도 SHA-256으로 고정했습니다.
- 선택된 P6 checkpoint의 SHA, D2/E1, source calibration과 Entity margin 근거는
  `../../baseline/v3.1/release-manifest.json` 및 베이스라인의 `config/`에 있습니다.

## v3.1 학습·계약 변경

| 책임 | 기록된 변경 |
|---|---|
| Trigger exact 결정 학습 | Gold exact span을 양성으로, N1 boundary mismatch를 구조적 음성으로 학습합니다. boundary는 proposal이고 exact head가 최종 점수를 냅니다. 자세한 계약은 `docs/v31-trigger-entity-head-contract.md`에 있습니다. |
| Participant fine 결정 학습 | in-window `participant.span_score` 손실을 최종 Participant loss에 연결했습니다. 수락된 ROLE mention은 Native와 동일한 Entity identity 경로를 따릅니다. `docs/unified-entity-identity-v1.md`에 ROLE_ONLY lifecycle이 설명돼 있습니다. |
| Entity pair 학습 | 학습·서빙의 feature 생성 함수를 공유하고 source router 후보·유사 표면·근접 pair 등 어려운 음성을 우선 표집합니다. 가능한 경우 음성 예산의 최소 10%는 결정적 random 표집으로 남깁니다. |
| 동결 근거 | `scripts/`에 후보 생성·Gold100 P6 calibration 스크립트를, 베이스라인의 `config/`에 선택 checkpoint·source calibration·Entity margin 기록을 보존했습니다. |

복사한 설계 문서에는 threshold **선정 전**의 작업 항목도 남아 있습니다.
이 동결본에서 실제로 결합된 checkpoint와 threshold의 기준은 베이스라인의
`release-manifest.json`과 `config/d2.json`, `config/e1.json`입니다.

원본 번들의 상태는 `FROZEN_GOLD100_REHEARSAL_CANDIDATE`입니다. Gold100
train73/dev15 리허설의 P6 checkpoint를 사용하며, Trigger·Participant fine
threshold는 dev15에서 선택됐습니다. Entity margin의 명시적 KEEP 근거는 9쌍이고
E1 cap은 이전 값을 고정했습니다. 원본의 `service_ready=false`는 서비스 검증
상태이며, 이 코드와 artifact가 동결됐는지 여부와는 별개의 기록입니다.

이 자료는 원본의 경로를 유지한 열람용 사본입니다. E206 베이스라인에는 weight가
없어 추론·번들 검증은 원본에서 수행해야 합니다. 이전 v3.0 학습 자료는 `../v3/`에
보존돼 있습니다.
