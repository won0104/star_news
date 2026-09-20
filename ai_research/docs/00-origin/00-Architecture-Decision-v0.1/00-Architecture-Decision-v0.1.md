# Architecture Decision v0.1

## 결정

KF-DeBERTa를 새 프로젝트의 token/span backbone 후보로 채택하되 단일 final layer를 고정하지 않는다. Routing, token/span, directed pair, symmetric coreference가 각자 representation layer 또는 learned mix를 선택할 수 있는 계약을 먼저 만든다.

## 근거

동일 Gold, split, initialization, 기존 shared context/Head 구조로 재학습한 결과:

- 핵심 4-task 평균 macro-F1: legacy L12 `0.5496`, KF L10 `0.8260`, KF L12 `0.8229`
- sentence routing macro-F1: legacy L12 `0.8777`, KF L10 `0.8191`, KF L12 `0.7478`
- entity exact-span micro-F1: KF L12 `0.6243` > KF L10 `0.5577`
- time/semantic/trigger exact-span micro-F1: KF L10이 KF L12보다 높음

상세 계약과 한계는 [DirectionTest 보고서](../../DirectionTest/Report-KF-L10-L12-Cache-Head-Retraining-v1.md)에 기록한다.

## 두 선행 프로젝트에서 가져올 교훈

### ArticleLocal-KG

- Gold coverage, end-exclusive offset, cache manifest, split 고정은 유지한다.
- 16개의 supervision task 자체와 16개의 독립 Head 구현은 분리해서 판단한다.
- Candidate pair explosion, all-negative coreference/relation, evidence hard dependency를 반복하지 않는다.

### ArticleLocal-KG-GLiner

- GLiNER checkpoint보다 label/schema-conditioned scoring 아이디어를 우선 가져온다.
- Span, record, relation candidate와 최종 LocalKG graph 판단을 분리한다.
- Selection은 prior로만 사용하고 span을 삭제하는 hard gate로 사용하지 않는다.
- Coreference는 프로젝트 책임으로 유지한다.

## 초기 component 경계

```text
BackboneOutput
  └─ task-aware LayerAdapter
       └─ SharedDocumentContext
            ├─ SchemaConditionedSpanFamily
            ├─ DirectedPairFamily
            └─ SymmetricCoreferenceFamily

Predictions
  └─ ConsistencyRouter
       └─ MentionGraph
            └─ CoreferenceClustering
                 └─ ClusterGraphVerifier
                      └─ DeterministicMaterializer
```

`SchemaConditionedSpanFamily`의 label embedding은 ontology가 고정되어 있더라도 task 간 parameter sharing과 새 label ablation을 가능하게 하는 수단으로 사용한다. Open-label zero-shot 지원 자체를 목표로 삼지 않는다.

## 보류 사항

- Routing용 최적 layer/mix
- Fixed Head 대비 label-conditioned scorer의 데이터 효율
- Pair/coreference에 적합한 layer와 negative sampling
- Frozen, partial unfreeze, full fine-tuning의 비용 대비 이득
- Decoder threshold 및 overlap/MIX 정책
- End-to-end graph metric 통과 기준

이 항목은 `DirectionTest`에서 검증하기 전 production contract로 승격하지 않는다.
