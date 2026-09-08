import { Backdrop } from '../common/Backdrop';
import styles from './CompactShell.module.css';

/**
 * Page frame for the reflowed scenes. The room photo stays — it is the one part of the
 * composition that survives losing the canvas — pinned behind a scrolling column of
 * content. Line-broken copy from the scene data is joined before it gets here, so it
 * wraps to the column instead of keeping the desktop's hand-set breaks.
 */
export function CompactShell({
  backdrop,
  brand,
  onBrand,
  brandLabel,
  title,
  subtitle,
  search,
  activeNav,
  navItems,
  motto,
  tagline,
  children,
}) {
  return (
    <>
      <div className={styles.room} aria-hidden>
        <Backdrop src={backdrop} />
        <div className={styles.scrim} />
      </div>

      <div className={styles.scroll}>
        <div className={styles.column}>
          <header className={styles.header}>
            <button type="button" className={styles.brand} onClick={onBrand} aria-label={brandLabel}>
              {brand}
            </button>
            <h1 className={styles.title}>{title}</h1>
            <p className={styles.subtitle}>{subtitle}</p>

            <div className={styles.search} role="search">
              {search}
            </div>

            <nav className={styles.nav} aria-label="섹션">
              <span className={styles.navActive} aria-current="page">
                {activeNav}
              </span>
              {navItems.map((item) => (
                <button key={item.id} type="button" className={styles.navItem}>
                  {item.label}
                </button>
              ))}
            </nav>
          </header>

          <main className={styles.main}>{children}</main>

          <footer className={styles.footer}>
            <div className={styles.rule} />
            <p className={styles.motto}>{motto}</p>
            <p className={styles.tagline}>{tagline}</p>
          </footer>
        </div>
      </div>
    </>
  );
}
