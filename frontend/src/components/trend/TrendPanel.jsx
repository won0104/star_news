import { useState } from 'react';
import { eventPanels, panelCopy } from '../../data/trend';
import styles from './TrendPanel.module.css';

/**
 * The articles behind the centre event, in a panel on the right of the stage.
 *
 * Opened by the centre star and closed from here, and it stays mounted either way: it
 * slides out rather than disappearing, and a panel that unmounted would have to animate
 * its own removal to do that. `inert` while it is closed, so what is off screen is also
 * out of the tab order — the same call <SideNav> made for its tucked board.
 *
 * The bookmarks are real toggles but local ones: nothing persists them, because there is
 * no endpoint behind this screen yet. `상세 보기` has nothing behind it at all — there is
 * no article route to send anyone to — so it is there for the shape of the row and does
 * nothing when pressed, which is worth fixing the moment either of those exists.
 */
export function TrendPanel({ eventId, title, open, onClose, id }) {
  const panel = eventPanels[eventId];
  const [saved, setSaved] = useState(() =>
    Object.fromEntries((panel?.articles ?? []).map((a) => [a.id, a.saved])),
  );

  // An event with no articles written for it yet gets no panel rather than an empty one.
  if (!panel) return null;

  return (
    <aside
      id={id}
      className={`${styles.panel} ${open ? '' : styles.panelClosed}`}
      aria-label={title}
      inert={!open}
    >
      <button type="button" className={styles.close} onClick={onClose} aria-label={panelCopy.close}>
        ✕
      </button>

      <div className={styles.head}>
        <span className={styles.eyebrow}>{panel.eyebrow}</span>
        <h2 className={styles.title}>
          {title}
          <span className={styles.titleStar} aria-hidden>
            ★
          </span>
        </h2>
        <p className={styles.meta}>
          {panelCopy.countLabel(panel.count)} · {panel.asOf}
        </p>
        <p className={styles.summary}>{panel.summary}</p>
      </div>

      <ul className={styles.list}>
        {panel.articles.map((article) => (
          <li key={article.id} className={styles.item}>
            <div className={styles.itemHead}>
              <span className={styles.source}>
                {article.source} · {article.at}
              </span>
              <button
                type="button"
                className={`${styles.bookmark} ${saved[article.id] ? styles.bookmarkOn : ''}`}
                aria-pressed={saved[article.id]}
                aria-label={saved[article.id] ? panelCopy.unsave : panelCopy.save}
                onClick={() => setSaved((was) => ({ ...was, [article.id]: !was[article.id] }))}
              >
                <svg className={styles.bookmarkIcon} viewBox="0 0 13 17" aria-hidden>
                  <path
                    d="M1 1.6A.6.6 0 0 1 1.6 1h9.8a.6.6 0 0 1 .6.6v14.2l-5.5-3.6L1 15.8z"
                    fill={saved[article.id] ? 'currentColor' : 'none'}
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>

            <p className={styles.headline}>{article.headline}</p>

            <button type="button" className={styles.detail}>
              {panelCopy.detail} →
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
