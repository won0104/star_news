/**
 * 나의 뉴스 세계 — Figma V3 / My World / 02 / 나의 리포트.
 *
 * Copy and figures are the frame's. Field ids match interestPane.topics in
 * data/settings.js, so a 분야 means the same thing here and in 관심 관리.
 */

/**
 * 분야별 탐색 — kept, unplaced. These had a group of their own in the left menu board;
 * the board is gone and where they land has not been decided, so the list is held here
 * rather than deleted and retyped later. Ids match interestPane.topics in
 * data/settings.js, so a 분야 means the same thing here and in 관심 관리.
 *
 * Nothing renders this yet.
 */
export const explore = {
  label: '분야별 탐색',
  fields: [
    { id: 'politics', label: '정치' },
    { id: 'economy', label: '경제' },
    { id: 'society', label: '사회' },
    { id: 'culture', label: '문화' },
    { id: 'world', label: '국제' },
    { id: 'region', label: '지역' },
    { id: 'sports', label: '스포츠' },
    { id: 'tech', label: 'IT · 과학' },
  ],
  soon: '준비 중입니다',
};

/**
 * What each bar destination says while it has no screen. Keyed by navItems id, so an
 * id with a note here and no branch in <ViewPane> still reads as deliberate rather than
 * as a blank pane. Only 나의 기록 is left in it.
 */
export const paneNotes = {
  log: '나의 기록 화면은 아직 붙이지 않았습니다.',
};

/**
 * The four cards. Every figure below is the frame's except the weekly split in
 * `weeks`, which the export could not be read for — text was flattened to outlines and
 * only the bar shapes were legible. Those are reconstructed to reconcile with the rest
 * of the report instead of being eyeballed: the twelve weekly totals sum to the 126
 * articles in `summary`, and each series sums to its own total in `fields` (경제 42,
 * IT·과학 31, 국제 19, and 기타 34 for everything outside the top five). The frame's own
 * bars do not reconcile — they run to about 250 articles against a stated 126 — so they
 * are illustrative, and matching them would have carried that contradiction into the code.
 */
export const report = {
  title: '최근 3개월의 뉴스 리포트',
  summary: '최근 3개월 동안 126개의 기사에서 24개 주제와 18개 출처를 접했어요.',
  summaryAside: '새 주제 4개',

  fields: {
    label: '분야별 읽은 기사',
    hint: '읽은 기록을 큰 분야별로 집계했어요.',
    rows: [
      { id: 'economy', label: '경제', count: 42 },
      { id: 'tech', label: 'IT · 과학', count: 31 },
      { id: 'world', label: '국제', count: 19 },
      { id: 'society', label: '사회', count: 14 },
      { id: 'politics', label: '정치', count: 9 },
    ],
  },

  sources: {
    label: '출처별 읽기 비중',
    hint: '어떤 언론사의 기사를 주로 접했는지 보여줘요.',
    rows: [
      { id: 'yonhap', label: '연합뉴스', share: 24 },
      { id: 'hankyung', label: '한국경제', share: 18 },
      { id: 'hani', label: '한겨레', share: 13 },
      { id: 'etnews', label: '전자신문', share: 10 },
      { id: 'etc', label: '기타', share: 35 },
    ],
    footnote: '상위 두 출처가 전체 읽기 기록의 42%를 차지합니다.',
  },

  weeks: {
    label: '최근 12주의 분야별 읽기 변화',
    hint: '주별 기사 수와 분야 구성이 어떻게 달라졌는지 보여줘요.',
    /** Back to front, so the darkest sits at the base of each column. */
    series: [
      { id: 'economy', label: '경제' },
      { id: 'tech', label: 'IT · 과학' },
      { id: 'world', label: '국제' },
      { id: 'etc', label: '기타' },
    ],
    axisMax: 20,
    ticks: [10, 20],
    /** [경제, IT·과학, 국제, 기타] per week; `month` labels the axis under that column. */
    columns: [
      { month: '6월', values: [2, 2, 1, 1] },
      { values: [3, 2, 1, 1] },
      { values: [3, 2, 1, 2] },
      { values: [3, 2, 1, 3] },
      { month: '7월', values: [3, 2, 1, 3] },
      { values: [3, 3, 2, 2] },
      { values: [4, 2, 2, 2] },
      { values: [4, 3, 2, 2] },
      { month: '8월', values: [4, 3, 2, 3] },
      { values: [4, 3, 2, 4] },
      { values: [4, 4, 2, 4] },
      { values: [5, 3, 2, 7] },
    ],
  },

  terrain: {
    label: '최근 주제 지형',
    hint: '최근 읽은 분야 안에서 주제들이 어떻게 분포했는지 보여드려요.',
    quadrants: {
      topLeft: '새로 살펴볼 흐름',
      topRight: '자주 만난 주요 흐름',
      bottomLeft: '가볍게 스친 흐름',
      bottomRight: '꾸준히 따라본 흐름',
    },
    /** `strong` is the frame's filled, bolder mark — a topic seen often. x/y are %. */
    topics: [
      { id: 'port', label: '항만 물류', x: 25, y: 22, strong: false },
      { id: 'energy', label: '에너지', x: 38, y: 40, strong: false },
      { id: 'semiconductor', label: '반도체', x: 63, y: 22, strong: true },
      { id: 'fx', label: '환율', x: 57, y: 40, strong: true },
      { id: 'localpolicy', label: '지역 정책', x: 43, y: 68, strong: false },
      { id: 'hbm', label: 'HBM', x: 62, y: 68, strong: true },
    ],
    axisX: '가로축 · 내가 접한 정도',
    axisY: '세로축 · 최근 읽은 분야에서 등장한 정도',
  },
};
