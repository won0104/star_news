import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  constellationEvents,
  constellationLayouts,
  constellationStart,
  panelCopy,
  stars,
  trendFigmaAssets,
} from '../../data/trend'
import { fetchNodeArticles } from '../../api/trend'
import { edgeLabels, nodeTypeLabels } from '../../data/trendNeighbors'
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

const PREVIEW_LIMITS = {
  EVENT: 2,
  ENTITY: 2,
  STATEMENT: 1,
}

const PREVIEW_POINTS = {
  relatedLeft: [
    [-15.5, -5.5],
    [-14, 3],
    [-10.5, 10],
    [-3.5, 14.5],
    [-16.5, 12],
  ],
  relatedRight: [
    [15.5, -7],
    [14, 2],
    [10.5, 9],
    [3.5, 13.5],
    [16.5, 11],
  ],
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
 * The composition has one centre, two related-event slots, two entity slots and one
 * statement slot, so a response is sorted into those four buckets and each takes as many
 * as it has room for. The response is already neighborScore descending, so what survives
 * the trim is the strongest of each kind rather than whatever came first.
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
        label: node.label,
        meta: metaFor(node.nodeKey),
        event: node.nodeKey,
        nodeType: node.nodeType,
      }))

  return {
    centre: [
      {
        id: centre.nodeKey,
        label: centre.label,
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

/**
 * 다음 중심 화면에 실제로 배치될 후보만 고른 뒤, 현재 화면에서 이미 보이는 Node는
 * 중복으로 그리지 않는다. 보이는 Node도 슬롯 수에는 포함해야 전환 뒤 구성과 어긋나지 않는다.
 */
function previewNodesFor(graph, visibleNodeKeys) {
  const taken = { EVENT: 0, ENTITY: 0, STATEMENT: 0 }

  return (graph?.nodes ?? []).reduce((preview, node) => {
    const limit = PREVIEW_LIMITS[node.nodeType]
    if (!limit || taken[node.nodeType] >= limit) return preview
    taken[node.nodeType] += 1
    if (visibleNodeKeys.has(node.nodeKey)) return preview
    preview.push(node)
    return preview
  }, [])
}

function previewSummary(nodes) {
  const count = { EVENT: 0, ENTITY: 0, STATEMENT: 0 }
  nodes.forEach((node) => {
    count[node.nodeType] += 1
  })

  return [
    count.EVENT ? `사건 ${count.EVENT}` : '',
    count.ENTITY ? `개체 ${count.ENTITY}` : '',
    count.STATEMENT ? `발언 ${count.STATEMENT}` : '',
  ]
    .filter(Boolean)
    .join(', ')
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

function StarArt({ role, nodeType }) {
  return (
    <span className={`${styles.art} ${styles.portableArt}`} aria-hidden>
      <img className={styles.mobileStar} src={NODE_STAR[nodeType] ?? ROLE_STAR[role]} alt="" />
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
  articlePanelOpen,
  onArticlePanelOpenChange,
  onBack,
  onWalk,
  articleSamples,
  overlayRoot,
  trail,
  onTrailSelect,
}) {
  const [centreId, setCentreId] = useState(constellationStart)
  const [localPanelOpen, setLocalPanelOpen] = useState(false)
  const [full, setFull] = useState(false)
  const articlePageRequestRef = useRef(null)
  const trailRef = useRef(null)
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
  const layoutKey = graph ? 'spread' : constellationEvents[centreId].layout
  const layout = constellationLayouts[layoutKey] ?? constellationLayouts.spread
  const bySlot = graph ? bySlotFromGraph(graph) : bySlotFromMock(centreId)
  const nodes = nodesFor(bySlot, narrow, layout.slots)
  const centre = nodes[0]
  const centreType = graph ? graph.centerNode.nodeType : 'EVENT'
  const visibleNodeKeys = new Set(nodes.map((node) => node.id))
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
    setOpen(!open)
  }

  const walkTo = (node) => {
    if (onWalk) {
      onWalk(node)
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
    list.addEventListener('wheel', onWheel, { passive: false })
    list.scrollTo({ left: list.scrollWidth })

    return () => list.removeEventListener('wheel', onWheel)
  }, [full, trail])

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
      className={`${styles.field} ${full ? styles.fieldFull : ''}`}
      data-layout={layoutKey}
      role="group"
      aria-label={panelCopy.fieldLabel}
    >
      <div className={styles.fieldActions}>
        {onBack && !full && (
          <button type="button" className={styles.fieldAction} onClick={onBack}>
            <span aria-hidden>←</span>
            오늘의 트렌드
          </button>
        )}

        <button
          type="button"
          className={styles.fieldAction}
          onClick={full ? leaveFull : enterFull}
          aria-pressed={full}
        >
          <span aria-hidden>{full ? '↙' : '↗'}</span>
          {full ? '전체화면 나가기' : '전체보기'}
        </button>
      </div>

      {trail?.length > 0 && (
        <nav className={styles.trail} aria-label="그래프 탐색 경로">
          <span className={styles.trailStart}>시작</span>
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
                    <span>{nodeTypeLabels[item.nodeType] ?? item.nodeType}</span>
                    {item.label}
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
          const art = <StarArt role={role} nodeType={isCentre ? centreType : node.nodeType} />
          const previewNodes =
            role === 'related' ? previewNodesFor(previewGraphs?.[node.id], visibleNodeKeys) : []
          const previewText = previewSummary(previewNodes)

          return (
            <div
              key={node.id}
              className={`${styles.node} ${ROLE_CLASS[role]} ${styles[`${visual}Node`]}`}
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
                    const [x, y] = PREVIEW_POINTS[visual][previewIndex]
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
                            '--preview-delay': `${previewIndex * 55}ms`,
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
                    ? `${node.label} — ${panelCopy.open(articles?.totalCount ?? 0)}`
                    : `${node.label} — ${panelCopy.recentre}${previewText ? `; 다음 구성 ${previewText}` : ''}`
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
