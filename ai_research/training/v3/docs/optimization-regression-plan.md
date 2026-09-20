# 14번 rc2 최적화 회귀 검사와 결과

## 검사 범위

1. pinned backbone의 layer capture hook 3개, `output_hidden_states=False`, `ContextVar` cleanup, all-valid window view를 확인한다. 실제 serving 호출마다 backbone/DCE 횟수를 hook으로 센다.
2. `ExactSourceSpanBridge`가 `CandidateSpanEncoder.forward_runtime_direct_states`에 도달함을 동적 spy로 확인한다. `prepare_backbone_layers`의 article-global layer stack은 테스트에서 예외를 발생시키도록 막는다.
3. Primary on/off 동일 raw article에 대해 backbone forward, shared DCE, captured layer set, source representation identity, final Event identity를 비교한다. relation adapter 자체의 연산은 별도로 기록한다.
4. extraction·Entity·Event-Time·Event coreference·ABOUT·CAUSES의 eligible/scored pair를 기록하고, cap 도달 시 partial을 표시한다. 이는 **predicted engineering coverage**이며 Gold representability 또는 recall 지표가 아니다.
5. 대표 input의 warmup 후 latency·process high-water RSS와 owner storage alias census를 기록한다. CPU/FP32만 실제 실행했다. GPU 수치는 미검사다.

## 관측 결과

실제 stage 13 smoke checkpoint와 engineering50 **train raw source** 1,102자 한 건을 사용했다. Gold label/target은 읽지 않았다. 요청마다 backbone 1, DCE 1, selective L8/L10/L12, capture hook 3, capture context tensor 0이었다. Primary on/off에서 추가 backbone/DCE/recapture는 각 0이고 final EventCluster 3개의 identity가 같았다. `tests.test_bcr_step9_5_capture`와 v2 Gold-free pipeline 7개가 통과했다. Stage14 test는 direct gather call 양수와 global layer stack call 0을 확인했다.

같은 입력의 engineering budget에서 Entity 후보 13개(누락 NER/role 0), Entity coref 78 pair, role resolution 7 pair, Event-Time 12/12, Event coref 3/3, ABOUT 9/9, CAUSES 6/6이었다. source proposal은 EVENT 32/82, STATEMENT 32/36, TRIGGER 32/109, ENTITY 22/22, TIME 22/22를 점수화했다. Participant는 72/212였다. budget 때문에 일부 추출 candidate universe는 partial이며 이 수치를 모델 recall로 표현하지 않는다. full-ALL fallback·무제한 Cartesian score tensor는 없다.

CPU/FP32 4 thread, warmup 후 3회 중앙값은 Primary on 약 1.8초, off 약 1.8초다. stage median에서 backbone/shared 약 1.1초, source extraction 약 0.7초가 주 비용이다. Entity·Time·Event identity·relation·Primary는 각각 밀리초 수준이었다. 따라서 v3 추가 semantic/head 계산 비용은 확인되지만 구조적인 backbone/DCE 중복은 관측되지 않았다. `ru_maxrss`는 약 1.36GB, model-load 뒤 baseline high-water 대비 약 34MB 증가했다. Python tracing은 native PyTorch storage를 포함하지 않는다. 정확한 재실행 수치는 `serving-audit-report.json`을 따른다.

과거 rc2의 72기사 평균 3.535초·peak RSS 6.947GB는 다른 corpus와 기능의 **historical reference**다. 현재 입력과 절대 latency/RSS 동등 비교는 불가능하다. 전체 rc2 정적 package 스크립트는 5번 v3 작업으로 바뀐 `models/context.py`의 historical source SHA mapping에서 멈췄다. 이 파일의 14번 working-tree diff는 없고, 회귀에 직접 관련된 selective capture/direct gather는 위 정적 소스 확인과 동적 spy로 검증했다. 단계 15의 engineering50 시간·메모리 smoke, tiny-fit, 성능 판단은 시작하지 않았다.
