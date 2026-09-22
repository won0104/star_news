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
/**
 * 나의 리포트의 세 페이지. 오른쪽 가장자리 책갈피가 이 목록이다 — 나의 기록이 카테고리
 * 책갈피로 오른쪽 페이지를 바꾸는 것과 같은 조작이다.
 */
export const reportTabs = [
  { id: 'report', label: '리포트' },
  { id: 'articles', label: '저장한 기사' },
]

/**
 * 리포트가 차트 대신 보여줄 한 줄들.
 *
 * 리포트는 내가 읽은 기록을 집계한 것이라 로그인 없이는 만들 수 없다. 그래서 비로그인과
 * 세션 만료를 한 문구로 묶지 않는다 — 전자는 아직 시작하지 않은 것이고, 후자는 하던 것이
 * 끊긴 것이라 사용자가 할 일이 다르다.
 */
export const reportCopy = {
  title: '나의 리포트',
  loading: '리포트를 집계하는 중…',
  signedOut: '로그인하면 최근 3개월의 읽기 기록을 정리해 드려요.',
  expired: '로그인이 만료됐어요. 다시 로그인하면 이어서 볼 수 있어요.',
  failed: '리포트를 불러오지 못했어요. 잠시 뒤 다시 시도해주세요.',
  signIn: '로그인하러 가기',
}

const SAVED_PRESS = ['연합뉴스', '한국경제', '전자신문', '한겨레', '머니투데이']

/**
 * 저장한 기사 표본 — `GET /users/me/bookmarks/articles` 응답 형태.
 *
 * CursorResponse<ArticleBookmarkItem>: `{ items, hasNext, nextCursor }`, 각 항목은
 * `{ articleId, title, publisher, publishedAt, summary, bookmarkedAt }`.
 *
 * 화면을 비워두지 않기 위한 것이고, 실제 북마크가 있으면 쓰이지 않는다. 목록이 스크롤되는지
 * 보려면 한 화면보다 길어야 해서 아홉 건을 둔다. `hasNext` 는 false — 다음 쪽을 가져올
 * 수 없는데 있다고 하면 눌러도 실패하는 버튼이 생긴다.
 */
export const savedArticlesSample = {
  items: [
    ['SK하이닉스, HBM3E 수율 80% 근접', '수율 발언 이후 주가가 20만 원을 돌파했고, 기술 자신감과 무리수라는 평가가 엇갈리고 있다.'],
    ['한국은행, 기준금리 3.50% 8차례 연속 동결', '물가가 5개월 연속 3%대에 머무르는 가운데 인하 압력과 물가 불확실성이 맞섰다.'],
    ['엔비디아, 차세대 가속기에 HBM4 채택', '공급망 재편이 예상되며 국내 메모리 업계의 수주 경쟁이 본격화되고 있다.'],
    ['유니테스트, SK하이닉스와 검사장비 공급 계약', '테스트 공정 수요가 늘며 후공정 장비업체에 대한 관심이 커졌다.'],
    ['원·달러 환율 1,330원대 진입', '수출 채산성과 물가에 동시에 영향을 주는 구간으로 들어섰다.'],
    ['미국, 대중 반도체 수출통제 확대', '허가 요건이 추가로 넓어지며 장비·소재 기업의 대응이 갈리고 있다.'],
    ['여야, 내년도 예산안 협상 착수', '법정 기한 내 처리를 목표로 상임위별 심사 일정이 조율되고 있다.'],
    ['EU, AI법 단계적 시행', '고위험 영역부터 적용되며 국내 기업의 준비 상황이 점검되고 있다.'],
    ['한미반도체, 본더 수주 사상 최대', 'HBM 생산 확대에 따라 연간 수주가 최고치를 기록했다.'],
  ].map(([title, rawSummary], i) => ({
    articleId: 940001 + i,
    title,
    publisher: SAVED_PRESS[i % SAVED_PRESS.length],
    publishedAt: `2026-09-${String(16 - i).padStart(2, '0')}T09:${String(10 + i * 5).padStart(2, '0')}:00+09:00`,
    summary: i === 4 || i === 7 ? null : rawSummary,
    bookmarkedAt: `2026-09-${String(16 - Math.floor(i / 2)).padStart(2, '0')}T21:00:00+09:00`,
    // 상세 응답이 붙기 전까지 왼쪽 페이지가 쓸 값. example.com 은 IANA 예약 도메인이라
    // 진짜 기사로 오해될 수 없다 — 표본이라는 사실이 주소에도 남는다.
    originalUrl: `https://example.com/articles/${940001 + i}`,
    summaryStatus: i === 4 ? 'NOT_REQUESTED' : i === 7 ? 'PROCESSING' : 'COMPLETED',
  })),
  hasNext: false,
  nextCursor: null,
}

/** 저장한 것들 화면의 문구. */
export const savedCopy = {
  events: {
    title: '저장한 사건',
    blurb: '즐겨찾기한 사건입니다. 왼쪽에서 자세히 볼 수 있어요.',
    empty: '아직 저장한 사건이 없어요.',
    emptyHint: '별자리에서 사건을 즐겨찾기하면 여기에 모입니다.',
  },
  articles: {
    title: '저장한 기사',
    blurb: '북마크한 기사입니다. 왼쪽에서 요약을 볼 수 있어요.',
    empty: '아직 저장한 기사가 없어요.',
    emptyHint: '기사 목록에서 북마크하면 여기에 모입니다.',
  },
  signedOut: '로그인하면 저장한 항목을 볼 수 있어요.',
  signedOutHint: '북마크는 계정에 저장됩니다.',
  loading: '불러오는 중…',
  failed: '불러오지 못했어요.',
  more: '더 보기',
  savedAt: (at) => `${at} 저장`,
  pickOne: '오른쪽에서 하나를 선택해 보세요.',
  relatedArticles: '관련 기사',
  openTrend: '오늘의 트렌드에서 보기 →',
  sampleNote: '표본 데이터 · 저장한 기사 없음',
  origin: '원문 보러가기',
  summaryNone: '이 기사에는 아직 요약이 없어요.',
  summaryPending: '요약을 만드는 중이에요.',
  summaryFailed: '요약을 만들지 못했어요.',
  // 422 ARTICLE_CONTENT_UNAVAILABLE — 다시 눌러도 달라지지 않는 쪽이라 실패와 나눠 적는다.
  summaryUnavailable: '원문 본문이 없어 요약을 만들 수 없어요.',
}

export const report = {
  title: '최근 3개월의 뉴스 리포트',
  summary: '최근 3개월 동안 126개의 기사에서 24개 주제와 18개 출처를 접했어요.',
  summaryAside: '새 주제 4개',

  /**
   * The three figures `summary` states, pulled out so the diary can set them as numbers
   * rather than re-parsing a sentence. Same values, no new claims: `articles` is also
   * what the twelve weekly columns sum to, while `topics` and `sources` are the frame's
   * own counts and are not broken down anywhere below.
   */
  totals: [
    { id: 'articles', label: '읽은 기사', value: 126 },
    { id: 'topics', label: '만난 주제', value: 24 },
    { id: 'sources', label: '접한 출처', value: 18 },
  ],

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
