import { eventCopy } from '../../data/events';
import styles from './ArticlePanel.module.css';

/**
 * 뉴스 상세 — one article, in the bar that opens on the right of the event page.
 *
 * Stays mounted whether it is open or shut so it can slide rather than appear, and is
 * `inert` while shut, which takes it out of the tab order as well as off the screen —
 * the call <SideNav> made for its tucked board.
 *
 * It shows where the piece came from, when, its headline and its opening sentence, and
 * then says plainly that the rest is at the source. That is all there is: no full text is
 * stored and there is no URL to send anyone to yet, so an 원문 보기 button here would be a
 * control that does nothing. The note takes its place until a link exists.
 *
 * `article` is null before anything has been pressed. The panel still renders — closed
 * and empty — because unmounting it would cost the slide on the way in.
 */
export function ArticlePanel({ article, open, onClose, onToggleSave, id }) {
  return (
    <aside
      id={id}
      className={`${styles.panel} ${open ? '' : styles.panelClosed}`}
      aria-label={eventCopy.panelLabel}
      inert={!open || !article}
    >
      <button type="button" className={styles.close} onClick={onClose} aria-label={eventCopy.close}>
        ✕
      </button>

      {article && (
        <>
          <div className={styles.head}>
            <span className={styles.eyebrow}>{eventCopy.panelLabel}</span>
            <p className={styles.source}>
              {article.source} · {article.at}
            </p>
            <h2 className={styles.headline}>{article.headline}</h2>
            {/* `url` is not in the article data yet, and React drops an undefined href —
                so this renders as plain text until the field exists, rather than as a
                link that goes nowhere. */}
            <a
              className={styles.origin}
              href={article.url}
              target="_blank"
              rel="noreferrer"
            >
              {eventCopy.origin} ↗
            </a>
          </div>

          <div className={styles.body}>
            <p className={styles.leadLabel}>{eventCopy.leadLabel}</p>
            <p className={styles.lead}>{article.lead}</p>
            <p className={styles.note}>{eventCopy.sourceNote}</p>
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={`${styles.save} ${article.saved ? styles.saveOn : ''}`}
              aria-pressed={article.saved}
              onClick={() => onToggleSave(article.id)}
            >
              {article.saved ? `✓ ${eventCopy.unsave}` : eventCopy.save}
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
