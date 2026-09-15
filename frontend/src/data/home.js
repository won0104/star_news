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
    id: 'report',
    label: '나의 리포트',
  },
]

/**
 * Screens that `?view=` can carry but the bar does not list. 나의 기록 is reached from
 * 오늘의 트렌드's constellation instead, so it needs to stay a legal view without taking
 * a fourth seat in the bar — see <AppScene>, which accepts both lists.
 */
export const extraViews = [
  {
    id: 'log',
    label: '나의 기록',
  },
  {
    id: 'foryou2',
    label: '나를 위한 추천 비교안',
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
  items: [
    {
      id: 'account',
      label: '계정설정',
    },
    {
      id: 'interest',
      label: '뉴스 관리',
    },
    {
      id: 'display',
      label: '화면설정',
    },
  ],
  signOut: '로그아웃',
}

/**
 * The sunlit room: the scene behind the front door, the auth screens, and every app
 * destination but 나를 위한 추천. `id` is what <PhotoBackdrop> keys its CSS off and what
 * <AppScene> keys the component itself off.
 */
export const backdrop = {
  id: 'home',
  src: '/assets/home/backdrop.png',
  /**
   * The same room in motion — 10 silent seconds the home screen fades in over the still
   * above, plays once, and fades back off. The clip's own last frame matches that still
   * closely (34.8dB measured, once the exposure correction in PhotoBackdrop.module.css
   * is applied), so the hand-back does not read as a cut; the still is also the sharper
   * picture, at 1672x941 against the clip's 1280x720.
   *
   * webm first, mp4 for Safari; re-encode with scripts/encode-clip.ps1. Files
   * in public/ carry no content hash, so a replacement needs a new name
   * (backdrop-loop-v2) or a CDN will keep handing out the old bytes.
   */
  loop: {
    webm: '/assets/home/backdrop-loop.webm',
    mp4: '/assets/home/backdrop-loop.mp4',
  },
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
