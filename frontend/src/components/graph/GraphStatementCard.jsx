import { card } from '../../data/assets';
import { statementCard } from '../../data/cards';
import { graphStatementContent } from '../../data/graph';
import { PinnedCard } from '../common/PinnedCard';
import styles from './GraphCards.module.css';

/** The quote pulled from the centred event's announcement. */
export function GraphStatementCard() {
  return <PinnedCard shell={statementCard}>
      <img className={styles.statementDot} src={card.dot.statement} alt="" />
      <p className={styles.statementType}>{graphStatementContent.type}</p>
      <p className={styles.quoteMark}>“</p>

      <div className={styles.statementBody}>
        {graphStatementContent.bodyLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <p className={styles.statementSource}>{graphStatementContent.source}</p>
    </PinnedCard>;
}
