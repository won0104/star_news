import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { fetchNewsReport } from '../../api/report'
import { reportFromApi } from '../../adapters/newsReport'
import { reportCopy, reportTabs } from '../../data/world'
import { useSession } from '../../store/session'
import { SavedPane } from './SavedPane'
import { DiaryShell } from './DiaryShell'
import styles from './DiaryReportPane.module.css'

const BOOKMARK_ASSET = '/assets/history/bookmarks'

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
 * Left page is how much and how it moved — the totals, then twelve weeks of composition.
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
  const { totals, sources, weeks, terrain } = report ?? {}

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
                  <p>{report.summary}</p>
                </header>

                <dl className={styles.totals}>
                  {totals.map((total) => (
                    <div key={total.id}>
                      <dd>{total.value}</dd>
                      <dt>{total.label}</dt>
                    </div>
                  ))}
                </dl>

                <section className={styles.block}>
                  <div className={styles.blockHead}>
                    <div>
                      <h2>{weeks.label}</h2>
                      <p className={styles.hint}>{weeks.hint}</p>
                    </div>
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
                      {weeks.columns.map((column, weekIndex) => (
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
                          </div>
                          <span className={styles.monthLabel}>{column.month ?? ''}</span>
                        </div>
                      ))}
                    </div>
                  </div>
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

                  <p className={styles.axisNote}>
                    {terrain.axisX}
                    <br />
                    {terrain.axisY}
                  </p>
                </section>
              </div>
            </>
          )}
        </div>
      </DiaryShell>
    </section>
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
function TerrainPoint({ cluster }) {
  const [open, setOpen] = useState(false)
  const [first, ...rest] = cluster.members

  const position = { left: `${cluster.x}%`, top: `${cluster.y}%` }
  const className = `${styles.topic} ${cluster.strong ? styles.topicStrong : ''}`

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
