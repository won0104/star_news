# ArticleLocal-KG v3 학습 하네스 (본학습 전)

project-free `ArticleLocal-KG-DeBERTa`의 v3 학습 코드와 설계 문서 사본입니다.
16단계 계획 중 **14/16 완료 시점**입니다.

- `v3_pretraining/` — 학습 하네스. 19개 task, 20개 loss 채널, 24 optimizer owner
- `docs/` — 계약·사용법·상태 문서. 시작점은 `docs/training-harness-usage.md`
- 추론측 코드는 `ai_research/baseline/v3/`에 있습니다
- 원본 커밋: `c3622a5ee7b9ac9c51c64b7d34054a1bd0ada18d`

**본학습은 아직 0회입니다.** smoke로 1 optimizer step만 검증된 상태이며
(`main_training: 0`, `optimizer_step: 0`, `tiny_fit: 0`),
현재 진행 상태의 기계 판독 원본은 `docs/execution-state.json`입니다.
