import { historyGraphMock } from './historyGraphMock.js';

/**
 * 나의 기록의 책상.
 *
 * 사진은 <PhotoBackdrop> 이 cover 로 깔므로 어느 비율에서도 화면을 덮지만, 비율이 멀수록
 * 커피잔과 사진, 별자리 도판처럼 모서리에 놓인 것들이 잘려 나간다. 그래서 비율별로 한 장씩
 * 두고 가장 가까운 것을 고른다 — 나를 위한 추천의 보드, 오늘의 트렌드의 창틀과 같은 방식.
 *
 * 책은 이 사진 위 좌표에 놓이지 않고 자기 상자를 갖는다. 그래서 책상만 갈아끼워도 책과
 * 탭은 움직이지 않는다.
 */
/**
 * 비율마다 한 장씩. `standIn` 은 그 사진이 도착하기 전 같은 자리에 까는 축소판이다 —
 * 긴 변 56px, webp 0.72, 1KB 남짓이고 번들에 실려 오므로 요청이 늘지 않는다.
 *
 * 없으면 공용 크림색(.wash)이 깔렸다가 사진이 덮으면서 새로고침마다 한 번 번쩍인다. 사진과
 * 스탠드인을 같은 항목에 두어, 비율이 바뀌어도 둘이 갈라지지 않는다.
 *
 * 다시 뽑으려면 scripts/make-standins.html 을 개발 서버 주소로 연다.
 */
export const desks = [
  { ratio: 1672 / 941, src: '/assets/history/desk-16x9-v2.webp', standIn: 'data:image/webp;base64,UklGRpYDAABXRUJQVlA4WAoAAAAgAAAANwAAHwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggqAEAANAJAJ0BKjgAIAA+lUSaSqWjoiGoGAwAsBKJQBXKsbqL0Pe5mNpbLGigOoMHM8WVV1k6pDZrC8hpG/KS4HsDozbqfbwL72s9bQV43St39ugqzvYLnkBTYADMezw4nQfYLxU7ma84iCO3+QLyfPh7YW0jU2Zd6aiPD3wq9dIqJeLCalwdUbtEafW9BIBXZSxmZ36QvVemZbLbuI36FSqlUgr/zYij39Ypb9xZWFD9siY/iEG4AmKMAU7WBlNjzqhisl225E8MSYyPm0MZW8M3bIhsbirJG7W1JKRzVI896rUDp6+IVaxE3u0xUHXAzQyX5nZX4XJc36+6AaZGD6dmI+qb8yfesIVAdip9NdGSZj9n4F4MqWJUsLPTxlCQDiuk+fq7zg0GYtHqA4D/VTY0H2ztNzxCvEIPQZGw1dJeEheIBzfZUpQ6WfyEaq8O21yz51XnbCQIRgPvdS1Q6rcdY8iYPAO7ewmlwRriAcUMGtsQmqBVACBqdkufdwcCe07oaDLeApzCeRmCX++X9dmDEhqlPxb27pc/Qd3RtYsFAAPynA1BTmWAAAA=' },
  { ratio: 1448 / 1086, src: '/assets/history/desk-4x3-v2.webp', standIn: 'data:image/webp;base64,UklGRmgEAABXRUJQVlA4WAoAAAAgAAAANwAAKQAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggegIAANAMAJ0BKjgAKgA+lUaZSiWkIiGoGqxwsBKJQBWHPYt3xuKYDNn8NlZolutSFT/1HNzfPotfMQjQTZB4PN+BpYoWQI+PyX+88y2cJl7tqmmOZFHry5N5Gx17dpWtV7k95vLn5k/x4ZfNTPYQfee4AADZolTyyALkMLto88RfFOkajBFFf25NRXYnpOgulykq8EbORXh2ltp1nITJ71FNP1L0ceztWk8d+NKv4LePvCbXE6+XQqyODX40qZKkQJFccLh+BcRpjIGAN8E6mWkAUrdcwxIyJSK7XI5m4fWEVCZaF0avFxRUEsMAr0OuS5w/EDeb4mmE1x3E+u8tcFkeWuAx8SyxrTUk1zhWXsKEtlS0uU4nPuI09Pj/98XJEntLYUMVVqGxftIZGTW+zIFhhcBPg/BCG/Hu+woHfC2aycc5JUIViukqBkInm/irmvNcP83QjQnKYTQBCsMkwRN0GzbNCFWnagi9nrFtTRH+HuGKR0RKhsanCzPcH5jJfiEsc8Apg+oJL1UHN3D9ff/596R3ZGUg622kXZuM6l2Qf6oflGvlNCqm7N42Q2lzfnY9wc2T1A7n2kdTBD3qSJftu+8aaq9PVpQeeYN/0rLN6P1PjgrBAK5uNu5qmtAjl1l9sIZB/wRvtwPdKg/wM9hTP3lSt+fmgbjw7yWeJr679gNC1G8Ov83KruWqvB9U/Izr0hYNTFMxWqWhSCBZ3qsqvULsZykwjk+977BfGn1Ivte3bBUYmo6zuvA/sU7kNZGa/RNljHeCRkc1yARmuuVjOFTRXeIB5sjwU8OkHXi568qdem1BOQUwex8FYSQewDti0rn63n9kYQq4AAA=' },
  { ratio: 1086 / 1448, src: '/assets/history/desk-3x4-v2.webp', standIn: 'data:image/webp;base64,UklGRngEAABXRUJQVlA4WAoAAAAgAAAAKQAANwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggigIAABANAJ0BKioAOAA+lT6aSiWjIiGqtAwAsBKJQBVR8wFDv1XIS7/vwmQKJXQfu40GrOMeVmZRSUGIYI4iUIKOOcXyd+Ryi+0grK0XeMw3dDMg+hBsu99jySFVNNh0nsYq3GUJ0ZQ/kApGlFd9+0m+5mzAAO3mq6WYjRv03lXOvBdKNp3xzXYli5EfwzvDQLEEFYxp2nfSom9eBz4uDa5ryxO9LIQB95DJWbFS0BJJnROTn1D6L+vsmatJpNc4cIepFDpvVJ0u9OJdRtNCieUEzAidyyae3jrXLuBVGk2DzBXCHNKdARKF0JWANsD7Gcvn76T5oSqbprUFCeXA3DoEYyx1zFqtk5Iy4Sou37tBmx53IdknnnqAVL2G8n3KU8M2fb5gnVNt13LqL7dm9+iL+YAfenXEEMc1pbSbLKqKHfuMAlfRHjBunwDY13v3D2h69IxS9w8OK+Rn7rz5uw8hV1E+n5pQVCPrBoz4KyaqdAsjNK8DoordH38cSECBx2cq4+0S8RtDH+0+B7ylwrVOMdV+f3iAYGVIg5VNCXlpm0Nu5Yl0+hQI0je5FjOv5bDqrVYZUgCIq0DY52aWe6YwOC6ijbgU8MQ0PK0JWwGJhHt9hlw5C73SAIOf7+RZQ9NMaT/2XHQ2OGIPaiuvCgssg0E55jafSQfCS19/3H7BnuIoCjrP+CDl2q1XwwWVdUtx12uRfd0z9zYGX18gtQkeRjdyUOVMrq0eTm2dXvlUPK2Pi+ReL9Mz0MLSdwc04RVdkkMd/KQq3GNQ8HVIjrdmsuJRchcAaswVrssAcpidRVWAN3i6SwRNfjkAm5FhekpcH+SCVlEHBNH3hNMoJEd844AVQ4YqE7X2AAAA' },
  { ratio: 941 / 1672, src: '/assets/history/desk-9x16-v2.webp', standIn: 'data:image/webp;base64,UklGRsQDAABXRUJQVlA4WAoAAAAgAAAAHwAANwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDgg1gEAAHAJAJ0BKiAAOAA+lUagS6WjoyGkCSCwEoliAJ0zcgHy9NNdURubezLfUdQZlFMJz7+5ZhLMKQAJJghum2Mi+EIyTeliaiC3qidz3rWVm3goCprfAAD+eOsioCsjZSx+6OxH4fODCuiPeij9d8dixS316pUGSwNBtV2XIdyobYj3J1TEIWj7Y6B+3pFAPsxQUtudvuhde687nQreYrwtEYj25BeJuybt23+LlbNYJbLIB8UZ21BoaSuzEJEhMtiwFBZpoMaQmWWfnM34e8f4gDXvxX9tdbejeR7qXjmSlk3o8yNYb1Rwj/3JScsyJeIWAHwBvT2vO5W0kGnBfC2KFUaIVyHp1zpDvLQ2E+TZC5WA30ORQc2XX1kPGn5bA3zUui3pTkAhZP2/kelNnA7DOW/T2537EzhPv4N2yEL5m4h2lmVlFmKow+cRNXymq1ZF4N4u0YsOBHGbobwwOugMGON1Iicxzkd5stwJXGR0AGfwy8tr9cHDv3paH7ipC2sVN5xyKRv3+9jVtdRHObzLeaxZaInE7SVZSvtJgAZ7vmAEltpm1Fa6DsKg5JPQm9LeDyo5+45kTPcdbykPTo92NvVHa1R8vCjcVkiaER4uhyoymWQCgAAA' },
];

export const historyOverview = {
  generatedAt: '2026.09.14 00:00',
  periodLabel: '최근 90일',
  totalArticleCount: 126,
  topicCount: 7,
};

const SOURCES = ['연합뉴스', '한국경제', '전자신문'];

/**
 * 한 기사에 실제 길이의 요약을 물려 기사 패널이 견디는지 본다. 나머지 기본 요약은
 * 30자 안팎이라 줄바꿈도 스크롤도 일어나지 않아, 그 상태로는 레이아웃이 검증되지 않는다.
 * 실제 요약은 이 정도 분량으로 내려온다.
 */
const SAMPLE_LONG_SUMMARY =
  '유니테스트가 최근 SK하이닉스와 검사장비 공급 계약을 체결했다. ' +
  'HBM3E 수율 경쟁이 본격화되며 테스트 장비 수요와 장비주에 대한 관심이 커진 상황에서 체결된 계약이다. ' +
  '유니테스트는 국내에서 처음으로 메모리 모듈·컴포넌트 테스터를 개발한 업체이며, ' +
  '전체 매출의 약 60%를 태양광 사업에서 올리고 태양광 발전시공과 태양전지 개발도 병행하고 있다.'

/** 사건 전체를 설명하는 Event 요약. 기사 한 건의 요약과는 다른 층위다. */
const SAMPLE_EVENT_SUMMARY =
  '한국은행이 1년째 기준금리 3.50%를 8차례 연속 동결했다. ' +
  '물가가 5개월 연속 3%대에 머무르는 가운데 부동산 PF 부실 우려·취약차주 연체율 상승·저성장 압력이 ' +
  '동시에 금리 인하 필요를 키웠지만 물가 안정 확신이 없어 긴축을 유지하는 딜레마에 빠졌다. ' +
  '관건은 물가 수습 여부로, 당분간 추가 동결 가능성이 거론되는 한편 시장은 2분기 말~3분기 인하 가능성을 주시하고 있다.'

/**
 * `summaries`를 주면 기사별 기본 요약 대신 그 값을 쓴다. 인덱스별로 null이면 기본값으로 떨어진다.
 * `summary`는 Event 자체의 요약으로, 기사 한 건이 아니라 사건 전체를 설명한다 — 화면의
 * EVENT SUMMARY가 첫 기사 요약을 빌려 쓰던 것을 대신한다.
 */
const STATEMENT_SHAPES = [
  (title) => `"${title}을 예정대로 추진한다"`,
  (title) => `"${title} 관련 협의를 이어가겠다"`,
  (title) => `"${title}의 영향을 지켜보고 있다"`,
]

/**
 * 이 사건에서 내가 접한 발언.
 *
 * Shaped like what `GET /users/me/graph/map` yields once that response is wired: the
 * STATEMENT nodes on the other end of this event's edges. So a statement carries the
 * node fields the graph uses — `nodeType`, `nodeKey`, `label` — rather than a shape of
 * its own, and swapping the mock for the response does not move anything downstream.
 *
 * 개수를 일부러 0~3 으로 흩뿌린다. 개인 그래프는 내가 읽거나 클릭한 Node 만 담으므로
 * 발언이 하나도 없는 사건이 실제로 나오고, 그 경우의 화면도 확인해야 한다.
 */
const makeStatements = (id, title, count) =>
  Array.from({ length: count }, (_, index) => ({
    nodeType: 'STATEMENT',
    nodeKey: `${id}-statement-${index + 1}`,
    label: STATEMENT_SHAPES[index % STATEMENT_SHAPES.length](title),
  }))

const makeEvent = (id, title, articleCount, lastReadAt, at, summaries = [], summary = null) => ({
  id,
  title,
  articleCount,
  lastReadAt,
  at,
  summary,
  statements: makeStatements(id, title, articleCount % 4),
  articles: SOURCES.map((source, index) => ({
    id: `${id}-article-${index + 1}`,
    source,
    readAt: index === 0 ? lastReadAt : `${index + 1}일 전`,
    title: [
      `${title}…핵심 내용과 향후 일정`,
      `${title}, 시장과 현장 반응은`,
      `${title} 관련 쟁점 정리`,
    ][index],
    summary: summaries[index] ?? [
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
  INTERNATIONAL: [
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
    makeEvent('budget-talk', '여야, 내년도 예산안 협상 착수', 7, '오늘 00:31', [19, 25], [SAMPLE_LONG_SUMMARY], SAMPLE_EVENT_SUMMARY),
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
  topic('INTERNATIONAL', '국제', 'violet', 17, 'ai-trade-rule', 'AI 규제와 첨단기술 통상 갈등', [
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

/**
 * 현재 로컬 기록과 임시 목업을 개인 그래프 API의 요약 응답 형태로 합친 fallback이다.
 * 백엔드 적재가 완성되면 historyGraphMock 병합부만 실제 응답 adapter로 교체한다.
 */
const graphEvents = historyStories.flatMap((cluster) => cluster.story.events);
const maxTopicArticleCount = Math.max(...historyStories.map((cluster) => cluster.articleCount));
const maxEventArticleCount = Math.max(...graphEvents.map((event) => event.articleCount));

const historyTopicNodes = historyStories.map((cluster) => ({
  id: `topic:${cluster.topicCode}`,
  kind: 'TOPIC_CLUSTER',
  nodeType: null,
  nodeKey: null,
  topicCode: cluster.topicCode,
  title: cluster.topicName,
  sourceArticleCount: cluster.articleCount,
  weight: cluster.articleCount / maxTopicArticleCount,
}));

const historyEventNodes = historyStories.flatMap((cluster) => cluster.story.events.map((event) => ({
  id: `EVENT:${event.id}`,
  kind: 'NODE',
  nodeType: 'EVENT',
  nodeKey: event.id,
  topicCode: cluster.topicCode,
  title: event.title,
  sourceArticleCount: event.articleCount,
  weight: event.articleCount / maxEventArticleCount,
  localContext: { storyId: cluster.story.id, eventId: event.id },
})));

/**
 * 인물·기관.
 *
 * 개인 그래프는 내가 읽은 기사가 지나간 Node 만 담으므로 분야마다 한두 곳만 남는다.
 * `GET /users/me/graph/map` 이 붙으면 이 표가 응답의 ENTITY 노드로 교체된다.
 *
 * `sourceArticleCount` 를 null 로 둔다 — 인물에게는 "내가 읽은 기사 수"가 없고, 0 으로
 * 두면 화면이 "기사 0개"라고 말해버린다. 행성 쪽은 null 을 보고 유형 이름을 대신 쓴다.
 */
const TOPIC_ENTITIES = {
  POLITICS: ['국회', '기획재정부'],
  ECONOMY: ['한국은행', '금융위원회'],
  SOCIETY: ['기상청'],
  CULTURE: ['국립박물관'],
  INTERNATIONAL: ['EU 집행위원회', '미국 상무부'],
  SPORTS: ['KBO'],
  IT_SCIENCE: ['삼성전자', '엔비디아'],
};

const entityId = (topicCode, index) => `ENTITY:${topicCode}-${index + 1}`;

const historyEntityNodes = historyStories.flatMap((cluster) => (
  (TOPIC_ENTITIES[cluster.topicCode] ?? []).map((name, index) => ({
    id: entityId(cluster.topicCode, index),
    kind: 'NODE',
    nodeType: 'ENTITY',
    nodeKey: `${cluster.topicCode.toLowerCase()}-entity-${index + 1}`,
    topicCode: cluster.topicCode,
    title: name,
    sourceArticleCount: null,
    weight: 0.44,
  }))
));

/** 인물은 사건의 주체로 붙는다. 한 분야에 인물이 둘이면 사건도 갈라 붙인다. */
const historyEntityEdges = historyStories.flatMap((cluster) => (
  (TOPIC_ENTITIES[cluster.topicCode] ?? []).map((name, index) => ({
    sourceId: entityId(cluster.topicCode, index),
    targetId: `EVENT:${cluster.story.events[index % cluster.story.events.length].id}`,
    relationship: 'ACTOR',
    weight: 0.52,
  }))
));

/** 발언은 이미 사건 안에 있다(makeStatements) — 그것을 그래프 노드로도 세운다. */
const historyStatementNodes = historyStories.flatMap((cluster) => (
  cluster.story.events.flatMap((event) => event.statements.map((statement) => ({
    id: `STATEMENT:${statement.nodeKey}`,
    kind: 'NODE',
    nodeType: 'STATEMENT',
    nodeKey: statement.nodeKey,
    topicCode: cluster.topicCode,
    title: statement.label,
    sourceArticleCount: null,
    weight: 0.3,
  })))
));

const historyStatementEdges = historyStories.flatMap((cluster) => (
  cluster.story.events.flatMap((event) => event.statements.map((statement) => ({
    sourceId: `EVENT:${event.id}`,
    targetId: `STATEMENT:${statement.nodeKey}`,
    relationship: 'CONTAINS_STATEMENT',
    weight: 0.4,
  })))
));

const historyTopicEdges = historyStories.flatMap((cluster) => cluster.story.events.map((event) => ({
  sourceId: `topic:${cluster.topicCode}`,
  targetId: `EVENT:${event.id}`,
  relationship: 'BELONGS_TO_TOPIC',
  weight: event.articleCount / maxEventArticleCount,
})));

export const historyGraph = {
  generatedAt: historyOverview.generatedAt,
  mockSource: historyGraphMock.source,
  mockNotice: historyGraphMock.notice,
  nodes: [
    ...historyTopicNodes,
    ...historyEventNodes,
    ...historyEntityNodes,
    ...historyStatementNodes,
    ...historyGraphMock.nodes,
  ],
  edges: [
    ...historyTopicEdges,
    ...historyEntityEdges,
    ...historyStatementEdges,
    ...historyGraphMock.edges,
  ],
};

export const historyCopy = {
  title: '나의 기록',
  description: '분야를 선택하고, 3D 기록 행성을 돌려 내가 읽은 맥락을 탐색해보세요.',
  articles: (count) => `읽은 기사 ${count}개`,
  eventCount: (count) => `Event ${count}개`,
  eventLabel: 'EVENT',
  articleLabel: 'ARTICLE',
  openEvent: (title) => `${title} 관련 읽은 기사 보기`,
  panelTitle: '내가 읽은 기사',
  panelCount: (count) => `이 Event에서 읽은 기사 ${count}개`,
  close: '닫기',
  sampleNotice: '최근 읽은 기사 3개를 보여드려요.',
  previous: '이전 분야',
  next: '다음 분야',
  page: (current, total) => `${current} / ${total} 페이지`,
};
