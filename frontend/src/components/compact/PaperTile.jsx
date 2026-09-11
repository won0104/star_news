import { card } from '../../data/assets';
import styles from './PaperTile.module.css';

/**
 * Flow-layout counterpart to <PinnedCard>. The scene's card shell is built from
 * absolute coordinates, so it cannot be reused once the cards reflow — this keeps the
 * things that carry the look (paper tint, brass pin, hand-pinned tilt) and lets the
 * grid decide the size. `paper` and `rotate` come straight off the same shell data, so
 * a card keeps its tint across both layouts.
 */
export function PaperTile({ paper, rotate = 0, className = '', onSelect, selectLabel, children }) {
  const interactive = onSelect
    ? {
        role: 'button',
        tabIndex: 0,
        'aria-label': selectLabel,
        onClick: onSelect,
        onKeyDown: (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onSelect();
          }
        },
      }
    : {};

  return (
    <div
      {...interactive}
      className={`${styles.tile} ${onSelect ? styles.interactive : ''} ${className}`}
      style={{
        '--paper-a': paper[0],
        '--paper-b': paper[1],
        '--paper-c': paper[2],
        '--tile-tilt': `${rotate}deg`,
      }}
    >
      <div className={styles.sheet} aria-hidden />
      <img className={styles.pin} src={card.pin} alt="" aria-hidden />
      <div className={styles.body}>{children}</div>
    </div>
  );
}
