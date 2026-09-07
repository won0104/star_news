import { PinnedCard } from '../common/PinnedCard';
import styles from './GraphCards.module.css';

/** A neighbour in the graph: entity, related event, topic, time or story. */
export function EntityCard({
  shell,
  content
}) {
  return <PinnedCard shell={shell}>
      <p className={styles.entityType} style={{
      color: content.typeColor
    }}>
        {content.type}
      </p>

      <div className={styles.entityTitle}>
        {content.titleLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <img className={styles.entityDot} src={content.dot} alt="" />
      <p className={styles.entitySub}>{content.sub}</p>
    </PinnedCard>;
}
