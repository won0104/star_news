# 단계 2 Gold coverage matrix

현재 Gold는 1K 전체 완성이 아니며 이 표의 support는 기존 train에 존재하는 Gold에서만 계산했다. 기존 split의 최종 유지 여부는 보류한다.

| 사례 | 현재 train Gold support | engineering50 | fit40 | canary10 | 상태 |
|---|---:|---:|---:|---:|---|
| generic | 367 | 49 | 39 | 10 | COVERED |
| actor_generic | 135 | 33 | 27 | 6 | COVERED |
| target_generic | 338 | 49 | 39 | 10 | COVERED |
| place_span_only | 28 | 28 | 27 | 1 | COVERED |
| assertor | 365 | 48 | 39 | 9 | COVERED |
| assertor_span_only | 107 | 22 | 19 | 3 | COVERED |
| remote_assertor | 230 | 35 | 30 | 5 | COVERED |
| time_normalized | 349 | 48 | 39 | 9 | COVERED |
| time_unresolved | 341 | 46 | 37 | 9 | COVERED |
| time_month | 132 | 26 | 18 | 8 | COVERED |
| time_year | 172 | 31 | 24 | 7 | COVERED |
| time_fy | 2 | 2 | 2 | 0 | COVERED |
| time_interval | 86 | 26 | 18 | 8 | COVERED |
| event_cluster_singleton | 397 | 50 | 40 | 10 | COVERED |
| event_cluster_multi | 224 | 34 | 28 | 6 | COVERED |
| rank_top_tie | 384 | 48 | 38 | 10 | COVERED |
| rank_middle_tie | 399 | 50 | 40 | 10 | COVERED |
| rank_cross_kind | 397 | 49 | 39 | 10 | COVERED |
| nested_entity_span | 260 | 37 | 29 | 8 | COVERED |
| about_positive | 325 | 45 | 36 | 9 | COVERED |
| about_negative | 396 | 49 | 39 | 10 | COVERED |
| causes_positive | 212 | 42 | 33 | 9 | COVERED |
| causes_negative | 385 | 50 | 40 | 10 | COVERED |
| length_short | 134 | 10 | 8 | 2 | COVERED |
| length_middle | 133 | 16 | 13 | 3 | COVERED |
| length_long | 133 | 24 | 19 | 5 | COVERED |

## 범위와 잔여 공백

- 현재 검증 통과 train Gold: 400기사. fit/canary는 모두 기존 train 소속이며 test/dev 선택은 0기사.
- ABOUT 음성은 Statement×EventCluster의 미기록 eligible pair, CAUSES 음성은 서로 다른 EventCluster 방향쌍의 미기록 pair 존재 여부다. 의미적 relation completeness 검증은 별도 검토가 필요하다.
- `actor_generic`/`target_generic`은 같은 Entity cluster에 속한 GENERIC EntityMention과 role의 exact span 일치로 확인했다. 기존 NER와 비교하는 진정한 role-only 여부는 현재 Gold provenance만으로 확정할 수 없다.
- remote_assertor는 Assertor span과 Statement span 사이가 80 Unicode code point 이상인 탐색용 기준이다. 이 숫자는 학습 threshold가 아니다.
- 길이 그룹은 현재 유효 train Gold 본문 길이의 1/3, 2/3 분위수로 정의했다.
- 표상 사례 미충족: 없음. 실제 support 0인 사례는 합성 unit fixture로 기계 계약을 먼저 보완한다. 의미 성능 평가는 합성 fixture로 대체하지 않는다.
- 실제 추가 기사 최소 건수는 현재 표상 사례 기준 0건이다. 전체 Gold coverage와 최종 split/분포 판단은 Gold가 충분히 완성된 뒤 별도 수행한다.
