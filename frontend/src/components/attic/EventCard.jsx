import { card, photo } from '../../data/assets';
import { eventCard, eventContent } from '../../data/cards';
import { PinnedCard } from '../common/PinnedCard';
import styles from './CardContent.module.css';

/** The focused card: a photographed news event with headline, date and place. */
export function EventCard() {
  return <PinnedCard shell={eventCard}>
      <div className={styles.thumbFrame}>
        <img className={styles.thumbCrop} src={photo.eventThumb} alt="" />
      </div>
      <div className={styles.thumbBorder} />

      <img className={styles.eventDot} src={card.dot.event} alt="" />
      <p className={styles.eventType}>{eventContent.type}</p>

      <div className={styles.eventHeadline}>
        {eventContent.headlineLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <p className={`${styles.eventMeta} ${styles.eventDate}`}>{eventContent.date}</p>
      <p className={`${styles.eventMeta} ${styles.eventPlace}`}>{eventContent.place}</p>
      <p className={styles.eventArrow}>→</p>
    </PinnedCard>;
}
