# 14번 Gold-free v3 serving 계약

Owner DAG·alias/storage·예외 해제는 `v3-lifecycle-contract.md`, rc2 구조 검사·pair 예산·측정 한계는 `optimization-regression-plan.md`에 자세히 기록한다.

## 진입점과 모델 상태

`runtime.v3_pretraining.serve_cli`는 `article_id`·원문 `content`와 선택적인 제목·기사 버전·게시 시각 JSON을 받아 `public`/`audit` JSON을 반환한다. `V3ServingWorker.analyze`가 동일한 Python API다. startup의 `load_diagnostic_worker`는 stage 13의 완전한 smoke checkpoint를 strict registry/parameter/config/pinned producer 검사 후 열며, Gold 기사나 split을 request에 읽지 않는다. `producer_version=V3_STEP13_SMOKE_DIAGNOSTIC`, `primary_score_status=UNTRAINED_FRESH_WEIGHT_DIAGNOSTIC`, PUBLIC `PERSISTENCE_NOT_READY`를 유지한다. 본학습·threshold 승인·DB 저장 경계는 아니다.

원문 → 128-token sentence/bridge layout → frozen KF-DeBERTa **1회** selective L8/L10/L12 → shared DCE **1회** → exact source 추출 → Statement-conditioned Assertor → NER/role/Assertor Entity union 및 5-type model evidence typing·resolution → Event/Time/Trigger/role/Entity direct gather → learned Event-Time attachment → all-member Event identity → final cluster relation/Primary → 원문 근거 canonical text → PUBLIC v3 순서다. Gold ID, target, teacher forcing, Gold membership을 이 경로에 전달하지 않는다. `score_final_relations`와 `score_final_primary`는 같은 final cluster lease를 각각 한 번 소비한다.

## Tensor owner와 해제 지점

| Owner | 마지막 소비자 | 해제 후 보존되는 값 |
| --- | --- | --- |
| backbone `BackboneOutput` 및 shared DCE lease | 모든 source decode, Entity resolution, Event/Time direct gather | 원문 좌표와 예측 scalar |
| Statement/Assertor feature map | Assertor/Entity resolution, relation 및 Primary | Statement/Assertor의 local ID·source grounding·resolution 상태 |
| Event-Time lease | normalization check, attachment, member feature 조립 | Time occurrence의 원문/value/status/attachment |
| Event member lease | same-event 점수와 final cluster aggregation | all-member role·Time·trigger scalar fact |
| final cluster lease | relation release 다음 Primary release | final Event ID, relation logit, Primary scalar |

각 request는 한 semaphore slot을 점유한다. 정상·예외 모두 `finally`에서 남은 lease를 닫고 instrumentation hook을 제거한다. source token tensor의 Python identity가 extraction·Assertor·role·Entity resolution·Event-Time feature consumer 전부에서 같음을 검사한다. `LocalEventState`, `V3ConstructionResult`, PUBLIC, `ServingResult.audit`에는 raw tensor가 없다. `candidate_span.forward_runtime_direct_states`만 사용하고 `prepare_backbone_layers`의 article-global stack 경로는 진입하지 않는다.

## 타입, 시간 및 선택 정책

Predicted Entity 후보는 5-type head의 log probability vector를 member별 scalar evidence로 가진다. cluster는 member evidence를 type별 합산하고 고정된 taxonomy 순서로 동률을 해소한다. 혼합 member label이면 `TYPE_CONFLICT`와 member evidence를 유지하며 canonical type은 다섯 개 중 정확히 하나다. ACTOR/TARGET/ASSERTED_BY endpoint를 삭제하지 않는다. Gold 구조의 혼합 label은 cluster-level 정답을 발명하지 않고 `entity-type-annotation-audit.md`의 별도 검토 대상으로 남긴다. `GENERIC`은 충돌용 fallback이 아니다.

ACTOR/TARGET predicted role span은 같은 Entity 후보 universe에서 먼저 예약한다. PLACE는 동일 exact NER 근거가 없는 경우 SPAN_ONLY로 남긴다. Assertor는 모델 resolution이 거부하면 SPAN_ONLY로 남긴다. Time mention은 normalization 값이 없어도 존재하고 attachment scorer의 후보가 된다. source 또는 timezone anchor로 확인되는 값만 유지하며, FY/interval/unresolved는 내부 occurrence에 보존된다. PUBLIC Time materialization은 선택 Event에 실제 부착된 단일 YEAR/MONTH/DAY 값만 허용한다. zero-event에서 fake Event를 만들지 않는다.

현재 추출 상위 후보 예산과 pair logit cutoff는 **provisional engineering diagnostic**이다. `ServingBudget`가 source·participant 후보와 pair chunk를 제한하고 budget 부족을 `partial_stages`로 드러낸다. Primary 자체는 quota/Top-K를 학습하거나 적용하지 않는다. smoke score로 production threshold 또는 persistence selection을 하지 않는다. PUBLIC은 diagnostic unfiltered로 모든 현재 proposition을 투영하며 관계·Entity·Time endpoint는 12번 validator가 다시 검사한다.

## 검증과 측정 한계

`tests.test_v3_serving`은 실제 로컬 smoke checkpoint의 Gold-free end-to-end, fresh instance 출력 일치, Primary on/off의 backbone·DCE 1회, direct gather와 global-stack 금지, raw tensor 0, endpoint 연결성, no-event, SPAN_ONLY PLACE/Assertor, unresolved/FY/interval Time, 혼합 Entity type, 예외 cleanup을 확인한다. `training.scripts.v3_serving_audit`는 engineering50 train manifest에 있는 1,102자 기사 `GNEWS-78d586610b9d7bc0008f37d79e823c0c`의 **processed 원문만** 입력받아 현재 환경의 latency·process high-water RSS를 `serving-audit-report.json`에 기록했다. Gold file/label은 측정 경로에 없다. 측정은 CPU/FP32, 4 thread, warmup 후 3회씩이며 model load 시간을 제외한다. `ru_maxrss`는 process high-water이고 `tracemalloc`은 native PyTorch tensor allocation을 포괄하지 않으므로 개별 tensor peak로 해석하지 않는다.

기존 rc2의 selective capture 테스트 7개가 통과하고 현재 pinned producer는 hook 3개, 반환 layer `{8,10,12}`, 정리 후 capture context tensor 0을 확인했다. 전체 rc2 정적 package 검사는 역사적 source mapping의 `models/context.py` SHA 불일치로 중단된다. 해당 파일은 5번 v3 구현 커밋 `df647751`에서 변경됐고 14번에는 수정되지 않았다. 따라서 현재 source 전체가 frozen rc2 package와 byte-identical하다고 주장하지 않는다. rc2의 역사적 72기사 평균 3.535초·peak RSS 6.947GB와 본 단계의 단일 54자 engineering 입력은 corpus·기능·측정 범위가 달라 절대값 동등 비교를 하지 않는다.

남은 검증은 학습 완료 checkpoint 및 threshold/calibration 이후의 predicted 품질·확장 article latency·메모리다. 전체 Gold gate는 dev `136.json` 문제로 계속 `BLOCKED`다.
