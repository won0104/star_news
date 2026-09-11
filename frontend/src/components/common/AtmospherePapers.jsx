import { atmospherePapers } from '../../data/scene';
import styles from './Papers.module.css';

/** Ghosted pinned papers hanging deeper in the room, drawn above the cards. */
export function AtmospherePapers() {
  return <>
      {atmospherePapers.map(paper => <div key={paper.src} className={styles.rotatedBox} style={{
      left: paper.left,
      top: paper.top,
      width: paper.width,
      height: paper.height
    }}>
          <div style={{
        position: 'relative',
        width: paper.innerWidth,
        height: paper.innerHeight,
        transform: `rotate(${paper.rotate}deg)`
      }}>
            <div className={styles.atmosBleed} style={{
          inset: paper.inset
        }}>
              <img className={styles.atmosArt} src={paper.src} alt="" />
            </div>
          </div>
        </div>)}
    </>;
}
