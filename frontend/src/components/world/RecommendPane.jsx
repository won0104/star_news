import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { recordNodeClick } from '../../api/personalGraph'
import { fetchRecommendationBoard, fetchRecommendationDetail } from '../../api/recommendations'
import {
  BOARD_ASSETS,
  PIN_BY_TONE,
  BOARDS,
  SLOTS,
  boardCopy,
  corkCentre,
  corkPlacement,
} from '../../data/recommendBoard'
import { topicName } from '../../data/topics'
import { useResizableCard } from '../../hooks/useResizableCard'
import { useNearestWindow } from '../../hooks/useNearestWindow'
import { useSession } from '../../store/session'
import styles from './RecommendPane.module.css'

/**
 * 나를 위한 추천 — 빈 코르크 보드 위에 종이와 핀을 건다.
 *
 * <PhotoBackdrop> 은 방과 빈 보드만 그린다(data/recommend.js 의 arrivalScene). 제목 종이,
 * 추천 종이, 핀은 이 컴포넌트가 data/recommendBoard.js 의 좌표에 별도 에셋으로 올린다.
 * 추천 카드의 button이 종이 전체를 감싸므로 글자가 아닌 종이를 눌러도 상세가 열린다.
 *
 * 그러려면 이 층이 사진과 정확히 같은 사각형 위에 서야 한다. <PhotoBackdrop> 은 사진을
 * `object-fit: cover; object-position: center bottom` 으로 깔므로, 여기 `.photoBox` 도 같은
 * 규칙으로 크기를 잡는다 — 뷰포트를 덮는 최소 크기로 늘리고, 가로 가운데·세로 아래에 맞춘다.
 * 그 위의 % 좌표는 사진 좌표와 1:1 이 된다.
 *
 * 추천은 한 회차가 통째로 온다(최대 10개). 카드를 누르면 요약과 기사를 담은 종이 한 장이
 * 보드 위로 올라온다 — 다른 화면으로 가지 않는다. 열 장을 훑는 게 이 화면의 일이라,
 * 하나를 보고 돌아올 때마다 판이 다시 그려지면 안 된다.
 *
 * 로그인이 필요하다. 비로그인(401)이면 카드 없이 로그인 안내만 띄운다.
 * 로그인 후 추천 목록이 비어 있으면 정해진 업데이트 시각만 안내한다.
 */
const RECOMMENDATION_COLUMN_COUNT = 5
const SHEET_ANCHOR_GAP = 14
/*
 * 카드 옆에 딱 붙이지 않고 누른 카드 쪽으로 이만큼 더 당긴다. 좌우 어느 쪽으로 열든 같은
 * 값이라 배치는 대칭으로 남는다 — 1열을 누른 자리와 4열을 누른 자리가 서로 맞바뀐다.
 *
 * 상자 기준으로는 카드를 51px 덮지만, 액자 종이는 가장자리에서 폭의 5.6% 가 투명이라
 * 눈에 보이는 종이가 카드를 타는 것은 그보다 적다.
 */
const SHEET_ANCHOR_PULL = 65
const SHEET_EDGE_GAP = 16
/* 이 폭 아래로는 종이를 카드 옆에 세우지 않는다 — RecommendPane.module.css 의 하단 sheet
   질의와 같은 값이어야 한다. */
const SHEET_BESIDE_MIN_WIDTH = 900
/* 하단 sheet 을 끝까지 밀어 넣었을 때 남는 높이 — 제목 한 줄은 보이게 한다. */
const SHEET_PEEK_MIN_HEIGHT = 132
const SHEET_PEEK_MAX_RATIO = 0.92
/*
 * 사건 제목은 기사에서 뽑은 문장이라 절반이 40자를 넘는다(2026-09-27 Neo4j 실측, 중앙값 42자).
 * 이 길이를 넘으면 상세 종이의 제목을 한 단계 낮춰 부제처럼 읽히게 한다. 잠정값이다.
 */
const LONG_TITLE_LENGTH = 40
const RESIZE_CORNERS = [
  { direction: 'nw', label: '왼쪽 위 모서리에서 종이 크기 조절' },
  { direction: 'ne', label: '오른쪽 위 모서리에서 종이 크기 조절' },
  { direction: 'sw', label: '왼쪽 아래 모서리에서 종이 크기 조절' },
  { direction: 'se', label: '오른쪽 아래 모서리에서 종이 크기 조절' },
]

export function RecommendPane({ settled = true }) {
  const account = useSession()
  // <AppScene> 이 같은 훅으로 같은 그림을 건다. 종이는 그 그림의 코르크 위에 앉는다.
  const boardArt = useNearestWindow(BOARDS)
  const [board, setBoard] = useState(null)
  const [state, setState] = useState('loading')
  const [openId, setOpenId] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchRecommendationBoard({ signal: controller.signal })
      .then((payload) => {
        setBoard(payload)
        setState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setState(error?.status === 401 ? 'signedOut' : 'failed')
      })
    return () => controller.abort()
  }, [])

  const items = board?.items ?? []
  const openIndex = items.findIndex((item) => item.userRecommendationId === openId)
  const open = openIndex >= 0 ? items[openIndex] : null
  // 다섯 열 중 오른쪽 두 열만 상세 종이를 왼쪽에 띄운다. 가운데 열은 사용자가
  // 요청한 대로 왼쪽 카드와 함께 오른쪽에 띄워 중심 Event를 가리지 않는다.
  const detailSide =
    openIndex >= 0 && openIndex % RECOMMENDATION_COLUMN_COUNT > 2 ? 'left' : 'right'

  /**
   * 카드를 펼치는 것이 이 화면의 "추천을 확인했다"이다. 그 순간만 개인 그래프에 클릭으로
   * 남긴다 — `POST /users/me/graph/nodes/EVENT/{eventId}/clicks`. 접는 것은 새 클릭이
   * 아니므로 보내지 않고, 이미 눌러 본 Event 를 다시 눌렀을 때는 서버가 클릭 수를 올린다.
   *
   * 키는 `item.eventId` 다 — 스펙이 말하는 Neo4j Event 의 nodeId 이고, 상세 조회에 쓰는
   * userRecommendationId 가 아니다. 비로그인은 401 이므로 부르지 않는다. 실패해도 화면이
   * 할 일은 없어 조용히 삼킨다.
   */
  const handleCardToggle = (item) => {
    const isOpen = openId === item.userRecommendationId
    setOpenId(isOpen ? null : item.userRecommendationId)
    if (isOpen) return
    if (account && item.eventId) {
      recordNodeClick('EVENT', item.eventId).catch(() => {})
    }
  }

  const handleSheetClose = () => {
    setOpenId(null)
  }

  const notice =
    state !== 'ready'
      ? {
          loading: boardCopy.loading,
          signedOut: account ? boardCopy.failed : boardCopy.signedOut,
          failed: boardCopy.failed,
        }[state]
      : null
  const noticeHint = notice === boardCopy.signedOut ? boardCopy.signedOutHint : null

  return (
    <section
      className={`${styles.stage} ${settled ? styles.stageIn : styles.stageWaiting}`}
      aria-labelledby="recommend-board-title"
    >
      {/* 사진과 같은 사각형 — 사진이 뷰포트를 채우므로 이 층도 뷰포트다. */}
      <div className={styles.photoBox}>
        {/* 종이가 사는 곳은 코르크 면뿐이다. 넘치면 나무틀을 넘지 않고 여기서 스크롤된다. */}
        {/* data-cork-area: 상세 종이가 이 면의 세로를 그대로 쓴다(useDetailSheetAnchor). */}
        <div className={styles.corkArea} data-cork-area style={corkPlacement(boardArt)}>
          {/* 제목 종이도 배경에 굽지 않고 독립 에셋으로 건다. */}
          <header className={styles.banner}>
            <img className={styles.bannerPaper} src={BOARD_ASSETS.title} alt="" aria-hidden />
            <span className={styles.bannerCopy}>
              <span className={styles.bannerMain}>
                <span className={styles.eyebrow}>{boardCopy.eyebrow}</span>
                <h1 id="recommend-board-title">{boardCopy.title}</h1>
              </span>
              <span className={styles.cycle}>{boardCopy.updateSchedule}</span>
            </span>
          </header>

          <ol className={styles.slots} aria-label="추천 Event 열 장">
            {SLOTS.map((slot, index) => {
              const item = items[index]
              return (
                <li key={slot.doodle} className={styles.slot} data-tone={slot.tone}>
                  {item ? (
                    <button
                      type="button"
                      className={styles.card}
                      data-recommendation-index={index}
                      aria-pressed={openId === item.userRecommendationId}
                      aria-label={`${index + 1}위. ${boardCopy.open(item.label)}`}
                      onClick={() => handleCardToggle(item)}
                    >
                      <span className={styles.cardFace}>
                        <img
                          className={styles.cardPaper}
                          src={BOARD_ASSETS.paper}
                          alt=""
                          aria-hidden
                        />
                        <span className={styles.cardCopy}>
                          <span className={styles.cardHead}>
                            <b className={styles.rank}>{String(item.rank).padStart(2, '0')}</b>
                            <span className={styles.topic}>{topicName(item.topicCode)}</span>
                          </span>
                          <strong className={styles.label}>{item.label}</strong>
                          {item.reason && <span className={styles.reason}>{item.reason}</span>}
                        </span>
                      </span>
                      <img
                        className={styles.cardPin}
                        src={PIN_BY_TONE[slot.tone]}
                        alt=""
                        aria-hidden
                      />
                    </button>
                  ) : (
                    <span className={styles.blank} aria-hidden="true" />
                  )}
                </li>
              )
            })}
          </ol>
        </div>
      </div>

      {/* 종이 밖의 것들은 사진 상자가 아니라 뷰포트에 붙인다 — 사진이 뷰포트보다 넓어져
          양옆이 잘릴 때 함께 잘려 나가지 않도록. */}
      {notice && (
        <div className={styles.notice} role="status" style={corkCentre(boardArt)}>
          <p>{notice}</p>
          {noticeHint && <p className={styles.noticeHint}>{noticeHint}</p>}
        </div>
      )}

      {open && (
        <DetailSheet
          key={open.userRecommendationId}
          item={open}
          side={detailSide}
          anchorIndex={openIndex}
          onClose={handleSheetClose}
        />
      )}
    </section>
  )
}

/**
 * 종이 한 장 위의 요약과 기사.
 *
 * userRecommendationId 로 키가 걸려 있어 다른 카드를 열면 새로 마운트된다 — 늦게 도착한
 * 이전 카드의 응답이 이 카드 위에 앉는 일이 없다.
 *
 * `contextSummary` 가 null 인 것은 정상이다. 공개 시각까지 요약이 안 만들어지는 회차가
 * 있어서, 그때는 "준비 중"이라고 말하고 기사만 보여준다.
 */
function DetailSheet({ item, side, anchorIndex, onClose }) {
  const [detail, setDetail] = useState(null)
  const [state, setState] = useState('loading')
  const { cardRef, cardStyle, dragging, resizing, positioned, handleProps, resizeHandleProps } =
    useResizableCard({ minWidth: 260, minHeight: 240 })
  const { peekStyle, peeking, peekHandleProps } = useBottomSheetPeek(cardRef)
  const anchorStyle = useDetailSheetAnchor(cardRef, anchorIndex, side)

  useEffect(() => {
    const controller = new AbortController()
    fetchRecommendationDetail(item.userRecommendationId, { signal: controller.signal })
      .then((payload) => {
        setDetail(payload)
        setState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setState('failed')
      })
    return () => controller.abort()
  }, [item.userRecommendationId])

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    const closeFromOutside = (event) => {
      if (!cardRef.current?.contains(event.target)) onClose()
    }

    document.addEventListener('pointerdown', closeFromOutside, true)
    return () => document.removeEventListener('pointerdown', closeFromOutside, true)
  }, [cardRef, onClose])

  const articles = detail?.articles ?? []

  return (
    <aside
      ref={cardRef}
      className={styles.sheet}
      style={{ ...anchorStyle, ...cardStyle, ...peekStyle }}
      data-dragging={dragging}
      data-resizing={resizing}
      data-peeking={peeking}
      data-positioned={positioned}
      data-side={side}
      aria-labelledby="recommend-sheet-title"
    >
      {/* 하단 sheet 에서만 보인다. 가로모드에서는 아래 네 모서리가 그 일을 한다. */}
      <button
        type="button"
        className={styles.peek}
        aria-label={boardCopy.peek}
        title={`${boardCopy.peek} — 방향키로도 조절할 수 있습니다`}
        {...peekHandleProps}
      />

      <button
        type="button"
        className={styles.sheetClose}
        aria-label={boardCopy.close}
        onClick={onClose}
      >
        ×
      </button>

      <header className={styles.sheetHead} {...handleProps}>
        <span className={styles.sheetKind}>
          {String(item.rank).padStart(2, '0')} · {topicName(item.topicCode)}
        </span>
        <h2
          id="recommend-sheet-title"
          data-long={(item.label?.length ?? 0) > LONG_TITLE_LENGTH || undefined}
        >
          {item.label}
        </h2>
      </header>
      {item.reason && (
        <p className={styles.sheetReason}>
          <b>{boardCopy.reasonLabel}</b> {item.reason}
        </p>
      )}

      {state === 'loading' && <p className={styles.sheetNote}>{boardCopy.loading}</p>}
      {state === 'failed' && <p className={styles.sheetNote}>{boardCopy.detailFailed}</p>}

      {state === 'ready' && (
        <>
          {detail?.contextSummary ? (
            <p className={styles.summary}>{detail.contextSummary}</p>
          ) : (
            <p className={styles.sheetNote}>{boardCopy.summaryPending}</p>
          )}

          <section className={styles.articles}>
            <h3>
              {boardCopy.articles}
              <b>{articles.length}</b>
            </h3>
            {articles.length > 0 ? (
              <ul>
                {articles.map((article) => (
                  <li key={article.articleId}>
                    <small>
                      {article.organizationName} · {formatDate(article.publishedAt)}
                    </small>
                    <p>{article.title}</p>
                    {article.originalUrl && (
                      <a href={article.originalUrl} target="_blank" rel="noreferrer">
                        {boardCopy.origin} ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.sheetNote}>{boardCopy.articlesEmpty}</p>
            )}
          </section>
        </>
      )}

      {RESIZE_CORNERS.map(({ direction, label }) => (
        <button
          key={direction}
          type="button"
          className={`${styles.resizeHandle} ${styles[`resize${direction.toUpperCase()}`]}`}
          aria-label={label}
          title={`${label} — 방향키로도 조절할 수 있습니다`}
          {...resizeHandleProps(direction)}
        />
      ))}
    </aside>
  )
}

/**
 * 상세 종이를 화면 모서리가 아니라 선택한 추천 종이에 붙인다.
 *
 * 오른쪽으로 열 때는 선택 종이의 오른쪽 변, 왼쪽으로 열 때는 왼쪽 변에서 시작한다. 가로만
 * 그렇다 — 세로 자리와 높이는 코르크 면에서 가져와 어느 카드를 눌러도 같다. 카드마다 높이가
 * 달라지면 열 장을 훑는 동안 종이가 위아래로 튀고, 내용 길이가 종이 크기를 정하게 된다.
 *
 * 보드가 줄거나 늘면 함께 따라가야 하므로 카드·종이와 함께 코르크도 다시 관찰한다.
 * 모바일은 별도 하단 sheet 레이아웃이 있으므로 위치를 덮어쓰지 않는다.
 */
function useDetailSheetAnchor(cardRef, anchorIndex, side) {
  const [anchorStyle, setAnchorStyle] = useState(null)

  useLayoutEffect(() => {
    const sheet = cardRef.current
    const anchorElement = document.querySelector(`[data-recommendation-index="${anchorIndex}"]`)
    const corkElement = document.querySelector('[data-cork-area]')
    if (!sheet || !anchorElement) return undefined

    const placeBesideCard = () => {
      if (window.innerWidth <= SHEET_BESIDE_MIN_WIDTH) {
        setAnchorStyle(null)
        return
      }

      const anchorRect = anchorElement.getBoundingClientRect()
      const corkRect = corkElement?.getBoundingClientRect()
      const sheetRect = sheet.getBoundingClientRect()
      const boundaryElement = sheet.offsetParent
      const boundaryRect = boundaryElement?.getBoundingClientRect() ?? {
        left: 0,
        top: 0,
        right: window.innerWidth,
        bottom: window.innerHeight,
      }
      // 데스크톱 rail 너비의 token 식과 같다. 카드 옆에 붙이더라도 내비게이션 위로
      // 침범하지 않게 실제 viewport 너비로 계산한다.
      const navigationInset =
        window.innerWidth >= 1024 ? Math.min(208, Math.max(176, window.innerWidth * 0.135)) : 0
      const minLeft = Math.max(boundaryRect.left, navigationInset) + SHEET_EDGE_GAP
      const maxRight = Math.min(boundaryRect.right, window.innerWidth) - SHEET_EDGE_GAP
      const minTop = Math.max(boundaryRect.top, 0) + SHEET_EDGE_GAP
      const maxBottom = Math.min(boundaryRect.bottom, window.innerHeight) - SHEET_EDGE_GAP
      const desiredLeft =
        side === 'left'
          ? anchorRect.left - sheetRect.width - SHEET_ANCHOR_GAP + SHEET_ANCHOR_PULL
          : anchorRect.right + SHEET_ANCHOR_GAP - SHEET_ANCHOR_PULL
      const maxLeft = Math.max(minLeft, maxRight - sheetRect.width)
      // 세로는 누른 카드가 아니라 보드가 정한다 — 같은 행, 같은 높이.
      const height = Math.min(corkRect?.height ?? sheetRect.height, maxBottom - minTop)
      const desiredTop = corkRect ? corkRect.top : anchorRect.top - SHEET_EDGE_GAP
      const maxTop = Math.max(minTop, maxBottom - height)
      // 브라우저가 키보드 포커스나 자동 scroll-into-view 때문에 overflow 컨테이너를
      // 내부 스크롤한 경우에도 viewport에서 보이는 카드 옆에 그대로 붙인다.
      const left =
        clamp(desiredLeft, minLeft, maxLeft) -
        boundaryRect.left +
        (boundaryElement?.scrollLeft ?? 0)
      const top =
        clamp(desiredTop, minTop, maxTop) - boundaryRect.top + (boundaryElement?.scrollTop ?? 0)
      // 높이만 넘기면 폭(aspect-ratio)과 안쪽 여백이 CSS 에서 따라온다.
      const nextStyle = { top, '--sheet-h': `${height}px`, right: 'auto', bottom: 'auto', left }

      setAnchorStyle((current) =>
        current?.top === nextStyle.top &&
        current?.left === nextStyle.left &&
        current?.['--sheet-h'] === nextStyle['--sheet-h']
          ? current
          : nextStyle,
      )
    }

    placeBesideCard()
    window.addEventListener('resize', placeBesideCard)
    const resizeObserver =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(placeBesideCard)
    resizeObserver?.observe(anchorElement)
    resizeObserver?.observe(sheet)
    if (corkElement) resizeObserver?.observe(corkElement)

    return () => {
      window.removeEventListener('resize', placeBesideCard)
      resizeObserver?.disconnect()
    }
  }, [anchorIndex, cardRef, side])

  return anchorStyle
}

/**
 * 하단 sheet 을 위아래로 여닫는다 — 높이만 바꾸고 좌우와 아래 변은 화면에 붙여 둔다.
 *
 * 가로모드의 모서리 조절(useResizableCard)은 이 sheet 에 걸리지 않는다. 그 훅은 offsetParent
 * 를 기준점으로 삼는데 `position: fixed` 인 요소에는 그것이 없어 조작이 시작되지 않는다.
 * 여기서 필요한 것도 네 방향이 아니라 높이 하나뿐이라 따로 둔다.
 *
 * 폭이 바뀌면 손으로 잡은 높이를 버리고 CSS 배치로 돌아간다 — 가로모드로 넘어갔을 때
 * 하단 sheet 시절의 높이가 종이에 남지 않도록.
 */
function useBottomSheetPeek(cardRef) {
  const [height, setHeight] = useState(null)
  const [peeking, setPeeking] = useState(false)
  const dragRef = useRef(null)

  useEffect(() => {
    const reset = () => {
      dragRef.current = null
      setPeeking(false)
      setHeight(null)
    }

    window.addEventListener('resize', reset)
    return () => window.removeEventListener('resize', reset)
  }, [])

  const limit = (value) =>
    clamp(value, SHEET_PEEK_MIN_HEIGHT, Math.round(window.innerHeight * SHEET_PEEK_MAX_RATIO))

  const begin = (event) => {
    const sheet = cardRef.current
    if (event.button !== 0 || !sheet) return

    dragRef.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startHeight: sheet.getBoundingClientRect().height,
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
    event.preventDefault()
    setPeeking(true)
  }

  const move = (event) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    // 위로 끌수록(음수 delta) 종이가 나온다.
    setHeight(limit(drag.startHeight - (event.clientY - drag.startY)))
  }

  const end = (event) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return

    event.currentTarget.releasePointerCapture?.(event.pointerId)
    dragRef.current = null
    setPeeking(false)
  }

  const nudge = (event) => {
    const sheet = cardRef.current
    if (!sheet || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return

    const step = event.shiftKey ? 48 : 16
    const current = sheet.getBoundingClientRect().height
    setHeight(limit(current + (event.key === 'ArrowUp' ? step : -step)))
    event.preventDefault()
  }

  return {
    peeking,
    // max-height 를 풀지 않으면 72vh 에서 더 끌어올려지지 않는다.
    peekStyle: height === null ? undefined : { height: `${height}px`, maxHeight: 'none' },
    peekHandleProps: {
      onPointerDown: begin,
      onPointerMove: move,
      onPointerUp: end,
      onPointerCancel: end,
      onKeyDown: nudge,
    },
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

/** ISO 든 `2026.09.10 08:55` 든, 월·일만 뽑는다. */
function formatDate(value) {
  const match = /^(\d{4})[-.](\d{2})[-.](\d{2})/.exec(value ?? '')
  if (!match) return value ?? ''
  return `${Number(match[2])}월 ${Number(match[3])}일`
}
