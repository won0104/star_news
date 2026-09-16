import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { eventCopy, events } from '../data/events'
import { PhotoBackdrop } from '../components/common/PhotoBackdrop'
import { TopBar } from '../components/common/TopBar'
import { ArticlePanel } from '../components/event/ArticlePanel'
import { useSettingsValues } from '../store/settings'
import { SCREEN_TRANSITIONS } from '../utils/motion'
import styles from './EventScene.module.css'

const PANEL_ID = 'article-detail'

/**
 * /event/:id — one event: its title, summary and hashtags, with the articles that covered
 * it underneath. Opened from a card in 나를 위한 추천.
 *
 * Pressing an article opens it in the bar on the right rather than navigating: the list
 * stays where it is, so several can be read one after another without losing your place,
 * and the row that is open stays marked.
 *
 * Saving is real but local. Nothing persists it — there is no endpoint behind this screen
 * — and it lives here rather than in the panel because the list shows the same mark, and
 * two copies of one truth would drift.
 *
 * No item in the top bar is current here. This is not one of the bar's four destinations;
 * it is a page underneath one, so its bar navigates into /app the way the attic's does.
 */
export function EventScene() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { reduceMotion } = useSettingsValues()
  const recommendationView = params.get('from') === 'foryou2' ? 'foryou2' : 'foryou'
  const event = events[id]

  const [openId, setOpenId] = useState(null)
  const [saved, setSaved] = useState(() =>
    Object.fromEntries((event?.articles ?? []).map((a) => [a.id, a.saved])),
  )

  const bar = (
    <TopBar
      onSelect={(view) => navigate(`/app?view=${view}`)}
      onBrand={() => navigate('/')}
      onAuth={(kind) => navigate(`/${kind}`)}
    />
  )

  // An id with no event behind it says so rather than crashing on a missing key.
  if (!event) {
    return (
      <PhotoBackdrop motion={false}>
        {bar}
        <div className={styles.page}>
          <div className={styles.column}>
            <Link className={styles.back} to={`/app?view=${recommendationView}`}>
              {eventCopy.back}
            </Link>
            <div className={styles.articles}>
              <p className={styles.missing}>{eventCopy.notFound}</p>
            </div>
          </div>
        </div>
      </PhotoBackdrop>
    )
  }

  const article = event.articles.find((a) => a.id === openId)
  const shown = article ? { ...article, saved: !!saved[article.id] } : null

  return (
    <PhotoBackdrop motion={SCREEN_TRANSITIONS && !reduceMotion}>
      {bar}

      <div className={styles.page}>
        <div className={styles.column}>
          <Link className={styles.back} to={`/app?view=${recommendationView}`}>
            {eventCopy.back}
          </Link>

          <div className={styles.head}>
            <span className={styles.eyebrow}>{eventCopy.eyebrow}</span>
            <h1 className={styles.title}>{event.title}</h1>
            <p className={styles.asOf}>{event.asOf}</p>

            <p className={styles.summaryLabel}>{eventCopy.summaryLabel}</p>
            <p className={styles.summary}>{event.summary}</p>

            <ul className={styles.tags}>
              {event.hashtags.map((tag) => (
                <li key={tag} className={styles.tag}>
                  {tag}
                </li>
              ))}
            </ul>
          </div>

          <section className={styles.articles}>
            <div className={styles.articlesHead}>
              <h2 className={styles.articlesTitle}>{eventCopy.articlesLabel}</h2>
              <span className={styles.articlesCount}>
                {eventCopy.countLabel(event.articles.length)}
              </span>
            </div>
            <p className={styles.articlesHint}>{eventCopy.articlesHint}</p>

            <ul className={styles.list}>
              {event.articles.map((entry) => (
                <li key={entry.id} className={styles.row}>
                  <button
                    type="button"
                    className={`${styles.rowButton} ${entry.id === openId ? styles.rowActive : ''}`}
                    aria-expanded={entry.id === openId}
                    aria-controls={PANEL_ID}
                    onClick={() => setOpenId(entry.id === openId ? null : entry.id)}
                  >
                    <span className={styles.rowSource}>
                      {entry.source} · {entry.at}
                      {saved[entry.id] && (
                        <span className={styles.savedMark} aria-label={eventCopy.unsave}>
                          ✓
                        </span>
                      )}
                    </span>
                    <span className={styles.rowHeadline}>{entry.headline}</span>
                    <span className={styles.rowGo} aria-hidden>
                      {eventCopy.openArticle} →
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <ArticlePanel
        id={PANEL_ID}
        article={shown}
        open={!!shown}
        onClose={() => setOpenId(null)}
        onToggleSave={(articleId) => setSaved((was) => ({ ...was, [articleId]: !was[articleId] }))}
      />
    </PhotoBackdrop>
  )
}
