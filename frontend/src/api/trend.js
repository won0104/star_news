/**
 * 오늘의 트렌드가 쓰는 두 엔드포인트. 둘 다 인증이 필요 없다 — 비회원도 같은 화면을 본다.
 *
 * Return shapes are the Java DTOs' (HomeResponse, GraphNeighborsResponse), not the
 * Swagger page's. Several DTOs declare nested `Item` / `NodeSummary` / `Edge` records and
 * they collapse onto one schema each in the generated document, so that page shows 개인
 * 그래프's fields for these endpoints. data/trendTop.js and data/trendNeighbors.js carry
 * the real shapes as mock, field for field.
 */

import { request } from './client'

/**
 * `GET /home` — 공개된 최신 회차의 상위 10개 Event.
 *
 * An empty round is not a failure: before the first aggregation, and on any day the
 * pipeline produced nothing, this answers `{ snapshotAt: null, trends: [] }` with a 200.
 * The caller shows its empty state rather than an error.
 */
export async function fetchHomeTrends({ signal } = {}) {
  return request('/home', { signal })
}

/**
 * `GET /topics/{topicCode}/exploration` — 그 분야의 공개된 최신 회차, 최대 10개.
 *
 * `/home` 과 같은 일을 분야 하나에 대해 한다. 응답도 거의 같은 모양인데 이름만 다르다 —
 * `trends`/`trendItemId` 자리에 `entryNodes`/`entryNodeId` 가 온다. 나머지 다섯 필드
 * (rank·nodeType·nodeKey·label·articleCount)는 글자까지 같다. 맞추는 일은 <TrendSky> 가
 * 한 곳에서 하고, 여기서는 서버가 준 모양 그대로 돌려준다.
 *
 * `centerTopic` 이 하나 더 온다 — 중앙에 세울 Topic 이고 순위에는 들어가지 않는다.
 *
 * `/home` 과 마찬가지로 인증이 필요 없고, 빈 회차는 실패가 아니다 —
 * `{ snapshotAt: null, centerTopic, entryNodes: [] }` 를 200 으로 답한다.
 *
 * 지원하지 않는 코드는 400 INVALID_TOPIC_CODE 다. 화면은 URL 의 분야를 topicByCode 로
 * 걸러 보내므로 정상 경로에서는 닿지 않는다.
 */
export async function fetchTopicExploration(topicCode, { signal } = {}) {
  return request(`/topics/${encodeURIComponent(topicCode)}/exploration`, { signal })
}

/**
 * `GET /graphs/nodes/{nodeType}/{nodeKey}` — Node 한 개의 상세.
 *
 * `{ nodeType, nodeKey, title, type, time, bookmarked }`. `type` is the Entity/Statement
 * subtype and `time` the Event's occurrence — both null where the kind has no such thing,
 * and `bookmarked` is always false while signed out.
 *
 * EVENT·ENTITY·STATEMENT 세 유형만 받는다. TIME·STORY 는 400 INVALID_NODE_TYPE.
 */
export async function fetchNodeDetail(nodeType, nodeKey, { signal } = {}) {
  return request(
    `/graphs/nodes/${encodeURIComponent(nodeType)}/${encodeURIComponent(nodeKey)}`,
    { signal },
  )
}

/**
 * `GET /graphs/nodes/{nodeType}/{nodeKey}/articles` — 그 Node와 이어진 기사, 최신 발행 순.
 *
 * `{ articles, totalCount, returnedCount, hasNext, nextCursor }`, and each article is
 * `{ articleId, title, organizationName, publishedAt, bookmarked }`. `totalCount` is the
 * de-duplicated total, which is what a count beside the title should show — `articles`
 * only holds this page.
 */
export async function fetchNodeArticles(nodeType, nodeKey, { size, cursor, signal } = {}) {
  const query = new URLSearchParams()
  if (size != null) query.set('size', String(size))
  if (cursor) query.set('cursor', cursor)

  const suffix = query.size > 0 ? `?${query}` : ''
  return request(
    `/graphs/nodes/${encodeURIComponent(nodeType)}/${encodeURIComponent(nodeKey)}/articles${suffix}`,
    { signal },
  )
}

/**
 * `GET /graphs/nodes/{nodeType}/{nodeKey}/neighbors` — 중심 Node와 주변 Node·Edge.
 *
 * `depth` 1~3, `limit` 1~30. Defaults are left to the server so the two sides cannot
 * drift apart; pass them only where a screen needs something other than the default.
 */
export async function fetchNeighbors(nodeType, nodeKey, { depth, limit, cursor, signal } = {}) {
  const query = new URLSearchParams()
  if (depth != null) query.set('depth', String(depth))
  if (limit != null) query.set('limit', String(limit))
  if (cursor) query.set('cursor', cursor)

  const suffix = query.size > 0 ? `?${query}` : ''
  return request(
    `/graphs/nodes/${encodeURIComponent(nodeType)}/${encodeURIComponent(nodeKey)}/neighbors${suffix}`,
    { signal },
  )
}
