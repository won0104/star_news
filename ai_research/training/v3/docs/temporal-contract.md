# 7번 Time 학습·정규화·attachment 계약

5번 `time_mention`은 정규화 값과 무관하게 exact textual span을 추출한다. 7번 `TimeGoldAdapter`는 같은 단일 backbone/공유 DCE lease의 Event/Time source 표현을 소비한다. `normalized_value`가 있는 Time만 format과 **전체 문자열** 문자 CE로 감독한다. `null`은 value loss에서만 제외한다. Event×Time의 실제 Gold attachment를 양성, 다른 eligible pair를 결정적 표본 음성으로 학습한다. 같은 문장/기사 공기만으로 edge를 만들지 않는다. Statement에는 Time 필드를 추가하지 않는다.

`parse_canonical_time`은 유효한 `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, `FYyyyy`, 같은 granularity의 정렬된 interval을 원형 그대로 보존한다. 윤년과 실제 월/일 범위를 검사한다. `infer_source_time`은 명시적 ISO·한국어 연/월/일 또는 정확한 timezone을 가진 `published_at`과 원문의 `오늘`/`어제`/`지난달`만 해석한다. `최근`/`당시`, anchor·timezone 부재, 지원되지 않는 시각 표현은 `UNRESOLVED`다. article 발행일에서 무조건 Event 시간을 만들지 않는다. `SOURCE_RULE` 결과는 source/anchor에서 동일 값을 다시 만들 수 없으면 거절한다. 학습된 문자 head의 임의 출력은 runtime calendar 값으로 직접 확정하지 않는다.

`TemporalOccurrence`는 exact grounding, 원래 precision, normalization 상태와 Event attachment 상태를 따로 보관한다. 같은 source occurrence는 합치되 다른 granularity의 값을 강제 병합하지 않는다. `calendar_eligible`은 유효한 단일 YEAR/MONTH/DAY 값에만 true다. FY·interval·null은 내부에서 보존하며 calendar materialization 대상으로 속이지 않는다. 정규화된 Time도 Event에 연결되지 않으면 `public_calendar_candidate=false`다. 실제 선택 Event와의 PUBLIC 연결성·Neo4j YEAR/MONTH/DAY 변환은 12번 adapter 책임이다. 8번의 final Event ID가 정해지면 `remap_time_attachments`가 모든 member의 Time 근거를 cluster endpoint로 합친다.

기존 rc2에서는 `temporal_consolidation.py`가 accepted source family에서 V1 normalization을 형식 선호에만 사용하고 미정규화 family도 유지한다. `compact_assembly.py`는 V1 미정규화 occurrence에만 V2를 적용하며 기존 V1 값을 덮지 않고 pending attachment를 remap한다. 새 v3 경로는 그 우선순위/미정규화 보호 원칙을 지키되 기존 서비스 serializer를 이번 단계에서 수정하지 않는다.

예측 attachment는 `EventTimeFeatureLease` 안에서만 점수화하며 임시 `score_threshold=0.0`, 4,096 pair cap에 걸리면 `partial`을 반환한다. 이 값은 서비스 threshold가 아니다. lease는 마지막 tensor consumer 뒤 닫고 scalar `TemporalOccurrence`에는 tensor를 넣지 않는다. 실제 pretrained checkpoint load나 서비스 quality/latency 측정은 수행하지 않았다.

`time-coverage-report.json`의 기존 train 400기사 정적 수치: Time span 3,257, normalized 1,733, unresolved 1,524, Event-Time 양성 2,302(이 중 null value 900), 유효 음성 universe 43,256, 정규화됐으나 미연결 Time 716. 이는 Gold 구조 계수이며 예측 정확도나 threshold 근거가 아니다. dev/test Gold는 사용하지 않았고 단계 2의 dev Gold blocker가 남아 있다.
