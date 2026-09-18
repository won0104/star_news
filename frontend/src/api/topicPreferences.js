/**
 * 관심 · 비관심 분야.
 *
 * 넷 다 Access Token 이 필요하다. 비로그인이면 401 UNAUTHORIZED — 화면은 그것을 오류가
 * 아니라 "로그인하면 설정할 수 있다"로 읽는다.
 *
 * 응답·요청 형태는 Java DTO 그대로다.
 *
 *   조회  TopicPreferenceResponse      { topicCodes: ['POLITICS', 'ECONOMY', …] }
 *         설정한 것이 없으면 빈 배열(200).
 *   변경  UpdateTopicPreferenceRequest { topicCodes: [...] }
 *         **최종 목록으로 통째로 교체**한다. 하나를 켜고 끌 때도 전체를 다시 보낸다.
 *         빈 배열을 보내면 전부 해제. 모르는 코드는 400 INVALID_TOPIC, 중복은 DUPLICATED_TOPIC.
 *
 * 코드는 백엔드 TopicCode enum 의 일곱 개 — data/topics.js 의 TOPICS 와 같다.
 * (국제는 INTERNATIONAL 이다. WORLD 가 아니다.)
 */

import { request } from './client'

export async function fetchInterests({ signal } = {}) {
  return request('/users/me/topic-preferences/interests', { signal })
}

export async function fetchDislikes({ signal } = {}) {
  return request('/users/me/topic-preferences/dislikes', { signal })
}

/** `topicCodes` 가 저장 뒤의 최종 관심 목록이 된다. */
export async function updateInterests(topicCodes, { signal } = {}) {
  return request('/users/me/topic-preferences/interests', {
    method: 'PUT',
    body: { topicCodes },
    signal,
  })
}

/** `topicCodes` 가 저장 뒤의 최종 비관심 목록이 된다. */
export async function updateDislikes(topicCodes, { signal } = {}) {
  return request('/users/me/topic-preferences/dislikes', {
    method: 'PUT',
    body: { topicCodes },
    signal,
  })
}
