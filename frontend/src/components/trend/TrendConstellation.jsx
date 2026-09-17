import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ambientLayouts,
  ambientStars,
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

const AMBIENT_ART = {
  event: trendFigmaAssets.relatedLeftSticker,
  entity: trendFigmaAssets.entitySticker,
  statement: trendFigmaAssets.statementSticker,
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
    centre: [{ id: centre.nodeKey, label: centre.label, meta: '지금 보는 사건', event: centre.nodeKey }],
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
export function TrendConstellation({ graph, onBack, onWalk, details, articleSamples }) {
  const [centreId, setCentreId] = useState(constellationStart)
  const [open, setOpen] = useState(false)
  const [full, setFull] = useState(false)
  // 사용자가 직접 연 Node. 없으면 카드는 중심 Node 를 설명한다.
  const [picked, setPicked] = useState(null)
  const [pickedState, setPickedState] = useState('idle')
  const [articles, setArticles] = useState(null)
  const [articlesState, setArticlesState] = useState('idle')
  const narrow = useIsNarrow()
  // A graph has no authored layout key of its own, so it takes the default composition.
  const layoutKey = graph ? 'spread' : constellationEvents[centreId].layout
  const layout = constellationLayouts[layoutKey] ?? constellationLayouts.spread
  const ambientLayout = ambientLayouts[layoutKey] ?? ambientLayouts.spread
  const bySlot = graph ? bySlotFromGraph(graph) : bySlotFromMock(centreId)
  const nodes = nodesFor(bySlot, narrow, layout.slots)
  const centre = nodes[0]
  const at = (node) => (narrow ? node.slot.atNarrow : node.slot.at)

  /**
   * 인물·기관과 발언을 눌렀을 때. 이 둘은 중심이 되지 않고 카드로만 펼친다 — 중심 자리의
   * 슬롯 배분이 Event 기준이라, Entity 를 가운데 두면 related/entity 칸이 맞지 않는다.
   *
   * `details` gives the sample its answers without a request: those keys are not in Neo4j,
   * so asking for them would only 404.
   */
  const openDetail = (node, nodeType) => {
    const ready = details?.[node.id]
    if (ready) {
      setPicked(ready)
      setPickedState('ready')
      return
    }

    setPicked({ nodeType, nodeKey: node.id, title: node.label })
    setPickedState('loading')
    fetchNodeDetail(nodeType, node.id)
      .then((payload) => {
        setPicked(payload)
        setPickedState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setPickedState('failed')
      })
  }

  /**
   * 중심 별을 눌렀을 때. 패널을 열면서 그 Node 의 기사를 가져온다.
   *
   * `articleSamples` answers for the sampled sky, whose keys are not in Neo4j. `cursor`
   * is passed for 더 보기, and the page is appended rather than replacing what is read.
   */
  const loadArticles = (cursor) => {
    const centreKey = centre.event
    const centreType = graph ? graph.centerNode.nodeType : 'EVENT'

    const ready = !cursor && articleSamples?.[centreKey]
    if (ready) {
      setArticles(ready)
      setArticlesState('ready')
      return
    }

    if (!cursor) setArticles(null)
    setArticlesState('loading')
    fetchNodeArticles(centreType, centreKey, { cursor })
      .then((payload) => {
        setArticles((was) =>
          cursor && was
            ? { ...payload, articles: [...was.articles, ...payload.articles] }
            : payload,
        )
        setArticlesState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setArticlesState('failed')
      })
  }

  const togglePanel = () => {
    const next = !open
    setOpen(next)
    if (next && articlesState === 'idle') loadArticles()
  }

  const walkTo = (node) => {
    if (onWalk) {
      onWalk(node)
      return
    }
    setCentreId(node.event)
    setOpen(false)
    setPicked(null)
    setPickedState('idle')
    setArticles(null)
    setArticlesState('idle')
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

  const board = (
    <div
      className={`${styles.field} ${full ? styles.fieldFull : ''}`}
      data-layout={layoutKey}
      role="group"
      aria-label={panelCopy.fieldLabel}
    >
      <span className={styles.layoutBadge}>구도 · {layout.label}</span>

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
        <div className={styles.ambientLayer} aria-hidden>
          {ambientStars.map((star, index) => {
            const starAt = ambientLayout[index] ?? star.at

            return (
              <span
                key={star.id}
                className={`${styles.ambientStar} ${styles[`ambient${star.role[0].toUpperCase()}${star.role.slice(1)}`]}`}
                data-star-id={star.id}
                data-related-events={star.events.join(' ')}
                style={{
                  left: `${starAt[0]}%`,
                  top: `${starAt[1]}%`,
                  width: `${star.size / 14.4}cqw`,
                  opacity: (star.opacity ?? 0.9) * 0.42,
                  transform: `translate(-50%, -50%) rotate(${star.rotate}deg)`,
                }}
              >
                <img src={AMBIENT_ART[star.role]} alt="" />
              </span>
            )
          })}
        </div>

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
              {isEvent ? (
                <button
                  type="button"
                  className={styles.starButton}
                  aria-expanded={isCentre ? open : undefined}
                  aria-controls={isCentre ? PANEL_ID : undefined}
                  aria-label={
                    isCentre
                      ? `${node.label} — ${panelCopy.open(articles?.totalCount ?? 0)}`
                      : `${node.label} — ${panelCopy.recentre}`
                  }
                  onClick={isCentre ? togglePanel : () => walkTo(node)}
                >
                  {art}
                </button>
              ) : (
                <button
                  type="button"
                  className={styles.starButton}
                  aria-label={`${node.label} — 상세 보기`}
                  onClick={() => openDetail(node, role === 'entity' ? 'ENTITY' : 'STATEMENT')}
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

      {graph && (
        <DetailCard
          // 중심이 바뀌거나 다른 Node 를 고르면 새로 마운트돼 닫힘 상태가 풀린다.
          key={`${graph.centerNode.nodeKey}:${picked?.nodeKey ?? ''}`}
          centre={graph.centerNode}
          sample={details?.[graph.centerNode.nodeKey]}
          picked={picked}
          pickedState={pickedState}
        />
      )}

      <TrendPanel
        id={PANEL_ID}
        data={articles}
        state={articlesState}
        title={centre.label}
        open={open}
        onClose={() => setOpen(false)}
        onMore={() => loadArticles(articles?.nextCursor)}
      />
    </div>
  )

  return full ? createPortal(board, document.body) : board
}

/**
 * 카드가 무엇을 설명할지 고른다 — 고른 Node 가 있으면 그것, 없으면 중심 Node.
 *
 * Its own component so a centre change or a new pick remounts it through the `key`,
 * which resets the closed flag without an effect writing state during a render pass.
 * The centre's own detail is fetched here rather than by the screen above, because this
 * is the only place that needs it.
 */
function DetailCard({ centre, sample, picked, pickedState }) {
  const [closed, setClosed] = useState(false)
  const [fetched, setFetched] = useState(null)
  const [state, setState] = useState(sample ? 'ready' : 'loading')

  useEffect(() => {
    if (sample) return
    const controller = new AbortController()
    fetchNodeDetail(centre.nodeType, centre.nodeKey, { signal: controller.signal })
      .then((payload) => {
        setFetched(payload)
        setState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setState('failed')
      })
    return () => controller.abort()
  }, [centre, sample])

  if (closed) return null

  return (
    <NodeDetailPanel
      node={picked ?? sample ?? fetched}
      state={picked ? pickedState : sample ? 'ready' : state}
      onClose={() => setClosed(true)}
    />
  )
}
