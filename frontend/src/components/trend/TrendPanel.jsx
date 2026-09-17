import { useState } from 'react'
import { panelCopy } from '../../data/trend'
import styles from './TrendPanel.module.css'

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
 * The bookmarks are real toggles but local ones — `PATCH /users/me/bookmarks/articles` is
 * where they will go, and it needs a signed-in user, which this screen does not require.
 * `상세 보기` has nothing behind it yet either: there is no article route to send anyone
 * to, and the response carries no link of its own.
 */
export function TrendPanel({ data, state, title, open, onClose, onMore, id }) {
  const [saved, setSaved] = useState({})

  const articles = data?.articles ?? []

  return (
    <aside
      id={id}
      className={`${styles.panel} ${open ? '' : styles.panelClosed}`}
      aria-label={title}
      inert={!open}
    >
      <button type="button" className={styles.close} onClick={onClose} aria-label={panelCopy.close}>
        ✕
      </button>

      <div className={styles.head}>
        <span className={styles.eyebrow}>RELATED ARTICLES</span>
        <h2 className={styles.title}>
          {title}
          <span className={styles.titleStar} aria-hidden>
            ★
          </span>
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
          <li key={article.articleId} className={styles.item}>
            <div className={styles.itemHead}>
              <span className={styles.source}>
                {article.organizationName} · {formatDate(article.publishedAt)}
              </span>
              <button
                type="button"
                className={`${styles.bookmark} ${(saved[article.articleId] ?? article.bookmarked) ? styles.bookmarkOn : ''}`}
                aria-pressed={saved[article.articleId] ?? article.bookmarked}
                aria-label={
                  (saved[article.articleId] ?? article.bookmarked)
                    ? panelCopy.unsave
                    : panelCopy.save
                }
                onClick={() =>
                  setSaved((was) => ({
                    ...was,
                    [article.articleId]: !(was[article.articleId] ?? article.bookmarked),
                  }))
                }
              >
                <svg className={styles.bookmarkIcon} viewBox="0 0 13 17" aria-hidden>
                  <path
                    d="M1 1.6A.6.6 0 0 1 1.6 1h9.8a.6.6 0 0 1 .6.6v14.2l-5.5-3.6L1 15.8z"
                    fill={(saved[article.articleId] ?? article.bookmarked) ? 'currentColor' : 'none'}
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>

            <p className={styles.headline}>{article.title}</p>

            <button type="button" className={styles.detail}>
              {panelCopy.detail} →
            </button>
          </li>
        ))}
      </ul>

      {state === 'ready' && data?.hasNext && (
        <button type="button" className={styles.more} onClick={onMore}>
          {panelCopy.more}
        </button>
      )}
    </aside>
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
