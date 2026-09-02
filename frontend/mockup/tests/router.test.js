/** 라우팅 계약이 화면 주소를 안정적으로 해석하는지 확인합니다. */

import assert from "node:assert/strict";
import test from "node:test";

import { resolveRoute } from "../src/router.js";

test("주요 정적 화면을 해석한다", () => {
  assert.equal(resolveRoute("/").id, "home");
  assert.equal(resolveRoute("/search").id, "search");
  assert.equal(resolveRoute("/my-world/records").id, "records");
  assert.equal(resolveRoute("/my-world/report").id, "report");
  assert.equal(resolveRoute("/my-world/map").id, "personalMap");
});

test("분야와 탐색 노드 매개변수를 복원한다", () => {
  assert.deepEqual(resolveRoute("/category/economy/").params, {
    categoryId: "economy",
  });
  assert.deepEqual(resolveRoute("/explore/topic%3Ahbm").params, {
    nodeId: "topic:hbm",
  });
});

test("검색 query와 반복 탐색 경로를 보존한다", () => {
  const trendRoute = resolveRoute("/", "?period=quarter");
  assert.equal(trendRoute.searchParams.get("period"), "quarter");

  const searchRoute = resolveRoute("/search", "?q=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90");
  assert.equal(searchRoute.searchParams.get("q"), "삼성전자");

  const explorationRoute = resolveRoute(
    "/explore/topic%3Ahbm",
    "?path=entity%3Asamsung-electronics&path=topic%3Ahbm",
  );
  assert.deepEqual(explorationRoute.searchParams.getAll("path"), [
    "entity:samsung-electronics",
    "topic:hbm",
  ]);
});

test("설정 섹션은 합의된 세 경로만 허용한다", () => {
  assert.equal(resolveRoute("/settings/account").params.section, "account");
  assert.equal(resolveRoute("/settings/dislikes").params.section, "dislikes");
  assert.equal(resolveRoute("/settings/display").params.section, "display");
  assert.equal(resolveRoute("/settings/unknown").id, "notFound");
});

test("알 수 없는 주소는 404 경로로 보낸다", () => {
  const route = resolveRoute("/this-does-not-exist");
  assert.equal(route.id, "notFound");
  assert.equal(route.isNotFound, true);
});
