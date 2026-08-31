/**
 * 통합 목업 데이터의 로딩, 최소 계약 검증, 공통 셸용 뷰 모델 생성을 담당합니다.
 * 원본 객체를 수정하지 않으며 화면별 그래프 계산은 이후 모듈에 맡깁니다.
 */

const DATASET_URL = new URL("../../data/mock/mock_dataset.json", import.meta.url);
const REQUIRED_ARRAY_FIELDS = ["categories", "articles", "nodes", "edges", "user_events"];
const REQUIRED_HOME_TREND_PERIOD_IDS = ["today", "week", "month", "quarter"];

function assertHomeTrendPeriodContract(dataset) {
  const home = dataset.views?.home;
  const periodOrder = home?.trend_period_order;
  const periods = home?.trend_periods;
  const provenance = home?.trend_statistics_provenance;
  const nodeIds = new Set(dataset.nodes.map((node) => node.id));

  if (
    !Array.isArray(periodOrder)
    || periodOrder.length !== REQUIRED_HOME_TREND_PERIOD_IDS.length
    || periodOrder.some((periodId, index) => periodId !== REQUIRED_HOME_TREND_PERIOD_IDS[index])
  ) {
    throw new TypeError("홈 기간별 트렌드 순서 계약이 올바르지 않습니다.");
  }
  if (!periods || typeof periods !== "object") {
    throw new TypeError("홈 기간별 트렌드 데이터가 없습니다.");
  }
  if (
    !provenance
    || provenance.kind !== "deterministic_mock"
    || provenance.synthetic !== true
  ) {
    throw new TypeError("홈 기간별 트렌드 통계 출처가 명시되지 않았습니다.");
  }

  for (const periodId of periodOrder) {
    const period = periods[periodId];
    const seeds = period?.seed_nodes;
    const risingNodeIds = period?.rising_node_ids;
    if (
      !period
      || period.id !== periodId
      || typeof period.title !== "string"
      || !Number.isInteger(period.window_days)
      || period.window_days < 1
    ) {
      throw new TypeError(`홈 기간별 트렌드 메타데이터가 올바르지 않습니다: ${periodId}`);
    }
    if (!Array.isArray(seeds) || seeds.length !== 8) {
      throw new TypeError(`홈 기간별 트렌드 seed는 8개여야 합니다: ${periodId}`);
    }

    const seedNodeIds = seeds.map((entry) => entry.node_id);
    if (
      new Set(seedNodeIds).size !== seedNodeIds.length
      || seedNodeIds.some((nodeId) => !nodeIds.has(nodeId))
    ) {
      throw new TypeError(`홈 기간별 트렌드 node 참조가 올바르지 않습니다: ${periodId}`);
    }
    if (
      !Array.isArray(risingNodeIds)
      || risingNodeIds.length !== 3
      || new Set(risingNodeIds).size !== 3
      || risingNodeIds.some((nodeId) => !seedNodeIds.includes(nodeId))
    ) {
      throw new TypeError(`홈 급상승 node 계약이 올바르지 않습니다: ${periodId}`);
    }

    for (const entry of seeds) {
      if (!entry || typeof entry !== "object") {
        throw new TypeError(`홈 기간별 트렌드 통계가 올바르지 않습니다: ${periodId}`);
      }
      const expectedChangeRate = Math.round(
        ((entry.article_count - entry.previous_article_count)
          / entry.previous_article_count) * 100,
      );
      if (
        !Number.isFinite(entry.x)
        || !Number.isFinite(entry.y)
        || entry.x < 0
        || entry.x > 1
        || entry.y < 0
        || entry.y > 1
        || !Number.isInteger(entry.article_count)
        || entry.article_count < 1
        || !Number.isInteger(entry.previous_article_count)
        || entry.previous_article_count < 1
        || !Number.isInteger(entry.change_rate)
        || entry.change_rate !== expectedChangeRate
      ) {
        throw new TypeError(`홈 기간별 트렌드 통계가 올바르지 않습니다: ${periodId}`);
      }
    }

    const seedByNodeId = new Map(seeds.map((entry) => [entry.node_id, entry]));
    if (risingNodeIds.some((nodeId) => seedByNodeId.get(nodeId).change_rate <= 0)) {
      throw new TypeError(`홈 급상승 node가 증가 상태가 아닙니다: ${periodId}`);
    }
  }
}

function assertDatasetContract(dataset) {
  if (!dataset || typeof dataset !== "object") {
    throw new TypeError("목업 데이터가 객체 형식이 아닙니다.");
  }

  const missingFields = REQUIRED_ARRAY_FIELDS.filter(
    (field) => !Array.isArray(dataset[field]),
  );

  if (missingFields.length > 0) {
    throw new TypeError(`목업 데이터 배열이 없습니다: ${missingFields.join(", ")}`);
  }

  if (!dataset.views || !dataset.navigation || !dataset.user) {
    throw new TypeError("목업 데이터의 views, navigation 또는 user가 없습니다.");
  }

  assertHomeTrendPeriodContract(dataset);
}

/** 최신 node_open 세션을 최근 탐색 바로가기 목록으로 압축합니다. */
export function deriveRecentExplorations(userEvents, nodeById, limit = 2) {
  const latestBySession = new Map();
  const nodeOpenEvents = userEvents
    .filter((event) => event.type === "node_open" && event.node_id)
    .sort((left, right) => right.occurred_at.localeCompare(left.occurred_at));

  for (const event of nodeOpenEvents) {
    if (latestBySession.has(event.session_id)) {
      continue;
    }

    const path = Array.isArray(event.path) && event.path.length > 0
      ? event.path
      : [event.node_id];
    const labels = path
      .slice(-2)
      .map((nodeId) => nodeById.get(nodeId)?.label)
      .filter(Boolean);

    latestBySession.set(event.session_id, {
      sessionId: event.session_id,
      nodeId: event.node_id,
      label: labels.join(" · ") || nodeById.get(event.node_id)?.label || "최근 탐색",
      occurredAt: event.occurred_at,
      href: `/explore/${encodeURIComponent(event.node_id)}`,
    });

    if (latestBySession.size >= limit) {
      break;
    }
  }

  return [...latestBySession.values()];
}

/** 원본 데이터에서 앱 전역에서 재사용할 읽기 전용 인덱스를 구성합니다. */
export function createMockModel(dataset) {
  assertDatasetContract(dataset);

  const nodeById = new Map(dataset.nodes.map((node) => [node.id, node]));
  const articleById = new Map(
    dataset.articles.map((article) => [article.id, article]),
  );
  const categoryById = new Map(
    dataset.categories.map((category) => [category.id, category]),
  );
  const edgeByPair = new Map();

  for (const edge of dataset.edges) {
    const key = [edge.source, edge.target].sort().join("\u0000");
    const previous = edgeByPair.get(key);
    if (!previous || (edge.weight ?? 0) > (previous.weight ?? 0)) {
      edgeByPair.set(key, edge);
    }
  }

  return {
    dataset,
    categories: dataset.categories,
    categoryById,
    nodeById,
    articleById,
    edgeByPair,
    navigation: dataset.navigation,
    user: dataset.user,
    recentExplorations: deriveRecentExplorations(
      dataset.user_events,
      nodeById,
    ),
    counts: {
      articles: dataset.articles.length,
      nodes: dataset.nodes.length,
      edges: dataset.edges.length,
      events: dataset.user_events.length,
    },
  };
}

/** 저장소의 통합 JSON을 fetch하고 공통 뷰 모델을 반환합니다. */
export async function loadMockModel(fetchImplementation = fetch) {
  const response = await fetchImplementation(DATASET_URL);
  if (!response.ok) {
    throw new Error(`목업 데이터를 불러오지 못했습니다. (${response.status})`);
  }

  return createMockModel(await response.json());
}
