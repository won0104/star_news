import { graphControls, graphSearchPlaceholder } from '../../data/graph';
import styles from './ExplorationControls.module.css';

/** Top-right cluster: depth, neighbour count and the "show more" action. */
export function ExplorationControls() {
  return <div className={styles.cluster}>
      <p className={styles.eyebrow}>{graphControls.eyebrow}</p>

      <button type="button" className={`${styles.chip} ${styles.depth}`}>
        <span className={styles.depthLabel}>{graphControls.depth}</span>
      </button>
      <button type="button" className={`${styles.chip} ${styles.count}`}>
        <span className={styles.countLabel}>{graphControls.count}</span>
      </button>
      <button type="button" className={`${styles.chip} ${styles.more}`}>
        <span className={styles.moreLabel}>{graphControls.more}</span>
      </button>
    </div>;
}

/** Graph-view search pill, sitting over the controls cluster. */
export function GraphSearchPill() {
  return <div className={styles.search} role="search">
      <p className={styles.searchLabel}>{graphSearchPlaceholder}</p>
    </div>;
}
