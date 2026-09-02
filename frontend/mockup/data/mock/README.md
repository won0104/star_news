# 별빛 뉴스 통합 목업 데이터

`scripts/build_mock_dataset.py`가 GNews 평가 원본에서 재현 가능하게 생성하는 데이터입니다.

## 데이터 경계

- `provider=gnews`, `synthetic=false`: 수집한 실제 기사입니다. 원문 링크와 출처를 보존합니다.
- `data_role=current_supplement`, `synthetic=true`: 카테고리별 시연량을 채우는 합성 기사입니다. 외부 링크가 없습니다.
- `data_role=personal_history`, `synthetic=true`: 3개월 개인 기록과 리포트를 위한 합성 기사입니다.
- 노드·엣지·사용자 이벤트·리포트는 목업 동작을 위한 파생 또는 합성 데이터입니다.
- `views.home.trend_statistics_provenance.kind=deterministic_mock`: 기간별 기사 수와
  직전 기간 증감률은 현재 수집량에서 재현 가능하게 산출한 합성 화면 통계입니다.

기사 분류는 `primary_category_id`에 화면 배치용 대표 분야를, `category_ids`에
검색·그래프·필터용 복수 분야를 저장합니다. GNews의 `general`, `world` 같은
수집 category는 분류 입력으로 사용하지 않고 provenance에만 보존합니다.

## 주요 파일

- `mock_dataset.json`: 프런트엔드에서 한 번에 읽을 수 있는 통합본
- `articles.json`: 실제 기사, 현재 보강 기사, 개인 기록 기사
- `nodes.json`, `edges.json`: 전체 및 개인 그래프 공용 데이터
- `navigation.json`: 어떤 노드를 눌러도 이웃과 관련 기사를 열 수 있는 탐색 인덱스
- `views.json`: 홈, 카테고리, 검색 화면의 seed 데이터와 좌표
- `user_events.json`, `user_report.json`: 숙련 사용자 시연 기록과 최근 3개월 리포트
- `coverage_report.json`: 분류 결과와 카테고리 부족분 산출 근거
- `review_queue.json`: 분류 확신이 낮아 사람이 확인할 실제 기사

## 기간별 홈 트렌드 계약

`views.home.trend_period_order`가 UI 버튼 순서를, `trend_periods`가 기간별 화면
데이터를 제공합니다. 기존 `today_trends`는 다음 UI 전환 전까지 유지하는 하위
호환 필드이며 `trend_periods.today.seed_nodes`에서 파생됩니다.

```json
{
  "trend_period_order": ["today", "week", "month", "quarter"],
  "trend_periods": {
    "week": {
      "id": "week",
      "label": "1주",
      "title": "이번 주 주요 흐름",
      "window_days": 7,
      "window_label": "최근 1주",
      "comparison_label": "직전 1주 대비",
      "starts_at": "ISO-8601",
      "ends_at": "ISO-8601",
      "comparison_starts_at": "ISO-8601",
      "comparison_ends_at": "ISO-8601",
      "updated_at": "ISO-8601",
      "seed_nodes": [
        {
          "node_id": "entity:russia",
          "x": 0.13,
          "y": 0.18,
          "article_count": 86,
          "previous_article_count": 64,
          "change_rate": 34
        }
      ],
      "rising_node_ids": ["entity:russia", "entity:united-states", "topic:crypto"]
    }
  }
}
```

- 각 기간은 고유한 seed 8개와 그중 급상승 3개를 가집니다.
- `rising_node_ids`는 반드시 같은 기간의 `seed_nodes`에 포함됩니다.
- `change_rate`는 `(article_count - previous_article_count) / previous_article_count`
  를 반올림한 정수입니다.
- 화면은 `node_id`로 `nodes`의 라벨·종류를 결합하고, Figma에 적힌 예시 수치를
  런타임 값으로 사용하지 않습니다.
- 원본 기사 기간이 직전 3개월 비교를 지원하지 않으므로 이 통계는 기사 원문 건수
  계약이 아니라 V2 기간 필터를 검증하기 위한 합성 view 데이터입니다.

## 다시 생성하기

```bash
python3 scripts/build_mock_dataset.py
```

분류는 목업 단계의 임시 규칙입니다. 실제 서비스의 BERT/NER/분류 모델 결과를 뜻하지 않습니다.
