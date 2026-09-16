import { useSyncExternalStore } from 'react';

/**
 * Who is signed in, for the whole app.
 *
 * A plain module store rather than a context, so screens read it with a hook and
 * nothing has to be wrapped in a provider — the same shape as useIsCompact and
 * usePrefersReducedMotion, which is how this codebase already reads shared state.
 *
 * In memory only, deliberately. The refresh token lives in an HttpOnly cookie the page
 * cannot read, so a reload signs you out here while the cookie survives — the fix is to
 * call `POST /auth/refresh` on boot and start a session from what it returns, not to
 * copy the access token into storage where a script could read it.
 */
let account = null;
const listeners = new Set();

const subscribe = (onChange) => {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
};

const getSnapshot = () => account;

const notify = () => listeners.forEach((listener) => listener());

/**
 * `next` is the login response: `{ accessToken, tokenType, expiresIn, user }`. Stored
 * whole so the access token is reachable for the Authorization header without a second
 * place to keep it in sync.
 */
export function startSession(next) {
  account = next;
  notify();
}

/** The access token for the Authorization header, or null when nobody is signed in. */
export function getAccessToken() {
  return account?.accessToken ?? null;
}

export function endSession() {
  account = null;
  notify();
}

/** The signed-in account, or null when nobody is. */
export function useSession() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
