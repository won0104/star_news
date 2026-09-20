# Span Architecture Decision v0.4

## 결정

범용 learned-label-conditioned span scorer는 채택하지 않는다.

| task | layer | 현 기준선 | label-conditioned 판정 |
|---|---:|---|---|
| Entity | L12 | BIO | micro gate 통과, 승격 보류 |
| Time | L10 | BIO | 실패 |
| Semantic Span | L8 | independent start/end | 실패 |
| Trigger | L8 | independent start/end | 실패 |

네 task 중 Entity만 사전 micro-F1 gate를 통과했으므로 general family gate는 실패했다.
Time·Semantic·Trigger는 기존 구조를 유지한다.

## Entity 보류 이유

Entity test exact micro-F1은 `0.2087 → 0.2783`으로 올랐지만 macro-F1은
`0.2491 → 0.2379`로 낮아졌다. 새 scorer는 recall `0.9910`이지만 precision이
`0.1619`다. PERSON은 개선됐지만 ORGANIZATION과 LOCATION F1은 하락했다.

또한 이 probe가 사용한 Construction Gold v2.0은 deterministic rule generator로
생성됐고 독립 사람 NER 품질 상한이 아니다. 실제 출력에서 일반 NER상 타당한 후보가
미주석 false positive가 되는 사례와 scorer의 실제 오탐·중첩 후보가 함께 확인됐다.

따라서 Entity scorer는 다음 조건을 확인한 뒤에만 승격한다.

1. 독립 검수한 exhaustive Entity slice
2. flat-span/non-overlap decoder
3. per-label threshold와 calibration
4. micro와 macro/per-label exact F1 동시 확인

상세 수치와 실제 문자열은 [DirectionTest 보고서](../../DirectionTest/Report-KF-Label-Conditioned-Span-Scorer-v1.md)에 있다.

## 다음 probe의 격리 원칙

Directed Pair와 Coreference probe는 예측 mention이 아니라 Gold mention을 입력으로 쓴다.
이렇게 해야 span decoder 오류가 pair/coreference 구조 선택에 섞이지 않는다.

