import { card, graph } from '../../data/assets';
import { eventCard } from '../../data/cards';
import { graphEventContent } from '../../data/graph';
import { PinnedCard } from '../common/PinnedCard';
import styles from './GraphCards.module.css';
const COLUMN_LEFTS = [52, 77, 102, 127, 152];

/** The centred event of the graph: an illustrated bank facade instead of a photo. */
export function GraphEventCard() {
  return <PinnedCard shell={eventCard}>
      <div className={styles.thumbFrame}>
        <div className={styles.bankRoofBox}>
          <div className={styles.bankRoofBleed}>
            <img className={styles.bankRoofArt} src={graph.bankRoof} alt="" />
          </div>
        </div>
        <div className={styles.bankBase} />
        {COLUMN_LEFTS.map(left => <div key={left} className={styles.bankColumn} style={{
        left
      }} />)}
        <p className={styles.thumbCaption}>{graphEventContent.thumbnailCaption}</p>
      </div>
      <div className={styles.thumbBorder} />

      <img className={styles.eventDot} src={card.dot.event} alt="" />
      <p className={styles.eventType}>{graphEventContent.type}</p>
      <p className={styles.bookmark}>{graphEventContent.bookmark}</p>

      <div className={styles.eventHeadline}>
        {graphEventContent.headlineLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <p className={`${styles.eventMeta} ${styles.eventCategory}`}>{graphEventContent.category}</p>
      <p className={`${styles.eventMeta} ${styles.eventArticles}`}>{graphEventContent.articles}</p>
      <p className={styles.eventArrow}>→</p>
    </PinnedCard>;
}
