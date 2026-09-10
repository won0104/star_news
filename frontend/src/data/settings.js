/**
 * Copy for the settings overlay — Figma V3 / Overlay / Settings.
 *
 * Structure and wording are the Figma frames'; the palette and type are this project's
 * (tokens.css), which is why nothing here carries a colour. The four panes are the
 * frame's own rail order, and `interest` is what the top bar's 뉴스 관리 opens.
 */

export const settingsCopy = {
  title: '설정',
  close: '설정 닫기',
  nav: '설정 항목',
  back: '← 별빛 뉴스로 돌아가기',
  save: '변경사항 저장'
};

export const settingsPanes = [{
  id: 'account',
  label: '계정 설정'
}, {
  id: 'interest',
  label: '관심 관리'
}, {
  id: 'dislikes',
  label: '관심 없음 관리'
}, {
  id: 'display',
  label: '화면 설정'
}];

/**
 * 계정 설정 — Figma V3 / Overlay / Settings / Account.
 *
 * Only the two changes that were asked for. No eyebrow: the Interest frame has one and
 * the Dislikes frame does not, so it is per-pane, and this frame's own header has not
 * been read. Better absent than invented.
 */
export const accountPane = {
  title: '계정 설정',
  blurb: '로그인에 쓰는 이메일과 비밀번호를 바꿉니다.',

  emailLabel: '이메일 변경',
  emailHint: '브리핑과 계정 알림을 받을 주소입니다',
  emailField: '새 이메일',
  emailPlaceholder: 'you@example.com',
  emailSubmit: '이메일 변경',
  emailDone: '이메일을 변경했습니다.',

  passwordLabel: '비밀번호 변경',
  passwordHint: '8자 이상으로 정합니다',
  currentField: '현재 비밀번호',
  currentPlaceholder: '현재 비밀번호를 입력하세요',
  nextField: '새 비밀번호',
  nextPlaceholder: '8자 이상 입력하세요',
  confirmField: '새 비밀번호 확인',
  confirmPlaceholder: '새 비밀번호를 다시 입력하세요',
  passwordSubmit: '비밀번호 변경',
  passwordDone: '비밀번호를 변경했습니다.',
  currentRequired: '현재 비밀번호를 입력해 주세요.',
  sameAsCurrent: '현재 비밀번호와 다른 비밀번호를 입력해 주세요.',
  failed: '변경에 실패했습니다. 잠시 후 다시 시도해 주세요.'
};

/** 관심 관리 — Figma V3 / Overlay / Settings / Interest. */
export const interestPane = {
  eyebrow: 'PREFERENCES · INTEREST',
  title: '관심 관리',
  blurb: '관심 토픽은 추천의 범위를, 관심 노드는 그래프에서 이어볼 키워드를 정합니다.',

  topicsLabel: '관심 토픽',
  topicsHint: '추천 후보를 넓히는 분야입니다',
  topicsCount: (n) => `${n}개 선택`,
  topics: [{
    id: 'politics',
    label: '정치',
    scope: '정부 · 국회 · 정당 · 외교 · 국방'
  }, {
    id: 'economy',
    label: '경제',
    scope: '금융 · 산업 · 부동산 · 고용 · 물가'
  }, {
    id: 'society',
    label: '사회',
    scope: '사건사고 · 교육 · 노동 · 복지'
  }, {
    id: 'culture',
    label: '문화',
    scope: '공연 · 전시 · 도서 · 라이프스타일'
  }, {
    id: 'world',
    label: '국제',
    scope: '외교 · 글로벌 이슈 · 해외 정세'
  }, {
    id: 'region',
    label: '지역',
    scope: '지자체 · 지역개발 · 교통 · 행정'
  }, {
    id: 'sports',
    label: '스포츠',
    scope: '프로스포츠 · 국가대표 · 리그'
  }, {
    id: 'tech',
    label: 'IT · 과학',
    scope: '정보기술 · AI · 플랫폼 · 우주'
  }],

  nodesLabel: '관심 노드',
  nodesHint: '그래프에서 이어볼 키워드입니다',
  nodesCount: (n) => `${n}개 등록`,
  nodePlaceholder: '인물 · 기업 · 기관 · 개념을 입력하세요',
  nodeAdd: '추가',
  suggestedLabel: '읽은 기사에서 추출됨',
  suggested: ['기준금리', '국정조사특위', '생성형 AI', '항만 물류'],
  nodeRemove: '관심 노드에서 제거',
  /** Reads as "읽은 기사 12건 · 연결 개념 8" under each node. */
  nodeMeta: (articles, concepts) => `읽은 기사 ${articles}건 · 연결 개념 ${concepts}`
};

/**
 * Node kinds carry the graph view's own dot colours (--entity-color and friends), so a
 * keyword kept here is the same colour when you meet it again on /explore.
 */
export const nodeKinds = {
  organisation: {
    label: '기관',
    tone: 'entity'
  },
  concept: {
    label: '개념',
    tone: 'topic'
  },
  company: {
    label: '기업',
    tone: 'story'
  }
};

/**
 * 화면 설정 — Figma V3 / Overlay / Settings / Display.
 *
 * Three controls. Only the last one is connected to anything: see the note on each.
 */
export const displayPane = {
  eyebrow: 'PREFERENCES · DISPLAY',
  title: '화면 설정',
  blurb: '보기 편한 쪽으로 화면을 맞춥니다.',

  themeLabel: '화면 테마',
  themeHint: '방의 밝기를 정합니다',
  themes: [{
    id: 'light',
    label: '밝게'
  }, {
    id: 'dark',
    label: '어둡게'
  }],
  themePending: '어두운 팔레트가 아직 없어 선택만 저장됩니다.',

  textSizeLabel: '글자 크기',
  textSizeHint: '본문과 카드 글자에 적용됩니다',
  textSizes: [{
    id: 'default',
    label: '보통'
  }, {
    id: 'large',
    label: '크게'
  }],
  textSizePending: '화면들이 아직 고정 px로 짜여 있어 선택만 저장됩니다.',

  motionLabel: '애니메이션 없애기',
  motionHint: '배경 영상을 재생하지 않습니다. OS의 “동작 줄이기”가 켜져 있으면 이 설정과 무관하게 이미 멈춰 있습니다.',
  motionState: (off) => (off ? '켜짐' : '꺼짐')
};

/** 관심 없음 관리 — Figma V3 / Overlay / Settings / Dislikes. */
export const dislikesPane = {
  title: '관심 없음 관리',
  blurb: '추천에서 덜 보고 싶은 분야와 주제를 관리합니다.',

  addLabel: '관심 없음 항목 추가',
  addPlaceholder: '분야 또는 주제를 입력하세요',
  addSubmit: '추가',

  listLabel: '등록된 항목',
  listCount: (n) => `${n}개`,
  listEmpty: '등록된 항목이 없습니다.',
  itemNote: '추천 후보에서 제외 예정',
  itemRemove: '목록에서 제거',

  /** Two lines in the frame, kept as two so the box breaks where it does there. */
  notice: [
    '추가하거나 제거한 내용은 저장 후 추천에 반영됩니다.',
    '읽지 않았다는 이유만으로 자동 등록되지 않습니다.'
  ]
};
