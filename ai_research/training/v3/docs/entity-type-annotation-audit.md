# 혼합 타입 Gold cluster annotation audit

6번의 기존 train Gold oracle census(`entity-union-coverage-report.json`)에는 `PRODUCT`와 `ORGANIZATION` mention이 같은 Gold EntityCluster에 속하는 사례가 있으며 해당 cluster를 가리키는 ACTOR/TARGET endpoint 3개가 보존됐다. 이 수치는 현재 검증된 train 400기사의 기존 보고에서 가져왔고, 14번 serving 검증에 Gold label을 주입하지 않았다.

현재 r05.3에는 EntityCluster 수준 canonical type 정답이 없다. 따라서 혼합 Gold cluster에 임의 type label을 추가하거나 `GENERIC`으로 치환하지 않는다. 후속 annotation audit에서 mention별 source/type 근거와 cluster membership을 검토해 label 오류인지 실제 다중 의미인지 결정해야 한다. 그 결정 전에는 Gold oracle 구조의 `TYPE_CONFLICT` 진단과 endpoint를 유지한다.

Predicted serving은 별도 정책을 쓴다. 5-type head가 각 member 후보에 낸 log probability를 cluster 단위로 합산하여 canonical type 하나를 결정하고, `TYPE_CONFLICT`와 member evidence를 함께 반환한다. 이는 학습 정답을 새로 만드는 절차가 아니라 서비스 표시용 deterministic aggregation이다. backend의 세분 EntityType 매핑과 Gold audit의 결론은 이 단계에서 정하지 않는다.
