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
