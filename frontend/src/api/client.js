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

/** A request that never reached the API — offline, DNS, the proxy being down. */
const NETWORK_ERROR = { status: 0, code: 'NETWORK_ERROR', message: '서버에 연결하지 못했습니다.' };

export async function request(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      signal,
      credentials: 'include',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
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
