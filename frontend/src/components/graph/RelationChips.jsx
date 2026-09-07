import { relationChips } from '../../data/graph';
import styles from './RelationChips.module.css';

/** Chips naming how each neighbour relates to the centred event. */
export function RelationChips() {
  return <>
      {relationChips.map(chip => <div key={chip.id} className={styles.chip} style={{
      left: chip.left,
      top: chip.top,
      width: chip.width,
      height: chip.height
    }}>
          <img className={styles.dot} src={chip.dot} alt="" />
          <p className={styles.label}>{chip.label}</p>
        </div>)}
    </>;
}
