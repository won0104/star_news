# v2.2 application-level CPU bottleneck profile

고정 final-run 72건의 latency/structure에서 고유 10건을 선택했다. 모델 1회 load, 비중복 기사 1건 warm-up, 선택 기사별 PUBLIC inference 1회이며 node/edge semantic parity는 10/10 PASS다. pinned cache의 선언 파일 SHA가 일치했고 네트워크 다운로드는 없었다.
직렬화·parity·aggregate는 inference timer 밖에서 수행했다. 후보별 로그, DEBUG dump, torch.profiler/cProfile은 사용하지 않았다. checkpoint/threshold/candidate/pair 정책과 PUBLIC schema는 유지했다.

선택 10건 평균 28.974s, median 7.731s, P90 32.801s. long blocker는 194.628s, 나머지 선택 9건 평균은 10.568s다. 이 9건도 구조 extrema가 포함된 의도적 sample이라 전체 평균으로 일반화할 수 없다.
기존 7.088s는 final-run 70건 measured set의 historical baseline이다. 그중 long blocker가 218.108s로 전체 44.0%를 차지했고, 나머지 69건 평균은 4.030s였다. profiler sample과 동일조건 전후 성능 비교가 아니다.

## CPU wall time 상위 stage

- `participant_entity_primary_resolution`: mean 6.967s (24.0% of selected total); blocker 51.707s; other 9 mean 1.996s.
- `event_pair_scoring`: mean 5.812s (20.1% of selected total); blocker 35.850s; other 9 mean 2.475s.
- `entity_candidate_enumeration_scoring`: mean 5.757s (19.9% of selected total); blocker 36.546s; other 9 mean 2.336s.
- `time_candidate_enumeration_scoring`: mean 4.683s (16.2% of selected total); blocker 28.443s; other 9 mean 2.043s.
- `rescue_only_resolution`: mean 2.416s (8.3% of selected total); blocker 22.641s; other 9 mean 0.169s.
- `role_entity_compact_handoff`: mean 1.505s (5.2% of selected total); blocker 9.959s; other 9 mean 0.566s.

## candidate/pair universe와 단위 비용

- `participant_entity_primary_resolution`: primary_pair_count mean 1149362, max 8847288; pooled 0.006ms/pair.
- `entity_candidate_enumeration_scoring`: enumerated_candidate_count mean 78931, max 476465; pooled 0.073ms/candidate.
- `time_candidate_enumeration_scoring`: enumerated_candidate_count mean 78436, max 470331; pooled 0.060ms/candidate.
- `event_pair_scoring`: scored_pair_count mean 613, max 4656; pooled 9.484ms/pair.
- `rescue_only_resolution`: rescue_pair_count mean 828, max 5389; pooled 2.919ms/pair.
- blocker census: Entity 후보 476,465, Time 후보 470,331, PRIMARY pair 8,847,288, Event pair 4,656, RESCUE_ONLY pair 5,389.
eligible/scored/accepted, filler role별 수, B3 evaluated/merged와 serving evidence 수는 `per-article.json` 및 `aggregate.json` census에 보존했다.

## article latency와 count의 관찰 상관 (blocker 제외 선택 9건)

- `role_entity_compact_handoff` / role_representation_filler_count: total latency Pearson r=0.981; 해당 stage time r=0.999.
- `participant_entity_primary_resolution` / primary_pair_count: total latency Pearson r=0.871; 해당 stage time r=0.996.
- `time_candidate_enumeration_scoring` / enumerated_candidate_count: total latency Pearson r=0.769; 해당 stage time r=1.000.
- `entity_candidate_enumeration_scoring` / enumerated_candidate_count: total latency Pearson r=0.769; 해당 stage time r=1.000.
- `event_pair_scoring` / scored_pair_count: total latency Pearson r=0.720; 해당 stage time r=0.230.

기사 길이/구조가 여러 count를 함께 늘린다. 9건의 Pearson r은 기술 통계이며 causal 근거나 pruning 근거가 아니다. blocker 포함 r은 단일 극단값 영향이 크다.

## 다음 최적화 후보 (아직 구현하지 않음)

1. PRIMARY Participant→Entity: blocker 8,847,288 pair / 51.707s. 동일 pair eligibility와 scoring을 유지한 채 eligibility index·feature packing·pair head batch의 비용을 다음에 분리한다.
2. Event pair scoring: blocker 4,656 pair / 35.850s, 선택 10건 pooled 9.484ms/pair. policy feature construction과 head scoring 경계를 더 측정하고 같은 pair set에서 loop/batch 비용을 줄일 여지를 확인한다.
3. Entity·Time span enumeration/scoring: blocker에서 각각 36.546s / 28.443s. span width와 후보를 그대로 둔 상태에서 iterator·packing·chunk scoring 비용을 분리한다.

## latency budget

historical 7.088s에서 3.5s까지 최소 3.588s/기사 절감이 필요하다 (4.0s: 3.088s, 3.0s: 4.088s).
70건 총량 기준으로 long blocker를 0초로 만든다는 불가능한 상한을 가정해도 3.5s 목표에는 나머지 69건에서 평균 최소 0.479s 추가 절감이 필요하다. 실제 blocker가 남으면 필요한 일반 기사 절감은 더 커진다.
선택 10건 stage share를 historical 70건 평균에 비례 적용한 가설적 3.5s 예산 배분은 다음과 같다. 이 배분은 달성값이나 동일조건 실측이 아니다.
- `participant_entity_primary_resolution`: 예시 절감 배분 1.000s/기사; 비례 적용한 현재 stage 용량 약 1.704s/기사.
- `event_pair_scoring`: 예시 절감 배분 0.900s/기사; 비례 적용한 현재 stage 용량 약 1.422s/기사.
- `entity_candidate_enumeration_scoring`: 예시 절감 배분 0.800s/기사; 비례 적용한 현재 stage 용량 약 1.408s/기사.
- `time_candidate_enumeration_scoring`: 예시 절감 배분 0.600s/기사; 비례 적용한 현재 stage 용량 약 1.146s/기사.
- `rescue_only_resolution`: 예시 절감 배분 0.288s/기사; 비례 적용한 현재 stage 용량 약 0.591s/기사.

가장 큰 단일 stage의 선택 10건 share는 24.0%이며 count universe가 확인됐다. 30% 이상이면서 application count로 원인이 불명확한 stage가 없어 낮은 수준 profiler 추가 실행은 하지 않았다. stage wall time에는 CPU synchronization과 Python bookkeeping이 섞인다.
