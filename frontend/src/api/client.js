/**
 * The one place a request is actually made.
 *
 * Every screen talks to the API through here so three things stay in one spot: the
 * `/api/v1` prefix (a relative path, proxied by the dev server — see vite.config.js),
 * `credentials: 'include'` for the HttpOnly refresh-token cookie, and the unwrapping of
 * the `{ data, meta }` envelope every success response is wrapped in.
 *
 * Failures are thrown as ApiError rather than returned, so a caller that does not care
 * why it failed can ignore the difference. Callers that do care branch on `code`, never
 * on `message`: the message is written for the reader and may change, while the code is
 * the contract (LOGIN_ID_ALREADY_EXISTS, INVALID_CREDENTIALS, …).
 */

import { endSessionIfToken, getAccessToken, getSessionRevision, replaceAccessToken } from '../store/session';

const BASE = '/api/v1';

export class ApiError extends Error {
  constructor({ status, code, message, requestId, errors }) {
    super(message ?? '요청을 처리하지 못했습니다.');
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.errors = errors ?? [];
  }
}

/**
 * The access token rides on every request that has one, so a screen never has to remember
 * to attach it. Public endpoints ignore the header, and a signed-out reader simply sends
 * none — which is how `/home` and the graph reads stay open to everyone.
 */
function authHeaders(body, token) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  return Object.keys(headers).length > 0 ? headers : undefined;
}

/** A request that never reached the API — offline, DNS, the proxy being down. */
const NETWORK_ERROR = { status: 0, code: 'NETWORK_ERROR', message: '서버에 연결하지 못했습니다.' };
const AUTH_RETRY_CODES = new Set(['EXPIRED_ACCESS_TOKEN', 'INVALID_ACCESS_TOKEN', 'UNAUTHORIZED']);

async function perform(path, { method, body, signal, token }) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      signal,
      credentials: 'include',
      headers: authHeaders(body, token),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    // An aborted request is the caller's own doing, not a failure to report as one.
    if (cause?.name === 'AbortError') throw cause;
    throw new ApiError(NETWORK_ERROR);
  }

  // 204 carries no envelope, by contract — logout and a few others answer this way.
  if (response.status === 204) return null;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      code: payload?.code,
      message: payload?.message,
      requestId: payload?.requestId,
      errors: payload?.errors,
    });
  }

  return payload?.data ?? null;
}

// The server rotates its refresh cookie on every call. Share one request among concurrent
// 401s in this tab so a second call cannot replay a token the first call just consumed.
let refreshInFlight = null;

export function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = perform('/auth/refresh', { method: 'POST', token: null })
      .then((data) => {
        if (typeof data?.accessToken !== 'string' || !data.accessToken) {
          throw new ApiError({ status: 502, code: 'INVALID_RESPONSE', message: '로그인을 복원하지 못했습니다.' });
        }
        return data;
      })
      .finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export async function request(path, { method = 'GET', body, signal, skipAuth = false } = {}) {
  const token = skipAuth ? null : getAccessToken();
  const revision = getSessionRevision();
  try {
    return await perform(path, { method, body, signal, token });
  } catch (error) {
    if (skipAuth || !token || !AUTH_RETRY_CODES.has(error?.code)) throw error;

    let fresh;
    try {
      fresh = await refreshAccessToken();
    } catch (refreshError) {
      if (refreshError?.status === 401) endSessionIfToken(token);
      throw refreshError;
    }

    if (getSessionRevision() !== revision) {
      throw new ApiError({ status: 401, code: 'UNAUTHORIZED', message: '로그인이 필요합니다.' });
    }
    replaceAccessToken(token, fresh);
    const currentToken = getAccessToken();
    if (!currentToken) {
      throw new ApiError({ status: 401, code: 'UNAUTHORIZED', message: '로그인이 필요합니다.' });
    }
    if (signal?.aborted) throw signal.reason ?? new DOMException('Aborted', 'AbortError');
    try {
      return await perform(path, { method, body, signal, token: currentToken });
    } catch (retryError) {
      if (retryError?.status === 401) endSessionIfToken(currentToken);
      throw retryError;
    }
  }
}
