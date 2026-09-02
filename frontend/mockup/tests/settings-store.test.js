/** 설정이 원본 목업 데이터를 바꾸지 않고 저장·복원되는지 확인합니다. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createMockModel } from "../src/data/repository.js";
import {
  applyDisplayPreferences,
  createSettingsStore,
  filterRecommendationSeeds,
} from "../src/data/settings-store.js";
import { resolveSettingsReturnPath } from "../src/pages/settings-page.js";

const datasetUrl = new URL("../data/mock/mock_dataset.json", import.meta.url);
const dataset = JSON.parse(await readFile(datasetUrl, "utf8"));
const model = createMockModel(dataset);

function createMemoryStorage() {
  const values = new Map();
  return {
    getItem(key) {
      return values.get(key) ?? null;
    },
    setItem(key, value) {
      values.set(key, value);
    },
  };
}

test("설정 기본값은 실제 사용자 이름과 명시적 비선호에서 시작한다", () => {
  const store = createSettingsStore(model);
  const state = store.getState();
  assert.equal(state.account.displayName, dataset.user.display_name);
  assert.deepEqual(state.dislikes, dataset.user.not_interested);
  assert.equal(store.findCandidateByLabel("물류")?.id, "topic:logistics");
  assert.equal(store.findCandidateByLabel("존재하지 않는 주제"), null);
});

test("저장한 관심 없음과 화면 설정은 같은 세션 저장소에서 복원된다", () => {
  const storage = createMemoryStorage();
  const first = createSettingsStore(model, { storage });
  first.saveDislikes(["sports", "topic:logistics"]);
  first.saveDisplay({ theme: "dark", fontSize: "large", reducedMotion: true });

  const restored = createSettingsStore(model, { storage }).getState();
  assert.deepEqual(restored.dislikes, ["sports", "topic:logistics"]);
  assert.deepEqual(restored.display, {
    theme: "dark",
    fontSize: "large",
    reducedMotion: true,
  });
});

test("화면 설정은 CSS가 소비할 전역 data 속성으로 변환된다", () => {
  const root = { dataset: {} };
  applyDisplayPreferences(
    { theme: "dark", fontSize: "large", reducedMotion: true },
    root,
  );
  assert.deepEqual(root.dataset, {
    displayTheme: "dark",
    effectiveTheme: "dark",
    fontSize: "large",
    reducedMotion: "true",
  });
});

test("설정 닫기 경로는 앱 내부의 비설정 주소만 허용한다", () => {
  assert.equal(resolveSettingsReturnPath("/my-world/report"), "/my-world/report");
  assert.equal(resolveSettingsReturnPath("https://example.com"), "/");
  assert.equal(resolveSettingsReturnPath("//example.com"), "/");
  assert.equal(resolveSettingsReturnPath("/settings/display"), "/");
});

test("명시적 비선호는 개인 추천 seed에서만 분야 단위로 제외할 수 있다", () => {
  const seeds = dataset.views.home.for_you;
  const firstNode = model.nodeById.get(seeds[0].node_id);
  const filtered = filterRecommendationSeeds(model, seeds, [firstNode.category_id]);
  assert.ok(filtered.length < seeds.length);
  assert.ok(filtered.every((entry) => (
    model.nodeById.get(entry.node_id).category_id !== firstNode.category_id
  )));
  assert.equal(dataset.views.home.today_trends.length, 8);
});
