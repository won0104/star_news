/**
 * 그래프별 원시 가중치를 화면 안에서 비교 가능한 0~1 값으로 정규화합니다.
 * 제곱근 곡선은 큰 값 하나가 나머지 시각 차이를 삼키지 않도록 완화합니다.
 */

function clamp(value, minimum = 0, maximum = 1) {
  return Math.min(maximum, Math.max(minimum, value));
}

function toWeight(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, number) : 0;
}

/** 현재 화면의 값들을 기준으로 0~1 정규화 함수를 만듭니다. */
export function createWeightNormalizer(values) {
  const transformed = values.map((value) => Math.sqrt(toWeight(value)));
  if (transformed.length === 0) {
    return () => 0.5;
  }

  const minimum = Math.min(...transformed);
  const maximum = Math.max(...transformed);
  const range = maximum - minimum;

  if (range <= Number.EPSILON) {
    return () => 0.5;
  }

  return (value) => clamp((Math.sqrt(toWeight(value)) - minimum) / range);
}

/** 정규화된 가중치를 지정 범위의 연속 값으로 변환합니다. */
export function interpolateWeight(normalizedWeight, minimum, maximum) {
  return minimum + (maximum - minimum) * clamp(Number(normalizedWeight) || 0);
}

/** 별 지름처럼 픽셀 경계가 선명해야 하는 값은 정수로 반환합니다. */
export function roundWeightSize(normalizedWeight, minimum, maximum) {
  return Math.round(interpolateWeight(normalizedWeight, minimum, maximum));
}
