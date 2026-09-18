import { useEffect, useState } from 'react'
import { fetchRecommendationBoard, fetchRecommendationDetail } from '../../api/recommendations'
import {
  BOARD_ASSETS,
  BANNER_FRAME,
  BOARD_FRAME,
  BOARD_SIZE,
  SLOTS,
  boardCopy,
  placement,
  sampleBoard,
  sampleDetail,
} from '../../data/recommendBoard'
import { topicName } from '../../data/topics'
import { useDraggableCard } from '../../hooks/useDraggableCard'
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
 * 로그인이 필요하다. 비로그인(401)·회차 없음·실패는 오류가 아니라 상태다 — 종이를
 * 비워두면 사진만 남아 화면이 뭘 하는 곳인지 알 수 없으니, 표본 카드를 걸고 표본임을
 * 밝힌다. SAMPLE_WHEN_EMPTY 를 끄면 그 자리에 상태 문구만 선다.
 */
const SAMPLE_WHEN_EMPTY = true

export function RecommendPane({ settled = true }) {
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

  const live = board?.items ?? []
  const sample = SAMPLE_WHEN_EMPTY && state !== 'loading' && live.length === 0
  const source = sample ? sampleBoard : board
  const items = source?.items ?? []
  const open = items.find((item) => item.userRecommendationId === openId) ?? null

  // 상태 문구는 표본을 걸지 않을 때만 종이 자리를 대신한다.
  const notice = !sample && state !== 'ready'
    ? { loading: boardCopy.loading, signedOut: boardCopy.signedOut, failed: boardCopy.failed }[state]
    : !sample && items.length === 0
      ? boardCopy.empty
      : null
  const noticeHint = notice === boardCopy.signedOut
    ? boardCopy.signedOutHint
    : notice === boardCopy.empty
      ? boardCopy.emptyHint
      : null

  return (
    <section
      className={`${styles.stage} ${settled ? styles.stageIn : styles.stageWaiting}`}
      aria-labelledby="recommend-board-title"
    >
      {/* <PhotoBackdrop> 의 .photoFramed 와 같은 변수 넷으로 같은 사각형을 만든다. */}
      <div
        className={styles.photoBox}
        style={{
          '--photo-w': BOARD_SIZE.width,
          '--photo-h': BOARD_SIZE.height,
          '--photo-focus-x': BOARD_FRAME.focusX ?? 0.5,
          '--photo-focus-y': BOARD_FRAME.focusY ?? 0.5,
          '--photo-zoom': BOARD_FRAME.zoom ?? 1,
        }}
      >
        {/* 제목 종이도 배경에 굽지 않고 독립 에셋으로 건다. */}
        <header className={styles.banner} style={placement(BANNER_FRAME)}>
          <img className={styles.bannerPaper} src={BOARD_ASSETS.title} alt="" aria-hidden />
          <span className={styles.bannerCopy}>
            <span className={styles.eyebrow}>{boardCopy.eyebrow}</span>
            <h1 id="recommend-board-title">{boardCopy.title}</h1>
            <span className={styles.cycle}>{cycleLine(source, sample)}</span>
          </span>
        </header>

        <ol className={styles.slots} aria-label="추천 Event 열 장">
          {SLOTS.map((slot, index) => {
            const item = items[index]
            return (
              <li
                key={slot.doodle}
                className={styles.slot}
                data-tone={slot.tone}
                style={placement(slot.frame)}
              >
                {item ? (
                  <button
                    type="button"
                    className={styles.card}
                    aria-pressed={openId === item.userRecommendationId}
                    aria-label={`${index + 1}위. ${boardCopy.open(item.label)}`}
                    onClick={() =>
                      setOpenId(openId === item.userRecommendationId ? null : item.userRecommendationId)
                    }
                  >
                    <img className={styles.cardPaper} src={BOARD_ASSETS.paper} alt="" aria-hidden />
                    <img className={styles.cardPin} src={BOARD_ASSETS.pin} alt="" aria-hidden />
                    <span className={styles.cardCopy}>
                      <span className={styles.cardHead}>
                        <b className={styles.rank}>{String(item.rank).padStart(2, '0')}</b>
                        <span className={styles.topic}>{topicName(item.topicCode)}</span>
                      </span>
                      <strong className={styles.label}>{item.label}</strong>
                      {item.reason && <span className={styles.reason}>{item.reason}</span>}
                    </span>
                  </button>
                ) : (
                  <span className={styles.blank} aria-hidden="true" />
                )}
              </li>
            )
          })}
        </ol>
      </div>

      {/* 종이 밖의 것들은 사진 상자가 아니라 뷰포트에 붙인다 — 사진이 뷰포트보다 넓어져
          양옆이 잘릴 때 함께 잘려 나가지 않도록. */}
      {notice && (
        <div className={styles.notice} role="status">
          <p>{notice}</p>
          {noticeHint && <p className={styles.noticeHint}>{noticeHint}</p>}
        </div>
      )}

      {sample && <p className={styles.sampleNote}>{boardCopy.sampleNote}</p>}

      {open && (
        <DetailSheet
          key={open.userRecommendationId}
          item={open}
          sample={sample}
          onClose={() => setOpenId(null)}
        />
      )}
    </section>
  )
}

/**
 * 종이 한 장 위의 요약과 기사.
 *
 * userRecommendationId 로 키가 걸려 있어 다른 카드를 열면 새로 마운트된다 — 늦게 도착한
 * 이전 카드의 응답이 이 카드 위에 앉는 일이 없다. 표본 모드에서는 요청을 보내지 않는다.
 *
 * `contextSummary` 가 null 인 것은 정상이다. 공개 시각까지 요약이 안 만들어지는 회차가
 * 있어서, 그때는 "준비 중"이라고 말하고 기사만 보여준다.
 */
function DetailSheet({ item, sample, onClose }) {
  const [detail, setDetail] = useState(sample ? sampleDetail(item) : null)
  const [state, setState] = useState(sample ? 'ready' : 'loading')
  const { cardRef, cardStyle, dragging, handleProps } = useDraggableCard()

  useEffect(() => {
    if (sample) return undefined
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
  }, [item.userRecommendationId, sample])

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const articles = detail?.articles ?? []

  return (
    <aside
      ref={cardRef}
      className={styles.sheet}
      style={cardStyle}
      data-dragging={dragging}
      aria-labelledby="recommend-sheet-title"
    >
      <button type="button" className={styles.sheetClose} aria-label={boardCopy.close} onClick={onClose}>
        ×
      </button>

      <header className={styles.sheetHead} {...handleProps}>
        <span className={styles.sheetKind}>
          {String(item.rank).padStart(2, '0')} · {topicName(item.topicCode)}
        </span>
        <h2 id="recommend-sheet-title">{item.label}</h2>
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
    </aside>
  )
}

/** "아침 추천 · 06:00 공개". 표본이면 시각을 말하지 않는다 — 없는 회차의 시각은 거짓이다. */
function cycleLine(source, sample) {
  if (!source?.cycle) return ''
  const cycle = boardCopy.cycle[source.cycle] ?? source.cycle
  if (sample) return cycle
  const time = formatTime(source.availableAt)
  return time ? `${cycle} · ${boardCopy.availableAt(time)}` : cycle
}

/** `2026-09-17T06:00:00+09:00` → `06:00`. 서버 오프셋을 그대로 읽는다. */
function formatTime(value) {
  const match = /T(\d{2}):(\d{2})/.exec(value ?? '')
  return match ? `${match[1]}:${match[2]}` : ''
}

/** ISO 든 `2026.09.10 08:55` 든, 월·일만 뽑는다. */
function formatDate(value) {
  const match = /^(\d{4})[-.](\d{2})[-.](\d{2})/.exec(value ?? '')
  if (!match) return value ?? ''
  return `${Number(match[2])}월 ${Number(match[3])}일`
}
