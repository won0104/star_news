import { Link } from 'react-router-dom'
import { events } from '../../data/events'
import { recommend } from '../../data/recommend'
import styles from './EditorialRecommendPane.module.css'

const TOPIC_LABEL = {
  POLITICS: '정치',
  ECONOMY: '경제',
  SOCIETY: '사회',
  CULTURE: '문화',
  INTERNATIONAL: '국제',
  SPORTS: '스포츠',
  IT_SCIENCE: 'IT·과학',
}

const EVENT_TOPIC = {
  'chip-export': 'IT_SCIENCE',
  'bok-rate': 'ECONOMY',
  'hbm4-race': 'IT_SCIENCE',
  'nk-defence': 'POLITICS',
  'won-rate': 'ECONOMY',
  'house-debt': 'ECONOMY',
  'semi-equip': 'INTERNATIONAL',
  'ev-battery': 'IT_SCIENCE',
  'ai-rule': 'IT_SCIENCE',
  shipbuilding: 'ECONOMY',
}

// The project does not have an authenticated recommendation client yet. This adapter
// mirrors the endpoint response so the view can switch to server data without changing
// its markup when the session store starts carrying an access token.
const recommendationFeed = {
  cycle: 'AM',
  availableAt: '2026-09-07T06:00:00+09:00',
  hasNext: false,
  nextCursor: null,
  items: recommend.cards.map((card, index) => ({
    userRecommendationId: 501 + index,
    eventId: card.eventId,
    rank: index + 1,
    topicCode: EVENT_TOPIC[card.eventId] ?? 'SOCIETY',
    label: events[card.eventId]?.title ?? '새로운 추천 Event',
    reason: card.reason,
  })),
}

function availableTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--'
  return new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Seoul',
  }).format(date)
}

export function EditorialRecommendPane() {
  const { cycle, availableAt, items } = recommendationFeed

  return (
    <section className={styles.page} aria-labelledby="editorial-recommend-title">
      <div className={styles.inner}>
        <header className={styles.head}>
          <div>
            <p className={styles.meta}>
              {cycle} 추천 · {availableTime(availableAt)} 업데이트
            </p>
            <h1 id="editorial-recommend-title" className={styles.title}>
              추천 Event <span aria-hidden="true">★</span>
            </h1>
            <p className={styles.subtitle}>
              당신의 관심 기록을 바탕으로 지금 확인해볼 만한 Event를 골랐어요.
            </p>
          </div>

          <Link className={styles.compareLink} to="/app?view=foryou">
            기존 화면 보기
          </Link>
        </header>

        {items.length > 0 ? (
          <ol className={styles.list} aria-label="추천 Event 목록">
            {items.map((item) => (
              <li key={item.userRecommendationId} className={styles.item}>
                <Link
                  className={styles.row}
                  to={`/event/${item.eventId}?from=foryou2`}
                  aria-label={`${item.label}. 추천 이유: ${item.reason}`}
                >
                  <span className={styles.rank}>{String(item.rank).padStart(2, '0')}</span>
                  <span className={styles.content}>
                    <span className={styles.topic}>{TOPIC_LABEL[item.topicCode]}</span>
                    <strong className={styles.eventTitle}>{item.label}</strong>
                    <span className={styles.reason}>{item.reason}</span>
                  </span>
                  <span className={styles.action}>
                    추천 Event 보기 <span aria-hidden="true">→</span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <div className={styles.empty}>
            <span aria-hidden="true">★</span>
            <h2>아직 준비된 추천 Event가 없어요.</h2>
            <p>새로운 추천이 준비되면 이곳에서 바로 확인할 수 있습니다.</p>
          </div>
        )}
      </div>
    </section>
  )
}
