# ArticleLocal-KG v3.1 baseline (동결 코드 사본, 열람용)

`project-free/ArticleLocal-KG-DeBERTa/release/kf-deberta-base-kg-extractor-v3.1-gold100-mini-candidate-v3`의
모델·런타임 코드와 설정·계약 사본입니다. v3.0 베이스라인과 같은 방식으로
**학습된 weight(`weights/selected-phase6.pt`, 약 59MB)와 LFS 설정은 포함하지 않았습니다.**
따라서 이 디렉터리만으로 추론하거나 `verify_bundle.py`를 통과시킬 수는 없습니다.

이 베이스라인은 아래 원본 상태를 **그대로 동결**한 코드 열람본입니다.

- 원본 `release_version`: `3.1-project-candidate-d2-e1`
- 원본 `status`: `FROZEN_GOLD100_REHEARSAL_CANDIDATE`
- checkpoint: Gold100 train73/dev15 미니 리허설의 Phase 6, 1 epoch / 37 optimizer step,
  SHA-256 `6441484865c2c020e0a808b056eb9d991e0195d30c8342d6ff4789c01453c36f`
- `source_tree_mode=WORKING_TREE_SNAPSHOT`,
  `source_snapshot_sha256=69106c0ccdaa3326b9d28513fa0bc46b1b9fe1e903328a996c5c0508883f127e`
- 원본 manifest의 `service_ready=false`는 서비스 검증 상태이며,
  이 코드 베이스라인의 동결 여부와는 별개입니다

## v3.0 대비 주요 변경

기사의 source 후보를 제한된 예산 안에서 제안한 뒤, Trigger·Participant의 exact
span 점수로 수락 여부를 정합니다. 수락된 Native/ROLE Entity mention은 하나의
동일성 경로에서 묶고, 마지막에 선택된 Event·Entity로 PUBLIC graph를 만듭니다.

| 책임 | v3.1 동결본의 동작 |
|---|---|
| Trigger 선택 | boundary 점수는 후보 제안과 초기 gate에 사용합니다. 최종 순위·수락은 exact span의 `trigger.span_score`와 `TRIGGER_FINE`으로 결정합니다. |
| Participant 선택 | B2 endpoint와 bounded routing 뒤 `participant.span_score`가 ACTOR/TARGET/PLACE의 최종 수락·순위를 정합니다. 수락된 ROLE mention은 Native와 같은 Entity 동일성 경로에 들어갑니다. |
| Entity 동일성 | 학습·서빙이 `entity_pair_features.py`의 대칭 source feature를 공유합니다. 최종 pair 결정은 `MERGE_logit - KEEP_logit`을 D2 margin과 비교합니다. Native 근거가 없는 ROLE_ONLY mention도 merge되지 않으면 singleton Entity로 남을 수 있습니다. |
| PUBLIC 표시 | projection이 `r6-edge-confidence`에서 `r9-participant-accepted-role-only`로 바뀌었습니다. Entity resolution 뒤 역할 관계를 endpoint별로 정리하고 confidence 순으로 Event당 ACTOR 2개, TARGET 2개, PLACE 1개까지 표시합니다. |

Gold100 P6 checkpoint와 dev15에서 선정한 Trigger·Participant fine threshold,
Entity margin은 `config/d2.json`에 결합돼 있습니다. Entity margin은 명시적 KEEP
9쌍에 근거한 잠정 선정이고, `config/e1.json`의 운영 cap은 v3.0 값을 고정한
것으로 지연 시간 재검증 결과가 아닙니다. 자세한 선정 근거는 `config/`의
`selected-checkpoint.json`, `source-calibration-report.json`,
`entity-margin-selection.json`에 있습니다.

## 구성

| 경로 | 내용 |
|---|---|
| `models/`, `runtime/` | 모델·추론 코드 |
| `config/` | 선택된 D2/E1, source policy·acceptance, routing 및 calibration 근거 |
| `contracts/` | PUBLIC JSON schema와 출력·canonical text 계약 |
| `examples/inference.py` | 원본 번들 사용 예시 |
| `release-manifest.json` | 원본 파일·checkpoint·설정 SHA와 학습 provenance |

`README.md`는 E206용 설명으로 바꿨고, weight와 `.gitattributes`는 뺐습니다.
나머지 복사된 파일의 SHA-256은 원본 `release-manifest.json`과 일치합니다.
원본의 `source_git_commit`만으로는 파일 바이트를 식별할 수 없으며, 작업 트리
스냅샷 SHA와 파일별 SHA가 이 동결본의 기준입니다.

관련 학습 코드와 설계 자료는 `../../training/v3.1/`에 있습니다.
