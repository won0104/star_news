import { depthPapers } from '../../data/scene';
import styles from './Papers.module.css';

/** Blurred, low-opacity paper rectangles that give the yarn something to sit in front of. */
export function DepthPapers() {
  return <>
      {depthPapers.map((paper, i) => <div key={i} className={styles.rotatedBox} style={{
      left: paper.left,
      top: paper.top,
      width: paper.width,
      height: paper.height
    }}>
          <div className={styles.depthPaper} style={{
        width: paper.innerWidth,
        height: paper.innerHeight,
        transform: `rotate(${paper.rotate}deg)`,
        filter: `blur(${paper.blur}px)`,
        opacity: paper.opacity
      }} />
        </div>)}
    </>;
}
