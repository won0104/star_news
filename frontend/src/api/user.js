/**
 * 계정 자체에 대한 요청. 지금은 탈퇴 하나다.
 *
 * `DELETE /users/me` — 현재 로그인한 계정을 비활성화한다(soft delete). Access Token 과
 * **비밀번호 재확인**이 함께 필요하다. 성공하면 200 에 data: null, 그리고 서버가 refresh
 * 쿠키를 만료시킨다 — 그 뒤 화면이 할 일은 세션을 버리고 첫 화면으로 돌아가는 것뿐이다.
 *
 * 실패는 code 로 가른다(message 는 사람에게 보여줄 문장이라 바뀔 수 있다).
 *   INVALID_INPUT_VALUE  비밀번호 누락 (400)
 *   INVALID_CREDENTIALS  비밀번호 불일치 (401) — 다시 입력받는다
 *   USER_DELETED         이미 탈퇴한 계정 (403) — 세션을 버리고 끝낸다
 *   UNAUTHORIZED / EXPIRED_ACCESS_TOKEN  토큰 문제 (401) — 다시 로그인
 */

import { request } from './client';

/**
 * `GET /users/me` — 로그인한 사용자의 기본 정보와 관심·비관심 Topic.
 *
 * 새로고침 뒤에 누구인지 되찾는 용도다. 부팅 때 부르는 `POST /auth/refresh` 는 토큰만
 * 돌려주고 `user` 를 담지 않아서, 그것만으로는 화면이 이름을 모른 채 로그인 상태가 된다.
 *
 * `{ userId, loginId, nickname, interestedTopicCodes[], dislikedTopicCodes[] }`
 */
export async function fetchMyProfile({ signal } = {}) {
  return request('/users/me', { signal });
}

export async function withdrawAccount(password) {
  return request('/users/me', { method: 'DELETE', body: { password } });
}
