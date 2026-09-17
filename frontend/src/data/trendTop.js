/**
 * 오늘의 트렌드 — 상위 10개 Event.
 *
 * `homeTrends` is shaped exactly like `GET /api/v1/home`'s `data`, field for field, so
 * swapping the mock for the request is one import change and nothing downstream moves.
 * The server's own contract is HomeResponse.java, not the Swagger page — several DTOs
 * declare a nested `record Item`, they all collapse onto one `Item` schema in the
 * generated document, and the one that wins there belongs to 개인 그래프.
 *
 *   snapshotAt    공개 회차 시각 (06:00/18:00 KST). 저장된 트렌드가 없으면 null
 *   trendItemId   개별 트렌드 항목 ID
 *   rank          집계 회차 내 순위 (1~10)
 *   nodeType      공통 Node 유형. 현재 집계 대상은 Event뿐이라 항상 EVENT
 *   nodeKey       Neo4j 내부 ID가 아닌 업무 ID. 연계 API의 경로에 그대로 넣는다
 *   label         집계 시점에 저장한 Event 표시 이름
 *   articleCount  직전 24시간 동안 연결된 고유 기사 수
 */

export const homeTrends = {
  snapshotAt: '2026-09-17T06:00:00+09:00',
  trends: [
    { trendItemId: 101, rank: 1, nodeType: 'EVENT', nodeKey: 'evt-hbm4-line', label: '삼성전자, HBM4 생산라인 증설 완료', articleCount: 23 },
    { trendItemId: 102, rank: 2, nodeType: 'EVENT', nodeKey: 'evt-rate-hold', label: '한국은행, 기준금리 3.50% 동결', articleCount: 19 },
    { trendItemId: 103, rank: 3, nodeType: 'EVENT', nodeKey: 'evt-nvidia-adopt', label: '엔비디아, 차세대 가속기에 HBM4 채택', articleCount: 17 },
    { trendItemId: 104, rank: 4, nodeType: 'EVENT', nodeKey: 'evt-budget-talk', label: '여야, 내년도 예산안 협상 착수', articleCount: 14 },
    { trendItemId: 105, rank: 5, nodeType: 'EVENT', nodeKey: 'evt-export-control', label: '미국, 대중 반도체 수출통제 확대', articleCount: 12 },
    { trendItemId: 106, rank: 6, nodeType: 'EVENT', nodeKey: 'evt-bonder-order', label: '한미반도체, 본더 수주 사상 최대', articleCount: 11 },
    { trendItemId: 107, rank: 7, nodeType: 'EVENT', nodeKey: 'evt-won-rate', label: '원·달러 환율 1,330원대 진입', articleCount: 9 },
    { trendItemId: 108, rank: 8, nodeType: 'EVENT', nodeKey: 'evt-eu-ai-act', label: 'EU, AI법 단계적 시행', articleCount: 8 },
    { trendItemId: 109, rank: 9, nodeType: 'EVENT', nodeKey: 'evt-medical-talk', label: '정부·의료계 후속 협의 재개', articleCount: 6 },
    { trendItemId: 110, rank: 10, nodeType: 'EVENT', nodeKey: 'evt-baseball-rank', label: '프로야구 상위권 순위 경쟁', articleCount: 4 },
  ],
}

/**
 * 순위별 별자리.
 *
 * `/home` returns a ranked list and nothing else — no edges, no coordinates — so the sky
 * has to be authored rather than derived. Fixed slots, filled in rank order: rank 1 takes
 * the first, rank 2 the second, and so on. Deriving positions from `nodeKey` instead would
 * scatter differently every session and let two stars land on top of each other; a fixed
 * set is the one arrangement that is always readable.
 *
 * `at` is a percentage of the field, matching how the rest of this screen is authored, and
 * `atNarrow` is the second set for a field taller than it is wide. Slots avoid the top
 * strip the toolbar sits in and leave room under each star for its label.
 */
export const trendSlots = [
  { at: [45, 47], atNarrow: [50, 30] },
  { at: [22, 29], atNarrow: [24, 16] },
  { at: [69, 32], atNarrow: [76, 18] },
  { at: [62, 64], atNarrow: [72, 44] },
  { at: [36, 70], atNarrow: [28, 45] },
  { at: [11, 47], atNarrow: [50, 58] },
  { at: [86, 54], atNarrow: [22, 70] },
  { at: [51, 18], atNarrow: [78, 70] },
  { at: [77, 75], atNarrow: [38, 84] },
  { at: [17, 72], atNarrow: [66, 86] },
]

/** 별 크기는 기사 수가 정한다. 가장 많은 Event가 1.0, 가장 적은 Event가 이 값. */
export const TREND_MIN_SCALE = 0.52

export const trendSkyCopy = {
  fieldLabel: '오늘의 트렌드 별자리',
  blurb: '최근 24시간 동안 기사가 가장 많이 모인 사건입니다. 별을 누르면 그 사건과 이어진 이야기가 펼쳐집니다.',
  rank: (n) => `${n}위`,
  articles: (n) => `기사 ${n}개`,
  snapshot: (at) => `${at} 기준`,
  empty: '아직 집계된 트렌드가 없어요.',
  emptyHint: '트렌드는 매일 06시와 18시에 새로 모입니다.',
  loading: '오늘의 트렌드를 불러오는 중…',
  sampleNote: '표본 데이터 · 집계 대기 중',
  failed: '트렌드를 불러오지 못했어요.',
  failedHint: '잠시 후 다시 시도해 주세요.',
}
