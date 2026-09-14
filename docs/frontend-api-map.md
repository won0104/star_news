# 별빛 뉴스 페이지별 API 연동 정리

> 기준 문서: [API 명세](https://app.notion.com/p/65cc86b36bc082bc94a481619baca626)  
> 최신 데이터베이스: [Spring Boot · /api/v1](https://app.notion.com/p/6afc86b36bc0836ea0c4018497e6262a), [FastAPI · /internal/v1](https://app.notion.com/p/df8c86b36bc083b0b2320158594177c6)  
> 확인 시점: 2026-09-11

## 1. 전체 계약

- Frontend는 Spring Boot의 `/api/v1`만 호출한다.
- FastAPI의 `/internal/v1`은 Spring Boot 또는 Spring Batch 전용이다.
- 회원 API는 `Authorization: Bearer {accessToken}`을 사용한다.
- Refresh Token은 `HttpOnly Cookie`로 전달하므로 인증 요청에는 `credentials: 'include'`가 필요하다.
- 일반 성공 응답은 `{ data, meta: { requestId } }` 형식이다.
- 실패 분기는 사용자 메시지가 아니라 `code`를 기준으로 한다.
- 목록은 기본적으로 `cursor`, `size`를 사용하고 응답은 `items`, `hasNext`, `nextCursor`를 사용한다.
- Frontend는 `nextCursor`를 해석하거나 변경하지 않고 다음 요청에 그대로 전달한다.
- `204 No Content`는 공통 응답 객체로 감싸지 않는다.
- 그래프 식별자는 Neo4j 내부 ID가 아닌 `nodeType + nodeKey` 조합을 사용한다.

## 2. 페이지별 한눈에 보기

| 화면 | 경로 | 최초 호출 | 후속 호출 |
|---|---|---|---|
| 메인/오늘의 트렌드 목록 | `/`, `/trend` | `GET /home` | 트렌드 선택 시 그래프 API |
| 주요 트렌드 별자리 | `/app?view=trend` | `GET /home` | `neighbors`, Node 상세, 관련 기사, 클릭 기록 |
| 나를 위한 추천 | `/app?view=foryou` | `GET /recommendations` | 추천 상세 |
| 추천 Event 상세 | `/event/:id` | `GET /recommendations/{userRecommendationId}` | 기사 상세·요약·열람·북마크 |
| 나의 기록 | `/app?view=log` | `GET /users/me/graph` + `GET /users/me/history` | Topic 지도, Node별 읽은 기사 |
| 나의 리포트 | `/app?view=report` | `GET /users/me/statistics/news-report` | 선택한 Node가 있으면 공용 그래프 API |
| 검색/탐색 | `/explore` | `GET /search` | Node 상세·주변 그래프·관련 기사 |
| 로그인 | `/login` | 없음 | 로그인, 전역 토큰 갱신 |
| 회원가입 | `/signup` | 아이디 중복 확인 | 회원가입 |
| 계정 설정 | 설정 Overlay | 현재 대응 조회 API 없음 | 회원 탈퇴만 존재 |
| 관심 관리 | 설정 Overlay | 관심 Topic + Node 즐겨찾기 | 일괄 저장 |
| 관심 없음 관리 | 설정 Overlay | 비관심 Topic | 일괄 저장 |
| 기사 상세 사이드바 | 여러 화면 공통 | 기사 상세 | 요약 생성·열람 기록·북마크 |

## 3. 인증 페이지

### 회원가입 `/signup`

1. **아이디 중복 확인**
   - `GET /api/v1/auth/login-id/availability?loginId={loginId}`
   - 인증 불필요
   - 입력: 영문 소문자·숫자·밑줄, 4~50자
   - 화면 사용 데이터: `data.loginId`, `data.available`
   - `available=true`는 아이디 예약을 의미하지 않는다.

2. **회원가입**
   - `POST /api/v1/auth/signup`
   - 인증 불필요
   - 입력: `loginId`, `password`, `nickname`, 선택값 `interestedTopicCodes[]`, `dislikedTopicCodes[]`
   - 출력: `userId`, `loginId`, `nickname`, 두 Topic 배열
   - 성공: `201 Created`; 가입과 동시에 로그인 토큰은 발급하지 않는다.

### 로그인 `/login`

- `POST /api/v1/auth/login`
- 입력: `loginId`, `password`
- 출력: `accessToken`, `tokenType`, `expiresIn`, `user { userId, loginId, nickname }`
- Refresh Token은 응답 본문이 아니라 Cookie로 받는다.
- 인증 실패는 아이디 존재 여부를 노출하지 않고 `INVALID_CREDENTIALS`로 통일한다.

### 전역 인증 처리

- **토큰 갱신:** `POST /api/v1/auth/refresh`
  - Body 없음, Refresh Cookie 사용
  - 출력: 새 `accessToken`, `tokenType`, `expiresIn`
  - Refresh Token Rotation을 적용한다.
- **로그아웃:** `POST /api/v1/auth/logout`
  - Access Token + Refresh Cookie 필요
  - 성공: `204 No Content`
  - 프론트는 성공 여부와 관계없이 로컬 Access Token과 사용자 상태를 정리하는 편이 안전하다.

## 4. 메인 및 주요 트렌드

### 트렌드 초기 데이터

- `GET /api/v1/home`
- 인증 불필요
- 화면 사용 데이터:
  - `trendSnapshotId`: 현재 스냅샷 식별자
  - `snapshotAt`: 집계 기준 시각
  - `trends[]`: 최대 10개
  - 항목별 `trendItemId`, `rank`, `nodeType`, `nodeKey`, `label`, `articleCount`, `growthRate`
- 최신 완료 스냅샷이 없으면 오류 대신 빈 `trends[]`를 받는다.
- 06:00·18:00에 최근 24시간 기준 스냅샷이 갱신된다.
- 이 응답에는 주변 별, Edge, 관련 기사, 개인화 정보가 들어오지 않는다.

### 별자리 화면 `/app?view=trend`

1. `GET /home`의 Event를 중심 별 후보로 표시한다.
2. 중심 Event 선택 또는 주변 Event 재중심화:
   - `GET /api/v1/graphs/nodes/{nodeType}/{nodeKey}/neighbors?depth=1&limit=15`
   - 출력: `centerNode`, `nodes[]`, `edges[]`, `returnedCount`, `hasNext`, `nextCursor`
   - Edge의 `weight`를 선 굵기와 발광 강도에 사용할 수 있다.
   - 중심 가능 유형은 `EVENT`, `ENTITY`, `STATEMENT`지만 현재 UX에서는 Event만 재중심화하도록 제한할 수 있다.
   - 주변 결과에는 `TIME`이 포함될 수 있으나 중심으로 사용할 수 없다.
3. 중심 별 상세 패널:
   - `GET /api/v1/graphs/nodes/{nodeType}/{nodeKey}`
   - 출력: `title`, `type`, `time`, `bookmarked`
4. 관련 기사 패널:
   - `GET /api/v1/graphs/nodes/{nodeType}/{nodeKey}/articles?size=30`
   - 출력: `articles[]`, `totalCount`, `returnedCount`, `hasNext`, `nextCursor`
   - 기사 항목: `articleId`, `title`, `organizationName`, `publishedAt`, `bookmarked`
5. 로그인 사용자가 실제 Node를 클릭한 경우:
   - `POST /api/v1/users/me/graph/nodes/{nodeType}/{nodeKey}/clicks`
   - 렌더링이나 자동 재조회가 아니라 실제 클릭 1회당 한 번만 호출한다.

### 공용 Node API의 지원 범위

- 상세·중심·관련 기사 지원: `EVENT`, `ENTITY`, `STATEMENT`
- 주변 Node로만 반환 가능: `TIME`
- 현재 단독 상세에서 제외: `STORY`, `TOPIC`, `CONCEPT`, `ARTICLE`

## 5. 나를 위한 추천

### 추천 보드 `/app?view=foryou`

- `GET /api/v1/recommendations?size=10`
- JWT 필요
- 06:00·18:00에 공개되는 최신 사전 계산 회차를 조회한다.
- 화면 사용 데이터:
  - 회차: `cycle`, `generatedAt`, `availableAt`
  - 카드: `userRecommendationId`, `eventId`, `label`, `topicCode`, `score`, `rank`, `recommendationType`, `reason`
  - 페이지네이션: `hasNext`, `nextCursor`
- 카드 링크에는 `eventId`가 아니라 상세 API 키인 `userRecommendationId`를 사용해야 한다.

### 추천 Event 상세 `/event/:id`

- `GET /api/v1/recommendations/{userRecommendationId}`
- JWT 필요
- 출력:
  - Event: `userRecommendationId`, `eventId`, `label`, `topicCode`
  - 요약: `contextSummary`
  - 기사: `articleId`, `title`, `organizationName`, `publishedAt`, `topicCode`, `originalUrl`
- Event 요약은 없거나 Event가 변경됐을 때만 상위 기사 최대 3개로 생성하고 이후 공통 재사용한다.
- 관련 기사 전체가 응답에 포함되지만 현재 명세에는 `cursor`와 `size`가 없다.

## 6. 기사 상세 사이드바

여러 페이지에서 기사를 선택할 때 같은 흐름을 재사용한다.

1. **상세 조회**
   - `GET /api/v1/articles/{articleId}`
   - 출력: `title`, `organizationName`, `publishedAt`, `summary`, `summaryStatus`, `originalUrl`, `bookmarked`
2. **요약 처리**
   - `COMPLETED`: 반환된 요약 표시
   - `NOT_REQUESTED`, `FAILED`: `POST /api/v1/articles/{articleId}/summary`
   - `PROCESSING`: 중복 생성 요청 없이 로딩 후 상세 GET 재조회
   - 요약 POST는 `200 COMPLETED` 또는 `202 PROCESSING`을 반환한다.
3. **열람 기록**
   - 로그인 사용자의 상세 GET 성공 후 `POST /api/v1/articles/{articleId}/reads`
   - 화면 진입 1회당 한 번만 호출하고 polling·재렌더링에서는 호출하지 않는다.
   - 성공: `204 No Content`
4. **기사 북마크**
   - `PATCH /api/v1/users/me/bookmarks/articles`
   - Body: `{ changes: [{ articleId, bookmarked }] }`
   - 한 개 변경과 여러 개 일괄 변경에 같은 API를 사용한다.

## 7. 나의 기록

### 최초 화면 `/app?view=log`

두 요청을 병렬로 호출한다.

1. `GET /api/v1/users/me/graph`
   - 7개 Topic Cluster를 모두 반환한다.
   - 출력: `generatedAt`, `nodes[]`, `edges[]`
   - Node: `id`, `kind`, `nodeType`, `nodeKey`, `topicCode`, `title`, `sourceArticleCount`, `weight`
   - `weight`는 별 크기와 강조 단계에 사용한다.
2. `GET /api/v1/users/me/history?size=20`
   - 출력: `items[]`, `hasNext`, `nextCursor`
   - 기사: `articleId`, `title`, `organizationName`, `topicCode`, `topicName`, `lastReadAt`, `clickCount`, `summaryPreview`, `bookmarked`
   - 오늘·어제 같은 날짜 그룹은 `lastReadAt`으로 Frontend가 만든다.

### Topic 선택 후 상세 지도

- `GET /api/v1/users/me/graph/map?topicCode={topicCode}`
  - Topic 전체 Node·Edge Snapshot을 한 번에 받는다.
  - 확대 단계는 추가 요청 없이 `weight`를 기준으로 Frontend가 제어한다.
- `GET /api/v1/users/me/history?topicCode={topicCode}&size=20`
  - 선택 Topic의 열람 기록만 표시할 때 사용한다.

### 개인 그래프 Node 선택

- Node 정보: `GET /api/v1/graphs/nodes/{nodeType}/{nodeKey}`
- 해당 Node와 연결된 읽은 기사:
  - `GET /api/v1/users/me/graph/nodes/{nodeType}/{nodeKey}/articles?size=20`
  - 출력: `node`, `items[]`, `hasNext`, `nextCursor`
  - `items[]`에는 `lastReadAt`, `summaryPreview`, `bookmarked`가 포함된다.
- 실제 클릭 신호:
  - `POST /api/v1/users/me/graph/nodes/{nodeType}/{nodeKey}/clicks`

## 8. 나의 리포트

### `/app?view=report`

- `GET /api/v1/users/me/statistics/news-report`
- JWT 필요, 기간은 최근 3개월 고정
- 화면 카드별 데이터:
  - 헤더: `period.from`, `period.to`, `totalReadArticleCount`, `generatedAt`
  - 분야별 읽기: `topicReads[] { topicCode, topicName, readArticleCount }`
  - 출처별 비중: `sourceReads[] { organizationId, organizationName, readArticleCount, ratio }`
  - 최근 12주 변화: `weeklyTopicTrend[] { weekStart, topics[] }`
  - 최근 주제 지형: `topicLandscape[] { nodeType, nodeKey, label, topicCode, readArticleCount, firstSeenAt, lastSeenAt, familiarity }`
- 기록이 없으면 404가 아니라 카운트 0과 빈 배열을 받는다.
- 리포트는 사용자 단위 완성 응답을 Redis에 캐시하며 기사 열람 시 무효화된다.

## 9. 검색 및 탐색

### 검색

- `GET /api/v1/search?query={query}&size=20`
- 인증 불필요
- 검색 대상: `EVENT`, `STORY`, `ENTITY`, `STATEMENT`
- 출력: `items[] { nodeType, nodeKey, label }`, `hasNext`, `nextCursor`
- 결과가 없으면 200과 빈 배열을 받는다.

### 결과 선택

- Node 상세: `GET /graphs/nodes/{nodeType}/{nodeKey}`
- 주변 탐색: `GET /graphs/nodes/{nodeType}/{nodeKey}/neighbors`
- 관련 기사: `GET /graphs/nodes/{nodeType}/{nodeKey}/articles`
- 단, 검색 결과의 `STORY`는 현재 공용 Node 상세 API에서 지원하지 않으므로 별도 처리 전에는 선택 불가능 상태로 보여야 한다.

## 10. 설정 Overlay

### 관심 관리

- Topic 초기값: `GET /api/v1/users/me/topic-preferences/interests`
- Topic 저장: `PUT /api/v1/users/me/topic-preferences/interests`
  - Body: `{ topicCodes: TOPIC[] }`
  - 빈 배열은 전체 해제
  - 기존 DISLIKE Topic을 저장하면 INTEREST로 전환
- 즐겨찾기 Node 목록:
  - `GET /api/v1/users/me/bookmarks/nodes?cursor=&size=20&nodeType=`
  - 출력: `nodeType`, `nodeKey`, `name`, `bookmarkedAt`
- 즐겨찾기 Node 변경:
  - `PATCH /api/v1/users/me/bookmarks/nodes`
  - Body: `{ changes: [{ nodeType, nodeKey, bookmarked }] }`

### 관심 없음 관리

- 초기값: `GET /api/v1/users/me/topic-preferences/dislikes`
- 저장: `PUT /api/v1/users/me/topic-preferences/dislikes`
  - Body: `{ topicCodes: TOPIC[] }`
  - 빈 배열은 전체 해제
  - 기존 INTEREST Topic을 저장하면 DISLIKE로 전환

### 계정 설정

- 현재 명세에서 가능한 서버 작업은 회원 탈퇴뿐이다.
  - `DELETE /api/v1/users/me`
  - Body: `{ password }`
  - 성공: `200 { data: null, meta }`
- 현재 UI에 있는 이메일 변경과 비밀번호 변경 API는 명세에 없다.
- 사용자 프로필을 다시 조회하는 `GET /users/me`도 없다.

### 화면 설정

- 밝게/어둡게, 글자 크기, 애니메이션 제거는 현재 서버 API가 없다.
- 로컬 설정으로 유지하거나 사용자 동기화가 필요하면 별도 Preferences API를 추가해야 한다.

## 11. 북마크 목록

- 기사 목록:
  - `GET /api/v1/users/me/bookmarks/articles?cursor=&size=20`
  - 최신 등록순, `articleId`, `title`, `publisher`, `publishedAt`, `summary`, `bookmarkedAt`
- 기사 변경:
  - `PATCH /api/v1/users/me/bookmarks/articles`
- Node 목록:
  - `GET /api/v1/users/me/bookmarks/nodes?cursor=&size=20&nodeType=`
- Node 변경:
  - `PATCH /api/v1/users/me/bookmarks/nodes`

현재 독립된 북마크 화면은 없지만 기사 패널, 관심 관리, 향후 저장 목록에서 재사용할 수 있다.

## 12. FastAPI 내부 API

Frontend에서는 호출하지 않는다.

| 상태 | 호출 주체 | API | 입력/출력 요약 |
|---|---|---|---|
| 작성 중 | Spring Boot | `POST /internal/v1/articles/analyze` | 기사 원문 → Topic, Event·Story·Entity·Statement ID와 캐시 무효화 대상 |
| 작성 중 | Spring Batch | `POST /internal/v1/user-graph/sync` | 사용자별 관심·비관심·소비 Event 집계 → Neo4j User Graph Upsert |
| 작성 중 | Spring Batch | `POST /internal/v1/recommendations/calculate` | 사용자 Chunk → 사용자별 추천 Event 최대 N개 |
| 완료 | Docker/Spring Boot | `GET /internal/v1/health` | `{ status: 'UP' }` |
| 보류 | Spring Boot | `POST /internal/v1/search/semantic` | 자연어 문장 → 유사 Article·Event·Story 후보와 점수 |

### 내부 배치 순서

1. 05:00·17:00: Spring Batch가 MySQL 행동 로그를 집계한다.
2. `/user-graph/sync`로 Neo4j User Graph를 갱신한다.
3. 05:30·17:30: `/recommendations/calculate`로 추천을 계산한다.
4. Spring Batch가 결과를 MySQL에 저장한다.
5. 06:00·18:00: Frontend의 `GET /recommendations`에 새 회차가 노출된다.

## 13. 명세 충돌 및 누락

프론트 연동 전에 아래 항목을 확정해야 한다.

1. **추천 유형 Enum 불일치**
   - 외부 `GET /recommendations`: `CONTENT_BASED | COLLABORATIVE | BOTH`
   - 내부 계산 API 최신 설명: `INTEREST_BASED | KNOWLEDGE_GAP`
   - MySQL에 그대로 저장되므로 하나로 통일해야 한다.
2. **개인 그래프 확장 API 누락**
   - Node별 읽은 기사 명세는 `GET /users/me/graph/nodes/{nodeType}/{nodeKey}/neighbors`도 병렬 호출한다고 설명하지만 실제 API 목록에 해당 엔드포인트가 없다.
   - 현재 `/graph/map`은 Topic Snapshot 전체 반환 방식이므로 이 설명을 제거하거나 API를 추가해야 한다.
3. **오래된 북마크 경로**
   - 일부 Node/기사 상세 문서가 `/users/me/node-bookmarks`, `/users/me/article-bookmarks`를 가리킨다.
   - 실제 최신 API는 `/users/me/bookmarks/nodes`, `/users/me/bookmarks/articles`다.
4. **추천 상세 기사 목록 페이지네이션 없음**
   - 공통 규칙은 모든 목록에 cursor/size를 요구하지만 `GET /recommendations/{id}`의 전체 관련 기사에는 페이지네이션이 없다.
5. **STORY 선택 흐름 단절**
   - 검색은 STORY를 반환하고 리포트 지형도 STORY를 반환하지만 공용 Node 상세·이웃·관련 기사 API는 STORY를 지원하지 않는다.
6. **CONCEPT 선택 흐름 단절**
   - 리포트 지형은 CONCEPT를 반환할 수 있지만 공용 Node 상세에서 제외한다.
7. **계정 설정 API 누락**
   - 이메일 변경, 비밀번호 변경, 내 프로필 조회 API가 없다.
8. **Topic 선택 목록의 출처 없음**
   - 관심/비관심 화면은 TOPIC Enum 목록과 한글 라벨이 필요하지만 이를 조회하는 API가 없다. Frontend 상수로 고정할지 공용 `GET /topics`를 만들지 결정해야 한다.
9. **기사 요약 내부 API 미정**
   - Spring Boot의 기사 요약 생성 흐름은 FastAPI를 호출한다고 되어 있지만 대응하는 FastAPI 내부 요약 API가 아직 명세에 없다.
10. **추천 상세 북마크 상태 누락**
    - 추천 상세의 기사 항목에는 `bookmarked`가 없어 리스트에서 저장 상태를 즉시 표시하려면 기사 상세를 각각 호출하거나 응답 필드를 추가해야 한다.
11. **공통 문서 오타**
    - 원문에 `2204 No Content`가 있으며 `204 No Content`가 맞다.

## 14. 프론트 구현 우선순위

1. 공통 API Client: base URL, 성공 envelope 해제, 오류 `code`, `requestId` 처리
2. 인증: Access Token 메모리 저장, Refresh Cookie, 401 단일 재시도
3. 기사 상세 공통 훅: 상세 → 조건부 요약 → 로그인 시 열람 기록
4. 주요 트렌드: HOME → neighbors → Node 상세/기사 패널
5. 추천: 추천 목록 → 추천 Event 상세 → 기사 사이드바
6. 나의 기록: graph/history 병렬 조회 → Topic map
7. 리포트: 단일 통계 API
8. 설정: 관심·비관심·북마크 Node
9. 누락·충돌 항목 확정 후 계정 변경, STORY/CONCEPT 탐색, 추천 상세 페이지네이션
