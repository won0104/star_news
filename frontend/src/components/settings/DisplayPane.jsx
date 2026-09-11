import { displayPane } from '../../data/settings';
import { setSetting, useSettingsValues } from '../../store/settings';
import { PaneHead, SectionHead } from './PaneChrome';
import styles from './DisplayPane.module.css';

/**
 * 화면 설정 — Figma V3 / Overlay / Settings / Display.
 *
 * The two choices are native radios inside a segmented control, so arrow keys move
 * between them without any key handling of our own. The last one is a checkbox with
 * `role="switch"`, which is what a switch actually is to a screen reader.
 *
 * Only 애니메이션 없애기 changes anything today, and it changes something real: the home
 * screen reads it and stops handing the clip to <BackgroundVideo>, which means the file
 * is not fetched at all rather than fetched and hidden. Theme and text size are stored
 * and marked as pending in the pane itself — see their notes in data/settings.js for
 * what each would take.
 */
export function DisplayPane() {
  const { theme, textSize, reduceMotion } = useSettingsValues();

  const choice = (name, options, current, pending) => (
    <>
      <div className={styles.segmented} role="radiogroup" aria-label={name.label}>
        {options.map((option) => (
          <label
            key={option.id}
            className={`${styles.segment} ${option.id === current ? styles.segmentOn : ''}`}
          >
            <input
              type="radio"
              className={styles.radio}
              name={name.key}
              value={option.id}
              checked={option.id === current}
              onChange={() => setSetting(name.key, option.id)}
            />
            {option.label}
          </label>
        ))}
      </div>
      <p className={styles.pending}>{pending}</p>
    </>
  );

  return (
    <>
      <PaneHead
        eyebrow={displayPane.eyebrow}
        title={displayPane.title}
        blurb={displayPane.blurb}
      />

      <SectionHead label={displayPane.themeLabel} hint={displayPane.themeHint} />
      {choice(
        { key: 'theme', label: displayPane.themeLabel },
        displayPane.themes,
        theme,
        displayPane.themePending,
      )}

      <SectionHead label={displayPane.textSizeLabel} hint={displayPane.textSizeHint} />
      {choice(
        { key: 'textSize', label: displayPane.textSizeLabel },
        displayPane.textSizes,
        textSize,
        displayPane.textSizePending,
      )}

      <SectionHead label={displayPane.motionLabel} />
      <label className={styles.switchRow}>
        <span className={styles.switchText}>
          <span className={styles.switchHint}>{displayPane.motionHint}</span>
        </span>
        <span className={styles.switchState}>{displayPane.motionState(reduceMotion)}</span>
        <input
          type="checkbox"
          role="switch"
          className={styles.switch}
          checked={reduceMotion}
          aria-checked={reduceMotion}
          aria-label={displayPane.motionLabel}
          onChange={(event) => setSetting('reduceMotion', event.target.checked)}
        />
      </label>
    </>
  );
}
