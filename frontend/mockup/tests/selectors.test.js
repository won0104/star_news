/** 실제 통합 목업 데이터에서 검색과 탐색 부분집합이 안정적으로 계산되는지 확인합니다. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createMockModel } from "../src/data/repository.js";
import {
  buildExploreHref,
  resolveExplorationPath,
  selectExploration,
  selectHomeTrendPeriod,
  selectSearchNodes,
  selectSearchResults,
} from "../src/data/selectors.js";
import { resolveRoute } from "../src/router.js";

const datasetUrl = new URL("../data/mock/mock_dataset.json", import.meta.url);
const dataset = JSON.parse(await readFile(datasetUrl, "utf8"));
const model = createMockModel(dataset);

test("홈 기간별 트렌드는 네 기간의 seed와 급상승 통계를 같은 계약에서 반환한다", () => {
  assert.deepEqual(dataset.views.home.trend_period_order, [
    "today",
    "week",
    "month",
    "quarter",
  ]);

  const signatures = new Set();
  for (const periodId of dataset.views.home.trend_period_order) {
    const period = selectHomeTrendPeriod(model, periodId);
    assert.equal(period.id, periodId);
    assert.equal(period.seeds.length, 8);
    assert.equal(period.rising.length, 3);
    assert.equal(period.statisticsProvenance.kind, "deterministic_mock");
    assert.ok(period.statisticsProvenance.synthetic);
    assert.ok(period.seeds.every((entry) => (
      entry.node
      && entry.articleCount >= 1
      && entry.previousArticleCount >= 1
      && Number.isInteger(entry.changeRate)
    )));
    assert.ok(period.rising.every((entry) => entry?.isRising && entry.changeRate > 0));
    assert.ok(period.rising.every((entry) => period.seeds.includes(entry)));
    signatures.add(period.seeds.map((entry) => entry.nodeId).join("|"));
  }
  assert.ok(signatures.size >= 2);
});

test("알 수 없는 홈 기간은 오늘 계약으로 안전하게 대체한다", () => {
  const period = selectHomeTrendPeriod(model, "unknown");
  assert.equal(period.id, "today");
  assert.equal(period.title, "오늘 주요 흐름");
});

test("정확한 노드 검색은 대상 노드와 데이터상 이웃을 반환한다", () => {
  const results = selectSearchNodes(model, "삼성전자", 8);
  assert.equal(results[0].id, "entity:samsung-electronics");
  assert.ok(results.some((node) => node.id === "entity:sk-hynix"));
  assert.ok(results.length <= 8);
});

test("검색 결과 관련도는 별 크기에 사용할 수 있도록 내림차순으로 유지된다", () => {
  const results = selectSearchResults(model, "삼성전자", 8);

  assert.equal(results[0].node.id, "entity:samsung-electronics");
  assert.ok(results.every((entry) => Number.isFinite(entry.score) && entry.score > 0));
  assert.ok(results.every((entry, index) => (
    index === 0 || results[index - 1].score >= entry.score
  )));
  assert.deepEqual(
    selectSearchNodes(model, "삼성전자", 8),
    results.map(({ node }) => node),
  );
});

test("탐색 부분집합은 현재 노드의 navigation과 기사 인덱스를 사용한다", () => {
  const exploration = selectExploration(model, "topic:hbm", ["topic:hbm"]);
  assert.equal(exploration.currentNode.label, "HBM");
  assert.deepEqual(
    exploration.neighbors.map(({ node }) => node.id),
    dataset.navigation["topic:hbm"].neighbor_node_ids,
  );
  assert.equal(
    exploration.articles[0].id,
    dataset.navigation["topic:hbm"].article_ids[0],
  );
  assert.ok(exploration.neighbors.every(({ edge }) => edge));
});

test("탐색 주소와 breadcrumb 경로를 같은 순서로 복원한다", () => {
  const path = ["entity:samsung-electronics", "topic:semiconductor-industry", "topic:hbm"];
  const href = buildExploreHref("topic:hbm", path);
  const url = new URL(href, "http://localhost");
  const route = resolveRoute(url.pathname, url.search);

  assert.deepEqual(resolveExplorationPath(model, route), path);
});
