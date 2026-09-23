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

/**
 * 새로고침 뒤 뒤늦게 알아낸 사용자 정보를 지금 세션에 붙인다.
 *
 * `POST /auth/refresh` 는 토큰만 주므로 부팅 직후의 세션에는 `user` 가 없다. 뒤이어 부른
 * `GET /users/me` 의 결과가 여기로 온다. revision 을 올리지 않는 것이 중요하다 — 올리면
 * 그 사이 날아간 요청들이 세션이 바뀐 것으로 보고 스스로를 취소한다.
 *
 * 기다리는 동안 로그아웃하거나 다시 로그인했으면 늦게 온 정보는 버린다.
 */
export function attachUser(expectedToken, user) {
  if (!account || account.accessToken !== expectedToken) return false;
  account = { ...account, user };
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
