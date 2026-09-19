import { useSyncExternalStore } from 'react';

/**
 * The settings overlay: which pane is open, and what its controls currently say.
 *
 * Same module-store shape as store/session.js, for the same reason — the overlay is
 * mounted once in App and opened from the top bar's account menu, two places with no
 * component tree in common, and a store reaches both without a provider.
 *
 * `values` holds the display preferences only — theme, text size, reduced motion. They are
 * per page load and, since the 화면 설정 pane was removed, nothing changes them at runtime;
 * the screens that read `reduceMotion` keep working on the default. Topic preferences do
 * not live here any more: 관심 관리 reads and writes them through the API directly
 * (api/topicPreferences.js), so the server is the only copy and a reload cannot disagree
 * with it.
 */
let section = null;

let values = {
  theme: 'light',
  textSize: 'default',
  reduceMotion: false,
};

const listeners = new Set();
const notify = () => listeners.forEach((listener) => listener());

const subscribe = (onChange) => {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
};

/** Opens the overlay on `id`, or moves to that pane if it is already open. */
export function openSettings(id) {
  section = id;
  notify();
}

export function closeSettings() {
  section = null;
  notify();
}

/** For the display pane's three plain values. */
export function setSetting(key, value) {
  values = { ...values, [key]: value };
  notify();
}

/** The open pane's id, or null when the overlay is closed. */
export function useSettingsSection() {
  return useSyncExternalStore(subscribe, () => section);
}

export function useSettingsValues() {
  return useSyncExternalStore(subscribe, () => values);
}
