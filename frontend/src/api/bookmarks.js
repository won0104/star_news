/**
 * 내가 저장한 것들 — 기사 북마크와 Node 즐겨찾기.
 *
 * 둘 다 Access Token 이 필요하다. 비로그인이면 401 UNAUTHORIZED 가 오고, 화면은 그걸
 * 오류가 아니라 "로그인하면 볼 수 있다"로 읽어야 한다.
 *
 * Return shapes are the Java DTOs', wrapped in CursorResponse:
 *
 *   articles  { items: [{ articleId, title, publisher, publishedAt, summary, bookmarkedAt }],
 *               hasNext, nextCursor }
 *   nodes     { items: [{ nodeType, nodeId, name, bookmarkedAt }],
 *               hasNext, nextCursor }
 *
 * Node 쪽은 `nodeId`·`name` 이다 — 그래프 API 의 `nodeKey`·`label` 과 이름이 다르니,
 * 저장 목록에서 고른 Node 로 상세를 조회할 때 그대로 넘기면 된다(값은 같은 업무 ID).
 */

import { request } from './client'

const page = ({ size, cursor }) => {
  const query = new URLSearchParams()
  if (size != null) query.set('size', String(size))
  if (cursor) query.set('cursor', cursor)
  return query.size > 0 ? `?${query}` : ''
}

/** `GET /users/me/bookmarks/articles` — 저장한 기사, 최근 저장 순. */
export async function fetchArticleBookmarks({ size, cursor, signal } = {}) {
  return request(`/users/me/bookmarks/articles${page({ size, cursor })}`, { signal })
}

/**
 * `GET /users/me/bookmarks/nodes` — 즐겨찾기한 Node.
 *
 * `nodeType` 으로 걸러 EVENT 만 받을 수 있다. 저장한 이벤트 페이지가 그렇게 쓴다.
 */
export async function fetchNodeBookmarks({ nodeType, size, cursor, signal } = {}) {
  const query = new URLSearchParams()
  if (nodeType) query.set('nodeType', nodeType)
  if (size != null) query.set('size', String(size))
  if (cursor) query.set('cursor', cursor)

  const suffix = query.size > 0 ? `?${query}` : ''
  return request(`/users/me/bookmarks/nodes${suffix}`, { signal })
}

/**
 * `PATCH /users/me/bookmarks/articles` — 기사 북마크의 **최종 상태**를 지정한다.
 *
 *   changes: [{ articleId, bookmarked }]   →   { results: [{ articleId, bookmarked }] }
 *
 * 토글이 아니라 목표 상태다. 같은 상태를 두 번 보내도 오류가 아니고, 응답의 `results` 가
 * 서버가 확정한 값이므로 화면은 그것으로 맞춘다. 빈 배열은 400 EMPTY_CHANGES, 한 기사가
 * 두 번 들어 있으면 DUPLICATED_ARTICLE_CHANGE.
 */
export async function updateArticleBookmarks(changes, { signal } = {}) {
  return request('/users/me/bookmarks/articles', { method: 'PATCH', body: { changes }, signal })
}

/**
 * `PATCH /users/me/bookmarks/nodes` — Node 즐겨찾기의 최종 상태.
 *
 *   changes: [{ nodeType, nodeId, bookmarked }]   →   { results: [{ nodeType, nodeId, bookmarked }] }
 *
 * `nodeId` 는 그래프 API 의 `nodeKey` 와 같은 값이다(이름만 다르다). EVENT·STORY·ENTITY·
 * STATEMENT 를 받고, 그 밖은 400 INVALID_NODE_TYPE.
 */
export async function updateNodeBookmarks(changes, { signal } = {}) {
  return request('/users/me/bookmarks/nodes', { method: 'PATCH', body: { changes }, signal })
}

/** 한 건짜리 편의 함수. 응답에서 그 항목의 확정 상태를 꺼내 돌려준다. */
export async function setArticleBookmark(articleId, bookmarked) {
  const payload = await updateArticleBookmarks([{ articleId, bookmarked }])
  return payload?.results?.find((r) => r.articleId === articleId)?.bookmarked ?? bookmarked
}

export async function setNodeBookmark(nodeType, nodeId, bookmarked) {
  const payload = await updateNodeBookmarks([{ nodeType, nodeId, bookmarked }])
  return payload?.results?.find((r) => r.nodeId === nodeId)?.bookmarked ?? bookmarked
}
