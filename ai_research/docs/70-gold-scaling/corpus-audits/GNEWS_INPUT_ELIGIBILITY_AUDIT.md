# GNews 장문 및 ArticleLocal KG 입력 적격성 2차 감사

이 문서는 [1차 Corpus Audit](ARTICLE_CORPUS_AUDIT.md)과 [후보 패턴](candidate_patterns.json)을 바탕으로 **GNews raw row 5,316건만** 다시 스캔한 결과다. 재실행 도구는 `python3 scripts/audit_gnews_input_eligibility.py`, 집계·식별자·제한된 발췌는 [근거 JSON](gnews_input_eligibility_evidence.json)에 있다. Raw 본문, production preprocessing, 모델 및 Gold는 변경하지 않았다. 아래 구조 tag와 적격성 평가는 탐색 결과이지 정제·제외·truncation의 최종 정책이 아니다.

## 1. Executive Summary

- `gnews_legacy` 1,329건, `gnews_fullversion` 3,987건을 스캔했다. 10,000자 초과는 fullversion의 11개 record(전체 0.21%, 동일 content hash를 가진 KBS 2건을 합치면 10개 본문)다.
- 장문 11건 중 **한 주제를 유지하는 정상 장문 6건**, **KBS의 거의 같은 본문 반복과 UI가 있는 2건**, **여러 독립 콘텐츠가 합쳐진 3건**을 관찰했다. 정상 장문 6건 모두 후반 25%에 새로운 사실·지역·날짜·논의가 있다. 따라서 앞부분만 쓰는 일률적 제한은 실제 정보 손실을 일으킬 수 있다.
- legacy 1,329건 모두 본문 끝에 GNews의 `... [N chars]` 잔여 길이 표식이 있다. 확실히 대응된 legacy/full 45쌍은 **표식을 비교에서만 제외하면** legacy 본문이 full 본문의 문자 단위 정확한 prefix였다. 그 substantive prefix 길이는 full의 중앙값 **16.3%**(범위 3.1~41.1%)였고, 20/45쌍(44.4%)은 문장 중간 종료 후보였다. 대응 없는 legacy 1,165개 URL entity의 원문 관계는 확인되지 않았다.
- 동일 URL의 legacy↔full group 45개에서 제목·source·URL·발행시각·description이 모두 같았다. 별도 KG 입력으로 둘을 모두 처리하면, 적어도 동일 기사 도입부의 사실을 중복 구성할 위험이 높다. 단, 독립적인 모델 실행·추출 결과를 비교한 것은 아니다.

## 2. Long Article Audit

### 2.1 11 Articles Overview

아래 `record`는 `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/` 뒤에 붙는 파일 경로와 `#articles[index]`다. 이 둘을 합친 문자열이 고유 **article record identifier**이며, KBS의 L01/L02는 raw article ID와 content hash가 동일해도 서로 다른 category 파일의 별도 record다. 문장 수는 감사 스크립트가 문장부호 뒤 공백 또는 개행에서 나눈 **근사치**다. 실제 모델 sentence splitter의 수나 offset과 동일하다고 가정하지 않는다.

| ID / record | Source / domain | Title | Category / publishedAt | 문자 / 빈 줄 제외 줄 / 근사 문장 | Type |
| --- | --- | --- | --- | ---: | --- |
| L01 `2026-05/08/business.json#articles[1]` | KBS 뉴스 / news.kbs.co.kr | `KBS 뉴스` | business / 2026-05-08T23:23:00Z | 10,119 / 111 / 291 | fullversion |
| L02 `2026-05/08/technology.json#articles[2]` | KBS 뉴스 / news.kbs.co.kr | `KBS 뉴스` | technology / 2026-05-08T23:23:00Z | 10,119 / 111 / 291 | fullversion |
| L03 `2026-03/17/science.json#articles[0]` | 한겨레 / www.hani.co.kr | `“버블 없는 혁신은 없어…AI 버블, 도약 기회로 삼아야”` | science / 2026-03-17T22:14:00Z | 10,177 / 49 / 166 | fullversion |
| L04 `2026-02/26/entertainment.json#articles[2]` | sidae.com / www.sidae.com | `"같이 성매매한 멤버 풀겠다"…유키스 동호 전처, 카톡 공개 '충격'` | entertainment / 2026-02-26T23:24:28Z | 10,324 / 8 / 152 | fullversion |
| L05 `2026-07/02/technology.json#articles[3]` | 슬로우뉴스 / slownews.kr | `“선물 아니다…": 슬로우레터 7월3일` | technology / 2026-07-02T22:35:08Z | 10,826 / 163 / 266 | fullversion |
| L06 `2026-01/20/health.json#articles[3]` | 현대건강신문 / www.hnews.kr | `“소리 없이 자라는 췌장암, 몸 이미 신호 보내”` | health / 2026-01-20T23:07:00Z | 12,190 / 10 / 163 | fullversion |
| L07 `2025-10/22/world.json#articles[1]` | 이코노미톡뉴스 / www.economytalk.kr | `24호 태풍 펑선 정보 등 지역별 오늘의 날씨 및 주말 날씨…` | world / 2025-10-22T23:29:53Z | 14,674 / 275 / 286 | fullversion |
| L08 `2025-10/21/world.json#articles[0]` | 이코노미톡뉴스 / www.economytalk.kr | `24호 태풍 펑선 정보 등 지역별 오늘의 날씨 및 주간 날씨…` | world / 2025-10-21T23:24:38Z | 17,077 / 319 / 333 | fullversion |
| L09 `2025-11/02/world.json#articles[3]` | 이코노미톡뉴스 / www.economytalk.kr | `[25호 태풍 갈매기 등 지역별 오늘의 날씨 및 이번주 날씨]…` | world / 2025-11-02T23:17:33Z | 17,148 / 309 / 330 | fullversion |
| L10 `2026-08/11/health.json#articles[3]` | 베이비뉴스 / www.ibabynews.com | `오디세우스가 먹은 로터스... 망각의 열매였을까 평온의 열매였을까` | health / 2026-08-11T23:25:00Z | 19,584 / 131 / 156 | fullversion |
| L11 `2025-11/26/world.json#articles[2]` | 이코노미톡뉴스 / www.economytalk.kr | `27호 태풍 고토 경로 등 지역별 오늘의 날씨 및 주말날씨…` | world / 2025-11-26T22:40:20Z | 27,993 / 439 / 462 | fullversion |

L05의 완전한 raw title과 모든 raw article ID는 근거 JSON의 `longArticles`에 보존했다. 표의 말줄임표는 보고서 표시용이며 원본 title을 변경한 것이 아니다.

### 2.2 Per-Article Structural Findings

구간 비율은 실제 본문을 읽고 제목, 주제 전환, 반복 및 footer를 구별하기 위한 **근사 범위**다. 문자열의 최종 body boundary나 Gold span은 확정하지 않았다.

| ID | 관찰된 구간 | 구조 tag와 판단 근거 | 마지막까지 같은 주제? / 후반 25% 새 정보? / 후반 25% 대부분 boilerplate? | 반복 가능한 end anchor / source pattern |
| --- | --- | --- | --- | --- |
| L01 | 0~50% AI 전력·중국·한국을 다룬 KBS 보도; 50~51% `■ 제보하기` UI; 51~99% **거의 같은 기사 본문과 제목·시각 재출현**; 99~100% 기자·반응 UI | `ARTICLE_PLUS_BOILERPLATE`, `MULTIPLE_CONTENT_BLOCKS`(새 기사가 아닌 **같은 본문 반복 후보**). 두 body 구간의 문자 alignment는 약 **97.4%**이고 영상 링크·사진 표기·기자 링크 등이 다르다. Raw title `KBS 뉴스`는 본문 실제 headline을 대표하지 못한다. | 예 / **새로운 고유 사실은 확인되지 않음**, 앞 구간 내용 재등장 / 아니오 | `■ 제보하기`는 1차 audit에서 KBS 계열 148건에 관측. 하지만 이 record에서는 anchor 뒤에도 본문이 재등장하므로 단순 뒤쪽 삭제 기준으로 확정할 수 없다. |
| L02 | L01과 전 구간 동일; business와 technology 파일에 각각 저장 | L01과 동일 hash·raw article ID·내용의 record 중복 | L01과 동일 | L01과 동일 |
| L03 | 0~약 75% 국가 AI 전략·투자·산업에 관한 인터뷰; 75~100% 저작권, 군사용 AI, 안전성, 경쟁과 AI 버블에 대한 추가 답변 | `GENUINE_LONG_ARTICLE`; 한 인터뷰의 연속 답변이다. | 예 / 예, 새 입장·발언 / 아니오 | 후반의 대량 UI나 corpus에서 검증된 body-end anchor 없음. |
| L04 | 0~14% 정치 논평; 14~30% 우유산업 칼럼; 30~72% 러시아·우크라이나 전쟁 논평; 72~100% 방송 논란을 다룬 연예 기사 | `MULTIPLE_CONTENT_BLOCKS`; raw title의 유키스 관련 본문은 관찰된 구간에서 찾지 못했고, 후반도 별도 연예 기사다. 비기사 UI가 지배적인 사례는 아니다. | 아니오 / 예, **다른 기사**의 새 사실 / 아니오 | 콘텐츠 경계는 제목 전환으로 보이지만 해당 source가 1건뿐이라 source 규칙은 미검증. |
| L05 | 0~약 90% 정치·원전·AI·경제·스포츠 등 여러 뉴스 항목의 슬로우레터; 약 90~100% 추가 항목과 구독·정정·의견 안내 | `MULTIPLE_CONTENT_BLOCKS`(의도된 다주제 뉴스레터), 소규모 `ARTICLE_PLUS_BOILERPLATE`. 하나의 일반 사건 기사와 다르다. | 아니오 / 예, 새 항목·배경 / 아니오 | `슬로우레터는 뉴스를 더 열심히…` footer는 1차 후보에서 슬로우뉴스 **4/4건**의 suffix에 관측됐으나 작은 표본이다. |
| L06 | 0~12% 치약 소재; 12~40% 흡연·전자담배; 40~63% TAVI 보험; 63~86% 수면 치료 서비스; 86~100% 공중보건의 부족 | `MULTIPLE_CONTENT_BLOCKS`; raw 췌장암 title과 다르게 **다섯 건강 기사**가 이어진다. UI가 아니라 다른 기사 내용이다. | 아니오 / 예, **다른 기사**의 새 사실 / 아니오 | 제목 전환은 관찰됐지만 6건의 해당 source corpus에서 이 묶음의 보편성·end anchor는 검증하지 못했다. |
| L07 | 0~약 18% 전국 날씨·특보; 18~95% 지역별 예보; 95~100% 중기·주말 예보 | `GENUINE_LONG_ARTICLE`(하나의 날씨 bulletin 안에 지역별 구간). | 예, 같은 날짜의 기상 주제 / 예, 새 지역·예보 시각 / 아니오 | 지역 소제목은 내부 구조이며 검증된 body-end anchor 없음. |
| L08 | 0~약 16% 전국 날씨·특보; 16~96% 지역별 예보; 96~100% 주간 예보 | `GENUINE_LONG_ARTICLE`; L07과 비슷한 지역별 구간이다. | 예 / 예, 새 지역·날짜 / 아니오 | L07과 같은 source의 지역 예보 구조 후보; footer boundary는 미검증. |
| L09 | 0~약 18% 전국 날씨·한파 특보; 18~97% 지역별 예보; 97~100% 이번 주 예보 | `GENUINE_LONG_ARTICLE`; 후반부도 지역·시간별 기상 정보다. | 예 / 예, 새 지역·날짜 / 아니오 | L07/L08과 같은 source 구조 후보; 마지막 지역을 일률적으로 잘라낼 근거 없음. |
| L10 | 0~약 75% 로터스 신화, 스트레스·식물 성분과 연구 근거; 75~약 99% ADHD·불면·강박 관련 임상 논의, 한계와 연구 전망; 마지막 약 1% 필자 소개·저작권 | `GENUINE_LONG_ARTICLE`, 작은 `ARTICLE_PLUS_BOILERPLATE`. 하나의 칼럼으로 전개된다. | 예 / 예, 새 임상 논의·한계 / 아니오 | 필자 소개·copyright는 관찰되지만 베이비뉴스가 corpus에 1건뿐이라 반복 anchor라 판정할 수 없다. |
| L11 | 0~약 14% 전국 예보·특보; 14~98% 지역별 상세 예보; 98~100% 주말·12월 전망 | `GENUINE_LONG_ARTICLE`; 가장 긴 지역별 기상 bulletin이다. | 예 / 예, 새 날짜·지역·화재 위험 / 아니오 | L07~L09와 같은 source의 내부 지역 구조 후보. |

### 2.3 Tail Information Risk

11개 중 **8개**(정상 장문 6개와 KBS 반복 2개)는 끝까지 대체로 같은 기사 주제를 유지한다. **9개**(정상 장문 6개, 다주제/혼합 3개)의 후반 25%에는 앞 구간에 없는 새 사실·발언·날짜·주제가 보인다. KBS 2개는 뒤쪽에 본문이 있지만 앞 본문과 **거의 같은** 내용을 반복한다. 후반 25%가 *대부분* boilerplate인 record는 0/11이다. 이 값은 Gold Event/Statement/Entity annotation이 아니라 **뒷부분을 자르면 의미가 사라질 가능성**에 관한 정성 표시다. L04/L06의 뒷부분은 의미 있는 사실이라도 raw title의 기사가 아닌 다른 기사이므로 KG 입력 위험의 성격이 다르다.

### 2.4 Truncation Policy Comparison

비교를 구체화하려고 A에 **앞 10,000자**, B에 **앞 100개 근사 문장**을 예시 cap으로 놓았다. cap은 실험용 숫자이며 실제 런타임 문장 분할·모델 비용을 측정한 값이 아니다. C의 source/body boundary도 아직 검증·구현하지 않았으므로 해당 cap의 실제 영향 건수는 결정할 수 없다.

| 가설 | 의미 정보 손실 / 이 corpus의 사례 | 구현 복잡도 | 모델 연산량 | offset·provenance 관리 | 현재 영향 |
| --- | --- | --- | --- | --- | --- |
| A. 앞 N자 | 높음. 정상 장문 6개의 뒤쪽 사실이 사라질 수 있고, L04/L06의 잘못 합쳐진 원문도 복구하지 못한다. | 낮음 | 낮음 | 자른 끝 이후 원문 span을 잃음; 앞쪽 offset은 유지 가능 | N=10,000이면 11/11, 총 160,231자 중 **50,231자(31.3%)** 미사용 |
| B. 앞 N문장 | 높음. L03의 인터뷰 후반, L07~L11의 지역·임상 구간 손실 가능. 문장 경계는 런타임과 다를 수 있다. | 중간 | 낮음~중간 | 원문 sentence start/end를 유지해야 하며 splitter 변경에 민감 | 근사 N=100이면 11/11, 총 근사 2,896문장 중 **1,796문장(62.0%)** 미사용 |
| C. source/body boundary 후 필요할 때만 sentence cap | boundary를 정확히 찾으면 KBS 반복·footer·복수 콘텐츠를 구별할 수 있다. 다만 genuine long 6개의 cap은 여전히 정보 손실 위험. | 높음, source 증거·예외 검증 필요 | 중간, 정제 결과와 cap에 따라 달라짐 | 원문 좌표와 정제 구간의 양방향 provenance가 필요; KBS의 anchor 뒤 본문 반복이 edge case | 구조 검토 대상 11/11; 실제 sentence cap 적용 건수 **미정** |
| D. 장문 전체 처리 | 정상 장문의 tail 손실 0. 그러나 L04/L06의 잘못 합쳐진 기사와 L05 다주제 구성이 그대로 모델에 들어갈 수 있다. | truncation만 보면 낮음 | 가장 높음; 11건 전체 160,231자 / 근사 2,896문장 | raw text offset 유지가 가장 단순하지만 잘못 합쳐진 원문 provenance는 별도 문제 | 전체 처리 11/11, 잘리는 건 0 |

**검토 우선순위: C → D → B → A**. C는 body/기사 경계를 소수 사례에서 검증할 경우 가장 많은 구조 문제를 함께 다룰 수 있다는 *가설*이다. 검증 전에는 D가 정상 장문 tail을 보존하는 비교 기준이다. 특히 11/5,316건(0.21%)뿐이라 이 corpus에서 D의 추가 연산량이 전역적으로 크다고 단정할 근거는 없다. 어느 가설도 최종 정책으로 확정하지 않는다.

## 3. Legacy vs Full-version

### 3.1 Corpus Statistics

| Type | Record / raw article file | URL entity / source / domain | Content 문자 min / median / mean / max | GNews 잔여 표식 |
| --- | ---: | ---: | ---: | ---: |
| legacy | 1,329 / 133 | 1,210 / 172 / 184 | 265 / 266 / 265.54 / 267 | 1,329/1,329 (100%) |
| fullversion | 3,987 / 999 | 3,626 / 389 / 365 | 500 / 1,295 / 1,660.54 / 27,993 | 해당 legacy 형식 표식 조사 범위 아님 |

legacy의 좁은 길이 분포와 `[N chars]` 표식은 **GNews 제공 길이 제한**을 강하게 시사한다. 그러나 짧다는 사실만으로 요약인지 도입부인지 결정하지 않았고, 실제 pair 문자열 관계 및 legacy 단독 표본을 아래에서 확인했다. URL entity는 같은 collection 안의 normalized URL 중복 record를 한 기사 후보로 묶은 단위다. URL별 content 변형이 있는 entity는 legacy 5개, full 7개로, 대표 record 한 쌍의 결과를 모든 중복 row의 본문으로 확대하면 안 된다.

### 3.2 Matched Article Pairs

Normalized URL 동일을 1순위로 놓고, 제목+source, 제목+publishedAt+source, 보수적 title 정규화를 차례대로 적용했다. 제목 단독으로는 source 이름이나 generic title이 흔해 모호하므로, 2순위에는 비-generic title·동일 발행일 조건을 추가했다. Unicode NFKC/인용부호/공백 정규화 외에 semantic pairwise 검색은 하지 않았다. **Pair는 중복 raw row 수가 아닌 URL entity 한 쌍**이다.

| Method | Candidate key / entity-pair 조합 | 채택 pair / 양쪽 unique entity | Ambiguous key 또는 시간 충돌 |
| --- | ---: | ---: | ---: |
| normalized URL | 45 / 45 | 45 / 45+45 | 0 |
| exact title + source | 2 / 7 | 0 / 0+0 | 2 |
| title + publishedAt + source | 0 / 0 | 0 / 0+0 | 0 |
| conservative title normalization | 0 / 0 | 0 / 0+0 | 0 |

제목+source의 두 key는 여러 후보 entity를 가리켜 대응 관계를 채택하지 않았다(상세 ID는 근거 JSON `ambiguityExamples`). 채택된 legacy 45/1,210 entity(3.7%) 외의 **1,165 entity**는 이 데이터 안에서 full 대응을 찾지 못했다. 이는 다른 수집 시점·coverage의 차이일 수 있지만 원인을 확정할 수 없다. URL이 다른 동일 기사도 미발견일 수 있다.

### 3.3 Content Relationship

Raw legacy는 끝의 `... [N chars]` 표식 때문에 full content의 문자 그대로 prefix는 아니다. **관계 분류에서만 그 provider 표식을 제거**한 substantive body를 비교했다. Raw URL·본문을 수정하거나 정규화 본문을 만들지 않았다.

| Relation (채택 45쌍) | Count / 비율 | 관찰 |
| --- | ---: | --- |
| `EXACT_PREFIX` (표식 제외 body) | 45 / 100% | 45쌍 모두 full content의 시작과 문자 단위 동일. legacy의 근사 문장 모두 full 안에 문자 그대로 존재. |
| `NORMALIZED_PREFIX`, `EXTRACTIVE_SNIPPET`, `DESCRIPTION_LIKE`, `DIFFERENT_CONTENT`, `UNCLEAR` | 각 0 / 0% | 이 **채택 쌍**에서 추가 유형을 관측하지 않았다. Unmatched legacy에 대한 0건 판정은 아니다. |
| `ABSTRACTIVE_SUMMARY` | 관측 0 | 채택 쌍은 전부 정확한 prefix라 재작성 요약으로 분류할 근거가 없다. |

Legacy **raw 길이/full 길이**는 중앙값 17.4%(3.2~43.7%, 평균 18.7%), **표식 제외 body/full 길이**는 중앙값 16.3%(3.1~41.1%, 평균 17.6%)다. 정확한 prefix이므로 substantive body가 full 시작의 바로 그 비율을 커버한다. GNews `[N chars]`에 적힌 잔여량과 실제 full의 잔여 길이 차이는 35쌍에서 0자, 10쌍에서 -1자다. 20/45쌍(44.4%)은 비종결 문자와 뒤따르는 full 본문으로 보아 **문장 중간 잘림 후보**다. 근사 문장 전체가 full에서 발견됐다는 45/45 결과에는 마지막 미완결 fragment도 포함되므로, 모든 문장이 완결됐다는 뜻은 아니다. 길이가 가장 짧은/중앙/긴 비율의 3쌍 발췌는 근거 JSON `contentRelationshipRepresentativeSamples`에 한정해 저장했다.

### 3.4 Legacy-only Sample Review

URL 대응이 없는 legacy entity에서 category, 상위 source, 다른 domain, generic/긴 title, description 일치, 문장 끝 edge를 우선하여 **25건**을 직접 읽었다. 아래 S01~S25는 근거 JSON `legacyOnlySample`의 순서이며 각 항목에 완전한 article identifier, source/domain/category/title, 265~267자 본문과 description을 보존한다. 모두 provider 잔여 표식이 있고, **25/25의 표식 제외 body가 독립적인 완성 기사라고 확인할 수 없었다**. `content == description`은 1/25, body가 문장부호로 끝난 것은 3/25이지만, 후자도 표식에 잔여 글자가 선언돼 있다.

| Sample | Source / category | 읽은 범위에서의 내용 형태 후보 |
| --- | --- | --- |
| S01 | v.daum.net / business | AI 기업 IPO 기사 도입부; 뒤 문장 잘림 |
| S02 | v.daum.net / entertainment | 연예 기사 도입부; 뒤 문장 잘림 |
| S03 | GameGPU / general | 기기 판매 내용의 요약형 도입; 원문 대응이 없어 요약/도입 구별 불확실 |
| S04 | 네이버 프리미엄콘텐츠 / health | 보이지 않는 문자·bullet 숫자 구간에서 시작; 본문 중간 fragment 가능, **UNCLEAR** |
| S05 | 연합뉴스 / nation | 피해 상황 소제목과 통신사 dateline 뒤 도입부 |
| S06 | 서울파이낸스 / science | 배터리 기사 도입부 |
| S07 | 연합뉴스 / sports | 축구 기사 도입부가 마침표로 끝나도 잔여 표식 존재 |
| S08 | tokenpost.kr / technology | 비트코인 기사 도입부 |
| S09 | 연합뉴스 한민족센터 / world | 자동차 경기 도입부; title은 기사 headline 아닌 source 이름 |
| S10 | v.daum.net / general | 스포츠 기사 도입부 |
| S11 | 연합뉴스 / general | 자동차 경기 도입부; S09와 내용·잔여 길이가 같은 source 표기 변형 후보 |
| S12 | KBS 뉴스 / general | `기사 본문 영역`·읽어주기 UI·실제 headline 다음에 본문 시작; raw title은 source 이름 |
| S13 | 한겨레 / general | 날씨 기사 도입부 |
| S14 | 매일경제 / world | `AI 해설 기사`·`Key Points` 등 **해설형 콘텐츠의 앞부분**; 본 기사 도입이라고 볼 수 없음 |
| S15 | 경향신문 / general | 애도 기사 도입부 |
| S16 | 한국경제 / general | 무역 기사 도입부; description은 제목·기자·분야 정보에 가까움 |
| S17 | 지디넷코리아 / business | 반도체 기사 도입부 |
| S18 | 뉴스핌 / general | `*AI를 활용해 정리한 경기 내용` 안내 뒤 경기 내용 시작; **AI 작성 안내 포함** |
| S19 | YTN / general | `AD`, 앵커·기자 표기 뒤 스포츠 본문 시작 |
| S20 | MBC 뉴스 / nation | category·기자·headline 두 번 뒤 정치 본문 시작 |
| S21 | 연합뉴스 한민족센터 / general | 시리아 사건의 도입부인데 raw title/description은 source 소개; metadata 품질 문제 |
| S22 | starnewskorea.com / sports | 야구 기사 도입부가 마침표로 끝나도 잔여 표식 존재; description과 body가 정규화 기준 동일한 1건 |
| S23 | 스포츠경향 / general | 연예 기사 도입부 |
| S24 | 더구루 / general | 부동산 기사 도입부; description은 lead와 비슷함 |
| S25 | 대구MBC / general | 경기 기사 도입부; description은 제목형 |

이 표본의 대략적인 형태는 일반 도입부 **19건**, UI/header가 body 앞에 있는 **3건**, AI 해설·작성 안내 **2건**, 시작 위치가 불명확한 fragment **1건**이다. 이는 전체 unmatched 1,165 entity의 유형 비율 추정치가 아니다. Source 이름 title이나 AI 안내 사례는 1차 후보 패턴 검토에도 유용하다.

### 3.5 Metadata Comparison

확실한 URL pair 45쌍에서 raw `title`, `source`, exact `url`, normalized URL, `publishedAt`, `description`이 **각각 45/45 동일**했다. 이 subset에서는 legacy 본문이 부분적이어도 metadata가 full과 안정적으로 함께 보존됐다. 다만 S09/S21처럼 title이 source 이름이고 description이 source 소개일 수 있으므로 **pair 간 동일성은 metadata의 기사 적합성 보증이 아니다**. 또한 45쌍 밖의 metadata 안정성은 이 감사로 판단할 수 없다.

### 3.6 Duplicate Interaction

중복 group은 동일 key를 가진 raw row가 2개 이상인 집합이다. `legacy↔full`은 서로 다른 content hash라도 URL key가 같은 경우를 포함한다. 그룹에 3개 이상 row가 있으면 row-pair 수가 group 수보다 많다.

| Key | legacy↔legacy | full↔full | legacy↔full | 총 group |
| --- | ---: | ---: | ---: | ---: |
| Exact URL | 113 | 348 | 45 | 506 |
| Normalized URL | 113 | 348 | 45 | 506 |
| Exact raw content hash | 139 | 384 | 0 | 523 |

Exact URL group 내부 row-pair는 각각 121, 370, 55다. Legacy↔full 45 URL group 중 6개는 category도 다르다. Full↔full URL 중복 348 group은 모두 다른 category를 포함하며, L01/L02가 한 예다. Legacy↔full의 exact content hash가 0인 이유는 provider 표식과 본문 길이가 다르기 때문이다. **서로 다른 hash를 서로 다른 기사로 취급하면 45개의 동일 URL 기사 도입부가 양쪽에 각각 입력**될 수 있다. 실제 중복 Event/Statement/Entity 건수는 모델 실행 전이라 측정하지 않았다.

## 4. Model Input Eligibility

평가 대상은 *향후* `Raw Article → preprocessing → ArticleLocal KG Model` 경로다. 현재 raw GNews row가 그대로 모델에 실행 연결돼 있다는 뜻이 아니다. 모델의 [`ArticleInput.from_mapping`](ArticleLocal-KG-DeBERTa/runtime/eventframe/contracts.py)은 비어 있지 않은 content와 `published_at`을 요구하고, [`RuntimePreprocessor.prepare`](ArticleLocal-KG-DeBERTa/runtime/eventframe/preprocessing.py)는 입력 원문 좌표의 sentence/span을 사용한다. Raw GNews의 `publishedAt` 필드와 원문·정제 본문 사이 좌표 연결은 별도 경로의 검증 대상이다. Viewer [`data/README.md`](data/README.md)는 `processed`/`gold`를 사용하며, 기존 [`build_gnews_1k.py`](data/tools/build_gnews_1k.py)는 fullversion raw에서 선택해 processed/Gold scaffold를 만든다. 이 감사에서는 그 코드를 고치거나 모델 결과를 생성하지 않았다.

| Collection | A. Production KG extraction | B. Training / Gold annotation 후보 | C. Retrieval / metadata fallback |
| --- | --- | --- | --- |
| `gnews_legacy` | **FALLBACK_ONLY**: 전체 1,329건의 provider 잘림 표식; 확인된 45쌍은 full 앞 **중앙값 16.3%**뿐이고 20쌍은 문장 중간 종료 후보. 본문 전체 사건·발언·실체를 대표하는 정상 입력으로 판정할 근거 부족. 단, **부분 lead extraction**을 별도 태스크로 평가할 가능성은 열어 둔다. | **NOT_ELIGIBLE**(완전 기사 Gold/학습 원문 목적): 확인된 pair에서 후반 대부분이 없고 모든 legacy에 잔여 표식. 부분 snippet만 명시한 별도 주석 실험은 다른 목적이며 여기서 금지한 것은 아니다. | **ELIGIBLE_WITH_CONDITIONS**: URL pair 45쌍에서 metadata 6필드 45/45 일치하며 검색·기사 식별·dedup에 가치. Source 이름 title, source 소개 description, category 중복과 URL variant는 검토 필요. |
| `gnews_fullversion` | **ELIGIBLE_WITH_CONDITIONS**: legacy보다 본문 분포가 넓고 6/11 장문은 실제 후반 정보가 있다. 그러나 장문 2건 raw title과 다른 여러 기사가 합쳐지고 1건 다주제 digest, 2건 동일 본문+UI 반복이다. 전체 3,987건의 구조 적합성을 단정하지 말고 body/기사 경계·중복·offset 검증 필요. | **ELIGIBLE_WITH_CONDITIONS**: 기존 1K 구축 도구가 full raw→processed/Gold scaffold를 사용하지만, raw 전량이 곧 Gold 원문이라고 볼 수 없음. 혼합 기사·중복·출처 좌표 확인 뒤 선별 가능. | **ELIGIBLE_WITH_CONDITIONS**: URL/title/category·긴 본문이 검색 근거를 주지만 full↔full exact URL 348 group 및 content hash 384 group을 그대로 색인하면 반복 hit가 생길 수 있다. |

이 표는 **article-level eligibility 후보 판단**이며 실행 코드나 삭제 정책이 아니다. Legacy의 1,165 unmatched entity가 다른 full 수집본에 존재하는지, 일부 legacy가 짧지만 독립된 기사인지, 모델이 부분 lead로 어떤 KG 오류를 내는지는 아직 충분한 증거가 없다. `FALLBACK_ONLY`는 현 목표인 *완전한 ArticleLocal KG construction*을 기준으로 한 추천이고, 부분 lead 태스크에 대한 절대적 금지는 아니다.

## 5. Open Questions

1. L04/L06처럼 raw title과 다른 독립 기사들이 content에 합쳐지는 문제가 각 source의 다른 record에도 있는가? 현재 장문 2건만 직접 확인했다.
2. KBS L01/L02의 `■ 제보하기` 뒤 같은 본문 반복은 다른 KBS record에도 재현되는가? Anchor 자체는 KBS 계열 148건에 관측됐지만 본문 반복 빈도는 미측정이다.
3. URL이 다른 legacy/full 동일 기사, 그리고 normalized URL 내부의 서로 다른 content version 5/7 entity는 어느 원문을 대표하는가?
4. Fullversion 3,987건 중 중·단문에도 AI 해설, 여러 콘텐츠 합본, title mismatch가 어느 비율로 있는가? 1차 후보 그룹의 제한된 sample로 후속 검토가 필요하다.
5. 모델의 실제 sentence splitter와 입력 길이별 비용·추출 품질, 원문 absolute offset 유지 방법이 검증돼야 cap 수치를 평가할 수 있다.

## 6. Recommendations for Pattern Catalog

사람이 다음 단계에서 우선 확인할 candidate는 **(1)** KBS `기사 본문 영역`·읽어주기 UI·`■ 제보하기` 앞뒤의 반복 본문, **(2)** 슬로우레터의 여러 뉴스 항목과 4/4 관측 footer, **(3)** 이코노미톡뉴스 지역별 예보를 실제 기사 내부 소제목으로 보존할 필요, **(4)** raw title과 본문이 다른 sidae.com·현대건강신문 장문, **(5)** legacy provider 잘림 표식과 매일경제/뉴스핌 AI 안내다. `candidate_patterns.json`의 발생 빈도와 이 보고서의 구간 관찰을 함께 검토해야 한다. `KEEP`, `REMOVE`, `RECOVER`, `REJECT` 정책과 source별 production 규칙은 아직 정하지 않는다.
