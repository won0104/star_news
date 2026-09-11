import { useEffect, useState } from 'react';

const NO_INSET = { top: 0, right: 0, bottom: 0, left: 0 };

/**
 * Illustrated scenes are laid out on a fixed design canvas, so instead of reflowing
 * them we scale the whole canvas to fit its slot. Fitting strictly inside leaves dark
 * bars on every viewport whose aspect ratio is not the canvas', so the scale is allowed
 * to grow until the safe margin around the composition — and nothing else — falls
 * outside. Centring would take an equal bite out of opposite edges, so the returned
 * offset re-weights the crop by the margin each edge actually has to give.
 *
 * `offsetY` reserves room for chrome that lives outside the canvas, e.g. a top bar.
 */
export function useSceneScale(designWidth, designHeight, safeInset = NO_INSET, offsetY = 0) {
  const [fit, setFit] = useState({ scale: 1, offsetX: 0, offsetY: 0 });
  const { top, right, bottom, left } = safeInset;

  useEffect(() => {
    const measure = () => {
      const viewWidth = window.innerWidth;
      const viewHeight = window.innerHeight - offsetY;
      const cropX = left + right;
      const cropY = top + bottom;

      // Largest scale that spends no more than the crop budget on either axis. This is
      // never smaller than fitting strictly inside, and only the limiting axis crops.
      const scale = Math.min(viewWidth / (designWidth - cropX), viewHeight / (designHeight - cropY));

      const overX = Math.max(0, designWidth - viewWidth / scale);
      const overY = Math.max(0, designHeight - viewHeight / scale);

      setFit({
        scale,
        offsetX: cropX ? overX * (0.5 - left / cropX) * scale : 0,
        offsetY: cropY ? overY * (0.5 - top / cropY) * scale : 0,
      });
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [designWidth, designHeight, top, right, bottom, left, offsetY]);

  return fit;
}
