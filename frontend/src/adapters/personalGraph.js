/**
 * 개인 그래프 응답 → 화면이 쓰는 모양.
 *
 * 두 응답이 한 화면을 채운다. 요약(`/users/me/graph`)은 분야 7칸과 분야마다 대표 Node 다섯,
 * 지도(`/users/me/graph/map`)는 고른 분야 하나의 전부다. 행성은 늘 둘을 합친 하나의 그래프를
 * 받는다 — 고른 분야만 속을 펼치고 나머지는 대표만 남긴 상태.
 *
 * 필드 이름이 두 응답에서 다르다(요약은 `title`·`topicCode` 를 주고 지도는 `label` 만 준다).
 * 그 차이를 여기서 한 번 흡수해서, 행성과 오른쪽 페이지는 한 가지 모양만 알면 되게 한다.
 */

import { topicName } from '../data/topics'

const clusterId = (topicCode) => `topic:${topicCode}`

/** 지도 응답의 Node 를 요약 응답의 Node 모양으로 옮긴다. */
const nodeFromMap = (node, topicCode) => ({
  id: node.id,
  kind: 'NODE',
  nodeType: node.nodeType,
  nodeKey: node.nodeKey,
  topicCode,
  title: node.label,
  sourceArticleCount: node.sourceArticleCount,
  weight: node.weight,
})

/**
 * 요약 응답을 행성 그래프로. 필드가 이미 행성이 쓰는 것과 같아서 감싸기만 한다.
 *
 * 읽은 것이 없으면 nodes 가 빈 배열로 온다 — 실패가 아니므로 그대로 통과시키고,
 * 화면이 "아직 기록이 없다"를 말한다.
 */
export function graphFromSummary(summary) {
  return {
    generatedAt: summary?.generatedAt ?? null,
    nodes: summary?.nodes ?? [],
    edges: summary?.edges ?? [],
  }
}

/**
 * 고른 분야의 속을 지도 응답으로 갈아 끼운다.
 *
 * 그 분야의 대표 Node 는 지도가 준 전체로 대체된다(같은 id 가 두 번 서지 않게). 다른 분야는
 * 요약이 준 대표 그대로 남는다. Edge 는 양 끝이 모두 남아 있는 것만 살린다 — 대표 다섯에
 * 걸려 있던 Edge 가 지도로 갈아 끼운 뒤 허공을 가리키는 일을 막는다.
 *
 * Topic Cluster 와 Node 를 잇는 BELONGS_TO_TOPIC 은 지도 응답에 없다(지도는 Node 사이
 * 관계만 준다). 행성의 분야 별과 그 아래 별들이 이어져 보이도록 여기서 만들어 붙인다.
 */
export function mergeTopicMap(graph, map) {
  const topicCode = map?.topic?.topicCode
  if (!topicCode) return graph

  const mapped = (map.nodes ?? []).map((node) => nodeFromMap(node, topicCode))
  const others = (graph.nodes ?? []).filter(
    (node) => node.kind === 'TOPIC_CLUSTER' || node.topicCode !== topicCode,
  )

  // 요약에 이 분야의 Cluster 가 없을 수 있다 — 기록이 처음 생긴 분야가 그렇다.
  const hasCluster = others.some((node) => node.id === clusterId(topicCode))
  const cluster = hasCluster
    ? []
    : [{
      id: clusterId(topicCode),
      kind: 'TOPIC_CLUSTER',
      nodeType: null,
      nodeKey: null,
      topicCode,
      title: map.topic.label ?? topicName(topicCode),
      sourceArticleCount: mapped.reduce((sum, node) => sum + (node.sourceArticleCount ?? 0), 0),
      weight: 1,
    }]

  const nodes = [...others, ...cluster, ...mapped]
  const present = new Set(nodes.map((node) => node.id))
  const keptEdges = (graph.edges ?? []).filter(
    (edge) => present.has(edge.sourceId) && present.has(edge.targetId),
  )
  const belongsTo = mapped.map((node) => ({
    sourceId: clusterId(topicCode),
    targetId: node.id,
    relationship: 'BELONGS_TO_TOPIC',
    weight: Math.max(0.34, (node.weight ?? 0.4) * 0.66),
  }))

  return {
    generatedAt: map.generatedAt ?? graph.generatedAt,
    nodes,
    edges: [...keptEdges, ...belongsTo, ...(map.edges ?? [])],
  }
}

/**
 * 지도 응답 → 오른쪽 페이지의 사건 목록.
 *
 * 사건 하나에 붙는 발언은 그 사건과 Edge 로 이어진 STATEMENT 다. 방향은 보지 않는다 —
 * CONTAINS_STATEMENT 는 사건에서 나가지만 다른 관계는 반대로 들어올 수 있고, 화면이 묻는
 * 것은 "이 사건 곁에 있는 발언"이지 관계의 방향이 아니다.
 *
 * 인물·기관(ENTITY)은 뽑지 않는다. 행성에는 서지만 오른쪽 페이지에는 넣지 않기로 했다.
 *
 * 읽은 기사 수가 많은 사건이 위로 온다. 지도 응답에는 시각이 없어서 최근 순으로는 세울 수 없다.
 */
export function eventsFromTopicMap(map) {
  const nodes = map?.nodes ?? []
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const neighbors = new Map(nodes.map((node) => [node.id, []]))

  ;(map?.edges ?? []).forEach((edge) => {
    if (neighbors.has(edge.sourceId) && byId.has(edge.targetId)) {
      neighbors.get(edge.sourceId).push(byId.get(edge.targetId))
    }
    if (neighbors.has(edge.targetId) && byId.has(edge.sourceId)) {
      neighbors.get(edge.targetId).push(byId.get(edge.sourceId))
    }
  })

  return nodes
    .filter((node) => node.nodeType === 'EVENT')
    .map((event) => ({
      id: event.id,
      nodeKey: event.nodeKey,
      title: event.label,
      articleCount: event.sourceArticleCount,
      statements: dedupeById(
        (neighbors.get(event.id) ?? []).filter((node) => node.nodeType === 'STATEMENT'),
      ).map((node) => ({ nodeKey: node.nodeKey, label: node.label })),
    }))
    .sort((left, right) => right.articleCount - left.articleCount)
}

/** 같은 Node 가 두 관계로 이어져 있으면 Edge 두 개를 타고 두 번 들어온다. */
function dedupeById(list) {
  const seen = new Set()
  return list.filter((node) => (seen.has(node.id) ? false : seen.add(node.id)))
}
