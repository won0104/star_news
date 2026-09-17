import { lazy, Suspense, useEffect, useRef, useState } from 'react'
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
  // 펼쳐 둔 사건. 한 번에 하나만 열린다.
  const [openEventId, setOpenEventId] = useState(null)
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

              {/*
                사건을 누르면 그 자리에서 펼쳐진다. 모달로 띄우던 것을 접은 이유는, 여기서
                보려는 것이 사건 하나의 전부가 아니라 "이 사건에서 내가 접한 발언"이라는
                한 조각이어서다 — 목록을 덮을 만큼의 내용이 아니다.

                한 번에 하나만 열린다. 페이지가 짧아 여러 개를 펼치면 목록이 화면을 넘긴다.
              */}
              <ul className={styles.eventList}>
                {visibleEvents.map((event) => {
                  const open = openEventId === event.id
                  const statements = event.statements ?? []

                  return (
                    <li key={event.id}>
                      <button
                        type="button"
                        aria-expanded={open}
                        onClick={() => {
                          setOpenEventId(open ? null : event.id)
                          // 목록과 행성이 따로 놀지 않도록, 펼치는 사건으로 지구를 돌린다.
                          if (!open) selectEventFromList(event)
                        }}
                      >
                        <small>{event.lastReadAt}</small>
                        <strong>{event.title}</strong>
                        <p>
                          <span className={styles.eventCount}>발언 {statements.length}</span>
                          <span className={styles.eventChevron} aria-hidden>
                            {open ? '▾' : '▸'}
                          </span>
                        </p>
                      </button>

                      {open && (
                        <div className={styles.statementBox}>
                          <section>
                            <h4>발언</h4>
                            {statements.length > 0 ? (
                              <ul className={styles.statementList}>
                                {statements.map((statement) => (
                                  <li key={statement.nodeKey}>{statement.label}</li>
                                ))}
                              </ul>
                            ) : (
                              <p className={styles.statementEmpty}>
                                이 사건에서 접한 발언이 없어요.
                              </p>
                            )}
                          </section>

                          <section>
                            <h4>
                              내가 읽은 기사
                              <b>{event.articles.length}</b>
                            </h4>
                            {event.articles.length > 0 ? (
                              <ul className={styles.eventArticleList}>
                                {event.articles.map((article) => (
                                  <li key={article.id}>
                                    <small>
                                      {article.source} · {article.readAt}
                                    </small>
                                    <p>{article.title}</p>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className={styles.statementEmpty}>
                                이 사건에서 읽은 기사가 없어요.
                              </p>
                            )}
                          </section>
                        </div>
                      )}
                    </li>
                  )
                })}
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

    </section>
  )
}

