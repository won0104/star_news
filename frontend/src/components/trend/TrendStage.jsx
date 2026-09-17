import { useState } from 'react';
import { nightfall } from '../../data/trend';
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion';
import { useSettingsValues } from '../../store/settings';
import { SCREEN_TRANSITIONS } from '../../utils/motion';
import { BackgroundVideo } from '../common/BackgroundVideo';
import { TrendSky } from './TrendSky';
import styles from './TrendStage.module.css';

/**
 * 주요 트렌드 — 밤 풍경을 담은 창과, 유리 안에서만 움직이는 별자리.
 *
 * Desktop and narrow screens use separately authored crops so `object-fit: cover` does
 * not throw the wooden frame away. <TrendSky> is clipped to the opening instead of the
 * whole photograph: the frame and plant therefore stay in the foreground even though
 * the photograph itself is one flat asset.
 *
 * A transition is optional. It only plays when an asset that ends on this exact still is
 * configured; otherwise the screen settles immediately instead of cross-fading between
 * unrelated rooms.
 */
export function TrendStage({ playTransition = false }) {
  const [ready, setReady] = useState(false);
  const [ended, setEnded] = useState(false);
  const { reduceMotion } = useSettingsValues();
  const prefersReducedMotion = usePrefersReducedMotion();

  const canPlayTransition = Boolean(
    nightfall.clip?.mp4 &&
      SCREEN_TRANSITIONS &&
      playTransition &&
      !reduceMotion &&
      !prefersReducedMotion,
  );
  const settled = !canPlayTransition || ended;

  return (
    <div className={styles.stage}>
      <div className={styles.sceneFrame}>
        <img
          className={styles.sidebarExtension}
          src={nightfall.sidebarStill}
          alt=""
          aria-hidden
        />

        <picture>
          <source
            media="(max-width: 900px) and (max-aspect-ratio: 2/3)"
            srcSet={nightfall.mobileStill}
          />
          <source media="(max-aspect-ratio: 1/1)" srcSet={nightfall.tabletStill} />
          <source media="(max-aspect-ratio: 4/3)" srcSet={nightfall.compactStill} />
          <img
            className={`${styles.still} ${ready ? styles.stillReady : ''}`}
            src={nightfall.still}
            alt=""
            aria-hidden
            onLoad={() => setReady(true)}
          />
        </picture>

        {canPlayTransition && (
          <BackgroundVideo
            mp4={nightfall.clip.mp4}
            playOnce
            fadeMs={1400}
            onEnded={() => setEnded(true)}
            className={styles.clip}
          />
        )}

        {settled && (
          <div className={styles.windowGlass}>
            <TrendSky />
          </div>
        )}
      </div>
    </div>
  );
}
