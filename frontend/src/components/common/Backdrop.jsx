import { photo } from '../../data/assets';
import styles from './Backdrop.module.css';

/**
 * The room photo plus the two light veils that shape the scene's lighting. Pinned to
 * the viewport rather than the scene canvas so the room fills the screen at any aspect
 * ratio; the veils are proportional so the lighting lands in the same place.
 *
 * `src` defaults to the bare wall every scene started on. The veils matter more the
 * busier the room is — they are what keeps the sidebar copy legible over the shelf and
 * the plants — so a replacement photo should be checked against them, not without.
 *
 * `leftVeil` dims that left wash. A scene that puts its own surface over the room, like
 * the trend view's frosted rail, is already carrying the copy's contrast and can let the
 * room back through; anything that lowers this has to re-measure the copy on top of it.
 */
export function Backdrop({ src = photo.backdrop, leftVeil = 1 }) {
  return (
    <div className={styles.root}>
      <img className={styles.room} src={src} alt="" />
      <div
        className={`${styles.veil} ${styles.leftVeil}`}
        style={leftVeil === 1 ? undefined : { opacity: leftVeil }}
      />
      <div className={`${styles.veil} ${styles.rightVeil}`} />
    </div>
  );
}
