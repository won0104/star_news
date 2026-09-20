# V3 Article-local KG Structural & Qualitative Review v1

## 결론

`KG_STRUCTURALLY_VALID_BUT_SEMANTICALLY_WEAK`이며 `READY_FOR_INACTIVE_LANE_READINESS_AUDIT = true`다. release-freeze runtime과 canonical ⑧ assembler를 튜닝 없이 사용해 pilot_dev 15개 전부와 pilot_train article_id 정렬 선두 10개, 총 25개 graph를 검토했다.

## 세 평가 층

### STRUCTURAL_VALIDITY

- 25/25 schema 및 serialization PASS
- dangling reference 0, duplicate node 0, duplicate edge 0, invalid endpoint 0
- Event/Statement count parity: True/True
- raw filler preservation: True
- NOT_RUN status preservation: True
- ASSEMBLY_BUG: 0

### QUANTITATIVE_ERROR

Curated Gold는 pilot_dev 15개의 evaluator/FIRST LOSS에만 사용했다. exact kind/offset을 primary로 하고 IoU>=0.5는 boundary diagnostic으로만 사용했다. graph qualitative review를 Gold metric으로 대체하지 않았다.

- Dev FIRST LOSS counts: `{"B2_ACTOR_SPAN_MISS": 15, "B2_PLACE_SPAN_MISS": 13, "B2_TARGET_SPAN_MISS": 66, "CONTEXTUAL_CROSS_SENTENCE_UNSUPPORTED": 27, "EVENT_BOUNDARY_NOT_EXACT": 129, "EVENT_NOT_IN_FINAL_GRAPH": 528, "PARTICIPANT_TRUE_POSITIVE": 42, "STATEMENT_BOUNDARY_NOT_EXACT": 15, "STATEMENT_NOT_IN_FINAL_GRAPH": 61, "TRUE_POSITIVE_FINAL": 127, "WRONG_PROPOSITION_KIND_EXACT": 12}`

### QUALITATIVE_PLAUSIBILITY

- Event/Statement `plausible`은 의미 종류가 맞는지를 세며, 경계 오류·중복은 별도 count이므로 mutually exclusive 합계가 아니다.
- Participant `plausible`은 해당 role 의미와 경계가 사람이 읽기에 타당한 filler 수다.
- `PARTIAL_MINI_MAP`은 핵심 서사 일부가 읽히는 경우, `SEMANTICALLY_WEAK`는 중심축 누락/중복/spray로 안정적 지도로 읽기 어려운 경우다.
- Mini-map rating: `{"PARTIAL_MINI_MAP": 16, "SEMANTICALLY_WEAK": 9}`
- Event plausible / total: 291 / 308
- Statement plausible / total: 196 / 197
- ACTOR plausible / total: 94 / 107
- TARGET plausible / total: 72 / 136
- PLACE plausible / total: 17 / 26
- Failure taxonomy: `{"ACTOR_BAD": 13, "ASSEMBLY_BUG": 0, "CROSS_EVENT_LEAKAGE": 4, "EVENT_BOUNDARY_BAD": 111, "EVENT_FALSE_POSITIVE": 17, "EVENT_MISSING": 56, "EVIDENCE_LOSS": 0, "MISSING_INACTIVE_LANE": 25, "MIX_FAILURE": 11, "MULTI_EVENT_FAILURE": 60, "PARTICIPANT_SPRAY": 42, "PLACE_BAD": 9, "STATEMENT_FALSE_POSITIVE": 31, "STATEMENT_MISSING": 2, "TARGET_BAD": 64}`

구조적으로 graph는 안정적이고 unresolved evidence도 손실되지 않았다. 다만 사람이 읽는 미니 지도로서는 Semantic proposition의 false positive/boundary와 B2 participant sparsity·오연결이 주요 제약이다. inactive lane 부재는 오류가 아니라 missing lane으로 집계했다.

## 판단

25개 중 실제 사건·주장 구조가 부분적으로 읽히는 graph는 존재하지만, proposition/participant 정확도가 고르게 충분하지 않아 완전한 의미 지도라고 부르지 않는다. 구조가 정성 실패의 원인은 아니며, model output을 충실히 보존하는 partial carrier로서 역할한다.

다음 작업은 threshold나 topology tuning이 아니라 inactive lane별 checkpoint/semantic-contract readiness audit다. Entity/Time/Trigger를 곧바로 활성화하지 말고 Curated 계약 호환성과 checkpoint provenance부터 확인해야 한다.

## 보호 상태

- MODEL_MODIFIED=false
- THRESHOLD_TUNED=false
- TOPOLOGY_MODIFIED=false
- GOLD_MODIFIED=false
- GUIDELINE_MODIFIED=false
- PILOT_TEST_USED=false
- ORIGINAL_1K_DEV_TEST_USED=false
- ASSEMBLY_BUG_FIXED=false
- NEXT_WORK_AUTOMATICALLY_EXECUTED=false
