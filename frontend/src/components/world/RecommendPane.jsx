import { Link } from 'react-router-dom';
import { events } from '../../data/events';
import { recommend } from '../../data/recommend';
import { BrassPin } from '../common/BrassPin';
import styles from './RecommendPane.module.css';

/**
 * 나를 위한 추천 — the recommendations pinned to a board.
 *
 * They were sheets in a column before; the board is now the surface they sit on, so they
 * are notes: smaller, tilted, and each with a brass pin through its top edge. The pin is
 * the attic's own <BrassPin>, unchanged — it derives its whole cluster from one anchor
 * point, so giving it a zero-width point centred on a note's top edge is all it needs.
 *
 * The tilt comes from a fixed table rather than Math.random. A random angle would be a
 * new angle on every render, so a note would twitch whenever anything else on the screen
 * changed.
 *
 * The board comes in when the room has stopped moving: `settled` is the arrival clip
 * reaching its end, and until then the board is held at the size it will shrink from, so
 * nothing lands over a moving picture.
 *
 * Ten notes, five across and two down, whatever the window — the stylesheet holds that
 * tiling and narrows what a note carries instead, so nothing here has to count anything.
 *
 * The notes are links, not buttons. They go to a URL — /event/:id — so an anchor is what
 * they should be, and opening one in a new tab works as it should.
 *
 * Each note's title and summary come from the event store rather than from the
 * recommendation, so a note and the page it opens cannot say different things.
 */

/** Degrees, by position. Small enough that .notes' gap absorbs them. */
const TILT = [-0.7, 0.5, -0.4, 0.8, -0.6, 0.35, -0.85, 0.6, -0.3, 0.75];

export function RecommendPane({ settled = true }) {
  const { cards } = recommend;

  return (
    <div className={styles.page}>
      {/*
        The heading block — the title, the line about how these were chosen and the count —
        is off for now. Its copy is still in data/recommend.js and its styles are still in
        the stylesheet, so putting it back is this element again.
      */}
      <div className={`${styles.board} ${settled ? styles.boardIn : styles.boardWaiting}`}>
        <div className={styles.cork}>
          <ul className={styles.notes}>
          {cards.map((card, index) => {
            const event = events[card.eventId];
            return (
              <li key={card.eventId} className={styles.note}>
                <span className={styles.pin} aria-hidden>
                  <BrassPin cardWidth={0} />
                </span>

                <Link
                  className={styles.paper}
                  to={`/event/${event.id}`}
                  style={{ transform: `rotate(${TILT[index % TILT.length]}deg)` }}
                >
                  <p className={styles.reason}>
                    <span className={styles.reasonKey}>{recommend.reasonLabel} · </span>
                    {card.reason}
                  </p>
                  <h3 className={styles.noteTitle}>{event.title}</h3>
                  <p className={styles.noteSummary}>{event.summary}</p>
                  <span className={styles.noteFoot}>
                    <span className={styles.noteTags}>{event.hashtags.join('  ')}</span>
                    <span className={styles.noteGo} aria-hidden>
                      자세히 →
                    </span>
                  </span>
                </Link>
              </li>
            );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
