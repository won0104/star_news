/**
 * 개인 그래프 백엔드 적재가 완성되기 전 EVENT 탐색을 검증하는 임시 데이터다.
 * 사용자 제공 topic-globe 데모에서 EVENT 간 관계만 현재 API 형태로 옮겼다.
 */
const mockEvent = (nodeKey, topicCode, title, sourceArticleCount, weight) => ({
  id: `EVENT:${nodeKey}`,
  kind: 'NODE',
  nodeType: 'EVENT',
  nodeKey,
  topicCode,
  title,
  sourceArticleCount,
  weight,
  isMock: true,
});

const mockEdge = (sourceId, targetId, relationship, weight) => ({
  sourceId,
  targetId,
  relationship,
  weight,
  isMock: true,
});

const nodes = [
  mockEvent('mock-rate-decision', 'ECONOMY', '한국은행 통화정책 결정', 6, 0.96),
  mockEvent('mock-loan-control', 'ECONOMY', '가계대출 관리 강화', 4, 0.78),
  mockEvent('mock-typhoon', 'SOCIETY', '태풍 해솔 한반도 접근', 5, 0.9),
  mockEvent('mock-flight-cancel', 'SOCIETY', '제주 항공편 결항', 3, 0.68),
  mockEvent('mock-ai-export', 'INTERNATIONAL', 'AI 가속기 수출규제 발표', 5, 0.92),
  mockEvent('mock-license-rule', 'INTERNATIONAL', '수출 허가요건 확대', 3, 0.7),
  mockEvent('mock-manager-exit', 'SPORTS', '부산 웨이브스 감독 사퇴', 4, 0.86),
  mockEvent('mock-team-rebuild', 'SPORTS', '선수단 개편 착수', 3, 0.68),
];

const semanticEdges = [
  mockEdge('EVENT:mock-loan-control', 'EVENT:mock-rate-decision', 'SUBEVENT_OF', 0.84),
  mockEdge('EVENT:mock-typhoon', 'EVENT:mock-flight-cancel', 'CAUSES', 0.78),
  mockEdge('EVENT:mock-license-rule', 'EVENT:mock-ai-export', 'SUBEVENT_OF', 0.82),
  mockEdge('EVENT:mock-manager-exit', 'EVENT:mock-team-rebuild', 'CAUSES', 0.78),
];

const topicEdges = nodes.map((node) => mockEdge(
  `topic:${node.topicCode}`,
  node.id,
  'BELONGS_TO_TOPIC',
  Math.max(0.34, node.weight * 0.66),
));

export const historyGraphMock = {
  source: 'topic-globe/dist.zip',
  notice: 'EVENT 중심 임시 목업',
  nodes,
  edges: [...topicEdges, ...semanticEdges],
};
