/**
 * 주요 트렌드 — the event constellation.
 *
 * Events are the stars and the star carries the event: an actor and a two-line phrase
 * are set inside the shape, so a node reads as something that happened rather than as
 * a company. The edges are event-to-event.
 *
 * There are no coordinates here. One event is centred and whatever it relates to is
 * placed around it from SLOTS in the component, so any event set lays itself out and
 * clicking a related star re-centres on it. That is forced by geometry rather than
 * chosen: a star wide enough to hold legible text is ~320px across on this field, and
 * five of those fit where nine collide. See the note on SLOTS.
 *
 * Seed content. The 삼성전자 event is the one that was given; the rest are written to
 * plausibly surround it. A real feed replaces `events` and `relations` wholesale.
 *
 * Nothing renders any of this at the moment — 주요 트렌드 is the clip in `nightfall`
 * above while the screen is redesigned. <TrendGraph> is still in the tree and intact,
 * so putting the constellation back is one line in <ViewPane>.
 */

/**
 * The window 오늘의 트렌드 is seen through, as layers: `backdrops` is the night outside
 * and nothing else, and one of `frames` is the wooden window over it.
 *
 * Splitting them is what makes the set small. A backdrop may be cropped to any shape,
 * so landscape and portrait cover every viewport between them. A frame may not — the
 * plant at its right and the bush at its left each run the full lower half of the
 * composition, and neither survives losing an edge — so it is stretched to fill
 * instead, and stretching only holds near the ratio it was drawn at.
 *
 * Hence five frames, a constant 0.75 apart in ratio. Whatever the viewport, the nearest
 * of them is within about 15% — see `useNearestWindow`, which is also all that has to
 * be true for a sixth to work: add it here, in ratio order, and nothing else changes.
 *
 * `opening` is the glass, in per cent of the frame's own box, measured off the asset's
 * alpha rather than authored. <TrendStage> insets the sky by it and then lets it run a
 * little under the wood; the margin is its business, so these stay the measurement.
 *
 * A transition stays disabled until a clip is authored to end on this exact room —
 * handing off from the former attic image would read as a flash cut.
 */
export const nightfall = {
  backdrops: {
    landscape: '/assets/trend/trend-window-backdrop-landscape-v2.webp',
    portrait: '/assets/trend/trend-window-backdrop-portrait-v2.webp',
  },
  frames: [
    {
      ratio: 16 / 9,
      src: '/assets/trend/trend-window-frame-16x9-v2.webp',
      opening: { top: 9.7, right: 6.6, bottom: 12.6, left: 11.5 },
    },
    {
      ratio: 4 / 3,
      src: '/assets/trend/trend-window-frame-4x3-v2.webp',
      opening: { top: 12.2, right: 11.2, bottom: 17, left: 12.5 },
    },
    {
      ratio: 1,
      src: '/assets/trend/trend-window-frame-1x1-v2.webp',
      opening: { top: 13.4, right: 12, bottom: 14.4, left: 16.3 },
    },
    {
      ratio: 3 / 4,
      src: '/assets/trend/trend-window-frame-3x4-v2.webp',
      opening: { top: 9, right: 12.1, bottom: 13.4, left: 13.5 },
    },
    {
      ratio: 9 / 16,
      src: '/assets/trend/trend-window-frame-9x16-v2.webp',
      opening: { top: 9.7, right: 11.9, bottom: 13.9, left: 15.3 },
    },
  ],
  sidebarStill: '/assets/trend/trend-window-night-sidebar-v3.webp',
  clip: null,
}

/** Exact exported layers from Figma frame 870:2. The relation layer includes the
 * ambient stars, six authored edges, the centre sticker, the upper entity and the
 * faded continuation event; the remaining assets sit above it at their named slots. */
export const trendFigmaAssets = {
  relations: '/assets/trend/figma/relations-core.svg',
  centreGlow: '/assets/trend/figma/event-center-glow.svg',
  relatedLeftGlow: '/assets/trend/figma/event-related-left-glow.svg',
  relatedLeftSticker: '/assets/trend/figma/event-related-left-sticker.svg',
  relatedRightGlow: '/assets/trend/figma/event-related-right-glow.svg',
  relatedRightSticker: '/assets/trend/figma/event-related-right-sticker.svg',
  entityGlow: '/assets/trend/figma/entity-glow.svg',
  entitySticker: '/assets/trend/figma/entity-sticker.svg',
  statementGlow: '/assets/trend/figma/statement-glow.svg',
  statementSticker: '/assets/trend/figma/statement-sticker.svg',
}

/**
 * Decorative stars from the Figma relation export, now represented as independent
 * elements. `events` records which event neighbourhood can light each star when the
 * exploration hover treatment is added.
 */
export const ambientStars = [
  {
    id: 'ambient-01',
    role: 'entity',
    at: [7.47, 29.83],
    size: 35,
    rotate: -8,
    events: ['increase', 'adopt'],
  },
  {
    id: 'ambient-02',
    role: 'statement',
    at: [12.29, 16.72],
    size: 40,
    rotate: 4,
    events: ['adopt'],
  },
  {
    id: 'ambient-03',
    role: 'event',
    at: [14.34, 36.5],
    size: 44,
    rotate: -4,
    events: ['adopt', 'increase'],
  },
  {
    id: 'ambient-04',
    role: 'entity',
    at: [94.34, 65.5],
    size: 34,
    rotate: 8,
    opacity: 0.38,
    events: ['bonder', 'cowos'],
  },
  {
    id: 'ambient-05',
    role: 'statement',
    at: [74.1, 62.83],
    size: 42,
    rotate: 3,
    events: ['bonder'],
  },
  {
    id: 'ambient-06',
    role: 'event',
    at: [58.99, 75.83],
    size: 30,
    rotate: -2,
    events: ['bonder', 'cowos'],
  },
  {
    id: 'ambient-07',
    role: 'entity',
    at: [35.31, 85.72],
    size: 34,
    rotate: -5,
    events: ['increase'],
  },
  {
    id: 'ambient-08',
    role: 'statement',
    at: [62.22, 90.28],
    size: 42,
    rotate: 6,
    events: ['increase', 'cowos'],
  },
  {
    id: 'ambient-09',
    role: 'statement',
    at: [39.44, 79.17],
    size: 42,
    rotate: -7,
    events: ['increase'],
  },
  { id: 'ambient-10', role: 'event', at: [38.99, 94.17], size: 44, rotate: 5, events: ['cowos'] },
  {
    id: 'ambient-11',
    role: 'entity',
    at: [64.41, 32.5],
    size: 34,
    rotate: -3,
    events: ['adopt', 'bonder'],
  },
  {
    id: 'ambient-12',
    role: 'statement',
    at: [74.1, 26.94],
    size: 42,
    rotate: 7,
    events: ['adopt'],
  },
  { id: 'ambient-13', role: 'event', at: [87.71, 41.44], size: 38, rotate: -6, events: ['bonder'] },
  {
    id: 'ambient-14',
    role: 'statement',
    at: [8.4, 73.94],
    size: 42,
    rotate: 2,
    events: ['increase'],
  },
  {
    id: 'ambient-15',
    role: 'event',
    at: [18.16, 77.06],
    size: 44,
    rotate: -4,
    events: ['increase', 'adopt'],
  },
  { id: 'ambient-16', role: 'event', at: [10.8, 57.39], size: 38, rotate: 5, events: ['increase'] },
  { id: 'ambient-17', role: 'event', at: [11.77, 86.17], size: 36, rotate: -5, events: ['cowos'] },
  {
    id: 'ambient-18',
    role: 'statement',
    at: [55.27, 24.84],
    size: 42,
    rotate: 68,
    events: ['adopt'],
  },
  {
    id: 'ambient-19',
    role: 'statement',
    at: [71.42, 13.03],
    size: 42,
    rotate: -3,
    events: ['bonder'],
  },
  { id: 'ambient-20', role: 'event', at: [53.06, 14.89], size: 44, rotate: 7, events: ['adopt'] },
]

/**
 * The stars themselves. Three renders, each cropped to the same body-relative frame so
 * they share one glow ratio — see the note in scripts/crop-stars.py. The star's body is
 * 1/1.8 of the image, which is what the sizes in TrendConstellation.module.css assume.
 */
export const stars = {
  event: '/assets/trend/star-event.webp',
  statement: '/assets/trend/star-statement.webp',
  entity: '/assets/trend/star-entity.webp',
}

/**
 * 주요 트렌드's constellation: one event at a time, taken apart into what it is made of,
 * with the events it connects to around it. Drawn once the clip has handed the screen
 * over to the still.
 *
 * Three kinds of node, and the star's size is the kind — the centre event is the biggest
 * star, a related event the next, a statement a middle one, an entity a small one.
 * Nothing else encodes the kind, so the picture is read by size the way a sky is.
 *
 * Only an event can be the centre. Pressing a related event moves the centre onto it and
 * the picture is drawn again around it; pressing the centre opens its articles. An entity
 * or a statement does neither — they describe the centre rather than being somewhere to
 * go. See `interactive` in TrendConstellation.
 *
 * Every event here has the same shape — two related events, two entities, one statement —
 * and that is load-bearing rather than tidy. The layout is a fixed set of slots that a
 * node is dropped into, and slots are what the "no line crosses a label" geometry was
 * verified against; if the shape varied by event, every centre would be its own layout to
 * check. An event carrying more than that shows the first of each, which is why `related`
 * is ordered.
 *
 * `related` is written on both ends, so any walk can be walked back. Nothing here is a
 * feed yet: the 삼성전자 event is the one that was given and the rest are written to
 * plausibly surround it, all on the same 9월 8일.
 */
export const constellationEvents = {
  increase: {
    id: 'increase',
    layout: 'spread',
    label: '삼성전자, HBM4 생산라인 증설 완료',
    meta: '사건 · 9월 8일',
    related: ['adopt', 'bonder'],
    entities: [
      { id: 'samsung', label: '삼성전자', meta: '기업' },
      { id: 'pyeongtaek', label: '평택 4공장', meta: '장소' },
    ],
    statements: [
      { id: 'yield', label: '"연내 양산 물량을 두 배로 늘린다"', meta: '발언 · 삼성전자 공시' },
    ],
  },
  adopt: {
    id: 'adopt',
    layout: 'orbit',
    label: '엔비디아, 차세대 가속기에 HBM4 채택',
    meta: '사건 · 9월 8일',
    related: ['increase', 'cowos'],
    entities: [
      { id: 'nvidia', label: '엔비디아', meta: '기업' },
      { id: 'hbm4', label: 'HBM4', meta: '제품' },
    ],
    statements: [
      { id: 'adopt-say', label: '"차세대 가속기에 HBM4를 채택한다"', meta: '발언 · 엔비디아 발표' },
    ],
  },
  bonder: {
    id: 'bonder',
    layout: 'diagonal',
    label: '한미반도체, HBM 본더 수주 사상 최대',
    meta: '사건 · 9월 2일',
    related: ['increase', 'cowos'],
    entities: [
      { id: 'hanmi', label: '한미반도체', meta: '기업' },
      { id: 'bonder-tool', label: 'HBM 본더', meta: '장비' },
    ],
    statements: [
      {
        id: 'bonder-say',
        label: '"수주 잔고가 사상 최대 수준이다"',
        meta: '발언 · 한미반도체 공시',
      },
    ],
  },
  cowos: {
    id: 'cowos',
    layout: 'crown',
    label: 'TSMC, CoWoS 생산능력 두 배 확대',
    meta: '사건 · 9월 4일',
    related: ['adopt', 'bonder'],
    entities: [
      { id: 'tsmc', label: 'TSMC', meta: '기업' },
      { id: 'cowos-proc', label: 'CoWoS', meta: '공정' },
    ],
    statements: [
      { id: 'cowos-say', label: '"패키징 생산능력을 두 배로 늘린다"', meta: '발언 · TSMC 발표' },
    ],
  },
}

/** Where the walk starts. */
export const constellationStart = 'increase'

/**
 * The slots a centre's nodes are dropped into, and the whole of the layout.
 *
 * `at` is a percentage of the field, not a pixel: the field is whatever the viewport
 * leaves under the bar and its shape changes with the window, so the layout is authored
 * in the proportions it keeps rather than in a coordinate space that would need scaling.
 * `atNarrow` is the second set, for a field taller than it is wide — one set cannot serve
 * both, since a composition held together by percentages comes apart when the shape does.
 *
 * `side` is which way the slot's text hangs, and it exists because a line drawn to a star
 * runs through whatever is written under it. The rule is only ever "put the text where the
 * lines are not": the centre's links all leave sideways and downward, so its text goes
 * above; the two entity slots have their link leaving inward, so their text goes outward.
 *
 * `hideNarrow` drops a slot on a narrow field, and the two entity slots carry it. Six
 * nodes with sentences under them do not fit in 375px of width: measured, every
 * arrangement that kept all six put the centre's downward fan through a related event's
 * label, because the two are on nearly the same ray whatever the spacing. What the narrow
 * field keeps is what can be walked — the centre and the two events beside it — plus the
 * statement. The entities are the descriptors, so they are the ones to lose.
 */
export const constellationSlots = [
  { role: 'centre', visual: 'centre', at: [43.68, 55.89], atNarrow: [50, 28] },
  { role: 'related', visual: 'relatedLeft', at: [23.68, 33.33], atNarrow: [23, 52] },
  { role: 'related', visual: 'relatedRight', at: [68.01, 42.89], atNarrow: [77, 52] },
  { role: 'entity', visual: 'entityLeft', at: [22.4, 61.56], hideNarrow: true },
  { role: 'entity', visual: 'entityTop', at: [65.38, 20.28], hideNarrow: true },
  { role: 'statement', visual: 'statement', at: [50, 78.11], atNarrow: [50, 76] },
]

/** Decorative-star coordinates for each event composition. Keeping these near the
 * perimeter leaves the event labels clear while letting every layout have its own sky. */
export const ambientLayouts = {
  spread: [
    [4, 14],
    [14, 7],
    [28, 10],
    [42, 5],
    [58, 7],
    [75, 6],
    [91, 14],
    [96, 27],
    [94, 43],
    [96, 60],
    [91, 79],
    [78, 91],
    [64, 95],
    [45, 94],
    [29, 92],
    [14, 88],
    [5, 76],
    [4, 59],
    [5, 42],
    [7, 27],
  ],
  orbit: [
    [7, 12],
    [22, 5],
    [39, 8],
    [58, 5],
    [77, 8],
    [92, 17],
    [96, 34],
    [93, 52],
    [96, 70],
    [87, 88],
    [70, 94],
    [52, 91],
    [34, 95],
    [16, 88],
    [5, 73],
    [8, 57],
    [3, 39],
    [11, 25],
    [84, 25],
    [82, 76],
  ],
  diagonal: [
    [5, 11],
    [20, 6],
    [37, 7],
    [54, 5],
    [90, 9],
    [96, 24],
    [92, 39],
    [97, 56],
    [91, 75],
    [96, 90],
    [78, 94],
    [62, 92],
    [34, 95],
    [16, 89],
    [5, 78],
    [8, 63],
    [3, 47],
    [8, 30],
    [83, 15],
    [70, 6],
  ],
  crown: [
    [4, 10],
    [16, 5],
    [31, 8],
    [68, 6],
    [84, 5],
    [96, 14],
    [93, 29],
    [97, 45],
    [94, 58],
    [96, 81],
    [83, 93],
    [66, 95],
    [50, 93],
    [34, 96],
    [18, 91],
    [5, 84],
    [4, 48],
    [7, 31],
    [89, 44],
    [11, 20],
  ],
}
export const constellationLayouts = {
  spread: { label: '펼침형', slots: constellationSlots },
  orbit: {
    label: '궤도형',
    slots: [
      { role: 'centre', visual: 'centre', at: [44, 51], atNarrow: [50, 43] },
      { role: 'related', visual: 'relatedLeft', at: [18, 49], atNarrow: [25, 25] },
      { role: 'related', visual: 'relatedRight', at: [78, 48], atNarrow: [75, 25] },
      { role: 'entity', visual: 'entityLeft', at: [29, 21], hideNarrow: true },
      { role: 'entity', visual: 'entityTop', at: [69, 20], hideNarrow: true },
      { role: 'statement', visual: 'statement', at: [48, 80], atNarrow: [50, 74] },
    ],
  },
  diagonal: {
    label: '대각선형',
    slots: [
      { role: 'centre', visual: 'centre', at: [42, 53], atNarrow: [45, 43] },
      { role: 'related', visual: 'relatedLeft', at: [19, 29], atNarrow: [24, 22] },
      { role: 'related', visual: 'relatedRight', at: [71, 70], atNarrow: [76, 62] },
      { role: 'entity', visual: 'entityLeft', at: [74, 19], hideNarrow: true },
      { role: 'entity', visual: 'entityTop', at: [20, 75], hideNarrow: true },
      { role: 'statement', visual: 'statement', at: [51, 84], atNarrow: [40, 78] },
    ],
  },
  crown: {
    label: '왕관형',
    slots: [
      { role: 'centre', visual: 'centre', at: [46, 64], atNarrow: [50, 55] },
      { role: 'related', visual: 'relatedLeft', at: [25, 35], atNarrow: [25, 29] },
      { role: 'related', visual: 'relatedRight', at: [72, 34], atNarrow: [75, 29] },
      { role: 'entity', visual: 'entityLeft', at: [15, 68], hideNarrow: true },
      { role: 'entity', visual: 'entityTop', at: [84, 65], hideNarrow: true },
      { role: 'statement', visual: 'statement', at: [48, 18], atNarrow: [50, 81] },
    ],
  },
}

/**
 * What the right-hand panel shows for an event, keyed by the event's id. Structured after
 * the supplied design: an eyebrow, the subject with a star beside it, how many articles
 * and as of when, a sentence of summary, then the articles — each a source and a time, a
 * headline, a way into it, and a bookmark.
 *
 * The eyebrow says EVENT where the design said TOPIC, because the subject here is an
 * event; the panel opens from the centre star and the centre is always an event.
 *
 * Only events have one. An entity or a statement cannot be the centre, so it never opens
 * this panel — see the note on `interactive` in TrendConstellation.
 *
 * Sources are the four in the report's 출처별 읽기 비중 (data/world.js), so the same
 * press names run through both screens.
 */
export const eventPanels = {
  increase: {
    eyebrow: 'CURRENT EVENT',
    count: 18,
    asOf: '2026.09.08 11:20 기준',
    summary: 'HBM4 증설과 공급 계약, 후속 장비 발주를 중심으로 보도가 이어지고 있어요.',
    articles: [
      {
        id: 'yonhap-hbm4-line',
        source: '연합뉴스',
        at: '2026.09.08 11:02',
        headline: '삼성전자, 평택 HBM4 라인 가동 시작',
        saved: true,
      },
      {
        id: 'hankyung-supply',
        source: '한국경제',
        at: '2026.09.08 10:38',
        headline: 'HBM4 공급 계약, 하반기 실적에 반영',
        saved: false,
      },
      {
        id: 'etnews-orders',
        source: '전자신문',
        at: '2026.09.08 10:20',
        headline: '후속 장비 발주 확대와 협력사 수주 전망',
        saved: false,
      },
    ],
  },

  adopt: {
    eyebrow: 'CURRENT EVENT',
    count: 24,
    asOf: '2026.09.08 11:14 기준',
    summary: '채택 확정과 공급망 재편, 경쟁 메모리사의 대응을 중심으로 보도가 이어지고 있어요.',
    articles: [
      {
        id: 'yonhap-adopt',
        source: '연합뉴스',
        at: '2026.09.08 10:51',
        headline: '엔비디아, 차세대 가속기 메모리로 HBM4 확정',
        saved: false,
      },
      {
        id: 'hankyung-chain',
        source: '한국경제',
        at: '2026.09.08 10:22',
        headline: '공급망 재편 시작, 국내 메모리사 수주 경쟁',
        saved: true,
      },
      {
        id: 'etnews-rivals',
        source: '전자신문',
        at: '2026.09.08 09:47',
        headline: '경쟁사 대응 시나리오와 단가 협상 쟁점',
        saved: false,
      },
    ],
  },

  bonder: {
    eyebrow: 'CURRENT EVENT',
    count: 11,
    asOf: '2026.09.02 16:40 기준',
    summary: '본더 수주 공시와 협력사 실적, 증설 일정과의 연결을 중심으로 보도가 이어지고 있어요.',
    articles: [
      {
        id: 'yonhap-bonder',
        source: '연합뉴스',
        at: '2026.09.02 16:05',
        headline: '한미반도체, HBM 본더 수주 잔고 사상 최대',
        saved: false,
      },
      {
        id: 'hankyung-partners',
        source: '한국경제',
        at: '2026.09.02 15:28',
        headline: '장비 협력사 실적 전망 잇단 상향',
        saved: false,
      },
      {
        id: 'etnews-schedule',
        source: '전자신문',
        at: '2026.09.02 14:50',
        headline: '증설 일정과 맞물린 장비 반입 계획',
        saved: false,
      },
    ],
  },

  cowos: {
    eyebrow: 'CURRENT EVENT',
    count: 9,
    asOf: '2026.09.04 13:10 기준',
    summary: '패키징 증설 계획과 고객사 배정, 후공정 병목 해소를 중심으로 보도가 이어지고 있어요.',
    articles: [
      {
        id: 'yonhap-cowos',
        source: '연합뉴스',
        at: '2026.09.04 12:36',
        headline: 'TSMC, CoWoS 생산능력 두 배로 늘린다',
        saved: false,
      },
      {
        id: 'hankyung-alloc',
        source: '한국경제',
        at: '2026.09.04 11:58',
        headline: '고객사별 물량 배정, 하반기 협상 본격화',
        saved: false,
      },
      {
        id: 'etnews-bottleneck',
        source: '전자신문',
        at: '2026.09.04 11:20',
        headline: '후공정 병목 해소 기대와 남은 변수',
        saved: false,
      },
    ],
  },
}

/** Copy for the panel's own furniture, which does not change with the event. */
export const panelCopy = {
  countLabel: (n) => `관련 기사 ${n}개`,
  /* 요약은 펼쳐야 가져온다 — 버튼 문구가 "읽겠다"는 뜻이 되도록 적는다. */
  summaryOpen: 'AI 요약 보기',
  summaryClose: '요약 접기',
  summaryLoading: '요약을 불러오는 중…',
  summaryPending: '다른 곳에서 요약을 만드는 중이에요.',
  summaryNone: '이 기사에는 아직 요약이 없어요.',
  /* 422 — 다시 눌러도 달라지지 않는 쪽이라 실패와 나눠 적는다. */
  summaryUnavailable: '원문 본문이 없어 요약을 만들 수 없어요.',
  summaryFailed: '요약을 만들지 못했어요.',
  summaryRetry: '다시 시도',
  origin: '원문 보러가기',
  close: '닫기',
  open: (n) => `관련 기사 ${n}개 보기`,
  recentre: '이 사건을 가운데로',
  save: '기사 저장',
  unsave: '저장 해제',
  saveNode: '이 사건 즐겨찾기',
  unsaveNode: '즐겨찾기 해제',
  /** 저장 버튼 옆 한 줄. 로그인 없이 누르면 요청 없이 이것만 뜬다. */
  signInToSave: '로그인하면 저장할 수 있어요.',
  saveFailed: '저장하지 못했어요. 다시 시도해 주세요.',
  fieldLabel: '사건 별자리',
  articlesLoading: '관련 기사를 불러오는 중…',
  articlesFailed: '관련 기사를 불러오지 못했어요.',
  articlesEmpty: '아직 이어진 기사가 없어요.',
  more: '더 보기',
}

/** The coordinate space the component's slots are percentages of. */
export const FIELD = { width: 1440, height: 960 }

export const trendCopy = {
  title: '오늘의 트렌드',
  blurb:
    '사건 하나를 가운데 두고, 그 사건과 이어진 사건을 둘러 놓았습니다. 둘레의 별을 누르면 그 사건이 가운데로 옵니다.',
  start: 'samsung',
  trailLabel: '지나온 사건',
  relatedLabel: (n) => `이어진 사건 ${n}개`,
  centreBadge: '지금 보는 사건',
  reset: '처음 사건으로',
  enterFull: '전체화면',
  exitFull: '전체화면 나가기',
  fullHint: 'Esc 로 나가기',
}

/**
 * `lines` is what goes inside the star, broken where it should break — authored rather
 * than measured, the way hero.titleLines and footerMotto already are, because the star
 * has room for two lines of about eight characters and no more. `text` is the whole
 * sentence and is read in the caption under the field.
 */
export const events = [
  {
    id: 'samsung',
    actor: '삼성전자',
    lines: ['HBM4 생산라인', '증설 완료'],
    text: '삼성전자는 HBM4 생산라인 증설을 완료했다',
    date: '9월 8일',
  },
  {
    id: 'nvidia',
    actor: '엔비디아',
    lines: ['차세대 가속기에', 'HBM4 채택'],
    text: '엔비디아는 차세대 AI 가속기에 HBM4 채택을 확정했다',
    date: '9월 8일',
  },
  {
    id: 'hynix',
    actor: 'SK하이닉스',
    lines: ['HBM4 12단', '샘플 공급'],
    text: 'SK하이닉스는 HBM4 12단 샘플을 주요 고객사에 공급했다',
    date: '9월 5일',
  },
  {
    id: 'pyeongtaek',
    actor: '삼성전자 평택',
    lines: ['4공장 클린룸', '공사 재개'],
    text: '삼성전자는 평택 4공장 클린룸 공사를 재개했다',
    date: '8월 27일',
  },
  {
    id: 'hanmi',
    actor: '한미반도체',
    lines: ['HBM 본더 수주', '사상 최대'],
    text: '한미반도체는 HBM용 본더 수주가 사상 최대라고 공시했다',
    date: '9월 2일',
  },
  {
    id: 'tsmc',
    actor: 'TSMC',
    lines: ['CoWoS 패키징', '생산능력 2배'],
    text: 'TSMC는 CoWoS 패키징 생산능력을 두 배로 늘린다고 밝혔다',
    date: '9월 4일',
  },
  {
    id: 'micron',
    actor: '마이크론',
    lines: ['2027년 HBM', '조기 완판'],
    text: '마이크론은 2027년 HBM 물량이 조기 완판됐다고 밝혔다',
    date: '8월 29일',
  },
  {
    id: 'commerce',
    actor: '미국 상무부',
    lines: ['대중국 장비', '수출통제 확대'],
    text: '미국 상무부는 대중국 반도체 장비 수출 통제를 확대했다',
    date: '9월 1일',
  },
  {
    id: 'bok',
    actor: '한국은행',
    lines: ['반도체 수출 회복', '성장률 상향'],
    text: '한국은행은 반도체 수출 회복을 근거로 성장률 전망을 상향했다',
    date: '9월 3일',
  },
  {
    id: 'asml',
    actor: 'ASML',
    lines: ['하이NA EUV', '출하 앞당김'],
    text: 'ASML은 하이NA EUV 장비 출하를 앞당긴다고 밝혔다',
    date: '8월 25일',
  },
  {
    id: 'apple',
    actor: '애플',
    lines: ['AI 서버 메모리', '물량 확대'],
    text: '애플은 자체 AI 서버용 메모리 물량을 늘렸다',
    date: '8월 22일',
  },
  {
    id: 'won',
    actor: '원/달러 환율',
    lines: ['수출 채산성', '개선'],
    text: '원/달러 환율 상승이 반도체 수출 채산성을 끌어올렸다',
    date: '9월 6일',
  },
]

/**
 * Undirected; `from`/`to` only say which end was written first. No event carries more
 * than four relations, which is the most the four slots around a centre can show — if
 * one ever does, the component says how many it is not drawing rather than dropping
 * them silently.
 */
export const relations = [
  { from: 'samsung', to: 'nvidia', label: '수요' },
  { from: 'samsung', to: 'hynix', label: '경쟁' },
  { from: 'samsung', to: 'pyeongtaek', label: '설비' },
  { from: 'samsung', to: 'hanmi', label: '공급망' },
  { from: 'nvidia', to: 'tsmc', label: '패키징' },
  { from: 'nvidia', to: 'hanmi', label: '공급망' },
  { from: 'hynix', to: 'micron', label: '경쟁' },
  { from: 'hynix', to: 'pyeongtaek', label: '증설 경쟁' },
  { from: 'hynix', to: 'won', label: '채산성' },
  { from: 'hanmi', to: 'commerce', label: '규제' },
  { from: 'pyeongtaek', to: 'bok', label: '거시' },
  { from: 'tsmc', to: 'asml', label: '장비' },
  { from: 'tsmc', to: 'apple', label: '수요' },
  { from: 'micron', to: 'apple', label: '수요' },
  { from: 'commerce', to: 'asml', label: '규제' },
  { from: 'bok', to: 'won', label: '환율' },
]
