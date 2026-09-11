import { useSyncExternalStore } from 'react';

/**
 * Narrow enough that a layout authored across a wide screen stops fitting sideways.
 *
 * Separate from COMPACT_QUERY in useIsCompact, and deliberately: that one asks whether a
 * fixed illustrated canvas is still worth scaling, and it fires on short windows as well
 * as narrow ones. This one is about width alone — what breaks here is things placed side
 * by side running into each other, which a short wide window does not do.
 *
 * 900px is where it starts for the constellation, and the number is arithmetic rather
 * than taste: its two statement stars sit at 37% and 64% of the field, so the gap between
 * their label centres is 0.27 of the viewport, and their labels are 240px wide. They
 * touch at 889px. Measured at 820px they overlapped by 18px, which is what corrected an
 * earlier guess of 700 here.
 *
 * The same 900 as COMPACT_QUERY's width clause, by coincidence rather than by sharing:
 * that query also fires on short windows, which is wrong for a decision about width.
 * TrendConstellation.module.css mirrors this number — change one and change the other.
 */
export const NARROW_QUERY = '(max-width: 900px)';

/** Created on first use so the module stays importable before the DOM exists. */
let query;
const media = () => (query ??= window.matchMedia(NARROW_QUERY));

const subscribe = (onChange) => {
  const list = media();
  list.addEventListener('change', onChange);
  return () => list.removeEventListener('change', onChange);
};

const getSnapshot = () => media().matches;

/** True while the viewport is too narrow for a side-by-side layout. */
export function useIsNarrow() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
