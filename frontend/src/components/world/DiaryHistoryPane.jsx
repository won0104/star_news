import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  fetchPersonalGraph,
  fetchPersonalNodeArticles,
  fetchPersonalTopicMap,
  recordNodeClick,
} from '../../api/personalGraph'
import {
  eventsFromTopicMap,
  graphFromSummary,
  mergeTopicMap,
} from '../../adapters/personalGraph'
import { TOPICS } from '../../data/topics'
import { useSettingsValues } from '../../store/settings'
import { DiaryShell } from './DiaryShell'
import styles from './DiaryHistoryPane.module.css'

const HistoryPlanet = lazy(() => import('./HistoryPlanet'))
const BOOKMARK_ASSET = '/assets/history/bookmarks'
const EVENTS_PER_PAGE = 3
const ARTICLES_PER_EVENT = 5

const TONE_CLASS = {
  rose: 'toneRose',
  gold: 'toneGold',
  mint: 'toneMint',
  peach: 'tonePeach',
  violet: 'toneViolet',
  cyan: 'toneCyan',
  blue: 'toneBlue',
}

const EMPTY_GRAPH = { generatedAt: null, nodes: [], edges: [] }

/**
 * 나의 기록.
 *
 * 화면 전체가 두 요청 위에 서 있다. 요약(`/users/me/graph`)이 분야마다 대표 별 다섯을 주어
 * 행성을 처음 채우고, 분야를 고를 때마다 지도(`/users/me/graph/map`)가 그 분야의 속을
 * 전부 가져와 갈아 끼운다. 오른쪽 페이지의 사건 목록도 같은 지도 응답에서 나오므로,
 * 왼쪽 행성과 오른쪽 목록이 서로 다른 것을 보는 일이 없다.
 *
 * 사건 안의 기사는 펼칠 때 따로 가져온다(`.../nodes/EVENT/{key}/articles`). 분야마다 사건이
 * 여럿이고 대부분은 펼쳐보지 않으므로, 미리 받아두면 대부분 버리는 요청이 된다.
 *
 * 셋 다 로그인이 필요하다. 비로그인이면 401 이 오고, 그것은 오류가 아니라 상태다 —
 * 화면은 "로그인하면 볼 수 있다"고 말하고 빈 행성을 띄운다.
 */
export function DiaryHistoryPane() {
  const [params, setParams] = useSearchParams()
  const { reduceMotion } = useSettingsValues()
  const planetPortalRef = useRef(null)

  const topic = TOPICS.find((item) => item.topicCode === params.get('topic')) ?? TOPICS[0]

  const [summaryGraph, setSummaryGraph] = useState(EMPTY_GRAPH)
  const [summaryState, setSummaryState] = useState('loading')
  /*
   * 지도와 기사는 분야에 딸린 것이라, 분야가 바뀌면 둘 다 버려야 한다. 버리는 일을 effect 에서
   * setState 로 하면 렌더가 한 번 더 돌므로, 값 자체에 어느 분야의 것인지를 달아두고 읽는 쪽에서
   * 가른다 — 분야가 다르면 없는 것으로 친다. 늦게 도착한 이전 분야의 응답도 같은 규칙에 걸린다.
   */
  const [map, setMap] = useState({ topicCode: null, state: 'loading', data: null })
  const [articles, setArticles] = useState({ topicCode: null, byEvent: {} })

  const [selectedNode, setSelectedNode] = useState(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [eventPageIndex, setEventPageIndex] = useState(0)
  const [openEventId, setOpenEventId] = useState(null)

  // 요약은 한 번만. 분야를 옮겨 다녀도 대표 별들은 그대로다.
  useEffect(() => {
    const controller = new AbortController()
    fetchPersonalGraph({ signal: controller.signal })
      .then((payload) => {
        setSummaryGraph(graphFromSummary(payload))
        setSummaryState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setSummaryState(error?.status === 401 ? 'signedOut' : 'failed')
      })
    return () => controller.abort()
  }, [])

  // 지도는 분야를 옮길 때마다.
  useEffect(() => {
    const controller = new AbortController()
    const topicCode = topic.topicCode
    fetchPersonalTopicMap(topicCode, { signal: controller.signal })
      .then((payload) => setMap({ topicCode, state: 'ready', data: payload }))
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setMap({ topicCode, state: error?.status === 401 ? 'signedOut' : 'failed', data: null })
      })
    return () => controller.abort()
  }, [topic.topicCode])

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === planetPortalRef.current)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  const current = map.topicCode === topic.topicCode ? map : { state: 'loading', data: null }
  const articlesByEvent = articles.topicCode === topic.topicCode ? articles.byEvent : {}
  const graph = current.data ? mergeTopicMap(summaryGraph, current.data) : summaryGraph
  const events = current.data ? eventsFromTopicMap(current.data) : []
  const state =
    summaryState === 'signedOut' || current.state === 'signedOut' ? 'signedOut' : current.state

  const eventPageCount = Math.max(1, Math.ceil(events.length / EVENTS_PER_PAGE))
  const safeEventPageIndex = Math.min(eventPageIndex, eventPageCount - 1)
  const visibleEvents = events.slice(
    safeEventPageIndex * EVENTS_PER_PAGE,
    (safeEventPageIndex + 1) * EVENTS_PER_PAGE,
  )

  const selectTopic = (nextTopic) => {
    setSelectedNode(null)
    setOpenEventId(null)
    setEventPageIndex(0)
    setParams({ view: 'log', topic: nextTopic.topicCode }, { replace: true })
  }

  /**
   * 사건 하나를 펼친다. 기사는 그때 받아온다 — 한 번 받은 것은 남겨두고 다시 묻지 않는다.
   * 클릭 기록은 화면이 기다릴 일이 아니므로 결과를 보지 않는다.
   */
  const loadArticles = useCallback((topicCode, event) => {
    const put = (value) =>
      setArticles((was) => {
        const byEvent = was.topicCode === topicCode ? was.byEvent : {}
        return { topicCode, byEvent: { ...byEvent, [event.nodeKey]: value } }
      })

    put({ state: 'loading' })
    fetchPersonalNodeArticles('EVENT', event.nodeKey, { size: ARTICLES_PER_EVENT })
      .then((payload) => put({ state: 'ready', items: payload?.items ?? [] }))
      .catch(() => put({ state: 'failed' }))
  }, [])

  const toggleEvent = (event) => {
    const open = openEventId === event.id
    setOpenEventId(open ? null : event.id)
    if (open) return
    // 목록과 행성이 따로 놀지 않도록, 펼치는 사건으로 행성을 돌린다.
    setSelectedNode({ id: event.id, nodeType: 'EVENT', nodeKey: event.nodeKey, topicCode: topic.topicCode })
    if (!articlesByEvent[event.nodeKey]) loadArticles(topic.topicCode, event)
    recordNodeClick('EVENT', event.nodeKey).catch(() => {})
  }

  /**
   * 행성에서 별을 눌렀을 때. 다른 분야의 별이면 그 분야로 옮겨 간다.
   *
   * 사건이면 오른쪽 목록의 같은 사건도 펼친다 — 행성과 목록이 같은 것을 가리키게.
   */
  const selectNode = (node) => {
    setSelectedNode(node)
    if (!node) return
    if (node.topicCode && node.topicCode !== topic.topicCode) {
      setOpenEventId(null)
      setEventPageIndex(0)
      setParams({ view: 'log', topic: node.topicCode }, { replace: true })
      return
    }
    if (node.nodeType !== 'EVENT') return
    const event = events.find((item) => item.id === node.id)
    if (!event) return
    setOpenEventId(event.id)
    setEventPageIndex(Math.floor(events.indexOf(event) / EVENTS_PER_PAGE))
    if (!articlesByEvent[event.nodeKey]) loadArticles(topic.topicCode, event)
  }

  const toggleFullscreen = async () => {
    if (document.fullscreenElement === planetPortalRef.current) await document.exitFullscreen()
    else await planetPortalRef.current?.requestFullscreen()
  }

  const topicArticleCount = events.reduce((sum, event) => sum + event.articleCount, 0)
  const recordedTopics = new Set(
    summaryGraph.nodes.filter((node) => node.kind !== 'TOPIC_CLUSTER').map((node) => node.topicCode),
  )

  return (
    <section
      className={`${styles.page} ${styles[TONE_CLASS[topic.tone]]}`}
      aria-label="나의 기록 다이어리"
    >
      <DiaryShell stageClassName={styles.diaryStage} frameClassName={styles.diaryFrame}>

        {/* 자리와 자르는 선은 틈(.reportSlot)이 갖고, 책갈피는 그 안에서 뽑힌다. */}
        <div className={styles.reportSlot}>
          <Link className={styles.reportBookmark} to="/app?view=report">
            <img src={`${BOOKMARK_ASSET}/report-v2.webp`} alt="" aria-hidden="true" />
            <span>나의 리포트</span>
          </Link>
        </div>

        <nav className={styles.categoryBookmarks} aria-label="뉴스 카테고리">
          {TOPICS.map((item) => {
            const selected = item.topicCode === topic.topicCode

            return (
              <button
                type="button"
                key={item.topicCode}
                aria-current={selected ? 'true' : undefined}
                onClick={() => selectTopic(item)}
              >
                <img
                  src={`${BOOKMARK_ASSET}/right-${selected ? 'active' : 'idle'}-v2.webp`}
                  alt=""
                  aria-hidden="true"
                />
                <span>{item.topicName}</span>
              </button>
            )
          })}
        </nav>

        {/* 책의 종이 — 세로 화면에서 여기만 스크롤된다. 탭은 이 밖에 있어 책 가장자리에
            그대로 남는다. 가로에서는 자리를 차지하지 않는 투명한 층이다. */}
        <div className={styles.pageScroll}>

        <header className={styles.diaryTitle}>
          <span>MY CONSTELLATION ARCHIVE</span>
          <h1>나의 기록들</h1>
          <p>작은 기록들이 모여 하나의 우주가 됩니다.</p>
        </header>

        <div ref={planetPortalRef} className={styles.planetPortal}>
          <Suspense fallback={<div className={styles.planetLoading}>기록 행성을 불러오는 중…</div>}>
            <HistoryPlanet
              graph={graph}
              activeTopic={topic.topicCode}
              reduceMotion={reduceMotion}
              selectedNode={selectedNode}
              selectedEvent={null}
              onSelectNode={selectNode}
              onOpenEvent={selectNode}
              variant={isFullscreen ? 'default' : 'diary'}
            />
          </Suspense>
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
              <span>{formatSnapshot(graph.generatedAt)}</span>
              <h2>{topic.topicName} 기록</h2>
            </div>
          </header>

          {state === 'loading' && <p className={styles.pageNotice}>기록을 불러오는 중…</p>}

          {state === 'signedOut' && (
            <div className={styles.emptyPage}>
              <span aria-hidden="true">✦</span>
              <h3>로그인하면 내 기록이 보여요</h3>
              <p>
                읽은 기사로 만들어지는 기록이라
                <br />
                로그인한 뒤에야 펼칠 수 있어요.
              </p>
            </div>
          )}

          {state === 'failed' && (
            <p className={styles.pageNotice}>기록을 불러오지 못했어요. 잠시 뒤 다시 시도해주세요.</p>
          )}

          {state === 'ready' && events.length > 0 && (
            <div className={styles.eventPage}>
              <div className={styles.eventIntro}>
                <span>{topic.topicName} EVENTS</span>
                <h3>{topic.topicName} 분야에서 읽은 사건</h3>
                <p>
                  Event {events.length}개 · 읽은 기사 {topicArticleCount}개
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
                  const articles = articlesByEvent[event.nodeKey]

                  return (
                    <li key={event.id}>
                      <button type="button" aria-expanded={open} onClick={() => toggleEvent(event)}>
                        <small>읽은 기사 {event.articleCount}개</small>
                        <strong>{event.title}</strong>
                        <p>
                          <span className={styles.eventCount}>발언 {event.statements.length}</span>
                          <span className={styles.eventChevron} aria-hidden>
                            {open ? '▾' : '▸'}
                          </span>
                        </p>
                      </button>

                      {open && (
                        <div className={styles.statementBox}>
                          <section>
                            <h4>발언</h4>
                            {event.statements.length > 0 ? (
                              <ul className={styles.statementList}>
                                {event.statements.map((statement) => (
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
                              {articles?.state === 'ready' && <b>{articles.items.length}</b>}
                            </h4>
                            {articles?.state === 'ready' && articles.items.length > 0 && (
                              <ul className={styles.eventArticleList}>
                                {/*
                                  읽은 날짜를 왼쪽 열로 빼 세로로 맞춘다. 발언은 사건의
                                  내용이고 이쪽은 내 행위의 기록이라, 날짜가 열을 이루면
                                  훑기만 해도 "언제 읽었나"가 보이고 위의 인용 덩어리와
                                  모양 자체가 갈린다.
                                */}
                                {articles.items.map((article) => (
                                  <li key={article.articleId}>
                                    <small className={styles.articleWhen}>
                                      {formatDate(article.lastReadAt)}
                                    </small>
                                    <span className={styles.articleBody}>
                                      <small className={styles.articleSource}>
                                        {article.organizationName}
                                      </small>
                                      <p>{article.title}</p>
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            )}
                            {articles?.state === 'ready' && articles.items.length === 0 && (
                              <p className={styles.statementEmpty}>
                                이 사건에서 읽은 기사가 없어요.
                              </p>
                            )}
                            {articles?.state === 'loading' && (
                              <p className={styles.statementEmpty}>기사를 불러오는 중…</p>
                            )}
                            {articles?.state === 'failed' && (
                              <p className={styles.statementEmpty}>
                                기사를 불러오지 못했어요.
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
          )}

          {state === 'ready' && events.length === 0 && (
            <div className={styles.emptyPage}>
              <span aria-hidden="true">✦</span>
              <h3>{topic.topicName} 기록이 아직 없어요</h3>
              <p>
                이 분야의 기사를 읽으면
                <br />
                별이 하나씩 이 행성에 남습니다.
              </p>
              <dl>
                <div>
                  <dt>기록 분야</dt>
                  <dd>{recordedTopics.size}</dd>
                </div>
                <div>
                  <dt>기록된 별</dt>
                  <dd>
                    {summaryGraph.nodes.filter((node) => node.kind !== 'TOPIC_CLUSTER').length}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </article>

        </div>
      </DiaryShell>

    </section>
  )
}

/** `2026-09-16T18:00:00+09:00` → `2026.09.16 기준`. 없으면 머리글 줄을 비운다. */
function formatSnapshot(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '')
  return match ? `${match[1]}.${match[2]}.${match[3]} 기준` : ''
}

/** 서버가 준 오프셋을 이 컴퓨터의 시간대로 옮기지 않으려고 문자열에서 바로 읽는다. */
function formatDate(value) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(value ?? '')
  if (!match) return ''
  const [, month, day] = match
  return `${Number(month)}월 ${Number(day)}일`
}
