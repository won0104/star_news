import { useEffect, useState } from 'react';

/**
 * Illustrated scenes are laid out on a fixed design canvas, so instead of reflowing
 * them we scale the whole canvas to fit its slot (letterboxed, never cropped).
 * `offsetY` reserves room for chrome that lives outside the canvas, e.g. the top bar.
 */
export function useSceneScale(designWidth, designHeight, offsetY = 0) {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const fit = () => setScale(Math.min(window.innerWidth / designWidth, (window.innerHeight - offsetY) / designHeight));
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [designWidth, designHeight, offsetY]);
  return scale;
}
