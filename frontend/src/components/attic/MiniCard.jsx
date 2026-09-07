import { PinnedCard } from '../common/PinnedCard';
import styles from './CardContent.module.css';

/** Small category card — a glyph, a coloured dot and a label. */
export function MiniCard({
  shell,
  content,
  onSelect
}) {
  return <PinnedCard shell={shell} onSelect={onSelect} selectLabel={content.label}>
      <p className={styles.miniGlyph}>{content.glyph}</p>
      <img className={styles.miniDot} src={content.dot} alt="" />
      <p className={styles.miniLabel}>{content.label}</p>
    </PinnedCard>;
}
