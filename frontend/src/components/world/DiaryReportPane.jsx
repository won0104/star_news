import { Link } from 'react-router-dom'
import { report } from '../../data/world'
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
 * Left page is what was read — who I am, the totals, the split by field and by source.
 * Right page is how it moved — twelve weeks of it, then where the topics landed.
 */
export function DiaryReportPane() {
  const { totals, fields, sources, weeks, terrain } = report
  const topFieldCount = Math.max(...fields.rows.map((row) => row.count))

  return (
    <section className={styles.page} aria-label={report.title}>
      <DiaryShell
        frameSrc="/assets/history/diary-report-frame.png"
        stageClassName={styles.diaryStage}
        frameClassName={styles.diaryFrame}
      >

        {/* Each screen's outer bookmark points at the other one, so the two read as one book. */}
        <Link className={styles.historyBookmark} to="/app?view=log">
          <img src={`${BOOKMARK_ASSET}/bookmark-report-blank.svg`} alt="" aria-hidden="true" />
          <span>나의 기록</span>
        </Link>

        {/* ─────────────── 왼쪽 페이지 ─────────────── */}
        <div className={styles.leftPage}>
          <header className={styles.pageHead}>
            <span>MY READING CHART</span>
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
            <h2>{fields.label}</h2>
            <p className={styles.hint}>{fields.hint}</p>

            <div className={styles.bars}>
              {fields.rows.map((row) => (
                <div className={styles.barRow} key={row.id}>
                  <span className={styles.barLabel}>{row.label}</span>
                  <span className={styles.barTrack}>
                    <span
                      className={styles.barFill}
                      style={{ width: `${(row.count / topFieldCount) * 100}%` }}
                    />
                  </span>
                  <span className={styles.barValue}>{row.count}</span>
                </div>
              ))}
            </div>
          </section>

          <section className={styles.block}>
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
        </div>

        {/* ─────────────── 오른쪽 페이지 ─────────────── */}
        <div className={styles.rightPage}>
          <section className={styles.block}>
            <div className={styles.blockHead}>
              <div>
                <h2>{weeks.label}</h2>
                <p className={styles.hint}>{weeks.hint}</p>
              </div>
              <ul className={styles.seriesLegend}>
                {weeks.series.map((entry, index) => (
                  <li key={entry.id}>
                    <span className={`${styles.swatch} ${styles[`tone${index}`]}`} aria-hidden />
                    {entry.label}
                  </li>
                ))}
              </ul>
            </div>

            <div className={styles.plot}>
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

              {terrain.topics.map((topic) => (
                <span
                  key={topic.id}
                  className={`${styles.topic} ${topic.strong ? styles.topicStrong : ''}`}
                  style={{ left: `${topic.x}%`, top: `${topic.y}%` }}
                >
                  <span className={styles.topicDot} aria-hidden />
                  {topic.label}
                </span>
              ))}
            </div>

            <p className={styles.axisNote}>
              {terrain.axisX}
              <br />
              {terrain.axisY}
            </p>
          </section>
        </div>
      </DiaryShell>
    </section>
  )
}
