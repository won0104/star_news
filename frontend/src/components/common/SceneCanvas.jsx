import { SCENE_HEIGHT, SCENE_SAFE_INSET, SCENE_WIDTH } from '../../data/scene';
import { useSceneScale } from '../../hooks/useSceneScale';
import { Backdrop } from './Backdrop';
import styles from './SceneCanvas.module.css';

/**
 * Fixed 1672x941 stage, scaled to fill the viewport. Shared by every scene.
 *
 * The room photo is deliberately *outside* the scaled canvas: it is a wall, with no
 * alignment relationship to the cards, so letting it cover the viewport on its own
 * removes the letterbox bars without stretching the composition. Only the yarn, cards
 * and chrome — which do depend on each other's coordinates — ride the canvas.
 *
 * `topChrome` is the height of a bar drawn above the stage. It both shrinks the height
 * the scale is fitted to and pads the box the canvas centres in, so the composition
 * clears the bar instead of sliding under it. The room still covers the full viewport,
 * bar included — <Backdrop> is absolute against the padding box, not the content box.
 *
 * `railWidth` draws a frosted panel from the viewport's left edge out to that design-px
 * column. It has to be drawn here rather than inside the scene, because the canvas is
 * only scaled until it covers the viewport on its limiting axis: at portrait-ish ratios
 * (roughly width < 1.72 x usable height, which includes 1280x900) it is letterboxed, and
 * a panel clipped to it would float as an island instead of running edge to edge. So the
 * panel sits outside the canvas and its width is computed back from the same numbers the
 * transform uses — the canvas centres in this padding box, so its left edge lands at
 * (100% - SCENE_WIDTH * scale) / 2 + offsetX.
 *
 * `leftVeil` is handed straight to <Backdrop>; a scene drawing a rail wants less of that
 * wash, since the rail is what the copy now sits on.
 */
export function SceneCanvas({
  backdrop,
  topChrome = 0,
  railWidth = 0,
  leftVeil = 1,
  children,
}) {
  const { scale, offsetX, offsetY } = useSceneScale(
    SCENE_WIDTH,
    SCENE_HEIGHT,
    SCENE_SAFE_INSET,
    topChrome,
  );

  return (
    <div className={styles.viewport} style={topChrome ? { paddingTop: topChrome } : undefined}>
      <Backdrop src={backdrop} leftVeil={leftVeil} />
      {railWidth > 0 && (
        <div
          className={styles.rail}
          style={{
            // An absolute child's containing block is the padding box, padding included,
            // so top:0 would put the rail behind the bar and stack the two tints.
            top: topChrome,
            width: `calc((100% - ${SCENE_WIDTH}px * ${scale}) / 2 + ${offsetX}px + ${railWidth}px * ${scale})`,
          }}
          aria-hidden
        />
      )}
      <div
        className={styles.canvas}
        style={{ transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})` }}
      >
        {children}
      </div>
    </div>
  );
}
