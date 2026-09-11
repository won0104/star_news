import { useSyncExternalStore } from 'react';

/**
 * The settings overlay: which pane is open, and what its controls currently say.
 *
 * Same module-store shape as store/session.js, for the same reason — the overlay is
 * mounted once in App and opened from the top bar's account menu, two places with no
 * component tree in common, and a store reaches both without a provider.
 *
 * The values live here rather than in the overlay's state so a pane remembers what you
 * set after you close it. Still only for this page load: nothing is sent anywhere yet,
 * so a reload starts over, and the counts and article tallies below are seed data
 * standing in for what the graph will report. When there is an endpoint, load into
 * `values` on boot and push on change — the panes read and write through the functions
 * at the bottom and will not need to change.
 */
let section = null;

let values = {
  theme: 'light',
  textSize: 'default',
  reduceMotion: false,
  topics: ['politics', 'economy', 'tech'],
  dislikes: [
    { id: 'sports', label: '스포츠' },
    { id: 'entertainment', label: '연예' },
  ],
  nodes: [
    { id: 'court', label: '헌법재판소', kind: 'organisation', articles: 12, concepts: 8 },
    { id: 'inflation', label: '인플레이션', kind: 'concept', articles: 9, concepts: 6 },
    { id: 'semiconductor', label: '반도체', kind: 'concept', articles: 7, concepts: 5 },
    { id: 'bok', label: '한국은행', kind: 'organisation', articles: 5, concepts: 4 },
    { id: 'jejuair', label: '제주항공', kind: 'company', articles: 4, concepts: 3 },
  ],
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

export function toggleTopic(id) {
  const kept = values.topics.filter((topic) => topic !== id);
  values = {
    ...values,
    topics: kept.length === values.topics.length ? [...values.topics, id] : kept,
  };
  notify();
}

/** A keyword typed in, or taken from the suggestions. Ignores blanks and duplicates. */
export function addNode(label) {
  const trimmed = label.trim();
  if (!trimmed) return;
  if (values.nodes.some((node) => node.label === trimmed)) return;
  values = {
    ...values,
    // Nothing has read this keyword's graph yet, so it starts with no tallies. `concept`
    // is the safe default kind until the backend can say what it actually is.
    nodes: [...values.nodes, { id: trimmed, label: trimmed, kind: 'concept', articles: 0, concepts: 0 }],
  };
  notify();
}

/** 관심 없음 항목. Same guards as addNode: no blanks, no duplicates. */
export function addDislike(label) {
  const trimmed = label.trim();
  if (!trimmed) return;
  if (values.dislikes.some((item) => item.label === trimmed)) return;
  values = { ...values, dislikes: [...values.dislikes, { id: trimmed, label: trimmed }] };
  notify();
}

export function removeDislike(id) {
  values = { ...values, dislikes: values.dislikes.filter((item) => item.id !== id) };
  notify();
}

export function removeNode(id) {
  values = { ...values, nodes: values.nodes.filter((node) => node.id !== id) };
  notify();
}

/** The open pane's id, or null when the overlay is closed. */
export function useSettingsSection() {
  return useSyncExternalStore(subscribe, () => section);
}

export function useSettingsValues() {
  return useSyncExternalStore(subscribe, () => values);
}
