# V3 task 계약 매트릭스 — 단계 3 compiler / 단계 4 architecture

> Historical 19-task matrix. The active registry removes `role_entity` and
> trains unified Native/ROLE identity in P3; see
> [unified-entity-identity-v1.md](unified-entity-identity-v1.md).

이 표는 **target이 컴파일되는 책임**과 **실제 head 연결 상태**를 구분한다. `models/v3_pretraining/task_contract.py`의 19개 task와 일치한다. 단계 5에서 추출·속성 8개, 단계 6에서 Entity 3개, 단계 7에서 Time 2개, 단계 8에서 Event coreference 1개가 fresh registry와 Gold loss에 연결됐다. 나머지 5개는 등록 전까지 `UnimplementedTaskError`로 남는다. 표의 "예정" 표기는 아직 연결하지 않은 task를 뜻한다. exact 문자 잔차·cross-window는 `extraction-head-migration.md`, Entity union은 `entity-union-closure-contract.md`, Time은 `temporal-contract.md`, final Event는 `cluster-representation-contract.md`에 검증 범위를 기록했다.

공통 입력: 128-token sentence/bridge window, 고정 KF L8/L10/L12 FP32, 요청당 공유 L8 DCE 1회. 추가 backbone/DCE 호출 예산은 아래 전 task에서 **0회**다. `fresh`는 고정 pretrained backbone 외 learned weight가 v3 run에서 새로 만들어져야 함을 뜻한다. 5번 head의 Gold loss 연결은 완료했지만 실제 pretrained model 품질이나 본학습 결과는 아니다.

예정 gradient 범위는 각 행의 task head에서 동일 run의 공유 DCE/candidate projection까지다. backbone에는 gradient가 흐르지 않는다. 단계별로 upstream을 동결하면 그 지점에서 끊으며, hard coreference membership은 미분 경로가 아니다. 이 공통 범위를 벗어나는 Primary 전용 adapter와 후보 유지 정책은 표에 별도 적었다. 실제 loss 연결은 후속 단계에서 확인한다.

| Task / 목적 | 입력 표현 | r05.3 target과 mask | 예정 loss → 출력 → consumer | 새 weight·gradient 범위 | 추가 backbone / DCE |
|---|---|---|---|---|---|
| `semantic_proposer` Event/Statement 후보 | L8→공유 DCE token | Event/Statement exact span 양성; 미기록 임의 의미 span은 음성 아님 | 제한된 proposal loss → 후보 셀 → boundary/validity/trigger/role/identity | proposer·DCE fresh; 여기까지 gradient 연결은 synthetic 검증, 실제 Gold loss는 5번 | 0 / 0 |
| `semantic_boundary` 문자 근거 | proposal, L8 RAW+DCE | Event/Statement exact start/end, signed residual, cross-window link; 표현 불가면 숨기지 않고 계수 | exact boundary loss 예정 → 문자 span → semantic validity/PUBLIC 근거 | canonical boundary/fusion fresh; Gold 연결 5번 | 0 / 0 |
| `semantic_validity` 의미 적격성 | proposal, L8 RAW+DCE | 기록된 semantic 양성; 임의 누락 span 음성화 금지 | eligibility loss는 검증된 후보 음성 정책 필요 → keep score → extraction | canonical semantic head fresh; Gold 연결 5번 | 0 / 0 |
| `trigger` 사건 트리거 | Event 후보, L8 | Event.trigger exact span; Event 없는 구간 mask | span/boundary loss 예정 → Trigger span → Event feature | fresh; upstream 공유 gradient 정책 5번 | 0 / 0 |
| `participant` ACTOR/TARGET/PLACE source | Event 후보, L8+DCE+Event | role별 exact source span, nullable Entity endpoint는 별도 `role_entity` mask | role-conditioned span loss 예정 → role span/ID → resolution/identity | fresh; Event/DCE까지 흐름 5–6번 | 0 / 0 |
| `entity_mention` 5-type Entity | L12+DCE와 role/Assertor 유래 후보 | Gold mention exact span + PERSON/ORGANIZATION/LOCATION/PRODUCT/GENERIC; role-only/중첩 보존 | type/span loss 예정 → Entity mention → resolution/coref | fresh; candidate projection·DCE 공유, union 정책 6번 | 0 / 0 |
| `time_mention` textual Time | L10+DCE | Time span 양성; normalized null도 추출 양성 | span loss 예정 → TimeMention → Event–Time/normalizer | fresh; DCE 공유, 7번 | 0 / 0 |
| `assertor_source` 발화 주체 근거 | Statement, L8+DCE | Assertor span 존재 시 양성; null이면 source loss 무시, Entity 해소는 별개 | conditioned span loss 예정 → Assertor span → ASSERTED_BY resolution | fresh; DCE 공유, 9번 | 0 / 0 |
| `statement_type` Statement 유형 | Statement candidate+DCE | Gold `Statement.type`; Statement 부재 mask | masked CE 예정 → 유형 → Statement carrier/ABOUT | fresh; DCE 공유, 5번 | 0 / 0 |
| `entity_priority` exact 후보 유지 | NER/role union 뒤 exact candidate | Gold 후보 유지 양성; 중요도 rank 아님 | 양성 softplus loss 연결 → 임시 priority score → bounded 후보 | fresh, 공유 DCE·projection gradient 연결; 음성/calibration은 미승인 | 0 / 0 |
| `time_normalization` Time 값·형식 | textual Time+원문 | normalized value 있으면 SUPERVISE, null은 value loss만 IGNORE | 전체 문자+format CE 연결 → source-constrained normalized/unresolved Time | fresh; 공유 DCE·projection gradient 연결, PUBLIC calendar 적격성 별도 | 0 / 0 |
| `role_entity` role→Entity 해소 | directed role span / 통합 Entity cluster | resolved role×Entity 전체에서 해당 endpoint 양성, 나머지 eligible 표본 음성; SPAN_ONLY/null은 resolution IGNORE | directed pair BCE 연결 → exact role endpoint → local Entity ID | fresh; 공유 DCE·projection gradient 연결, chunked pair | 0 / 0 |
| `event_time` Event→Time attachment | Event/Time directed pair | Event×Time 전체 중 `event.times` 양성; null normalization Time도 textual attachment 대상 | directed pair BCE 연결 → attachment → final Event feature/Time | fresh; 공유 DCE·projection gradient 연결, Gold positive cap 없음 | 0 / 0 |
| `assertor_entity` Statement→Entity | Assertor source/Entity directed pair | resolved Assertor×Entity 전체에서 Gold endpoint 양성; unresolved는 IGNORE | directed pair loss 예정 → ASSERTED_BY → relation/runtime | fresh; 9번 | 0 / 0 |
| `entity_coreference` 기사 내 Entity identity | NER/role 통합 candidate의 unordered pair | 같은 Gold Entity cluster 양성, 다른 cluster 결정적 표본 음성 | symmetric CE 연결 → complete-link local Entity identity → endpoint remap | fresh; 공유 DCE·projection gradient 연결, chunked pair | 0 / 0 |
| `event_coreference` 사건 occurrence identity | 공유 Event/Trigger/role/Entity/Time 8채널과 unordered Event pair | 같은 Gold EventCluster 양성, 다른 occurrence 결정적 표본 음성 | symmetric CE 연결 → complete-link final cluster ID와 member→cluster remap → 9/10번 transient consumer | fresh; source 채널·공유 DCE gradient 연결, hard membership은 미분 불가 | 0 / 0 |
| `about` Statement→EventCluster | Statement + final cluster compact bundle | Statement×EventCluster 전체 closed-world; 기록된 ABOUT만 양성 | directed pair BCE 예정 → ABOUT edge → PUBLIC selection | fresh adapter/head; final ID 공유, 9번 | 0 / 0 |
| `causes` EventCluster→EventCluster | final cluster compact bundle, 방향 채널 | 서로 다른 cluster ordered pair 전체 closed-world; 기록된 CAUSES만 양성 | directed pair BCE 예정 → CAUSES edge → PUBLIC selection | fresh adapter/head; symmetric scorer 재사용 금지, 9번 | 0 / 0 |
| `primary` 상대 중요도 | final EventCluster∪Statement, 작은 전용 adapter | Gold rank 엄격 비교쌍 SUPERVISE; 동순위 TIE_IGNORE; 아직 selection threshold 없음 | pairwise ranking loss 예정 → 유한 scalar score/status → 후속 선택 | 전용 adapter는 현재 fresh; scorer/gate는 10번에 fresh 구현, backward 전 scalar 변환 금지 | 0 / 0 |

## 공통 경계

- compiler의 Gold ID는 target 결합 키다. raw serving 입력에는 Gold를 넣지 않는다. `PairUniverse`의 negative는 r05.3에서 허용한 eligible domain에만 존재하고, 학습 표본화는 평가 universe를 바꾸지 않는다.
- source view window 중복은 절대 문자 좌표로 닫는다. 5번 extraction head는 signed boundary/long-span을 128-token truncate로 학습 mask 처리하지 않는다. 후속 identity/relation task는 해당 단계에서 별도 연결한다.
- `FrozenBackboneFeatureBuilder`는 이미 주입된 고정 backbone을 한 번 `no_grad`로 실행하고 일반 tensor L8/L10/L12만 넘긴다. v2.3-rc2의 selective capture/all-valid/direct gather 구현을 수정하지 않는다. `@inference_mode` 서빙 출력을 trainable DCE에 직접 전달하지 않는다.
- 공유 substrate는 single-owner DCE, candidate projection, Event/Statement/Entity/Time 공통 표현이다. learned task projection은 각 head가 소유한다. 기존 checkpoint들의 DCE를 같은 좌표계로 합치지 않는다. fresh manifest는 현재 생성되는 모든 parameter의 owner/digest를 기록하고, 미구현 task weight는 기록하지 않는다.
- `CompactRepresentationBundle`은 article version/content/producer/config/revision/layer·mix/context/dtype/tokenizer/layout과 ordered IDs/mask를 검사하는 요청 범위 handoff다. tensor는 마지막 consumer 이후 닫는다. 장기 semantic/PUBLIC carrier에는 `ScalarSemanticRecord`의 scalar 근거만 허용한다.
- 단계 2의 Gold blocker가 유지된다. 이 표는 전체 Gold readiness, 실제 head 학습, 성능, 본학습 checkpoint, 서비스 threshold 승인을 뜻하지 않는다.
