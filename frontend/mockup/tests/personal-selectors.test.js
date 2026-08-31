/** 실제 목업 기록에서 개인 그래프와 리포트 집계가 재현되는지 확인합니다. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createMockModel } from "../src/data/repository.js";
import {
  selectPersonalMap,
  selectPersonalReport,
  selectReadHistory,
  selectRecordGraph,
} from "../src/data/personal-selectors.js";

const datasetUrl = new URL("../data/mock/mock_dataset.json", import.meta.url);
const dataset = JSON.parse(await readFile(datasetUrl, "utf8"));
const model = createMockModel(dataset);

test("전체 기록은 리포트의 열람 수와 같고 최신순으로 정렬된다", () => {
  const history = selectReadHistory(model);
  assert.equal(history.entries.length, dataset.user_report.overview.articles_read);
  assert.ok(history.entries[0].occurredAt >= history.entries.at(-1).occurredAt);
  assert.ok(history.entries.every((entry) => entry.article && entry.sourceName));
});

test("기록 요약 그래프는 상위 네 군집과 실제 데이터 엣지를 사용한다", () => {
  const graph = selectRecordGraph(model);
  assert.equal(graph.nodes.filter((node) => node.graphKind === "category").length, 4);
  assert.equal(graph.nodes.length, 16);
  assert.ok(graph.edges.length >= 12);
  assert.ok(graph.edges.every((edge) => model.edgeByPair.has(
    [edge.source, edge.target].sort().join("\u0000"),
  )));
  assert.ok(graph.edges.every((edge) => (
    edge.relations?.includes("category_membership") || edge.read_support > 0
  )));
});

test("전체 개인 지도는 읽은 노드를 강한 관계와 최소 구조선으로 연결한다", () => {
  const graph = selectPersonalMap(model);
  assert.equal(graph.nodes.length, 58);
  assert.ok(graph.edges.length >= graph.nodes.length / 2);
  assert.ok(graph.edges.length < 78);
  assert.ok(graph.nodes.every((node) => node.read_count > 0));
  assert.ok(graph.edges.every((edge) => (
    edge.read_support > 0 || edge.relations?.includes("category_membership")
  )));
  assert.ok(graph.nodes.every((node) => graph.edges.some((edge) => (
    edge.source === node.id || edge.target === node.id
  ))));
});

test("개인 리포트는 12주와 출처 비중을 열람 이벤트에서 집계한다", () => {
  const report = selectPersonalReport(model);
  assert.equal(report.categoryDistribution[0].category_id, "economy");
  assert.equal(report.weeklyReading.buckets.length, 12);
  assert.ok(report.terrain.length > 0);
  const sourceRatio = report.sourceDistribution.segments
    .reduce((sum, entry) => sum + entry.ratio, 0);
  assert.ok(Math.abs(sourceRatio - 1) < Number.EPSILON * 8);
});
