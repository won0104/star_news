import { subtypeLabels, trendSkyExpandCopy } from '../../data/trendNeighbors'
import { nodeTypeLabels } from '../../data/trendNeighbors'
import { useBookmark } from '../../hooks/useBookmark'
import { useDraggableCard } from '../../hooks/useDraggableCard'
import styles from './NodeDetailPanel.module.css'

const BOOKMARK_COPY = {
  signIn: trendSkyExpandCopy.signInToBookmark,
  failed: trendSkyExpandCopy.bookmarkFailed,
}

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
 *
 * 즐겨찾기는 실제 토글이다 — `PATCH /users/me/bookmarks/nodes`. 상세 응답의 `bookmarked` 가
 * 초기값이고(비로그인이면 늘 false 로 온다), 카드는 호출한 쪽이 nodeKey 로 키를 걸어 Node
 * 가 바뀌면 새로 마운트되므로 토글 상태가 다른 Node 로 넘어가지 않는다.
 */
export function NodeDetailPanel({ id, node, state, onClose }) {
  const { cardRef, cardStyle, dragging, handleProps } = useDraggableCard()

  if (!node && state === 'idle') return null

  return (
    <aside
      ref={cardRef}
      id={id}
      className={styles.card}
      style={cardStyle}
      data-dragging={dragging}
      aria-live="polite"
      title="드래그하여 이동"
      {...handleProps}
    >
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
          </dl>

          <BookmarkRow node={node} />
        </>
      )}
    </aside>
  )
}

/** 카드 아래 한 줄 — ★ 버튼과, 필요할 때만 뜨는 안내. */
function BookmarkRow({ node }) {
  const { on, pending, hint, toggle } = useBookmark({
    kind: 'node',
    nodeType: node.nodeType,
    key: node.nodeKey,
    initial: node.bookmarked,
    copy: BOOKMARK_COPY,
  })

  return (
    <div className={styles.bookmarkRow}>
      <button
        type="button"
        className={`${styles.bookmarkButton} ${on ? styles.bookmarkOn : ''}`}
        aria-pressed={on}
        disabled={pending}
        onClick={(event) => {
          // 카드 전체가 드래그 손잡이다 — 버튼을 누른 것이 끌기로 시작되지 않게.
          event.stopPropagation()
          toggle()
        }}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <span aria-hidden>{on ? '★' : '☆'}</span>
        {on ? trendSkyExpandCopy.unbookmark : trendSkyExpandCopy.bookmark}
      </button>
      {hint && <p className={styles.hint} role="status">{hint}</p>}
    </div>
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
