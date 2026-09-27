/**
 * 트렌드 Event 하나의 주변 그래프 — `GET /api/v1/graphs/nodes/{nodeType}/{nodeKey}/neighbors`.
 *
 * Shaped like GraphNeighborsResponse, field for field, so the mock and the request are
 * interchangeable. Read off the Java DTO rather than the Swagger page: several DTOs
 * declare nested `NodeSummary` / `Edge` records, they collapse onto one schema each in the
 * generated document, and the pair that wins there belongs to 개인 그래프 — that page shows
 * `title` and `sourceId`, while the real response carries `label` and
 * `sourceNodeType` / `sourceNodeKey`.
 *
 *   centerNode  { nodeType, nodeKey, label }      선택한 Node
 *   nodes       [{ nodeType, nodeKey, label }]    중심 제외 주변 Node (neighborScore DESC)
 *   edges       [{ sourceNodeType, sourceNodeKey,
 *                  targetNodeType, targetNodeKey,
 *                  edgeType, weight }]            양 끝이 모두 위 목록에 있는 관계
 *   returnedCount / hasNext / nextCursor          커서 페이지네이션
 *
 * Returned node types are EVENT, ENTITY, STATEMENT and TIME; STORY and ARTICLE are held
 * back by the endpoint as screen-irrelevant.
 */

/** 주변 Node 하나를 그 Event에 매달고, 중심에서 나가는 Edge까지 함께 만든다. */
const link = (centerKey, nodeType, nodeKey, label, edgeType, weight) => ({
  node: { nodeType, nodeKey, label },
  edge: {
    sourceNodeType: 'EVENT',
    sourceNodeKey: centerKey,
    targetNodeType: nodeType,
    targetNodeKey: nodeKey,
    edgeType,
    weight,
  },
})

/**
 * 한 Event의 응답 하나를 만든다.
 *
 * `spec`의 순서가 곧 응답의 순서다. 서버는 neighborScore 내림차순으로 주는데, 목업에서는
 * 관여도가 큰 것부터 적은 것 순으로 적어 그 순서를 흉내 낸다 — 화면이 순서에 기대어
 * 배치하므로, 순서가 뒤바뀌면 실제 응답에서 그림이 달라진다.
 */
const buildNeighbors = (centerKey, centerLabel, spec) => {
  const links = spec.map(([nodeType, nodeKey, label, edgeType, weight]) =>
    link(centerKey, nodeType, nodeKey, label, edgeType, weight),
  )

  return {
    centerNode: { nodeType: 'EVENT', nodeKey: centerKey, label: centerLabel },
    nodes: links.map((entry) => entry.node),
    edges: links.map((entry) => entry.edge),
    returnedCount: links.length,
    hasNext: false,
    nextCursor: null,
  }
}

/** nodeKey → 그 Event의 주변 그래프. 서버에서는 요청 하나가 이 값 하나에 대응한다. */
export const trendNeighbors = {
  'evt-hbm4-line': buildNeighbors('evt-hbm4-line', '삼성전자, HBM4 생산라인 증설 완료', [
    ['ENTITY', 'ent-samsung', '삼성전자', 'ACTOR', 0.94],
    ['EVENT', 'evt-nvidia-adopt', '엔비디아, 차세대 가속기에 HBM4 채택', 'CAUSES', 0.88],
    ['STATEMENT', 'stm-yield-double', '"연내 양산 물량을 두 배로 늘린다"', 'CONTAINS_STATEMENT', 0.82],
    ['ENTITY', 'ent-pyeongtaek', '평택 4공장', 'TARGET', 0.71],
    ['EVENT', 'evt-bonder-order', '한미반도체, 본더 수주 사상 최대', 'CAUSES', 0.64],
    ['TIME', 'tim-2026-09', '2026년 9월', 'OCCURRED_AT', 0.5],
  ]),

  'evt-rate-hold': buildNeighbors('evt-rate-hold', '한국은행, 기준금리 3.50% 동결', [
    ['ENTITY', 'ent-bok', '한국은행', 'ACTOR', 0.96],
    ['STATEMENT', 'stm-inflation', '"물가 안정 확신에는 아직 이르다"', 'CONTAINS_STATEMENT', 0.85],
    ['EVENT', 'evt-won-rate', '원·달러 환율 1,330원대 진입', 'CAUSES', 0.79],
    ['ENTITY', 'ent-household-loan', '가계대출', 'TARGET', 0.68],
    ['TIME', 'tim-2026-09', '2026년 9월', 'OCCURRED_AT', 0.48],
  ]),

  'evt-nvidia-adopt': buildNeighbors('evt-nvidia-adopt', '엔비디아, 차세대 가속기에 HBM4 채택', [
    ['ENTITY', 'ent-nvidia', '엔비디아', 'ACTOR', 0.93],
    ['ENTITY', 'ent-hbm4', 'HBM4', 'TARGET', 0.9],
    ['EVENT', 'evt-hbm4-line', '삼성전자, HBM4 생산라인 증설 완료', 'CAUSES', 0.86],
    ['STATEMENT', 'stm-adopt', '"차세대 가속기에 HBM4를 채택한다"', 'CONTAINS_STATEMENT', 0.8],
    ['EVENT', 'evt-export-control', '미국, 대중 반도체 수출통제 확대', 'SUBEVENT_OF', 0.58],
  ]),

  'evt-budget-talk': buildNeighbors('evt-budget-talk', '여야, 내년도 예산안 협상 착수', [
    ['ENTITY', 'ent-assembly', '국회', 'ACTOR', 0.91],
    ['STATEMENT', 'stm-budget', '"법정 기한 내 처리를 목표로 한다"', 'CONTAINS_STATEMENT', 0.77],
    ['ENTITY', 'ent-budget-2027', '2027년도 예산안', 'TARGET', 0.74],
    ['EVENT', 'evt-audit-plan', '국정감사 일정과 증인 협의', 'SUBEVENT_OF', 0.62],
  ]),

  'evt-export-control': buildNeighbors('evt-export-control', '미국, 대중 반도체 수출통제 확대', [
    ['ENTITY', 'ent-us-commerce', '미국 상무부', 'ACTOR', 0.92],
    ['ENTITY', 'ent-china', '중국', 'TARGET', 0.87],
    ['EVENT', 'evt-nvidia-adopt', '엔비디아, 차세대 가속기에 HBM4 채택', 'CAUSES', 0.7],
    ['STATEMENT', 'stm-license', '"허가 요건을 추가로 확대한다"', 'CONTAINS_STATEMENT', 0.66],
    ['TIME', 'tim-2026-09', '2026년 9월', 'OCCURRED_AT', 0.44],
  ]),

  'evt-bonder-order': buildNeighbors('evt-bonder-order', '한미반도체, 본더 수주 사상 최대', [
    ['ENTITY', 'ent-hanmi', '한미반도체', 'ACTOR', 0.9],
    ['ENTITY', 'ent-bonder', 'TC 본더', 'TARGET', 0.83],
    ['EVENT', 'evt-hbm4-line', '삼성전자, HBM4 생산라인 증설 완료', 'CAUSES', 0.72],
    ['STATEMENT', 'stm-order', '"연간 수주가 사상 최대를 기록했다"', 'CONTAINS_STATEMENT', 0.6],
  ]),

  'evt-won-rate': buildNeighbors('evt-won-rate', '원·달러 환율 1,330원대 진입', [
    ['ENTITY', 'ent-fx', '원·달러 환율', 'TARGET', 0.89],
    ['EVENT', 'evt-rate-hold', '한국은행, 기준금리 3.50% 동결', 'CAUSES', 0.84],
    ['ENTITY', 'ent-exporters', '수출 기업', 'ACTOR', 0.63],
    ['STATEMENT', 'stm-fx', '"채산성과 물가에 동시에 영향을 준다"', 'CONTAINS_STATEMENT', 0.55],
  ]),

  'evt-eu-ai-act': buildNeighbors('evt-eu-ai-act', 'EU, AI법 단계적 시행', [
    ['ENTITY', 'ent-eu', '유럽연합', 'ACTOR', 0.93],
    ['ENTITY', 'ent-ai-act', 'AI법', 'TARGET', 0.88],
    ['STATEMENT', 'stm-ai-act', '"고위험 영역부터 단계적으로 적용한다"', 'CONTAINS_STATEMENT', 0.75],
    ['TIME', 'tim-2026-09', '2026년 9월', 'OCCURRED_AT', 0.46],
  ]),

  'evt-medical-talk': buildNeighbors('evt-medical-talk', '정부·의료계 후속 협의 재개', [
    ['ENTITY', 'ent-health-ministry', '보건복지부', 'ACTOR', 0.9],
    ['ENTITY', 'ent-doctors', '의료계', 'TARGET', 0.86],
    ['EVENT', 'evt-regional-care', '지역 필수의료 지원 확대', 'SUBEVENT_OF', 0.67],
    ['STATEMENT', 'stm-medical', '"필수의료 대책을 함께 논의한다"', 'CONTAINS_STATEMENT', 0.58],
  ]),

  'evt-baseball-rank': buildNeighbors('evt-baseball-rank', '프로야구 상위권 순위 경쟁', [
    ['ENTITY', 'ent-kbo', 'KBO 리그', 'TARGET', 0.85],
    ['EVENT', 'evt-playoff', '포스트시즌 진출 경쟁', 'SUBEVENT_OF', 0.7],
    ['STATEMENT', 'stm-baseball', '"남은 일정이 순위를 가른다"', 'CONTAINS_STATEMENT', 0.52],
  ]),
}

/** 원문은 보존하고, 화면에 그릴 때만 유형별 최대 길이 뒤를 말줄임한다. */
export function formatTrendGraphLabel(node) {
  const label = (node?.label ?? '').trim()
  const characters = [...label]
  const limit = node?.nodeType === 'ENTITY' ? 19 : node?.nodeType === 'EVENT' ? 199 : null
  if (limit == null || characters.length <= limit) return label
  return `${characters.slice(0, limit).join('')}…`
}

/**
 * Entity·Statement 의 세부 유형. 서버 응답의 `type` 자리에 들어가는 값이다.
 * 목업에 없는 키는 `null` — 실제 응답에서도 유형에 따라 비어 올 수 있는 필드다.
 */
const SUBTYPES = {
  'ent-samsung': 'ORGANIZATION',
  'ent-nvidia': 'ORGANIZATION',
  'ent-bok': 'ORGANIZATION',
  'ent-hanmi': 'ORGANIZATION',
  'ent-eu': 'ORGANIZATION',
  'ent-us-commerce': 'ORGANIZATION',
  'ent-health-ministry': 'ORGANIZATION',
  'ent-assembly': 'ORGANIZATION',
  'ent-doctors': 'ORGANIZATION',
  'ent-pyeongtaek': 'LOCATION',
  'ent-china': 'LOCATION',
  'ent-hbm4': 'PRODUCT',
  'ent-bonder': 'PRODUCT',
  'ent-ai-act': 'POLICY',
  'ent-budget-2027': 'POLICY',
  'ent-fx': 'INDICATOR',
  'ent-household-loan': 'INDICATOR',
  'ent-kbo': 'ORGANIZATION',
  'ent-exporters': 'ORGANIZATION',
  'stm-yield-double': 'PLAN',
  'stm-inflation': 'ASSESSMENT',
  'stm-adopt': 'PLAN',
  'stm-budget': 'PLAN',
  'stm-license': 'PLAN',
  'stm-order': 'FACT',
  'stm-fx': 'ASSESSMENT',
  'stm-ai-act': 'PLAN',
  'stm-medical': 'PLAN',
  'stm-baseball': 'ASSESSMENT',
}

/**
 * nodeKey → `GET /graphs/nodes/{nodeType}/{nodeKey}` 응답.
 *
 * Built from the graphs above rather than written out again, so a node cannot describe
 * itself one way in a neighbour list and another way in its own detail. Shape is
 * GraphNodeDetailResponse: `{ nodeType, nodeKey, title, type, time, bookmarked }`.
 * `time` is the Event's occurrence and is null for the other kinds; `bookmarked` is false
 * because the sample stands in for a signed-out read.
 */
export const trendNodeDetails = Object.values(trendNeighbors).reduce((all, graph) => {
  const add = (node, time = null) => {
    if (all[node.nodeKey]) return
    all[node.nodeKey] = {
      nodeType: node.nodeType,
      nodeKey: node.nodeKey,
      title: node.label,
      type: SUBTYPES[node.nodeKey] ?? null,
      time,
      bookmarked: false,
    }
  }

  add(graph.centerNode, '2026-09-17T09:00:00+09:00')
  graph.nodes.forEach((node) =>
    add(node, node.nodeType === 'EVENT' ? '2026-09-16T18:00:00+09:00' : null),
  )
  return all
}, {})

const PRESS = ['연합뉴스', '한국경제', '전자신문', '한겨레', '머니투데이']

/**
 * nodeKey → `GET /graphs/nodes/{nodeType}/{nodeKey}/articles` 응답.
 *
 * Derived from each node's own title so the sample reads as that node's coverage rather
 * than as filler. Shape is RelatedArticlesResponse:
 * `{ articles, totalCount, returnedCount, hasNext, nextCursor }`, each article being
 * `{ articleId, title, organizationName, publishedAt, bookmarked }`.
 *
 * One page only: `hasNext` is false and `totalCount` matches what is here. The sample's
 * keys are not in Neo4j, so a second page could not be fetched — claiming one would put a
 * 더 보기 button on screen that always fails. Paging is implemented and waits for real data.
 */
export const trendNodeArticles = Object.values(trendNodeDetails).reduce((all, node, index) => {
  const count = 3 + (index % 3)
  all[node.nodeKey] = {
    articles: Array.from({ length: count }, (_, i) => ({
      articleId: 930000 + index * 10 + i,
      title: [
        `${node.title} — 배경과 쟁점`,
        `${node.title}, 시장은 어떻게 봤나`,
        `${node.title} 관련 후속 일정 정리`,
        `${node.title}에 대한 현장 반응`,
      ][i % 4],
      organizationName: PRESS[(index + i) % PRESS.length],
      publishedAt: `2026-09-${String(16 - i).padStart(2, '0')}T09:${String(10 + i * 7).padStart(2, '0')}:00+09:00`,
      bookmarked: false,
    })),
    totalCount: count,
    returnedCount: count,
    hasNext: false,
    nextCursor: null,
  }
  return all
}, {})

export const trendSkyExpandCopy = {
  back: '← 오늘의 트렌드',
  centre: '선택한 사건',
  around: (n) => `이어진 Node ${n}개`,
  missing: '이 사건의 주변 그래프가 아직 없어요.',
  loading: '이어진 이야기를 찾는 중…',
  failed: '주변 그래프를 불러오지 못했어요.',
  detailLabel: 'NODE',
  detailLoading: '불러오는 중…',
  detailFailed: '이 Node의 상세를 불러오지 못했어요.',
  detailTime: (at) => `${at} 발생`,
  close: '닫기',
  bookmark: '즐겨찾기',
  unbookmark: '즐겨찾기 해제',
  signInToBookmark: '로그인하면 즐겨찾기할 수 있어요.',
  bookmarkFailed: '저장하지 못했어요. 다시 시도해 주세요.',
}
