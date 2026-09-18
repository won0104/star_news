/**
 * Copy for the settings overlay — Figma V3 / Overlay / Settings.
 *
 * Structure and wording are the Figma frames'; the palette and type are this project's
 * (tokens.css), which is why nothing here carries a colour. One pane is left — 관심 관리,
 * which is what the top bar's 뉴스 관리 opens.
 *
 * 뺀 것들: 계정 설정(이메일·비밀번호 변경)은 배포 API 에 회원 정보를 바꾸는 엔드포인트가
 * 없어 목업으로만 서 있던 화면이었다. 화면 설정(테마·글자 크기·애니메이션)은 셋 중 둘이
 * 저장만 되고 어디에도 적용되지 않았고, 애니메이션은 utils/motion.js 가 전역으로 끈 상태다.
 * 관심 없음 관리는 자유 입력이라 API(분야 코드 목록)에 넣을 수 없어, 관심 관리 안의 두 번째
 * 목록으로 합쳤다. 필요해지면 그때 다시 넣는다.
 */

export const settingsCopy = {
  title: '설정',
  close: '설정 닫기',
  nav: '설정 항목',
  back: '← 별빛 뉴스로 돌아가기',
  save: '변경사항 저장'
};

export const settingsPanes = [{
  id: 'interest',
  label: '관심 관리'
}, {
  id: 'account',
  label: '계정'
}];

/**
 * 계정 — 지금은 "누구로 로그인했는가"와 회원 탈퇴, 둘뿐이다.
 *
 * 이메일·비밀번호 변경은 API 에 없어 여기 없다. 탈퇴는 `DELETE /users/me` 가 비밀번호
 * 재확인을 요구하므로, 버튼을 누르면 그 자리에 비밀번호 칸이 펼쳐지고 한 번 더 누르게 한다.
 * 되돌릴 수 없는 일이라 두 단계로 나눈 것이고, 두 번째 버튼 문구는 첫 번째와 다르게 써서
 * "같은 버튼을 두 번 눌렀다"가 아니라 "확인했다"로 읽히게 한다.
 */
export const accountPane = {
  eyebrow: 'ACCOUNT',
  title: '계정',
  blurb: '로그인한 계정을 확인하고, 필요하면 탈퇴합니다.',

  whoLabel: '로그인한 계정',
  idLabel: '아이디',
  nicknameLabel: '닉네임',

  withdrawLabel: '회원 탈퇴',
  withdrawHint: '되돌릴 수 없습니다',
  withdrawBlurb: [
    '계정이 비활성화되고 즉시 로그아웃됩니다.',
    '읽은 기록, 북마크, 관심 분야 설정에 더 이상 접근할 수 없습니다.',
    '같은 아이디로는 다시 가입할 수 없습니다.'
  ],
  withdrawOpen: '회원 탈퇴',
  withdrawCancel: '취소',
  passwordLabel: '비밀번호 확인',
  passwordPlaceholder: '현재 비밀번호를 입력하세요',
  passwordRequired: '비밀번호를 입력해 주세요.',
  withdrawConfirm: '탈퇴하기',
  withdrawing: '탈퇴 처리 중…',
  wrongPassword: '비밀번호가 맞지 않아요.',
  alreadyDeleted: '이미 탈퇴한 계정이에요. 로그아웃합니다.',
  sessionExpired: '로그인이 만료됐어요. 다시 로그인한 뒤 시도해 주세요.',
  failed: '탈퇴하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
  done: '탈퇴가 완료됐어요. 첫 화면으로 돌아갑니다.'
};

/**
 * 관심 관리 — 관심 분야와 관심 없는 분야, 둘 다 백엔드 TopicCode 일곱 개 중에서 고른다.
 *
 * 분야 목록은 data/topics.js 의 TOPICS 를 그대로 쓴다(코드가 API 와 같아야 저장이 된다).
 * 예전의 "관심 노드"(자유 입력 키워드)와 자유 입력 비관심은 뺐다 — 서버가 받는 것은 분야
 * 코드 목록뿐이고, 노드 관심은 그래프에서 별을 즐겨찾기하는 것(PATCH /bookmarks/nodes)으로
 * 이미 대신한다.
 */
export const interestPane = {
  eyebrow: 'PREFERENCES · TOPICS',
  title: '관심 관리',
  blurb: '관심 분야는 추천을 넓히고, 관심 없는 분야는 추천에서 덜 보이게 합니다. 바꾸는 즉시 저장됩니다.',

  interestsLabel: '관심 분야',
  interestsHint: '추천 후보를 넓히는 분야입니다',
  dislikesLabel: '관심 없는 분야',
  dislikesHint: '추천에서 덜 보고 싶은 분야입니다',
  count: (n) => `${n}개 선택`,

  /** 같은 분야를 양쪽에 동시에 둘 수 없다. 한쪽을 켜면 다른 쪽에서는 내려온다. */
  exclusive: '관심 분야와 관심 없는 분야는 겹칠 수 없어요. 한쪽을 켜면 다른 쪽에서 빠집니다.',

  loading: '설정을 불러오는 중…',
  signedOut: '로그인하면 관심 분야를 설정할 수 있어요.',
  failed: '설정을 불러오지 못했어요. 잠시 뒤 다시 열어주세요.',
  saving: '저장 중…',
  saved: '저장됨',
  saveFailed: '저장하지 못해 이전 상태로 되돌렸어요.',

  /** 분야 아래 한 줄 — 어디까지가 이 분야인지. 코드 순서는 TOPICS 와 같다. */
  scope: {
    POLITICS: '정부 · 국회 · 정당 · 외교 · 국방',
    ECONOMY: '금융 · 산업 · 부동산 · 고용 · 물가',
    SOCIETY: '사건사고 · 교육 · 노동 · 복지',
    CULTURE: '공연 · 전시 · 도서 · 라이프스타일',
    INTERNATIONAL: '외교 · 글로벌 이슈 · 해외 정세',
    SPORTS: '프로스포츠 · 국가대표 · 리그',
    IT_SCIENCE: '정보기술 · AI · 플랫폼 · 우주'
  }
};
