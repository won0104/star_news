# ArticleLocal-KG 연구 기록

뉴스 기사 한 건에서 `Event`, `Statement`, `Entity`, `Time`과 이들 사이의 관계를 추출해
article-local Knowledge Graph로 구성하는 모델의 연구·설계·실험 기록입니다.
`project-free` 레포지토리의 연구 문서 중, 현재 구조의 설계 근거와 판단 과정을
추적하는 데 필요한 문서만 선별해 옮겼습니다.

- 초기 이관 당시 원본 연구 문서: 267건
- 연구 기록: 초기 선별 47건 + v3.1 베이스라인 실험 요약 1건
- 게시된 릴리스: v2.3
- Hugging Face: [kf-deberta-base-kg-extractor](https://huggingface.co/sysy9292/kf-deberta-base-kg-extractor)

코드 열람용 동결 베이스라인은 [v3.0](../baseline/v3/README.md)과
[v3.1](../baseline/v3.1/README.md)에 있다. v3.1의 Gold100 P6 실험 판정과
검증 범위는 [베이스라인 동결 기록](10-baseline/v31-gold100-p6-baseline-v1/report.md)에
따로 정리했다. 베이스라인 동결은 게시된 릴리스나 서비스 검증을 뜻하지 않는다.

이 문서들은 최종 구조만 정리한 명세서가 아니라, 어떤 가설을 검토했고 무엇을
기각·채택했는지까지 포함한 연구 기록입니다. 반복 실험, 단순 재검수본, 중간 산출물은
제외하고 설계 결정이나 후속 작업에 영향을 준 결과를 중심으로 남겼습니다.

문서의 디렉터리 구조는 원본 위치와 동일하지만, 원본의 상대 링크와 실행 당시
로컬 경로는 동작하지 않습니다. 학습 체크포인트와 캐시는 `project-free`에만 있어
이 문서들만으로 실험을 재현할 수는 없습니다.

## 연구 흐름

전체 연구 흐름을 압축하면 다음과 같습니다.

```text
Backbone 후보 비교
→ layer 재검증 및 KF-DeBERTa 채택
→ learned layer mix / span representation 설계
→ multitask baseline
→ argument / relation 구조 실험
→ Gold coverage 문제 확인
→ semantic scope 확장과 calibration 문제 발견
→ validity / scope 책임 분리
→ canonical span representation 동결
→ Gold 95 → 380 scaling
→ entity / participant / event coreference / time 통합
→ article-local KG runtime
→ public output contract
→ v2.1 → v2.2 → v2.3 release
→ v3.0 동결 코드 베이스라인
→ v3.1 Gold100 P1–P6 리허설·코드 베이스라인
```

대표적인 정량 결과는 #40 Gold Scaling Study입니다.

- 외부 exact F1: `0.092346 → 0.139691` (Gold 95 → 380)
- `PERFORMANCE_SCALING_SUPPORTED=true`
- `STRONG_V3_SCALING_SUPPORT=false`

여기서 exact F1은 단순 span F1이 아니라 nested span과 relation을 포함한 KG 전체 구조의
exact match 기준입니다. 부분 정답은 0으로 취급합니다.

## 처음 읽는다면

1. [백본 역전](00-origin/direction-test/Report-KF-L10-L12-Cache-Head-Retraining-v1/Report-KF-L10-L12-Cache-Head-Retraining-v1.md) — 왜 KF-DeBERTa를 사용하게 되었는가
2. [#35 책임 분리 아키텍처](30-semantic/v3-semantic-responsibility-split-architecture-v2/report.md) — 현재 semantic 구조의 핵심 설계 결정
3. [#40 Gold 스케일링](70-gold-scaling/v3-frozen-gold-scaling-study-v1/fixed-dev39-final-unblock/report.md) — 데이터 증가가 실제 성능 향상으로 이어졌는가
4. [HF Public Output Contract V2](80-release-v2/hf-public-output-contract-v2/report.md) — 서비스가 실제로 소비하는 출력 구조
5. [#41 Socket Replay](30-semantic/v3-jointspanproposer-v3-socket-replay-v1/report.md) — v2.3 이후에도 남아 있는 핵심 문제
6. [v3.1 Gold100 P6 베이스라인](10-baseline/v31-gold100-p6-baseline-v1/report.md) — 새 head 결정 경로, 리허설·보정·PUBLIC 실행의 근거와 한계

## 전체 목록

### 00-origin — 백본과 최초 계약
| 문서 | 내용 |
|---|---|
| [Architecture Decision v0.1](00-origin/00-Architecture-Decision-v0.1/00-Architecture-Decision-v0.1.md) | KF-DeBERTa 채택, 단일 final layer 미고정 |
| [Learned Mix Decision v0.2](00-origin/01-Learned-Mix-Decision-v0.2/01-Learned-Mix-Decision-v0.2.md) | task별 layer/mix 선택 계약 |
| [Semantic Span Layer Decision v0.3](00-origin/02-Semantic-Span-Layer-Decision-v0.3/02-Semantic-Span-Layer-Decision-v0.3.md) | semantic span 레이어 결정 |
| [Span Architecture Decision v0.4](00-origin/03-Span-Architecture-Decision-v0.4/03-Span-Architecture-Decision-v0.4.md) | span 구조 결정 |
| [KF-DeBERTa vs KLUE-RoBERTa](00-origin/direction-test/Report-KF-DeBERTa-vs-Legacy-KLUE-RoBERTa-v1/Report-KF-DeBERTa-vs-Legacy-KLUE-RoBERTa-v1.md) | frozen probe에서 **기각** (0.5032 vs 0.5931) |
| [L10/L12 Cache + Head 재학습](00-origin/direction-test/Report-KF-L10-L12-Cache-Head-Retraining-v1/Report-KF-L10-L12-Cache-Head-Retraining-v1.md) | 레이어 바꾸자 **역전** (0.8260 vs 0.5496) |

### 10-baseline / 15-augmentation
| 문서 | 내용 |
|---|---|
| [Full Multitask Baseline v1](10-baseline/08-Full-Multitask-Baseline-v1/08-Full-Multitask-Baseline-v1.md) | 이후 모든 비교의 기준선 |
| [v3.1 Gold100 P6 베이스라인 동결 기록](10-baseline/v31-gold100-p6-baseline-v1/report.md) | P1–P6 리허설, dev15 threshold·Entity margin, PUBLIC smoke 및 검증 범위 |
| [Synthetic Augmentation Utility v1](15-augmentation/10-Synthetic-Augmentation-Utility-v1/10-Synthetic-Augmentation-Utility-v1.md) | 합성 증강 유용성 판정 (종결) |

### 20-argument-relation — 구조에서 데이터로
| 문서 | 내용 |
|---|---|
| [Relation Ontology Migration v1](20-argument-relation/09-Relation-Ontology-Migration-v1/09-Relation-Ontology-Migration-v1.md) | relation 온톨로지 정의 |
| [#19 True Relation-Head Factorization](20-argument-relation/19-Argument-True-Relation-Head-Factorization-Ablation-v1/19-Argument-True-Relation-Head-Factorization-Ablation-v1.md) | `INCONCLUSIVE` → gold 감사 요구 |
| [#20 ACTOR Gold Coverage Audit](20-argument-relation/20-Argument-ACTOR-Gold-Coverage-Audit-v1/20-Argument-ACTOR-Gold-Coverage-Audit-v1.md) | **데이터로 전환한 지점** |
| [causes C1 Mechanism Falsification](20-argument-relation/v3-relation-causes-c1-mechanism-falsification-v1/report.md) | `CURRENT_DATA_INSUFFICIENT` |
| [ABOUT Contract Audit](20-argument-relation/v3-about-contract-audit-v1/report.md) | ABOUT 관계 계약 |

### 30-semantic — calibration 붕괴와 책임 분리
| 문서 | 내용 |
|---|---|
| [#31 Scope Aux Gradient Attribution](30-semantic/v3-semantic-scope-aux-gradient-attribution-audit-v1/report.md) | 원인은 DCE가 아니라 verifier |
| [#32 Verifier Calibration Drift](30-semantic/v3-semantic-verifier-calibration-drift-audit-v1/report.md) | drift가 boundary 경로를 따라감 |
| [#34 Frozen-A Scope Scorer Feasibility](30-semantic/v3-semantic-proposition-scope-scorer-feasibility-v1/report.md) | 분리된 scorer에서 신호 확인 |
| [#35 Responsibility Split Architecture v2](30-semantic/v3-semantic-responsibility-split-architecture-v2/report.md) | validity/scope 물리적 분리 |
| [#36 Responsibility Split Training v2](30-semantic/v3-semantic-responsibility-split-training-v2/report.md) | 분리 구조 학습 |
| [#38 Canonical Span Representation Freeze](30-semantic/v3-canonical-span-representation-architecture-v1/report.md) | **표현 동결** |
| [#39 TRAIN196 Controlled Evaluation](30-semantic/v3-canonical-span-representation-train196-eval-v1/report.md) | 동결 표현 학습·평가 |
| [#41 JointSpanProposer Socket Replay](30-semantic/v3-jointspanproposer-v3-socket-replay-v1/report.md) | #40 재현, cross-corpus 문제 잔존 |

### 40-entity / 45-participant / 50-event-coreference / 60-time
| 문서 | 내용 |
|---|---|
| [Entity Overlap / Nested Audit](40-entity/v3-entity-overlap-audit-v1/report.md) | nested 문제 정의 |
| [Entity Mention Completion](40-entity/v3-entity-mention-completion-v1/report.md) | nested-capable 추출 |
| [Soft-Priority Runtime Promotion](40-entity/v3-entity-candidate-restriction-soft-priority-promotion-v1/report.md) | 최종 채택 형태 |
| [Entity Identity + Participant Resolution](40-entity/v3-entity-identity-participant-resolution-v1/report.md) | ENTITY 노드 동일성 |
| [Participant Architecture Fair Comparison v2](45-participant/v3-participant-architecture-fair-comparison-v2/report.md) | 구조 비교 |
| [Participant Safe Supervision Contract](45-participant/v3-participant-safe-supervision-contract-v1/report.md) | supervision 계약 |
| [Event Identity Coreference](50-event-coreference/v3-event-identity-coreference-v1/report.md) | 사건 동일성 |
| [Event Coref Calibration Prior](50-event-coreference/v3-event-coreference-calibration-prior-v1/report.md) | 보정 |
| [Time Contract Decision Audit](60-time/v3-time-contract-audit-v1/report.md) | 시간 계약 결정 |
| [Generic TimeExpression Completion](60-time/v3-generic-time-expression-completion-v1/report.md) | 시간 표현 + 사건 연결 |
| [TimeExpression Normalization Contract](60-time/v3-generic-time-expression-completion-v1/normalization_contract.md) | 기사 상대 정규화 규약 |

### 70-gold-scaling — 라벨과 데이터
| 문서 | 내용 |
|---|---|
| [#40 Gold Scaling Study (final)](70-gold-scaling/v3-frozen-gold-scaling-study-v1/fixed-dev39-final-unblock/report.md) | Gold 95→380, exact F1 0.0923→0.1397 |
| [Annotation Guideline RC v3](70-gold-scaling/gold-v3-work/round01-03-curated-rc1/guideline_rc_v3.md) | 최종 라벨링 기준 |
| [Training Gold 380 (consolidated)](70-gold-scaling/gold-v3-work/consolidated/training-gold-380-r01-07-r10-v1/report.md) | 최종 학습 Gold 구성 |
| [Article Corpus Audit](70-gold-scaling/corpus-audits/ARTICLE_CORPUS_AUDIT.md) | 코퍼스 출처 |
| [GNews Input Eligibility Audit](70-gold-scaling/corpus-audits/GNEWS_INPUT_ELIGIBILITY_AUDIT.md) | 입력 적격성 |

### 75-integration-runtime / 80~95 release
| 문서 | 내용 |
|---|---|
| [EventFrame Architecture Decision Gate](75-integration-runtime/v3-eventframe-architecture-decision-gate-v1/v3-eventframe-architecture-decision-gate-v1.md) | 통합 아키텍처 결정 |
| [Graph Assembly Input Contract](75-integration-runtime/v3-eventframe-runtime-consolidation-v1/graph_assembly_input_contract.md) | 그래프 조립 입력 규약 |
| [Gold-free Article KG End-to-End](75-integration-runtime/v3-goldfree-article-kg-end-to-end-v1/report.md) | 실제 기사 전 구간 동작 |
| [ArticleLocal-KG Qualitative Review](75-integration-runtime/v3-articlelocal-kg-qualitative-review-v1/report.md) | 정성 평가 |
| [**HF Public Output Contract V2**](80-release-v2/hf-public-output-contract-v2/report.md) | node/edge 닫힌 집합 — 서비스 연동 기준 |
| [Runtime Release Milestone](80-release-v2/runtime-release-milestone/2026-09-07-runtime-release-milestone.md) | v2 릴리스 시점 |
| [v2.1 Public API Release Validation](90-release-v21/release-v21-public-api-release-validation-v1/report.md) | API 검증 |
| [v2.2 CPU Bottleneck Profile](92-release-v22/performance-profile/bottleneck-report.md) | 성능 병목 |
| [v2.3 Final Validation Summary](95-release-v23/release-v23/final-validation-summary.md) | 최종 검증 |
| [v2.3 Publish Summary](95-release-v23/release-v23/publish-summary.md) | 배포 요약 |
