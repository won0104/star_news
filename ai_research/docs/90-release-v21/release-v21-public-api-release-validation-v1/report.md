# Release V2.1 Work Package E — Public API / Release Validation

## 결과

Release V2.1의 public API, output profile, portable package, 문서와 배포 검증을 완료했다. 기본 출력은 compact `PUBLIC`이며 `AUDIT`와 `DEBUG`는 같은 public graph identity를 유지한 채 보조 진단 정보의 노출 범위만 달리한다. 모델, checkpoint, threshold, Gold, preprocessing, public ontology와 graph semantics는 변경하지 않았다.

Hugging Face `sysy9292/kf-deberta-base-kg-extractor`의 `main`에 revision `23ade4ef64d3d9758351806f7bb9eb3ba08d8ca7`을 게시했다. 이 revision을 새 임시 경로에 직접 내려받아 repository root 없이 pipeline construction, inference, 세 profile, serialization, public validation을 다시 통과했다. 원격의 12개 checkpoint는 manifest의 크기와 SHA-256에 전부 일치한다.

## Public API와 profile

1. **기본 output profile은 무엇인가?** `PUBLIC`이다. `pipeline.run(article)`과 assembler의 기본 projection이 `PUBLIC`을 사용한다.

2. **PUBLIC에는 무엇이 포함되는가?** `schema_version`, `output_profile`, article, public nodes/edges, node/edge evidence와 provenance, compact coverage/status, release·policy provenance, validation, non-debug warning/source failure를 포함한다.

3. **PUBLIC에서 무엇이 제외되는가?** raw `source_lanes`, full unmaterialized-evidence body, full trace, Participant filler/candidate inventory, raw EventFrame·LocalEvent·LocalEntity carrier, canonicalization pair diagnostics를 제외한다. public nodes/edges 자체의 evidence와 provenance는 유지한다.

4. **AUDIT은 무엇을 더 노출하는가?** full unmaterialized evidence, 상세 coverage, projection/policy trace를 제공하되 raw source-lane body는 제외한다. 고급 사용자는 `assemble_with_audit(...)`로 graph output과 `AssemblyAuditTrail`을 함께 받을 수 있다.

5. **DEBUG는 무엇을 더 노출하는가?** pre-E pass-through 수준의 raw source lanes, EventFrames/model lanes, unmaterialized evidence, source failures와 full projection trace를 보존한다. `output_profile="DEBUG"` 자체가 비싼 runtime tracing을 켜지는 않으며, 필요하면 별도로 `debug_trace=True`를 지정한다.

6. **profile 간 nodes/edges는 동일한가?** 동일하다. 대표 fixture와 frozen prediction graph에서 node/edge ID, kind/type, semantic properties, endpoint가 profile 간 일치했다. profile projector는 representation-only이다.

## 크기와 temporal compatibility

7. **PUBLIC은 DEBUG보다 얼마나 작은가?** 네 대표 입력의 UTF-8 compact JSON 합산 비율은 `PUBLIC/DEBUG = 0.1497570891`이다. 실제 예시는 `20,360 / 107,240` bytes, small frozen graph는 `12,866 / 49,024`, median graph는 `3,201,081 / 21,488,302`, dense graph는 `22,028,621 / 147,048,136` bytes였다. 모든 사례에서 `PUBLIC < AUDIT <= DEBUG`였다. 임의 비율 gate는 사용하지 않았다.

8. **public graph schema는 그대로인가?** `articlelocal-kg-public-v2` 그대로다. node allowlist는 `ARTICLE, EVENT, STATEMENT, ENTITY, TIME`; edge allowlist는 `COVERS, CONTAINS_STATEMENT, MENTIONS, ACTOR, TARGET, PLACE, OCCURRED_ON`이다. dangling/fake node는 모두 0이다.

9. **활성 B3/C/D policy는 무엇인가?** EVENT는 `EVENT_SPAN_EQUIVALENCE_STRICT_V1`, TIME representation은 `TEMPORAL_SURFACE_CANONICALIZATION_V1`, Entity safety는 `ENTITY_IDENTITY_CONSTRAINT_V1`, composite는 `RELEASE_V21_TEMPORAL_IDENTITY_CANONICALIZATION_V1`, derivation은 `TIME_NORMALIZER_V2`다. `EVENT_TIME_RESCUE_V1`은 비활성이다. resolution execution은 `ENTITY_ONCE_PARTICIPANT_CHUNKED_STREAMING_ARGMAX_V1`이다.

10. **legacy V1 temporal fact는 어떻게 설명되는가?** TimeNormalizer V2는 새 deterministic derivation과 rescue eligibility를 관장한다. 기존 V2 temporal graph fact는 backward compatibility를 위해 유지되므로 모든 public TIME이 V2에서 새로 normalize됐다는 뜻은 아니다. frozen C replay에서 V1 normalized 822건 중 458건은 V2 기준 unresolved로 재분류됐고, public TIME 459개 중 legacy-compatible fact만으로 존재하는 것은 164개, OCCURRED_ON 609개 중 그 TIME에만 의존하는 것은 281개였다. E에서 이 fact를 삭제하거나 재해석하지 않았다.

## 무결성, 실행 검증, publication

11. **weights/checkpoints는 동일한가?** 동일하다. checkpoint manifest 12행의 파일 크기와 SHA-256을 local portable package와 게시된 원격 snapshot에서 모두 검증했다. `MODEL_RETRAINED=false`, `CHECKPOINT_CHANGED=false`, `WEIGHT_DIGEST_CHANGED=false`다.

12. **release-only smoke는 통과했는가?** 통과했다. `python -I`의 clean temporary copy에서 import, config/checkpoint resolution, pipeline construction, one-article inference, PUBLIC/AUDIT/DEBUG, serialization, validation을 실행했다.

13. **package가 repository-root import와 독립적인가?** 독립적이다. smoke의 `runtime` module은 임시 release copy에서 load됐고 training/tests/root-only runtime module은 import되지 않았다. Hugging Face 원격 snapshot에서도 같은 조건을 다시 통과했다.

14. **D의 380/380 상태는 보존됐는가?** 보존됐다. D의 frozen evidence는 requested/completed/failed `380/380/0`, pre-D 379 semantic parity true, long-article OOM fixed true다. E는 payload sizing을 위해 380건 resolution audit을 불필요하게 반복하지 않았다.

15. **Hugging Face publication은 완료됐는가?** 완료됐다. remote `main`과 public raw README가 `23ade4e...`를 가리킨다. E는 runtime/config/manifest/docs/examples만 새 commit에 반영했으며 checkpoint weight 내용을 수정하거나 다시 생성하지 않았다.

16. **remote smoke는 통과했는가?** 통과했다. 원격 revision의 106개 파일을 snapshot으로 내려받고, checkpoint 12개 무결성 및 실제 inference/profile/serialization/validation을 검증했다.

17. **Release V2.1은 완료됐는가?** local 및 remote gate가 모두 통과했으므로 완료다. Work Package E는 새 model research나 semantic rule을 시작하지 않는다.

## 구현 및 테스트

- `ASSEMBLY_OUTPUT_PROFILE_V2` projector가 PUBLIC/AUDIT/DEBUG exposure를 분리한다.
- normal pipeline과 public assembler 모두 명시적 `output_profile`을 받으며 기본은 PUBLIC이다.
- release manifest가 B3/C/D policy ID, output profile, D runtime evidence, config/ontology/checkpoint digests를 고정한다.
- README, release notes, real quick-start/example output을 V2.1 기준으로 갱신했다.
- stale historical test fixture에는 누락됐던 disabled `entity_candidate_restriction` lane row만 추가했다. runtime semantics는 변경하지 않았다.
- focused/regression unit tests: 121 PASS, 0 failure, 0 error, 1 CUDA-unavailable skip.
- source/release changed reusable module parity, compile, JSON validation, `git diff --check`: PASS.

## Machine-readable summary

```text
WORK_STATUS=RELEASE_V21_PUBLIC_API_AND_RELEASE_VALIDATION_COMPLETE
RELEASE_VERSION=2.1
PUBLIC_GRAPH_SCHEMA_VERSION=articlelocal-kg-public-v2
OUTPUT_PROFILE_CONTRACT=ASSEMBLY_OUTPUT_PROFILE_V2
DEFAULT_OUTPUT_PROFILE=PUBLIC
COMPACT_PUBLIC_ENABLED=true
PUBLIC_GRAPH_SEMANTICS_CHANGED=false
MODEL_RETRAINED=false
OPTIMIZER_STEP_COUNT=0
CHECKPOINT_CHANGED=false
WEIGHT_DIGEST_CHANGED=false
ACTIVE_EVENT_CANONICALIZATION_POLICY=EVENT_SPAN_EQUIVALENCE_STRICT_V1
ACTIVE_TEMPORAL_CANONICALIZATION_POLICY=TEMPORAL_SURFACE_CANONICALIZATION_V1
ACTIVE_ENTITY_IDENTITY_POLICY=ENTITY_IDENTITY_CONSTRAINT_V1
ACTIVE_DERIVATION_POLICY=TIME_NORMALIZER_V2
EVENT_TIME_RESCUE_POLICY_ACTIVE=false
RESOLUTION_EXECUTION_MODE=ENTITY_ONCE_PARTICIPANT_CHUNKED_STREAMING_ARGMAX_V1
KNOWN_LONG_ARTICLE_OOM_FIXED=true
RUNTIME_ARTICLES_REQUESTED=380
RUNTIME_ARTICLES_COMPLETED=380
RUNTIME_ARTICLES_FAILED=0
PUBLIC_SCHEMA_CHANGED=false
DANGLING_EDGE_COUNT=0
FAKE_NODE_COUNT=0
RELEASE_ONLY_SMOKE_PASS=true
HF_PUBLICATION_STATUS=PUBLISHED
HF_REMOTE_SMOKE_PASS=true
RELEASE_V21_COMPLETE=true
```
