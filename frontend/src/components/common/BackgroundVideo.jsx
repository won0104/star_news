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
 * is what the screen settles on. The clip is not removed until that fade has actually
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
export function BackgroundVideo({ webm, mp4, playOnce = false, className = '' }) {
  const [ready, setReady] = useState(false);
  const [finished, setFinished] = useState(false);
  const [retired, setRetired] = useState(false);
  const prefersReducedMotion = usePrefersReducedMotion();

  // Rendering nothing means nothing is downloaded either — the still underneath stands in.
  if (prefersReducedMotion || retired) return null;

  return (
    <video
      className={`${styles.video} ${ready && !finished ? styles.videoReady : ''} ${className}`}
      autoPlay
      muted
      loop={!playOnce}
      playsInline
      preload="auto"
      disablePictureInPicture
      aria-hidden
      tabIndex={-1}
      onCanPlay={() => setReady(true)}
      onEnded={playOnce ? () => setFinished(true) : undefined}
      onTransitionEnd={(event) => {
        // Also fires for the fade in, hence the guard. If it never arrives the clip
        // just stays mounted at opacity 0, which costs nothing and shows nothing.
        if (finished && event.propertyName === 'opacity') setRetired(true);
      }}
    >
      {/* webm first — VP9 is about half the bytes of H.264 here. mp4 is the Safari fallback. */}
      <source src={webm} type="video/webm" />
      <source src={mp4} type="video/mp4" />
    </video>
  );
}
