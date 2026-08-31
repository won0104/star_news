/** 공통 셸용 최근 탐색 변환이 실제 이벤트 순서를 보존하는지 확인합니다. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createMockModel, deriveRecentExplorations } from "../src/data/repository.js";

test("세션별 최신 node_open 한 건을 최근순으로 선택한다", () => {
  const nodes = new Map([
    ["category:economy", { label: "경제" }],
    ["topic:logistics", { label: "물류" }],
    ["topic:hbm", { label: "HBM" }],
  ]);
  const events = [
    {
      type: "node_open",
      session_id: "session:a",
      occurred_at: "2026-08-23T12:00:00Z",
      node_id: "category:economy",
      path: ["category:economy"],
    },
    {
      type: "node_open",
      session_id: "session:a",
      occurred_at: "2026-08-23T12:10:00Z",
      node_id: "topic:logistics",
      path: ["category:economy", "topic:logistics"],
    },
    {
      type: "node_open",
      session_id: "session:b",
      occurred_at: "2026-08-23T12:05:00Z",
      node_id: "topic:hbm",
      path: ["topic:hbm"],
    },
    { type: "article_read", occurred_at: "2026-08-23T12:20:00Z" },
  ];

  const recent = deriveRecentExplorations(events, nodes, 2);
  assert.deepEqual(
    recent.map(({ nodeId, label }) => ({ nodeId, label })),
    [
      { nodeId: "topic:logistics", label: "경제 · 물류" },
      { nodeId: "topic:hbm", label: "HBM" },
    ],
  );
  assert.equal(recent[0].href, "/explore/topic%3Alogistics");
});

test("기간별 홈 통계가 누락된 데이터셋은 로딩 단계에서 거부한다", async () => {
  const datasetUrl = new URL("../data/mock/mock_dataset.json", import.meta.url);
  const dataset = JSON.parse(await readFile(datasetUrl, "utf8"));
  delete dataset.views.home.trend_periods.week;

  assert.throws(
    () => createMockModel(dataset),
    /홈 기간별 트렌드 메타데이터가 올바르지 않습니다: week/,
  );
});
