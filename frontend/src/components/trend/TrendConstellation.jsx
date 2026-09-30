import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  constellationEvents,
  constellationLayouts,
  constellationStart,
  panelCopy,
  stars,
  visitedStar,
  trendFigmaAssets,
} from '../../data/trend'
import { fetchNodeArticles } from '../../api/trend'
import { edgeLabels, nodeTypeLabels } from '../../data/graphLabels'
import { formatTrendGraphLabel } from '../../data/trendNeighbors'
import { useIsNarrow } from '../../hooks/useIsNarrow'
import { TrendPanel } from './TrendPanel'
import styles from './TrendConstellation.module.css'

const PANEL_ID = 'trend-articles'

const ROLE_CLASS = {
  centre: styles.centreNode,
  related: styles.relatedNode,
  entity: styles.entityNode,
  statement: styles.statementNode,
}

const ROLE_STAR = {
  centre: stars.event,
  related: stars.event,
  entity: stars.entity,
  statement: stars.statement,
}

const NODE_STAR = {
  EVENT: stars.event,
  ENTITY: stars.entity,
  STATEMENT: stars.statement,
}


const PREVIEW_STAR = {
  EVENT: trendFigmaAssets.relatedLeftSticker,
  ENTITY: trendFigmaAssets.entitySticker,
  STATEMENT: trendFigmaAssets.statementSticker,
}

const PREVIEW_RING_CAPACITIES = [6, 10, 14]
const PREVIEW_RING_RADII = [10, 14, 18]

/** 다음 Event들을 현재 별에서 바깥쪽으로 펼친 세 겹의 반원에 놓는다. */
function previewPoint(index, total, visual) {
  let ring = 0
  let offset = index
  while (ring < PREVIEW_RING_CAPACITIES.length - 1 && offset >= PREVIEW_RING_CAPACITIES[ring]) {
    offset -= PREVIEW_RING_CAPACITIES[ring]
    ring += 1
  }

  const usedBefore = PREVIEW_RING_CAPACITIES.slice(0, ring).reduce((sum, count) => sum + count, 0)
  const count = Math.min(PREVIEW_RING_CAPACITIES[ring], total - usedBefore)
  const centreAngle = visual === 'relatedLeft' ? Math.PI : visual === 'relatedBottom' ? Math.PI / 2 : 0
  const span = Math.PI * 0.86
  const angle = count <= 1 ? centreAngle : centreAngle - span / 2 + (span * offset) / (count - 1)
  const radius = PREVIEW_RING_RADII[ring]

  return [Math.cos(angle) * radius, Math.sin(angle) * radius]
}

/** 목업 별자리 한 벌을 슬롯별 후보로 정리한다. */
function bySlotFromMock(centreId) {
  const centre = constellationEvents[centreId]
  return {
    centre: [{ id: centre.id, label: centre.label, meta: centre.meta, event: centre.id }],
    related: centre.related.map((id) => {
      const event = constellationEvents[id]
      return { id: event.id, label: event.label, meta: event.meta, event: event.id }
    }),
    entity: centre.entities,
    statement: centre.statements,
  }
}

/**
 * `GET /graphs/nodes/{type}/{key}/neighbors` 응답 하나를 같은 후보 목록으로 옮긴다.
 *
 * The desktop composition has one centre and eight neighbor slots; the compact layout
 * keeps two related Events and one Statement around the centre. A response is sorted into
 * type buckets and each takes as many nodes as its slots allow. The response is already
 * neighborScore descending, so what survives the trim is the strongest of each kind.
 *
 * TIME nodes have no slot in this composition and are dropped. `meta` is the relation's
 * own name, which is the one thing the mock carried that the graph does not.
 */
function bySlotFromGraph(graph) {
  const centre = graph.centerNode
  const metaFor = (nodeKey) => {
    const edge = graph.edges?.find((e) => e.targetNodeKey === nodeKey)
    return edgeLabels[edge?.edgeType] ?? edge?.edgeType ?? ''
  }
  const of = (nodeType) =>
    (graph.nodes ?? [])
      .filter((node) => node.nodeType === nodeType)
      .map((node) => ({
        id: node.nodeKey,
        label: formatTrendGraphLabel(node),
        fullLabel: node.label,
        meta: metaFor(node.nodeKey),
        event: node.nodeKey,
        nodeType: node.nodeType,
      }))

  return {
    centre: [
      {
        id: centre.nodeKey,
        label: formatTrendGraphLabel(centre),
        fullLabel: centre.label,
        meta: '지금 보는 중심 노드',
        event: centre.nodeKey,
        nodeType: centre.nodeType,
      },
    ],
    related: of('EVENT'),
    entity: of('ENTITY'),
    statement: of('STATEMENT'),
  }
}

function nodesFor(bySlot, narrow, layoutSlots) {
  const slots = layoutSlots.filter((slot) => !(narrow && slot.hideNarrow))
  const taken = { centre: 0, related: 0, entity: 0, statement: 0 }

  return slots
    .map((slot) => {
      const node = bySlot[slot.role][taken[slot.role]]
      taken[slot.role] += 1
      return node ? { ...node, slot } : null
    })
    .filter(Boolean)
}

/** 유형별 표시 슬롯을 고려한 실제 주변 별 수에 맞춰 상세 탐색 구도를 고른다. */
function graphLayoutKey(graph) {
  const counts = (graph?.nodes ?? []).reduce(
    (result, node) => ({ ...result, [node.nodeType]: (result[node.nodeType] ?? 0) + 1 }),
    {},
  )
  const visibleCount =
    Math.min(counts.EVENT ?? 0, 3) +
    Math.min(counts.ENTITY ?? 0, 4) +
    Math.min(counts.STATEMENT ?? 0, 1)

  if (visibleCount <= 3) return 'graphSparse'
  if (visibleCount <= 6) return 'graphBalanced'
  return 'graphDense'
}

/**
 * 다음 중심 화면에 실제로 배치될 후보만 고른 뒤, 현재 화면에서 이미 보이는 Node는
 * 중복으로 그리지 않는다. 보이는 Node도 슬롯 수에는 포함해야 전환 뒤 구성과 어긋나지 않는다.
 */
function previewNodesFor(graph) {
  return (graph?.nodes ?? []).filter((node) => node.nodeType === 'EVENT')
}

function scrollTrailHorizontally(event) {
  const list = event.currentTarget
  if (list.scrollWidth <= list.clientWidth) return

  const rawDelta =
    Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  if (!rawDelta) return

  event.preventDefault()
  const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? list.clientWidth : 1
  list.scrollLeft += rawDelta * unit
}

/** `visited` 면 색 계열이 다른 같은 모양을 쓴다 — 자리와 크기는 그대로다. */
function StarArt({ role, nodeType, visited = false }) {
  const src = visited ? visitedStar : (NODE_STAR[nodeType] ?? ROLE_STAR[role])

  return (
    <span className={`${styles.art} ${styles.portableArt}`} aria-hidden>
      <img className={styles.mobileStar} src={src} alt="" />
    </span>
  )
}

/**
 * `graph`를 주면 그 주변 그래프를 그리고, 없으면 목업 별자리를 그린다.
 *
 * Either way the composition is the same — one centre with its parts hung on the authored
 * slots — so 오늘의 트렌드 keeps the picture it always had while the data behind it moves
 * from the mock to the endpoint. `onWalk` is how a related event re-centres when the
 * caller owns the loading; without it the mock's own walk is used.
 */
export function TrendConstellation({
  graph,
  previewGraphs,
  journey,
  articlePanelOpen,
  onArticlePanelOpenChange,
  onWalk,
  articleSamples,
  overlayRoot,
  trail,
  onTrailSelect,
}) {
  const [centreId, setCentreId] = useState(constellationStart)
  const [localPanelOpen, setLocalPanelOpen] = useState(false)
  const [candidatePanelOpen, setCandidatePanelOpen] = useState(false)
  const [full, setFull] = useState(false)
  const articlePageRequestRef = useRef(null)
  const trailRef = useRef(null)
  // 경로가 칸을 넘칠 때 어느 쪽으로 더 갈 수 있는지. 그쪽 끝에만 화살표를 세운다.
  const [trailEdges, setTrailEdges] = useState({ start: false, end: false })
  const [articles, setArticles] = useState(null)
  const [articlesState, setArticlesState] = useState('idle')
  const [articlesKey, setArticlesKey] = useState(null)
  const open = articlePanelOpen ?? localPanelOpen
  const setOpen = (next) => {
    if (onArticlePanelOpenChange) onArticlePanelOpenChange(next)
    else setLocalPanelOpen(next)
  }
  const narrow = useIsNarrow()
  // A graph has no authored layout key of its own, so it takes the default composition.
  const layoutKey = graph ? graphLayoutKey(graph) : constellationEvents[centreId].layout
  const layout = constellationLayouts[layoutKey] ?? constellationLayouts.spread
  const bySlot = graph ? bySlotFromGraph(graph) : bySlotFromMock(centreId)
  const nodes = nodesFor(bySlot, narrow, layout.slots)
  const centre = nodes[0]
  const centreType = graph ? graph.centerNode.nodeType : 'EVENT'
  const visibleNodeKeys = new Set(nodes.map((node) => node.id))
  const candidates = (graph?.nodes ?? []).slice(0, 15)
  // trail 의 마지막은 지금 중심이다. 그 앞의 것들이 이미 지나온 별이다.
  const visitedKeys = new Set((trail ?? []).slice(0, -1).map((item) => item.nodeKey))
  const at = (node) => (narrow ? node.slot.atNarrow : node.slot.at)

  /** 현재 Event의 다음 기사 페이지를 기존 카드에 이어 붙인다. */
  const loadMoreArticles = (cursor) => {
    if (!cursor || articlesKey !== centre.event) return

    articlePageRequestRef.current?.abort()
    const controller = new AbortController()
    articlePageRequestRef.current = controller
    setArticlesState('loading')
    fetchNodeArticles(centreType, centre.event, { cursor, signal: controller.signal })
      .then((payload) => {
        if (controller.signal.aborted) return
        setArticles((was) => ({
          ...payload,
          articles: [...(was?.articles ?? []), ...payload.articles],
        }))
        setArticlesState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setArticlesState('failed')
      })
      .finally(() => {
        if (articlePageRequestRef.current === controller) articlePageRequestRef.current = null
      })
  }

  const togglePanel = () => {
    setCandidatePanelOpen(false)
    setOpen(!open)
  }

  const toggleCandidatePanel = () => {
    setOpen(false)
    setCandidatePanelOpen((current) => !current)
  }

  const walkTo = (node) => {
    if (onWalk) {
      onWalk(
        { ...node, label: node.fullLabel ?? node.label },
        node.slot
          ? {
              x: at(node)[0],
              y: at(node)[1],
            }
          : null,
      )
      return
    }
    setCentreId(node.event)
  }

  const enterFull = useCallback(() => {
    setFull(true)
    document.documentElement.requestFullscreen?.().catch(() => {})
  }, [])

  const leaveFull = useCallback(() => {
    setFull(false)
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  }, [])

  /**
   * 패널이 열린 채 중심 Event가 바뀌면 카드는 유지하고 내용만 새 Event 기준으로 바꾼다.
   * 현재 key의 응답이 도착하기 전에는 이전 기사를 섞지 않고 loading 상태를 보여준다.
   */
  useEffect(() => {
    if (!open || articlesKey === centre.event) return undefined

    articlePageRequestRef.current?.abort()
    const controller = new AbortController()
    const centreKey = centre.event
    const ready = articleSamples?.[centreKey]
    const request = ready
      ? Promise.resolve(ready)
      : fetchNodeArticles(centreType, centreKey, { signal: controller.signal })

    request
      .then((payload) => {
        if (controller.signal.aborted) return
        setArticles(payload)
        setArticlesKey(centreKey)
        setArticlesState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setArticles(null)
        setArticlesKey(centreKey)
        setArticlesState('failed')
      })

    return () => controller.abort()
  }, [articleSamples, articlesKey, centre.event, centreType, open])

  useEffect(() => {
    return () => {
      articlePageRequestRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    const list = trailRef.current
    if (!list) return

    const onWheel = (event) => scrollTrailHorizontally(event)
    // 1px 여유는 소수점 폭에서 끝에 닿아도 scrollLeft 가 끝값에 조금 못 미치는 경우를 받는다.
    const updateEdges = () =>
      setTrailEdges({
        start: list.scrollLeft > 1,
        end: list.scrollLeft + list.clientWidth < list.scrollWidth - 1,
      })
    const observer = new ResizeObserver(updateEdges)
    list.addEventListener('wheel', onWheel, { passive: false })
    list.addEventListener('scroll', updateEdges, { passive: true })
    observer.observe(list)
    list.scrollTo({ left: list.scrollWidth })
    updateEdges()

    return () => {
      list.removeEventListener('wheel', onWheel)
      list.removeEventListener('scroll', updateEdges)
      observer.disconnect()
    }
  }, [full, trail])

  /** 화살표는 한 칸씩이 아니라 그 방향 끝까지 보낸다 — 경로의 처음과 지금 자리로. */
  const scrollTrailTo = (edge) => {
    const list = trailRef.current
    if (!list) return
    list.scrollTo({ left: edge === 'start' ? 0 : list.scrollWidth, behavior: 'smooth' })
  }

  useEffect(() => {
    const onFullscreenChange = () => {
      if (!document.fullscreenElement) setFull(false)
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') leaveFull()
    }

    document.addEventListener('fullscreenchange', onFullscreenChange)
    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.removeEventListener('fullscreenchange', onFullscreenChange)
      document.removeEventListener('keydown', onKeyDown)
      if (document.fullscreenElement) {
        document.exitFullscreen?.().catch(() => {})
      }
    }
  }, [leaveFull])

  const articleIsCurrent = articlesKey === centre.event
  const articlePanel = (
    <TrendPanel
      id={PANEL_ID}
      data={articleIsCurrent ? articles : null}
      state={open && !articleIsCurrent ? 'loading' : articlesState}
      title={centre.label}
      node={{ nodeType: centreType, nodeKey: centre.event }}
      open={open}
      onClose={() => setOpen(false)}
      onMore={() => loadMoreArticles(articles?.nextCursor)}
    />
  )

  const overlays = articlePanel

  const board = (
    <div
      className={`${styles.field} ${full ? styles.fieldFull : ''} ${journey?.phase === 'departing' ? styles.fieldDeparting : ''} ${journey?.phase === 'arriving' ? styles.fieldArriving : ''}`}
      data-layout={layoutKey}
      role="group"
      aria-label={panelCopy.fieldLabel}
      style={{
        '--journey-x': `${journey?.x ?? 50}%`,
        '--journey-y': `${journey?.y ?? 50}%`,
        '--journey-shift-x': `${(50 - (journey?.x ?? 50)) * 0.34}%`,
        '--journey-shift-y': `${(50 - (journey?.y ?? 50)) * 0.34}%`,
        '--journey-arrive-x': `${((journey?.x ?? 50) - 50) * 0.1}%`,
        '--journey-arrive-y': `${((journey?.y ?? 50) - 50) * 0.1}%`,
      }}
    >
      {/* 순위로 돌아가는 단추는 두지 않는다 — Esc 와 레일의 "오늘의 트렌드"가 그 길이다. */}
      <div className={styles.fieldActions}>
        <button
          type="button"
          className={styles.fieldAction}
          onClick={full ? leaveFull : enterFull}
          aria-pressed={full}
        >
          <span aria-hidden>{full ? '↙' : '↗'}</span>
          {full ? '전체화면 나가기' : '전체보기'}
        </button>

        {graph && candidates.length > 0 && (
          <button
            type="button"
            className={styles.fieldAction}
            aria-expanded={candidatePanelOpen}
            aria-controls="trend-candidates"
            onClick={toggleCandidatePanel}
          >
            <span aria-hidden>✦</span>
            더보기 {candidates.length}
          </button>
        )}
      </div>

      {trail?.length > 0 && (
        <nav className={styles.trail} aria-label="그래프 탐색 경로">
          {/* 넘친 쪽에만 선다. 경로 위에 겹쳐 띄워, 나타나고 사라져도 경로의 폭이 바뀌지 않는다. */}
          {trailEdges.start && (
            <button
              type="button"
              className={`${styles.trailEdge} ${styles.trailEdgeStart}`}
              aria-label="경로 처음으로"
              onClick={() => scrollTrailTo('start')}
            >
              ‹
            </button>
          )}
          {trailEdges.end && (
            <button
              type="button"
              className={`${styles.trailEdge} ${styles.trailEdgeEnd}`}
              aria-label="경로 끝으로"
              onClick={() => scrollTrailTo('end')}
            >
              ›
            </button>
          )}
          <ol ref={trailRef}>
            {trail.map((item, index) => {
              const current = index === trail.length - 1
              return (
                <li key={`${item.nodeType}:${item.nodeKey}:${index}`}>
                  {index > 0 && <span className={styles.trailArrow} aria-hidden>›</span>}
                  <button
                    type="button"
                    className={styles.trailNode}
                    aria-current={current ? 'location' : undefined}
                    disabled={current}
                    title={item.label}
                    onClick={() => onTrailSelect?.(item, index)}
                  >
                    <span className={styles.trailType}>
                      {nodeTypeLabels[item.nodeType] ?? item.nodeType}
                    </span>
                    <span className={styles.trailLabel}>{item.label}</span>
                  </button>
                </li>
              )
            })}
          </ol>
        </nav>
      )}

      <div className={styles.canvas}>
        <svg
          className={`${styles.mobileLinks} ${styles.variantLinks}`}
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden
        >
          {nodes.slice(1).map((node) => (
            <line
              key={`link-${node.id}`}
              x1={at(centre)[0]}
              y1={at(centre)[1]}
              x2={at(node)[0]}
              y2={at(node)[1]}
            />
          ))}
        </svg>

        {nodes.map((node, index) => {
          const { role, visual } = node.slot
          const isCentre = role === 'centre'
          const art = (
            <StarArt
              role={role}
              nodeType={isCentre ? centreType : node.nodeType}
              visited={!isCentre && visitedKeys.has(node.id)}
            />
          )
          const previewGraph = role === 'related' ? previewGraphs?.[node.id] : null
          const previewNodes = previewNodesFor(previewGraph)

          return (
            <div
              key={node.id}
              className={`${styles.node} ${ROLE_CLASS[role]} ${styles[`${visual}Node`]} ${isCentre && journey?.phase === 'arriving' ? styles.centreArrival : ''}`}
              style={{
                left: `${at(node)[0]}%`,
                top: `${at(node)[1]}%`,
                animationDelay: `${index * 90}ms`,
              }}
            >
              {previewNodes.length > 0 && (
                <div
                  className={`${styles.previewCluster} ${styles[`${visual}Preview`]}`}
                  aria-hidden
                >
                  {previewNodes.map((preview, previewIndex) => {
                    const [x, y] = previewPoint(previewIndex, previewNodes.length, visual)
                    const lineLength = Math.hypot(x, y)
                    const lineAngle = Math.atan2(-y, -x)

                    return (
                      <Fragment key={preview.nodeKey}>
                        <span
                          className={styles.previewLink}
                          style={{
                            '--preview-x': `${x}cqw`,
                            '--preview-y': `${y}cqw`,
                            '--preview-line-length': `${lineLength}cqw`,
                            '--preview-line-angle': `${lineAngle}rad`,
                          }}
                        />
                        <span
                          className={`${styles.previewStar} ${styles[`preview${preview.nodeType[0]}${preview.nodeType.slice(1).toLowerCase()}`]}`}
                          data-node-type={preview.nodeType}
                          style={{
                            '--preview-x': `${x}cqw`,
                            '--preview-y': `${y}cqw`,
                            '--preview-delay': `${Math.min(previewIndex, 10) * 24}ms`,
                            '--preview-rotate': `${previewIndex % 2 === 0 ? -6 : 7}deg`,
                          }}
                        >
                          <img src={PREVIEW_STAR[preview.nodeType]} alt="" />
                        </span>
                      </Fragment>
                    )
                  })}
                </div>
              )}

              <button
                type="button"
                className={styles.starButton}
                aria-expanded={isCentre ? open : undefined}
                aria-controls={isCentre ? PANEL_ID : undefined}
                aria-label={
                  isCentre
                    ? `${node.fullLabel ?? node.label} — ${panelCopy.open(articles?.totalCount ?? 0)}`
                    : `${node.fullLabel ?? node.label} — ${panelCopy.recentre}`
                }
                onClick={isCentre ? togglePanel : () => walkTo(node)}
              >
                {art}
              </button>

              <div className={`${styles.text} ${styles[`${visual}Text`]}`}>
                <p className={styles.label}>{node.label}</p>
                <p className={styles.meta}>{node.meta}</p>
              </div>
            </div>
          )
        })}
      </div>

      {candidatePanelOpen && (
        <aside id="trend-candidates" className={styles.candidatePanel} aria-label="주변 노드 후보">
          <div className={styles.candidateHeader}>
            <div>
              <p>주변 후보</p>
              <span>별자리에 없는 후보도 선택해 중심으로 이동할 수 있습니다.</span>
            </div>
            <button type="button" onClick={() => setCandidatePanelOpen(false)} aria-label="후보 목록 닫기">
              ×
            </button>
          </div>

          <ol className={styles.candidateList}>
            {candidates.map((candidate, index) => {
              const visible = visibleNodeKeys.has(candidate.nodeKey)
              const navigable = candidate.nodeType !== 'TIME'
              return (
                <li key={`${candidate.nodeType}:${candidate.nodeKey}`}>
                  <button
                    type="button"
                    disabled={!navigable}
                    onClick={() => {
                      if (!navigable) return
                      setCandidatePanelOpen(false)
                      walkTo({
                        id: candidate.nodeKey,
                        event: candidate.nodeKey,
                        label: candidate.label,
                        nodeType: candidate.nodeType,
                      })
                    }}
                  >
                    <span className={styles.candidateRank}>{String(index + 1).padStart(2, '0')}</span>
                    <span className={styles.candidateCopy}>
                      <b>{formatTrendGraphLabel(candidate) || '이름 없는 노드'}</b>
                      <small>
                        {nodeTypeLabels[candidate.nodeType] ?? candidate.nodeType}
                        {visible ? ' · 별자리에 표시 중' : ''}
                        {!navigable ? ' · 시간 정보' : ''}
                      </small>
                    </span>
                    {navigable && <span className={styles.candidateArrow} aria-hidden>→</span>}
                  </button>
                </li>
              )
            })}
          </ol>
        </aside>
      )}

      {(full || !overlayRoot) && overlays}
    </div>
  )

  if (full) return createPortal(board, document.body)

  return (
    <>
      {board}
      {overlayRoot && createPortal(overlays, overlayRoot)}
    </>
  )
}
