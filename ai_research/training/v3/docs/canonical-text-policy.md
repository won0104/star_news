# 11번 원문 근거 canonical text 정책

`runtime/v3_pretraining/canonical_text.py`는 학습하지 않는 순수 결정적 표시문 규칙이다. 입력은 검증된 `RawArticle`, final `LocalEventState` 또는 `GroundedStatement`이며 출력은 `text`, `status`, `rule_version`, `used_grounding_ids`, `audit`이다. 출력은 반드시 원문의 연속 부분문자열이다. 입력 evidence의 `[start,end)`와 `text`는 수정하지 않는다. canonical text equality는 Event/Entity 동일성 병합의 근거가 아니다.

## 우선순위와 경계

1. 단독으로 읽히는 완결 원문 span은 그대로 표시한다(`SOURCE_COMPLETE`). Event의 짧은 trigger-only 표기는 단독으로 충분하지 않으면 다음 규칙을 시도한다.
2. 동일한 원문 clause 안에서만 span을 확대한다(`SOURCE_CLAUSE_EXPANDED`). 인용 내부 구두점과 숫자의 소수점을 clause 경계로 보지 않는다. 쉼표·세미콜론·문장 말미는 경계다. 확대 길이는 최대 160 Unicode 문자다.
3. Event는 대표 member의 trigger 및 그 member와 연관된 role 근거가 같은 clause에 있어야 확대한다. 다른 EventCluster member의 ACTOR/TARGET/PLACE/Time을 조합하지 않는다. 충돌 cluster, 원격 role, forecast/추정 문맥, 복수 clause 접속, 미완결 clause는 확대하지 않는다.
4. Statement는 `FORECAST/CLAIM/EVALUATION` type을 유지하고 원문의 가능성·조건·부정·인용·발화자 표현을 삭제하거나 factual Event 서술로 바꾸지 않는다. Assertor가 같은 clause에 실제로 있으면 사용한 근거 ID를 기록하되, 다른 clause의 발화자를 text에 만들어 넣지 않는다.
5. 확대가 안전하지 않으면 원문 대표 span을 `FALLBACK_SOURCE_SPAN` 또는 `INSUFFICIENT_CONTEXT`로 반환한다. 이 상태는 성공적인 독립 문장 생성이라는 뜻이 아니다. 빈 source/오프셋 오류는 각각 진단 상태/예외다.

안전한 어미 변경이나 여러 span의 frame 합성은 이번 규칙에 넣지 않았다. 원문에 없는 주체, 숫자, 날짜, modality를 추가할 위험을 줄이기 위한 구현 선택이다. embedding과 외부 표시 스타일은 backend 책임이다. canonicalization은 PUBLIC 선택 이후 선택된 proposition에만 적용할 수 있으며, 선택 정책을 바꾸려면 보존된 construction graph에서 다시 projection한다.

## 검증

synthetic fixture는 완결 span, trigger-only, 관형형, 복수 절, 부정, 수치/소수점, 연도, forecast, 조건, nested quote, 원격 role, 역할 누락, 충돌 cluster, 원문 말미, 반복 호출을 확인한다. 검증된 기존 train Gold 400기사의 정적 census에서는 EventCluster 3,908개와 Statement 6,164개 모두 canonical text가 원문 부분문자열이고 evidence offset이 그대로였다. Event는 `SOURCE_COMPLETE` 1,461, `SOURCE_CLAUSE_EXPANDED` 957, fallback/context 부족 1,490개였다. Statement는 각각 4,315, 1,085, 764개였다. 이 수치는 extractive 규칙 통과 수이며 서비스 가독성이나 의미 품질 점수가 아니다. 전체 Gold intake의 dev `136.json` blocker는 유지된다.
