import { Fragment } from 'react';
import { authActions, brand, navItems } from '../../data/home';
import { useSession } from '../../store/session';
import { UserMenu } from './UserMenu';
import styles from './TopBar.module.css';

/**
 * Site chrome over the room photo: brand, section nav, and the right-hand end, which is
 * the sign-in and sign-up entry points until someone signs in and the account mark and
 * its menu take their place.
 *
 * The nav is now the whole of the site's navigation — the left menu board it used to
 * share the job with is gone, and the four destinations that were nested inside it (two
 * board entries, each with a two-tab strip) are flat here.
 *
 * The hairlines between buttons are their own elements rather than a border or a
 * `::before` on the button, because the active button is a filled dark pill: a rule
 * drawn on the button would sit inside that pill, and a border would ride the pill's
 * rounded edge. Free-standing spans stay clear of it, and being decorative they are
 * `aria-hidden` — the nav's own list semantics say where one item ends.
 *
 * `onAuth` is only asked for while nobody is signed in. The account menu needs nothing
 * from here — its entries open the settings overlay and end the session themselves.
 *
 * `onBrand` is where the mark leads, and it is separate from `onSelect` because the mark
 * is not a fifth destination: from inside the app it leaves for the front of the site.
 * Without it the mark falls back to opening the first destination, which is what the
 * screens that are already at the front want.
 */
export function TopBar({ activeId, onSelect, onBrand, onAuth }) {
  const account = useSession();

  return (
    <header className={styles.bar}>
      <button
        type="button"
        className={styles.brand}
        onClick={onBrand ?? (() => onSelect(navItems[0].id))}
      >
        <span className={styles.brandName}>{brand.name}</span>
      </button>

      <nav className={styles.nav}>
        {navItems.map((item, index) => (
          <Fragment key={item.id}>
            {index > 0 && <span className={styles.navRule} aria-hidden />}
            <button
              type="button"
              className={`${styles.navItem} ${item.id === activeId ? styles.navItemActive : ''}`}
              aria-current={item.id === activeId ? 'page' : undefined}
              onClick={() => onSelect(item.id)}
            >
              {item.label}
            </button>
          </Fragment>
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
