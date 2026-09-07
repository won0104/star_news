import { authActions, brand, navItems } from '../../data/home';
import styles from './TopBar.module.css';

/** Site chrome over the home photo: brand, section nav, and the login / signup entry points. */
export function TopBar({
  activeId,
  onSelect,
  onAuth
}) {
  return <header className={styles.bar}>
      <button type="button" className={styles.brand} onClick={() => onSelect('foryou')}>
        <span className={styles.brandName}>{brand.name}</span>
        <span className={styles.brandSection}>· {brand.section}</span>
      </button>

      <nav className={styles.nav}>
        {navItems.map(item => <button key={item.id} type="button" className={`${styles.navItem} ${item.id === activeId ? styles.navItemActive : ''}`} aria-current={item.id === activeId ? 'page' : undefined} onClick={() => onSelect(item.id)}>
            {item.label}
          </button>)}
      </nav>

      <div className={styles.spacer} />

      <div className={styles.auth}>
        <button type="button" className={styles.signIn} onClick={() => onAuth('login')}>
          {authActions.signIn}
        </button>
        <button type="button" className={styles.signUp} onClick={() => onAuth('signup')}>
          {authActions.signUp}
        </button>
      </div>
    </header>;
}
