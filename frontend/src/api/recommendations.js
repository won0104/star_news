/**
 * 나를 위한 추천.
 *
 * 둘 다 Access Token 이 필요하다. 비로그인이면 401 UNAUTHORIZED — 화면은 그것을 오류가
 * 아니라 "로그인하면 볼 수 있다"로 읽는다.
 *
 * 응답 형태는 Java DTO 그대로다(Swagger 가 아니라).
 *
 *   보드   RecommendationBoardResponse
 *          { cycle: 'AM' | 'PM' | null,
 *            generatedAt, availableAt,          공개된 회차가 없으면 셋 다 null
 *            items: [{ userRecommendationId, eventId, label, topicCode, score, rank,
 *                      recommendationType, reason }] }
 *
 *          한 회차 전부가 한 번에 온다(페이지 없음). 서버 설정상 사용자당 최대 10개.
 *          회차가 없으면 items 가 빈 배열이고 200 이다 — 실패가 아니라 상태다.
 *
 *   상세   RecommendationDetailResponse
 *          { userRecommendationId, eventId, label, topicCode,
 *            contextSummary,                    요약. 아직 없거나 실패했으면 null
 *            articles: [{ articleId, title, organizationName, publishedAt, topicCode,
 *                         originalUrl }] }
 *
 *          `contextSummary` 는 공개 시각까지 만들어지지 않을 수 있다. null 을 정상으로 다룬다.
 *          상세 링크의 키는 eventId 가 아니라 userRecommendationId 다.
 */

import { request } from './client'

/** `GET /recommendations` — 공개된 최신 회차, 순위 순. */
export async function fetchRecommendationBoard({ signal } = {}) {
  return request('/recommendations', { signal })
}

/** `GET /recommendations/{userRecommendationId}` — 카드 하나의 Event 요약과 기사. */
export async function fetchRecommendationDetail(userRecommendationId, { signal } = {}) {
  return request(`/recommendations/${encodeURIComponent(userRecommendationId)}`, { signal })
}
