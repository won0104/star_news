import { hangers } from '../../data/graph';
import styles from './Hangers.module.css';
function Piece({
  src,
  left,
  top,
  width,
  height,
  inset
}) {
  return <div className={styles.piece} style={{
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

/** Coloured threads (plus their knots) tying each card up to the yarn above it. */
export function Hangers() {
  return <>
      {hangers.map(hanger => <div key={hanger.id}>
          <Piece {...hanger.line} />
          <Piece {...hanger.knot} />
        </div>)}
    </>;
}
