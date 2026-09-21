import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { signOut } from '../../api/auth';
import { accountMenu } from '../../data/home';
import { endSession } from '../../store/session';
import { openSettings } from '../../store/settings';
import styles from './UserMenu.module.css';

/**
 * The signed-in account's mark in the top bar, and the panel it opens.
 *
 * Deliberately not `role="menu"`: that pattern owes the user arrow-key navigation
 * between items, and claiming it without that is worse than not claiming it. A popup of
 * ordinary buttons gets Tab order, Enter and a focus ring for free. Escape closes and
 * hands focus back to the mark, and a pointer press anywhere outside closes too.
 *
 * Both kinds of entry act on shared state rather than on the page, so neither needs a
 * callback from the caller: the three settings entries open the settings overlay on
 * their pane, and 로그아웃 ends the session. Focus goes back to the mark before the
 * overlay opens, so the overlay has something to return focus to when it closes.
 *
 * Where the panel is drawn depends on the bar's shape. In the horizontal bar it hangs
 * off the mark as a dropdown. From 1024px up (TopBar.module.css's rail query — keep the
 * two in step) the bar is a left rail with the mark at its very bottom, so a dropdown
 * would open past the bottom of the viewport; there the panel is portalled to body and
 * centred on the screen instead. The portal is necessary, not just tidy: the rail has a
 * backdrop-filter, which makes it the containing block for any fixed descendant, so a
 * `position: fixed` panel left inside it would be centred within the rail's width.
 */
const RAIL_QUERY = '(min-width: 1024px)';

let railMedia;
const rail = () => (railMedia ??= window.matchMedia(RAIL_QUERY));
const subscribeRail = (onChange) => {
  const list = rail();
  list.addEventListener('change', onChange);
  return () => list.removeEventListener('change', onChange);
};
const useIsRail = () => useSyncExternalStore(subscribeRail, () => rail().matches);

export function UserMenu({ account }) {
  const navigate = useNavigate();
  const displayName = account.user?.nickname || account.user?.loginId || accountMenu.unknownUser;
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState(null);
  const rootRef = useRef(null);
  const markRef = useRef(null);
  const panelRef = useRef(null);
  const isRail = useIsRail();

  useEffect(() => {
    if (!open) return undefined;

    // The panel may be portalled out of root, so it has to be checked on its own.
    const closeOnOutsidePress = (event) => {
      if (signingOut) return;
      const inside =
        rootRef.current?.contains(event.target) || panelRef.current?.contains(event.target);
      if (!inside) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key !== 'Escape' || signingOut) return;
      setOpen(false);
      markRef.current?.focus();
    };

    document.addEventListener('pointerdown', closeOnOutsidePress);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePress);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open, signingOut]);

  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    setSignOutError(null);
    try {
      await signOut();
    } catch {
      setSignOutError(accountMenu.signOutFailed);
      setSigningOut(false);
      return;
    }
    setOpen(false);
    endSession();
    navigate('/', { replace: true });
  };

  const panel = (
    <div className={`${styles.panel} ${isRail ? styles.panelCentred : ''}`} ref={panelRef}>
      <p className={styles.who}>{displayName}</p>

      {accountMenu.items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={styles.item}
          disabled={signingOut}
          onClick={() => {
            setOpen(false);
            markRef.current?.focus();
            openSettings(item.id);
          }}
        >
          {item.label}
        </button>
      ))}

      <div className={styles.divider} />

      <button
        type="button"
        className={styles.item}
        disabled={signingOut}
        onClick={handleSignOut}
      >
        {signingOut ? accountMenu.signingOut : accountMenu.signOut}
      </button>
      {signOutError && <p className={styles.error} role="alert">{signOutError}</p>}
    </div>
  );

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        ref={markRef}
        className={styles.mark}
        disabled={signingOut}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`${displayName} · ${accountMenu.label}`}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        {displayName.trim().charAt(0).toUpperCase()}
      </button>

      {open && (isRail ? createPortal(panel, document.body) : panel)}
    </div>
  );
}
