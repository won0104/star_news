/**
 * 나를 위한 추천 — 빈 코르크 보드 위에 에셋 카드를 거는 자리표와 로그인 전 표본.
 *
 * 배경 사진(1672×941)에는 빈 보드만 있다. 제목 종이, 추천 종이, 핀은 각각 투명 PNG 에셋이며
 * 아래 좌표에 독립적으로 놓인다. 이 구조 덕분에 종이 전체가 버튼이 되고, 추천 수가 줄면 빈
 * 종이가 배경에 문신처럼 남지 않는다.
 *
 * 열 자리 = 추천 열 개. 서버가 사용자당 최대 10개를 주므로(app.recommendation.limit-per-user)
 * 자리가 남거나 모자라는 일은 정상 범위에서 생기지 않는다. 적게 오면 사용하지 않는 슬롯에는
 * 아무 에셋도 그리지 않는다.
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

export const BOARD_ASSETS = {
  title: '/assets/board/recommend-title-paper.png',
  paper: '/assets/board/recommend-paper.png',
  pin: '/assets/board/recommend-pin-red.png',
}

/** 위쪽 제목 종이 에셋이 앉는 자리. */
export const BANNER_FRAME = { x: 632, y: 120, w: 436, h: 70 }

/**
 * 종이 열 장. 왼쪽 위부터 읽는 순서 = 추천 순위.
 *
 * `tone` 은 순위 글자와 핀의 색을 함께 정한다. 핀은 붉은 원본 하나에 hue filter를 적용해 기존
 * 장면의 rose/sky/mint/sand/lilac/coral 순서를 보존한다. `doodle` 은 슬롯의 안정적인 key다.
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
