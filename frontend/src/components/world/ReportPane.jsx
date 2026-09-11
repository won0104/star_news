import { report } from '../../data/world';
import styles from './ReportPane.module.css';

/**
 * 나의 리포트 — Figma V3 / My World / 02 / 나의 리포트.
 *
 * Four charts, all of them static, all drawn with divs and one inline SVG. No chart
 * library: nothing here animates, updates or needs a scale solver, and a library would
 * add more to the bundle than the whole report weighs while fighting the hand-made look
 * the rest of the app has.
 *
 * The frame's palette is a cool slate; the four series here are warm instead, spaced far
 * enough apart in lightness to stay separable — the series colour carries meaning in the
 * stack and the legend, so it could not simply be flattened to one hue.
 */
export function ReportPane() {
  const { fields, sources, weeks, terrain } = report;
  const topCount = Math.max(...fields.rows.map((row) => row.count));

  return (
    <>
      <div className={styles.head}>
        <h2 className={styles.title}>{report.title}</h2>
        <p className={styles.summary}>
          {report.summary}
          <span className={styles.aside}> · {report.summaryAside}</span>
        </p>
      </div>

      <div className={styles.grid}>
        {/* ① 분야별 읽은 기사 */}
        <section className={styles.card}>
          <h3 className={styles.cardTitle}>{fields.label}</h3>
          <p className={styles.cardHint}>{fields.hint}</p>

          <div className={styles.bars}>
            {fields.rows.map((row) => (
              <div className={styles.barRow} key={row.id}>
                <span className={styles.barLabel}>{row.label}</span>
                <span className={styles.barTrack}>
                  <span
                    className={styles.barFill}
                    style={{ width: `${(row.count / topCount) * 100}%` }}
                  />
                </span>
                <span className={styles.barValue}>{row.count}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ② 출처별 읽기 비중 */}
        <section className={styles.card}>
          <h3 className={styles.cardTitle}>{sources.label}</h3>
          <p className={styles.cardHint}>{sources.hint}</p>

          <div className={styles.shareBar}>
            {sources.rows.map((row, index) => (
              <span
                key={row.id}
                className={`${styles.shareSegment} ${styles[`tone${index}`]}`}
                style={{ width: `${row.share}%` }}
              />
            ))}
          </div>

          <dl className={styles.legendGrid}>
            {sources.rows.map((row, index) => (
              <div className={styles.legendRow} key={row.id}>
                <dt className={styles.legendName}>
                  <span className={`${styles.swatch} ${styles[`tone${index}`]}`} aria-hidden />
                  {row.label}
                </dt>
                <dd className={styles.legendValue}>{row.share}%</dd>
              </div>
            ))}
          </dl>

          <p className={styles.footnote}>{sources.footnote}</p>
        </section>

        {/* ③ 최근 12주의 분야별 읽기 변화 */}
        <section className={`${styles.card} ${styles.cardWide}`}>
          <div className={styles.cardHead}>
            <div>
              <h3 className={styles.cardTitle}>{weeks.label}</h3>
              <p className={styles.cardHint}>{weeks.hint}</p>
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
                      const seriesIndex = column.values.length - 1 - reversedIndex;
                      return (
                        <span
                          key={weeks.series[seriesIndex].id}
                          className={`${styles.segment} ${styles[`tone${seriesIndex}`]}`}
                          style={{ height: `${(value / weeks.axisMax) * 100}%` }}
                        />
                      );
                    })}
                  </div>
                  <span className={styles.monthLabel}>{column.month ?? ''}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ④ 최근 주제 지형 */}
        <section className={styles.card}>
          <h3 className={styles.cardTitle}>{terrain.label}</h3>
          <p className={styles.cardHint}>{terrain.hint}</p>

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
    </>
  );
}
