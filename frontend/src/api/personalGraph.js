/**
 * 나의 기록 — 개인 지식 그래프.
 *
 * 네 요청 모두 Access Token 이 필요하다. 비로그인이면 401 UNAUTHORIZED 가 오고, 화면은
 * 그것을 오류가 아니라 "로그인하면 볼 수 있다"로 읽어야 한다.
 *
 * 응답 형태는 Java DTO 그대로다(Swagger 문서가 아니라). 중첩 record 이름이 겹쳐
 * 생성 문서의 스키마가 뒤섞이므로, 필드는 아래 주석과 .java 파일을 기준으로 삼는다.
 *
 *   요약   PersonalGraphSummaryResponse
 *          { generatedAt,
 *            nodes: [{ id, kind, nodeType, nodeKey, topicCode, title,
 *                      sourceArticleCount, weight }],
 *            edges: [{ sourceId, targetId, relationship, weight }] }
 *
 *          `kind` 는 TOPIC_CLUSTER 또는 NODE 이고, Cluster 는 nodeType·nodeKey 가 null 이다.
 *          Topic 당 대표 Node 최대 5개만 담긴다 — 분야 안쪽 전체는 map 이 맡는다.
 *
 *   지도   PersonalGraphMapResponse
 *          { generatedAt, topic: { topicCode, label },
 *            nodes: [{ id, nodeType, nodeKey, label, sourceArticleCount, weight }],
 *            edges: [{ sourceId, targetId, relationship, weight }] }
 *
 *          요약과 필드 이름이 다르다 — 여기서는 `title` 이 아니라 `label` 이고 topicCode 는
 *          Node 마다 오지 않는다(요청한 Topic 하나뿐이므로). adapters/personalGraph.js 가 맞춘다.
 *
 *   기사   PersonalNodeArticlesResponse
 *          { node: { nodeType, nodeKey, title },
 *            items: [{ articleId, title, organizationName, topicCode, lastReadAt,
 *                      summaryPreview, bookmarked }],
 *            hasNext, nextCursor }
 *
 *   기록   ArticleHistoryResponse
 *          { items: [{ articleId, title, organizationName, topicCode, topicName,
 *                      lastReadAt, clickCount, summaryPreview, bookmarked }],
 *            hasNext, nextCursor }
 */

import { request } from './client'

/**
 * `GET /users/me/graph` — 최초 진입용 요약.
 *
 * 읽은 것이 하나도 없으면 `nodes`·`edges` 가 빈 배열로 온다(200). 실패가 아니라 상태다.
 */
export async function fetchPersonalGraph({ signal } = {}) {
  return request('/users/me/graph', { signal })
}

/** `GET /users/me/graph/map?topicCode=` — 분야 하나의 EVENT·ENTITY·STATEMENT 전부와 그 사이 Edge. */
export async function fetchPersonalTopicMap(topicCode, { signal } = {}) {
  return request(`/users/me/graph/map?topicCode=${encodeURIComponent(topicCode)}`, { signal })
}

/**
 * `GET /users/me/graph/nodes/{nodeType}/{nodeKey}/articles` — 그 Node 로 내가 **실제로 읽은** 기사.
 *
 * 공개 그래프의 `/graphs/.../articles` 와 다르다. 저쪽은 그 Node 와 이어진 모든 기사고,
 * 이쪽은 그중 내가 연 것만 최근 읽은 순으로 준다. 나의 기록이 쓸 것은 이쪽이다.
 *
 * 개인 그래프에 없는 Node 면 404 NODE_NOT_ACQUIRED.
 */
export async function fetchPersonalNodeArticles(nodeType, nodeKey, { size, cursor, signal } = {}) {
  const query = new URLSearchParams()
  if (size != null) query.set('size', String(size))
  if (cursor) query.set('cursor', cursor)

  const suffix = query.size > 0 ? `?${query}` : ''
  return request(
    `/users/me/graph/nodes/${encodeURIComponent(nodeType)}/${encodeURIComponent(nodeKey)}/articles${suffix}`,
    { signal },
  )
}

/** `GET /users/me/history` — 분야와 무관한 전체 열람 기록, 마지막으로 읽은 순. */
export async function fetchArticleHistory({ size, cursor, signal } = {}) {
  const query = new URLSearchParams()
  if (size != null) query.set('size', String(size))
  if (cursor) query.set('cursor', cursor)

  const suffix = query.size > 0 ? `?${query}` : ''
  return request(`/users/me/history${suffix}`, { signal })
}

/**
 * `POST /users/me/graph/nodes/{nodeType}/{nodeKey}/clicks` — Node 를 직접 누른 기록.
 *
 * 상세 조회(GET)는 클릭으로 치지 않는다. 별을 실제로 누른 순간에만 보낸다. 실패해도
 * 화면이 할 일은 없으므로 호출한 쪽에서 조용히 삼킨다.
 */
export async function recordNodeClick(nodeType, nodeKey, { signal } = {}) {
  return request(
    `/users/me/graph/nodes/${encodeURIComponent(nodeType)}/${encodeURIComponent(nodeKey)}/clicks`,
    { method: 'POST', signal },
  )
}
