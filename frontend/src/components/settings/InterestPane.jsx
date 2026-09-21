import { useEffect, useRef, useState } from 'react';
import {
  fetchDislikes,
  fetchInterests,
  updateDislikes,
  updateInterests,
} from '../../api/topicPreferences';
import { interestPane } from '../../data/settings';
import { TOPICS } from '../../data/topics';
import { PaneHead, SectionHead } from './PaneChrome';
import styles from './InterestPane.module.css';

/**
 * 관심 관리 — 관심 분야와 관심 없는 분야, 각각 일곱 칸.
 *
 * 두 목록 모두 서버가 진실이다. 열 때 둘을 받아 오고, 칸을 켜고 끌 때마다 그 목록 전체를
 * PUT 으로 다시 보낸다(API 가 "최종 목록으로 교체"라 부분 갱신이 없다). 그래서 저장 버튼이
 * 없다 — 누른 순간이 저장이고, 실패하면 서버의 현재 상태를 다시 읽어 화면에 반영하려 한다.
 *
 * 같은 분야가 양쪽에 동시에 있을 수 없다. 서버는 한쪽 PUT에서 선택한 분야를 반대쪽에서
 * 원자적으로 옮기므로, 한 번의 선택에 요청은 하나만 보낸다.
 *
 * 화면을 먼저 바꾸고, 저장 중에는 다른 선택을 잠시 막는다. 전체 목록을 교체하는 PUT이
 * 역순으로 도착해 이전 선택이 서버의 최종 상태가 되는 일을 피하기 위해서다. 실패하면
 * 두 목록을 다시 읽어 서버 상태로 맞춘다.
 *
 * 비로그인은 401 이고, 그건 오류가 아니라 상태다.
 */
export function InterestPane() {
  const [interests, setInterests] = useState([]);
  const [dislikes, setDislikes] = useState([]);
  const [state, setState] = useState('loading');
  const [save, setSave] = useState(null); // null | 'saving' | 'saved' | 'failed'
  const savingRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchInterests({ signal: controller.signal }),
      fetchDislikes({ signal: controller.signal }),
    ])
      .then(([a, b]) => {
        setInterests(a?.topicCodes ?? []);
        setDislikes(b?.topicCodes ?? []);
        setState('ready');
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return;
        setState(error?.status === 401 ? 'signedOut' : 'failed');
      });
    return () => controller.abort();
  }, []);

  /**
   * 한 칸을 뒤집는다. `side` 는 'interests' | 'dislikes'.
   * 켜는 쪽이면 반대편에서 같은 코드를 빼고, 켠 쪽의 최종 목록만 서버에 보낸다.
   */
  const handleToggle = async (side, code) => {
    if (savingRef.current) return;
    savingRef.current = true;
    const mine = side === 'interests' ? interests : dislikes;
    const on = !mine.includes(code);
    const nextMine = on ? [...mine, code] : mine.filter((c) => c !== code);

    const other = side === 'interests' ? dislikes : interests;
    const nextOther = on ? other.filter((c) => c !== code) : other;

    const next =
      side === 'interests'
        ? { interests: nextMine, dislikes: nextOther }
        : { interests: nextOther, dislikes: nextMine };

    setInterests(next.interests);
    setDislikes(next.dislikes);
    setSave('saving');

    try {
      if (side === 'interests') await updateInterests(next.interests);
      else await updateDislikes(next.dislikes);
      setSave('saved');
    } catch {
      try {
        const [currentInterests, currentDislikes] = await Promise.all([
          fetchInterests(),
          fetchDislikes(),
        ]);
        setInterests(currentInterests?.topicCodes ?? []);
        setDislikes(currentDislikes?.topicCodes ?? []);
        setSave('failed');
      } catch {
        setState('failed');
      }
    } finally {
      savingRef.current = false;
    }
  };

  const status =
    save === 'saving'
      ? interestPane.saving
      : save === 'saved'
        ? interestPane.saved
        : save === 'failed'
          ? interestPane.saveFailed
          : null;

  return (
    <>
      <PaneHead
        eyebrow={interestPane.eyebrow}
        title={interestPane.title}
        blurb={interestPane.blurb}
      />

      {state === 'loading' && <p className={styles.notice}>{interestPane.loading}</p>}
      {state === 'signedOut' && <p className={styles.notice}>{interestPane.signedOut}</p>}
      {state === 'failed' && <p className={styles.notice}>{interestPane.failed}</p>}

      {state === 'ready' && (
        <>
          <TopicList
            side="interests"
            label={interestPane.interestsLabel}
            hint={interestPane.interestsHint}
            picked={interests}
            disabled={save === 'saving'}
            onToggle={handleToggle}
          />

          <TopicList
            side="dislikes"
            label={interestPane.dislikesLabel}
            hint={interestPane.dislikesHint}
            picked={dislikes}
            disabled={save === 'saving'}
            onToggle={handleToggle}
          />

          <p className={styles.rule}>{interestPane.exclusive}</p>

          {/* 저장 상태는 한 줄로만. 매 클릭이 저장이라 버튼이 없다. */}
          <p className={styles.status} data-state={save ?? ''} role="status" aria-live="polite">
            {status}
          </p>
        </>
      )}
    </>
  );
}

/** 일곱 분야를 두 열로. 체크박스가 라벨 안에 있어 카드 전체가 클릭 영역이다. */
function TopicList({ side, label, hint, picked, disabled, onToggle }) {
  return (
    <>
      <SectionHead label={label} hint={hint} count={interestPane.count(picked.length)} />
      <div className={styles.grid} role="group" aria-label={label}>
        {TOPICS.map((topic) => {
          const on = picked.includes(topic.topicCode);
          return (
            <label
              key={topic.topicCode}
              className={`${styles.card} ${on ? styles.cardPicked : ''} ${disabled ? styles.cardDisabled : ''}`}
            >
              <span className={styles.cardTitle}>{topic.topicName}</span>
              <input
                type="checkbox"
                className={styles.box}
                checked={on}
                disabled={disabled}
                onChange={() => onToggle(side, topic.topicCode)}
              />
              <span className={styles.cardScope}>{interestPane.scope[topic.topicCode]}</span>
            </label>
          );
        })}
      </div>
    </>
  );
}
