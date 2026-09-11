import { card } from '../../data/assets';
import { graphActiveNav, graphHero, graphMotto, graphNavItems } from '../../data/graph';
import styles from './GraphSidebar.module.css';

/**
 * Left rail of the graph view. The brand line doubles as the way back to the attic
 * until a dedicated navigation/transition layer exists.
 */
export function GraphSidebar({
  onBack
}) {
  return <>
      <button type="button" className={styles.brand} onClick={onBack}>
        {graphHero.brand}
      </button>

      <div className={styles.title}>
        {graphHero.titleLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <div className={styles.subtitle}>
        {graphHero.subtitleLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <button type="button" className={styles.activePill} aria-current="page">
        <span className={styles.activePillLabel}>{graphActiveNav.label}</span>
      </button>

      {graphNavItems.map(item => <button key={item.id} type="button" className={styles.navItem} style={{
      top: item.top
    }}>
          {item.label}
        </button>)}

      <div className={styles.footerRule}>
        <img className={styles.footerRuleArt} src={card.footerRule} alt="" />
      </div>

      <div className={styles.motto}>
        {graphMotto.map(line => <p key={line}>{line}</p>)}
      </div>
    </>;
}
