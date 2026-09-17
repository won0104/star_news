import { subtypeLabels, trendSkyExpandCopy } from '../../data/trendNeighbors'
import { nodeTypeLabels } from '../../data/trendNeighbors'
import styles from './NodeDetailPanel.module.css'

/**
 * `GET /graphs/nodes/{nodeType}/{nodeKey}` 한 건 — 인물·기관이나 발언을 눌렀을 때 뜨는 카드.
 *
 * A card in the corner of the field rather than a full panel: an entity or a statement is
 * a few lines — a name, its kind, and whether it is bookmarked — and the reason for
 * pressing one is to know what it is without losing the constellation you are reading.
 * Events keep the wider article panel, because those have a list behind them.
 *
 * `type` and `time` are nullable by contract, so each line only appears when its value
 * came back; a card with one line is a valid answer rather than a broken one.
 */
export function NodeDetailPanel({ node, state, onClose }) {
  if (!node && state === 'idle') return null

  return (
    <aside className={styles.card} aria-live="polite">
      <button type="button" className={styles.close} onClick={onClose} aria-label={trendSkyExpandCopy.close}>
        ✕
      </button>

      {state === 'loading' && <p className={styles.status}>{trendSkyExpandCopy.detailLoading}</p>}

      {state === 'failed' && <p className={styles.status}>{trendSkyExpandCopy.detailFailed}</p>}

      {state === 'ready' && node && (
        <>
          <span className={styles.eyebrow}>
            {nodeTypeLabels[node.nodeType] ?? node.nodeType}
          </span>
          <h3 className={styles.title}>{node.title}</h3>

          <dl className={styles.facts}>
            {node.type && (
              <div>
                <dt>세부 유형</dt>
                <dd>{subtypeLabels[node.type] ?? node.type}</dd>
              </div>
            )}
            {node.time && (
              <div>
                <dt>시각</dt>
                <dd>{formatTime(node.time)}</dd>
              </div>
            )}
            <div>
              <dt>즐겨찾기</dt>
              <dd>{node.bookmarked ? '등록됨' : '없음'}</dd>
            </div>
          </dl>
        </>
      )}
    </aside>
  )
}

/** `2026-09-16T18:00:00+09:00` → `9월 16일 18시`. Read out of the string so the server's
 *  own offset is kept rather than shifted into this machine's zone. */
function formatTime(value) {
  const match = /^\d{4}-(\d{2})-(\d{2})T(\d{2})/.exec(value)
  if (!match) return value
  const [, month, day, hour] = match
  return `${Number(month)}월 ${Number(day)}일 ${hour}시`
}
