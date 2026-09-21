import { useSyncExternalStore } from 'react';

/**
 * Who is signed in, for the whole app.
 *
 * A plain module store rather than a context, so screens read it with a hook and
 * nothing has to be wrapped in a provider — the same shape as useIsCompact and
 * usePrefersReducedMotion, which is how this codebase already reads shared state.
 *
 * Account data and the access token stay in memory. The refresh token lives in an
 * HttpOnly cookie the page cannot read; App calls `POST /auth/refresh` on boot. The
 * refresh response does not include user details, so the account mark uses a generic
 * label after a reload. Cross-tab logout sends only a notification marker.
 */
let account = null;
let sessionRevision = 0;
const listeners = new Set();
const LOGOUT_CHANNEL = 'starlight-session';
const LOGOUT_STORAGE_KEY = 'starlight-session-logout';
let lastRemoteLogoutId = null;

// No token or user data crosses tabs. The storage event covers browsers that do not
// support BroadcastChannel; its value is only a changing notification marker.
const logoutChannel =
  typeof window !== 'undefined' && typeof window.BroadcastChannel === 'function'
    ? new window.BroadcastChannel(LOGOUT_CHANNEL)
    : null;

function handleRemoteLogout(id) {
  if (!id || id === lastRemoteLogoutId) return;
  lastRemoteLogoutId = id;
  const wasSignedIn = !!account;
  endSession({ broadcast: false });
  if (wasSignedIn) window.location.replace('/');
}

if (typeof window !== 'undefined') {
  logoutChannel?.addEventListener('message', (event) => {
    if (event.data?.type === 'logout') handleRemoteLogout(event.data.id);
  });
  window.addEventListener('storage', (event) => {
    if (event.key === LOGOUT_STORAGE_KEY) handleRemoteLogout(event.newValue);
  });
}

function notifyOtherTabs() {
  if (typeof window === 'undefined') return;
  const id = `${Date.now()}-${Math.random()}`;
  try {
    logoutChannel?.postMessage({ type: 'logout', id });
  } catch {
    // The storage event remains available if the channel cannot send.
  }
  try {
    window.localStorage.setItem(LOGOUT_STORAGE_KEY, id);
  } catch {
    // BroadcastChannel still delivers the logout when storage is unavailable.
  }
}

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
  endSession({ broadcast: false });
  return true;
}

/** Explicit logout and account withdrawal also clear already-open tabs. */
export function endSession({ broadcast = true } = {}) {
  const wasSignedIn = !!account;
  sessionRevision += 1;
  account = null;
  notify();
  if (broadcast && wasSignedIn) notifyOtherTabs();
}

/** The signed-in account, or null when nobody is. */
export function useSession() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
