import styles from './PaneChrome.module.css';

/**
 * The furniture every settings pane shares: the header block, the section headers, and
 * the primary action in the bottom-right. Pulled out because all four Figma panes are
 * built the same way down to the spacing, and a pane should only have to describe what
 * is actually its own.
 */

export function PaneHead({ eyebrow, title, blurb }) {
  return (
    <>
      <p className={styles.eyebrow}>{eyebrow}</p>
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.blurb}>{blurb}</p>
    </>
  );
}

/** `count` is optional and sits at the far right; panes derive it, never store it. */
export function SectionHead({ label, hint, count }) {
  return (
    <div className={styles.sectionHead}>
      <h3 className={styles.sectionLabel}>{label}</h3>
      {hint && <p className={styles.sectionHint}>{hint}</p>}
      {count && <p className={styles.sectionCount}>{count}</p>}
    </div>
  );
}

export function PaneFooter({ children }) {
  return <div className={styles.footer}>{children}</div>;
}
