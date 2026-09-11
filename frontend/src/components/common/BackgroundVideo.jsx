import { useState } from 'react';
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion';
import styles from './BackgroundVideo.module.css';

/**
 * A silent clip played behind a screen. Decoration only, so it stays out of the
 * accessibility tree and never takes focus, and it fades in rather than appearing:
 * whatever is painted underneath shows until the first frame is decoded, and keeps
 * showing for good if the file never arrives or the codec is refused.
 *
 * `playOnce` runs it a single time and then fades it back off, so the still underneath
 * is what the screen settles on, and `fadeMs` sets how long that takes — worth raising
 * when the clip's last frame and the still are not the same picture. `onEnded` fires at
 * that moment, for a caller with something to do once the screen stops moving.
 *
 * `hold` keeps the clip on screen at its final frame instead of fading off, which is
 * for the case where there is no still that matches where the clip lands: the landing
 * is then seamless by construction, at the cost of a decoded frame the browser has to
 * keep. A still is lighter and sharper, so this is the second choice, not the first.
 *
 * A caller that has to know whether the clip will play at all should not ask this
 * component: with reduced motion it renders nothing and `onEnded` never comes, so the
 * decision belongs on the outside, where it can be made before the clip is mounted. The clip is not removed until that fade has actually
 * finished — unmounting on `ended` would cut to the still instead of crossing to it.
 * Worth knowing: the still is usually the better picture of the two, since it is not
 * limited to the clip's resolution, so settling on it is a gain and not a fallback.
 *
 * autoPlay + muted + playsInline are one unit. Without `muted` the browser's autoplay
 * policy blocks it; without `playsInline` iOS Safari takes the video fullscreen. Drop
 * either and this stops being a background.
 *
 * Sizing belongs to the caller — give the parent a box.
 */
export function BackgroundVideo({
  webm,
  mp4,
  playOnce = false,
  hold = false,
  fadeMs,
  onEnded,
  className = '',
}) {
  const [ready, setReady] = useState(false);
  const [finished, setFinished] = useState(false);
  const [retired, setRetired] = useState(false);
  const prefersReducedMotion = usePrefersReducedMotion();

  // Rendering nothing means nothing is downloaded either — the still underneath stands in.
  if (prefersReducedMotion || retired) return null;

  return (
    <video
      className={`${styles.video} ${ready && !finished ? styles.videoReady : ''} ${className}`}
      // Inline, because .video sets `transition` as a shorthand: a `transition-duration`
      // longhand from the caller's own module has the same specificity and loses or wins
      // on stylesheet order, which is not something a caller should have to reason about.
      style={fadeMs ? { transitionDuration: `${fadeMs}ms` } : undefined}
      autoPlay
      muted
      loop={!playOnce}
      playsInline
      preload="auto"
      disablePictureInPicture
      aria-hidden
      tabIndex={-1}
      onCanPlay={() => setReady(true)}
      onEnded={
        playOnce
          ? () => {
              // Held clips never set `finished`, which is what keeps them mounted and
              // opaque: the fade-out and the retire both hang off that flag.
              if (!hold) setFinished(true);
              onEnded?.();
            }
          : onEnded
      }
      onTransitionEnd={(event) => {
        // Also fires for the fade in, hence the guard. If it never arrives the clip
        // just stays mounted at opacity 0, which costs nothing and shows nothing.
        if (finished && event.propertyName === 'opacity') setRetired(true);
      }}
    >
      {/* webm first — VP9 is about half the bytes of H.264 here. mp4 is the Safari
          fallback. Guarded because a <source> with no src is not skipped politely by
          every browser, and only home has a VP9 pair — the trend clip is mp4 only. */}
      {webm && <source src={webm} type="video/webm" />}
      <source src={mp4} type="video/mp4" />
    </video>
  );
}
