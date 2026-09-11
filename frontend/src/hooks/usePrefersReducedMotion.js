import { useSyncExternalStore } from 'react';

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/** Created on first use so the module stays importable before the DOM exists. */
let query;
const media = () => (query ??= window.matchMedia(REDUCED_MOTION_QUERY));

const subscribe = (onChange) => {
  const list = media();
  list.addEventListener('change', onChange);
  return () => list.removeEventListener('change', onChange);
};

const getSnapshot = () => media().matches;

/**
 * Whether the OS asks for less motion (Windows: 설정 → 접근성 → 시각 효과 → 애니메이션 효과).
 * A background loop has no pause control, so it is exactly the kind of movement this
 * setting exists to stop — unstoppable motion is what triggers nausea for people with
 * a vestibular disorder. Flipping the setting re-renders immediately, without a reload.
 */
export function usePrefersReducedMotion() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
