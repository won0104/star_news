import { useState } from 'react';
import { interestPane, nodeKinds, settingsCopy } from '../../data/settings';
import { addNode, removeNode, toggleTopic, useSettingsValues } from '../../store/settings';
import { PaneFooter, PaneHead, SectionHead } from './PaneChrome';
import paneStyles from './PaneChrome.module.css';
import styles from './InterestPane.module.css';

/**
 * 관심 관리 — Figma V3 / Overlay / Settings / Interest.
 *
 * Two sections: the topics that widen what gets recommended, and the nodes that are
 * followed through the graph. Both counts in the section headers are derived, never
 * stored, so they cannot drift from the lists under them.
 *
 * A topic is a real checkbox inside a label, so the whole card is a hit target and the
 * control keeps its native semantics and keyboard behaviour; `accent-color` is all it
 * takes to make it brass.
 */
export function InterestPane() {
  const { topics, nodes } = useSettingsValues();
  const [draft, setDraft] = useState('');

  const submitDraft = (event) => {
    event.preventDefault();
    addNode(draft);
    setDraft('');
  };

  return (
    <>
      <PaneHead
        eyebrow={interestPane.eyebrow}
        title={interestPane.title}
        blurb={interestPane.blurb}
      />

      <SectionHead
        label={interestPane.topicsLabel}
        hint={interestPane.topicsHint}
        count={interestPane.topicsCount(topics.length)}
      />

      <div className={styles.grid}>
        {interestPane.topics.map((topic) => {
          const picked = topics.includes(topic.id);
          return (
            <label
              key={topic.id}
              className={`${styles.card} ${picked ? styles.cardPicked : ''}`}
            >
              <span className={styles.cardTitle}>{topic.label}</span>
              <input
                type="checkbox"
                className={styles.box}
                checked={picked}
                onChange={() => toggleTopic(topic.id)}
              />
              <span className={styles.cardScope}>{topic.scope}</span>
            </label>
          );
        })}
      </div>

      <SectionHead
        label={interestPane.nodesLabel}
        hint={interestPane.nodesHint}
        count={interestPane.nodesCount(nodes.length)}
      />

      <form className={styles.addRow} onSubmit={submitDraft}>
        <input
          type="text"
          className={styles.input}
          placeholder={interestPane.nodePlaceholder}
          aria-label={interestPane.nodesLabel}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" className={paneStyles.primary}>
          {interestPane.nodeAdd}
        </button>
      </form>

      <div className={styles.suggested}>
        <p className={styles.suggestedLabel}>{interestPane.suggestedLabel}</p>
        {interestPane.suggested
          .filter((label) => !nodes.some((node) => node.label === label))
          .map((label) => (
            <button
              key={label}
              type="button"
              className={styles.chip}
              onClick={() => addNode(label)}
            >
              + {label}
            </button>
          ))}
      </div>

      <div className={styles.grid}>
        {nodes.map((node) => {
          const kind = nodeKinds[node.kind];
          return (
            <div key={node.id} className={styles.node}>
              <span className={`${styles.dot} ${styles[kind.tone]}`} aria-hidden />
              <span className={styles.nodeTitle}>{node.label}</span>
              <span className={styles.kind}>{kind.label}</span>
              <button
                type="button"
                className={styles.remove}
                aria-label={`${node.label} ${interestPane.nodeRemove}`}
                onClick={() => removeNode(node.id)}
              >
                <svg viewBox="0 0 24 24" aria-hidden focusable="false">
                  <path d="M6 6 18 18M18 6 6 18" />
                </svg>
              </button>
              <span className={styles.nodeMeta}>
                {interestPane.nodeMeta(node.articles, node.concepts)}
              </span>
            </div>
          );
        })}
      </div>

      <PaneFooter>
        <button type="button" className={paneStyles.primary}>
          {settingsCopy.save}
        </button>
      </PaneFooter>
    </>
  );
}
