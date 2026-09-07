import { photo } from '../../data/assets';
import styles from './Backdrop.module.css';

/** Empty attic room photo plus the two light veils that shape the scene's lighting. */
export function Backdrop() {
  return <div className={styles.root}>
      <img className={styles.room} src={photo.backdrop} alt="" />
      <div className={`${styles.veil} ${styles.leftVeil}`} />
      <div className={`${styles.veil} ${styles.rightVeil}`} />
    </div>;
}
