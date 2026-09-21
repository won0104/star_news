/**
 * Auth API boundary.
 *
 * 회원가입·로그인·아이디 중복확인·로그아웃 — 전부 배포 엔드포인트에 연결돼 있다.
 * 회원 정보 변경(이메일·비밀번호)은 API 에 없어 여기에도 없다. 생기면 그때 붙인다.
 */

import { ApiError, request } from './client';

/**
 * `GET /auth/login-id/availability`.
 *
 * A malformed id answers 400 rather than `available: false`, and the form has already
 * checked the format by the time this runs — so a 400 here means the two rule sets have
 * drifted apart, and reporting "taken" would hide that. Only the server's own answer is
 * treated as an answer; anything else is thrown for the caller to surface.
 */
export async function checkIdAvailability(id) {
  const data = await request(`/auth/login-id/availability?loginId=${encodeURIComponent(id.trim())}`, { skipAuth: true });
  return data.available;
}

/**
 * `POST /auth/login`. Returns `{ accessToken, tokenType, expiresIn, user }`; the refresh
 * token is set as an HttpOnly cookie by the response and is never visible here.
 */
export async function signIn({ id, password }) {
  return request('/auth/login', {
    method: 'POST',
    body: { loginId: id.trim(), password },
    skipAuth: true,
  });
}

/**
 * `POST /auth/signup`, then a login.
 *
 * Signing up answers 201 with the new account but no token, so a second call is what
 * actually starts the session. They are together in one function because a caller has
 * no use for an account it cannot yet act as — and if the login is the half that fails,
 * the account still exists, so the error says to sign in rather than to try again.
 */
export async function signUp({ id, nickname, password }) {
  await request('/auth/signup', {
    method: 'POST',
    body: { loginId: id.trim(), nickname: nickname.trim(), password },
    skipAuth: true,
  });

  try {
    return await signIn({ id, password });
  } catch {
    throw new ApiError({
      status: 0,
      code: 'SIGNUP_LOGIN_FAILED',
      message: '가입은 완료됐습니다. 로그인 화면에서 로그인해 주세요.',
    });
  }
}

/** `POST /auth/logout`. Clears the refresh cookie; answers 204. */
export async function signOut() {
  return request('/auth/logout', { method: 'POST' });
}
