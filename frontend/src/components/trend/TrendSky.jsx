import { useCallback, useEffect, useRef, useState } from 'react'
import { recordNodeClick } from '../../api/personalGraph'
import { fetchHomeTrends, fetchNeighbors, fetchTopicExploration } from '../../api/trend'
import { stars } from '../../data/trend'
import {
  trendNeighbors,
  trendNodeArticles,
  trendSkyExpandCopy,
  formatTrendGraphLabel,
} from '../../data/trendNeighbors'
import { homeTrends, TREND_MIN_SCALE, trendSkyCopy, trendSlots } from '../../data/trendTop'
import { useSession } from '../../store/session'
import { TrendConstellation } from './TrendConstellation'
import styles from './TrendSky.module.css'

/**
 * 오늘의 트렌드 — the ten events `GET /home` ranks, and the graph behind whichever one is
 * pressed. 분야를 고르면 같은 자리에 `GET /topics/{topicCode}/exploration` 의 열이 선다.
 *
 * Two states in one screen, because they are two views of the same sky rather than two
 * places: the ranked ten, and one of them opened out into its own neighbours. Pressing a
 * star loads `/graphs/nodes/EVENT/{nodeKey}/neighbors` and moves the picture to the
 * second; the back control (or Escape) returns.
 *
 * The ranked view draws no lines. `/home` returns a list with no edges, so any line there
 * would be a relationship the data does not claim — the links belong to the neighbours
 * response, which is exactly what the second state draws.
 *
 * Both states read their shape off the data rather than off authored art: rank picks a
 * slot, `articleCount` sets a star's size, and in the expansion the neighbour's own order
 * places it on the ring while `nodeType` picks its star and `weight` its line.
 *
 * `data` and `neighbors` are accepted as props so a caller can hand its own in.
 *
 * Until the aggregation publishes a round the endpoint answers an empty list, which would
 * leave this screen with nothing on it, so an empty or failed load falls back to the
 * sample in data/trendTop.js — and says so on the page. 분야 회차에는 그 대역을 쓰지
 * 않는다: 샘플 열은 여러 분야에 걸쳐 쓰여 있어서, 정치를 골랐는데 스포츠 별이 뜬다. The screen stays worth looking at
 * while the pipeline is being finished, and nobody reads ten invented events as today's
 * news. Set SAMPLE_WHEN_EMPTY to false, or delete it and the `sample` branches, once real
 * rounds are landing.
 */
const SAMPLE_WHEN_EMPTY = true
const TRACKED_NODE_TYPES = new Set(['EVENT', 'ENTITY', 'STATEMENT'])

/**
 * 분야 회차를 오늘의 트렌드와 같은 모양으로 맞춘다.
 *
 * 두 응답은 이름만 다르다 — `entryNodes` 가 `trends` 자리에 온다. 별을 놓는 코드가 어느
 * 회차를 보고 있는지 몰라도 되도록 여기서 한 번 맞춘다.
 *
 * `entryNodeId` 는 옮기지 않는다. 짝인 `trendItemId` 도 화면이 읽는 곳이 없고(별의 key 는
 * nodeKey 다), 쓰지 않는 값을 옮겨 두면 나중에 읽는 사람이 쓰이는 줄 안다.
 *
 * `centerTopic` 도 버린다 — 고른 분야는 창틀의 쪽지가 이미 쓰고 있어서, 화면 가운데에 한 번
 * 더 세우면 같은 말이 두 번 선다.
 */
function asRound(payload) {
  return { snapshotAt: payload?.snapshotAt ?? null, trends: payload?.entryNodes ?? [] }
}

function trailNode(node) {
  return {
    nodeType: node.nodeType ?? 'EVENT',
    nodeKey: node.nodeKey ?? node.id,
    label: node.label ?? node.title ?? '이름 없는 노드',
  }
}

export function TrendSky({ data: given, neighbors: givenNeighbors, overlayRoot, selectedNode, topic = null }) {
  const account = useSession()
  /*
   * 받아 둔 회차와, 그것이 어느 분야의 것인지.
   *
   * 분야를 한 쌍으로 들고 다니는 것이 요점이다. 분야를 갈아타는 순간 이 값은 헌 것이 되는데,
   * 효과 안에서 'loading' 으로 되돌리려면 렌더 중에 상태를 쓰게 된다. 지금 보고 있는 분야와
   * 견주기만 하면 되돌릴 것이 없다 — 짝이 맞지 않으면 그것이 곧 기다리는 중이다.
   */
  const [round, setRound] = useState(() => (given ? { topic, state: 'ready', payload: given } : null))
  const arrived = round?.topic === topic ? round : null
  const home = given ?? arrived?.payload ?? null
  const homeState = given ? 'ready' : (arrived?.state ?? 'loading')
  const [openKey, setOpenKey] = useState(null)
  const [graph, setGraph] = useState(null)
  const [graphState, setGraphState] = useState('idle')
  const [previewGraphs, setPreviewGraphs] = useState({})
  const [articlePanelOpen, setArticlePanelOpen] = useState(false)
  const [trail, setTrail] = useState([])
  const [journey, setJourney] = useState(null)
  // Neighbours do not change while the screen is open, so a key already opened is served
  // from here rather than fetched again.
  const cache = useRef(new Map())
  const activeKeyRef = useRef(null)
  const handledSelectionRef = useRef(null)
  const journeyTimerRef = useRef(null)

  useEffect(() => () => window.clearTimeout(journeyTimerRef.current), [])

  useEffect(() => {
    if (given) return
    const controller = new AbortController()
    // 답이 오면 어느 분야의 것인지와 함께 적는다 — 늦게 온 앞 분야의 답이 지금 화면을
    // 차지하지 못한다. abort 가 대부분 막아 주지만, 짝을 보는 쪽이 최종 판단이다.
    const asked = topic
    const pending = asked
      ? fetchTopicExploration(asked, { signal: controller.signal }).then(asRound)
      : fetchHomeTrends({ signal: controller.signal })
    pending
      .then((payload) => setRound({ topic: asked, state: 'ready', payload }))
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setRound({ topic: asked, state: 'failed', payload: null })
      })
    return () => controller.abort()
  }, [given, topic])

  const close = useCallback(() => {
    window.clearTimeout(journeyTimerRef.current)
    activeKeyRef.current = null
    setOpenKey(null)
    setGraph(null)
    setGraphState('idle')
    setArticlePanelOpen(false)
    setTrail([])
    setJourney(null)
  }, [])

  /*
   * 분야를 갈아타면 펼쳐 둔 별자리를 접는다. 그 별은 앞 회차의 것이고, 접지 않으면 쪽지에는
   * 정치라고 쓰인 채 경제 사건의 이웃 그래프가 남는다.
   *
   * 첫 렌더는 건너뛴다 — 현관에서 검색으로 실려 온 사건이 그때 펼쳐지는데, 여기서 같이
   * 접으면 그 사건이 곧바로 닫힌다.
   */
  const shownTopic = useRef(topic)
  useEffect(() => {
    if (shownTopic.current === topic) return
    shownTopic.current = topic
    close()
  }, [topic, close])

  useEffect(() => {
    if (!openKey) return
    const onKeyDown = (event) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [openKey, close])

  const live = home?.trends ?? []
  // A published round is the only case that needs no help. 분야 회차는 비어 있어도 대신
  // 세우지 않는다 — 위 머리말 참고.
  const sample = SAMPLE_WHEN_EMPTY && !topic && homeState !== 'loading' && live.length === 0
  const source = sample ? homeTrends : home
  const trends = source?.trends ?? []
  const ranked = [...trends].sort((a, b) => a.rank - b.rank).slice(0, trendSlots.length)
  const topCount = Math.max(1, ...ranked.map((trend) => trend.articleCount))

  const open = useCallback((
    trend,
    { preserveGraph = false, trailMode = 'append', trailIndex = -1, navigation = null } = {},
  ) => {
    const nodeType = trend.nodeType ?? 'EVENT'
    const nextTrailNode = trailNode(trend)
    const journeyStartedAt = performance.now()
    const departureDuration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 300
    window.clearTimeout(journeyTimerRef.current)
    activeKeyRef.current = trend.nodeKey
    setOpenKey(trend.nodeKey)
    setJourney(navigation ? { ...navigation, phase: 'departing' } : null)
    setTrail((current) => {
      if (trailMode === 'reset') return [nextTrailNode]
      if (trailMode === 'truncate') return current.slice(0, trailIndex + 1)
      const repeatedAt = current.findIndex(
        (node) => node.nodeType === nextTrailNode.nodeType && node.nodeKey === nextTrailNode.nodeKey,
      )
      if (repeatedAt >= 0) return current.slice(0, repeatedAt + 1)
      return [...current, nextTrailNode]
    })

    // 사용자가 실제 Node를 선택한 순간만 개인 그래프 탐색 기록으로 남긴다.
    // 샘플 별은 Neo4j에 없는 키이고, 비로그인 사용자는 개인 기록의 주체가 없으므로 제외한다.
    if (!sample && account && TRACKED_NODE_TYPES.has(nodeType)) {
      recordNodeClick(nodeType, trend.nodeKey).catch(() => {})
    }

    const commitGraph = (payload) => {
      if (activeKeyRef.current !== trend.nodeKey) return
      const apply = () => {
        if (activeKeyRef.current !== trend.nodeKey) return
        setGraph(payload)
        setGraphState('ready')
        if (!navigation) return
        setJourney({ ...navigation, phase: 'arriving' })
        journeyTimerRef.current = window.setTimeout(() => setJourney(null), 850)
      }

      // Keep even cached responses from replacing the scene before the departure reads.
      const delay = navigation
        ? Math.max(0, departureDuration - (performance.now() - journeyStartedAt))
        : 0
      journeyTimerRef.current = window.setTimeout(apply, delay)
    }

    // A sampled sky's keys are not in Neo4j, so asking for them would only 404.
    const ready = sample
      ? trendNeighbors[trend.nodeKey]
      : (givenNeighbors?.[trend.nodeKey] ?? cache.current.get(trend.nodeKey))

    if (ready) {
      commitGraph(ready)
      return
    }

    if (!preserveGraph) setGraph(null)
    setGraphState('loading')
    // Event-to-event links usually pass through a shared Entity, so the main graph
    // needs two hops. A one-hop response contains only the Event's direct parts.
    // Share one graph between the main constellation and its hover previews.
    fetchNeighbors(nodeType, trend.nodeKey, { depth: 2, limit: 30 })
      .then((payload) => {
        cache.current.set(trend.nodeKey, payload)
        commitGraph(payload)
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        if (activeKeyRef.current !== trend.nodeKey) return
        window.clearTimeout(journeyTimerRef.current)
        setJourney(null)
        setGraph(null)
        setGraphState('failed')
      })
  }, [account, givenNeighbors, sample])

  useEffect(() => {
    if (!selectedNode?.nodeKey || selectedNode.selectionId == null) return
    if (handledSelectionRef.current === selectedNode.selectionId) return
    handledSelectionRef.current = selectedNode.selectionId
    open(selectedNode, { trailMode: 'reset' })
  }, [open, selectedNode])

  /**
   * 화면에 보이는 관련 Event가 다음 중심이 되었을 때의 2-Hop 구성을 최대 30개까지
   * 미리 가져온다. 작은 별 하나가 다음 Event 하나를 뜻하며, 중심 이동도 같은 2-Hop·30개
   * 응답을 쓰므로 이미 받은 결과는 공용 cache에 보관한다.
   */
  useEffect(() => {
    if (graphState !== 'ready' || !graph || sample) return undefined

    const relatedEvents = (graph.nodes ?? [])
      .filter((node) => node.nodeType === 'EVENT')
      .slice(0, 3)
    const missing = relatedEvents.filter(
      (node) => !givenNeighbors?.[node.nodeKey] && !previewGraphs[node.nodeKey],
    )
    if (missing.length === 0) return undefined

    const controller = new AbortController()
    Promise.allSettled(
      missing.map(async (node) => {
        const payload =
          cache.current.get(node.nodeKey) ??
          (await fetchNeighbors(node.nodeType, node.nodeKey, {
            depth: 2,
            limit: 30,
            signal: controller.signal,
          }))
        cache.current.set(node.nodeKey, payload)
        return [node.nodeKey, payload]
      }),
    ).then((results) => {
      if (controller.signal.aborted) return
      const ready = results
        .filter((result) => result.status === 'fulfilled')
        .map((result) => result.value)
      if (ready.length === 0) return
      setPreviewGraphs((current) => ({ ...current, ...Object.fromEntries(ready) }))
    })

    return () => controller.abort()
  }, [givenNeighbors, graph, graphState, previewGraphs, sample])

  if (openKey) {
    if (!graph) {
      const chosen = ranked.find((trend) => trend.nodeKey === openKey)
      return (
        <Notice
          mark={graphState === 'failed' ? '⚠' : '✦'}
          title={graphState === 'failed' ? trendSkyExpandCopy.failed : trendSkyExpandCopy.loading}
          hint={chosen?.label}
          onBack={close}
        />
      )
    }

    const previews = Object.fromEntries(
      (graph.nodes ?? [])
        .filter((node) => node.nodeType === 'EVENT')
        .slice(0, 3)
        .map((node) => [
          node.nodeKey,
          sample
            ? trendNeighbors[node.nodeKey]
            : (givenNeighbors?.[node.nodeKey] ?? previewGraphs[node.nodeKey]),
        ])
        .filter(([, preview]) => preview),
    )

    return (
      <TrendConstellation
        graph={graph}
        previewGraphs={previews}
        journey={journey}
        articlePanelOpen={articlePanelOpen}
        onArticlePanelOpenChange={setArticlePanelOpen}
        onBack={close}
        onWalk={(node, navigation) =>
          open(
            {
              nodeType: node.nodeType ?? 'EVENT',
              nodeKey: node.id,
              label: node.label,
            },
            { preserveGraph: true, navigation },
          )
        }
        trail={trail}
        onTrailSelect={(node, index) =>
          open(node, { trailMode: 'truncate', trailIndex: index })
        }
        articleSamples={sample ? trendNodeArticles : undefined}
        overlayRoot={overlayRoot}
      />
    )
  }

  if (homeState === 'loading') {
    return <Notice mark="✦" title={trendSkyCopy.loading} />
  }

  if (ranked.length === 0) {
    /*
     * 빈 회차의 문구는 회차 종류를 따른다. 전체가 비었다면 아직 아무것도 모이지 않은 것이고,
     * 분야가 비었다면 다른 분야에는 있을 수 있다 — 읽는 이가 할 일이 다르다.
     */
    const failed = homeState === 'failed'
    const emptyTitle = topic ? trendSkyCopy.topicEmpty : trendSkyCopy.empty
    const emptyHint = topic ? trendSkyCopy.topicEmptyHint : trendSkyCopy.emptyHint

    return (
      <Notice
        mark={failed ? '⚠' : '✦'}
        title={failed ? trendSkyCopy.failed : emptyTitle}
        hint={failed ? trendSkyCopy.failedHint : emptyHint}
      />
    )
  }

  return (
    <div className={styles.field} role="group" aria-label={trendSkyCopy.fieldLabel}>
      <div className={styles.canvas}>
        {ranked.map((trend, index) => {
          const slot = trendSlots[index]
          const [x, y] = slot.at
          const [narrowX, narrowY] = slot.atNarrow || slot.at
          // Area, not diameter, carries the count — a star twice as wide should not read
          // as four times the news.
          const scale =
            TREND_MIN_SCALE + (1 - TREND_MIN_SCALE) * Math.sqrt(trend.articleCount / topCount)

          return (
            <div
              key={trend.nodeKey}
              className={styles.node}
              style={{
                '--x': `${x}%`,
                '--y': `${y}%`,
                '--narrow-x': `${narrowX}%`,
                '--narrow-y': `${narrowY}%`,
                '--scale': scale,
              }}
            >
              <button
                type="button"
                className={styles.star}
                onClick={() => open(trend, { trailMode: 'reset' })}
                aria-label={`${trendSkyCopy.rank(trend.rank)} ${trend.label}`}
              >
                <img src={stars.event} alt="" aria-hidden />
              </button>

              <div className={styles.text}>
                <p className={styles.label}>{formatTrendGraphLabel(trend)}</p>
                <p className={styles.meta}>
                  <span className={styles.rank}>{trendSkyCopy.rank(trend.rank)}</span>
                </p>
              </div>
            </div>
          )
        })}
      </div>

      {!sample && source?.snapshotAt && (
        <p className={styles.snapshot}>
          {trendSkyCopy.snapshot(formatSnapshot(source.snapshotAt))}
        </p>
      )}
    </div>
  )
}

/** 로딩·실패·빈 결과를 같은 자리에 같은 모양으로 알린다. */
function Notice({ mark, title, hint, onBack }) {
  return (
    <div className={styles.field} role="group" aria-label={trendSkyCopy.fieldLabel}>
      {onBack && (
        <button type="button" className={styles.back} onClick={onBack}>
          {trendSkyExpandCopy.back}
        </button>
      )}

      <div className={styles.empty}>
        <span aria-hidden>{mark}</span>
        <p aria-live="polite">{title}</p>
        {hint && <p className={styles.emptyHint}>{hint}</p>}
      </div>
    </div>
  )
}

/** `2026-09-17T06:00:00+09:00` → `9월 17일 06시`. The offset is the server's, so it is read
 *  out of the string rather than through a Date, which would shift it to this machine's
 *  zone and quietly move a 06:00 round to the day before. */
function formatSnapshot(snapshotAt) {
  const match = /^\d{4}-(\d{2})-(\d{2})T(\d{2})/.exec(snapshotAt)
  if (!match) return snapshotAt
  const [, month, day, hour] = match
  return `${Number(month)}월 ${Number(day)}일 ${hour}시`
}
