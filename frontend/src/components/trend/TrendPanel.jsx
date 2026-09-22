import { useEffect, useRef, useState } from 'react'
import { fetchArticleDetail, recordArticleRead } from '../../api/articles'
import { fetchNodeDetail } from '../../api/trend'
import { panelCopy } from '../../data/trend'
import { useArticleSummary } from '../../hooks/useArticleSummary'
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
 * 하고, 없이 누르면 요청 없이 한 줄 안내만 뜬다(useBookmark).
 *
 * 기사를 여는 일은 별도 화면이 아니라 줄 안에서 펼치는 것으로 끝낸다. 기사 상세 API 가
 * 주는 것이 제목·언론사·발행일·원문 주소뿐이고 그 셋은 이 목록에 이미 있어서, 화면을 하나
 * 더 띄워 봐야 원문 링크 하나가 늘 뿐이다. 펼치면 요약을 만들고(POST /summary) 열람으로
 * 기록한다(POST /reads) — 자세한 조건은 <ArticleRow>.
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

/**
 * 기사 한 줄. 책갈피는 이 기사의 북마크 — 줄마다 자기 상태를 가진다.
 *
 * 요약은 펼쳐야 가져온다. `POST /articles/{id}/summary` 는 저장된 요약이 없으면 그 자리에서
 * 만들기 때문에, 목록에 뜨는 것만으로 부르면 아무도 읽지 않을 요약까지 만들게 된다. 펼치기를
 * 누른 것만 만든다 — 사용자가 읽겠다고 한 것과 생성 비용이 같은 자리에 온다.
 *
 * 한 번 받아온 요약은 접었다 펴도 다시 부르지 않는다(훅이 들고 있다).
 */
function ArticleRow({ article }) {
  const { on, pending, hint, toggle } = useBookmark({
    kind: 'article',
    key: article.articleId,
    initial: article.bookmarked,
    copy: ARTICLE_COPY,
  })
  const account = useSession()
  const [open, setOpen] = useState(false)
  // 원문 주소는 관련 기사 목록에 없고 상세에만 있다. 그래서 펼칠 때 둘을 나란히 부른다 —
  // 서로 기다리지 않으므로 요약이 실패해도 원문 링크는 뜬다.
  const [origin, setOrigin] = useState(null)
  const { summary, state, load, retry } = useArticleSummary(article.articleId)
  // 이 기사를 이미 읽음으로 남겼는지. 접었다 펴도 다시 보내지 않기 위한 표시다.
  const recorded = useRef(false)
  const bodyId = `article-summary-${article.articleId}`

  useEffect(() => {
    if (!open || origin) return
    const controller = new AbortController()
    fetchArticleDetail(article.articleId, { signal: controller.signal })
      .then((detail) => setOrigin(detail?.originalUrl ?? null))
      .catch(() => {})
    return () => controller.abort()
  }, [open, origin, article.articleId])

  /**
   * 펼치는 것이 이 앱의 "기사를 읽었다"이다.
   *
   * 명세가 말하는 상세 화면이 아직 없어서, 목록에서 내용을 펼치는 이 동작이 그 자리를
   * 대신한다. 목록에 떠 있는 것만으로는 읽었다고 할 수 없고, 펼친 것은 읽겠다는 뜻이다.
   *
   * effect 가 아니라 클릭에서 보낸다 — StrictMode 는 effect 를 두 번 실행하므로
   * 열람 횟수를 증가시키는 요청을 거기 두면 개발 모드에서 두 배가 된다.
   * 접었다 펴는 것은 새 열람이 아니므로 ref 로 한 번만 보낸다.
   * 비로그인은 보내지 않는다 — 어차피 401 로 거절될 요청이다.
   */
  const expand = () => {
    const next = !open
    setOpen(next)
    if (!next) return

    load()
    if (account && !recorded.current) {
      recorded.current = true
      recordArticleRead(article.articleId).catch(() => {
        // 읽음 기록은 화면이 하는 일의 곁가지다. 실패해도 요약 읽기를 방해하지 않는다.
        recorded.current = false
      })
    }
  }

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

      <button
        type="button"
        className={styles.detail}
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={expand}
      >
        {open ? panelCopy.summaryClose : panelCopy.summaryOpen}
        <span className={styles.detailCaret} aria-hidden>
          {open ? '▴' : '▾'}
        </span>
      </button>

      <div className={styles.summaryBody} id={bodyId} hidden={!open}>
        {summary ? (
          <p className={styles.summaryText}>{summary}</p>
        ) : (
          <p className={styles.summaryNote} role="status">
            {summaryNote(state)}
          </p>
        )}

        {(state === 'failed' || state === 'pending') && (
          <button type="button" className={styles.summaryRetry} onClick={retry}>
            {panelCopy.summaryRetry}
          </button>
        )}

        {origin && (
          <a className={styles.origin} href={origin} target="_blank" rel="noreferrer">
            {panelCopy.origin} ↗
          </a>
        )}
      </div>
    </li>
  )
}

/** 요약이 비어 있는 이유를 화면 말로 옮긴다. */
function summaryNote(state) {
  if (state === 'loading') return panelCopy.summaryLoading
  if (state === 'pending') return panelCopy.summaryPending
  if (state === 'unavailable') return panelCopy.summaryUnavailable
  if (state === 'failed') return panelCopy.summaryFailed
  return panelCopy.summaryNone
}

/** `2024-01-11T09:52:15+09:00` → `1월 11일`. Read out of the string so the server's own
 *  offset is kept rather than shifted into this machine's zone. */
function formatDate(value) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(value ?? '')
  if (!match) return value ?? ''
  const [, month, day] = match
  return `${Number(month)}월 ${Number(day)}일`
}
