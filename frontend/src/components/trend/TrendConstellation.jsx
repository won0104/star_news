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
import { fetchNodeArticles, fetchNodeDetail } from '../../api/trend'
import { edgeLabels } from '../../data/trendNeighbors'
import { useIsNarrow } from '../../hooks/useIsNarrow'
import { NodeDetailPanel } from './NodeDetailPanel'
import { TrendPanel } from './TrendPanel'
import styles from './TrendConstellation.module.css'

const PANEL_ID = 'trend-articles'
const DETAIL_ID = 'trend-node-detail'

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
      { id: centre.nodeKey, label: centre.label, meta: '지금 보는 사건', event: centre.nodeKey },
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

function StarArt({ role }) {
  return (
    <span className={`${styles.art} ${styles.portableArt}`} aria-hidden>
      <img className={styles.mobileStar} src={ROLE_STAR[role]} alt="" />
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
  details,
  articleSamples,
  overlayRoot,
}) {
  const [centreId, setCentreId] = useState(constellationStart)
  const [localPanelOpen, setLocalPanelOpen] = useState(false)
  const [full, setFull] = useState(false)
  // 사용자가 직접 연 Entity·Statement. 같은 별을 다시 누르면 선택이 풀린다.
  const [picked, setPicked] = useState(null)
  const [pickedState, setPickedState] = useState('idle')
  const detailRequestRef = useRef(null)
  const articlePageRequestRef = useRef(null)
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

  /**
   * 인물·기관과 발언을 눌렀을 때. 이 둘은 중심이 되지 않고 카드로만 펼친다 — 중심 자리의
   * 슬롯 배분이 Event 기준이라, Entity 를 가운데 두면 related/entity 칸이 맞지 않는다.
   *
   * `details` gives the sample its answers without a request: those keys are not in Neo4j,
   * so asking for them would only 404.
   */
  const closeDetail = () => {
    detailRequestRef.current?.abort()
    detailRequestRef.current = null
    setPicked(null)
    setPickedState('idle')
  }

  const toggleDetail = (node, nodeType) => {
    if (picked?.nodeKey === node.id) {
      closeDetail()
      return
    }

    detailRequestRef.current?.abort()
    detailRequestRef.current = null

    const ready = details?.[node.id]
    if (ready) {
      setPicked(ready)
      setPickedState('ready')
      return
    }

    setPicked({ nodeType, nodeKey: node.id, title: node.label })
    setPickedState('loading')
    const controller = new AbortController()
    detailRequestRef.current = controller
    fetchNodeDetail(nodeType, node.id, { signal: controller.signal })
      .then((payload) => {
        if (controller.signal.aborted) return
        setPicked(payload)
        setPickedState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setPickedState('failed')
      })
      .finally(() => {
        if (detailRequestRef.current === controller) detailRequestRef.current = null
      })
  }

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
    closeDetail()

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
      detailRequestRef.current?.abort()
      articlePageRequestRef.current?.abort()
    }
  }, [])

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

  const detailCard =
    graph && picked ? (
      <NodeDetailPanel
        key={picked.nodeKey}
        id={DETAIL_ID}
        node={picked}
        state={pickedState}
        onClose={closeDetail}
      />
    ) : null

  const articleIsCurrent = articlesKey === centre.event
  const articlePanel = (
    <TrendPanel
      id={PANEL_ID}
      data={articleIsCurrent ? articles : null}
      state={open && !articleIsCurrent ? 'loading' : articlesState}
      title={centre.label}
      open={open}
      onClose={() => setOpen(false)}
      onMore={() => loadMoreArticles(articles?.nextCursor)}
    />
  )

  const overlays = (
    <>
      {detailCard}
      {articlePanel}
    </>
  )

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
          const isEvent = isCentre || role === 'related'
          const art = <StarArt role={role} />
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

              {isEvent ? (
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
              ) : (
                <button
                  type="button"
                  className={styles.starButton}
                  aria-expanded={picked?.nodeKey === node.id}
                  aria-controls={DETAIL_ID}
                  aria-label={`${node.label} — ${picked?.nodeKey === node.id ? '상세 닫기' : '상세 보기'}`}
                  onClick={() => toggleDetail(node, role === 'entity' ? 'ENTITY' : 'STATEMENT')}
                >
                  {art}
                </button>
              )}

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
