# 2026-09-07 Runtime Release Milestone

## 3–5분 복구 요약

우리는 Construction Gold v3 Round01–03 Curated RC1을 기반으로 Article → Event/Statement → Trigger + raw ACTOR/TARGET/PLACE EventFrame carrier, StatementType, nested-capable EntityMention + soft priority, article-local LocalEntity + Participant resolution, generic TimeExpression + Event attachment + 보수적 normalization을 만들고 있다. 현재는 **pre-v0.1 Event identity limited activation staging**이다. Fine threshold 0.64로 article-local LocalEvent를 연결했으며 production/generalization certification은 아니다. 다음 독립 작업은 Assertor다. Neo4j write와 공개 배포는 아직 하지 않았다.

Release-freeze milestone commit은 `chore(release): freeze audited eventframe runtime staging` 메시지로 식별한다. 정확한 commit은 `git log -1 --oneline`으로 확인한다.

## Source of truth

- Release runtime config: `release/kf-deberta-base-kg-extractor/config/runtime.json`
- Runtime API: `runtime.eventframe.ArticleLocalRuntime`
- Canonical ⑧ API: `runtime.graph.ArticleLocalKGAssembler`
- Canonical Gold-free Article → KG API: `runtime.ArticleLocalKGPipeline`
- End-to-end pipeline config: `runtime/configs/goldfree-article-kg-pipeline-v1.json`
- Assembly config: `runtime/configs/article-local-kg-assembly-v1.json`
- Assembly result: `training/results/v3-article-eventframe-kg-assembly-integration-v1/`
- KG qualitative review: `training/results/v3-articlelocal-kg-qualitative-review-v1/`
- Inactive lane readiness audit: `training/results/v3-inactive-lane-readiness-audit-v1/`
- Evidence lane recovery: `training/results/v3-evidence-lane-recovery-integration-v1/`
- Resolution/relation recovery gate: `training/results/v3-resolution-relation-lane-recovery-v1/`
- Gold-free end-to-end integration: `training/results/v3-goldfree-article-kg-end-to-end-v1/`
- Release model/checkpoint manifests: `release/kf-deberta-base-kg-extractor/model_manifest.json`, `checkpoint_manifest.json`
- Runtime consolidation: `training/results/v3-eventframe-runtime-consolidation-v1/report.md`
- Checkpoint audit: `training/results/v3-release-checkpoint-audit-hf-staging-v1/report.md`
- Entity identity + Participant resolution: `training/results/v3-entity-identity-participant-resolution-v1/report.md`
- Event coreference recovery: `training/results/v3-event-coreference-recovery-v1/report.md`
- Event coreference pair interaction: `training/results/v3-event-coreference-pair-interaction-v1/report.md`
- Event coreference calibration/promotion: `training/results/v3-event-coreference-calibration-prior-v1/report.md`
- Curated Gold SHA: `0e4d1fa7f1dc0969fb8d8208c67cdd07b037f68b7acef71afd3d02af4ea80002`
- Guideline: `v3-guideline-r02-curated-rc1`, SHA `a3c3012750b27b0ab3946a0156e43012e1b95204787deb73f50e4fbbab5030a1`
- Prospective integrated guideline: `../data/gold/v3_work/round01-03-curated-rc1/guideline_rc_v2.md`, revision `v3-guideline-r03`, SHA `14ae3da84f1a63879b3d22f87c7d299a5e99a1cd7bdefab289bf5490a07ddcd1`. RC1 schema는 r02/r03 guideline version을 모두 허용하지만 현재 Gold와 active runtime은 계속 r02를 사용한다.

## Active weights

- KF-DeBERTa external base: `363b171d71443b0874b0bf9cea053eb5b1650633`, `3cd6cd7811b3c9190e97cae7eb41571c2bc0076431baae7d41d449a8c1c18c6c`, MIT
- Semantic full: `5a70fa862f8063c4b403eac334fe2c1e2b4dc20570c94d6aabb67873d58c64dd`, `BEST_WITHIN_VALID_RUN`
- Participant B2: `0f16f6c6436036afb1c97ff45ebff428420965c6d6df0ddb2a630ce8c929135c`, `RELEASE_READY`
- Trigger: `f7cbd633ea7b33d4ec9a48d5d207ed9f4779470e329150315b8228e2c12b0fda`, `RUNTIME_ADAPTER_RECOVERED`
- StatementType: `01bfea8e470c4ad90d92171e33ee53851b3b93e5148651a08dd149100e6f690c`, Curated selected epoch 2, `CURATED_RETRAIN_READY`
- Entity Mention: `6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`, Curated selected epoch 8, `RUNTIME_READY_WITH_LIMITATIONS`
- Entity Candidate Soft Priority: `7ae7813979d2fa30d56dbd915fa8446b0d01b7c39679c5b4fec58e34cb11f0f6`, pilot_train120 fixed epoch 7, `ACTIVE_SOFT_PRIORITY_WITH_LIMITATIONS`
- Entity Coreference: `29e47da8976d2b315b310bde4731b3c8b6bb2088bec2e13ef131072277f089d9`, pilot_train120 fresh epoch 8, threshold 0.6, `RUNTIME_READY_WITH_LIMITATIONS`
- Participant Entity Resolution: `03be6024245e6c00164912fe011612385e9f1a91c3c3597b5ae5205b8c17c44e`, pilot_train120 fresh epoch 8, threshold 0.3, `RUNTIME_READY_WITH_LIMITATIONS`
- Generic TimeExpression: `38bcffd9012c2550d5c447aacc0850630ec5f4b0a4cb23b3898def43753c9b18`, pilot_train120 selected epoch 7, threshold 0.8, `RUNTIME_READY_WITH_LIMITATIONS`
- Event→TimeExpression: `75deb17ce8cbefd025fcfe9e42a1b2f399a6e7c240242f3e75483caec4b21bfb`, pilot_train120 selected epoch 8, threshold 0.4, `ACTIVE_WITH_LIMITATIONS`
- Event Coreference: `be70dfaf8a4643f73f63bc348f879f997ef746e563d322b6b3697a0fbbc5b72f`, pair-interaction epoch 8, calibrated threshold 0.64, `RUNTIME_READY_WITH_LIMITATIONS`.
- Boundary lineage `319e21...ad9`는 별도 active file이 아니라 Semantic full의 provenance다.

열한 selected runtime weight는 `release/kf-deberta-base-kg-extractor/weights/` 아래에 있고 Git LFS로 추적한다. KF-DeBERTa base weight와 tokenizer는 bundle에 복제하지 않으며, 위 revision/SHA로 고정된 external dependency다.

## 완료 milestone

Curated semantic contract와 safe participant supervision을 고정했고, Semantic runtime과 predicted Event → B2를 진단했다. canonical raw-Article API를 만들고 parity/determinism을 통과했다. active checkpoint provenance/curve/readiness를 감사하고, B2를 exact 재현했으며, old Semantic을 non-regression 원칙으로 유지했다. 독립 release bundle의 self-containment smoke도 통과했다.

⑧ 조립은 release-freeze `ArticleLocalRuntimeResult`만 소비한다. dev 15에서 Event 185, Statement 113, raw ACTOR/TARGET/PLACE 75/74/14를 보존했고, ARTICLE/EVENT/STATEMENT node와 COVERS/CONTAINS_STATEMENT edge만 만들었다. serialization/schema/dangling/duplicate/endpoint 검증은 PASS다. unresolved raw filler는 source EventFrame과 함께 unmaterialized evidence로 남고 fake Entity나 role edge로 승격되지 않는다. 상태는 `PARTIAL_KG_ASSEMBLY_READY`, `READY_FOR_KG_QUALITATIVE_REVIEW=true`다.

고정 runtime을 pilot_dev 15개와 article_id 정렬로 고정한 pilot_train 10개, 총 25개에 실행해 실제 graph를 원문과 대조했다. 구조는 25/25 schema·serialization PASS, dangling/duplicate/invalid endpoint 0, Event/Statement/raw filler count parity와 NOT_RUN 보존 PASS이며 assembler bug와 evidence loss는 0이다. 정성 결과는 `KG_STRUCTURALLY_VALID_BUT_SEMANTICALLY_WEAK`: 16개는 부분 미니 지도로 읽혔고 9개는 중심 Event 누락, 중복/절단 proposition, participant span spray 때문에 안정적 지도로 보기 어려웠다. `READY_FOR_INACTIVE_LANE_READINESS_AUDIT=true`는 inactive lane을 곧바로 활성화한다는 뜻이 아니라 contract/checkpoint provenance를 read-only로 감사할 준비가 됐다는 뜻이다.

Inactive lane 11개를 Curated RC support, old checkpoint provenance, canonical adapter, 25개 graph service impact로 감사했다. 즉시 활성화 가능한 lane은 0개다. Trigger는 span 계약이 parent→Curated에서 변하지 않고 old boundary weight를 재사용할 수 있지만 predicted Event attachment/parity가 남아 `RUNTIME_ADAPTER_ONLY`다. StatementType·Presence·Entity coreference는 `RETRAIN_ON_CURATED_RC`, Entity·generic TimeExpression·Event coreference·Assertor·narrow ABOUT·CAUSES는 `CONTRACT_MIGRATION_REQUIRED`, SUBEVENT_OF는 sparse bounded-parent relation이라 `DEFER_LOW_PRIORITY`다.

`READY_FOR_EVIDENCE_LANE_RECOVERY=true`는 별도 승인 작업에서 contract-preserving recovery를 시작할 근거가 있다는 뜻이며 즉시 runtime activation 승인이 아니다. `READY_FOR_RESOLUTION_RELATION_RECOVERY=false`다. Entity mention representation, canonical EventFrame pair input, Assertor raw-span/context candidate, ABOUT safe-negative 권한이 먼저 필요하다.

승인된 recovery를 실행해 Trigger와 StatementType을 새 active config `eventframe_runtime_candidate_v2_evidence_recovery_freeze`에 연결했다. Trigger는 parent pilot checkpoint의 동일 Head tensor와 기존 threshold 0.5 / width 64 / greedy one-to-one decoder를 재사용하고, predicted Event 안의 nearest-contained anchor를 연결한다. Trigger는 B2 feature나 gate가 아니다. StatementType은 기존 topology/objective 그대로 Curated train120에서 fresh retrain했고 dev Gold-Statement-conditioned macro-F1 0.8028, selected epoch 2다. pilot_dev15에서 이전 Event/Statement/B2 output은 15/15 exact parity, Event 185·Statement 113·raw Participant 163을 그대로 보존했다. Trigger는 119 Event에 연결됐고 Statement 113개 모두 type output을 받았다. 구조 검증은 15/15 PASS다.

Resolution/relation recovery gate를 다시 적용한 결과 활성화 lane은 0개다. Entity coreference는 `RETRAIN_ON_CURATED_RC`이지만 최종 Curated Entity mention universe가 아직 execution-connected가 아니어서 retrain 자체를 보류했다. Event coreference, Assertor, narrow ABOUT, CAUSES는 `CONTRACT_MIGRATION_REQUIRED`, SUBEVENT_OF는 `DEFER_LOW_PRIORITY`이므로 모두 의도적으로 `NOT_RUN`이다. Assertor source→Statement 방향, narrow ABOUT의 Statement→Event|Statement endpoint, CAUSES/SUBEVENT_OF 독립 binary family, RESPONDS_TO 금지 계약을 validation으로 고정했다. 현재 `READY_FOR_END_TO_END_KG=false`이며 이는 안전한 partial runtime 판정이지 실행 실패가 아니다.

Gold-free end-to-end integration에서는 `runtime.ArticleLocalKGPipeline.from_config(...).run(article)` 하나로 raw Article → fixed EventFrame runtime → evidence-preserving ⑧ assembly → deterministic partial KG JSON을 만들도록 연결했다. 이전처럼 호출자가 runtime과 assembler를 직접 조합하거나 experiment adapter를 알 필요가 없다. 직전 정성 검토와 동일한 pilot_dev 15 + pilot_train 10을 Gold 없이 실행했고 decoded graph determinism 25/25, schema/serialization 25/25, dangling/duplicate/invalid endpoint/fake Entity 0, raw filler 269개 보존을 확인했다. 출력은 Event 308, Statement 197, Trigger 206, StatementType 197, ARTICLE/EVENT/STATEMENT node 530, COVERS/CONTAINS_STATEMENT edge 505다.

현재 end-to-end gate는 `END_TO_END_PARTIAL_KG_READY`이며 `READY_FOR_HF_V0_1_FINALIZATION=false`다. 구조적 경로는 완성됐지만 고정 10개 current graph 재검토 결과는 여전히 `KG_STRUCTURALLY_VALID_BUT_SEMANTICALLY_WEAK`다. proposition 누락·중복·경계 문제와 Participant spray/leakage가 남고 Entity/Time/resolution/coreference/ABOUT/CAUSES/SUBEVENT_OF가 `NOT_RUN`이다. Neo4j CLI/driver/credential도 현재 환경에 없어 DB write는 하지 않았고, review 가능한 deterministic projection JSON과 idempotent Cypher만 준비했다.

## 건드리면 안 되는 것

Gold/guideline/Round04, topology/loss/candidate/threshold, production defaults, auxiliary signals, pilot_test/original 1K dev/test, Notion, HF repository를 이 milestone의 후속 자동 작업으로 변경하지 않는다. 현재 bundle은 staging이며 project 공개 license는 미정이다.

## NOT_RUN

Canonical runtime 내부에서는 Trigger, StatementType, Entity Mention, Entity soft priority,
Entity Coreference, LocalEntity, Participant Entity Resolution, generic TimeExpression,
Event→TimeExpression, deterministic Time normalization이 `EXECUTED`이고,
Presence, Assertor/narrow ABOUT, CAUSES/SUBEVENT_OF가 `NOT_RUN`이다. Event coreference는
article-local limited mode로 `EXECUTED_WITH_LIMITATIONS`다. 별도 ⑧ assembler가 조립을 `EXECUTED`로 기록하되
source runtime의 `NOT_RUN` 상태와 reason을 보존한다. NOT_RUN은 ABSENT가 아니다.

## 다음 작업

Trigger adapter/parity, StatementType Curated retrain, nested-capable Entity Mention migration/retrain은
완료됐고 generic TimeExpression generic-contract migration/retrain과 attachment/normalization도
완료됐고 Entity Identity + Participant Resolution도 아래 milestone에서 완료됐다. Event Identity /
Coreference Work Bundle #4와 #4.1은 차단됐지만 #4.2 pair interaction checkpoint를 #4.3에서
threshold 0.64로 calibration해 article-local limited runtime에 승격했다. 다음 공식 work bundle은
Assertor다. 그 뒤 Presence, CAUSES, ABOUT 순으로 contract gate를 다시 확인하고 SUBEVENT_OF는
뒤로 미룬다. 현재 `READY_FOR_ASSERTOR=true`다. 각 lane의
activation은 별도 parity/release gate가 필요하다. 특히 inactive lane 추가가 현재 Semantic Event
recall과 B2 span spray를 해결한다고 가정하지 않는다. 공개 license 결정과 README/Model Card/HF
upload도 별도 작업이다.

Gold-free pipeline 자체는 후속 caller가 사용할 수 있지만, HF v0.1 최종화보다 먼저 semantic proposition 품질과 B2 precision/leakage, Curated-compatible Entity/Time evidence lane을 별도 승인 작업으로 다뤄야 한다. Neo4j 투입은 `neo4j_projection.json`/`neo4j_import.cypher`를 credential이 구성된 환경에서 검토한 뒤 별도로 수행한다. 이 milestone은 HF 작업을 자동으로 시작하지 않는다.

Gold-free end-to-end milestone은 local commit `b9e2a94`다. 이 commit 직후 `git push origin master`를 실행했으나 GitHub SSH `Permission denied (publickey)`로 실패했다. 따라서 local 실행은 재현 가능하지만 remote sync가 될 때까지 `CROSS_DEVICE_CONTINUATION_READY=false`다.

## HF v0.1 finalization gate 재확인

`V3 Hugging Face v0.1 Release Bundle & Model Card Finalization` 시작 시 최신
`training/results/v3-goldfree-article-kg-end-to-end-v1/summary.json`과 report의 SHA를 다시
검증했다. 명시적 gate는 여전히 `READY_FOR_HF_V0_1_FINALIZATION=false`이고 상태는
`END_TO_END_PARTIAL_KG_READY`, 정성 판정은
`KG_STRUCTURALLY_VALID_BUT_SEMANTICALLY_WEAK`다.

따라서 project staging을 공개 v0.1 bundle로 재작성하거나 실제 Hugging Face working tree에
복사하지 않았다. 연결된 `sysy9292/kf-deberta-base-kg-extractor` local repository는
`main`/`origin/main` 동일 상태이며 이 작업에서 수정·commit·push·tag하지 않았다. blocker 근거는
`training/results/v3-hf-v0-1-release-finalization/`에 있다.

HF finalization의 다음 허용 조건은 새 end-to-end gate가 명시적으로 true가 되는 것이다. 그 전에는
README metric 자동 수집, synthetic example inference, release self-containment smoke, staging→HF
manifest parity, HF local commit을 실행하지 않는다. 현재 다음 단계는 HF upload가 아니라 Semantic
proposition 및 B2 participant quality blocker와 v0.1 지원 lane 범위를 별도 승인 작업에서 해소하는
것이다.

이 blocker 판정은 project local commit `bafb18a`에 기록했다. 이어서 실행한 normal
`git push origin master`는 GitHub SSH `Permission denied (publickey)`로 실패했다. HF remote에는
push를 시도하지 않았다. 따라서 `CROSS_DEVICE_CONTINUATION_READY=false`다.

## Evidence Lane Completion v2

최신 canonical config와 prior recovery artifact를 다시 읽고 네 evidence lane을 terminal status로
고정했다. Trigger와 StatementType은 이미 검증된 checkpoint/adapter를 그대로 사용해 `ACTIVE`이며
재학습하지 않았다. Entity Mention과 generic TimeExpression은
`INTENTIONALLY_NOT_RUN_WITH_BLOCKER`다.

Entity blocker는 Curated RC 4,817 mention에 남은 strict nested 103쌍을 기존 flat 9-label BIO가
동시에 표현하지 못하는 model-representation gap이다. Time blocker는 generic textual span과 legacy
DATE/TIME/DURATION/SET taxonomy의 계약 불일치, overlap 5쌍, article-level safe-negative
completeness 부재다. Gold mention을 삭제하거나 UNKNOWN을 negative로 바꾸지 않았고 새
topology/Head/threshold를 만들지 않았다.

pilot_dev 15 raw Article replay에서 기존 Event/Statement/B2 exact output과 15/15 parity,
graph validation 15/15 PASS를 확인했다. Event 185, Statement 113, raw Participant 163, attached
Trigger 119, StatementType 113이며 Entity/Time은 15/15 명시적 `NOT_RUN`이다. 전체 canonical test
suite는 256 PASS(1 skip)다. 판정은 `EVIDENCE_LANES_PARTIAL`,
`READY_FOR_IDENTITY_RESOLUTION_COMPLETION=false`이며 상세 source/checkpoint/blocker는
`training/results/v3-evidence-lane-completion-v2/`에 있다.

다음 허용 작업은 Entity/Time을 억지 활성화하는 것이 아니다. Entity에는 nested span을 보존하는
representation architecture 승인과 Curated retrain이, Time에는 generic span negative completeness와
overlap 표현 계약 결정이 먼저 필요하다. identity/relation recovery는 이 gate가 true가 되기 전에는
자동 재개하지 않는다.

Evidence Lane Completion v2는 local commit `dd33837`에 기록했다. 이어서 실행한 normal
`git push origin master`는 GitHub SSH `Permission denied (publickey)`로 실패했다. 따라서 local
artifact는 재현 가능하지만 remote sync 전까지 `CROSS_DEVICE_CONTINUATION_READY=false`다.

## Event Coreference Recovery v1

Work Bundle #4의 `EVENT_IDENTITY_BLOCKED` 결과와 artifact를 파일별 SHA-256으로 동결한 뒤,
동일 seed1008·96/24 split·all MERGE·deterministic hard/representative KEEP 8:1·MERGE weight4·
CrossEntropyLoss·lr0.0003·weight decay0.01·pair batch32·기존 symmetric head 조건을 유지했다.
유일한 독립변수는 maximum epoch 8→24였다. Apple MPS에서 fresh initialization으로 실행했고
최고 validation MERGE PR-AUC는 epoch18의 0.21798이었다. 이후 train loss는 계속 감소했지만
마지막 3개 epoch PR-AUC가 peak보다 지속 하락해 `OVERFIT`으로 판정했다. 기존 CUDA epoch1–8
trajectory는 MPS에서 수치적으로 재현되지 않았으므로 exact continuation이라고 표현하지 않는다.

Epoch18 checkpoint를 고정한 post-hoc Time masking에서 FULL/NO_TIME PR-AUC는
0.21798/0.21793으로 과거 NO_TIME 이득은 재현되지 않았다. 다만 Time representation만 제거하면
0.22264로 개선되고 availability만 제거하면 0.21637로 하락했다. 따라서 전체 Time channel은
`NEUTRAL_WITH_MIXED_COMPONENT_EFFECTS`이며 semantic representation은 약한 negative/confounded,
availability는 positive signal이다. canonical EventFeatureBundle과 Time lane은 수정하지 않았다.

Internal validation+pilot_dev의 Gold Event 676개 중 predicted Event exact recovery는 228개다. 이
subset의 predicted Trigger/ACTOR/TARGET/PLACE availability는 73.68%/33.33%/38.60%/6.14%다.
Trigger의 최대 first-loss는 acceptance이며 exact/overlap recall은 51.32%/65.79%다. 같은 subset에서
Gold TARGET availability는 98.68%지만 predicted는 38.60%이고, Gold TARGET filler 278개 중
184개가 정확 start/end acceptance에서 처음 탈락했다. ACTOR 최대 손실도 acceptance이고 PLACE는
exact token proposal 표현 불가가 최대다. Event proposition upstream miss 448개는 조건부
Trigger/B2 손실과 분리했다.

Selected fixed-grid threshold0.9의 internal MERGE P/R/F1은
0.15122/0.42466/0.22302다. PR-AUC, candidate recall1.0, nonzero MERGE, pilot Gold/Gold signal,
deterministic complete-link, bridge safety, raw EventFrame 100% 보존, fake/dangling Event 0은
통과했지만 F1 0.40과 precision 0.50을 모두 넘지 못했다. 따라서 상태는
`EVENT_IDENTITY_RECOVERY_BLOCKED`, runtime/release promotion은 false이며 recovery checkpoint와
feature/runtime cache는 source-of-truth가 아닌 재생성 가능한 transient로 남긴다. 다음 작업은
`READY_FOR_ASSERTOR=true`이고 추가 Event coreference tuning은 자동 실행하지 않는다.

## Git / cross-device handoff

다른 컴퓨터에서는 Git LFS를 설치한 뒤 repository를 clone/pull하면 release bundle의 네 selected weight를 함께 받을 수 있다. 이어서 `release/kf-deberta-base-kg-extractor/config/runtime.json`을 source of truth로 사용한다. canonical runtime source는 `runtime/`, evidence recovery 계약 테스트는 `tests/test_v3_evidence_lane_recovery.py`, release provenance는 `training/results/v3-evidence-lane-recovery-integration-v1/`의 최종 JSON/Markdown artifact다.

Git에 넣지 않는 것은 HF/transformers cache, frozen-backbone feature cache, retrain epoch별 intermediate checkpoint, 임시 proposal/logit/tensor dump, `__pycache__`, pytest cache다. 이 파일들은 source-of-truth가 아니며 재생성 가능하다. 공개 배포용 project license 결정은 아직 남아 있지만, 내부 Git sync와 다음 KG integration을 막는 runtime blocker는 아니다.

Release-freeze base milestone은 local commit `600f25f`, evidence recovery는 `5b02d71`, resolution/relation gate는 `d660f34`이며, KG assembly milestone은 `feat(graph): integrate evidence-preserving article kg assembly` 메시지로 식별한다. `d660f34` 생성 후 normal SSH push를 다시 시도했지만 `Permission denied (publickey)`로 실패했다. 따라서 다른 컴퓨터가 위 artifact를 받으려면 이 컴퓨터에서 GitHub 인증을 구성한 뒤 `git push origin master`를 실행해야 한다. 파일별 전송 blocker는 `docs/CROSS-DEVICE-BLOCKER.md`에 기록한다.

또한 Curated RC의 `curated_gold_rc.json`과 `guideline_rc.md`는 현재 작업 시작 전부터 존재한 사용자 untracked artifact라 inactive-lane audit commit에 섞지 않았다. 두 source가 별도 curation milestone commit으로 추적되고 local commits가 push되기 전까지 `CROSS_DEVICE_CONTINUATION_READY=false`다.

## Entity Mention Completion v1

기존 flat 9-label `EntityBIOHead`는 Curated RC 4,817 mentions의 strict nested 103쌍을
동시에 표현할 수 없었다. 이는 checkpoint 성능이 아니라 output representation blocker다.
전수 audit에서 partial overlap과 same-boundary multi-type pair는 0, cross-sentence mention은
1건이었다. 최대-cardinality flat BIO recall ceiling은 4,718/4,817(97.94%)이고 nested pair
joint recovery ceiling은 0%다. Gold/guideline을 수정하거나 overlap mention을 삭제하지 않았다.

선택 representation은 `SPAN_NATIVE_MULTILABEL`이다. 기존 frozen KF-DeBERTa L12,
`DocumentContextEncoder`, `CandidateSpanEncoder`를 재사용하고 contiguous absolute character
span마다 기존 PERSON/ORGANIZATION/LOCATION/PRODUCT independent logit을 출력한다. covering
token 내부 character boundary feature로 exact tokenizer endpoint가 아닌 Gold도 보존한다.
pilot_train120 안에서 seed1008 article split 96/24, 최대8 epoch로 학습했고 epoch8과 global
threshold0.7을 고정한 뒤 train120 전체 release-purpose fresh training을 수행했다.

pilot_dev15 최종 exact typed P/R/F1은 0.1425/0.8684/0.2448, macro-F1 0.2420,
macro PR-AUC 0.4677이다. nested mention recall은 27/32(84.38%), nested pair joint recovery는
13/18(72.22%)다. 다만 평균 206.8 predictions/article와 false exact typed span
177.3/article로 precision/output-density limitation이 크다. 따라서 판정은
`ENTITY_MENTION_RUNTIME_READY_WITH_LIMITATIONS`이며 identity resolution 입력 승격은 보류한다.

active runtime config는 `eventframe_runtime_candidate_v3_entity_mention_freeze`, selected
checkpoint는 `release/kf-deberta-base-kg-extractor/weights/entity.pt`, SHA256은
`6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`다. Entity Mention은
`ACTIVE`, Entity Coreference/Participant Resolution은 `NOT_RUN`이다. dev15에서 기존
Event/Statement/Trigger/StatementType/B2 exact parity 15/15, graph Entity evidence
3,102/3,102와 raw participant163 보존, fake Entity/dangling0, release self-containment smoke
PASS를 확인했다.

다음 roadmap은 별도 승인 작업의 generic TimeExpression completion이다. Entity Coreference와
Participant Resolution은 자동으로 이어서 실행하지 않는다. 현재 operating point는 높은 recall과
nested recovery를 보이지만 precision/density를 별도 gate에서 다루기 전에는 LocalEntity 생성이나
role resolution의 입력으로 승격하지 않는다.

## Entity Mention false-positive audit v1

selected checkpoint와 threshold 0.7을 변경하지 않고 고정 pilot_dev15의 442 TP/2,660 FP를
read-only로 분해했다. 학습 sampled universe는 positive 1개당 negative 114.64개였지만 full runtime
candidate universe는 3,271.78개로 28.54배 더 희박하다. weighted BCE `pos_weight`도
80.62–249.64여서 raw sigmoid score를 calibrated posterior probability로 해석할 수 없다.

동시에 N1 wrong-type과 N2 Gold subspan은 negative 1,000개당 각각 36.02/32.12 FP로 N6
far/easy의 0.96보다 크게 높다. hard-strata 전체 FP rate는 N6의 2.35배이고 FP median score도
0.9200으로 높다. 따라서 현재 low precision 판정은
`C_BOTH`—score calibration/prior mismatch와 hard-negative discrimination 부족이 함께 존재함—이다.
상세 stratum/type/span-width quantile은
`training/results/v3-entity-mention-fp-audit-v1/`에 있다. 이 audit으로 checkpoint, threshold,
runtime config, Entity status를 변경하지 않았으며 다음 roadmap은 여전히 별도 prompt의 generic
TimeExpression이다.

## Entity Mention Precision Stabilization v1

`SPAN_NATIVE_MULTILABEL` architecture와 Entity output contract를 유지하고 seed1008
internal_train96/internal_validation24에서 A(prior correction), B(hard-negative), C(A+B)를 최대6
epoch로 비교했다. 세 후보가 사전 고정 gate를 통과하지 못해, 허용된 reduced-weight 비교를
`sqrt(original pos_weight)` 한 점으로 고정하여 A2/C2까지 실행한 뒤 추가 sweep을 종료했다.
pilot_dev와 pilot_test는 선택에 사용하지 않았다.

출력 밀도 100/article 이하인 최선 A2 지점(e6/t0.8)은 P/R/F1
0.3979/0.7307/0.5152였지만 nested recall 47.83%, nested pair joint recovery 21.74%로 떨어졌다.
반대로 recovery gate를 지킨 A2 지점(e6/t0.3)은 recall 92.76%, nested recall 86.96%, joint
78.26%였지만 precision 12.56%, 306.29 predictions/article였다. 다른 후보도 같은 trade-off를
보여 precision, recovery, density gate를 동시에 만족한 후보는 0개다.

판정은 `ENTITY_MENTION_PRECISION_STABILIZATION_BLOCKED`다. 내부 winner가 없으므로
release-purpose retraining과 one-time pilot_dev final reference는 실행하지 않았고, 기존 threshold
0.7과 checkpoint SHA256
`6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`를 그대로 유지했다.
release config/manifest/runtime source도 변경하지 않았다. 따라서 기존 Entity Mention runtime은
`READY_WITH_LIMITATIONS` 상태를 유지하지만 새로 refreeze한 것은 아니다.

`READY_FOR_GENERIC_TIME_EXPRESSION_COMPLETION=false`다. TimeExpression lane 자체는 기술적으로
독립적이지만, 이번 prompt가 요구한 precision stabilization 후 refreeze라는 순서가 완료되지 않았다.
상세 protocol, 전체 training history, constraint frontier와 보호 상태는
`training/results/v3-entity-mention-precision-stabilization-v1/`에 있다. intermediate/rejected
checkpoint와 cache는 source-of-truth가 아니므로 Git에 포함하지 않는다.

## Entity Candidate Restriction — Promotion Verifier v1

③ EntityMention extractor를 checkpoint SHA256
`6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`, threshold0.7,
`SPAN_NATIVE_MULTILABEL`로 완전히 고정하고, 실제 accepted typed prediction만 입력으로 쓰는 단일
⑦ binary Promotion Verifier를 검증했다. detached span/L12 boundary context, 기존 score/boundary/width,
accepted-candidate competition feature를 사용했으며 NMS나 overlap hard suppression은 없다.

unweighted BCE와 full accepted-candidate prior로 최대8 epoch 학습했고 validation PR-AUC 0.69638인
epoch7을 선택했다. 사전 고정 threshold grid의 최선 diagnostic t0.3에서 internal FP는 92.53%
줄었지만 conditional TP retention 74.07%, nested retention 47.83%, pair retention 30.43%로
각 gate 80%/75%/70%를 통과하지 못했다. pilot_dev reference도 FP 88.76% 감소와 P/R/F1
0.5138/0.6208/0.5623을 보였으나 TP retention 71.49%, nested 59.26%, pair 30.77%에 그쳤다.

판정은 `ENTITY_CANDIDATE_RESTRICTION_NOT_PROMOTED`다. 실험 view의 pilot_dev 615 PROMOTED와
2,487 EVIDENCE_ONLY decision은 canonical runtime에 연결하지 않았다. ③ raw EntityMention 3,102개와
graph evidence 3,102개는 모두 보존됐고 fake Entity/LocalEntity/MENTIONS edge/dangling reference는
모두 0, 기존 Event/Statement/Trigger/StatementType/B2 regression도 0이다.

release verifier weight, runtime config, model/checkpoint manifest는 변경하지 않았고 ③ `entity.pt`도
교체하지 않았다. rejected verifier checkpoint와 feature cache는 Git에 포함하지 않는다. Entity 추가
연구는 자동으로 이어가지 않으며 `READY_FOR_TIME_EXPRESSION_COMPLETION=true`로 generic
TimeExpression handoff가 가능하다. 상세 결과는
`training/results/v3-entity-candidate-restriction-v1/`에 있다.

## Entity Candidate Restriction — Nested-Aware Distribution Stabilization v2

사용자가 명시적으로 허용한 마지막 Entity stabilization에서 ③→⑦ responsibility architecture를
정식 결정으로 채택했다. ③은 immutable high-recall EntityMention evidence를 보존하고, ⑦은 향후
⑥에 넘길 `PROMOTED`/`EVIDENCE_ONLY` derived view만 판정한다. ⑥ Entity Identity/Coreference와
Participant Resolution은 실행하지 않는다. 이번 독립변수는 ⑦ train exposure뿐이었다.

③은 `SPAN_NATIVE_MULTILABEL`, threshold0.7, checkpoint SHA256
`6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`로 고정했다. v1의
detached CandidateSpanEncoder/L12 local context/score/boundary/competition feature, binary MLP,
unweighted BCE, optimizer, seed1008 96/24 split, validation universe, 최대8 epoch, PR-AUC selection과
0.3–0.9 threshold grid도 그대로 유지했다.

Train의 recoverable strict nested pair 44쌍을 audit하고 pair positive 양쪽과 동일 sentence N1–N5
local hard competitor를 묶는 2× replay를 사전에 고정했다. A runtime stream 20,643 known rows는
매 epoch 전부 한 번 유지했고 B는 528 presentations(2.56%)만 추가했으며 N6와 UNKNOWN은 replay에
넣지 않았다. Fresh verifier의 validation PR-AUC 최고 epoch7(0.71322)을 선택했다.

Internal diagnostic t0.3에서 v2 conditional TP retention 87.84%와 FP reduction 86.94%는 gate를
통과했다. v1 대비 nested mention retention은 47.83%→67.39%, pair joint retention은
30.43%→43.48%로 회복됐지만 필수 75%/70%에는 미달했다. false/article은 v1 17.58에서 v2
30.75로 늘었으나 raw 235.42보다 낮았다. 고정 후 1회 평가한 pilot_dev reference에서는 nested
retention 74.07%, pair retention 61.54%, FP reduction 84.47%, P/R/F1
0.4551/0.6778/0.5446이었다. 이 reference로 설정을 변경하지 않았다.

따라서 최종 상태는
`ENTITY_CANDIDATE_RESTRICTION_ARCHITECTURE_ACCEPTED_MODEL_NOT_READY`다. ③ EntityMention은
`ACTIVE_WITH_LIMITATIONS`, ⑦은 `ARCHITECTURE_ACCEPTED_MODEL_NOT_READY`이며 checkpoint/runtime
promotion은 하지 않았다. `entity.pt`, runtime config와 release manifest를 수정하지 않았고
EntityMention raw parity를 유지했다. Gate 실패 계약에 따라 v2 graph replay는 실행하지 않았으며
Entity/LocalEntity/MENTIONS edge도 만들지 않았다.

이번이 마지막 Entity Candidate Restriction stabilization이다. 성공/실패와 관계없이 추가 Entity
architecture/loss/distribution 실험을 자동으로 이어가지 않는다. 다음 canonical roadmap은 별도
prompt의 generic TimeExpression Completion이며
`READY_FOR_TIME_EXPRESSION_COMPLETION=true`다. 상세 source, distribution, pair diagnostics,
FIRST LOSS와 비교표는
`training/results/v3-entity-candidate-restriction-nested-aware-v2/`에 있다.

## Entity Candidate Restriction — Soft-Priority Runtime Promotion v1

사용자 최종 정책에 따라 v2 verifier를 Entity의 hard validity/deletion gate가 아니라 향후 ⑥
Entity Identity/Resolution을 위한 non-destructive priority metadata로 승격했다. v2의 역사적 hard
gate는 그대로다. Internal conditional TP retention 87.84%와 FP reduction 86.94%는 PASS였지만
nested mention 67.39%와 nested pair 43.48%는 75%/70% 기준에 미달했으므로
`HARD_ENTITY_RESTRICTION_READY=false`다. 동시에 raw evidence를 삭제하지 않는 정책 계약으로
`SOFT_ENTITY_PRIORITIZATION_READY=true`다. 과거 v1/v2 결과와 판정은 수정하지 않았다.

③ EntityMention은 기존 `SPAN_NATIVE_MULTILABEL`, threshold0.7, checkpoint SHA256
`6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`를 그대로 사용한다. ⑦은
각 `entity_prediction_id`에 release-purpose verifier score와 `TIER1_PROMOTED` 또는
`TIER2_EVIDENCE_ONLY`만 별도 제공한다. TIER2는 false/rejected/deleted Entity가 아니며 bounded
rescue가 가능한 저우선순위 raw evidence다. `hard_deletion_authorized=false`,
`hard_identity_eligibility_gate_authorized=false`, `raw_entity_evidence_preserved=true`,
`TIER2_RESCUE_POLICY=DEFERRED_TO_ENTITY_IDENTITY_INTEGRATION`이고 이번 단계에서 pair expansion은
실행하지 않았다.

v2에서 고정된 architecture/features, nested-aware replay2x, unweighted BCE, seed1008, epoch7,
threshold0.3을 변경하지 않고 pilot_train120 전체로 fresh release-purpose training했다. validation
selection, epoch reselection, threshold calibration은 없었다. selected release weight는
`release/kf-deberta-base-kg-extractor/weights/entity_candidate_restriction.pt`, SHA256
`7ae7813979d2fa30d56dbd915fa8446b0d01b7c39679c5b4fec58e34cb11f0f6`다. 고정 후 1회 실행한
pilot_dev reference에서 Tier1 diagnostic P/R/F1은 0.5108/0.6483/0.5714였고 conditional TP
retention 74.66%, FP reduction 88.12%, nested mention retention 55.56%, nested pair retention
23.08%였다. 이 수치는 설정 변경이나 hard-gate 재판정에 사용하지 않았다.

새 canonical runtime ID는 `eventframe_runtime_candidate_v3_entity_soft_priority_freeze`다. pilot_dev
15건에서 raw EntityMention 3,102개를 3,102개 모두 유지하면서 Tier1 646개(43.07/article), Tier2
2,456개(163.73/article)의 완전한 derived view를 만들었다. verifier input/scoring delta는 평균
0.0826초/article이다. 참고용 미실행 pair upper bound는 raw 539,102개에서 Tier1-only 23,289개로
줄지만, Tier2 rescue pair는 생성하지 않았다.

같은 모델 인스턴스에서 ⑦만 비활성화한 control과 비교해 ③ raw Entity, Event, Statement,
Trigger, StatementType, B2가 15/15 exact parity였다. 과거 별도 CUDA 실행과도 derived runtime ID를
제외한 구조는 15/15 동일했고 최대 score 차이는 1.18e-5였다. Graph replay는 raw Entity/Tier1/Tier2
evidence를 전부 보존했고 LocalEntity/fake Entity/MENTIONS edge/dangling reference는 모두 0,
serialization/schema는 15/15 PASS였다. release-only GPU smoke도 PASS다.

최종 상태는 `ENTITY_CANDIDATE_PRIORITIZATION_RUNTIME_READY_WITH_LIMITATIONS`이다. ③은
`ACTIVE_WITH_LIMITATIONS`, ⑦은 `ACTIVE_SOFT_PRIORITY_WITH_LIMITATIONS`, Entity Coreference와
Participant Entity Resolution은 `NOT_RUN`이다. 이 작업 이후 Entity architecture/loss/distribution
실험을 추가로 시작하지 않는다. 다음 공식 work bundle은 별도 prompt의
`generic TimeExpression + normalization`이며 `READY_FOR_TIME_EXPRESSION_COMPLETION=true`다.
상세 provenance와 검증은
`training/results/v3-entity-candidate-restriction-soft-priority-promotion-v1/`에 있다.

## Generic TimeExpression Completion + Event Attachment + Article-relative Normalization v1

Generic TimeExpression의 canonical representation을 frozen KF-DeBERTa L10 기반
`SPAN_NATIVE_BINARY_TIME_EXPRESSION`으로 고정했다. 865 Gold 전부가 candidate universe에 포함되며
858개는 exact token boundary, 7개는 token-internal character boundary로 표현된다. alignment failure,
truncation loss, cross-sentence span은 0이고 strict nested pair는 4쌍이다. Tiny proof에서는 nested
mention 6/6과 pair 3/3을 동시에 복구해 representation/decoder의 nested-capability를 확인했다.

pilot_train120의 seed1008 96/24 article split에서 fresh training했고 internal PR-AUC로 epoch7을 먼저
선택한 뒤 threshold0.8을 고정했다. Internal P/R/F1은 0.5082/0.6327/0.5636이고 고정 후 한 번만
실행한 pilot_dev reference는 0.3134/0.7000/0.4330이다. pilot_dev의 recoverable nested pair 한 쌍은
최종 모델이 복구하지 못했으므로 lane은 `ACTIVE_WITH_LIMITATIONS`다. Release-purpose checkpoint는
`weights/time_expression.pt`, SHA256
`38bcffd9012c2550d5c447aacc0850630ec5f4b0a4cb23b3898def43753c9b18`이다.

Event→TimeExpression은 기존 `DirectedPairEncoder` 기반 directed binary attachment로 구현했다.
Internal oracle PR-AUC로 epoch8을 선택한 뒤 threshold0.4를 고정했다. pilot_dev Gold/Gold oracle
P/R/F1은 0.7278/0.8452/0.7821이고 fully-predicted cascade는
0.1771/0.2000/0.1879다. Release checkpoint `weights/event_time_attachment.pt` SHA256은
`75deb17ce8cbefd025fcfe9e42a1b2f399a6e7c240242f3e75483caec4b21bfb`이며 attachment도
`ACTIVE_WITH_LIMITATIONS`다.

⑧ normalization은 절대 표현과 제한된 relative rule만 deterministic하게 처리하며 relative reference가
필요할 때 article `publishedAt`만 사용한다. System current time, extraction/attachment feature,
DATE/TIME/DURATION/SET neural subtype는 사용하지 않는다. Normalized Gold는 786개 중 8개(1.02%)뿐이고
exact 7/8(87.5%), absolute 7/7, relative 0/1이다. 상대식 한 건은 processed `publishedAt`과 Gold의
historical narrative reference가 충돌했다. Unsupported/ambiguous/duration/set 표현은 정상적인
`UNRESOLVED` raw evidence로 보존한다.

pilot_dev graph replay는 raw TimeExpression 268개와 attachment 175개를 전부 보존했고 materializable한
Time node 16개와 OCCURRED_ON 21개만 생성했다. fake Time, dangling reference, duplicate Time edge는 0,
serialization과 기존 Event/Statement/Trigger/StatementType/B2/Entity 출력 parity는 PASS다. 새 runtime
ID는 `eventframe_runtime_candidate_v3_generic_time_freeze`다.

Freeze 후 추가한 density audit에서 raw Time search-space는 pilot_dev mean 27,847.4/article이지만
accepted Time은 17.87, predicted Event는 12.33, 실제 eligible Event×accepted-Time pair는 mean 250.6,
median 169, p90 744, max 1,015다. ⑤가 raw 33k 후보와 직접 Cartesian product하지 않음을 확인했고
`PAIR_EXPLOSION_CONFIRMED=false`다. Time extraction 0.5661초/article, attachment 0.00966초/article이며
33k search-space는 ③ inference optimization debt로 남겼다. Gold attachment 거리 coverage는
same-sentence 90.94%, ±1 96.41%, ±2 98.51%, ±3 98.80%다.

최종 상태는 `GENERIC_TIME_EXPRESSION_RUNTIME_READY_WITH_LIMITATIONS`다. 다음 공식 work bundle은
Entity Identity + Participant Resolution이며 `READY_FOR_ENTITY_IDENTITY_PARTICIPANT_RESOLUTION=true`다.
이번 milestone은 해당 resolution을 자동 실행하지 않는다. 상세 artifact와 보고서는
`training/results/v3-generic-time-expression-completion-v1/`에 있다.

## Entity Identity + Participant Resolution Completion v1

③ `SPAN_NATIVE_MULTILABEL` EntityMention과 ⑦ soft priority를 고정한 채 ⑥만 fresh training했다.
Curated RC에는 EntityMention 4,817개와 article-local cluster 1,753개가 있으며 singleton 1,016개,
multi-mention 737개, explicit cluster membership에서 파생된 MERGE 18,078쌍이다. ③/⑦ projection
audit 결과 same-type pair 중 적어도 한쪽이 TIER1인 최소 정책만으로 recoverable MERGE의
99.2412%를 표현했다. Participant는 TIER1 전체와 raw filler에 겹치는 TIER2만 허용하는 bounded
rescue로 conditional target recall 99.9376%를 확보했다. TIER2 raw evidence는 삭제하거나 semantic
negative로 바꾸지 않는다.

Entity Coreference는 기존 symmetric pair encoder를 사용하고 complete-link 조건으로 한 개의 약한
bridge가 cluster 전체를 합치지 못하게 했다. seed1008의 기존 train96/validation24 split, 최대8
epoch에서 internal MERGE PR-AUC 0.9475인 epoch8을 선택한 뒤 threshold0.6을 고정했다. Internal
MERGE P/R/F1은 0.9137/0.8367/0.8735, cluster B³ F1 0.8584, CoNLL F1 0.8386이다. 설정 고정 후
pilot_dev15 reference는 PR-AUC 0.9599, P/R/F1 0.9841/0.8154/0.8919, B³ F1 0.7771,
CoNLL F1 0.7126이다. CEAF_e는 SciPy가 없는 고정 환경에서 deterministic greedy fallback으로
계산했으므로 exact Hungarian CEAF와 구분한다.

Participant resolver는 directed pair encoder와 unweighted binary objective를 사용했다. 같은 split의
internal PR-AUC 0.8652인 epoch8과 threshold0.3을 고정했다. Gold Participant×Gold Entity internal
P/R/F1은 0.9788/0.6588/0.7875, exact target accuracy는 97.99%다. pilot_dev frozen reference는
P/R/F1 0.9647/0.5697/0.7163, target accuracy 92.36%이며 role accuracy는 ACTOR 98.46%,
TARGET 91.76%, PLACE 82.19%다. Fully predicted cascade에서는 exact recovered ENTITY_RESOLVED
27개 중 22개를 올바른 LocalEntity로 연결했다(81.48%). 가장 큰 end-to-end FIRST LOSS는 resolver가
아니라 B2/Event exact participant upstream miss 261개다. SPAN_ONLY 298개, contextual 37개,
VALUE_RESOLVED 1개는 정상 terminal/UNKNOWN으로 loss 밖에 두고 raw evidence를 보존했다.

Release-purpose fresh pilot_train120 epoch8 weights는 `weights/entity_coreference.pt` SHA256
`29e47da8976d2b315b310bde4731b3c8b6bb2088bec2e13ef131072277f089d9`와
`weights/participant_entity_resolution.pt` SHA256
`03be6024245e6c00164912fe011612385e9f1a91c3c3597b5ae5205b8c17c44e`다. 기존 Entity,
priority, Time, B2 weight와 threshold는 변경하지 않았다. 새 runtime config ID는
`eventframe_runtime_candidate_v3_entity_identity_participant_resolution_freeze`다.

pilot_dev15 canonical graph replay는 raw EntityMention 3,102개와 raw Participant 163개를 그대로
보존하면서 LocalEntity 472개, MENTIONS 472개, ACTOR/TARGET/PLACE edge 75/36/11개를 만들었다.
TIER1/TIER2는 646/2,456개로 이전과 exact parity이며 participant 때문에 단독 materialize된 TIER2
cluster는 34개다. fake Entity, dangling reference, duplicate Entity edge는 모두 0이고 기존
Event/Statement/Trigger/StatementType/B2/Entity/priority/Time/Event-Time output은 15/15 exact
parity다. 39개 article에서 ⑥ total delta는 평균 약 0.106초/article이며 candidate 폭발을 숨기지
않고 상세 분포를 `latency_metrics.json`에 기록했다.

최종 상태는 `ENTITY_IDENTITY_PARTICIPANT_RESOLUTION_RUNTIME_READY_WITH_LIMITATIONS`이다.
LocalEntity는 article-local identity이며 global Entity가 아니다. 해결되지 않은 Participant는 fake
Entity나 edge를 만들지 않는다. 다음 공식 work bundle은 별도 지시의 Event Identity / Coreference며
`READY_FOR_EVENT_IDENTITY_COREFERENCE=true`다. Presence, Assertor, ABOUT, CAUSES,
SUBEVENT_OF나 global Entity linking을 자동 실행하지 않는다.

## Event Identity / Coreference Completion v1

Current EventFrame을 기존 `EventFeatureBundle`로 migration했다. Historical mode의 tensor shape는
유지하면서 current-contract mode에 resolved LocalEntity representation, 실제 Event→Time attachment,
channel availability/count/confidence를 추가했다. 허용 135개 기사에서 proposition 2,133/2,133,
Trigger 2,133/2,133, raw ACTOR 1,179, TARGET 2,059, PLACE 726, resolved Entity 1,483,
Time 854, document context 2,133개 Event에 실제 non-zero tensor가 전달됐다. Optional feature 부재는
zero tensor와 explicit false mask로 표현하며 semantic mismatch나 MERGE hard prerequisite로 쓰지 않는다.
한 개 Gold Event proposition은 128-token sentence truncation으로 model-unrepresentable하여 별도
alignment diagnostic에 남겼다.

Curated 150개 전체에는 Event 2,374개와 unordered pair 27,745개(MERGE 390 / KEEP 27,355)가 있다.
기존 seed1008 train96/validation24 split을 유지하고, all MERGE와 deterministic hard/representative
KEEP 8:1 sampling, existing binary CE의 bounded MERGE weight 4를 사용했다. Tiny 6기사/120-step은
loss 감소와 MERGE/KEEP score 분리를 보여 all-KEEP collapse를 벗어났다. Main은 internal MERGE
PR-AUC로 epoch8을 선택하고 frozen grid에서 threshold0.6을 선택했다.

그러나 internal Gold Event/Gold feature MERGE P/R/F1은 0.1756/0.2466/0.2051,
PR-AUC 0.1662(base rate 0.0260)로 non-zero ranking signal은 확인했지만 명시된 F1 0.60 promotion gate를
통과하지 못했다. Cluster B3 F1은 0.9053, exact article partition 0.50, largest cluster 6으로 bridge
폭발은 없었으나 pair false split 125개가 false merge 26개보다 컸다. Frozen pilot_dev reference도
Gold/Gold feature F1 0.2273, Gold endpoint/predicted feature F1 0, fully predicted cascade F1 0이었다.

따라서 `EVENT_IDENTITY_BLOCKED`로 판정했다. EventFeatureBundle migration source와 실패 evidence는
보존하지만 `weights/event_coreference.pt`, runtime config, graph materialization은 승격하지 않았다.
기존 raw EventFrame과 모든 upstream runtime/graph output은 그대로 유지된다. 이 결과는 production
generalization certification이 아니며, Assertor는 Event identity를 hard prerequisite로 삼지 않으므로
별도 Work Bundle로 진행할 수 있다(`READY_FOR_ASSERTOR=true`). 상세 artifact는
`training/results/v3-event-identity-coreference-v1/`에 있다.

## Event Coreference Pair-Level Interaction Recovery v1

Work Bundle #4/#4.1의 실패 artifact를 파일별 SHA-256으로 동결한 뒤, 기존
EventFeatureEncoder→SymmetricPairEncoder 경로를 유지하고 7개 EventFeatureBundle hidden channel의
대칭 sum/product/absdiff를 channel별 32차원으로 투영하는 단일 explicit interaction branch만
추가했다. Optional channel은 BOTH_AVAILABLE일 때만 hidden interaction을 열고 one/neither 및 기존
count/confidence를 unordered metadata로 사용한다. 기존 12개 scalar policy feature는 변경하거나
중복 구현하지 않았다.

MPS fresh seed1008, 기존 train96/validation24 distribution과 objective를 유지한 24-epoch run에서
MERGE PR-AUC 기준 epoch8을 선택했다. Internal threshold0.6 P/R/F1은
0.4757/0.3356/0.3936, PR-AUC는
0.3943로 recovery baseline 0.2180/0.2230 PR-AUC/F1보다 각각
+0.1763/+0.1706 개선됐다.
그러나 사전 gate F1 0.40과 precision 0.50을 각각 근소하게 밑돌았으므로
`EVENT_IDENTITY_PAIR_INTERACTION_BLOCKED`다. Threshold0.7은 precision 0.7255지만 F1 0.3756으로
동시에 gate를 만족하지 못한다.

NO_EXPLICIT_INTERACTION frozen ablation은 PR-AUC 0.0293과 all-KEEP로 내려가 branch 사용을
입증했다. Trigger, resolved Entity, Target interaction의 FULL−masked PR-AUC 기여가 가장 컸다.
High-similarity/shared-Entity/same-Actor/same-Target KEEP FP는 각각 감소했지만 same-Entity MERGE와
Time-available MERGE recall debt가 남았다. Pilot Gold/Gold는 PR-AUC
0.6800, F1
0.6552다.

Active source-of-truth는 계속 `release/kf-deberta-base-kg-extractor/config/runtime.json`이며 active
Event coreference weight는 없다. Failed selected checkpoint는
`training/results/v3-event-coreference-pair-interaction-v1/cache/`의 재생성 가능한 연구 cache로만
보존한다. Runtime config/model/checkpoint manifest와 graph materialization은 변경하지 않았다.
다음 공식 lane은 Assertor이며 `READY_FOR_ASSERTOR=true`다. Event proposition, Trigger, B2, Entity,
Time, Gold/guideline, pair candidate/sampling/loss/class weight, complete-link clustering은 건드리지 않는다.

## Sentence Router CLS Representation Feasibility Check v1

Production과 release를 동결한 채 KF-DeBERTa sentence Router용 local representation만 비교했다.
Primary L8 비교는 active Semantic checkpoint의 frozen pre-document attention pooling과 L8 index-0
`[CLS]`를 각각 같은 2-layer Router와 independent EVENT/STATEMENT Presence bit head에 입력했다.
tokenizer contract상 index 0은 token id 2 `[CLS]`이며 attention 대상이지만 source-token mask에서는
제외된다. train96/internal-validation24, seed1008, 6 epoch와 checkpoint selection을 동일하게 유지했다.

L8 attention/CLS mean PR-AUC는 각각 0.9127/0.5345이고 4-state macro-F1은 0.5556/0.2134다.
99% gold-bearing retention에서 safe-drop은 6.02%/0.96%였다. L8 CLS는 문장 간 cosine median
0.999824, article 내 dimension variance median 0.00001084로 near-collapse가 확인되어
`CLS_ROUTER_NOT_PROMISING`이다.

사용자 요청으로 L8 완료 후 L12 CLS만 같은 계약으로 한 번 더 실행했다. L10, L12 attention,
다른 topology는 실행하지 않았다. L12는 collapse가 없었고(cosine median 0.566303, variance median
0.379119), internal EVENT/STATEMENT/mean PR-AUC 0.7703/0.7771/0.7737, 4-state macro-F1
0.4593, 99% retention safe-drop 5.34%를 기록했다. L8 CLS보다는 뚜렷이 회복했지만 frozen attention
reference에는 미달해 `CLS_L12_ROUTER_IMPROVED_BUT_BELOW_REFERENCE`다. Pilot dev mean PR-AUC는
attention/L8 CLS/L12 CLS가 각각 0.8926/0.5089/0.8023이었다.

이 결과는 representation feasibility evidence이며 runtime hard routing 승인이 아니다. Production
runtime, `DocumentContextEncoder`, backbone, Gold/guideline은 수정하지 않았고 Salience head도 만들지
않았다. 선택 checkpoint는 namespace 내부의 재생성 가능한 ignored cache이며 release weight가 아니다.
다음 source-of-truth는 `training/results/v3-sentence-router-cls-feasibility-v1/`의 report와 JSON
artifact다.


## Event Coreference Calibration & Prior Recovery v1

Work Bundle #4.2의 epoch8 explicit interaction checkpoint byte를 SHA256
`be70dfaf8a4643f73f63bc348f879f997ef746e563d322b6b3697a0fbbc5b72f`로 고정하고 재학습 없이 0.600–0.700 fine grid를 MPS에서 평가했다.
PR-AUC는 0.3943259295로 정확히 재현됐고, gate를 만족하는 threshold가 10개 있었다.
사전 selection rule은 threshold 0.640을 선택했으며 internal TP/FP/FN/TN은
46/29/100/5,450, P/R/F1은 0.6133/0.3151/0.4163이다. Phase A가 통과했으므로
PRIOR_A/B/C retraining은 `NOT_RUN_FINE_THRESHOLD_PASS`로 종료했다.

Frozen pilot_dev Gold/Gold는 PR-AUC 0.6800, P/R/F1 0.6923/0.6000/0.6429다.
Internal complete-link B³ F1 0.9178, pairwise F1 0.3438, split/merge error 113/13,
largest cluster 5이며 false-merge catastrophe는 없다. Pilot 15개 active release replay는
raw EventFrame 185개를 전부 보존한 채 LocalEvent 136개, accepted pair 49개,
`MEMBER_OF_EVENT` 185개를 만들었다. fake/dangling/duplicate lifted Event는 모두 0이고
serialization은 deterministic하다.

따라서 새 상태는 `EVENT_IDENTITY_RUNTIME_READY_WITH_LIMITATIONS`다. Active runtime은
`eventframe_runtime_candidate_v3_event_identity_limited_activation`, graph assembly는 `eventframe_partial_kg_assembly_v3_event_identity`이며 release weight는
`weights/event_coreference.pt`다. Checkpoint tensor와 interaction architecture/channel/policy는
변경하지 않았고 threshold만 0.64로 calibration했다. Raw EventFrame, member provenance,
accepted pair score, exact Time conflict와 complete-link가 유지된다. 이 threshold는 internal
validation engineering operating point이며 production/generalization certification이 아니다.
Fully predicted pilot의 주요 FIRST LOSS는 Event upstream miss 26개이고, Assertor는 Event
identity를 hard prerequisite로 요구하지 않는다(`READY_FOR_ASSERTOR=true`). 상세 source-of-truth는
`training/results/v3-event-coreference-calibration-prior-v1/`이다.

## Sentence Router Representation & Salience Feasibility v1

Production/runtime/release를 동결하고 cached KF-DeBERTa L12만 재사용해 sentence-local
representation을 비교했다. Presence에서는 fresh attention pooling이 CLS보다 우수했다. Internal
EVENT/STATEMENT/mean PR-AUC는 pool 0.8712/0.8876/0.8794, CLS
0.7907/0.7740/0.7823이며 99% gold-bearing retention safe-drop은 5.88%/4.92%였다.
두 representation 모두 collapse가 없었다. Historical L8 learned pool mean PR-AUC 0.9127은
active Semantic 학습 pooling을 포함한 reference이므로 공정한 L12 competitor로 사용하지 않았다.

Curated semantic Gold와 분리된 30기사/655문장 Salience sidecar를 작성했다. 이는 Presence label을
pseudo-label로 쓰지 않은 단일 Codex-agent 수동 editorial reference이며, human annotation이 아니고
unadjudicated다. 6개 held-out article에서 CLS/pool macro Spearman은 0.3487/0.3384,
pairwise accuracy는 0.6837/0.6829, NDCG@5는 0.8181/0.7761이었다. 둘 다 early-position
baseline NDCG@5 0.7577을 넘었지만 표본과 annotation quality 한계가 크다.

Presence는 fresh pool, Salience는 CLS를 선택해 local representation은 공유하지 않았다. 그 뒤
task별 local encoder와 하나의 inter-sentence Router만 공유한 최소 ablation은 separate baseline 대비
Presence mean PR-AUC +0.0027, safe-drop +0.0055, Salience Spearman +0.0734로 사전 3% guardrail을
통과했다.

마지막 shadow budget 실험에서 current Semantic baseline proposal recall은 0.8356이었다. Baseline
대비 recall 97% 보존을 통과한 conservative policy는 candidate/verifier workload를 3.62%/2.64%
줄이는 데 그쳤고 Router 포함 MPS latency는 42.62ms/article에서 45.42ms/article로 늘었다.
23.77% candidate 감소를 낸 aggressive policy는 baseline recall의 94.04%만 보존해 실패했다.
따라서 `READY_FOR_SENTENCE_ROUTER_RUNTIME_PROMOTION_REVIEW=false`다. EntityMention과
TimeExpression은 gate하지 않았고 production module, backbone, DocumentContextEncoder,
EventCoref, Curated Gold/guideline은 변경하지 않았다. 상세 source-of-truth는
`training/results/v3-sentence-router-representation-salience-v1/`이며 재현 가능한 experiment
checkpoint는 namespace 내부 ignored cache로만 남긴다.

## Assertor Source Attribution & ASSERTED_BY Runtime v1

Assertor를 EntityMention과 독립적인 raw/contextual source discovery, Statement-conditioned
attachment, optional Entity/LocalEntity resolution의 세 단계로 분리해 평가했다. Curated 계약은
Statement 2,387개, PRESENT/ABSENT/UNRESOLVED 1,256/133/998개와
ENTITY_RESOLVED/SPAN_ONLY/CONTEXTUAL 863/238/155개로 재확인됐다. Article-wide L12 cached
span universe는 Gold source candidate recall 1.0을 달성했고 추가 backbone forward는 없었다.

Gold source와 ABSENT safe negative를 구분하는 internal attachment PR-AUC는 0.9965이고 Gold
source acceptance accuracy는 1.0이었다. 그러나 PRESENT 내부 unlinked alternatives를 UNKNOWN으로
보존한 실제 predicted-source exact conditional attachment accuracy는 0.0224, exact F1은 0.0223,
CONTEXTUAL recall은 0이었다. Fully predicted internal cascade의 research-only resolved edge
precision도 0.0282였다. Exact source가 선택된 2건의 optional Entity resolution은 모두 성공했지만
support가 작아 승격 근거가 되지 않는다.

사전 gate의 predicted attachment 0.65와 resolved edge precision 0.70을 통과하지 못했으므로
`ASSERTOR_RUNTIME_BLOCKED`다. Blocker는 candidate representability나 Entity prerequisite가 아니라
`SAFE_SUPERVISION_CANNOT_RANK_PRESENT_UNLINKED_ALTERNATIVES`로 좁혀졌다. ASSERTED_BY/ABOUT edge,
runtime config, release manifest, graph assembly, 기존 Statement/Entity/Event/Time runtime은 변경하지
않았다. 다음 단계에는 reviewed candidate-level alternative supervision 설계가 필요하며 Assertor가
막힌 상태라 `READY_FOR_ABOUT=false`다. 상세 source-of-truth는
`training/results/v3-assertor-source-attribution-runtime-v1/`이다.

## Narrow ABOUT Endpoint Migration & Provisional Training v1

Assertor 결과는 immutable하게 유지하되 ABOUT이 sibling Statement lane이라는 계약에 따라, 별도 사용자
지시로 narrow endpoint migration과 provisional training을 수행했다. Curated ABOUT는 Statement 2,387개,
PRESENT/NONE/UNRESOLVED 650/1,640/97개, positive link 779개(Event 495, Statement 284)다.
한 Statement의 target은 최대 5개이고 multi-target source가 102개이므로, `Statement → Event|Statement`
direct proposition을 independent binary link로 점수화했다. Entity/Topic target과 self-link는 candidate
universe에서 제외했다.

Gold positive 779개는 모두 cached KF-DeBERTa L12 source/target span과 current Event identity lift에
정렬되어 candidate recall 1.0을 확인했다. 추가 backbone forward는 0회다. train96의 positive 440개는
전부 보존하고, unlinked pair를 canonical negative로 승격하지 않은 채 training-only provisional
pseudo-negative 3,520개를 8:1, deterministic hard/representative 50:50으로 사용했다. UNRESOLVED
source와 ambiguous endpoint는 pseudo-negative에서 제외했지만 Gold positive는 그대로 유지했다.

MPS seed1008의 12-epoch fresh run은 canonical positive MRR 기준 epoch3을 선택했다. Internal validation
positive 196개에서 Recall@1/3/5 0.1020/0.1990/0.2449, MRR 0.2202, NDCG@5 0.1774다.
Event/Statement Recall@5는 0.2985/0.1290이다. Frozen threshold0.5의 provisional PR-AUC/P/R/F1은
0.0190/0.0438/0.1020/0.0613이며 canonical precision으로 해석하지 않는다. High-score provisional
pseudo-negative 50건의 원문 수동 감사에서는 `POSSIBLE_MISSING_GOLD` 26건, `AMBIGUOUS` 14건,
`LIKELY_FALSE_POSITIVE` 10건이었다. Gold는 수정하지 않았다.

Freeze 후 pilot_dev15의 Gold positive 67개를 모두 유지해 평가했다. Gold/Gold Recall@5/MRR은
0.3433/0.2125이고 fully predicted cascade positive recovery는 2/67(0.0299)이다. Ranking gate,
provisional precision/F1 gate, qualitative negative-quality gate가 모두 실패했으므로 최종 상태는
`ABOUT_RUNTIME_BLOCKED_BY_NEGATIVE_CONTRACT_OR_MODEL`이다. ABOUT runtime/weight/graph edge는 추가하지
않았고 active release의 limited Event Identity, raw EventFrame, Assertor evidence, Entity, Time은 그대로다.
실패 checkpoint SHA256은 `bf058befdb0f4a07e82d6ec3666f3bab899ba67fcef019ed114ded518744c6da`이며
`training/results/v3-narrow-about-endpoint-migration-v1/cache/`의 재생성 가능한 local research cache로만
남긴다.

다음 단계는 reviewed candidate-level ABOUT negative authority 또는 ranking supervision 계약을 먼저
설계하는 것이다. `READY_FOR_CAUSES=false`이며 CAUSES/SUBEVENT_OF를 자동 실행하지 않는다. Curated
Gold/guideline, release runtime/manifest, Assertor, Event Identity를 건드리지 않는다. 상세 source-of-truth는
`training/results/v3-narrow-about-endpoint-migration-v1/`이다.

## CAUSES / SUBEVENT_OF & Full Canonical Article-local KG Integration v1

Event Identity 이후의 `LocalEvent → LocalEvent` 방향 relation adapter를 하나의 고정 architecture로
평가했다. Gold Event endpoint의 identity lift는 전부 가능했고 self collapse는 0이다. Lift 후 중복
positive는 CAUSES 7건, SUBEVENT_OF 1건이며 향후 edge 하나와 member provenance 목록으로 결정적으로
dedupe해야 한다. Current EventFeatureBundle member representation은 mean, availability는 any, count는
sum, confidence는 max로 집계한 뒤 기존 `DirectedPairEncoder`와 relation별 독립 binary head에 넣었다.

CAUSES internal candidate recall은 1.0이고 PR-AUC는 0.1806(base rate 0.00310)이었지만 선택
threshold 0.9의 P/R/F1은 0.2381/0.2273/0.2326이었다. SUBEVENT_OF candidate recall도 1.0이나
PR-AUC 0.00976, P/R/F1 0/0/0으로 신호가 부족했다. CAUSES의 precision 0.50/F1 0.40 gate와
SUBEVENT_OF의 precision 0.50/F1 0.30 gate를 각각 통과하지 못했으므로 두 lane은 release/runtime에
승격하지 않았다. 실패 checkpoint는 namespace 내부 ignored research cache에만 남긴다.

관계 밀집 train10은 공개 단일 API `runtime.ArticleLocalKGPipeline.from_config(...).run(article)`로
CPU strict 실행했고, frozen pilot15 graph replay와 합쳐 25기사를 감사했다. ARTICLE/EVENT/LOCAL_EVENT/
STATEMENT/LOCAL_ENTITY/TIME 노드는 25/336/245/243/802/21개다. Fake node, dangling/invalid endpoint,
duplicate/self/cross-article edge는 모두 0이며 serialization은 deterministic하다. Assertor, ABOUT,
CAUSES, SUBEVENT_OF는 historical/current gate 실패에 따라 명시적으로 disabled다. 따라서 현재 상태는
`ARTICLE_LOCAL_KG_READY_WITH_DEFERRED_LANES`, `READY_FOR_HF_V0_1_FINALIZATION=false`다. Release와 HF
staging은 변경하지 않았다. 상세 source-of-truth는
`training/results/v3-hard-relations-full-kg-integration-v1/`이다.

## Semantic Data-Sufficiency Learning-Curve Audit v1

Windows CUDA/FP32에서 historical train96만 사용해 nested 24/48/72/96 × seed
1008/2008/3008의 12개 Boundary Context verifier run을 수행했다. 모든 run은 동일한
function-preserving initialization과 48 optimizer updates를 사용했고, validation24 및 Round-04와
train overlap은 0이다. Round-04는 `FIXED_OBSERVED_EXTERNAL_BENCHMARK`로만 사용했으며 학습·subset,
epoch, threshold, architecture 선택에는 사용하지 않았다.

FULL96 validation Recall@5는 historical 대비 delta 0.015032로 tolerance 0.03을 통과했지만,
exact-vs-near PR-AUC delta가 0.041629로 tolerance 0.015를 초과했다. 따라서 현재 blocker는
`BLOCKED_FULL96_REPRODUCTION_DRIFT`이며, 24→96 curve로 96 article 부족 또는 ranking/abstention의
data-limited 상태를 결론내리지 않는다. 다음 단일 작업은 historical Boundary Context upstream,
initialization, optimizer parity를 고정한 FULL96 drift-isolation audit이다. Round-04 결과를 보고
grid/loss/budget을 수정하면 안 된다.

현재 #16 source-of-truth는
`training/experiments/v3_semantic_data_sufficiency_learning_curve_v1/`와
`training/results/v3-semantic-data-sufficiency-learning-curve-v1/`이다. 12개 verifier checkpoint,
HF/backbone/DCE/TOP32 cache는 production artifact가 아니며 ignored rebuildable cache로만 남긴다.
Active runtime config/checkpoint, release, Gold, guideline은 변경하지 않았다.
Harness `68307e8220639fbfa6674e622af936a3240a70a5`와 result
`c26f63f71ec8266aec450f9d26b26128b293fa7a`는 remote master에 push됐다. 따라서 다른
컴퓨터에서 Git sync만으로 blocker 분석을 이어갈 수 있다.

## Semantic Verifier Training-Path Stability & Dynamics Audit v1

#16 FULL96 drift를 N=96 고정 조건에서 base ordering과 shuffle seed로 분리했다. seed1008의
historical-order와 sorted-order sequence는 두 epoch 모두 96/96 위치가 다르고 동일 optimizer
group은 0/48이었지만, A-B validation PR-AUC/Recall@5 signed delta는 +0.006750/+0.002491로
사전 meaningful threshold보다 작았다. historical-order seed1008/2008/3008 spread도 validation
PR-AUC 0.005842, Recall@5 0.002491, Round-04 Recall@5 0.009738로 stable 범위였다.

Update 0/12/24/36/48 dynamics에서는 반복 late degradation이나 meaningful oscillation이 없었고,
ranking-abstention trade-off도 사전 기준으로 검출되지 않았다. Historical-order A의 validation
Recall@5는 historical tolerance를 통과했지만 PR-AUC는 0.714070으로 reference 0.748949 대비
0.034879 낮아 여전히 실패했다. 따라서 진단은 `BACKEND_OR_IMPLEMENTATION_DRIFT_REMAINS`이며,
ordering 또는 tested seed variance가 #16 drift의 주원인이라는 근거는 없다.

현재 source-of-truth는 `training/experiments/v3_semantic_training_path_stability_audit_v1/`와
`training/results/v3-semantic-training-path-stability-audit-v1/`이다. 다음 단일 실험은 Mac MPS와
Windows CUDA의 exact replay다. Round-04는 계속 selection에 사용하지 않으며, data-size grid,
loss, architecture, threshold를 바꾸지 않는다. A/C/D diagnostic checkpoint와 tensor/HF cache는
ignored rebuildable cache로만 남고 production runtime/release/Gold/Guideline은 변경하지 않았다.

## Semantic Verifier Responsibility & Supervision Sufficiency Audit v1

#17 CUDA historical-order seed1008 update48 verifier state SHA
`544d6eb626287323a655025f5991c669c816ee34b51ced41132c178ebf7869e3`를 검증해 primary
diagnostic checkpoint로 재사용했다. Verifier, DCE, backbone, Joint TOP32 proposer는 모두
freeze하고 train96-only statistics와 fixed 30-epoch single-Linear probe로 DCE_FULL evidence,
verifier pre-logit components, final scalar를 비교했다. Round-04는 관찰된 external diagnostic에만
사용했고 Round-05는 사용하지 않았다. Mac MPS historical exact replay는 이 작업과 분리해 deferred했다.

Round-04에서 DCE_FULL START/END PR-AUC는 0.767850/0.866015, verifier pre-logit은
0.664900/0.849944, final scalar는 0.311945/0.462909였다. Pre-logit START/END AUROC는
0.895025/0.946204로 `AXIS_INFORMATION_STATUS=STRONG`이며 geometry macro F1 0.520062로
`GEOMETRY_HIDDEN_SEPARABILITY=MODERATE`다. START에는 DCE→hidden transformation-loss signal이
있고 START/END 모두 hidden→scalar compression signal이 있다. 이에 primary diagnosis는
`MIXED_RESPONSIBILITY_SUPERVISION_GAP`이다. 이 결과는 BCE 폐기나 multi-head 승격 근거가 아니다.

Cell abstention에서는 C0 max-scalar 대비 C2 hidden-pool AUROC가 validation
0.951395→0.921966, Round-04 0.870136→0.863912로 개선되지 않아
`CELL_RESPONSIBILITY_SPLIT_SIGNAL=false`다. Multi-Gold는 primary axis probe에서 제외했고 별도
selection/decoding 문제로 유지한다. 다음 단일 실험은 DCE, candidate universe, data, update budget을
고정한 동일 verifier의 start/end auxiliary-supervision controlled A/B다.

현재 #18 source-of-truth는
`training/experiments/v3_semantic_verifier_responsibility_supervision_audit_v1/`와
`training/results/v3-semantic-verifier-responsibility-supervision-audit-v1/`이다. Probe model과
feature tensor는 production artifact가 아니며 저장·추적하지 않는다. #17 Run A checkpoint와
HF/DCE/TOP32 cache는 ignored rebuildable cache로 남는다. Active runtime config/checkpoint, release,
Gold, guideline과 기존 experiment result는 변경하지 않는다.

## Semantic Verifier Start/End Auxiliary-Supervision Controlled A/B v1

Windows CUDA/FP32에서 historical train96, fixed Joint TOP32 candidate universe, historical
article order, function-preserving base initialization, main exact/non-exact BCE와 48 optimizer
updates를 고정했다. A/B 모두 동일 wrapper와 auxiliary-head initialization을 사용했고, B에서만
single-Gold·main-active candidate에 START/END loss를 각각 0.25로 적용했다. Auxiliary 대상은
1,822 cells, 57,359 candidates이며 START/END positive prevalence는 0.210446/0.261668이다.

Validation exact-vs-near PR-AUC는 A→B 평균 delta -0.019436이고 세 seed 모두 감소했다.
Round-04 PR-AUC는 +0.006277로 세 seed 모두 소폭 증가했지만 Recall@5는 -0.002435였다.
Round-04 START/END scalar PR-AUC delta는 +0.006385/+0.003485로 사전 strong signal보다 작고,
wrong-start/wrong-end win-rate delta도 +0.002012/-0.001650에 그쳤다. Validation zero-Gold AUPRC는
-0.015217, fixed-threshold F1은 -0.026813으로 material regression guard를 통과하지 못했다. 따라서
`AUXILIARY_SUPERVISION_STATUS=NOT_SUPPORTED`이며 #18 multi-axis supervision 가설은 이 고정
auxiliary-head/loss intervention에 대해 `WEAKENED`다. Auxiliary head 자체의 axis decodability가 높아도
기존 inference scalar의 exact ranking 개선으로 이어지지 않았다.

현재 #19 source-of-truth는
`training/experiments/v3_semantic_start_end_aux_supervision_ab_v1/`와
`training/results/v3-semantic-start-end-aux-supervision-ab-v1/`이다. 다음 작업은 auxiliary weight sweep이
아니라 representation/generalization diagnosis로 복귀하는 것이다. Round-04는 계속 selection에 쓰지
않고 Round-05는 untouched로 유지한다. Probe/checkpoint/tensor 및 HF/DCE/TOP32 cache는 추적하지 않으며,
active runtime config/checkpoint, release, Gold, guideline은 변경하지 않았다.

## Semantic Exact Scalar Composition & Readout Sufficiency Audit v1

#19 A/B verifier checkpoint 6개를 manifest SHA로 검증하고 완전히 freeze한 뒤, #18/#19의 동일
512-d pre-logit hidden 위에서 current scalar(R0), fresh exact Linear(R1), fixed START×END(R2),
OOF axis Linear fusion(R3), scalar+axis Linear fusion(R4)을 비교했다. Train96의 START/END stacking은
article-level deterministic 5-fold cross-fitting으로 생성했고 validation/Round-04에는 train96 full
probe를 적용했다. Round-04는 readout 선택이나 tuning에 사용하지 않았다.

Validation에서 선택된 A readout은 `R0`이며 single-Gold exact PR-AUC는 R0 0.722843에서
0.722843로 변했다. 동일 family의 Round-04 PR-AUC는 R0 0.439756에서 0.439756로 변했다.
사전 gate에 따른 최종 진단은 `AUX_HIDDEN_INFORMATION_WAS_USABLE`이고
`CURRENT_SCALAR_READOUT_INSUFFICIENT=false`다.
이 diagnostic readout은 production scalar, threshold, decoder 또는 zero-Gold abstention을 대체하지 않는다.

현재 #20 source-of-truth는 `training/experiments/v3_semantic_exact_scalar_composition_audit_v1/`와
`training/results/v3-semantic-exact-scalar-composition-audit-v1/`이다. #19 recovery checkpoints와 hidden
tensor cache는 ignored/rebuildable이고 추적하지 않는다. Runtime, release, Gold, guideline, Round-04/05와
기존 experiment result는 변경하지 않았다. 다음 단일 실험은 `#19 auxiliary hidden plus explicit composition controlled training/inference A/B`다.
