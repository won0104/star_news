/**
 * 개인 열람 이벤트를 기록 목록, 군집 그래프, 리포트, 전체 지도용 데이터로 변환합니다.
 * 목업 데이터의 사실만 집계하며 Figma에 적힌 예시 수치와 기사명은 사용하지 않습니다.
 */

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
const SOURCE_COLORS = ["#5f84aa", "#7899ba", "#96abc0", "#b1c0ce", "#d8e0e7"];

export const CLUSTER_COLORS = {
  politics: "#b99e91",
  economy: "#78a3c8",
  society: "#88b4a6",
  culture: "#c0a77e",
  world: "#aaa2c6",
  local: "#82adae",
  sports: "#a3a8b1",
  tech_science: "#8fa9c4",
};

function safeDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function getNodeKind(node) {
  if (node.type === "category") {
    return "category";
  }
  if (["topic", "technology", "industry", "sport"].includes(node.type)) {
    return "topic";
  }
  if (["policy", "event"].includes(node.type)) {
    return "event";
  }
  return "entity";
}

/** 기사 열람 이벤트를 기사·분야 메타데이터와 결합해 최신순으로 반환합니다. */
export function selectReadHistory(model, nodeId = null) {
  const selectedNode = nodeId ? model.nodeById.get(nodeId) : null;
  const entries = model.dataset.user_events
    .filter((event) => {
      if (event.type !== "article_read" || !event.article_id) {
        return false;
      }
      if (!selectedNode) {
        return true;
      }
      if (selectedNode.type === "category") {
        return (
          event.category_ids?.includes(selectedNode.category_id)
          || event.node_ids?.includes(selectedNode.id)
        );
      }
      return event.node_ids?.includes(selectedNode.id);
    })
    .map((event) => {
      const article = model.articleById.get(event.article_id);
      if (!article) {
        return null;
      }
      const category = model.categoryById.get(article.primary_category_id);
      return {
        id: event.id,
        occurredAt: event.occurred_at,
        event,
        article,
        sourceName: article.source?.name || "출처 미상",
        categoryName: category?.name || article.primary_category_name || "기타",
      };
    })
    .filter(Boolean)
    .sort((left, right) => right.occurredAt.localeCompare(left.occurredAt));

  return {
    node: selectedNode,
    title: selectedNode ? `${selectedNode.label} 기록` : "전체 기록",
    entries,
  };
}

/** 최근 기록 화면에 표시할 상위 네 군집과 군집별 대표 노드를 선택합니다. */
export function selectRecordGraph(model, clusterLimit = 4, childLimit = 3) {
  const distribution = [...model.dataset.user_report.category_distribution]
    .filter((entry) => entry.count > 0)
    .sort((left, right) => right.count - left.count)
    .slice(0, clusterLimit);
  const centers = [
    { x: 0.31, y: 0.42 },
    { x: 0.67, y: 0.29 },
    { x: 0.72, y: 0.7 },
    { x: 0.31, y: 0.73 },
  ];
  const childOffsets = [
    [{ x: -0.17, y: -0.12 }, { x: 0.05, y: -0.18 }, { x: 0.16, y: 0.09 }],
    [{ x: -0.12, y: -0.16 }, { x: 0.15, y: -0.13 }, { x: 0.18, y: 0.1 }],
    [{ x: 0.14, y: -0.15 }, { x: 0.16, y: 0.1 }, { x: -0.12, y: 0.16 }],
    [{ x: -0.15, y: -0.11 }, { x: -0.17, y: 0.12 }, { x: 0.13, y: 0.14 }],
  ];
  const nodes = [];

  distribution.forEach((entry, index) => {
    const categoryNode = model.nodeById.get(`category:${entry.category_id}`);
    if (!categoryNode) {
      return;
    }
    const center = centers[index];
    nodes.push({
      ...categoryNode,
      graphX: center.x,
      graphY: center.y,
      graphKind: "category",
      color: CLUSTER_COLORS[entry.category_id],
    });

    model.dataset.nodes
      .filter((node) => (
        node.type !== "category"
        && node.category_id === entry.category_id
        && (node.read_count ?? 0) > 0
      ))
      .sort((left, right) => (
        (right.read_count ?? 0) - (left.read_count ?? 0)
        || (right.personal_score ?? 0) - (left.personal_score ?? 0)
      ))
      .slice(0, childLimit)
      .forEach((node, childIndex) => {
        const offset = childOffsets[index][childIndex];
        nodes.push({
          ...node,
          graphX: center.x + offset.x,
          graphY: center.y + offset.y,
          graphKind: getNodeKind(node),
          color: CLUSTER_COLORS[entry.category_id],
        });
      });
  });

  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = model.dataset.edges
    .filter((edge) => (
      nodeIds.has(edge.source)
      && nodeIds.has(edge.target)
      && (
        edge.relations?.includes("category_membership")
        || (edge.read_support ?? 0) > 0
      )
    ))
    .sort((left, right) => (
      Number(right.relations?.includes("category_membership"))
      - Number(left.relations?.includes("category_membership"))
      || (right.read_support ?? 0) - (left.read_support ?? 0)
    ));

  return { nodes, edges, distribution };
}

function selectPersonalMapEdges(edges, nodes) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edgeKey = (edge) => [edge.source, edge.target].sort().join("\u0000");
  const distance = (edge) => {
    const source = nodeById.get(edge.source)?.layout?.personal_map;
    const target = nodeById.get(edge.target)?.layout?.personal_map;
    return source && target ? Math.hypot(source.x - target.x, source.y - target.y) : 1;
  };
  const isCrossCategory = (edge) => (
    nodeById.get(edge.source)?.category_id !== nodeById.get(edge.target)?.category_id
  );
  const isStructural = (edge) => edge.relations?.includes("category_membership");
  const candidates = edges
    .filter((edge) => isStructural(edge) || (edge.read_support ?? 0) > 0)
    .sort((left, right) => (
      (right.read_support ?? 0) - (left.read_support ?? 0)
      || Number(isCrossCategory(left)) - Number(isCrossCategory(right))
      || distance(left) - distance(right)
      || edgeKey(left).localeCompare(edgeKey(right))
    ));
  const selected = new Map();
  const degree = new Map(nodes.map((node) => [node.id, 0]));

  const add = (edge) => {
    const key = edgeKey(edge);
    if (selected.has(key)) {
      return;
    }
    selected.set(key, edge);
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  };

  candidates.filter((edge) => (edge.read_support ?? 0) >= 2).forEach(add);

  [...nodes]
    .sort((left, right) => (right.read_count ?? 0) - (left.read_count ?? 0))
    .forEach((node) => {
      if ((degree.get(node.id) ?? 0) > 0) {
        return;
      }
      const fallback = candidates
        .filter((edge) => (
          (edge.source === node.id || edge.target === node.id)
          && !selected.has(edgeKey(edge))
        ))
        .sort((left, right) => (
          Number(isStructural(right)) - Number(isStructural(left))
          || (right.read_support ?? 0) - (left.read_support ?? 0)
          || Number(isCrossCategory(left)) - Number(isCrossCategory(right))
          || distance(left) - distance(right)
        ))[0];
      if (fallback) {
        add(fallback);
      }
    });

  return [...selected.values()];
}

/** 읽은 노드와 강한 열람 관계, 고립 방지용 구조선을 개인 지도 부분집합으로 반환합니다. */
export function selectPersonalMap(model) {
  const nodes = model.dataset.nodes
    .filter((node) => (
      (node.read_count ?? 0) > 0
      && node.layout?.personal_map
    ))
    .map((node) => ({
      ...node,
      graphKind: getNodeKind(node),
      color: CLUSTER_COLORS[node.category_id] ?? "#a8b6c2",
    }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = selectPersonalMapEdges(
    model.dataset.edges.filter((edge) => (
      nodeIds.has(edge.source) && nodeIds.has(edge.target)
    )),
    nodes,
  );

  return { nodes, edges };
}

function selectSourceDistribution(history) {
  const counts = new Map();
  for (const entry of history.entries) {
    const rawName = entry.sourceName;
    const name = rawName === "별빛 뉴스 시연 데이터" ? "시연 기록" : rawName;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const sorted = [...counts.entries()].sort((left, right) => right[1] - left[1]);
  const top = sorted.slice(0, 4);
  const otherCount = sorted.slice(4).reduce((sum, [, count]) => sum + count, 0);
  const total = history.entries.length || 1;
  const segments = [...top, ...(otherCount ? [["기타", otherCount]] : [])]
    .map(([name, count], index) => ({
      name,
      count,
      ratio: count / total,
      color: SOURCE_COLORS[index],
    }));
  return { uniqueCount: counts.size, segments };
}

function selectWeeklyReading(model, history, weeks = 12) {
  const periodEnd = safeDate(model.dataset.user_report.period.to) ?? new Date();
  const start = new Date(periodEnd.getTime() - weeks * WEEK_MS);
  const topCategoryIds = [...model.dataset.user_report.category_distribution]
    .sort((left, right) => right.count - left.count)
    .slice(0, 3)
    .map((entry) => entry.category_id);
  const categories = [
    ...topCategoryIds.map((categoryId) => ({
      id: categoryId,
      name: model.categoryById.get(categoryId)?.name ?? categoryId,
    })),
    { id: "other", name: "기타" },
  ];
  const buckets = Array.from({ length: weeks }, (_, index) => ({
    index,
    start: new Date(start.getTime() + index * WEEK_MS),
    values: Object.fromEntries(categories.map((category) => [category.id, 0])),
    total: 0,
  }));

  for (const entry of history.entries) {
    const occurredAt = safeDate(entry.occurredAt);
    if (!occurredAt || occurredAt < start || occurredAt > periodEnd) {
      continue;
    }
    const bucketIndex = Math.min(
      weeks - 1,
      Math.floor((occurredAt.getTime() - start.getTime()) / WEEK_MS),
    );
    const bucket = buckets[bucketIndex];
    const categoryId = topCategoryIds.includes(entry.article.primary_category_id)
      ? entry.article.primary_category_id
      : "other";
    bucket.values[categoryId] += 1;
    bucket.total += 1;
  }

  let previousMonth = null;
  for (const bucket of buckets) {
    const month = bucket.start.getUTCMonth() + 1;
    bucket.monthLabel = month !== previousMonth ? `${month}월` : "";
    previousMonth = month;
  }

  return {
    categories,
    buckets,
    maxTotal: Math.max(1, ...buckets.map((bucket) => bucket.total)),
  };
}

function selectTerrain(model, limit = 8) {
  const points = model.dataset.user_report.recent_topic_terrain.points
    .map((point) => ({ ...point, node: model.nodeById.get(point.node_id) }))
    .filter((point) => point.node);
  const quadrantGroups = new Map();

  for (const point of points) {
    const key = `${point.x_read_frequency >= 0.5 ? "high" : "low"}-${point.y_recent_growth >= 0 ? "up" : "down"}`;
    const group = quadrantGroups.get(key) ?? [];
    group.push(point);
    quadrantGroups.set(key, group);
  }

  const selected = [...quadrantGroups.values()]
    .flatMap((group) => group.sort((left, right) => right.read_count - left.read_count).slice(0, 2));
  for (const point of points) {
    if (selected.length >= limit) {
      break;
    }
    if (!selected.includes(point)) {
      selected.push(point);
    }
  }
  return selected.slice(0, limit);
}

/** 개인 리포트 화면의 모든 차트 입력을 실제 기록에서 구성합니다. */
export function selectPersonalReport(model) {
  const history = selectReadHistory(model);
  const report = model.dataset.user_report;
  return {
    period: report.period,
    overview: report.overview,
    categoryDistribution: [...report.category_distribution]
      .filter((entry) => entry.count > 0)
      .sort((left, right) => right.count - left.count)
      .slice(0, 5),
    sourceDistribution: selectSourceDistribution(history),
    weeklyReading: selectWeeklyReading(model, history),
    terrain: selectTerrain(model),
  };
}
