/** Home — a single full-bleed photo with the site chrome over it. */

export const brand = {
  name: '별빛 뉴스',
  section: '나를 위한 추천'
};
export const navItems = [{
  id: 'foryou',
  label: '나를 위한 추천'
}, {
  id: 'trend',
  label: '오늘의 트렌드'
}, {
  id: 'saved',
  label: '저장됨'
}, {
  id: 'history',
  label: '나의 기록'
}];
export const authActions = {
  signIn: '로그인',
  signUp: '회원가입'
};

/** The photograph behind every screen. Replace the file at this path to swap it. */
export const backdrop = {
  src: '/assets/home/backdrop.png'
};

/**
 * Real photographed props (not CSS/SVG), used to make the auth card read as a
 * physical paper pinned to the wall rather than a flat UI panel.
 */
export const deskProps = {
  paperTile: '/assets/home/paper-tile.png',
  paperOverlay: '/assets/home/paper-overlay.png',
  clipFront: '/assets/home/clip-front.png',
  clipAngle: '/assets/home/clip-angle.png'
};
