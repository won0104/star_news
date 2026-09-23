/** Home — a single full-bleed photo with the site chrome over it. */

export const brand = {
  name: '별빛 뉴스',
  section: '나를 위한 추천',
}
/**
 * The bar's destinations. These were two levels until the left menu board was removed —
 * 홈 and 나의 뉴스 세계 in the board, each with a two-tab strip inside its pane — and the
 * leaves are now flat in the bar, so a screen is one click from any other instead of
 * two. `id` is what <AppScene> switches on and what `?view=` carries.
 */
export const navItems = [
  {
    id: 'trend',
    label: '오늘의 트렌드',
  },
  {
    id: 'foryou',
    label: '나를 위한 추천',
  },
  {
    id: 'log',
    label: '나의 기록',
  },
]

/**
 * Screens that `?view=` can carry but the bar does not list; see <AppScene>, which
 * accepts both lists.
 */
export const extraViews = [
  {
    id: 'report',
    label: '나의 리포트',
  },
]
export const authActions = {
  signIn: '로그인',
  signUp: '회원가입',
}

/**
 * The account menu behind the avatar, once someone is signed in. Each `id` is a pane in
 * the settings overlay (data/settings.js `settingsPanes`), so an entry here opens that
 * overlay on that pane — 뉴스 관리 opens 관심 관리. `signOut` is kept out of the list
 * because it is not a place to go: it ends the session.
 */
export const accountMenu = {
  label: '계정 메뉴',
  unknownUser: '내 계정',
  items: [
    {
      id: 'interest',
      label: '뉴스 관리',
    },
    {
      id: 'account',
      label: '계정',
    },
  ],
  signOut: '로그아웃',
  signingOut: '로그아웃 중…',
  signOutFailed: '로그아웃하지 못했어요. 잠시 후 다시 시도해 주세요.',
}

/**
 * 햇살 든 방 — 현관, 로그인·회원가입, 기사 상세가 함께 서 있는 한 방.
 *
 * 비율마다 한 장씩 그려져 있다. 사진은 cover 로 깔리므로 어느 비율에서도 화면을 덮지만,
 * 비율이 멀수록 창과 소파, 화분처럼 모서리에 놓인 것들이 잘려 나간다 — 책상·보드·창틀과
 * 같은 방식으로 가장 가까운 장을 고른다(useNearestWindow).
 *
 * 파일이 /assets/auth 에 있는 것은 이 방이 로그인 화면용으로 먼저 그려졌기 때문이고, 지금은
 * 세 화면이 같은 장을 쓴다.
 */
export const rooms = [
  { ratio: 1672 / 941, src: '/assets/auth/room-16x9-v2.webp' },
  { ratio: 1448 / 1086, src: '/assets/auth/room-4x3-v2.webp' },
  { ratio: 1086 / 1448, src: '/assets/auth/room-3x4-v2.webp' },
  { ratio: 941 / 1672, src: '/assets/auth/room-9x16-v2.webp' },
]

/**
 * 그 방을 장면으로 세운 것. `id` 는 <PhotoBackdrop> 이 CSS 를, <AppScene> 이 컴포넌트를
 * 키잉하는 값이다. `src` 가 없으므로 <PhotoBackdrop> 이 위 목록에서 비율에 맞는 장을 고른다.
 */
export const backdrop = {
  id: 'home',
  /**
   * 일러스트 방에는 짝이 되는 클립이 아직 없다.
   *
   * 예전 사진풍 스틸(assets/home/backdrop.png)에는 같은 방을 찍은 10초 클립이 있었고, 그
   * 마지막 프레임이 스틸과 34.8dB 로 맞아 넘김이 컷으로 읽히지 않았다. 방을 일러스트로 바꾸면
   * 그 짝이 깨진다 — 사진풍 클립이 끝나면서 일러스트로 넘어가면 전혀 다른 방으로 점프한다.
   * 클립을 다시 그리기 전까지는 움직임 없이 스틸만 선다.
   *
   * 그 스틸과 클립, 그리고 둘의 노출 차를 되돌리던 .loopHome 보정은 함께 내렸다. 되살릴
   * 일이 있으면 git 히스토리에 있지만, 일러스트 방에는 새 클립과 새 측정이 필요하다.
   */
  loop: null,
}

/**
 * Real photographed props (not CSS/SVG), used to make the auth card read as a
 * physical paper pinned to the wall rather than a flat UI panel.
 */
export const deskProps = {
  paperTile: '/assets/home/paper-tile.png',
  paperOverlay: '/assets/home/paper-overlay.png',
  clipFront: '/assets/home/clip-front.png',
  clipAngle: '/assets/home/clip-angle.png',
}
