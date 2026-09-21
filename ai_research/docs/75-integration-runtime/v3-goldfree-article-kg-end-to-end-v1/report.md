# V3 Gold-free Article → KG End-to-End Integration v1

## 판정

**END_TO_END_PARTIAL_KG_READY**

- READY_FOR_HF_V0_1_FINALIZATION = false
- corpus = fixed pilot_dev 15 + pilot_train 10 (25), pilot_test/original 1K dev/test 미사용
- Gold runtime/evaluation 사용 = 0
- canonical entry point = `runtime.ArticleLocalKGPipeline.from_config(...).run(article)`
- Neo4j = `NEO4J_RUNTIME_UNAVAILABLE`; database write 0

## STRUCTURAL

단일 API는 raw Article을 release-freeze `ArticleLocalRuntime`에 넣고, 그 canonical
result만 `ArticleLocalKGAssembler`에 전달한다. 호출자는 training/experiment adapter를
알 필요가 없다. 25개 모두 schema/serialization/deterministic replay를 통과했고 dangling,
duplicate ID, invalid endpoint, fake Entity, provenance 누락은 0이다. Event/Statement identity와
269개 raw ACTOR/TARGET/PLACE evidence가 보존됐다.
`NOT_RUN`은 `ABSENT`로 변환하지 않았고 unresolved filler로 role edge를 만들지 않았다.

기존 독립 프로젝트의 `ArticleConstructionResult`와는 article/version identity와 tensor-free
collection 경계가 부분적으로 호환되지만, legacy materialized Entity/Time/ontology dataclass와
직접 호환된다고 주장하지 않는다. 현재 판정은
`PARTIAL_WIRE_COMPATIBLE_NOT_DATACLASS_COMPATIBLE`이다.

## QUANTITATIVE

이는 정확도 지표가 아니라 Gold-free output density다. 25개에서 Event
308, Statement 197, Trigger
206, StatementType 197, raw
participant 269개를 만들었다. graph는 node
530, edge 505개다. 이전 정성 검토
대상의 Semantic/B2 core output parity는
25/25다.

## QUALITATIVE

고정 corpus 앞 10개를 성능과 무관하게 선택해 현재 Trigger/StatementType이 포함된 실제
graph를 다시 읽었다. 판정은 `KG_STRUCTURALLY_VALID_BUT_SEMANTICALLY_WEAK`이다. Event flow와
Statement/Event 분리는 일부 기사에서 유용하지만 proposition 누락·중복·경계 오류와
TARGET/PLACE spray, cross-Event leakage가 남아 있다. Trigger는 Event와 별도 evidence로
보존되며 B2 gate/feature가 아니다. inactive Entity/Time/resolution/relation lane은 모델
오류가 아니라 명시적 missing lane으로 집계했다. 상세 10개 판단은
`qualitative_review.json`, 원문과 현재 graph는 `graph_examples.json`에 있다.

## Neo4j

현재 환경에는 안전하게 사용할 Neo4j runtime 조건이 없어 DB write를 실행하지 않았다.
대신 canonical ARTICLE/EVENT/STATEMENT 및 COVERS/CONTAINS_STATEMENT만 포함하는
`neo4j_projection.json`과 idempotent `neo4j_import.cypher`를 만들었다. credential은 읽거나
기록하지 않았고 raw participant는 fake Entity로 변환하지 않았다.

## Gate 해석

`END_TO_END_PARTIAL_KG_READY`는 raw Article 한 건에서 deterministic partial KG JSON을
끝까지 만들 수 있다는 구조적 판정이다. semantic correctness나 production 품질 PASS가
아니다. Entity/Time/resolution/coreference/ABOUT/CAUSES/SUBEVENT_OF가 의도적으로
`NOT_RUN`이고, 기존 fixed-25 review의 semantic 약점도 유지되므로 HF v0.1 최종화는 아직
준비되지 않았다.

## 재현

```bash
cd ArticleLocal-KG-DeBERTa
ARTICLELOCAL_HF_CACHE=<hf-cache-root> PYTHONPATH=. \
  /opt/homebrew/Caskroom/miniforge/base/envs/model-test-py312/bin/python \
  training/scripts/run_v3_goldfree_article_kg_end_to_end.py prepare --device cpu

PYTHONPATH=. /opt/homebrew/Caskroom/miniforge/base/envs/model-test-py312/bin/python \
  training/scripts/run_v3_goldfree_article_kg_end_to_end.py finalize \
  --annotations training/results/v3-goldfree-article-kg-end-to-end-v1/qualitative_annotations.json

PYTHONPATH=. /opt/homebrew/Caskroom/miniforge/base/envs/model-test-py312/bin/python -m runtime \
  --config runtime/configs/goldfree-article-kg-pipeline-v1.json \
  --input release/kf-deberta-base-kg-extractor/examples/example_article.json \
  --output /tmp/article-local-kg.json --device cpu
```

Source config SHA: `881552d781136e274d17fb411349e52911072d03f9ca595a66eb35f2051b25ed`. 이 작업은 HF upload/최종화를
자동으로 시작하지 않는다.

## Git / cross-device handoff

- milestone commit: `b9e2a94` (`feat(runtime): complete gold-free article kg pipeline`)
- normal push: `UNPUSHED` — GitHub SSH `Permission denied (publickey)`
- required ignored milestone results: 개별 `git add -f`로 포함
- ignored cache/transient: `_full_graphs_source.json`, Python/pytest/HF/feature cache는 미추적
- pre-existing user artifacts: Curated RC directory와 architecture decision document는 이 commit에 섞지 않음
- `CROSS_DEVICE_CONTINUATION_READY=false`: remote push와 pre-existing Curated source의 별도 추적이 남음
