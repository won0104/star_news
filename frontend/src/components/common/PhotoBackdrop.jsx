import { useState } from 'react';
import { backdrop } from '../../data/home';
import { BackgroundVideo } from './BackgroundVideo';
import styles from './PhotoBackdrop.module.css';

/**
 * The sunlit-room photo, full-bleed. Shared by every screen that sits on top of it
 * (home, login, signup) so they all reference the same image and fade-in behaviour —
 * one file to swap when a different photo replaces this one.
 *
 * `motion` fades the same room, in motion, in over the still once it can play, runs it
 * once and fades back to the still. It is opt-in because the auth screens put a paper
 * card and a form over this photo and a moving background behind live text is a
 * separate design call.
 */
export function PhotoBackdrop({ motion = false, veil = false, children }) {
  const [ready, setReady] = useState(false);

  return (
    <div className={styles.root}>
      <div className={styles.wash} aria-hidden>
        <img
          className={`${styles.photo} ${ready ? styles.photoReady : ''}`}
          src={backdrop.src}
          alt=""
          onLoad={() => setReady(true)}
        />
        {motion && (
          <BackgroundVideo
            webm={backdrop.loop.webm}
            mp4={backdrop.loop.mp4}
            playOnce
            className={styles.loop}
          />
        )}
      </div>
      {veil && <div className={styles.veil} aria-hidden />}
      {children}
    </div>
  );
}
