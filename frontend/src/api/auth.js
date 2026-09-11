/**
 * Auth API boundary. Everything here is a stand-in that resolves locally after a short
 * delay; swap the bodies for real requests when the backend exists — the screens only
 * depend on these signatures.
 */

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

/** Ids treated as already registered, so the duplicate check has something to reject. */
const TAKEN_IDS = new Set(['admin', 'test', 'news', 'byeolbit']);
export async function checkIdAvailability(id) {
  await wait(450);
  return !TAKEN_IDS.has(id.trim().toLowerCase());
}
// eslint-disable-next-line no-unused-vars -- signature kept for the real request that replaces this stub
export async function signIn(credentials) {
  await wait(500);
}
// eslint-disable-next-line no-unused-vars -- signature kept for the real request that replaces this stub
export async function signUp(account) {
  await wait(600);
}
// eslint-disable-next-line no-unused-vars -- signature kept for the real request that replaces this stub
export async function changeEmail(next) {
  await wait(500);
}

/** `change` is `{ current, next }`. A real endpoint rejects a wrong `current`. */
// eslint-disable-next-line no-unused-vars -- signature kept for the real request that replaces this stub
export async function changePassword(change) {
  await wait(500);
}
