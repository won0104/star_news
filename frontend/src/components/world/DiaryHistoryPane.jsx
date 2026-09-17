import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useSearchParams } from 'react-router-dom'
import { historyGraph, historyOverview, historyStories } from '../../data/history'
import { useSettingsValues } from '../../store/settings'
import { DiaryShell } from './DiaryShell'
import { HistoryPane } from './HistoryPane'
import styles from './DiaryHistoryPane.module.css'

const HistoryPlanet = lazy(() => import('./HistoryPlanet'))
const BOOKMARK_ASSET = '/assets/history/bookmarks'
const EVENTS_PER_PAGE = 3

const TONE_CLASS = {
  rose: 'toneRose',
  gold: 'toneGold',
  mint: 'toneMint',
  peach: 'tonePeach',
  violet: 'toneViolet',
  cyan: 'toneCyan',
  blue: 'toneBlue',
}

function findEvent(node) {
  if (!node?.localContext) return null
  return (
    historyStories
      .find((item) => item.topicCode === node.topicCode)
      ?.stories.find((story) => story.id === node.localContext.storyId)
      ?.events.find((event) => event.id === node.localContext.eventId) ?? null
  )
}

export function DiaryHistoryPane() {
  const [params, setParams] = useSearchParams()
  const { reduceMotion } = useSettingsValues()
  const planetPortalRef = useRef(null)
  const cluster =
    historyStories.find((item) => item.topicCode === params.get('topic')) ?? historyStories[0]
  const [selectedNode, setSelectedNode] = useState(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [eventPageIndex, setEventPageIndex] = useState(0)
  const selectedEvent = findEvent(selectedNode)
  // The primary story's events are exactly the ones the graph turns into stars.
  const clusterEvents = cluster.story.events
  const eventPageCount = Math.max(1, Math.ceil(clusterEvents.length / EVENTS_PER_PAGE))
  const safeEventPageIndex = Math.min(eventPageIndex, eventPageCount - 1)
  const visibleEvents = clusterEvents.slice(
    safeEventPageIndex * EVENTS_PER_PAGE,
    (safeEventPageIndex + 1) * EVENTS_PER_PAGE,
  )

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === planetPortalRef.current)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  const selectTopic = (nextCluster) => {
    setSelectedNode(null)
    setEventPageIndex(0)
    setParams({ view: 'log', topic: nextCluster.topicCode }, { replace: true })
  }

  // The right page lists the same events the planet carries as stars, so picking one
  // from the list builds the node the planet already knows — same `id`, so the globe
  // turns to that star instead of the two halves drifting apart.
  const selectEventFromList = (event) =>
    setSelectedNode({
      id: `EVENT:${event.id}`,
      topicCode: cluster.topicCode,
      localContext: { storyId: cluster.story.id, eventId: event.id },
    })

  // Opening an Event now means opening its article window, which selecting it already
  // does — the planet's open action and its select action are the same thing here.
  const selectNode = (node) => {
    setSelectedNode(node)
    if (node?.topicCode && node.topicCode !== cluster.topicCode) {
      setEventPageIndex(0)
      setParams({ view: 'log', topic: node.topicCode }, { replace: true })
    }
  }

  const toggleFullscreen = async () => {
    if (document.fullscreenElement === planetPortalRef.current) await document.exitFullscreen()
    else await planetPortalRef.current?.requestFullscreen()
  }

  return (
    <section
      className={`${styles.page} ${styles[TONE_CLASS[cluster.tone]]}`}
      aria-label="나의 기록 다이어리"
    >
      <DiaryShell stageClassName={styles.diaryStage} frameClassName={styles.diaryFrame}>

        <Link className={styles.reportBookmark} to="/app?view=report">
          <img src={`${BOOKMARK_ASSET}/bookmark-report-blank.svg`} alt="" aria-hidden="true" />
          <span>나의 리포트</span>
        </Link>

        <nav className={styles.categoryBookmarks} aria-label="뉴스 카테고리">
          {historyStories.map((item) => {
            const selected = item.topicCode === cluster.topicCode

            return (
              <button
                type="button"
                key={item.topicCode}
                aria-current={selected ? 'true' : undefined}
                onClick={() => selectTopic(item)}
              >
                <img
                  src={`${BOOKMARK_ASSET}/tab-${selected ? 'selected' : 'default'}-blank.svg`}
                  alt=""
                  aria-hidden="true"
                />
                <span>{item.topicName}</span>
              </button>
            )
          })}
        </nav>

        <header className={styles.diaryTitle}>
          <span>MY CONSTELLATION ARCHIVE</span>
          <h1>나의 기록들</h1>
          <p>작은 기록들이 모여 하나의 우주가 됩니다.</p>
        </header>

        <div ref={planetPortalRef} className={styles.planetPortal}>
          {isFullscreen ? (
            <HistoryPane
              viewId="log"
              fullscreenLayout
              onExitFullscreen={() => document.exitFullscreen()}
            />
          ) : (
            <Suspense
              fallback={<div className={styles.planetLoading}>기록 행성을 불러오는 중…</div>}
            >
              <HistoryPlanet
                graph={historyGraph}
                activeTopic={cluster.topicCode}
                reduceMotion={reduceMotion}
                selectedNode={selectedNode}
                selectedEvent={selectedEvent}
                onSelectNode={selectNode}
                onOpenEvent={selectNode}
                variant="diary"
              />
            </Suspense>
          )}
        </div>

        {/* Sits on the left page because what it expands is the planet above it, not the
            record page on the right. */}
        <div className={styles.planetActions}>
          <button type="button" onClick={toggleFullscreen} aria-pressed={isFullscreen}>
            {isFullscreen ? '화면 닫기' : '전체 보기'}
          </button>
        </div>

        <p className={styles.planetCaption}>별을 선택해 오른쪽 페이지에서 기록을 펼쳐보세요.</p>

        <article className={styles.recordPage} aria-live="polite">
          <header className={styles.recordHeader}>
            <div>
              <span>
                {historyOverview.periodLabel} · {historyOverview.generatedAt}
              </span>
              <h2>{selectedEvent ? '선택한 Event' : `${cluster.topicName} 기록`}</h2>
            </div>
          </header>

          {clusterEvents.length > 0 ? (
            <div className={styles.eventPage}>
              <div className={styles.eventIntro}>
                <span>{cluster.topicName} EVENTS</span>
                <h3>{cluster.story.title}</h3>
                <p>
                  Event {clusterEvents.length}개 · 읽은 기사 {cluster.articleCount}개
                </p>
              </div>

              <ul className={styles.eventList}>
                {visibleEvents.map((event) => (
                  <li key={event.id}>
                    <button type="button" onClick={() => selectEventFromList(event)}>
                      <small>{event.lastReadAt}</small>
                      <strong>{event.title}</strong>
                      <p>관련 기사 {event.articles.length}개</p>
                    </button>
                  </li>
                ))}
              </ul>

              {eventPageCount > 1 && (
                <nav className={styles.eventPager} aria-label="이벤트 목록 페이지">
                  <button
                    type="button"
                    onClick={() => setEventPageIndex((page) => Math.max(0, page - 1))}
                    disabled={safeEventPageIndex === 0}
                    aria-label="이전 이벤트 페이지"
                  >
                    ‹
                  </button>
                  <span>
                    {safeEventPageIndex + 1} / {eventPageCount}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setEventPageIndex((page) => Math.min(eventPageCount - 1, page + 1))
                    }
                    disabled={safeEventPageIndex === eventPageCount - 1}
                    aria-label="다음 이벤트 페이지"
                  >
                    ›
                  </button>
                </nav>
              )}
            </div>
          ) : (
            <div className={styles.emptyPage}>
              <span aria-hidden="true">✦</span>
              <h3>어떤 기록을 펼쳐볼까요?</h3>
              <p>
                왼쪽 행성을 돌려 Event 별을 선택하면
                <br />
                관련 기사가 이 페이지에 정리됩니다.
              </p>
              <dl>
                <div>
                  <dt>읽은 기사</dt>
                  <dd>{historyOverview.totalArticleCount}</dd>
                </div>
                <div>
                  <dt>기록 분야</dt>
                  <dd>{historyOverview.topicCount}</dd>
                </div>
                <div>
                  <dt>현재 분야</dt>
                  <dd>{cluster.articleCount}</dd>
                </div>
              </dl>
            </div>
          )}
        </article>
      </DiaryShell>

      {selectedEvent && (
        <ArticlePopup event={selectedEvent} onClose={() => setSelectedNode(null)} />
      )}
    </section>
  )
}

/**
 * The articles behind one Event, in a window over the diary.
 *
 * The diary's right page lists Events and nothing else, so the articles need somewhere
 * of their own; a window keeps the page underneath intact, which a second in-page view
 * did not. Mounted only while an Event is chosen — there is no open/closed animation to
 * preserve, so there is nothing to keep mounted for.
 */
function ArticlePopup({ event, onClose }) {
  const closeRef = useRef(null)

  useEffect(() => {
    const closeOnEscape = (keyEvent) => {
      if (keyEvent.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', closeOnEscape)
    closeRef.current?.focus()
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  return createPortal(
    <div
      className={styles.scrim}
      role="presentation"
      onClick={(clickEvent) => {
        if (clickEvent.target === clickEvent.currentTarget) onClose()
      }}
    >
      <div
        className={styles.popup}
        role="dialog"
        aria-modal="true"
        aria-labelledby="article-popup-title"
      >
        <button
          type="button"
          ref={closeRef}
          className={styles.popupClose}
          onClick={onClose}
          aria-label="닫기"
        >
          ✕
        </button>

        <div className={styles.popupHead}>
          <span>READ ARTICLES</span>
          <h3 id="article-popup-title">{event.title}</h3>
          <p>
            관련 기사 {event.articles.length}개 · 마지막 열람 {event.lastReadAt}
          </p>
        </div>

        <ol className={styles.articleList}>
          {event.articles.map((article, index) => (
            <li key={article.id}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <div>
                <small>
                  {article.source} · {article.readAt}
                </small>
                <strong>{article.title}</strong>
                <p>{article.summary}</p>
                {/* Nothing behind this yet: the article data carries no link and there is
                    no article route, the same gap <TrendPanel>'s 상세 보기 is holding. */}
                <button type="button" className={styles.articleDetail}>
                  상세 보기 →
                </button>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>,
    document.body,
  )
}
