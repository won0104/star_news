import { request } from './client'

/**
 * `GET /users/me/statistics/news-report` — 최근 3개월 사용자 뉴스 리포트.
 *
 * Access Token이 필요하며 공통 client가 토큰 첨부·갱신과 `{ data, meta }` 응답의
 * data 추출을 담당한다.
 *
 * `{ period, totalReadArticleCount, sourceReads, weeklyTopicTrend,
 *    topicLandscape, generatedAt }`
 */
export async function fetchNewsReport({ signal } = {}) {
  return request('/users/me/statistics/news-report', { signal })
}
