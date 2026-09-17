/**
 * 나를 위한 추천 — 코르크 보드 사진 위의 자리표와, 로그인 전에 보여줄 표본.
 *
 * 사진(1680×944)에는 종이 열 장, 핀, 테이프, 낙서가 이미 찍혀 있다. 그래서 화면은 종이를
 * 그리지 않고 **종이가 있는 자리에 글자만 얹는다.** 아래 좌표는 사진의 각 종이가 차지하는
 * 사각형을 사진 크기에 대한 비율로 적은 것이다 — 사진이 어떤 크기로 늘어나도 글자가 종이
 * 안에 머물도록.
 *
 * 열 자리 = 추천 열 개. 서버가 사용자당 최대 10개를 주므로(app.recommendation.limit-per-user)
 * 자리가 남거나 모자라는 일은 정상 범위에서 생기지 않는다. 적게 오면 빈 종이가 남고, 그건
 * 사진 그대로라 어색하지 않다.
 */

import { events } from './events'
import { arrivalScene, recommend } from './recommend'

/**
 * 사진은 <PhotoBackdrop> 이 깐다(data/recommend.js 의 arrivalScene). 여기서는 크기만 안다.
 *
 * 실제 파일은 1672×941 이다. 아래 종이 좌표는 1680×944 로 본 미리보기에서 잰 값인데, 두 비율의
 * 차이가 0.2% 라 같은 좌표계로 써도 종이 위에서 1px 안으로 든다. 크기만 실제 값으로 두어
 * 이 층의 사각형이 배경 사진의 cover 사각형과 정확히 같은 비율이 되게 한다.
 */
export const BOARD_IMAGE = arrivalScene.src
/** 크기·초점·확대는 사진을 거는 쪽(arrivalScene.frame)이 정한다. 여기서는 같은 값을 읽기만. */
export const BOARD_FRAME = arrivalScene.frame
export const BOARD_SIZE = { width: BOARD_FRAME.width, height: BOARD_FRAME.height }

/** 위쪽 분홍 테이프 — 제목이 앉는 자리. */
export const BANNER_FRAME = { x: 632, y: 120, w: 436, h: 70 }

/**
 * 종이 열 장. 왼쪽 위부터 읽는 순서 = 추천 순위.
 *
 * `tone` 은 사진 속 테이프 색이다. 종이 위 글자에는 쓰지 않고(사진에 이미 색이 있다),
 * 마우스를 올렸을 때의 테두리와 좁은 화면의 대체 목록에서 그 카드를 같은 색으로 잇는 데 쓴다.
 * `doodle` 은 종이 오른쪽 위에 그려진 낙서 — 스크린 리더에게 어느 종이인지 말해줄 이름.
 */
const COLUMNS = [
  { x: 305, w: 205 },
  { x: 528, w: 207 },
  { x: 752, w: 206 },
  { x: 978, w: 207 },
  { x: 1203, w: 217 },
]
const ROWS = [
  { y: 255, h: 230 },
  { y: 508, h: 232 },
]

const TOP_ROW = [
  { tone: 'rose', doodle: '반짝이' },
  { tone: 'sky', doodle: '음표' },
  { tone: 'mint', doodle: '잎사귀' },
  { tone: 'sand', doodle: '바구니' },
  { tone: 'lilac', doodle: '달과 별' },
]
const BOTTOM_ROW = [
  { tone: 'mint', doodle: '펼친 책' },
  { tone: 'coral', doodle: '꽃병' },
  { tone: 'lilac', doodle: '라벤더' },
  { tone: 'rose', doodle: '발자국' },
  { tone: 'sky', doodle: '포크와 나이프' },
]

export const SLOTS = [...TOP_ROW, ...BOTTOM_ROW].map((meta, index) => {
  const column = COLUMNS[index % COLUMNS.length]
  const row = ROWS[Math.floor(index / COLUMNS.length)]
  return { ...meta, frame: { x: column.x, y: row.y, w: column.w, h: row.h } }
})

/** 사진 좌표 → 보드에 대한 % 위치. */
export const placement = ({ x, y, w, h }) => ({
  left: `${(x / BOARD_SIZE.width) * 100}%`,
  top: `${(y / BOARD_SIZE.height) * 100}%`,
  width: `${(w / BOARD_SIZE.width) * 100}%`,
  height: `${(h / BOARD_SIZE.height) * 100}%`,
})

export const boardCopy = {
  title: '나를 위한 추천',
  eyebrow: 'PINNED FOR YOU',
  cycle: { AM: '아침 추천', PM: '저녁 추천' },
  availableAt: (time) => `${time} 공개`,
  loading: '추천을 불러오는 중…',
  signedOut: '로그인하면 나만의 추천이 걸려요',
  signedOutHint: '읽은 기사와 관심 분야로 하루 두 번 골라 드립니다.',
  empty: '아직 공개된 추천 회차가 없어요',
  emptyHint: '06:00 · 18:00 에 새 추천이 걸립니다.',
  failed: '추천을 불러오지 못했어요. 잠시 뒤 다시 시도해주세요.',
  sampleNote: '로그인 전이라 예시 카드를 보여드려요',
  reasonLabel: '추천 이유',
  open: (label) => `${label} — 요약과 기사 보기`,
  close: '닫기',
  summaryPending: '요약을 준비하고 있어요. 조금 뒤에 다시 열어보세요.',
  articles: '이 사건을 다룬 기사',
  articlesEmpty: '아직 연결된 기사가 없어요.',
  origin: '원문 보기',
  detailFailed: '상세를 불러오지 못했어요.',
}

/* ---- 표본 -------------------------------------------------------------------- */

const EVENT_TOPIC = {
  'chip-export': 'IT_SCIENCE',
  'bok-rate': 'ECONOMY',
  'hbm4-race': 'IT_SCIENCE',
  'nk-defence': 'POLITICS',
  'won-rate': 'ECONOMY',
  'house-debt': 'ECONOMY',
  'semi-equip': 'WORLD',
  'ev-battery': 'IT_SCIENCE',
  'ai-rule': 'IT_SCIENCE',
  shipbuilding: 'ECONOMY',
}

/**
 * RecommendationBoardResponse 모양의 표본. 로그인 전이나 회차가 없을 때 판을 비워두지
 * 않기 위한 것이고, 화면은 표본임을 밝힌다. 제목·요약은 data/events.js 의 것을 그대로 써서
 * 카드와 /event/:id 가 다른 말을 하지 않게 한다.
 */
export const sampleBoard = {
  cycle: 'AM',
  generatedAt: '2026-09-17T05:30:00+09:00',
  availableAt: '2026-09-17T06:00:00+09:00',
  items: recommend.cards.map((card, index) => ({
    userRecommendationId: 501 + index,
    eventId: card.eventId,
    label: events[card.eventId]?.title ?? '새로운 추천 Event',
    topicCode: EVENT_TOPIC[card.eventId] ?? 'SOCIETY',
    score: Number((0.95 - index * 0.04).toFixed(6)),
    rank: index + 1,
    recommendationType: 'INTEREST_BASED',
    reason: card.reason,
  })),
}

/** RecommendationDetailResponse 모양의 표본. `originalUrl` 은 표본에 없으므로 null — 링크가 뜨지 않는다. */
export const sampleDetail = (item) => {
  const event = events[item.eventId]
  return {
    userRecommendationId: item.userRecommendationId,
    eventId: item.eventId,
    label: item.label,
    topicCode: item.topicCode,
    contextSummary: event?.summary ?? null,
    articles: (event?.articles ?? []).map((article, index) => ({
      articleId: index + 1,
      title: article.headline,
      organizationName: article.source,
      publishedAt: article.at,
      topicCode: item.topicCode,
      originalUrl: null,
    })),
  }
}
