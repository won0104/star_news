import { Link } from 'react-router-dom'
import { Fragment, useEffect, useRef, useState } from 'react'
import { fetchNewsReport } from '../../api/report'
import { reportFromApi } from '../../adapters/newsReport'
import { reportCopy, reportTabs } from '../../data/world'
import { useSession } from '../../store/session'
import { SavedPane } from './SavedPane'
import { DiaryShell } from './DiaryShell'
import styles from './DiaryReportPane.module.css'

const BOOKMARK_ASSET = '/assets/history/bookmarks'
/* 기타 조각에 머물러야 하는 시간. 훑는 동안 말풍선이 연달아 뜨지 않을 만큼만 길다. */
const HOVER_OPEN_MS = 400

/**
 * 나의 리포트 — the same four charts as <ReportPane>, laid across one diary spread.
 *
 * The book this opens in has no cut-out window, unlike 나의 기록's observatory frame, so
 * nothing here sits inside a lit portal: every chart is drawn as ink on the page, and the
 * palette flips from that screen's night sky to paper. The bookmark asset README's own
 * colours (ink #44392F, navy #182B43, gold #EEC376, cream #EBE2D2–#F8F3E9) are what the
 * stylesheet is built from, so the charts and the book's own trim agree.
 *
 * Both pages are flat and equal, which is why the whole report fits at once and there is
 * no page turn: a report is scanned as a whole, and paging away half of it would hide the
 * comparison it exists to make. 나의 기록 pages because it is a list that keeps going.
 *
 * Left page is how much and how it moved — one summary sentence, then twelve weeks of composition.
 * Right page is where it came from and where the topics landed.
 *
 * The split by field is gone: it was the twelve-week chart's own totals drawn again, so
 * the page spent a block saying what the block beside it already said.
 *
 * 차트는 전부 `GET /users/me/statistics/news-report` 의 집계다. 표본으로 대체하지 않는다 —
 * 리포트는 "내가 무엇을 읽었나"에 답하는 화면이라, 남의 숫자를 채워 넣으면 화면이 하는 말이
 * 거짓이 된다. 불러오지 못했으면 차트 자리에 그 사실을 적는다.
 */
export function DiaryReportPane() {
  const account = useSession()
  const [report, setReport] = useState(null)
  const [state, setState] = useState('loading')
  // 오른쪽 가장자리 책갈피가 고르는 페이지. 나의 기록의 카테고리 책갈피와 같은 조작이다.
  const [tab, setTab] = useState('report')

  useEffect(() => {
    const controller = new AbortController()
    fetchNewsReport({ signal: controller.signal })
      .then((payload) => {
        setReport(reportFromApi(payload))
        setState('ready')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') return
        setState(error?.status === 401 ? 'signedOut' : 'failed')
      })
    return () => controller.abort()
  }, [])

  // 401 이어도 세션에 계정이 남아 있으면 처음부터 비로그인인 게 아니라 끊긴 것이다.
  const notice = {
    loading: reportCopy.loading,
    signedOut: account ? reportCopy.expired : reportCopy.signedOut,
    failed: reportCopy.failed,
  }[state]
  const offerSignIn = state === 'signedOut'
  // 차트는 ready 일 때만 그리므로 이 넷은 그 안에서 항상 채워져 있다.
  const { sources, weeks, terrain } = report ?? {}

  return (
    <section className={styles.page} aria-label={reportCopy.title}>
      <DiaryShell
        stageClassName={styles.diaryStage}
        frameClassName={styles.diaryFrame}
      >
        {/* Each screen's outer bookmark points at the other one, so the two read as one book. */}
        <div className={styles.historySlot}>
          <Link className={styles.historyBookmark} to="/app?view=log">
            <img src={`${BOOKMARK_ASSET}/report-v2.webp`} alt="" aria-hidden="true" />
            <span>나의 기록</span>
          </Link>
        </div>

        {/* 오른쪽 가장자리 — 이 책 안의 페이지들. 나의 기록이 카테고리로 쓰는 것과 같은 에셋. */}
        <nav className={styles.pageBookmarks} aria-label="리포트 페이지">
          {reportTabs.map((item) => {
            const selected = item.id === tab

            return (
              <button
                type="button"
                key={item.id}
                aria-current={selected ? 'true' : undefined}
                onClick={() => setTab(item.id)}
              >
                <img
                  src={`${BOOKMARK_ASSET}/right-${selected ? 'active' : 'idle'}-v2.webp`}
                  alt=""
                  aria-hidden="true"
                />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        {/* 책의 종이 — 세로 화면에서 여기만 스크롤된다. 책갈피는 이 밖에 있어 책
            가장자리에 그대로 남는다. 가로에서는 자리를 차지하지 않는 투명한 층이다. */}
        <div className={styles.pageScroll}>
          {tab !== 'report' && <SavedPane kind={tab} />}

          {/* 집계를 못 얻었으면 차트 자리에 그 사실만 적는다. 표본으로 채우지 않는다. */}
          {tab === 'report' && state !== 'ready' && (
            <div className={styles.notice} role="status">
              <p>{notice}</p>
              {offerSignIn && (
                <Link className={styles.noticeAction} to="/login">
                  {reportCopy.signIn}
                </Link>
              )}
            </div>
          )}

          {tab === 'report' && state === 'ready' && (
            <>
              {/* ─────────────── 왼쪽 페이지 ─────────────── */}
              <div className={styles.leftPage}>
                <header className={styles.pageHead}>
                  <span>{report.eyebrow}</span>
                  <h1>{report.title}</h1>
                  <p>
                    <Parts parts={report.summary} />
                  </p>
                </header>

                <section className={styles.block}>
                  <div className={styles.blockHead}>
                    <div>
                      <h2>{weeks.label}</h2>
                      <p className={styles.hint}>{weeks.hint}</p>
                    </div>
                    {/* 기타에 무엇이 들었는지는 조각에 마우스를 올려 본다 — <OtherHotspot>. */}
                    <ul className={styles.seriesLegend}>
                      {weeks.series.map((entry, index) => (
                        <li key={entry.id}>
                          <span
                            className={`${styles.swatch} ${styles[`tone${index}`]}`}
                            aria-hidden
                          />
                          {entry.label}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className={styles.plot}>
                    {weeks.empty && <p className={styles.plotEmpty}>{weeks.empty}</p>}

                    {weeks.ticks.map((tick) => (
                      <div
                        className={styles.tick}
                        key={tick}
                        style={{ bottom: `${(tick / weeks.axisMax) * 100}%` }}
                      >
                        <span className={styles.tickLabel}>{tick}</span>
                      </div>
                    ))}

                    <div className={styles.columns}>
                      {weeks.columns.map((column, weekIndex) => {
                        const otherIndex = weeks.series.findIndex((entry) => entry.id === 'OTHER')
                        const otherValue = otherIndex >= 0 ? column.values[otherIndex] : 0

                        return (
                          <div className={styles.column} key={weekIndex}>
                            <div className={styles.stack}>
                              {/* Reversed so the first series ends up at the base of the column. */}
                              {[...column.values].reverse().map((value, reversedIndex) => {
                                const seriesIndex = column.values.length - 1 - reversedIndex
                                return (
                                  <span
                                    key={weeks.series[seriesIndex].id}
                                    className={`${styles.segment} ${styles[`tone${seriesIndex}`]}`}
                                    style={{ height: `${(value / weeks.axisMax) * 100}%` }}
                                  />
                                )
                              })}

                              {otherValue > 0 && column.otherParts.length > 0 && (
                                <OtherHotspot
                                  column={column}
                                  value={otherValue}
                                  below={
                                    column.values.reduce((sum, one) => sum + one, 0) - otherValue
                                  }
                                  axisMax={weeks.axisMax}
                                />
                              )}
                            </div>
                            <span className={styles.monthLabel}>{column.month ?? ''}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* 차트를 줄인 자리에 숫자가 말하는 것을 한두 줄로 적는다. */}
                  {weeks.insights.length > 0 && (
                    <ul className={styles.insights}>
                      {weeks.insights.map((line) => (
                        <li key={line.map((part) => part.text).join('')}>
                          <Parts parts={line} />
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>

              {/* ─────────────── 오른쪽 페이지 ─────────────── */}
              <div className={styles.rightPage}>
                <section className={`${styles.block} ${styles.blockTight}`}>
                  <h2>{sources.label}</h2>

                  <div className={styles.shareBar}>
                    {sources.rows.map((row, index) => (
                      <span
                        key={row.id}
                        className={`${styles.shareSegment} ${styles[`tone${index}`]}`}
                        style={{ width: `${row.share}%` }}
                      />
                    ))}
                  </div>

                  <ul className={styles.shareLegend}>
                    {sources.rows.map((row, index) => (
                      <li key={row.id}>
                        <span className={`${styles.swatch} ${styles[`tone${index}`]}`} aria-hidden />
                        {row.label}
                        <b>{row.share}%</b>
                      </li>
                    ))}
                  </ul>

                  <p className={styles.footnote}>{sources.footnote}</p>
                </section>
                <section className={styles.block}>
                  <h2>{terrain.label}</h2>
                  <p className={styles.hint}>{terrain.hint}</p>

                  <div className={styles.terrain}>
                    <span className={styles.quadrantFill} aria-hidden />
                    <span className={`${styles.quadrantLabel} ${styles.qTopLeft}`}>
                      {terrain.quadrants.topLeft}
                    </span>
                    <span className={`${styles.quadrantLabel} ${styles.qTopRight}`}>
                      <span aria-hidden>✦ </span>
                      {terrain.quadrants.topRight}
                    </span>
                    <span className={`${styles.quadrantLabel} ${styles.qBottomLeft}`}>
                      {terrain.quadrants.bottomLeft}
                    </span>
                    <span className={`${styles.quadrantLabel} ${styles.qBottomRight}`}>
                      {terrain.quadrants.bottomRight}
                    </span>

                    {terrain.clusters.map((cluster) => (
                      <TerrainPoint key={cluster.id} cluster={cluster} />
                    ))}
                  </div>

                  <ul className={styles.axisNote}>
                    <li>{terrain.axisX}</li>
                    <li>{terrain.axisY}</li>
                  </ul>
                </section>
              </div>
            </>
          )}
        </div>
      </DiaryShell>
    </section>
  )
}

/** 문장 조각을 잇는다. `strong` 조각(데이터에서 나온 숫자)만 굵게. */
function Parts({ parts }) {
  return parts.map((part, index) =>
    part.strong ? <b key={index}>{part.text}</b> : <Fragment key={index}>{part.text}</Fragment>,
  )
}

/**
 * 12주 기둥에서 `기타` 조각을 가리키는 판정 영역.
 *
 * 조각 자체가 아니라 그 위에 투명한 층을 덮는다. 기타는 정의상 접히고 남은 작은 값들이라
 * 어떤 주에는 높이가 1~2px 이고, 그 높이를 그대로 표적으로 쓰면 스쳐 지나갈 뿐 멈춰 있을
 * 수가 없다. 그래서 조각을 덮되 최소 높이를 보장하고, 기둥 폭 전체를 쓴다.
 *
 * 머문 뒤에만 연다. 12주를 훑느라 가로지르는 동안 말풍선이 연달아 튀면 차트를 못 읽는다.
 * 다만 `몇 초`는 길어서 대부분 포기하고 지나가므로, 우연과 의도가 갈리는 선인 0.4초로 둔다.
 *
 * 마우스만의 길이다 — 터치와 키보드는 범례의 `기타`를 눌러 12주 합계를 본다.
 */
function OtherHotspot({ column, value, below, axisMax }) {
  const [open, setOpen] = useState(false)
  const timer = useRef(null)

  const clear = () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
  }

  // 언마운트될 때 남은 타이머가 사라진 컴포넌트를 열려고 하지 않게 한다.
  useEffect(() => clear, [])

  return (
    <span
      className={styles.otherHotspot}
      /* 기타는 기둥 맨 위에 쌓이므로, 아래 조각들의 합만큼 띄운 자리에서 시작한다.
         바닥을 고정해 두면 최소 높이가 위쪽 빈 곳으로만 자라 다른 조각을 가리지 않는다. */
      style={{
        bottom: `${(below / axisMax) * 100}%`,
        height: `${(value / axisMax) * 100}%`,
      }}
      onMouseEnter={() => {
        clear()
        timer.current = setTimeout(() => setOpen(true), HOVER_OPEN_MS)
      }}
      onMouseLeave={() => {
        clear()
        setOpen(false)
      }}
    >
      {open && (
        <span className={styles.otherTip} role="status">
          <b>기타 {value}</b>
          {column.otherParts.map((part) => (
            <span key={part.id}>
              {part.label} {part.count}
            </span>
          ))}
        </span>
      )}
    </span>
  )
}

/**
 * 지형 위의 점 하나. 같은 자리에 선 것이 여럿이면 하나로 묶고 `+N` 을 단다.
 *
 * 흩뜨리지 않는 이유는 어댑터의 terrainClusters 주석에 적어 뒀다 — 겹침이 오차가 아니라
 * 같은 값이어서다. 옮기면 없는 차이를 만든다.
 *
 * 묶인 점만 버튼이다. 혼자 선 점은 이름이 이미 옆에 있어 누를 일이 없고, 지형 열두 자리가
 * 전부 누를 수 있는 것처럼 보이면 눌러 볼 것이 없는 점까지 눌러 보게 된다.
 */
/* 이름을 안쪽으로 붙이기 시작하는 가로 위치(%). 잠정값이다. */
const EDGE_LEFT = 30
const EDGE_RIGHT = 70

function TerrainPoint({ cluster }) {
  const [open, setOpen] = useState(false)
  const [first, ...rest] = cluster.members

  const position = { left: `${cluster.x}%`, top: `${cluster.y}%` }
  /*
   * 가장자리 가까운 점은 이름을 안쪽으로 붙인다. 가운데 맞춤 그대로 두면 긴 이름이 판과 쪽
   * 밖으로 나갔다("아이치 인터내셔널 아레나에서"). 점은 어느 경우든 좌표 위에 남는다.
   */
  const edge = cluster.x > EDGE_RIGHT ? styles.topicAtRight : cluster.x < EDGE_LEFT ? styles.topicAtLeft : ''
  const className = `${styles.topic} ${cluster.strong ? styles.topicStrong : ''} ${edge}`

  if (rest.length === 0) {
    return (
      <span className={className} style={position}>
        <span className={styles.topicDot} aria-hidden />
        {first.label}
      </span>
    )
  }

  return (
    <span className={className} style={position}>
      <span className={styles.topicDot} aria-hidden />
      <button
        type="button"
        className={styles.clusterToggle}
        aria-expanded={open}
        onClick={() => setOpen((was) => !was)}
      >
        {first.label}
        <b className={styles.clusterCount}>+{rest.length}</b>
      </button>

      {/* 목록은 라벨 아래로 펼친다. 같은 자리의 이름들이라 점에서 멀어지면 어느 점의
          것인지 알 수 없다. */}
      {open && (
        <span className={styles.clusterList}>
          {rest.map((member) => (
            <span key={member.id}>{member.label}</span>
          ))}
        </span>
      )}
    </span>
  )
}
