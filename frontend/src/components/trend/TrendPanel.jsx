import { useEffect, useState } from 'react'
import { fetchNodeDetail } from '../../api/trend'
import { panelCopy } from '../../data/trend'
import { useBookmark } from '../../hooks/useBookmark'
import { useResizableCard } from '../../hooks/useResizableCard'
import { useSession } from '../../store/session'
import styles from './TrendPanel.module.css'

const RESIZE_CORNERS = [
  { direction: 'nw', label: '왼쪽 위 모서리에서 카드 크기 조절' },
  { direction: 'ne', label: '오른쪽 위 모서리에서 카드 크기 조절' },
  { direction: 'sw', label: '왼쪽 아래 모서리에서 카드 크기 조절' },
  { direction: 'se', label: '오른쪽 아래 모서리에서 카드 크기 조절' },
]

const ARTICLE_COPY = { signIn: panelCopy.signInToSave, failed: panelCopy.saveFailed }
const NODE_COPY = ARTICLE_COPY

/**
 * 중심 Node와 이어진 기사들 — `GET /graphs/nodes/{nodeType}/{nodeKey}/articles`.
 *
 * Opened by the centre star and closed from here, and it stays mounted either way: it
 * slides out rather than disappearing, and a panel that unmounted would have to animate
 * its own removal to do that. `inert` while it is closed, so what is off screen is also
 * out of the tab order.
 *
 * `totalCount` rather than `articles.length` beside the title: the list holds one page,
 * while the count is of everything behind the node.
 *
 * 저장은 둘이다. 제목 옆 ★ 은 이 사건(Node) 자체의 즐겨찾기 — `PATCH /bookmarks/nodes`,
 * 기사 줄의 책갈피는 그 기사의 북마크 — `PATCH /bookmarks/articles`. 둘 다 로그인이 필요
 * 하고, 없이 누르면 요청 없이 한 줄 안내만 뜬다(useBookmark). `상세 보기` has nothing
 * behind it yet: there is no article route to send anyone to.
 */
export function TrendPanel({ data, state, title, node, open, onClose, onMore, id }) {
  const { cardRef, cardStyle, dragging, resizing, positioned, handleProps, resizeHandleProps } =
    useResizableCard()

  const articles = data?.articles ?? []

  return (
    <aside
      ref={cardRef}
      id={id}
      className={`${styles.panel} ${open ? '' : styles.panelClosed}`}
      style={cardStyle}
      data-dragging={dragging}
      data-resizing={resizing}
      data-positioned={positioned}
      aria-label={title}
      inert={!open}
    >
      <button type="button" className={styles.close} onClick={onClose} aria-label={panelCopy.close}>
        ✕
      </button>

      <div className={styles.head} title="드래그하여 이동" {...handleProps}>
        <span className={styles.eyebrow}>RELATED ARTICLES</span>
        <h2 className={styles.title}>
          {title}
          {node?.nodeKey && <NodeStar key={node.nodeKey} node={node} open={open} />}
        </h2>
        {state === 'ready' && (
          <p className={styles.meta}>{panelCopy.countLabel(data?.totalCount ?? 0)}</p>
        )}
      </div>

      {state !== 'ready' && (
        <p className={styles.summary}>
          {state === 'failed' ? panelCopy.articlesFailed : panelCopy.articlesLoading}
        </p>
      )}

      {state === 'ready' && articles.length === 0 && (
        <p className={styles.summary}>{panelCopy.articlesEmpty}</p>
      )}

      <ul className={styles.list}>
        {articles.map((article) => (
          <ArticleRow key={article.articleId} article={article} />
        ))}
      </ul>

      {state === 'ready' && data?.hasNext && (
        <button type="button" className={styles.more} onClick={onMore}>
          {panelCopy.more}
        </button>
      )}

      {RESIZE_CORNERS.map(({ direction, label }) => (
        <button
          key={direction}
          type="button"
          className={`${styles.resizeHandle} ${styles[`resize${direction.toUpperCase()}`]}`}
          aria-label={label}
          title={`${label} — 방향키로도 조절할 수 있습니다`}
          {...resizeHandleProps(direction)}
        />
      ))}
    </aside>
  )
}

/**
 * 제목 옆 ★ — 가운데 사건의 즐겨찾기.
 *
 * 기사 목록 응답에는 사건 자체의 즐겨찾기 여부가 없어서, 패널이 열리고 로그인돼 있을 때
 * 상세(`GET /graphs/nodes/{type}/{key}`)를 한 번 받아 초기값으로 쓴다. 로그인 전에는 받지
 * 않는다 — 항상 false 로 오는 값이라 물을 이유가 없다. nodeKey 로 키가 걸려 사건이 바뀌면
 * 새로 마운트된다.
 */
function NodeStar({ node, open }) {
  const account = useSession()
  const [initial, setInitial] = useState(false)

  useEffect(() => {
    if (!open || !account) return undefined
    const controller = new AbortController()
    fetchNodeDetail(node.nodeType, node.nodeKey, { signal: controller.signal })
      .then((detail) => setInitial(!!detail?.bookmarked))
      .catch(() => {})
    return () => controller.abort()
  }, [open, account, node.nodeType, node.nodeKey])

  const { on, pending, hint, toggle } = useBookmark({
    kind: 'node',
    nodeType: node.nodeType,
    key: node.nodeKey,
    initial,
    copy: NODE_COPY,
  })

  return (
    <>
      <button
        type="button"
        className={`${styles.titleStar} ${on ? '' : styles.titleStarOff}`}
        aria-pressed={on}
        aria-label={on ? panelCopy.unsaveNode : panelCopy.saveNode}
        title={on ? panelCopy.unsaveNode : panelCopy.saveNode}
        disabled={pending}
        // 제목 줄은 드래그 손잡이다 — 별을 누른 것이 끌기로 시작되지 않게.
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation()
          toggle()
        }}
      >
        ★
      </button>
      {hint && <span className={styles.hint} role="status">{hint}</span>}
    </>
  )
}

/** 기사 한 줄. 책갈피는 이 기사의 북마크 — 줄마다 자기 상태를 가진다. */
function ArticleRow({ article }) {
  const { on, pending, hint, toggle } = useBookmark({
    kind: 'article',
    key: article.articleId,
    initial: article.bookmarked,
    copy: ARTICLE_COPY,
  })

  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        <span className={styles.source}>
          {article.organizationName} · {formatDate(article.publishedAt)}
        </span>
        <button
          type="button"
          className={`${styles.bookmark} ${on ? styles.bookmarkOn : ''}`}
          aria-pressed={on}
          aria-label={on ? panelCopy.unsave : panelCopy.save}
          disabled={pending}
          onClick={toggle}
        >
          <svg className={styles.bookmarkIcon} viewBox="0 0 13 17" aria-hidden>
            <path
              d="M1 1.6A.6.6 0 0 1 1.6 1h9.8a.6.6 0 0 1 .6.6v14.2l-5.5-3.6L1 15.8z"
              fill={on ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <p className={styles.headline}>{article.title}</p>
      {hint && <p className={styles.hint} role="status">{hint}</p>}

      <button type="button" className={styles.detail}>
        {panelCopy.detail} →
      </button>
    </li>
  )
}

/** `2024-01-11T09:52:15+09:00` → `1월 11일`. Read out of the string so the server's own
 *  offset is kept rather than shifted into this machine's zone. */
function formatDate(value) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(value ?? '')
  if (!match) return value ?? ''
  const [, month, day] = match
  return `${Number(month)}월 ${Number(day)}일`
}
