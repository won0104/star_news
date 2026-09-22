import { useEffect, useState } from 'react'
import { fetchArticleDetail, generateArticleSummary } from '../../api/articles'
import { fetchArticleBookmarks, fetchNodeBookmarks, setArticleBookmark } from '../../api/bookmarks'
import { fetchNodeArticles, fetchNodeDetail } from '../../api/trend'
import { nodeTypeLabels, subtypeLabels } from '../../data/trendNeighbors'
import { savedCopy } from '../../data/world'
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
 * 비어 있을 때 표본을 깔던 것은 걷어냈다. 북마크를 넣고 뺄 길이 없던 동안의 임시였고, 지금은
 * 트렌드·나의 기록·이 화면 모두에서 담고 뺄 수 있다. 오히려 마지막 하나를 해제하면 표본
 * 세 건이 나타나 지운 것이 되살아난 것처럼 보였다. 빈 목록은 빈 목록이라고 말한다.
 */
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

  /**
   * 해제한 기사를 목록에서 뺀다.
   *
   * 다른 화면의 책갈피와 달리 여기서는 자리에 남겨 둘 수 없다. 이 목록의 뜻 자체가 "저장한
   * 것"이라, 해제한 기사가 그대로 있으면 목록이 제 이름과 어긋난다.
   *
   * 왼쪽에 펼쳐 둔 것이 그 기사였다면 함께 닫는다 — 목록에 없는 것을 읽고 있는 상태가 된다.
   * `totalCount` 같은 집계는 서버가 주는 값이라 손대지 않는다. 다시 불러오면 맞춰진다.
   */
  const removeArticle = (articleId) => {
    setList((was) =>
      was ? { ...was, items: was.items.filter((item) => item.articleId !== articleId) } : was,
    )
    setChosen((was) => (was?.articleId === articleId ? null : was))
  }

  const items = list?.items ?? []
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
            <ArticleDetail key={chosen.articleId} article={chosen} />
          )
        ) : (
          <p className={styles.placeholder}>{savedCopy.pickOne}</p>
        )}
      </div>

      {/* ── 오른쪽: 목록 ── */}
      <div className={styles.rightPage}>
        {state === 'loading' && <p className={styles.notice}>{savedCopy.loading}</p>}

        {state === 'signedOut' && (
          <div className={styles.notice}>
            <p>{savedCopy.signedOut}</p>
            <p className={styles.noticeHint}>{savedCopy.signedOutHint}</p>
          </div>
        )}

        {state === 'failed' && <p className={styles.notice}>{savedCopy.failed}</p>}

        {state === 'ready' && items.length === 0 && (
          <div className={styles.notice}>
            <p>{copy.empty}</p>
            <p className={styles.noticeHint}>{copy.emptyHint}</p>
          </div>
        )}

        {state === 'ready' && items.length > 0 && (
          <>
            <ul className={styles.list}>
              {items.map((item) => (
                <li key={keyOf(item)} className={styles.row}>
                  <button
                    type="button"
                    className={`${styles.rowPick} ${
                      chosen && keyOf(chosen) === keyOf(item) ? styles.rowOn : ''
                    }`}
                    aria-current={chosen && keyOf(chosen) === keyOf(item) ? 'true' : undefined}
                    onClick={() => setChosen(item)}
                  >
                    <small>
                      {kind === 'articles' && `${item.publisher} · `}
                      {savedCopy.savedAt(formatDate(item.bookmarkedAt))}
                    </small>
                    <strong>{kind === 'events' ? item.name : item.title}</strong>
                  </button>

                  {kind === 'articles' && (
                    <UnsaveButton
                      article={item}
                      onRemoved={() => removeArticle(item.articleId)}
                    />
                  )}
                </li>
              ))}
            </ul>

            {list?.hasNext && (
              <button type="button" className={styles.more} onClick={more}>
                {savedCopy.more}
              </button>
            )}
          </>
        )}
      </div>
    </>
  )
}

/**
 * 행 오른쪽의 북마크 해제.
 *
 * 되돌리기(undo)를 두지 않는 대신 응답을 기다렸다가 지운다. 다른 화면의 책갈피는 낙관적으로
 * 먼저 칠하지만(useBookmark), 여기서 낙관적으로 하면 실패했을 때 지운 행을 원래 자리에 되살려
 * 놓아야 한다 — 그 사이 `더 보기`로 목록이 늘어났을 수도 있어 자리를 장담할 수 없다.
 * 요청 하나 기다리는 값이 그 복잡함보다 싸다.
 *
 * 실패는 행 안에 한 줄로 남긴다. 행이 사라지지 않았다는 것 자체가 이미 절반의 안내다.
 */
function UnsaveButton({ article, onRemoved }) {
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(false)

  const unsave = () => {
    if (pending) return
    setPending(true)
    setFailed(false)
    setArticleBookmark(article.articleId, false)
      .then((confirmed) => {
        // API 가 확정 상태를 돌려준다. 여전히 담긴 것으로 온다면 해제되지 않은 것이므로
        // 행을 지우면 안 된다 — 다시 불러오면 되살아나 사라졌다 나타나는 꼴이 된다.
        if (confirmed) {
          setFailed(true)
          setPending(false)
          return
        }
        onRemoved()
      })
      .catch(() => {
        setFailed(true)
        setPending(false)
      })
  }

  return (
    <>
      <button
        type="button"
        className={styles.unsave}
        aria-label={`${article.title} ${savedCopy.unsave}`}
        title={savedCopy.unsave}
        disabled={pending}
        onClick={unsave}
      >
        <svg viewBox="0 0 13 17" aria-hidden>
          <path
            d="M1 1.6A.6.6 0 0 1 1.6 1h9.8a.6.6 0 0 1 .6.6v14.2l-5.5-3.6L1 15.8z"
            fill="currentColor"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {failed && (
        <small className={styles.unsaveFailed} role="status">
          {savedCopy.unsaveFailed}
        </small>
      )}
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

/** 요약이 만들어지길 기다릴 때 다시 물어보는 간격과 횟수. */
const SUMMARY_RETRY_MS = 2500
const SUMMARY_MAX_TRIES = 3

/**
 * 저장한 기사 하나.
 *
 * The bookmark row already carries a summary, so the title and the text appear at once;
 * `GET /articles/{id}` is what adds the original link, and it fills in when it arrives.
 * Keyed by the caller on `articleId`, so choosing another row remounts this rather than
 * letting a slow response land on the wrong article.
 *
 * 상세와 요약은 두 요청이고, 서로를 기다리지 않는다. 상세가 실패해도 요약은 뜨고, 요약이
 * 502 로 죽어도 제목·발행일·원문 링크는 그대로 있다 — 둘을 한 체인으로 묶으면 한쪽 실패가
 * 아무 상관 없는 다른 쪽까지 지운다.
 *
 * 요약이 없는 이유는 한 가지가 아니다. 본문이 없어 만들 수 없는 것(422)과 만들다 실패한
 * 것(502)과 남이 만드는 중인 것(PROCESSING)은 읽는 사람이 할 일이 다르므로 따로 말한다.
 */
function ArticleDetail({ article }) {
  const [detail, setDetail] = useState(null)
  // 북마크 행이 이미 들고 있는 요약이 출발점이다. 있으면 생성을 부르지 않는다.
  const [summary, setSummary] = useState(article.summary ?? null)
  const [summaryState, setSummaryState] = useState(article.summary ? 'ready' : 'loading')

  useEffect(() => {
    const controller = new AbortController()
    fetchArticleDetail(article.articleId, { signal: controller.signal })
      .then(setDetail)
      .catch(() => {})
    return () => controller.abort()
  }, [article])

  useEffect(() => {
    if (article.summary) return
    const controller = new AbortController()
    let timer = null
    let tries = 0
    // abort 만으로는 부족하다. 응답이 abort 보다 먼저 도착하면 then 이 그대로 돌아
    // 언마운트된 뒤에도 다음 재시도를 걸어버린다 — 그 체인을 끊는 플래그다.
    let dropped = false

    const ask = () => {
      tries += 1
      generateArticleSummary(article.articleId, { signal: controller.signal })
        .then((result) => {
          if (dropped) return
          if (result?.summaryStatus === 'PROCESSING') {
            setSummaryState('pending')
            // 서버가 중복 생성을 막으므로 다시 물어도 GMS 를 두 번 부르지 않는다.
            if (tries < SUMMARY_MAX_TRIES) timer = setTimeout(ask, SUMMARY_RETRY_MS)
            return
          }
          setSummary(result?.summary ?? null)
          setSummaryState(result?.summary ? 'ready' : 'none')
        })
        .catch((error) => {
          if (dropped || error?.name === 'AbortError') return
          setSummaryState(error?.status === 422 ? 'unavailable' : 'failed')
        })
    }
    ask()

    return () => {
      dropped = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [article])

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
        summaryState !== 'loading' && (
          <p className={styles.summaryNone}>{summaryNote(summaryState)}</p>
        )
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
function summaryNote(state) {
  if (state === 'pending') return savedCopy.summaryPending
  if (state === 'unavailable') return savedCopy.summaryUnavailable
  if (state === 'failed') return savedCopy.summaryFailed
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
