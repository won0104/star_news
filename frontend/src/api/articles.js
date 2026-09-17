/**
 * 기사 한 건.
 *
 * 아직 배포 전이다 — 배포 스펙의 articles 경로는 `POST /articles/{id}/reads` 하나뿐이라,
 * 이 요청은 붙는 순간부터 동작하도록 미리 맞춰둔 것이다. 형태는 백엔드가 알려준 응답 그대로.
 *
 *   { articleId, title, organizationName, publishedAt,
 *     summary,            요약. 없으면 null
 *     summaryStatus,      COMPLETED | NOT_REQUESTED | PROCESSING | FAILED
 *     originalUrl,        원문 주소
 *     bookmarked }        비로그인이면 false
 *
 * `summary` 와 `summaryStatus` 는 짝이다 — 요약이 null 인 이유가 "아직 요청하지 않아서"인지
 * "만들다 실패해서"인지에 따라 화면이 할 말이 다르므로, null 만 보고 판단하지 않는다.
 */

import { request } from './client'

export async function fetchArticleDetail(articleId, { signal } = {}) {
  return request(`/articles/${encodeURIComponent(articleId)}`, { signal })
}

/** 열람 기록. 기사 상세로 들어간 시점에 한 번 보낸다. 로그인 상태에서만 의미가 있다. */
export async function recordArticleRead(articleId, { signal } = {}) {
  return request(`/articles/${encodeURIComponent(articleId)}/reads`, {
    method: 'POST',
    signal,
  })
}
