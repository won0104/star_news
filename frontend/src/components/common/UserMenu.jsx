import { useEffect, useRef, useState } from 'react';
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
 */
export function UserMenu({ account }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const markRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const closeOnOutsidePress = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      markRef.current?.focus();
    };

    document.addEventListener('pointerdown', closeOnOutsidePress);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePress);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        ref={markRef}
        className={styles.mark}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`${account.id} · ${accountMenu.label}`}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        {(account.user?.nickname ?? account.user?.loginId ?? '').trim().charAt(0).toUpperCase()}
      </button>

      {open && (
        <div className={styles.panel}>
          <p className={styles.who}>{account.user?.nickname ?? account.user?.loginId}</p>

          {accountMenu.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={styles.item}
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
            onClick={() => {
              setOpen(false);
              endSession();
            }}
          >
            {accountMenu.signOut}
          </button>
        </div>
      )}
    </div>
  );
}
