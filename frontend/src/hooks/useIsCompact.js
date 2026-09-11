import { useSyncExternalStore } from 'react';

/**
 * The illustrated scenes are one fixed composition, so below a certain size there is
 * nothing left to scale into: the 8–13px annotation type stops being readable long
 * before the cards do. Under this query those screens render a reflowed layout
 * instead of the canvas. Raise the width to hand more viewports to the reflow.
 */
export const COMPACT_QUERY = '(max-width: 900px), (max-height: 560px)';

/** Created on first use so the module stays importable before the DOM exists. */
let query;
const media = () => (query ??= window.matchMedia(COMPACT_QUERY));

const subscribe = (onChange) => {
  const list = media();
  list.addEventListener('change', onChange);
  return () => list.removeEventListener('change', onChange);
};

const getSnapshot = () => media().matches;

/** True while the viewport is too small for the scene canvas to be worth scaling. */
export function useIsCompact() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

