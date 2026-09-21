# 14번 serving source extraction 중복 계산 제거

15번 전의 요청 범위 최적화다. 14번 변경 전 수치는 기존 `serving-audit-report.json`에 그대로 보존했고, 같은 audit 프로그램의 변경 후 출력은 `source-extraction-postopt-audit.json`에 별도로 저장했다. 입력은 engineering50 train에 속한 `GNEWS-78d586610b9d7bc0008f37d79e823c0c`의 **processed 원문 1,102자만** 사용했다. source SHA-256은 `530b73c3641819ded0d6106b9e96642ff7c5ae296f297810b3867abebe80a8cd`, checkpoint SHA-256은 `fbf6e8e8779b184fd08c690317592bf41e3d3104816c5761fc319402f8bb4a8f`다. Gold label은 읽지 않았고 smoke checkpoint의 production 상태는 바꾸지 않았다.

## 변경 범위

- 한 request의 generic endpoint logit을 한 번 계산해 EVENT/STATEMENT/ENTITY/TIME/TRIGGER가 공유한다. 마지막 generic consumer 뒤 tensor 참조를 해제한다. PARTICIPANT는 role 전용 boundary 출력만 읽으며 generic endpoint를 계산하거나 dense generic tensor로 확장하지 않는다.
- bridge source index의 window row/local token position을 한 번 계산해 source kind와 role decode가 공유한다. 한 Event의 exact-span representation은 세 role에서 공유하고 해당 Event가 끝나면 해제한다. Assertor bridge token state도 request에서 한 번 gather해 모든 Statement에 전달하고 마지막 Assertor 뒤 해제한다.
- 새 `SourceDecodeContext`는 request 내부에서만 쓰고 role decode 뒤 닫는다. semantic/PUBLIC 결과에는 tensor나 lookup이 들어가지 않는다. 후보·score·예산·threshold·span decode 정책은 그대로다.

## 동일 입력 회귀

`training.scripts.v3_source_extraction_parity`로 변경 전 `52917404` 코드의 스냅샷을 먼저 생성하고 변경 후 같은 checkpoint·raw input으로 비교했다. EVENT/STATEMENT/TRIGGER/ENTITY/TIME/PARTICIPANT의 **14개 decode 결과 전체**(kind, label, 문자 start/end, text, score, pair 수), Assertor, Entity candidate/closure와 Event identity, ABOUT/CAUSES, Primary, PUBLIC 및 안정적인 audit scalar가 정확히 같았다. semantic JSON의 전후 SHA-256도 모두 `0491a49b21ec0e061d203a252a65d16756cb7b9b03b3de6595ed2e66e3e6acfb`다. 숫자 비교의 허용 오차는 상대 `1e-6`, 절대 `1e-5`였지만 실제 JSON 값은 exact equality였다. 예산별 source/participant 및 나머지 pair 집계도 기존 audit와 같다.

| 계측 | 변경 전 | 변경 후 |
| --- | ---: | ---: |
| generic endpoint forward | 14 | 1 |
| Assertor bridge gather | 3 | 1 |
| Event single-span feature | 9 (기존 각 role 호출 경로) | 3 (Event별 1회) |
| candidate direct gather 호출 | 29 | 29 |
| backbone / DCE | 1 / 1 | 1 / 1 |

전후 모두 selective L8/L10/L12 hook 3개, global layer stack 0, PUBLIC dangling endpoint 0, PUBLIC/audit raw tensor 0이다. 변경 후 `SourceDecodeContext`의 endpoint와 lookup은 종료 때 비워지고 weakref로 endpoint tensor 회수를 확인했다. 기존 3회 반복 request의 feature weakref 및 예외/cancellation lease 정리 테스트도 통과했다.

`conda run -n model-test-py312 python -m unittest tests.test_v3_serving tests.test_v3_harness tests.test_v3_public_graph tests.test_v3_extraction tests.test_v3_entity_union tests.test_v3_time tests.test_v3_event_identity tests.test_v3_attribution tests.test_v3_primary tests.test_v3_architecture tests.test_v3_target_compiler tests.test_v3_canonical_text tests.test_bcr_step9_5_capture tests.test_goldfree_article_kg_pipeline -q`에서 87개 테스트가 통과했다. 새 source context는 정상 종료와 source extraction 예외 모두에서 닫히며 generic endpoint, Assertor bridge state, Event feature의 weakref가 request 뒤 소멸한다.

## 동일 1,102자 입력 latency

CPU/FP32, PyTorch 4 threads, 모델 load 제외, warmup 뒤 Primary-on 3회와 off 3회를 측정했다. 이 값은 소수 반복의 engineering 측정이며 성능 분포나 서비스 SLA가 아니다.

| Primary-on 중앙값 | 변경 전 | 변경 후 | 차이 |
| --- | ---: | ---: | ---: |
| source extraction | 712.492 ms | 644.359 ms | -68.133 ms (-9.56%) |
| 전체 요청 | 1,820.098 ms | 1,765.363 ms | -54.735 ms (-3.01%) |

변경 후 전체 Primary-on 개별 값은 1,762.302/1,765.363/1,786.455 ms다. 변경 전/후 process high-water RSS는 각각 1,360,543,744/1,371,652,096 byte였으며 이 값은 native PyTorch tensor peak나 tensor leak의 직접 측정치가 아니다. 별도 request tensor/lease 회귀 테스트로 누수를 확인했다. 체크포인트 선택, 학습, threshold/calibration 및 15번 단계는 수행하지 않았다.
