import { useLayoutEffect, useState } from 'react'

/**
 * Picks the window frame drawn closest to the shape of the box it will be drawn into.
 *
 * It measures the box rather than the viewport, and the two are not the same: the
 * desktop navigation rail takes 176–208px off the stage, so a 16:9 screen hands the
 * frame a 1.59 box. Choosing on the viewport would pick a frame the box then has to
 * stretch further to fill, and on some widths would pick the wrong one outright.
 *
 * Distance is measured on the log of the ratio, not on the difference, because what
 * the eye reads is how far the wood has been stretched — a factor, not an amount. On a
 * linear scale 1.0 would sit nearer 1.333 than 0.75 even though both are the same 33%
 * away, and the squat frame would be chosen for tall screens.
 *
 * Media queries are deliberately not used. Their breakpoints would be derived from the
 * frame list — the crossovers are its geometric means — so writing them out by hand
 * would be the same numbers kept in a second place, and they cannot see the rail at
 * all. This way the list in data/trend is the only place a ratio is written down.
 */
const nearestIndex = (frames, ratio) => {
  let best = 0
  let bestDistance = Infinity
  frames.forEach((frame, index) => {
    const distance = Math.abs(Math.log(ratio / frame.ratio))
    if (distance < bestDistance) {
      bestDistance = distance
      best = index
    }
  })
  return best
}

/**
 * The entry of `frames` nearest the measured ratio of `ref`'s element, or of the
 * viewport when no ref is given.
 *
 * Two layers that must agree on the same entry — a photograph and the things pinned to
 * it — should both omit the ref. Measuring the same viewport makes them agree by
 * construction rather than by staying in sync.
 *
 * Seeded from the viewport so the first paint is already close: a measured box is
 * narrower than the viewport, never wider, so the seed is at worst one entry out and is
 * corrected before the browser paints.
 */
export function useNearestWindow(frames, ref) {
  const [index, setIndex] = useState(() =>
    typeof window === 'undefined'
      ? 0
      : nearestIndex(frames, window.innerWidth / window.innerHeight),
  )

  useLayoutEffect(() => {
    const node = ref?.current ?? document.documentElement

    const measure = () => {
      const { width, height } = ref?.current
        ? node.getBoundingClientRect()
        : { width: window.innerWidth, height: window.innerHeight }
      if (!width || !height) return
      setIndex(nearestIndex(frames, width / height))
    }

    const observer = new ResizeObserver(measure)
    observer.observe(node)
    measure()
    return () => observer.disconnect()
  }, [frames, ref])

  return frames[index]
}
