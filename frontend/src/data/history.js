export const historyOverview = {
  generatedAt: '2026.09.14 00:00',
  periodLabel: '최근 90일',
  totalArticleCount: 126,
  topicCount: 7,
};

const SOURCES = ['연합뉴스', '한국경제', '전자신문'];

const makeEvent = (id, title, articleCount, lastReadAt, at) => ({
  id,
  title,
  articleCount,
  lastReadAt,
  at,
  articles: SOURCES.map((source, index) => ({
    id: `${id}-article-${index + 1}`,
    source,
    readAt: index === 0 ? lastReadAt : `${index + 1}일 전`,
    title: [
      `${title}…핵심 내용과 향후 일정`,
      `${title}, 시장과 현장 반응은`,
      `${title} 관련 쟁점 정리`,
    ][index],
    summary: [
      '사건의 배경과 발표 내용, 앞으로의 일정을 정리한 기사예요.',
      '사건 이후 시장과 업계, 현장에서 나타난 변화를 다뤘어요.',
      '이 사건과 연결된 주요 쟁점과 후속 전망을 설명해요.',
    ][index],
  })),
});

const STORY_POSITIONS = [[19, 25], [81, 26], [50, 80]];
const STORY_ARTICLE_COUNTS = [6, 5, 4];
const STORY_READ_AT = ['어제 22:10', '9월 12일', '9월 10일'];

const storyVariants = {
  POLITICS: [
    ['local-election', '지방선거를 앞둔 정당 재편', ['주요 정당 공천 기준 발표', '지역별 후보군 윤곽', '정책 연대 논의 본격화']],
    ['diplomatic-agenda', '정상외교와 안보 의제', ['한미 정상회담 의제 조율', '다자회의 공동성명 채택', '방산 협력 실무협의 개최']],
  ],
  ECONOMY: [
    ['housing-policy', '주택 공급과 대출 정책 변화', ['수도권 공급 계획 추가 발표', '정책대출 금리 조정', '전세대출 보증 기준 개편']],
    ['export-recovery', '수출 회복과 산업별 온도차', ['반도체 수출 두 자릿수 증가', '자동차 수출 호조 지속', '석유화학 업황 회복 지연']],
  ],
  SOCIETY: [
    ['education-change', '교육과 돌봄 정책 변화', ['늘봄학교 운영 지역 확대', '대학 전형 개선안 발표', '교권 보호 후속 대책 시행']],
    ['climate-safety', '기후재난과 도시 안전', ['집중호우 예보 체계 강화', '지하공간 침수 대책 점검', '폭염 취약계층 지원 확대']],
  ],
  CULTURE: [
    ['performing-arts', '공연 시장의 새로운 성장', ['대형 뮤지컬 관객 기록 경신', '지역 공연장 공동제작 확대', '온라인 공연 유통 실험']],
    ['heritage-return', '문화유산 보존과 환수', ['해외 소재 문화유산 국내 환수', '궁궐 복원 사업 단계 완료', '디지털 문화유산 공개 확대']],
  ],
  WORLD: [
    ['global-election', '주요국 선거 이후 정책 전환', ['새 내각 경제정책 발표', '이민 정책 개편안 공개', '의회 연정 협상 타결']],
    ['energy-order', '에너지 공급망 재편', ['산유국 감산 기조 연장', '유럽 천연가스 비축률 상승', '재생에너지 공동투자 확대']],
  ],
  SPORTS: [
    ['international-games', '국제대회 대표팀의 도전', ['대표팀 최종 엔트리 확정', '해외 전지훈련 일정 발표', '세대교체 선수 활약 주목']],
    ['sports-industry', '스포츠 산업과 중계권 변화', ['프로리그 중계권 계약 갱신', '구단 팬 플랫폼 이용자 증가', '스포츠 데이터 사업 확대']],
  ],
  IT_SCIENCE: [
    ['ai-service', '생성형 AI 서비스 경쟁', ['국내 기업 새 AI 모델 공개', '기업용 AI 도입 사례 증가', 'AI 안전성 평가 기준 마련']],
    ['space-mission', '민간 우주개발의 확장', ['차세대 발사체 시험 성공', '초소형 위성 군집 운용 시작', '달 탐사 장비 개발 착수']],
  ],
};

const makeStory = (id, title, events) => {
  const completeEvents = [
    ...events,
    makeEvent(
      `${id}-followup`,
      `${title}, 후속 대응과 일정 공개`,
      4,
      '9월 9일',
      [31, 72],
    ),
    makeEvent(
      `${id}-outlook`,
      `${title} 관련 시장·현장 전망`,
      3,
      '9월 8일',
      [69, 72],
    ),
  ];

  return {
    id,
    title,
    eventCount: completeEvents.length,
    events: completeEvents,
  };
};

const makeVariantStory = ([id, title, eventTitles]) => makeStory(
  id,
  title,
  eventTitles.map((eventTitle, index) => makeEvent(
    `${id}-event-${index + 1}`,
    eventTitle,
    STORY_ARTICLE_COUNTS[index],
    STORY_READ_AT[index],
    STORY_POSITIONS[index],
  )),
);

const topic = (topicCode, topicName, tone, articleCount, storyId, storyTitle, events) => {
  const primaryStory = makeStory(storyId, storyTitle, events);
  return {
    topicCode,
    topicName,
    tone,
    articleCount,
    story: primaryStory,
    events,
    stories: [
      primaryStory,
      ...storyVariants[topicCode].map(makeVariantStory),
    ],
  };
};

export const historyStories = [
  topic('POLITICS', '정치', 'rose', 18, 'policy-session', '정기국회와 주요 정책 협상', [
    makeEvent('budget-talk', '여야, 내년도 예산안 협상 착수', 7, '오늘 00:31', [19, 25]),
    makeEvent('committee', '상임위별 주요 법안 심사 재개', 6, '어제 19:20', [81, 26]),
    makeEvent('audit-plan', '국정감사 일정과 증인 협의', 5, '9월 11일', [50, 80]),
  ]),
  topic('ECONOMY', '경제', 'gold', 24, 'rate-market', '금리 동결 이후 금융시장 변화', [
    makeEvent('rate-hold', '한국은행, 기준금리 3.25% 동결', 9, '오늘 00:20', [19, 25]),
    makeEvent('won-rate', '원·달러 환율 1,330원대 진입', 8, '어제 21:14', [81, 26]),
    makeEvent('household-loan', '가계대출 증가폭 둔화', 7, '9월 11일', [50, 80]),
  ]),
  topic('SOCIETY', '사회', 'mint', 21, 'medical-change', '의료개혁 협의와 현장 변화', [
    makeEvent('medical-talk', '정부·의료계 후속 협의 재개', 8, '오늘 00:15', [19, 25]),
    makeEvent('regional-care', '지역 필수의료 지원 확대', 7, '어제 20:08', [81, 26]),
    makeEvent('emergency-system', '응급의료 전달체계 개편', 6, '9월 10일', [50, 80]),
  ]),
  topic('CULTURE', '문화', 'peach', 13, 'content-wave', '한국 콘텐츠의 글로벌 확장', [
    makeEvent('festival', '국제영화제 경쟁 부문 발표', 5, '어제 22:10', [19, 25]),
    makeEvent('webtoon', '웹툰 플랫폼 해외 매출 증가', 4, '9월 12일', [81, 26]),
    makeEvent('museum', '국립박물관 야간 개장 확대', 4, '9월 9일', [50, 80]),
  ]),
  topic('WORLD', '국제', 'violet', 17, 'ai-trade-rule', 'AI 규제와 첨단기술 통상 갈등', [
    makeEvent('eu-ai-act', 'EU, AI법 단계적 시행', 6, '어제 23:02', [19, 25]),
    makeEvent('export-control', '미국, 대중 반도체 수출통제 확대', 6, '어제 13:45', [81, 26]),
    makeEvent('japan-chip', '일본, 첨단 반도체 투자 지원', 5, '9월 10일', [50, 80]),
  ]),
  topic('SPORTS', '스포츠', 'cyan', 12, 'season-race', '가을 시즌 순위 경쟁', [
    makeEvent('baseball-rank', '프로야구 상위권 순위 경쟁', 5, '어제 23:11', [19, 25]),
    makeEvent('football-squad', '축구대표팀 소집 명단 발표', 4, '어제 16:40', [81, 26]),
    makeEvent('volleyball', '프로배구 신인 드래프트 실시', 3, '9월 10일', [50, 80]),
  ]),
  topic('IT_SCIENCE', 'IT·과학', 'blue', 21, 'hbm4-chain', 'HBM4 공급망 경쟁', [
    makeEvent('hbm4-line', '삼성전자, HBM4 생산라인 증설', 8, '오늘 00:08', [19, 25]),
    makeEvent('nvidia-adopt', '엔비디아, 차세대 가속기에 HBM4 채택', 7, '어제 18:35', [81, 26]),
    makeEvent('bonder-order', '한미반도체, 본더 수주 사상 최대', 6, '9월 11일', [50, 80]),
  ]),
];

export const historyCopy = {
  title: '나의 기록',
  description: '분야 안의 Story를 보고, 연결된 Event를 선택하면 내가 읽은 기사를 확인할 수 있어요.',
  articles: (count) => `읽은 기사 ${count}개`,
  eventCount: (count) => `Event ${count}개`,
  storyLabel: 'STORY',
  eventLabel: 'EVENT',
  articleLabel: 'ARTICLE',
  openStory: (title) => `${title} Story 강조하기`,
  openEvent: (title) => `${title} 관련 읽은 기사 보기`,
  panelTitle: '내가 읽은 기사',
  panelCount: (count) => `이 Event에서 읽은 기사 ${count}개`,
  close: '닫기',
  sampleNotice: '최근 읽은 기사 3개를 보여드려요.',
  previous: '이전 분야',
  next: '다음 분야',
  page: (current, total) => `${current} / ${total} 페이지`,
  storyPage: (current, total) => `Story ${current} / ${total}`,
  previousStory: '이전 Story',
  nextStory: '다음 Story',
};
