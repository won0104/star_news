import { searchPlaceholder } from '../../data/scene';
import styles from './SearchPill.module.css';

/** Frosted-glass search affordance floating over the top-right of the room. */
export function SearchPill() {
  return <div className={styles.pill} role="search">
      <div className={styles.glass} aria-hidden />
      <p className={styles.label}>{searchPlaceholder}</p>
    </div>;
}
