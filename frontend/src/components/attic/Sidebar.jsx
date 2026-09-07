import { card } from '../../data/assets';
import { activeNav, footerMotto, hero, navItems } from '../../data/scene';
import styles from './Sidebar.module.css';

/** Left rail: hero copy, the Explore pill, secondary navigation and the footer motto. */
export function Sidebar() {
  return <>
      <div className={styles.title}>
        {hero.titleLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <div className={styles.subtitle}>
        {hero.subtitleLines.map(line => <p key={line}>{line}</p>)}
      </div>

      <button type="button" className={styles.activePill} aria-current="page">
        <span className={styles.activePillLabel}>{activeNav.label}</span>
      </button>

      {navItems.map(item => <button key={item.id} type="button" className={styles.navItem} style={{
      top: item.top
    }}>
          {item.label}
        </button>)}

      <div className={styles.footerRule}>
        <img className={styles.footerRuleArt} src={card.footerRule} alt="" />
      </div>

      <div className={styles.motto}>
        {footerMotto.map(line => <p key={line}>{line}</p>)}
      </div>
    </>;
}
