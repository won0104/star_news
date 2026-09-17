import { useEffect, useState } from 'react'
import { fetchArticleDetail } from '../../api/articles'
import { fetchArticleBookmarks, fetchNodeBookmarks } from '../../api/bookmarks'
import { fetchNodeArticles, fetchNodeDetail } from '../../api/trend'
import { nodeTypeLabels, subtypeLabels } from '../../data/trendNeighbors'
import { savedArticlesSample, savedCopy } from '../../data/world'
import styles from './SavedPane.module.css'

/**
 * 저장한 사건 / 저장한 기사 — 한 화면의 두 얼굴.
 *
 * Right page is the list and it scrolls; left page is whatever is chosen on it. That way
 * the thing being read stays put while the list moves under the reader's hand, which is
 * the opposite of a list that pushes its own detail down the page.
 *
 * `kind` is the only difference between the two pages, and it changes three things: which
 * endpoint fills the list, what a row shows, and what the left page can say. Articles
 * already carry their summary in the bookmark row, so choosing one costs no request;
 * events carry only a name, so choosing one fetches its detail and its articles.
 *
 * Bookmarks need a token. A signed-out reader gets 401, which is not an error to report
 * but a state to explain — the screen says so.
 *
 * Nothing can be bookmarked yet: the write endpoints are not wired here, and there is no
 * public way to reach an article id to bookmark in the first place. So rather than leave
 * the page empty while it is being designed, an empty or refused load falls back to the
 * sample in data/world.js and says so on the page. Set SAMPLE_WHEN_EMPTY to false, or
 * delete it and the `sample` branches, once real bookmarks are landing.
 */
const SAMPLE_WHEN_EMPTY = true
export function SavedPane({ kind }) {
  const copy = savedCopy[kind]
  const [list, setList] = useState(null)
  const [state, setState] = useState('loading')
  const [chosen, setChosen] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    const load =
      kind === 'events'
        ? fetchNodeBookmarks({ nodeType: 'EVENT', signal: controller.signal })
        : fetchArticleBookmarks({ signal: controller.signal })

    load
      .then((payload) => {
        setList(payload)
        setState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setState(error?.status === 401 ? 'signedOut' : 'failed')
      })

    return () => controller.abort()
  }, [kind])

  const more = () => {
    const cursor = list?.nextCursor
    if (!cursor) return
    const load =
      kind === 'events'
        ? fetchNodeBookmarks({ nodeType: 'EVENT', cursor })
        : fetchArticleBookmarks({ cursor })

    load
      .then((payload) =>
        setList((was) => ({ ...payload, items: [...(was?.items ?? []), ...payload.items] })),
      )
      .catch(() => setState('failed'))
  }

  const live = list?.items ?? []
  // 로그인 전이거나, 로그인했지만 저장한 것이 없거나, 불러오지 못했을 때.
  const sample =
    SAMPLE_WHEN_EMPTY && kind === 'articles' && state !== 'loading' && live.length === 0
  const source = sample ? savedArticlesSample : list
  const items = source?.items ?? []
  const keyOf = (item) => (kind === 'events' ? item.nodeId : item.articleId)

  return (
    <>
      {/* ── 왼쪽: 고른 하나 ── */}
      <div className={styles.leftPage}>
        <header className={styles.head}>
          <span>{kind === 'events' ? 'SAVED EVENTS' : 'SAVED ARTICLES'}</span>
          <h1>{copy.title}</h1>
          <p>{copy.blurb}</p>
        </header>

        {chosen ? (
          kind === 'events' ? (
            <EventDetail key={chosen.nodeId} node={chosen} />
          ) : (
            <ArticleDetail key={chosen.articleId} article={chosen} sample={sample} />
          )
        ) : (
          <p className={styles.placeholder}>{savedCopy.pickOne}</p>
        )}
      </div>

      {/* ── 오른쪽: 목록 ── */}
      <div className={styles.rightPage}>
        {state === 'loading' && <p className={styles.notice}>{savedCopy.loading}</p>}

        {!sample && state === 'signedOut' && (
          <div className={styles.notice}>
            <p>{savedCopy.signedOut}</p>
            <p className={styles.noticeHint}>{savedCopy.signedOutHint}</p>
          </div>
        )}

        {!sample && state === 'failed' && <p className={styles.notice}>{savedCopy.failed}</p>}

        {!sample && state === 'ready' && items.length === 0 && (
          <div className={styles.notice}>
            <p>{copy.empty}</p>
            <p className={styles.noticeHint}>{copy.emptyHint}</p>
          </div>
        )}

        {(sample || state === 'ready') && items.length > 0 && (
          <>
            <ul className={styles.list}>
              {items.map((item) => (
                <li key={keyOf(item)}>
                  <button
                    type="button"
                    className={chosen && keyOf(chosen) === keyOf(item) ? styles.rowOn : ''}
                    aria-current={chosen && keyOf(chosen) === keyOf(item) ? 'true' : undefined}
                    onClick={() => setChosen(item)}
                  >
                    <small>
                      {kind === 'articles' && `${item.publisher} · `}
                      {savedCopy.savedAt(formatDate(item.bookmarkedAt))}
                    </small>
                    <strong>{kind === 'events' ? item.name : item.title}</strong>
                  </button>
                </li>
              ))}
            </ul>

            {source?.hasNext && (
              <button type="button" className={styles.more} onClick={more}>
                {savedCopy.more}
              </button>
            )}

            {sample && <p className={styles.sampleNote}>{savedCopy.sampleNote}</p>}
          </>
        )}
      </div>
    </>
  )
}

/**
 * 저장한 사건 하나.
 *
 * The bookmark row carries only a name, so the detail and the article list are fetched
 * here. Keyed by the caller on `nodeId`, so choosing another event remounts this and the
 * two requests start clean rather than racing the ones still in flight.
 */
function EventDetail({ node }) {
  const [detail, setDetail] = useState(null)
  const [articles, setArticles] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchNodeDetail(node.nodeType, node.nodeId, { signal: controller.signal })
      .then(setDetail)
      .catch(() => {})
    fetchNodeArticles(node.nodeType, node.nodeId, { size: 5, signal: controller.signal })
      .then(setArticles)
      .catch(() => {})
    return () => controller.abort()
  }, [node])

  return (
    <div className={styles.detail}>
      <span className={styles.kind}>{nodeTypeLabels[node.nodeType] ?? node.nodeType}</span>
      <h2>{node.name}</h2>

      <dl className={styles.facts}>
        {detail?.type && (
          <div>
            <dt>세부 유형</dt>
            <dd>{subtypeLabels[detail.type] ?? detail.type}</dd>
          </div>
        )}
        {detail?.time && (
          <div>
            <dt>발생</dt>
            <dd>{formatDate(detail.time)}</dd>
          </div>
        )}
        <div>
          <dt>저장</dt>
          <dd>{formatDate(node.bookmarkedAt)}</dd>
        </div>
      </dl>

      {articles?.articles?.length > 0 && (
        <section className={styles.related}>
          <h3>
            {savedCopy.relatedArticles}
            <b>{articles.totalCount}</b>
          </h3>
          <ul>
            {articles.articles.map((article) => (
              <li key={article.articleId}>
                <small>
                  {article.organizationName} · {formatDate(article.publishedAt)}
                </small>
                <p>{article.title}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/**
 * 저장한 기사 하나.
 *
 * The bookmark row already carries a summary, so the title and the text appear at once;
 * `GET /articles/{id}` is what adds the original link and the summary's status, and it
 * fills in when it arrives. Keyed by the caller on `articleId`, so choosing another row
 * remounts this rather than letting a slow response land on the wrong article.
 *
 * `summaryStatus` decides what to say when there is no text: not asked for, still being
 * made, or failed are three different things to a reader, and `summary === null` alone
 * cannot tell them apart.
 */
function ArticleDetail({ article, sample }) {
  const [detail, setDetail] = useState(sample ? article : null)

  useEffect(() => {
    if (sample) return
    const controller = new AbortController()
    fetchArticleDetail(article.articleId, { signal: controller.signal })
      .then(setDetail)
      .catch(() => {})
    return () => controller.abort()
  }, [article, sample])

  const summary = detail?.summary ?? article.summary
  const status = detail?.summaryStatus
  const url = detail?.originalUrl

  return (
    <div className={styles.detail}>
      <span className={styles.kind}>{article.publisher}</span>
      <h2>{article.title}</h2>

      <dl className={styles.facts}>
        <div>
          <dt>발행</dt>
          <dd>{formatDate(article.publishedAt)}</dd>
        </div>
        <div>
          <dt>저장</dt>
          <dd>{formatDate(article.bookmarkedAt)}</dd>
        </div>
      </dl>

      {summary ? (
        <p className={styles.summary}>{summary}</p>
      ) : (
        status && <p className={styles.summaryNone}>{summaryNote(status)}</p>
      )}

      {url && (
        <a className={styles.origin} href={url} target="_blank" rel="noreferrer">
          {savedCopy.origin} ↗
        </a>
      )}
    </div>
  )
}

/** 요약이 비어 있는 이유를 화면 말로 옮긴다. */
function summaryNote(status) {
  if (status === 'PROCESSING') return savedCopy.summaryPending
  if (status === 'FAILED') return savedCopy.summaryFailed
  return savedCopy.summaryNone
}

/** `2026-09-16T18:00:00+09:00` → `9월 16일`. Read out of the string so the server's own
 *  offset is kept rather than shifted into this machine's zone. */
function formatDate(value) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(value ?? '')
  if (!match) return value ?? ''
  const [, month, day] = match
  return `${Number(month)}월 ${Number(day)}일`
}
