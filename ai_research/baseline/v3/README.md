# ArticleLocal-KG v3 baseline (동결 번들, 코드 열람용)

project-free `ArticleLocal-KG-DeBERTa/release/kf-deberta-base-kg-extractor-v3-main`의 사본입니다.
한국어 뉴스 기사 한 편에서 Event·Statement·Entity·Time을 추출해 **Event-centered Article-local KG**를
PUBLIC JSON graph로 반환하는 v3 동결 번들입니다.

**학습된 weight(`weights/selected-phase6.pt`, 약 61MB)는 포함하지 않아 이 디렉터리만으로는 실행되지 않습니다.**
같은 이유로 `verify_bundle.py`도 weight 누락으로 실패합니다.
v3 weight의 Hugging Face 배포 기록은 아직 없습니다.

- 원본 커밋(번들 freeze): `7c56f0bc` — Freeze v3 bundle with PUBLIC edge confidence
- `release_version`: `3.0-project-final-d2-e1`, `status`: `FROZEN_USER_SELECTED_D2_E1`
- checkpoint: Phase 6 `cluster_consumers`, 3 epoch / 471 optimizer step,
  sha256 `87bc8b000490ebfff71287cbbe5c05605c02243178dc6411ac22a088eccb2acf`
- 검증 상태: `service_validation_status=PROVISIONAL_NOT_PREDICTED_VALIDATED`,
  `source_validation_status=PROVISIONAL_ENGINEERING_ONLY`
- Backbone `kakaobank/kf-deberta-base`는 번들에 없으며 revision
  `363b171d71443b0874b0bf9cea053eb5b1650633`에 고정됩니다

## 구성

| 경로 | 내용 |
|---|---|
| `models/`, `runtime/` | 모델·추론 코드. 진입점은 `runtime/v3_pretraining/project_release.py`의 `load_project_release_worker` |
| `config/` | 사용자가 선택한 D2 threshold, E1 운영 cap, source policy·acceptance, active routing |
| `contracts/` | PUBLIC JSON schema, 출력 계약, canonical text 정책 |
| `examples/inference.py` | 기사 JSON 하나로 PUBLIC 경로를 실행하는 예시 |
| `release-manifest.json` | 모든 파일·checkpoint·config SHA와 학습 provenance |

`README.md`를 제외한 파일은 `release-manifest.json`의 `files_sha256`과 일치합니다.
`README.md`는 원본 번들의 모델 카드 대신 이 문서로 바꿨고, weight와 LFS 설정(`.gitattributes`)은 뺐습니다.

학습 하네스와 설계 문서는 `ai_research/training/v3/`에 있습니다.
