/**
 * 분야 7개 — 코드·한글명·색조.
 *
 * 목업이 아니라 화면의 분류 체계다. 서버도 같은 7개 코드를 쓰지만(topicCode), 북마크 탭은
 * 내가 읽은 기록이 없는 분야까지 늘 7개가 서 있어야 하므로 응답에서 만들지 않고 여기 둔다.
 * 응답이 주는 것은 "그 분야에 내 기록이 있는가"이지 "그 분야가 존재하는가"가 아니다.
 *
 * `tone` 은 다이어리 페이지의 색조 클래스 이름이고, 행성의 별 색은 HistoryPlanet 의
 * TOPIC_COLORS 가 따로 가진다 — 하나는 종이, 하나는 빛이라 값이 다르다.
 */
export const TOPICS = [
  { topicCode: 'POLITICS', topicName: '정치', tone: 'rose' },
  { topicCode: 'ECONOMY', topicName: '경제', tone: 'gold' },
  { topicCode: 'SOCIETY', topicName: '사회', tone: 'mint' },
  { topicCode: 'CULTURE', topicName: '문화', tone: 'peach' },
  { topicCode: 'INTERNATIONAL', topicName: '국제', tone: 'violet' },
  { topicCode: 'SPORTS', topicName: '스포츠', tone: 'cyan' },
  { topicCode: 'IT_SCIENCE', topicName: 'IT·과학', tone: 'blue' },
]

/**
 * 분야를 고르지 않은 상태.
 *
 * `topicCode` 가 null 인 것이 요점이다 — "전체"라는 분야가 따로 있는 것이 아니라 고르지
 * 않았다는 뜻이고, 그래서 URL 에도 담기지 않는다. 서버에도 보낼 값이 없다.
 */
export const TOPIC_ALL = { topicCode: null, topicName: '전체' }

export const topicByCode = new Map(TOPICS.map((topic) => [topic.topicCode, topic]))

export const topicName = (topicCode) => topicByCode.get(topicCode)?.topicName ?? topicCode
