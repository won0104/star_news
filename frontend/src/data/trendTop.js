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
 * 순위별 별자리 — 고정 배치 세 벌.
 *
 * `/home` returns a ranked list and nothing else — no edges, no coordinates — so the sky
 * has to be authored rather than derived. Rank 1 takes the first slot, rank 2 the second,
 * and so on. 한 벌만 두면 매일 같은 모양이라, 줄 구성을 달리한 세 벌(4-3-3, 3-4-3, 3-3-4)을
 * 두고 집계 회차마다 하나를 고른다(TrendSky 의 pickSlotPattern — 그 회차 제목 길이로 좌우가
 * 가장 고른 벌 쪽에서 고른다). 같은 회차는 늘 같은 벌이다. 세 벌 모두 x 의 평균은 50% 근처다.
 *
 * 좌표는 유리에 대한 %, 별의 가운데다. 제목은 그 아래로 자라고 가로 유리에서는 끝까지 보이므로,
 * 자리는 가장 긴 제목을 견디게 잡았다 — 1440×900(유리 950×637)에서 90자 남짓한 제목이 다섯 줄,
 * 별부터 순위까지 높이의 27% 다. 이보다 낮은 유리는 줄을 자른다(TrendSky.module.css). 그래서:
 *
 * - 좌우로 겹치는 두 별(가운데 사이가 제목 폭 23cqw + 여유 1.1% 보다 가까운 쌍)은 위아래로 28%
 *   넘게 떨어뜨린다(27% 에 딱 맞추니 조금 더 긴 제목에서 7px 겹쳤다). 네 별이 선 줄은 x 를
 *   24.1% 간격으로 두어 양쪽 끝에 2.3% 씩 남기고, 세 별이 선 줄은 끝에서 3% 넘게 띄운다.
 * - 세 줄을 유리 높이에 고르게 편다 — 별이 9~13%, 38~42%, 68~71% 에 선다. 흩어진 느낌은
 *   줄마다 높이를 1~4% 엇갈리고, 세 별이 선 줄의 x 를 비켜서 낸다.
 * - 가장 긴 제목(다섯 줄)이 맨 아래 칸에 와도 유리 높이의 95% 안에서 끝난다.
 *
 * `atNarrow` 는 세로로 긴 유리다(세 벌 모두 같다). 두 제목이 폭을 거의 다 쓰는 2열이라 x 는
 * 2~3% 만 흔들고, 제목은 세 줄(낮은 유리는 두 줄)에서 자른다. 왼쪽 위에 "오늘의 트렌드" 알약이,
 * 오른쪽 위에 기준 시각이 있어 첫 줄을 조금 내려 둔다.
 */
const NARROW_SLOTS = [
  [25, 12.5],
  [76, 10.5],
  [28, 29.5],
  [72, 27.5],
  [22, 46.5],
  [78, 44.5],
  [27, 63.5],
  [73, 61.5],
  [23, 80.5],
  [77, 78.5],
]

const WIDE_PATTERNS = [
  // 4-3-3
  [[38, 10], [13.8, 13], [62.1, 12], [86.2, 9], [22, 42], [52, 41], [81, 40], [16, 71], [46, 70], [76, 69]],
  // 3-4-3
  [[50, 9], [20, 12], [80, 10], [13.8, 41], [38, 40], [62.1, 38], [86.2, 40], [25, 69], [55, 68], [83, 70]],
  // 3-3-4
  [[44, 10], [16, 13], [76, 11], [83, 40], [25, 42], [54, 39], [13.8, 71], [38, 70], [62.1, 68], [86.2, 69]],
]

export const trendSlotPatterns = WIDE_PATTERNS.map((wide) =>
  wide.map((at, index) => ({ at, atNarrow: NARROW_SLOTS[index] })),
)

/** 별 크기는 기사 수가 정한다. 가장 많은 Event가 1.0, 가장 적은 Event가 이 값. */
export const TREND_MIN_SCALE = 0.52

export const trendSkyCopy = {
  fieldLabel: '오늘의 트렌드 별자리',
  rank: (n) => `${n}위`,
  articles: (n) => `기사 ${n}개`,
  snapshot: (at) => `${at} 기준`,
  empty: '아직 집계된 트렌드가 없어요.',
  emptyHint: '트렌드는 매일 06시와 18시에 새로 모입니다.',
  loading: '오늘의 트렌드를 불러오는 중…',
  failed: '트렌드를 불러오지 못했어요.',
  failedHint: '잠시 후 다시 시도해 주세요.',
  topicEmpty: '이 분야는 아직 모인 트렌드가 없어요.',
  topicEmptyHint: '분야마다 따로 모이므로, 다른 분야에는 있을 수 있어요.',
}
