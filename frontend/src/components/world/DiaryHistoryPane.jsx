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
import { fetchArticleDetail } from '../../api/articles'
import { panelCopy } from '../../data/trend'
import { TOPICS } from '../../data/topics'
import { useArticleSummary } from '../../hooks/useArticleSummary'
import { useBookmark } from '../../hooks/useBookmark'
import { useSettingsValues } from '../../store/settings'
import { DiaryShell } from './DiaryShell'
import { loadHistoryPlanet } from './historyPlanetChunk'
import styles from './DiaryHistoryPane.module.css'

const HistoryPlanet = lazy(loadHistoryPlanet)
const BOOKMARK_ASSET = '/assets/history/bookmarks'
/*
 * 한 쪽에 세우는 사건 수.
 *
 * 셋이던 것을 넷으로 늘린다. 줄 높이를 70px 에서 32px 로 줄이고 목록에 스크롤을 준 뒤로는
 * 셋이 종이의 위쪽만 쓰고 아래가 비어, 쪽을 넘길 이유가 실제 분량보다 자주 생겼다.
 */
const EVENTS_PER_PAGE = 4
const ARTICLES_PER_EVENT = 5
/*
 * 펼친 사건이 처음에 보여 주는 발언 수.
 *
 * 서버는 사건에 달린 발언을 개수 제한 없이 준다. 그대로 다 펼치면 발언이 열 개인 사건
 * 하나가 목록 전체를 먹어, 같은 페이지의 다른 사건이 스크롤 저편으로 밀린다. 넷은 무엇에
 * 대한 사건인지 감이 오는 최소치다 — 나머지는 눌러서 본다.
 */
const STATEMENTS_PER_EVENT = 4
const FS_DETAIL_MIN_WIDTH = 32
const FS_DETAIL_MAX_WIDTH = 70

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
 * 오늘을 `yyyy-MM-dd` 로, KST 기준으로 준다. 날짜 칸의 상한으로 쓴다.
 *
 * 서버가 기간을 KST 날짜로 읽으므로 브라우저의 시간대로 찍으면 안 된다 — 한국 밖에서 보면
 * 하루가 밀린다. `en-CA` 로케일이 그 형식을 그대로 준다.
 */
const KST_DATE = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' })
function kstToday() {
  return KST_DATE.format(new Date())
}

/** 비어 있는 기간 — 이 상태로 두면 파라미터를 보내지 않아 전체 기록이 온다. */
const NO_RANGE = { from: '', to: '' }

/**
 * 책갈피가 실패했을 때 줄 밑에 한 줄로 남긴다.
 *
 * 로그인 문구도 들고 있지만 이 화면에서는 거의 쓰이지 않는다 — 기록 자체가 로그인해야 보이는
 * 것이라 여기까지 온 사람은 이미 로그인돼 있다. 세션이 중간에 끊긴 경우를 위해 남겨 둔다.
 */
const ARTICLE_BOOKMARK_COPY = {
  signIn: '로그인하면 담을 수 있어요.',
  failed: '북마크를 바꾸지 못했어요.',
}

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
  const [map, setMap] = useState({ scope: null, state: 'loading', data: null })
  const [articles, setArticles] = useState({ scope: null, byEvent: {} })

  /*
   * 기간은 URL 이 아니라 여기에 둔다. 분야를 옮길 때 setParams 로 검색 문자열을 통째로 갈아
   * 끼우고 있어서, URL 에 두면 분야를 누를 때마다 기간이 조용히 초기화된다.
   *
   * 칸에 적힌 값(draft)과 실제로 보내는 값(range)을 나눈다. 서버는 from·to 를 함께 받거나
   * 둘 다 없거나만 허용하므로(한쪽만 오면 400), 시작일만 고르고 끝을 아직 안 고른 중간 상태를
   * 그대로 보내면 안 된다. 그 사이는 오류가 아니라 고르는 중이다.
   */
  const [draft, setDraft] = useState(NO_RANGE)
  const [range, setRange] = useState(NO_RANGE)
  // `yyyy-MM-dd` 는 사전순과 날짜순이 같아 문자열 비교로 충분하다.
  const reversed = Boolean(draft.from && draft.to) && draft.from > draft.to

  /*
   * 지도와 기사에 달아 두는 꼬리표. 분야뿐 아니라 기간까지 넣는다 — 기간만 바꾼 경우에도
   * 손에 든 응답은 이미 남의 것이므로, 분야만으로 가르면 새 응답이 오기 전까지 이전 기간의
   * 사건이 그대로 보인다. 보내지 않는 기간(빈 문자열)은 전체를 뜻하므로 그것도 한 꼬리표다.
   */
  const rangeKey = `${range.from}|${range.to}`
  const scope = `${topic.topicCode}|${rangeKey}`

  const [selectedNode, setSelectedNode] = useState(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  /*
   * 전체화면에서 띠가 보여 주는 사건. 행성이 화면을 덮으면 오른쪽 종이가 가려지므로,
   * 아래 가로 띠와 오른쪽 칸이 그 자리를 대신한다.
   *
   * 띠 자체는 전체화면이면 늘 떠 있다 — 분야 탭이 거기 있어서, 접혀 있으면 고를 것이
   * 어디에도 보이지 않는다.
   */
  const [fsEventId, setFsEventId] = useState(null)
  const [fsDetailWidth, setFsDetailWidth] = useState(FS_DETAIL_MIN_WIDTH)
  const [fsDetailResizing, setFsDetailResizing] = useState(false)
  const fsDetailPointerRef = useRef(null)
  const [eventPageIndex, setEventPageIndex] = useState(0)
  const [openEventId, setOpenEventId] = useState(null)
  // 발언을 다 펼친 사건. 사건 id 로 들고 있어서 다른 사건을 열면 저절로 접힌다.
  const [allStatementsFor, setAllStatementsFor] = useState(null)
  // 펼친 사건 줄. 목록이 스크롤되면 아래쪽 사건은 보이는 자리 밖에서 열려 아무 일도 일어나지
  // 않은 것처럼 보인다. 그래서 펼친 줄을 눈에 들어오는 자리로 끌어온다.
  const openEventRef = useRef(null)
  // 전체화면 카드 띠. 휠을 가로 이동으로 바꾸려면 네이티브 리스너가 필요하다(아래 effect).
  const fsStripRef = useRef(null)
  const fsEventCardRefs = useRef(new Map())

  // 분야를 옮겨 다녀도 대표 별들은 그대로다. 다시 부르는 것은 기간이 바뀔 때뿐이다.
  useEffect(() => {
    const controller = new AbortController()
    fetchPersonalGraph({ ...range, signal: controller.signal })
      .then((payload) => {
        setSummaryGraph(graphFromSummary(payload))
        setSummaryState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setSummaryState(error?.status === 401 ? 'signedOut' : 'failed')
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeKey])

  // 지도는 분야를 옮기거나 기간을 바꿀 때마다.
  useEffect(() => {
    const controller = new AbortController()
    const forScope = scope
    fetchPersonalTopicMap(topic.topicCode, { ...range, signal: controller.signal })
      .then((payload) => setMap({ scope: forScope, state: 'ready', data: payload }))
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setMap({ scope: forScope, state: error?.status === 401 ? 'signedOut' : 'failed', data: null })
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope])

  useEffect(() => {
    if (!openEventId) return
    // `nearest` 는 이미 보이면 움직이지 않는다 — 펼칠 때마다 목록이 튀지 않게.
    openEventRef.current?.scrollIntoView({
      block: 'nearest',
      behavior: reduceMotion ? 'auto' : 'smooth',
    })
  }, [openEventId, reduceMotion])

  /*
   * 카드 띠 위에서 굴린 휠을 좌우 이동으로 바꾼다.
   *
   * React 의 onWheel 은 루트에 passive 로 붙어 preventDefault 가 듣지 않으므로, 요소에
   * 직접 `{ passive: false }` 로 건다. 막지 않으면 휠이 카드도 옮기고 뒤쪽도 함께 굴려
   * 한 번의 조작이 두 군데에 먹는다.
   *
   * 트랙패드의 가로 제스처(deltaX)는 건드리지 않는다 — 브라우저가 이미 옳게 처리한다.
   */
  useEffect(() => {
    const strip = fsStripRef.current
    if (!strip) return undefined
    const handleWheel = (event) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return
      event.preventDefault()
      strip.scrollLeft += event.deltaY
    }
    strip.addEventListener('wheel', handleWheel, { passive: false })
    return () => strip.removeEventListener('wheel', handleWheel)
  }, [isFullscreen])

  useEffect(() => {
    if (!isFullscreen || !fsEventId) return undefined
    const frameId = window.requestAnimationFrame(() => {
      fsEventCardRefs.current.get(fsEventId)?.scrollIntoView({
        behavior: reduceMotion ? 'auto' : 'smooth',
        block: 'nearest',
        inline: 'center',
      })
    })
    return () => window.cancelAnimationFrame(frameId)
  }, [fsEventId, isFullscreen, reduceMotion])

  useEffect(() => {
    const handleFullscreenChange = () => {
      const on = document.fullscreenElement === planetPortalRef.current
      setIsFullscreen(on)
      // 들어갈 때는 종이에서 펼쳐 둔 사건을 그대로 이어받고, 나갈 때는 놓는다. 펼친 채로
      // 전체화면을 켰는데 아무것도 안 골라져 있으면 보던 것을 잃은 것처럼 보인다.
      setFsEventId(on ? openEventId : null)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
    // openEventId 가 바뀔 때마다 리스너를 다시 건다. ref 로 최신값을 훔쳐보는 편이 리스너를
    // 한 번만 걸지만, 렌더 중에 ref 를 쓰게 되어 규칙에 어긋난다. 이 리스너는 붙였다 떼는
    // 비용이 없는 쪽이라 의존성에 넣는 것이 낫다.
  }, [openEventId])

  const current = map.scope === scope ? map : { state: 'loading', data: null }
  const articlesByEvent = articles.scope === scope ? articles.byEvent : {}
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

  /**
   * 기간을 바꾼다. 펼쳐 둔 사건과 페이지는 접는다 — 새 기간에 그 사건이 남아 있다는 보장이
   * 없고, 사라진 사건을 펼친 채로 두면 빈 칸이 열려 있게 된다.
   */
  const changeRange = (next) => {
    setDraft(next)

    // 칸에 적힌 것이 곧 보낼 것은 아니다. 한쪽만 고른 중간과 거꾸로 고른 상태에서는 들고 있던
    // 기간을 그대로 둔다 — 그래야 고치는 동안 화면이 제멋대로 전체로 돌아가지 않는다.
    const settled = !next.from && !next.to
    if (!settled && !(next.from && next.to && next.from <= next.to)) return

    setSelectedNode(null)
    setOpenEventId(null)
    setEventPageIndex(0)
    setRange(settled ? NO_RANGE : { from: next.from, to: next.to })
  }

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
  const loadArticles = useCallback((forScope, event, forRange) => {
    const put = (value) =>
      setArticles((was) => {
        const byEvent = was.scope === forScope ? was.byEvent : {}
        return { scope: forScope, byEvent: { ...byEvent, [event.nodeKey]: value } }
      })

    put({ state: 'loading' })
    fetchPersonalNodeArticles('EVENT', event.nodeKey, { ...forRange, size: ARTICLES_PER_EVENT })
      .then((payload) => put({ state: 'ready', items: payload?.items ?? [] }))
      .catch(() => put({ state: 'failed' }))
  }, [])

  const toggleEvent = (event) => {
    const open = openEventId === event.id
    setOpenEventId(open ? null : event.id)
    if (open) return
    // 목록과 행성이 따로 놀지 않도록, 펼치는 사건으로 행성을 돌린다.
    setSelectedNode({ id: event.id, nodeType: 'EVENT', nodeKey: event.nodeKey, topicCode: topic.topicCode })
    if (!articlesByEvent[event.nodeKey]) loadArticles(scope, event, range)
    recordNodeClick('EVENT', event.nodeKey).catch(() => {})
  }

  /**
   * 행성에서 별을 눌렀을 때. 다른 분야의 별이면 그 분야로 옮겨 간다.
   *
   * 사건이면 오른쪽 목록의 같은 사건도 펼친다 — 행성과 목록이 같은 것을 가리키게.
   *
   * 분야 중심 별은 전체화면에서 아래 띠를 연다. 지금 보고 있는 분야의 별도 똑같이 연다 —
   * 일곱 중 하나만 눌러도 반응이 없으면 그 별만 고장 난 것처럼 보인다.
   */
  const selectNode = (node) => {
    setSelectedNode(node)
    if (!node) return

    const otherTopic = node.topicCode && node.topicCode !== topic.topicCode
    if (otherTopic) {
      setOpenEventId(null)
      setEventPageIndex(0)
      setParams({ view: 'log', topic: node.topicCode }, { replace: true })
    }

    // 분야 중심 별은 그 분야로 옮기는 것으로 끝난다. 띠는 이미 떠 있다.
    if (node.kind === 'TOPIC_CLUSTER') return

    // 분야를 막 옮겼으면 events 는 아직 이전 분야의 것이라 여기서 찾으면 엉뚱한 것이 걸린다.
    if (otherTopic || node.nodeType !== 'EVENT') return
    const event = events.find((item) => item.id === node.id)
    if (!event) return
    if (isFullscreen) openInFullscreen(event)
    setOpenEventId(event.id)
    setEventPageIndex(Math.floor(events.indexOf(event) / EVENTS_PER_PAGE))
    if (!articlesByEvent[event.nodeKey]) loadArticles(scope, event, range)
  }

  /**
   * 전체화면 아래 띠에서 사건을 골랐을 때. 행성이 왼쪽 절반으로 물러나고 오른쪽에 속이 열린다.
   *
   * 오른쪽 종이의 토글과 같은 일을 하지만 그쪽 상태(openEventId)는 건드리지 않는다 —
   * 전체화면을 닫았을 때 종이가 제 상태 그대로 남아 있어야 한다.
   */
  const openInFullscreen = (event) => {
    setFsEventId(event.id)
    setSelectedNode({
      id: event.id,
      nodeType: 'EVENT',
      nodeKey: event.nodeKey,
      topicCode: topic.topicCode,
    })
    if (!articlesByEvent[event.nodeKey]) loadArticles(scope, event, range)
    recordNodeClick('EVENT', event.nodeKey).catch(() => {})
  }

  const toggleFullscreen = async () => {
    if (document.fullscreenElement === planetPortalRef.current) await document.exitFullscreen()
    else await planetPortalRef.current?.requestFullscreen()
  }

  const resizeFsDetail = (clientX) => {
    const bounds = planetPortalRef.current?.getBoundingClientRect()
    if (!bounds?.width) return
    const next = ((bounds.right - clientX) / bounds.width) * 100
    setFsDetailWidth(Math.min(FS_DETAIL_MAX_WIDTH, Math.max(FS_DETAIL_MIN_WIDTH, next)))
  }

  const beginFsDetailResize = (event) => {
    if (event.button !== 0) return
    fsDetailPointerRef.current = event.pointerId
    event.currentTarget.setPointerCapture?.(event.pointerId)
    resizeFsDetail(event.clientX)
    setFsDetailResizing(true)
    event.preventDefault()
  }

  const moveFsDetailResize = (event) => {
    if (fsDetailPointerRef.current !== event.pointerId) return
    resizeFsDetail(event.clientX)
  }

  const endFsDetailResize = (event) => {
    if (fsDetailPointerRef.current !== event.pointerId) return
    event.currentTarget.releasePointerCapture?.(event.pointerId)
    fsDetailPointerRef.current = null
    setFsDetailResizing(false)
  }

  const nudgeFsDetailResize = (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    const direction = event.key === 'ArrowLeft' ? 1 : -1
    setFsDetailWidth((width) =>
      Math.min(FS_DETAIL_MAX_WIDTH, Math.max(FS_DETAIL_MIN_WIDTH, width + direction * 2)),
    )
    event.preventDefault()
  }

  // 띠에서 고른 사건. 분야가 바뀌면 events 가 갈리므로 여기서 못 찾고 저절로 닫힌다.
  const fsEvent = fsEventId ? (events.find((item) => item.id === fsEventId) ?? null) : null
  const fsAllStatements = fsEvent ? allStatementsFor === fsEvent.id : false
  const fsStatements = fsEvent
    ? (fsAllStatements ? fsEvent.statements : fsEvent.statements.slice(0, STATEMENTS_PER_EVENT))
    : []
  const fsRestCount = fsEvent ? fsEvent.statements.length - fsStatements.length : 0

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

        {/*
          전체화면은 이 상자만 그린다(:fullscreen 은 그 요소의 자손만 띄운다). 그래서 띠와
          오른쪽 칸도 여기 안에 있어야 한다 — 밖에 두면 전체화면에서 사라진다.
        */}
        <div
          ref={planetPortalRef}
          className={styles.planetPortal}
          data-strip={isFullscreen ? 'on' : undefined}
          data-split={isFullscreen && fsEvent ? 'on' : undefined}
          data-resizing={fsDetailResizing ? 'on' : undefined}
          style={{ '--fs-detail-width': `${fsDetailWidth}%` }}
        >
          <div className={styles.planetStage}>
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
                showInspector={false}
              />
            </Suspense>
          </div>

          {isFullscreen && fsEvent && (
            <aside
              className={styles.fsDetail}
              data-resizing={fsDetailResizing ? 'on' : undefined}
              aria-label={`${fsEvent.title} 기록`}
            >
              <div
                className={styles.fsDetailResize}
                role="separator"
                tabIndex={0}
                aria-label="상세보기 너비 조절"
                aria-orientation="vertical"
                aria-valuemin={FS_DETAIL_MIN_WIDTH}
                aria-valuemax={FS_DETAIL_MAX_WIDTH}
                aria-valuenow={Math.round(fsDetailWidth)}
                title="좌우로 끌어 상세보기 너비 조절"
                onPointerDown={beginFsDetailResize}
                onPointerMove={moveFsDetailResize}
                onPointerUp={endFsDetailResize}
                onPointerCancel={endFsDetailResize}
                onDoubleClick={() => setFsDetailWidth(FS_DETAIL_MIN_WIDTH)}
                onKeyDown={nudgeFsDetailResize}
              />
              <header>
                <span>{topic.topicName}</span>
                <h3>{fsEvent.title}</h3>
                <button type="button" onClick={() => setFsEventId(null)} aria-label="닫기">
                  ✕
                </button>
              </header>
              <EventBody
                className={styles.fsDetailBody}
                event={fsEvent}
                articles={articlesByEvent[fsEvent.nodeKey]}
                statements={fsStatements}
                restCount={fsRestCount}
                allStatements={fsAllStatements}
                dark
                onToggleStatements={() =>
                  setAllStatementsFor(fsAllStatements ? null : fsEvent.id)
                }
              />
            </aside>
          )}

          {isFullscreen && (
            <div className={styles.fsStrip}>
              {/*
                분야 탭. 행성의 분야 중심 별과 같은 일을 하지만, 별은 돌려서 찾아야 하고
                이쪽은 일곱이 한눈에 선다. 기록이 없는 분야는 흐리게 두되 막지는 않는다 —
                눌리지 않으면 왜 안 되는지 알 수 없다.
              */}
              <div className={styles.fsTabs} role="tablist" aria-label="분야">
                {TOPICS.map((item) => (
                  <button
                    key={item.topicCode}
                    type="button"
                    role="tab"
                    aria-selected={item.topicCode === topic.topicCode}
                    className={`${styles.fsTab} ${styles[TONE_CLASS[item.tone]]}`}
                    data-empty={recordedTopics.has(item.topicCode) ? undefined : 'on'}
                    onClick={() => selectTopic(item)}
                  >
                    {item.topicName}
                  </button>
                ))}
                <span className={styles.fsTabsCount}>사건 {events.length}</span>
              </div>

              {events.length === 0 ? (
                <p className={styles.fsStripEmpty}>이 분야에 남은 기록이 없어요.</p>
              ) : (
                <ul ref={fsStripRef}>
                  {events.map((event) => (
                    <li key={event.id}>
                      <button
                        ref={(element) => {
                          if (element) fsEventCardRefs.current.set(event.id, element)
                          else fsEventCardRefs.current.delete(event.id)
                        }}
                        type="button"
                        aria-current={event.id === fsEventId ? 'true' : undefined}
                        onClick={() => openInFullscreen(event)}
                      >
                        <strong>{event.title}</strong>
                        <small>기사 {event.articleCount}개</small>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
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
              <span>{formatSnapshot(graph.generatedAt)}</span>
              <h2>{topic.topicName} 기록</h2>
            </div>
            <div className={styles.periodRow} role="group" aria-label="기간">
              <label className={styles.periodField}>
                <span>부터</span>
                <input
                  type="date"
                  value={draft.from}
                  max={draft.to || kstToday()}
                  onChange={(event) => changeRange({ ...draft, from: event.target.value })}
                />
              </label>
              <label className={styles.periodField}>
                <span>까지</span>
                <input
                  type="date"
                  value={draft.to}
                  min={draft.from || undefined}
                  max={kstToday()}
                  onChange={(event) => changeRange({ ...draft, to: event.target.value })}
                />
              </label>
              {(draft.from || draft.to) && (
                <button type="button" className={styles.periodClear} onClick={() => changeRange(NO_RANGE)}>
                  전체 보기
                </button>
              )}
            </div>
          </header>

          {/*
            기간을 건 동안만 밝힌다. 기준이 클릭이 아니라 열람이라는 것을 모르면, 별만 눌러 본
            사건이 빠진 것을 기록이 사라진 것으로 읽는다.

            한쪽만 고른 상태는 안내하지 않는다 — 고르는 중이지 잘못한 것이 아니다. 거꾸로 고른
            것만 짚는다. 그대로는 보낼 수 없는 값이라 화면이 말해 주지 않으면 왜 그대로인지 알
            길이 없다.
          */}
          {reversed && (
            <p className={styles.periodNote}>
              <b>시작일이 끝일보다 뒤</b>예요. 날짜를 바꾸면 그 기간으로 다시 그립니다.
            </p>
          )}
          {!reversed && range.from && (
            <p className={styles.periodNote}>
              이 기간에 <b>읽은 기사</b>를 기준으로 다시 그립니다.
            </p>
          )}

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
                  const titleCanExpand = event.title.length > 72
                  const articles = articlesByEvent[event.nodeKey]
                  const allStatements = allStatementsFor === event.id
                  const statements = allStatements
                    ? event.statements
                    : event.statements.slice(0, STATEMENTS_PER_EVENT)
                  const restCount = event.statements.length - statements.length

                  return (
                    <li key={event.id} ref={open ? openEventRef : null}>
                      <button
                        type="button"
                        aria-expanded={open}
                        onClick={() => toggleEvent(event)}
                      >
                        <strong
                          className={
                            titleCanExpand && !open ? styles.eventTitlePreview : undefined
                          }
                        >
                          {event.title}
                        </strong>
                        <small>기사 {event.articleCount}개</small>
                        <span className={styles.eventChevron} aria-hidden>
                          {open ? '▾' : '▸'}
                        </span>
                      </button>

                      {open && (
                        <EventBody
                          className={styles.statementBox}
                          event={event}
                          articles={articles}
                          statements={statements}
                          restCount={restCount}
                          allStatements={allStatements}
                          onToggleStatements={() =>
                            setAllStatementsFor(allStatements ? null : event.id)
                          }
                        />
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

/**
 * 펼친 사건의 속 — 발언과 내가 읽은 기사.
 *
 * 오른쪽 페이지의 목록 안에서도, 행성 전체화면의 오른쪽 칸에서도 같은 것을 보여 주므로
 * 한 군데에 둔다. 다른 것은 감싸는 상자의 모양뿐이라 className 으로 받는다.
 */
function EventBody({
  className,
  event,
  articles,
  statements,
  restCount,
  allStatements,
  dark = false,
  onToggleStatements,
}) {
  return (
    <div className={className}>
      <section>
        <h4>발언</h4>
        {event.statements.length > 0 ? (
          <>
            <ul className={styles.statementList}>
              {statements.map((statement) => (
                <li
                  key={statement.nodeKey}
                  className={dark ? styles.statementOnDark : undefined}
                >
                  {statement.label}
                </li>
              ))}
            </ul>
            {(restCount > 0 || allStatements) && (
              <button
                type="button"
                className={styles.statementMore}
                aria-expanded={allStatements}
                onClick={onToggleStatements}
              >
                {allStatements ? '발언 접기' : `발언 ${restCount}개 더`}
              </button>
            )}
          </>
        ) : (
          <p className={styles.statementEmpty}>이 사건에서 접한 발언이 없어요.</p>
        )}
      </section>

      <section>
        {/* 총계는 접힌 줄의 `기사 N개` 가 이미 말한다. 여기 두면 한 화면에 두 수가 서고,
            이쪽은 받아온 한 페이지(최대 ARTICLES_PER_EVENT)라 총계와 어긋난다. */}
        <h4>내가 읽은 기사</h4>
        {articles?.state === 'ready' && articles.items.length > 0 && (
          <ul
            className={`${styles.eventArticleList} ${dark ? styles.articleListOnDark : ''}`}
          >
            {/*
              읽은 날짜를 왼쪽 열로 빼 세로로 맞춘다. 발언은 사건의 내용이고 이쪽은 내
              행위의 기록이라, 날짜가 열을 이루면 훑기만 해도 "언제 읽었나"가 보이고 위의
              인용 덩어리와 모양 자체가 갈린다.
            */}
            {articles.items.map((article) => (
              <ArticleRow key={article.articleId} article={article} />
            ))}
          </ul>
        )}
        {articles?.state === 'ready' && articles.items.length === 0 && (
          <p className={styles.statementEmpty}>이 사건에서 읽은 기사가 없어요.</p>
        )}
        {articles?.state === 'loading' && (
          <p className={styles.statementEmpty}>기사를 불러오는 중…</p>
        )}
        {articles?.state === 'failed' && (
          <p className={styles.statementEmpty}>기사를 불러오지 못했어요.</p>
        )}
      </section>
    </div>
  )
}

/**
 * 읽은 기사 한 줄. 날짜 · 출처와 제목 · 책갈피 세 칸이다.
 *
 * 책갈피가 여기 서는 이유는, 나의 기록이 "무엇을 읽었나"를 보는 자리여서 그중 남겨 둘 것을
 * 고르는 일이 같은 자리에서 끝나야 하기 때문이다. 이걸 빼면 기사를 다시 찾아 트렌드나 추천
 * 화면으로 돌아가야 저장할 수 있다.
 *
 * 훅이 줄마다 자기 상태를 들고 있어야 해서 컴포넌트로 뺀다 — map 안에서는 훅을 부를 수 없다.
 * 초기값은 목록 응답의 `bookmarked` 고, 누른 뒤에는 훅이 든 값이 이긴다(useBookmark 참고).
 */
function ArticleRow({ article }) {
  const { on, pending, hint, toggle } = useBookmark({
    kind: 'article',
    key: article.articleId,
    initial: article.bookmarked,
    copy: ARTICLE_BOOKMARK_COPY,
  })
  const [open, setOpen] = useState(false)
  // 원문 주소는 이 목록에 없고 상세에만 있다. 한 번 받으면 들고 있다가 링크로 건다.
  const [origin, setOrigin] = useState(null)
  /*
   * 목록 응답이 저장된 요약의 앞부분(summaryPreview)을 같이 준다. 그것을 씨앗으로 넘기면
   * 대개 요청 없이 바로 펼쳐진다 — 오늘의 트렌드와 달리 여기 기사는 이미 읽은 것이라
   * 요약이 만들어져 있는 경우가 많다. 없을 때만 그 자리에서 만든다.
   */
  const { summary, state, load, retry } = useArticleSummary(article.articleId, {
    seed: article.summaryPreview ?? null,
  })
  const bodyId = `history-article-summary-${article.articleId}`

  const expand = () => {
    const next = !open
    setOpen(next)
    if (next) load()
  }

  /**
   * 원문 주소를 아직 모를 때만 쓰는 길. 빈 탭을 클릭과 같은 흐름에서 먼저 열고 주소를
   * 넣는다 — 응답을 기다렸다 window.open 을 부르면 팝업 차단에 걸린다.
   */
  const openOrigin = () => {
    const tab = window.open('', '_blank', 'noopener,noreferrer')
    fetchArticleDetail(article.articleId)
      .then((detail) => {
        const url = detail?.originalUrl ?? null
        setOrigin(url)
        if (url && tab) tab.location.href = url
        else tab?.close()
      })
      .catch(() => tab?.close())
  }

  return (
    <li>
      <small className={styles.articleWhen}>{formatDate(article.lastReadAt)}</small>
      <span className={styles.articleBody}>
        <small className={styles.articleSource}>{article.organizationName}</small>
        <p>{article.title}</p>
        {hint && (
          <small className={styles.articleHint} role="status">
            {hint}
          </small>
        )}

        <span className={styles.articleActions}>
          <button
            type="button"
            className={styles.articleAction}
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={expand}
          >
            {open ? panelCopy.summaryClose : panelCopy.summaryOpen}
            <b aria-hidden>{open ? '▴' : '▾'}</b>
          </button>

          {origin ? (
            <a
              className={`${styles.articleAction} ${styles.articleActionAway}`}
              href={origin}
              target="_blank"
              rel="noreferrer"
            >
              {panelCopy.origin}
              <b aria-hidden>↗</b>
            </a>
          ) : (
            <button
              type="button"
              className={`${styles.articleAction} ${styles.articleActionAway}`}
              onClick={openOrigin}
            >
              {panelCopy.origin}
              <b aria-hidden>↗</b>
            </button>
          )}
        </span>

        <span className={styles.articleSummary} id={bodyId} hidden={!open}>
          {summary ? (
            <span className={styles.articleSummaryText}>{summary}</span>
          ) : (
            <span className={styles.articleSummaryNote} role="status">
              {summaryNote(state)}
            </span>
          )}
          {(state === 'failed' || state === 'pending') && (
            <button type="button" className={styles.articleAction} onClick={retry}>
              {panelCopy.summaryRetry}
            </button>
          )}
        </span>
      </span>
      <button
        type="button"
        className={`${styles.articleBookmark} ${on ? styles.articleBookmarkOn : ''}`}
        aria-pressed={on}
        aria-label={`${article.title} ${on ? '북마크 해제' : '북마크'}`}
        title={on ? '북마크 해제' : '북마크에 담기'}
        disabled={pending}
        onClick={toggle}
      >
        <svg viewBox="0 0 13 17" aria-hidden>
          <path
            d="M1 1.6A.6.6 0 0 1 1.6 1h9.8a.6.6 0 0 1 .6.6v14.2l-5.5-3.6L1 15.8z"
            fill={on ? 'currentColor' : 'none'}
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </li>
  )
}

/** 요약이 비어 있는 이유를 화면 말로 옮긴다. TrendPanel 과 같은 문구를 쓴다. */
function summaryNote(state) {
  if (state === 'loading') return panelCopy.summaryLoading
  if (state === 'pending') return panelCopy.summaryPending
  if (state === 'unavailable') return panelCopy.summaryUnavailable
  if (state === 'failed') return panelCopy.summaryFailed
  return panelCopy.summaryNone
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
