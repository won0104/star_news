import { card } from '../../data/assets';
import { statementCard, statementContent } from '../../data/cards';
import { PinnedCard } from '../common/PinnedCard';
import styles from './CardContent.module.css';

/** A pull-quote card attributing a statement to its source. */
export function StatementCard() {
  return <PinnedCard shell={statementCard}>
      <img className={styles.statementDot} src={card.dot.statement} alt="" />
      <p className={styles.statementType}>{statementContent.type}</p>
      <p className={styles.quoteMark}>“</p>

      <div className={styles.statementBody}>
        {statementContent.bodyLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <p className={styles.statementSource}>{statementContent.source}</p>
    </PinnedCard>;
}
