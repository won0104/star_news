import { graph } from './assets';
/**
 * Screen 2 — "Graph Exploration / Event centered / 한국은행 기준금리 동결" (Figma 680:2).
 * The room, yarn and card geometry are shared with the attic view; only the content,
 * the hanging threads, the relation chips and the exploration controls are new.
 */

export const graphHero = {
  brand: '별빛 뉴스  ·  그래프 탐색',
  titleLines: ['한 사건에서,', '다음 맥락으로.'],
  subtitleLines: ['카드를 선택하면 그 지식이 중심이 되고,', '연결된 뉴스가 다시 펼쳐집니다.']
};
export const graphActiveNav = {
  label: '⌘   탐색 중'
};
export const graphNavItems = [{
  id: 'trend',
  label: '○   오늘의 트렌드',
  top: 383
}, {
  id: 'foryou',
  label: '⌖   나를 위한 추천',
  top: 442
}, {
  id: 'saved',
  label: '▱   저장됨',
  top: 501
}, {
  id: 'history',
  label: '◷   나의 기록',
  top: 560
}];
export const graphMotto = ['NEWS IN CONTEXT', 'GRAPH EXPLORATION'];
export const graphSearchPlaceholder = '⌕   뉴스 그래프 검색';
export const graphControls = {
  eyebrow: '탐색 도구',
  depth: '연결 깊이 1  ▾',
  count: '연결 8',
  more: '+8  더 보기'
};
export const graphHints = [{
  id: 'strength',
  left: 316,
  top: 510,
  width: 150,
  opacity: 0.55,
  lines: ['실의 선명도는', '연결 강도를 나타냅니다.']
}, {
  id: 'recenter',
  left: 1518,
  top: 478,
  width: 125,
  opacity: 0.55,
  lines: ['다른 카드를 고르면', '중심이 이동합니다.']
}];
export const graphTagline = {
  left: 1438,
  top: 815,
  width: 180,
  opacity: 0.62,
  lines: ['CENTER · EVENT', 'NEIGHBORS 7 + 8']
};

/** The centred event card: an illustrated thumbnail rather than a photo crop. */
export const graphEventContent = {
  type: 'EVENT',
  thumbnailCaption: '기준금리 동결',
  headlineLines: ['한국은행', '기준금리 동결'],
  category: '경제 · 통화정책',
  articles: '관련 기사 12건',
  bookmark: '♡'
};
export const graphStatementContent = {
  type: 'STATEMENT',
  bodyLines: ['물가와 금융안정', '상황을 함께 살펴볼', '필요가 있습니다.'],
  source: '— 발표 요지'
};

/** Neighbour cards, keyed by the shared mini-card shell they reuse. */
export const graphEntityContent = {
  people: {
    id: 'people',
    type: 'ENTITY',
    typeColor: 'var(--entity-color)',
    titleLines: ['한국은행'],
    sub: '기관',
    dot: graph.dot.entityBank
  },
  policy: {
    id: 'policy',
    type: 'ENTITY',
    typeColor: 'var(--entity-color)',
    titleLines: ['금융통화', '위원회'],
    sub: '기관',
    dot: graph.dot.entityCommittee
  },
  region: {
    id: 'region',
    type: 'EVENT',
    typeColor: 'var(--accent-event)',
    titleLines: ['물가 상승률', '둔화'],
    sub: '관련 사건',
    dot: graph.dot.relatedEvent
  },
  peace: {
    id: 'peace',
    type: 'TOPIC',
    typeColor: 'var(--topic-color)',
    titleLines: ['통화정책'],
    sub: '주제',
    dot: graph.dot.topic
  },
  impact: {
    id: 'impact',
    type: 'TIME',
    typeColor: 'var(--time-color)',
    titleLines: ['2026 ·', '3분기'],
    sub: '시간',
    dot: graph.dot.time
  },
  media: {
    id: 'media',
    type: 'STORY',
    typeColor: 'var(--story-color)',
    titleLines: ['금리', '방향성'],
    sub: '흐름',
    dot: graph.dot.story
  }
};
export const relationChips = [{
  id: 'entity',
  left: 653,
  top: 168,
  width: 54,
  height: 24,
  label: '주체',
  dot: graph.relationDot.entity
}, {
  id: 'statement',
  left: 1017,
  top: 269,
  width: 56,
  height: 24,
  label: '발언',
  dot: graph.relationDot.statement
}, {
  id: 'topic',
  left: 1276,
  top: 178,
  width: 54,
  height: 24,
  label: '주제',
  dot: graph.relationDot.topic
}, {
  id: 'event',
  left: 520,
  top: 593,
  width: 72,
  height: 24,
  label: '연관 사건',
  dot: graph.relationDot.event
}];
const KNOT_INSET = '-11.9% -35.71% -59.52% -35.71%';
const knot = (src, left, top) => ({
  src,
  left,
  top,
  width: 4.2,
  height: 4.2,
  inset: KNOT_INSET
});

/** Threads tying each card up to the yarn, coloured to match the card's type. */
export const hangers = [{
  id: 'event-center',
  line: {
    src: graph.hanger.eventCenter,
    left: 884.711,
    top: 131,
    width: 0.577,
    height: 29,
    inset: '-0.32% -138.55%'
  },
  knot: knot(graph.hanger.eventCenterKnot, 882.9, 157.9)
}, {
  id: 'statement',
  line: {
    src: graph.hanger.statement,
    left: 1177.711,
    top: 245,
    width: 0.577,
    height: 35,
    inset: '-0.22% -138.56%'
  },
  knot: knot(graph.hanger.statementKnot, 1175.9, 277.9)
}, {
  id: 'entity-bank',
  line: {
    src: graph.hanger.entityBank,
    left: 585.711,
    top: 74,
    width: 0.577,
    height: 16,
    inset: '-1.02% -138.53%'
  },
  knot: knot(graph.hanger.entityBankKnot, 583.9, 87.9)
}, {
  id: 'entity-committee',
  line: {
    src: graph.hanger.entityCommittee,
    left: 550.711,
    top: 326,
    width: 0.577,
    height: 32,
    inset: '-0.26% -138.55%'
  },
  knot: knot(graph.hanger.entityCommitteeKnot, 548.9, 355.9)
}, {
  id: 'related-event',
  line: {
    src: graph.hanger.relatedEvent,
    left: 494.711,
    top: 628,
    width: 0.577,
    height: 18,
    inset: '-0.81% -138.54%'
  },
  knot: knot(graph.hanger.relatedEventKnot, 492.9, 643.9)
}, {
  id: 'topic',
  line: {
    src: graph.hanger.topic,
    left: 1425.711,
    top: 113,
    width: 0.577,
    height: 27,
    inset: '-0.36% -138.55%'
  },
  knot: knot(graph.hanger.topicKnot, 1423.9, 137.9)
}, {
  id: 'time',
  line: {
    src: graph.hanger.time,
    left: 1444.711,
    top: 431,
    width: 0.577,
    height: 24,
    inset: '-0.46% -138.55%'
  },
  knot: knot(graph.hanger.timeKnot, 1442.9, 452.9)
}, {
  id: 'story',
  line: {
    src: graph.hanger.story,
    left: 1304.711,
    top: 624,
    width: 0.577,
    height: 20,
    inset: '-0.66% -138.54%'
  },
  knot: knot(graph.hanger.storyKnot, 1302.9, 641.9)
}];
