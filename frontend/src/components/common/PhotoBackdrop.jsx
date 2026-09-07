import { useState } from 'react';
import { backdrop } from '../../data/home';
import styles from './PhotoBackdrop.module.css';

/**
 * The sunlit-room photo, full-bleed. Shared by every screen that sits on top of it
 * (home, login, signup) so they all reference the same image and fade-in behaviour —
 * one file to swap when a different photo replaces this one.
 */
export function PhotoBackdrop({
  veil = false,
  children
}) {
  const [ready, setReady] = useState(false);
  return <div className={styles.root}>
      <div className={styles.wash} aria-hidden>
        <img className={`${styles.photo} ${ready ? styles.photoReady : ''}`} src={backdrop.src} alt="" onLoad={() => setReady(true)} />
      </div>
      {veil && <div className={styles.veil} aria-hidden />}
      {children}
    </div>;
}
