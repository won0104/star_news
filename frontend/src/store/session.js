import { useSyncExternalStore } from 'react';

/**
 * Who is signed in, for the whole app.
 *
 * A plain module store rather than a context, so screens read it with a hook and
 * nothing has to be wrapped in a provider — the same shape as useIsCompact and
 * usePrefersReducedMotion, which is how this codebase already reads shared state.
 *
 * In memory only, deliberately. The refresh token lives in an HttpOnly cookie the page
 * cannot read; App calls `POST /auth/refresh` on boot. The refresh response does not
 * include user details, so the account mark uses a generic label after a reload.
 */
let account = null;
let sessionRevision = 0;
const listeners = new Set();

const subscribe = (onChange) => {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
};

const getSnapshot = () => account;

const notify = () => listeners.forEach((listener) => listener());

/**
 * `next` is the login or refresh response. The login response also has `user`;
 * both contain the access token used for the Authorization header.
 */
export function startSession(next) {
  sessionRevision += 1;
  account = next;
  notify();
}

/** The access token for the Authorization header, or null when nobody is signed in. */
export function getAccessToken() {
  return account?.accessToken ?? null;
}

export function getSessionRevision() {
  return sessionRevision;
}

/** Ignore a late refresh result if the signed-in session changed while it was pending. */
export function replaceAccessToken(expectedToken, next) {
  if (!account || account.accessToken !== expectedToken) return false;
  account = { ...account, ...next };
  notify();
  return true;
}

export function endSessionIfToken(expectedToken) {
  if (!account || account.accessToken !== expectedToken) return false;
  endSession();
  return true;
}

export function endSession() {
  sessionRevision += 1;
  account = null;
  notify();
}

/** The signed-in account, or null when nobody is. */
export function useSession() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
