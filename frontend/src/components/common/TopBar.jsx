import { authActions, brand, navItems } from '../../data/home';
import { useSession } from '../../store/session';
import { UserMenu } from './UserMenu';
import styles from './TopBar.module.css';

/**
 * Site chrome over the room photo: brand, section nav, and the right-hand end, which is
 * the sign-in and sign-up entry points until someone signs in and the account mark and
 * its menu take their place.
 *
 * `onAuth` is only asked for while nobody is signed in. The account menu needs nothing
 * from here — its entries open the settings overlay and end the session themselves.
 */
export function TopBar({ activeId, onSelect, onAuth }) {
  const account = useSession();

  return (
    <header className={styles.bar}>
      <button type="button" className={styles.brand} onClick={() => onSelect('foryou')}>
        <span className={styles.brandName}>{brand.name}</span>
        <span className={styles.brandSection}>· {brand.section}</span>
      </button>

      <nav className={styles.nav}>
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`${styles.navItem} ${item.id === activeId ? styles.navItemActive : ''}`}
            aria-current={item.id === activeId ? 'page' : undefined}
            onClick={() => onSelect(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className={styles.spacer} />

      <div className={styles.auth}>
        {account ? (
          <UserMenu account={account} />
        ) : (
          <>
            <button type="button" className={styles.signIn} onClick={() => onAuth('login')}>
              {authActions.signIn}
            </button>
            <button type="button" className={styles.signUp} onClick={() => onAuth('signup')}>
              {authActions.signUp}
            </button>
          </>
        )}
      </div>
    </header>
  );
}
