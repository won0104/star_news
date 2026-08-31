/** 공통 가중치가 화면별 시각 범위를 벗어나지 않고 순서를 보존하는지 확인합니다. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  createWeightNormalizer,
  interpolateWeight,
  roundWeightSize,
} from "../src/data/weight-scale.js";

test("가중치 정규화는 제곱근 곡선으로 순서와 양 끝을 보존한다", () => {
  const normalize = createWeightNormalizer([1, 4, 9]);

  assert.equal(normalize(1), 0);
  assert.equal(normalize(4), 0.5);
  assert.equal(normalize(9), 1);
  assert.ok(normalize(1) < normalize(4));
  assert.ok(normalize(4) < normalize(9));
});

test("동일하거나 비정상인 값은 중간 가중치로 안전하게 표시한다", () => {
  const normalizeSame = createWeightNormalizer([4, 4, 4]);
  const normalizeEmpty = createWeightNormalizer([]);

  assert.equal(normalizeSame(4), 0.5);
  assert.equal(normalizeEmpty(100), 0.5);
});

test("화면별 크기와 역방향 거리 범위를 정확히 만든다", () => {
  assert.equal(roundWeightSize(0, 11, 24), 11);
  assert.equal(roundWeightSize(1, 11, 24), 24);
  assert.equal(interpolateWeight(0, 320, 140), 320);
  assert.equal(interpolateWeight(1, 320, 140), 140);
});
