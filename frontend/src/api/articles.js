/**
 * 기사 한 건.
 *
 * 상세와 요약은 별개 요청이다. 2026-09-21 `be/fix: 기사 분석 및 요약 api 분리` 에서
 * 상세 응답의 `summary`·`summaryStatus` 가 빠지고 요약이 전용 경로로 옮겨갔다.
 * 상세는 이제 요약을 만들지도, 돌려주지도 않는다.
 *
 * GET /articles/{id} — 인증 선택
 *   { articleId, title, organizationName, publishedAt, originalUrl,
 *     bookmarked }        비로그인이면 false
 *
 * POST /articles/{id}/summary — 인증 선택
 *   { articleId, summary, summaryStatus }
 *   summaryStatus 는 PROCESSING | COMPLETED 둘뿐이다. 실패는 상태값이 아니라 에러로 온다 —
 *   422 ARTICLE_CONTENT_UNAVAILABLE(요약할 본문 없음), 502 SUMMARY_GENERATION_FAILED,
 *   500 SUMMARY_SAVE_FAILED. 그래서 `summaryStatus === 'FAILED'` 같은 분기는 없다.
 *
 * POST /articles/{id}/reads — Access Token 필요, 204
 */

import { request } from './client'

export async function fetchArticleDetail(articleId, { signal } = {}) {
  return request(`/articles/${encodeURIComponent(articleId)}`, { signal })
}

/**
 * 요약을 받아온다.
 *
 * 읽기 전용 경로가 없어서 POST 하나가 조회와 생성을 겸한다. 저장된 요약이 있으면 그대로
 * 돌려주고, 없을 때만 GMS 로 만든다. 다른 요청이 이미 만드는 중이면 GMS 를 다시 부르지 않고
 * `summary: null, summaryStatus: 'PROCESSING'` 으로 답하므로(HTTP 202), 같은 기사에 대해
 * 다시 물어도 생성이 중복되지 않는다 — PROCESSING 을 받았을 때 재시도해도 안전하다.
 */
export async function generateArticleSummary(articleId, { signal } = {}) {
  return request(`/articles/${encodeURIComponent(articleId)}/summary`, {
    method: 'POST',
    signal,
  })
}

/** 열람 기록. 기사 상세로 들어간 시점에 한 번 보낸다. 로그인 상태에서만 의미가 있다. */
export async function recordArticleRead(articleId, { signal } = {}) {
  return request(`/articles/${encodeURIComponent(articleId)}/reads`, {
    method: 'POST',
    signal,
  })
}
