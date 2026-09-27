# ArticleLocal-KG v3 학습 하네스와 설계 문서

project-free `ArticleLocal-KG-DeBERTa`의 v3 학습 코드와 설계 문서 사본입니다.
`ai_research/baseline/v3/`의 동결 번들과 같은 커밋(`7c56f0bc`) 기준입니다.

- `v3_pretraining/` — 학습 하네스. 16단계 계획의 fresh-init 하네스 위에
  dependency DAG 단계별 학습(`staged.py`), Gold400 schedule, epoch 선택, predicted source replay가 추가됐습니다
- `docs/` — 계약·사용법·상태 문서. 시작점은 `docs/training-harness-usage.md`
- 추론측 코드는 `ai_research/baseline/v3/`에 있습니다

`docs/execution-state.json`은 16단계 사전 계획의 진행 기록이며, 그 뒤의 단계별 본학습 상태는 담고 있지 않습니다.
동결 checkpoint의 학습 provenance는 `ai_research/baseline/v3/release-manifest.json`의 `training_provenance`를 보세요.

## 구조·최적화 결정 문서

v3 구조를 바꾸거나 최적화 방향을 정한 문서입니다.

| 문서 | 내용 |
|---|---|
| [dag-staged-training-v1.md](docs/dag-staged-training-v1.md) | 전체 head 동시 학습에서 dependency DAG 단계별 학습으로 전환 (v1 계약) |
| [p5-p6-event-head-split-v1.md](docs/p5-p6-event-head-split-v1.md) | P5 Event identity와 P6 Primary의 feature 경계 |
| [unified-entity-identity-v1.md](docs/unified-entity-identity-v1.md) | Native·Participant 두 경로의 Entity identity 결정을 하나로 통합 |
| [v3-frozen-feature-cache.md](docs/v3-frozen-feature-cache.md) | frozen KF-DeBERTa feature를 run 안에서 재사용해 반복 backbone 실행 제거 |
| [optimization-history.md](docs/optimization-history.md) | 2026-09-24~27 V3/V23 최적화의 채택·기각 이력 |

`optimization-history.md`는 project-free `EOT/v3-runtime-optimization-2026-09/docs/`에서 가져온 문서이고,
나머지는 `ArticleLocal-KG-DeBERTa/docs/v3-pretraining/`에서 가져왔습니다.
원본의 상대 링크는 이 레포에서 동작하지 않습니다.
