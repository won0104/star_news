import { useEffect, useRef } from 'react';
import { settingsCopy, settingsPanes } from '../../data/settings';
import { closeSettings, openSettings, useSettingsSection } from '../../store/settings';
import { AccountPane } from './AccountPane';
import { DislikesPane } from './DislikesPane';
import { DisplayPane } from './DisplayPane';
import { InterestPane } from './InterestPane';
import styles from './SettingsOverlay.module.css';

/**
 * The settings overlay — Figma V3 / Overlay / Settings.
 *
 * Mounted once in App rather than per screen, so it opens over whatever you were
 * looking at and the top bar's account menu is the only thing that has to know it
 * exists. Renders nothing until a pane is asked for.
 *
 * All four panes are built.
 */
export function SettingsOverlay() {
  const section = useSettingsSection();
  const modalRef = useRef(null);
  const openerRef = useRef(null);

  const open = section !== null;

  useEffect(() => {
    if (!open) return undefined;

    // Whatever was focused when this opened is where focus goes back to on close —
    // the account mark, since UserMenu hands focus back to it before opening.
    openerRef.current = document.activeElement;
    modalRef.current?.focus();

    const closeOnEscape = (event) => {
      if (event.key === 'Escape') closeSettings();
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      if (openerRef.current instanceof HTMLElement) openerRef.current.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className={styles.scrim}
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) closeSettings();
      }}
    >
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
        ref={modalRef}
      >
        <div className={styles.rail}>
          <p className={styles.railTitle} id="settings-title">
            {settingsCopy.title}
          </p>

          <nav className={styles.nav} aria-label={settingsCopy.nav}>
            {settingsPanes.map((entry) => (
              <button
                key={entry.id}
                type="button"
                className={`${styles.navItem} ${entry.id === section ? styles.navItemActive : ''}`}
                aria-current={entry.id === section ? 'page' : undefined}
                onClick={() => openSettings(entry.id)}
              >
                {entry.label}
              </button>
            ))}
          </nav>

          <button type="button" className={styles.back} onClick={closeSettings}>
            {settingsCopy.back}
          </button>
        </div>

        <div className={styles.pane}>
          <button
            type="button"
            className={styles.close}
            aria-label={settingsCopy.close}
            onClick={closeSettings}
          >
            <svg viewBox="0 0 24 24" aria-hidden focusable="false">
              <path d="M6 6 18 18M18 6 6 18" />
            </svg>
          </button>

          {section === 'account' && <AccountPane />}
          {section === 'interest' && <InterestPane />}
          {section === 'dislikes' && <DislikesPane />}
          {section === 'display' && <DisplayPane />}
        </div>
      </div>
    </div>
  );
}
