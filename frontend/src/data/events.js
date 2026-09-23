/**
 * The event store: one entry per event, holding everything any screen needs about it.
 *
 * Two screens read it and neither owns it. 나를 위한 추천 shows a card per event, and
 * 사건 하나를 통째로 보여주던 /event/:id 가 없어졌다. 아래 값들은 추천 보드가 카드 문구로
 * here once, and data/recommend.js carries only which events are recommended and why.
 * Written the other way round, a card and its own detail page could drift apart.
 *
 * `articles[].lead` is the opening sentence, which is what the side panel can honestly
 * show: there is no full text behind this yet and no URL to send anyone to, so the panel
 * says where the piece came from and how it starts rather than pretending to hold it.
 *
 * Sources are the four in the report's 출처별 읽기 비중 (data/world.js), so the same press
 * names run through every screen.
 *
 * Seed content. A feed replaces this file wholesale; nothing outside it knows the shape
 * of an event beyond the fields below.
 */

const article = (id, source, at, headline, lead, saved = false) => ({
  id,
  source,
  at,
  headline,
  lead,
  saved,
});

export const events = {
  'chip-export': {
    id: 'chip-export',
    title: '반도체 수출 동향',
    summary: '메모리 가격 반등과 수출 회복세가 이어지고 있어요.',
    hashtags: ['#반도체', '#수출', '#메모리가격'],
    asOf: '2026.09.10 09:20 기준',
    articles: [
      article('ce-1', '연합뉴스', '2026.09.10 08:55', '8월 반도체 수출 두 자릿수 증가',
        '관세청은 8월 반도체 수출이 지난해 같은 달보다 18% 늘었다고 밝혔다.', true),
      article('ce-2', '한국경제', '2026.09.10 08:12', '메모리 현물가 3주 연속 상승',
        '서버용 D램 현물 가격이 3주째 오르며 감산 효과가 가격에 반영되고 있다.'),
      article('ce-3', '전자신문', '2026.09.09 17:40', '하반기 출하 계획 상향 조정',
        '주요 메모리사가 하반기 출하 계획을 잇따라 올려 잡았다.'),
    ],
  },

  'bok-rate': {
    id: 'bok-rate',
    title: '한국은행 기준금리 동결',
    summary: '물가와 가계부채 흐름을 지켜보며 금리를 유지했어요.',
    hashtags: ['#기준금리', '#통화정책', '#가계부채'],
    asOf: '2026.09.09 16:40 기준',
    articles: [
      article('br-1', '연합뉴스', '2026.09.09 10:05', '한국은행, 기준금리 연 2.75% 동결',
        '금융통화위원회가 기준금리를 현 수준에서 유지하기로 결정했다.'),
      article('br-2', '한겨레', '2026.09.09 11:30', '"물가와 금융안정 함께 살펴야"',
        '총재는 물가 둔화 흐름과 가계부채 증가세를 함께 보겠다고 말했다.', true),
      article('br-3', '한국경제', '2026.09.09 14:02', '시장은 연내 인하 가능성에 무게',
        '채권시장은 연내 한 차례 인하 가능성을 이미 가격에 반영하고 있다.'),
    ],
  },

  'hbm4-race': {
    id: 'hbm4-race',
    title: 'AI 반도체 경쟁, HBM4',
    summary: '국내 기업들이 차세대 메모리 개발 일정을 앞당기고 있어요.',
    hashtags: ['#HBM4', '#AI반도체', '#메모리'],
    asOf: '2026.09.08 11:20 기준',
    articles: [
      article('hr-1', '연합뉴스', '2026.09.08 11:02', '삼성전자, 평택 HBM4 라인 가동 시작',
        '삼성전자가 평택 4공장의 HBM4 생산라인 증설을 마치고 가동에 들어갔다.', true),
      article('hr-2', '한국경제', '2026.09.08 10:38', 'HBM4 공급 계약, 하반기 실적에 반영',
        '고객사와의 물량 계약이 하반기 실적에 순차적으로 반영될 전망이다.'),
      article('hr-3', '전자신문', '2026.09.08 10:20', '후속 장비 발주 확대와 협력사 수주 전망',
        '증설에 따른 후속 장비 발주가 협력사 수주로 이어질 것으로 보인다.'),
    ],
  },

  'nk-defence': {
    id: 'nk-defence',
    title: '북한 국방 동향',
    summary: '국방 예산과 한미 연합훈련 관련 보도가 이어지고 있어요.',
    hashtags: ['#북한', '#국방예산', '#한미연합훈련'],
    asOf: '2026.09.09 18:05 기준',
    articles: [
      article('nd-1', '연합뉴스', '2026.09.09 17:22', '국방부, 한미 연합훈련 일정 발표',
        '국방부가 하반기 연합훈련의 기간과 규모를 공개했다.'),
      article('nd-2', '한국일보', '2026.09.09 16:48', '내년 국방 예산안, 첨단 전력에 집중',
        '내년 예산안은 무인체계와 감시정찰 자산에 비중을 뒀다.', true),
      article('nd-3', '한겨레', '2026.09.09 15:10', '방산 수출 확대와 후속 지원 과제',
        '수출 확대에 따른 후속 정비와 인력 지원이 과제로 남았다.'),
    ],
  },

  'won-rate': {
    id: 'won-rate',
    title: '원/달러 환율 흐름',
    summary: '환율 상승이 수출 채산성과 물가에 동시에 영향을 주고 있어요.',
    hashtags: ['#환율', '#수출채산성', '#물가'],
    asOf: '2026.09.10 10:15 기준',
    articles: [
      article('wr-1', '한국경제', '2026.09.10 09:40', '원/달러 환율 1,390원대 등락',
        '환율이 1,390원대에서 오르내리며 방향을 찾지 못하고 있다.'),
      article('wr-2', '연합뉴스', '2026.09.10 09:05', '수출기업 채산성은 개선, 수입물가는 부담',
        '같은 환율이 수출과 수입에 반대로 작용하고 있다는 분석이다.'),
      article('wr-3', '한겨레', '2026.09.09 19:20', '외환당국 "쏠림에는 대응"',
        '당국은 한쪽으로 치우친 움직임에는 조치하겠다는 입장을 밝혔다.'),
    ],
  },

  'house-debt': {
    id: 'house-debt',
    title: '가계부채 관리 방안',
    summary: '대출 한도 산정 방식이 바뀌며 실수요자 영향이 논의되고 있어요.',
    hashtags: ['#가계부채', '#DSR', '#주택담보대출'],
    asOf: '2026.09.08 17:30 기준',
    articles: [
      article('hd-1', '연합뉴스', '2026.09.08 16:50', '금융위, 가계부채 관리 방안 발표',
        '금융위원회가 대출 한도 산정 기준을 조정하는 방안을 내놨다.'),
      article('hd-2', '한국경제', '2026.09.08 17:05', '실수요자 예외 범위가 쟁점',
        '생애최초와 이주 수요를 어디까지 예외로 둘지가 쟁점으로 떠올랐다.'),
      article('hd-3', '한겨레', '2026.09.08 18:12', '은행권 대출 창구 혼선 우려',
        '시행 시점이 촉박해 창구 혼선이 우려된다는 지적이 나왔다.'),
    ],
  },

  'ev-battery': {
    id: 'ev-battery',
    title: '전기차 배터리 수요 둔화',
    summary: '완성차 재고 조정으로 배터리 주문이 미뤄지고 있어요.',
    hashtags: ['#전기차', '#배터리', '#수요둔화'],
    asOf: '2026.09.07 15:00 기준',
    articles: [
      article('eb-1', '전자신문', '2026.09.07 14:20', '배터리 3사 3분기 가동률 하락',
        '국내 배터리 3사의 3분기 가동률이 나란히 내려갔다.'),
      article('eb-2', '한국경제', '2026.09.07 13:35', '완성차 재고 조정에 주문 이연',
        '완성차의 재고 조정이 배터리 주문 이연으로 이어지고 있다.'),
      article('eb-3', '연합뉴스', '2026.09.06 18:40', '보조금 개편이 수요에 미칠 영향',
        '내년 보조금 개편안이 수요 회복 시점을 가를 변수로 꼽힌다.'),
    ],
  },

  'shipbuilding': {
    id: 'shipbuilding',
    title: '조선 수주 잔량 최고',
    summary: '친환경 선박 발주가 이어지며 수주 잔량이 최고 수준이에요.',
    hashtags: ['#조선', '#수주잔량', '#친환경선박'],
    asOf: '2026.09.06 11:45 기준',
    articles: [
      article('sb-1', '연합뉴스', '2026.09.06 11:10', '국내 조선 수주 잔량 3년 최고',
        '국내 조선사의 수주 잔량이 3년 만에 가장 많은 수준에 이르렀다.'),
      article('sb-2', '한국경제', '2026.09.06 10:25', 'LNG선 중심의 고부가 물량',
        '수익성이 높은 LNG 운반선이 잔량의 중심을 이루고 있다.'),
      article('sb-3', '전자신문', '2026.09.05 17:55', '인력 확보가 납기의 관건',
        '숙련 인력 확보가 납기를 지키는 관건으로 지목됐다.'),
    ],
  },

  'ai-rule': {
    id: 'ai-rule',
    title: 'AI 규제 논의',
    summary: '고위험 인공지능의 범위와 사업자 의무를 두고 논의가 이어지고 있어요.',
    hashtags: ['#AI규제', '#고위험AI', '#가이드라인'],
    asOf: '2026.09.05 16:20 기준',
    articles: [
      article('ar-1', '한겨레', '2026.09.05 15:40', '고위험 AI 범위 어디까지',
        '어떤 서비스를 고위험으로 볼지에 따라 의무의 무게가 달라진다.'),
      article('ar-2', '전자신문', '2026.09.05 14:55', '사업자 설명 의무 신설 검토',
        '이용자에게 판단 근거를 설명할 의무를 두는 방안이 검토된다.'),
      article('ar-3', '연합뉴스', '2026.09.04 18:30', '산업계 "예측 가능성 필요"',
        '산업계는 기준이 먼저 분명해져야 한다는 입장을 냈다.'),
    ],
  },

  'semi-equip': {
    id: 'semi-equip',
    title: '반도체 장비 수출 통제',
    summary: '장비 수출 통제가 확대되며 공급망 재편이 빨라지고 있어요.',
    hashtags: ['#수출통제', '#반도체장비', '#공급망'],
    asOf: '2026.09.04 13:10 기준',
    articles: [
      article('se-1', '연합뉴스', '2026.09.04 12:30', '미국, 대중국 장비 통제 품목 추가',
        '미국 상무부가 통제 품목에 후공정 장비 일부를 더했다.'),
      article('se-2', '전자신문', '2026.09.04 11:50', '국내 장비사 우회 수요 반사이익',
        '통제 밖 품목을 다루는 국내 장비사에 반사이익이 예상된다.'),
      article('se-3', '한국경제', '2026.09.03 19:05', '고객사 생산 계획 조정 불가피',
        '중국 내 생산 계획을 둔 고객사는 일정 조정이 불가피해졌다.'),
    ],
  },
};

/** Copy the event page and its side panel share. */
export const eventCopy = {
  eyebrow: 'EVENT',
  summaryLabel: '요약',
  tagsLabel: '해시태그',
  articlesLabel: '관련 기사',
  // No direction in it: the panel opens on the right on a wide screen and covers the
  // whole stage on a narrow one, so naming a side would be wrong half the time.
  articlesHint: '이 사건을 다룬 기사예요. 하나를 누르면 자세히 보여드려요.',
  countLabel: (n) => `기사 ${n}건`,
  openArticle: '자세히 보기',
  panelLabel: '뉴스 상세',
  close: '닫기',
  save: '기사 저장',
  unsave: '저장 해제',
  leadLabel: '기사 요약',
  origin: '원문 기사 보기',
  sourceNote: '전문은 원문 매체에서 확인할 수 있어요.',
  back: '← 추천으로',
  notFound: '아직 준비되지 않은 사건이에요.',
};
