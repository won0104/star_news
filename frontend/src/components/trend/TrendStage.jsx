import { useState } from 'react';
import { nightfall } from '../../data/trend';
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion';
import { useSettingsValues } from '../../store/settings';
import { SCREEN_TRANSITIONS } from '../../utils/motion';
import { BackgroundVideo } from '../common/BackgroundVideo';
import { TrendSky } from './TrendSky';
import styles from './TrendStage.module.css';

/**
 * 주요 트렌드 — the attic going dark, once, and then the constellation on the still it
 * settles on.
 *
 * The clip is the screen changing state, not an intro: it hands over to the still, and
 * the stars are drawn on the still, so they wait for the hand-over rather than competing
 * with ten seconds of moving light. `settled` is that moment.
 *
 * Two ways to be settled, and both are needed. The clip reaching its end is the ordinary
 * one. The other is nobody having asked for a clip — the 애니메이션 없애기 setting, or the
 * OS's own reduced-motion preference — and it has to be decided out here: <BackgroundVideo>
 * renders nothing under reduced motion, so waiting for its `onEnded` would leave the
 * screen a bare wall with no stars on it, forever.
 *
 * The still carries the screen and the clip plays over it, which is why the still is
 * mounted from the start rather than swapped in on `ended`.
 *
 * `fadeMs` is double <BackgroundVideo>'s default 700ms because this join is a step, not a
 * match. Home's clip ends on its own still (34.8dB, once corrected) and can cut quickly;
 * this one does not — measured in the stage box, the clip's last frame is mean 29,26,28
 * against the still's 70,65,67, so the screen lifts about 2.5x however it is handled
 * (per-channel 2.8/2.6/2.3, and 14.8dB against that still). Over 1.4s that reads as the
 * room settling; at 700ms it read as a flash.
 *
 * Those figures survived the clip being replaced: the 3.3s 1080p render ends on the same
 * near-black as the 10s one it took over from, so the correction here did not have to
 * move. Its tail is a smooth fade — 116, 94, 75, 56, 40, 31 over the last three quarters
 * of a second — with no cut in it. An all-black sample at 2.9s on the first pass was an
 * undecoded frame, not a frame: seeking fires `seeked` before the decoder has produced
 * the picture, so anything measuring frames here has to wait for one.
 */
export function TrendStage({ playTransition = false }) {
  const [ready, setReady] = useState(false);
  const [ended, setEnded] = useState(false);
  const { reduceMotion } = useSettingsValues();
  const prefersReducedMotion = usePrefersReducedMotion();

  const still = !SCREEN_TRANSITIONS || !playTransition || reduceMotion || prefersReducedMotion;
  const settled = still || ended;

  return (
    <div className={styles.stage}>
      <img
        className={`${styles.still} ${ready ? styles.stillReady : ''}`}
        src={nightfall.still}
        alt=""
        aria-hidden
        onLoad={() => setReady(true)}
      />

      {!still && (
        <BackgroundVideo
          mp4={nightfall.clip.mp4}
          playOnce
          fadeMs={1400}
          onEnded={() => setEnded(true)}
          className={styles.clip}
        />
      )}

      {settled && <TrendSky />}
    </div>
  );
}
