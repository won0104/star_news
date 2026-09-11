import styles from './BleedImage.module.css';

/**
 * Figma exports strokes with the artwork bleeding past the layer box. Reproducing that
 * needs the layer box for positioning and an inner, negatively-inset box for the artwork.
 */
export function BleedImage({
  src,
  left,
  top,
  width,
  height,
  inset
}) {
  return <div className={styles.box} style={{
    left,
    top,
    width,
    height
  }}>
      <div className={styles.bleed} style={{
      inset
    }}>
        <img className={styles.art} src={src} alt="" />
      </div>
    </div>;
}
