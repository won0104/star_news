import { useState } from 'react';
import { dislikesPane, settingsCopy } from '../../data/settings';
import { addDislike, removeDislike, useSettingsValues } from '../../store/settings';
import { PaneFooter, PaneHead, SectionHead } from './PaneChrome';
import paneStyles from './PaneChrome.module.css';
import styles from './DislikesPane.module.css';

/**
 * 관심 없음 관리 — Figma V3 / Overlay / Settings / Dislikes.
 *
 * No eyebrow: this frame does not carry one, unlike 관심 관리.
 *
 * The count beside 등록된 항목 is derived from the list, never stored, so the two cannot
 * disagree. Adding is a form rather than a bare button, so Enter works in the field,
 * and it takes the same guards as 관심 노드 — no blanks, no duplicates.
 *
 * Each row reads 추천 후보에서 제외 예정 — "예정" because nothing takes effect until
 * 변경사항 저장, which is what the notice at the bottom is there to say. That button has
 * nowhere to send anything yet.
 */
export function DislikesPane() {
  const { dislikes } = useSettingsValues();
  const [draft, setDraft] = useState('');

  const submit = (event) => {
    event.preventDefault();
    addDislike(draft);
    setDraft('');
  };

  return (
    <>
      <PaneHead title={dislikesPane.title} blurb={dislikesPane.blurb} />

      <SectionHead label={dislikesPane.addLabel} />

      <form className={styles.addRow} onSubmit={submit}>
        <input
          type="text"
          className={styles.input}
          placeholder={dislikesPane.addPlaceholder}
          aria-label={dislikesPane.addLabel}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" className={styles.add}>
          {dislikesPane.addSubmit}
        </button>
      </form>

      <SectionHead
        label={dislikesPane.listLabel}
        count={dislikesPane.listCount(dislikes.length)}
      />

      {dislikes.length === 0 ? (
        <p className={styles.empty}>{dislikesPane.listEmpty}</p>
      ) : (
        <ul className={styles.list}>
          {dislikes.map((item) => (
            <li className={styles.item} key={item.id}>
              <span className={styles.itemText}>
                <span className={styles.itemLabel}>{item.label}</span>
                <span className={styles.itemNote}>{dislikesPane.itemNote}</span>
              </span>
              <button
                type="button"
                className={styles.remove}
                onClick={() => removeDislike(item.id)}
              >
                {dislikesPane.itemRemove}
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className={styles.notice}>
        {dislikesPane.notice.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </p>

      <PaneFooter>
        <button type="button" className={paneStyles.primary}>
          {settingsCopy.save}
        </button>
      </PaneFooter>
    </>
  );
}
