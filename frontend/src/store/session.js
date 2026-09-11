import { useSyncExternalStore } from 'react';

/**
 * Who is signed in, for the whole app.
 *
 * A plain module store rather than a context, so screens read it with a hook and
 * nothing has to be wrapped in a provider — the same shape as useIsCompact and
 * usePrefersReducedMotion, which is how this codebase already reads shared state.
 *
 * In memory only, deliberately: api/auth.js `signIn` is still a stub that resolves with
 * nothing, so there is no token to keep and a reload signs you out. When the real
 * endpoint lands, persist what it returns and rehydrate `account` here on module load —
 * that is the only change this file needs, and every screen keeps working unchanged.
 */
let account = null;
const listeners = new Set();

const subscribe = (onChange) => {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
};

const getSnapshot = () => account;

const notify = () => listeners.forEach((listener) => listener());

/** `next` is what the sign-in screens know about the user — `{ id }` for now. */
export function startSession(next) {
  account = next;
  notify();
}

export function endSession() {
  account = null;
  notify();
}

/** The signed-in account, or null when nobody is. */
export function useSession() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
