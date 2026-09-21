# V3 본학습 이전 단계 1: 현재 실행 기준 지도

기준: 로컬 `master` HEAD `d756efb1953619a4a1a9b0e1d01c2f98e23eebbf`, 2026-09-20. 이 문서는 코드와 고정 rc2의 **연결 상태**를 기록한다. 이후 v3 구현 또는 성능 승인으로 읽지 않는다. 경로는 저장소 루트 기준이다. 파일별 SHA와 보호할 Gold 목록은 `source-manifest.json`에 있다.

## 주 실행 경로와 소유권

1. 기사 요청 진입(`ArticleLocalKGPipeline.from_config/run`, `runtime/pipeline.py`)이 기본 `runtime/configs/goldfree-article-kg-pipeline-v22.json`을 읽는다. 설정의 runtime ID와 compact assembler ID를 대조한다. 기본 `PUBLIC` 호출은 `ArticleLocalRuntime.run_compact`로 연결된다. 명시적 구형 assembly 설정을 선택하면 별도 legacy `run`/assembler 경로가 있다.
2. 본문 정렬과 표현 생성(`RuntimePreprocessor`, `SharedBackboneProvider`, `runtime/eventframe/runtime.py`, `runtime/eventframe/features.py`)은 caller의 `ArticleInput`을 `ArticleRunScope`에 두고 pinned KF backbone에서 L8/L10/L12를 얻는다. `models/backbone.py`의 `_RequiredLayerCapture`가 선택층만 잡고 종료 시 context를 지운다. `models/context.py`의 `CandidateSpanEncoder.forward_runtime_direct`는 후보가 참조하는 문장과 층을 gather한다.
3. 의미 후보 및 속성 추출(`runtime/eventframe/runtime.py`의 component wrappers)은 semantic Event/Statement, trigger, participant, entity, time, statement type을 만든다. Entity/Time 후보 제한과 Participant→Entity/Event→Time 라우팅은 `runtime/candidate_routing/integrated.py`가 고정 정책을 제공할 때 적용된다. `ArticleLocalBoundedCandidate.run`은 실제로 다섯 bounded policy를 `pipeline.run`에 전달한다. 기본 개발 파이프라인을 policy 없이 직접 부르는 호출과 구별한다.
4. article-local 동일성 종료(`FixedEventIdentityRuntime.run`, `runtime/eventframe/event_identity.py`)는 `EventFeatureBundle`과 pair scorer, complete-link, B3 closure를 사용해 `EventIdentityClosure`/LocalEvent ID를 확정한다. `runtime/eventframe/runtime.py`는 그 뒤 `IdentityResolutionHandoff`와 `EventRoleFeatureHandoff`를 `release()`하고 raw EventFrame 참조를 비운다. 이 지점은 현재 identity의 마지막 tensor 소비 지점이며, 새 Primary·relation consumer를 붙일 때 그대로 마지막 소비라고 가정할 수 없다.
5. 공개 그래프 조립(`build_resolved_graph_state` → `CompactArticleLocalKGAssembler.assemble`, `runtime/graph/compact_assembly.py`)은 scalar/grounding/ID를 가진 `ResolvedGraphState`에서 Time V2 파생, node/edge 생성, 원문 offset 검증, profile projection을 수행한다. `runtime/lifecycle.py`의 `ArticleRunScope.close`가 요청 소유 표현을 비운다. `runtime/graph/neo4j.py`는 offline projection/Cypher 준비 코드이며 DB 연결을 열지 않는다.

이 흐름은 소스 연결과 rc2의 과거 72기사 실행 기록으로 확인했다. 이번 단계의 모델 로드와 기사 추론은 0이다. 새 v3 요구 기능의 실행 성공을 뜻하지 않는다.

## rc2 최적화와 시간 순서

`release/kf-deberta-base-kg-extractor-v2.3-rc2/`의 153개 manifest 대상 파일 및 self manifest를 포함한 154개 파일 재고, 12개 checkpoint, source mapping, config/schema, isolated import가 `scripts/validate_bcr_v23_rc2_static.py`에서 PASS였다. tree SHA-256은 `0214782141eef30d3b57a8b74aaca812788b0f644cfad14c59208b507787eb8b`이며 Git tree SHA가 아니다. 현재 개발 `models/**/*.py`와 `runtime/**/*.py`의 tree hash는 각각 rc2 검증에 기록된 `552d49db78b941be030c0d0670e2138bb0e9b05d364efed8ae1ddac411e4b0f8`, `b7d8c7c6316e3ae8de8906c9dfd1028fd0e7f053a865cd6afd496f12af132bf5`와 같다. 개발/runtime config는 release-local artifact 경로 등의 차이가 있다.

선택층 포착은 `models/backbone.py`의 `output_hidden_states=False`, L8/L10/L12 hook, `finally` cleanup에 연결된다. all-valid view와 padded scatter 선택은 같은 파일의 `KFDeBERTaBackbone.forward`에 있다. 단일/혼합층 direct gather는 `models/context.py`의 `_gather_single_layer_sentences`/`_gather_mixed_layer_sentences`와 Entity/Time/Statement/B2 등의 `forward_runtime_direct` 호출에 있다. bounded routing은 `runtime/candidate_routing/integrated.py`의 다섯 policy와 rc2 검증 runner의 `candidate.pipeline.run(...bounded_policy=...)`에서 실행 연결이 확인된다. rc1 Step 11.5의 full-stack 문제를 현 rc2 미구현으로 재등록하지 않는다.

`model_manifest.json`의 `PENDING_STEP12_FINAL_VALIDATION`은 패키징 당시 상태다. 후속 `docs/release-v2.3/final-validation-summary.md`는 같은 tree의 72기사 CPU/FP32 검증을 `COMPLETE_V23_FINAL_VALIDATION_PASS_PUBLISH_READY`로 기록한다. 더 뒤의 `docs/release-v2.3/publish-summary.md`와 `validation-bounded-candidates/final-v23/publication-record.json`에는 2026-09-16 게시 완료가 기록돼 있다. 이번 단계에서는 원격 바이트를 다시 조회하지 않았고 새 게시도 하지 않았다. 이 세 상태를 하나의 현재 manifest 값으로 덮어쓰지 않는다.

## 현재 모듈별 연결 상태

`실행 연결`은 기본 compact 또는 rc2 bounded runner에서 호출이 확인된 경우다. `학습 연결`은 별도 v2.x `training/scripts/train.py` 경로이며 새 r05.3 Gold 학습 가능성과 다르다. 아래 `head/core`는 새 학습의 초기 weight 사용 승인이라는 뜻이 아니다. 12개 고정 weight 파일과 threshold는 rc2 `model_manifest.json` 및 runtime config에 기록돼 있다.

| 책임 / 구현 | 현재 생성자·head/core | 현재 입력 표현 → 소비자·출력 carrier | 현재 상태·weight 의존성 |
|---|---|---|---|
| 공통 backbone | `KFDeBERTaBackbone`, `SharedBackboneProvider` | tokenized article → L8/L10/L12 `BackboneOutput` → 각 head | 실행 연결; pinned external KF revision/6개 cache hash. 모델은 worker 보유, 표현은 요청 보유. |
| Event/Statement 의미 후보 | `CanonicalV3SemanticRuntimeModel` (`DocumentContextEncoder`, `JointSpanProposalHead`, `CanonicalSpanRepresentationV3`), `FixedCanonicalV3SemanticRuntime` | L8/context → accepted Event/Statement mention → trigger/B2/identity/Statement | 실행 연결; `semantic_proposer.pt`, `semantic_v3.pt` 필요. `SemanticRuntimeModel`은 구형 config 호환 경로. |
| Trigger | `TriggerRuntimeModel` / `TriggerBoundaryHead`, `FixedTriggerRuntime` | L8 token → Event trigger evidence → Event feature/closure | 실행 연결; `trigger.pt`. |
| Participant role | `ParticipantB2RuntimeModel` / `ParticipantBoundaryHead`, `FixedParticipantB2Runtime` | Event span + L8/context → ACTOR/TARGET/PLACE/TIME filler → resolution/role handoff | 실행 연결; `participant_b2.pt`. 현재 role-only Entity 승격의 r05.3 완전 계약은 미검증. |
| Entity mention | `EntityMentionRuntimeModel` / `EntitySpanNativeHead`, `FixedEntityMentionRuntime` | L12 candidate span + context → typed EntityMention → priority/identity | 실행 연결; `entity.pt`. 현재 config type은 PERSON/ORGANIZATION/LOCATION/PRODUCT 네 개. GENERIC은 없음. |
| Entity 우선순위 | `EntityCandidatePriorityRuntimeModel`, Entity wrapper | accepted Entity feature → promotion tier → identity/resolution | 실행 연결; `entity_candidate_restriction.pt`; threshold 0.3, 삭제 허용 false. |
| Entity 동일성·role endpoint | `EntityCoreferenceRuntimeModel` / `EntityCoreferenceHead`, `ParticipantEntityResolutionRuntimeModel` / `ParticipantEntityResolutionHead`, `FixedEntityIdentityParticipantResolutionRuntime` | candidate span/pair + policy feature → `LocalEntityState`, remap, role facts → Event closure | 실행 연결; `entity_coreference.pt`, `participant_entity_resolution.pt`. 현 NER 중심 후보 계약을 새 Gold에 적응해야 함. |
| Time mention | `TimeExpressionRuntimeModel` / `TimeExpressionSpanNativeHead`, `FixedTimeExpressionRuntime` | L10 span + context → TimeExpression/occurrence → attachment/normalization | 실행 연결; `time_expression.pt`. |
| Event–Time | `EventTimeAttachmentRuntimeModel` / `DirectedPairEncoder` + linear head, `FixedEventTimeAttachmentRuntime` | Event/Time span pair → attachment → Event feature/fact | 실행 연결; `event_time_attachment.pt`; threshold 0.3. |
| 시간 정규화 | `ArticleRelativeTimeNormalizer`, `TimeNormalizerV2` | Time occurrence + 원문/발행 시각 → canonical temporal key 또는 unresolved → compact assembly | 실행 연결; 규칙 기반, checkpoint 없음. 새 calendar eligibility 검증 필요. |
| Statement type | `StatementTypeRuntimeModel` / `StatementTypeHead`, `FixedStatementTypeRuntime` | Statement span + context → FORECAST/CLAIM/EVALUATION → `CanonicalStatementState` | 실행 연결; `statement_type.pt`. |
| Event 동일성 | `EventIdentityInteractionRuntimeModel` / `EventFeatureEncoder` + `EventCoreferenceInteractionHead`, `FixedEventIdentityRuntime` | `EventFeatureBundle` + selected pair → complete-link/B3 → `EventIdentityClosure` | 실행 연결; `event_coreference.pt`; threshold 0.4. `EventIdentityRuntimeModel`은 존재하지만 현재 config가 선택한 interaction architecture는 아님. |
| PUBLIC 조립 | `CompactArticleLocalKGAssembler` | `ResolvedGraphState` + 원문 → `CompactKnowledgeGraphResult` | 실행 연결; `articlelocal-kg-public-v2.2`, 5 node kinds/7 edge types. |
| Assertor/ASSERTED_BY | `AssertorHead`, `DirectedPairTaskAdapter`, `GoldCandidateBuilder`의 v2.x target | v2.x training candidates → task loss; compact runtime carrier 없음 | v2.x 학습 경로에 구현은 있음. 현 runtime config `assertor.enabled=false`, PUBLIC edge 없음. 새 r05.3 source span/Entity 경로는 미연결. |
| ABOUT/CAUSES | `StatementAboutHead`/`CausalHead` 및 `ProductionTaskRegistry` 선택 분기 | 구형 relation candidate → task loss; compact runtime carrier 없음 | 선택 가능한 v2.x 학습 구현. 기본 `ModelConfig`는 `legacy_v2_2`; 현 runtime config 두 lane 비활성. r05.3 cluster endpoint/closed-world는 미연결. |
| sentence presence / subevent | `SentencePresenceHead`/`SubeventHead` 등 | baseline/production training registry 또는 구형 경로 | head 존재. rc2 runtime config는 `presence`/`subevent_of` 비활성. Presence는 hard deletion gate가 아님. |
| v2.x 학습 진입 | `training/scripts/train.py` → `GoldCorpus.load` → `ArticleLocalKGModel` → `Trainer` | 단일 v2.x construction Gold 파일 → old targets/loss/checkpoint | 실행 가능한 기존 진입점이지만 `GoldCorpus.load`가 `articlelocal-kg-construction-gold-v2.`만 받는다. r05.3 `gold_verified/*.json` fresh-init harness가 아님. `--initial-checkpoint`는 명시적 warm start. |

## 현재 출력과 새 Gold의 확인된 간극

- r05.3 Gold의 `EventCluster.importance_rank`와 `Statement.importance_rank`는 같은 기사 안의 상대순위이며 최고 EventCluster 동순위도 허용한다. 현 PUBLIC schema에는 `primary_score`가 없고, 코드의 다른 `PRIMARY`/`primary_score`는 Entity 후보·Participant resolution 우선순위 용어다. 새 Primary scorer로 오인하지 않는다.
- r05.3 schema는 `GENERIC`을 다섯 번째 EntityMention type으로 두고 ACTOR/TARGET endpoint를 non-null로 요구한다. rc2 Entity config는 네 type이다. PLACE/Assertor의 `entity_id=null` SPAN_ONLY는 Gold에서 허용된다.
- r05.3의 ABOUT는 Statement→EventCluster, CAUSES는 서로 다른 EventCluster 방향쌍이며 완성 Gold의 eligible pair에서 closed-world다. rc2 compact PUBLIC은 두 edge가 없고, v2.x training `ProductionTaskRegistry` 존재만으로 이 계약을 충족하지 않는다.
- 현재 `canonical_text`는 `LocalEventState`/`CanonicalStatementState`에서 compact assembler로 이관된다. 원문 근거를 지키는 새 정규화 구현과 검증은 별도 단계다. 현재 PUBLIC은 `MENTIONS`만으로 Entity를 만들 수 있어, 선택된 Event/Statement와 의미 관계로 연결된 Entity만 보존하는 새 정책과 다르다.
- 기존 `runtime/graph/neo4j.py`는 `ArticleLocalKGNode.id`와 허용된 7개 edge를 사용하는 offline projection이다. N1의 공용 UUID `nodeId` 및 백엔드 영속화 계약과 동일하지 않다.

## 확인 범위

단계 1의 정적 validator와 7개 fixture/unit test만 새로 실행했다. 고정 rc2의 historical 72기사 성능 수치는 `docs/release-v2.3/final-validation-summary.md`의 조건부 기록이다. 전체 현재 Gold의 schema/join/offset 및 semantic census는 단계 2 대상이다. 실제 v3 model forward/backward, memory/timing, GPU는 이번 단계에서 측정하지 않았다.
