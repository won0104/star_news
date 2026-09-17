/**
 * Auth API boundary.
 *
 * 회원가입·로그인·아이디 중복확인은 실제 엔드포인트에 연결돼 있고, 계정 설정 쪽
 * (changeEmail / changePassword)은 아직 엔드포인트가 없어 목업으로 남아 있다.
 */

import { ApiError, request } from './client';

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

/**
 * `GET /auth/login-id/availability`.
 *
 * A malformed id answers 400 rather than `available: false`, and the form has already
 * checked the format by the time this runs — so a 400 here means the two rule sets have
 * drifted apart, and reporting "taken" would hide that. Only the server's own answer is
 * treated as an answer; anything else is thrown for the caller to surface.
 */
export async function checkIdAvailability(id) {
  const data = await request(`/auth/login-id/availability?loginId=${encodeURIComponent(id.trim())}`);
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

// eslint-disable-next-line no-unused-vars -- 엔드포인트가 아직 없다. 시그니처만 유지.
export async function changeEmail(next) {
  await wait(500);
}

/** `change` is `{ current, next }`. A real endpoint rejects a wrong `current`. */
// eslint-disable-next-line no-unused-vars -- 엔드포인트가 아직 없다. 시그니처만 유지.
export async function changePassword(change) {
  await wait(500);
}
