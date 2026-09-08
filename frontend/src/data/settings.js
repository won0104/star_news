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
 * Only the two changes that were asked for. The eyebrow follows the Interest frame's
 * `PREFERENCES · <PANE>` shape rather than a word of my own, since I have not read
 * this frame's own header.
 */
export const accountPane = {
  eyebrow: 'PREFERENCES · ACCOUNT',
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

/** Panes that exist as Figma frames but are not built here yet. */
export const paneStub = {
  note: (label) => `${label} 화면은 아직 붙이지 않았습니다.`
};
