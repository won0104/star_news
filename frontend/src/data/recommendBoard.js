/**
 * 나를 위한 추천 — 빈 코르크 보드 위에 에셋 카드를 거는 자리표와 로그인 전 표본.
 *
 * 배경에는 빈 보드만 있다. 제목 띠, 추천 종이, 압정은 각각 투명 에셋이며 아래 좌표에
 * 독립적으로 놓인다. 이 구조 덕분에 종이 전체가 버튼이 되고, 추천 수가 줄면 빈 종이가
 * 배경에 문신처럼 남지 않는다.
 *
 * 열 자리 = 추천 열 개. 서버가 사용자당 최대 10개를 주므로(app.recommendation.limit-per-user)
 * 자리가 남거나 모자라는 일은 정상 범위에서 생기지 않는다. 적게 오면 사용하지 않는 슬롯에는
 * 아무 에셋도 그리지 않는다.
 */

import { events } from './events'
import { recommend } from './recommend'

/**
 * 제목 띠, 추천 종이, 압정. 압정은 tone 마다 실제로 그려진 색이 따로 있다 — 예전에는 붉은
 * 한 장에 hue-rotate 를 걸어 여섯 색을 흉내 냈는데, 필터는 하이라이트와 그림자까지 같이
 * 돌려 색마다 광택이 어긋났다.
 */
export const BOARD_ASSETS = {
  title: '/assets/board/recommend-v2-banner.webp',
  paper: '/assets/board/recommend-v2-paper.webp',
}

/** tone 이름은 장면이 쓰던 것을 그대로 두고, 그 색으로 그려진 압정을 건다. */
export const PIN_BY_TONE = {
  rose: '/assets/board/recommend-pin-v2-red.webp',
  sky: '/assets/board/recommend-pin-v2-blue.webp',
  mint: '/assets/board/recommend-pin-v2-green.webp',
  sand: '/assets/board/recommend-pin-v2-yellow.webp',
  lilac: '/assets/board/recommend-pin-v2-purple.webp',
  coral: '/assets/board/recommend-pin-v2-orange.webp',
}

/**
 * 방이 그려진 배경들. 사진은 뷰포트를 그대로 채우므로(늘어난다) 화면 비율에서 먼 그림을
 * 고르면 나무틀과 화분이 눈에 띄게 뭉개진다 — 그래서 비율별로 한 장씩 두고 가장 가까운 것을
 * 고른다. 16:9 한 장만 쓰던 때 1280×1024 에서 가로가 30% 줄었다.
 *
 * `cork` 는 코르크 면의 사각형이며 그림에 대한 비율이다. 사진이 뷰포트를 채우므로 이 값은
 * 화면에 대한 비율이기도 하다. 알파가 아니라 색(r-b ≥ 90)으로 실측한 값 — 코르크만 주황이고
 * 벽과 나무틀은 그렇지 않다.
 *
 * 보드를 추가하려면 여기 한 항목만 넣으면 된다. 종이 자리는 아래 LAYOUT 이 코르크에 대한
 * 비율로 들고 있으므로 좌표를 다시 잴 필요가 없다.
 */
export const BOARDS = [
  {
    ratio: 1672 / 941,
    src: '/assets/board/recommend-board-empty-16x9-v2.webp',
    cork: { x: 0.19498, y: 0.09564, w: 0.72548, h: 0.77258 },
  },
  {
    ratio: 1448 / 1086,
    src: '/assets/board/recommend-board-empty-4x3-v2.webp',
    cork: { x: 0.14917, y: 0.13076, w: 0.74862, h: 0.63996 },
  },
  {
    ratio: 1086 / 1448,
    src: '/assets/board/recommend-board-empty-3x4-v2.webp',
    cork: { x: 0.17587, y: 0.11326, w: 0.66022, h: 0.71202 },
  },
  {
    ratio: 941 / 1672,
    src: '/assets/board/recommend-board-empty-9x16-v2.webp',
    cork: { x: 0.16366, y: 0.11065, w: 0.68225, h: 0.72428 },
  },
]

/**
 * `tone` 은 순위 글자 색과 압정을 함께 정한다. `doodle` 은 슬롯의 안정적인 key다.
 *
 * 자리 좌표는 없다. 종이는 코르크 안에서 그리드로 흐르므로 보드가 좁아지면 열 수가 줄고,
 * 열 장이 한 화면에 안 들어가면 코르크 안에서 스크롤된다. 자리를 좌표로 박아두던 때에는
 * 보드보다 목록이 길어지면 종이가 나무틀을 넘어 책상 위로 흘러내렸다.
 */
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

export const SLOTS = [...TOP_ROW, ...BOTTOM_ROW]

/** 코르크 면의 자리 — 화면에 대한 %. 사진이 뷰포트를 채우므로 보드의 `cork` 가 곧 그 값이다. */
export const corkPlacement = (board) => ({
  left: `${board.cork.x * 100}%`,
  top: `${board.cork.y * 100}%`,
  width: `${board.cork.w * 100}%`,
  height: `${board.cork.h * 100}%`,
})

export const boardCopy = {
  title: '나를 위한 추천',
  eyebrow: 'PINNED FOR YOU',
  updateSchedule: '매일 06:00 · 18:00 업데이트',
  loading: '추천을 불러오는 중…',
  signedOut: '로그인하면 나만의 추천이 걸려요',
  signedOutHint: '읽은 기사와 관심 분야로 하루 두 번 골라 드립니다.',
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
  'semi-equip': 'INTERNATIONAL',
  'ev-battery': 'IT_SCIENCE',
  'ai-rule': 'IT_SCIENCE',
  shipbuilding: 'ECONOMY',
}

/**
 * RecommendationBoardResponse 모양의 표본. 비로그인일 때 판을 비워두지
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
