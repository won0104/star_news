/**
 * 나의 뉴스 세계 — Figma V3 / My World / 02 / 나의 리포트.
 *
 * Copy and figures are the frame's. Field ids match interestPane.topics in
 * data/settings.js, so a 분야 means the same thing here and in 관심 관리.
 */

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
/** 저장한 것들 화면의 문구. */
export const savedCopy = {
  events: {
    title: '저장한 사건',
    blurb: '즐겨찾기한 사건입니다. 왼쪽에서 자세히 볼 수 있어요.',
    empty: '여기는 아직 비어 있어요.',
    emptyHint:
      '별자리에서 사건에 ★ 을 달아 두면 여기 모입니다. 며칠 뒤에 다시 와도 그 사건이 어떻게 이어졌는지 따라갈 수 있어요.',
  },
  articles: {
    title: '저장한 기사',
    blurb: '북마크한 기사입니다. 왼쪽에서 요약을 볼 수 있어요.',
    empty: '여기는 아직 비어 있어요.',
    emptyHint:
      '읽다가 남겨 두고 싶은 기사에 책갈피를 꽂아 두면 여기 모입니다. 언제든 다시 꺼내 읽을 수 있어요.',
  },
  signedOut: '로그인하면 저장한 항목을 볼 수 있어요.',
  signedOutHint: '북마크는 계정에 저장됩니다.',
  loading: '불러오는 중…',
  failed: '불러오지 못했어요.',
  more: '더 보기',
  savedAt: (at) => `${at} 저장`,
  pickOne: '오른쪽에서 하나를 선택해 보세요.',
  unsave: '북마크 해제',
  unsaveFailed: '북마크를 해제하지 못했어요.',
  relatedArticles: '관련 기사',
  openTrend: '오늘의 트렌드에서 보기 →',
  origin: '원문 보러가기',
  summaryNone: '이 기사에는 아직 요약이 없어요.',
  summaryPending: '요약을 만드는 중이에요.',
  summaryFailed: '요약을 만들지 못했어요.',
  // 422 ARTICLE_CONTENT_UNAVAILABLE — 다시 눌러도 달라지지 않는 쪽이라 실패와 나눠 적는다.
  summaryUnavailable: '원문 본문이 없어 요약을 만들 수 없어요.',
}
