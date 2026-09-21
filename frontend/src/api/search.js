import { request } from './client'

/**
 * `GET /search` — Event, Entity, Statement Node를 한 번에 검색한다.
 *
 * `{ items: [{ nodeType, nodeKey, label }], hasNext, nextCursor }`
 */
export async function searchNodes(queryText, { size, cursor, signal } = {}) {
  const query = new URLSearchParams({ query: queryText })
  if (size != null) query.set('size', String(size))
  if (cursor) query.set('cursor', cursor)
  return request(`/search?${query}`, { signal, skipAuth: true })
}
