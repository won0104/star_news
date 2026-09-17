import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHomeTrends, fetchNeighbors } from '../../api/trend'
import { stars } from '../../data/trend'
import {
  trendNeighbors,
  trendNodeArticles,
  trendNodeDetails,
  trendSkyExpandCopy,
} from '../../data/trendNeighbors'
import { homeTrends, TREND_MIN_SCALE, trendSkyCopy, trendSlots } from '../../data/trendTop'
import { TrendConstellation } from './TrendConstellation'
import styles from './TrendSky.module.css'

/**
 * 오늘의 트렌드 — the ten events `GET /home` ranks, and the graph behind whichever one is
 * pressed.
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
 * sample in data/trendTop.js — and says so on the page. The screen stays worth looking at
 * while the pipeline is being finished, and nobody reads ten invented events as today's
 * news. Set SAMPLE_WHEN_EMPTY to false, or delete it and the `sample` branches, once real
 * rounds are landing.
 */
const SAMPLE_WHEN_EMPTY = true
export function TrendSky({ data: given, neighbors: givenNeighbors, overlayRoot }) {
  const [home, setHome] = useState(given ?? null)
  const [homeState, setHomeState] = useState(given ? 'ready' : 'loading')
  const [openKey, setOpenKey] = useState(null)
  const [graph, setGraph] = useState(null)
  const [graphState, setGraphState] = useState('idle')
  const [previewGraphs, setPreviewGraphs] = useState({})
  const [articlePanelOpen, setArticlePanelOpen] = useState(false)
  // Neighbours do not change while the screen is open, so a key already opened is served
  // from here rather than fetched again.
  const cache = useRef(new Map())
  const activeKeyRef = useRef(null)

  useEffect(() => {
    if (given) return
    const controller = new AbortController()
    // No synchronous setState here: `homeState` already starts at 'loading' when nothing
    // was handed in, so the only writes are the async ones below.
    fetchHomeTrends({ signal: controller.signal })
      .then((payload) => {
        setHome(payload)
        setHomeState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setHomeState('failed')
      })
    return () => controller.abort()
  }, [given])

  const close = useCallback(() => {
    activeKeyRef.current = null
    setOpenKey(null)
    setGraph(null)
    setGraphState('idle')
    setArticlePanelOpen(false)
  }, [])

  useEffect(() => {
    if (!openKey) return
    const onKeyDown = (event) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [openKey, close])

  const live = home?.trends ?? []
  // A published round is the only case that needs no help.
  const sample = SAMPLE_WHEN_EMPTY && homeState !== 'loading' && live.length === 0
  const source = sample ? homeTrends : home
  const trends = source?.trends ?? []
  const ranked = [...trends].sort((a, b) => a.rank - b.rank).slice(0, trendSlots.length)
  const topCount = Math.max(1, ...ranked.map((trend) => trend.articleCount))

  // Not memoised: it only ever lands on an onClick, and it has to read `sample`, which is
  // derived from this render.
  const open = (trend, { preserveGraph = false } = {}) => {
    activeKeyRef.current = trend.nodeKey
    setOpenKey(trend.nodeKey)

    // A sampled sky's keys are not in Neo4j, so asking for them would only 404.
    const ready = sample
      ? trendNeighbors[trend.nodeKey]
      : (givenNeighbors?.[trend.nodeKey] ?? cache.current.get(trend.nodeKey))

    if (ready) {
      setGraph(ready)
      setGraphState('ready')
      return
    }

    if (!preserveGraph) setGraph(null)
    setGraphState('loading')
    fetchNeighbors(trend.nodeType, trend.nodeKey)
      .then((payload) => {
        cache.current.set(trend.nodeKey, payload)
        // A different star may have been pressed while this was in flight.
        if (activeKeyRef.current !== trend.nodeKey) return
        setGraph(payload)
        setGraphState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        if (activeKeyRef.current !== trend.nodeKey) return
        setGraphState('failed')
      })
  }

  /**
   * 화면에 보이는 관련 Event가 다음 중심이 되었을 때의 1-Hop 구성을 미리 가져온다.
   * 작은 별은 별도 장식이 아니라 이 응답을 유형별로 요약한 것이며, 이미 받아 둔 응답은
   * 실제 Event 이동에도 같은 cache를 사용한다.
   */
  useEffect(() => {
    if (graphState !== 'ready' || !graph || sample) return undefined

    const relatedEvents = (graph.nodes ?? [])
      .filter((node) => node.nodeType === 'EVENT')
      .slice(0, 2)
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
            depth: 1,
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
        .slice(0, 2)
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
        articlePanelOpen={articlePanelOpen}
        onArticlePanelOpenChange={setArticlePanelOpen}
        onBack={close}
        onWalk={(node) =>
          open({ nodeType: node.nodeType ?? 'EVENT', nodeKey: node.id }, { preserveGraph: true })
        }
        details={sample ? trendNodeDetails : undefined}
        articleSamples={sample ? trendNodeArticles : undefined}
        overlayRoot={overlayRoot}
      />
    )
  }

  if (homeState === 'loading') {
    return <Notice mark="✦" title={trendSkyCopy.loading} />
  }

  if (ranked.length === 0) {
    return (
      <Notice
        mark={homeState === 'failed' ? '⚠' : '✦'}
        title={homeState === 'failed' ? trendSkyCopy.failed : trendSkyCopy.empty}
        hint={homeState === 'failed' ? trendSkyCopy.failedHint : trendSkyCopy.emptyHint}
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
                onClick={() => open(trend)}
                aria-label={`${trendSkyCopy.rank(trend.rank)} ${trend.label} — ${trendSkyCopy.articles(trend.articleCount)}`}
              >
                <img src={stars.event} alt="" aria-hidden />
              </button>

              <div className={styles.text}>
                <p className={styles.label}>{trend.label}</p>
                <p className={styles.meta}>
                  <span className={styles.rank}>{trendSkyCopy.rank(trend.rank)}</span>
                  {trendSkyCopy.articles(trend.articleCount)}
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
