import { BrassPin } from './BrassPin';
import styles from './PinnedCard.module.css';

/**
 * Shared paper-card shell: cast shadow, paper gradient, grain, flecks and brass pin.
 * Every pinned card in the attic is this shell plus its own content layer.
 */
export function PinnedCard({
  shell,
  children,
  onSelect,
  selectLabel
}) {
  const {
    frame,
    shadow,
    width,
    height,
    rotate,
    paper,
    flecks,
    grain
  } = shell;
  const interactive = onSelect ? {
    role: 'button',
    tabIndex: 0,
    'aria-label': selectLabel,
    onClick: onSelect,
    onKeyDown: event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onSelect();
      }
    }
  } : {};
  return <>
      <div className={styles.shadowBox} style={{
      left: shadow.left,
      top: shadow.top,
      width: shadow.width,
      height: shadow.height
    }}>
        <div className={styles.shadowInner} style={{
        width,
        height,
        transform: `rotate(${rotate}deg)`,
        background: shadow.color,
        filter: `blur(${shadow.blur}px)`
      }} />
      </div>

      <div className={styles.cardBox} style={{
      left: frame.left,
      top: frame.top,
      width: frame.width,
      height: frame.height
    }}>
        <div {...interactive} className={`${styles.card} ${onSelect ? styles.interactive : ''}`} style={{
        width,
        height,
        transform: `rotate(${rotate}deg)`,
        '--paper-a': paper[0],
        '--paper-b': paper[1],
        '--paper-c': paper[2]
      }}>
          <div className={styles.paper} aria-hidden />

          <div className={`${styles.bottomShade} ${shell.strongBottomShade ? styles.bottomShadeStrong : ''}`} style={{
          top: height - 5.8,
          width: width - 12
        }} />
          <div className={styles.topHighlight} style={{
          width: width - 10
        }} />

          {flecks.map((fleck, i) => <img key={i} className={styles.fleck} src={fleck.src} alt="" style={{
          left: fleck.left,
          top: fleck.top,
          width: fleck.width,
          height: fleck.height
        }} />)}

          {grain.map((g, i) => <div key={i} className={styles.grainBox} style={{
          left: g.left,
          top: g.top,
          width: g.boxWidth,
          height: g.boxHeight
        }}>
              <div className={styles.grainLine} style={{
            width: g.lineWidth,
            transform: `rotate(${g.rotate}deg)`
          }}>
                <img className={styles.grainArt} src={g.src} alt="" />
              </div>
            </div>)}

          <BrassPin cardWidth={width} />

          {children}

          <div className={styles.innerGlow} aria-hidden />
        </div>
      </div>
    </>;
}
