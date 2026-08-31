/**
 * 목업 원본을 변경하지 않고 홈 기간 통계와 검색·탐색 부분집합을 계산합니다.
 * 검색 점수는 목업 단계의 임시 휴리스틱이며 실제 추천·검색 모델을 뜻하지 않습니다.
 */

function normalizeSearchText(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("ko-KR")
    .replace(/\s+/g, " ")
    .trim();
}

function addScore(scores, nodeId, score) {
  if (!nodeId) {
    return;
  }
  scores.set(nodeId, Math.max(scores.get(nodeId) ?? 0, score));
}

export const DEFAULT_HOME_TREND_PERIOD_ID = "today";

/** 기간별 홈 통계 계약을 화면에서 바로 사용할 수 있는 node 결합 뷰로 변환합니다. */
export function selectHomeTrendPeriod(
  model,
  requestedPeriodId = DEFAULT_HOME_TREND_PERIOD_ID,
) {
  const home = model.dataset.views.home;
  const periodId = home.trend_period_order.includes(requestedPeriodId)
    ? requestedPeriodId
    : DEFAULT_HOME_TREND_PERIOD_ID;
  const period = home.trend_periods[periodId];
  const risingNodeIds = new Set(period.rising_node_ids);
  const seeds = period.seed_nodes.map((entry) => ({
    nodeId: entry.node_id,
    node: model.nodeById.get(entry.node_id),
    x: entry.x,
    y: entry.y,
    articleCount: entry.article_count,
    previousArticleCount: entry.previous_article_count,
    changeRate: entry.change_rate,
    isRising: risingNodeIds.has(entry.node_id),
  }));
  const seedByNodeId = new Map(seeds.map((entry) => [entry.nodeId, entry]));

  return {
    id: period.id,
    label: period.label,
    title: period.title,
    windowDays: period.window_days,
    windowLabel: period.window_label,
    comparisonLabel: period.comparison_label,
    startsAt: period.starts_at,
    endsAt: period.ends_at,
    comparisonStartsAt: period.comparison_starts_at,
    comparisonEndsAt: period.comparison_ends_at,
    updatedAt: period.updated_at,
    statisticsProvenance: home.trend_statistics_provenance,
    seeds,
    rising: period.rising_node_ids.map((nodeId) => seedByNodeId.get(nodeId)),
  };
}

/** 검색어와 직접 일치하는 노드, 기사 속 노드, 직접 이웃을 관련도와 함께 정렬합니다. */
export function selectSearchResults(model, query, limit = 8) {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return [];
  }

  const scores = new Map();
  const directNodeIds = [];

  for (const node of model.dataset.nodes) {
    const label = normalizeSearchText(node.label);
    const aliases = (node.aliases ?? []).map(normalizeSearchText);
    let score = 0;

    if (label === normalizedQuery) {
      score = 120;
    } else if (label.includes(normalizedQuery)) {
      score = 82;
    } else if (aliases.some((alias) => alias === normalizedQuery)) {
      score = 100;
    } else if (aliases.some((alias) => alias.includes(normalizedQuery))) {
      score = 68;
    }

    if (score > 0) {
      addScore(scores, node.id, score);
      directNodeIds.push(node.id);
    }
  }

  for (const article of model.dataset.articles) {
    const sourceName = article.source?.name ?? "";
    const haystack = normalizeSearchText(
      `${article.title ?? ""} ${article.description ?? ""} ${sourceName}`,
    );
    if (!haystack.includes(normalizedQuery)) {
      continue;
    }

    for (const nodeId of article.node_ids ?? []) {
      addScore(scores, nodeId, 54);
    }
  }

  for (const nodeId of directNodeIds.slice(0, 3)) {
    const neighbors = model.navigation[nodeId]?.neighbor_node_ids ?? [];
    neighbors.forEach((neighborId, index) => {
      // 직접 일치 노드의 관계를 기사 본문에서 우연히 함께 잡힌 노드보다 우선합니다.
      addScore(scores, neighborId, 72 - index * 2);
    });
  }

  return [...scores.entries()]
    .map(([nodeId, score]) => ({ node: model.nodeById.get(nodeId), score }))
    .filter(({ node }) => node && node.type !== "category")
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return (right.node.trend_score ?? 0) - (left.node.trend_score ?? 0);
    })
    .slice(0, limit);
}

/** 기존 호출부를 위해 검색 결과에서 노드 배열만 반환합니다. */
export function selectSearchNodes(model, query, limit = 8) {
  return selectSearchResults(model, query, limit).map(({ node }) => node);
}

/** 두 노드 사이에서 가장 강한 엣지를 반환합니다. */
export function selectEdge(model, firstNodeId, secondNodeId) {
  const key = [firstNodeId, secondNodeId].sort().join("\u0000");
  return model.edgeByPair.get(key);
}

/** URL query에 저장된 경로를 현재 탐색 노드까지 유효한 배열로 정리합니다. */
export function resolveExplorationPath(model, route) {
  const currentNodeId = route.params.nodeId;
  if (!currentNodeId || !model.nodeById.has(currentNodeId)) {
    return [];
  }

  const requestedPath = route.searchParams
    .getAll("path")
    .filter((nodeId) => model.nodeById.has(nodeId));
  const currentIndex = requestedPath.lastIndexOf(currentNodeId);

  if (currentIndex >= 0) {
    return requestedPath.slice(0, currentIndex + 1);
  }

  return [...requestedPath, currentNodeId];
}

/** 탐색 경로를 보존하는 노드 주소를 생성합니다. */
export function buildExploreHref(nodeId, path = [nodeId]) {
  const params = new URLSearchParams();
  path.forEach((pathNodeId) => params.append("path", pathNodeId));
  const search = params.toString();
  return `/explore/${encodeURIComponent(nodeId)}${search ? `?${search}` : ""}`;
}

/** 현재 노드의 이웃, 엣지, 관련 기사만 탐색 화면용으로 선택합니다. */
export function selectExploration(model, currentNodeId, path = [currentNodeId]) {
  const currentNode = model.nodeById.get(currentNodeId);
  if (!currentNode) {
    return null;
  }

  const pathSet = new Set(path);
  const navigation = model.navigation[currentNodeId] ?? {
    neighbor_node_ids: [],
    article_ids: [],
  };
  const neighbors = navigation.neighbor_node_ids
    .filter((nodeId) => !pathSet.has(nodeId))
    .map((nodeId) => model.nodeById.get(nodeId))
    .filter(Boolean)
    .map((node) => ({
      node,
      edge: selectEdge(model, currentNodeId, node.id),
    }));
  const articles = navigation.article_ids
    .map((articleId) => model.articleById.get(articleId))
    .filter(Boolean);

  return { currentNode, neighbors, articles };
}
