/**
 * 홈·카테고리·찾아보기의 seed 노드를 가중치와 무관한 별자리로 배치합니다.
 * 같은 화면 상태에서는 좌표를 재현하며, 관계 엣지나 의미 기반 거리는 그리지 않습니다.
 */

import { buildExploreHref } from "../data/selectors.js";
import { createWeightNormalizer, roundWeightSize } from "../data/weight-scale.js";

const ASSET_BASE = "/design/figma/assets";
const SEED_SIZE_MIN = 11;
const SEED_SIZE_MAX = 24;
const SEED_LAYOUT_SLOTS = [
  { x: 0.18, y: 0.21 },
  { x: 0.51, y: 0.14 },
  { x: 0.82, y: 0.27 },
  { x: 0.33, y: 0.43 },
  { x: 0.69, y: 0.48 },
  { x: 0.15, y: 0.72 },
  { x: 0.49, y: 0.8 },
  { x: 0.82, y: 0.73 },
];

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function hashString(value) {
  let hash = 2166136261;
  for (const character of String(value)) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function createSeededRandom(seed) {
  let state = hashString(seed) || 0x6d2b79f5;
  return () => {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

/** 같은 layout seed에는 같은 비정렬 별자리 좌표를 반환합니다. */
export function createScatteredSeedPositions(layoutSeed, count) {
  const random = createSeededRandom(layoutSeed);
  const slots = SEED_LAYOUT_SLOTS.map((slot) => ({ ...slot }));

  for (let index = slots.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [slots[index], slots[swapIndex]] = [slots[swapIndex], slots[index]];
  }

  return slots.slice(0, count).map((slot) => ({
    x: clamp(slot.x + (random() - 0.5) * 0.055, 0.08, 0.9),
    y: clamp(slot.y + (random() - 0.5) * 0.055, 0.1, 0.86),
  }));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatKoreanTimestamp(isoString) {
  if (!isoString) {
    return "";
  }

  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function renderSeedNode(entry, node, index, normalizedWeight) {
  const x = Math.min(0.9, Math.max(0.08, Number(entry.x) || 0.5));
  const y = Math.min(0.86, Math.max(0.1, Number(entry.y) || 0.5));
  const size = roundWeightSize(normalizedWeight, SEED_SIZE_MIN, SEED_SIZE_MAX);
  const ringSize = size + 22;
  const glowSize = Math.round(Math.max(58, size * 3.1));

  return `
    <a
      class="seed-node ${x > 0.68 ? "is-right-aligned" : ""}"
      data-route
      data-transition-focus
      data-node-id="${escapeHtml(node.id)}"
      data-node-index="${index}"
      data-node-size="${size}"
      data-node-weight="${escapeHtml(entry.visual_weight ?? node.trend_score ?? 0)}"
      data-node-x="${x.toFixed(4)}"
      data-node-y="${y.toFixed(4)}"
      href="${escapeHtml(buildExploreHref(node.id))}"
      aria-label="${escapeHtml(node.label)}, 이 별에서 탐색 시작"
      style="--node-x: ${x * 100}%; --node-y: ${y * 100}%; --seed-index: ${index}; --seed-size: ${size}px; --seed-ring-size: ${ringSize}px; --seed-glow-size: ${glowSize}px; --seed-translate-x: ${x > 0.68 ? "calc(-100% + 15px)" : "-15px"};"
    >
      <span class="seed-node__visual" aria-hidden="true">
        <img class="seed-node__glow" src="${ASSET_BASE}/node-selected-glow.svg" alt="" />
        <img class="seed-node__ring" src="${ASSET_BASE}/node-selected-ring.svg" alt="" />
        <img class="seed-node__star" src="${ASSET_BASE}/node-star.svg" alt="" />
      </span>
      <span class="seed-node__label">${escapeHtml(node.label)}</span>
    </a>
  `;
}

/** 선택적으로 결정적 랜덤 좌표를 사용하는 어두운 seed 그래프 DOM을 만듭니다. */
export function createSeedCanvas({
  model,
  seeds,
  ariaLabel,
  instruction,
  updatedAt,
  windowLabel = "",
  previewText,
  centerElement,
  emptyMessage = "표시할 주제를 찾지 못했어요.",
  variant = "default",
  layoutSeed = "",
}) {
  const sourceSeeds = seeds
    .map((entry) => ({ entry, node: model.nodeById.get(entry.node_id) }))
    .filter(({ node }) => node);
  const scatteredPositions = layoutSeed
    ? createScatteredSeedPositions(layoutSeed, sourceSeeds.length)
    : [];
  const resolvedSeeds = sourceSeeds.map((resolved, index) => ({
    ...resolved,
    entry: scatteredPositions[index]
      ? { ...resolved.entry, ...scatteredPositions[index] }
      : resolved.entry,
  }));
  const weightFor = ({ entry, node }) => (
    entry.visual_weight
    ?? entry.article_count
    ?? node.trend_score
    ?? node.personal_score
    ?? 0
  );
  const normalizeWeight = createWeightNormalizer(resolvedSeeds.map(weightFor));
  const canvas = document.createElement("div");
  canvas.className = `graph-canvas seed-canvas seed-canvas--${variant}`;
  canvas.setAttribute("role", "region");
  canvas.setAttribute("aria-label", ariaLabel);
  canvas.innerHTML = `
    <p class="graph-canvas__instruction">${escapeHtml(instruction)}</p>
    <div class="seed-canvas__nodes">
      ${resolvedSeeds
        .map((resolved, index) => renderSeedNode(
          resolved.entry,
          resolved.node,
          index,
          normalizeWeight(weightFor(resolved)),
        ))
        .join("")}
    </div>
    <div class="seed-preview" role="status" hidden>
      <strong></strong>
      <p></p>
    </div>
    ${resolvedSeeds.length === 0 && emptyMessage ? `<p class="seed-canvas__empty">${escapeHtml(emptyMessage)}</p>` : ""}
    <p class="graph-canvas__timestamp">
      ${escapeHtml([windowLabel, formatKoreanTimestamp(updatedAt)].filter(Boolean).join(" · "))}${updatedAt ? " 기준" : ""}
    </p>
  `;

  if (centerElement) {
    const center = document.createElement("div");
    center.className = "seed-canvas__center";
    center.append(centerElement);
    canvas.append(center);
  }

  const preview = canvas.querySelector(".seed-preview");
  const previewTitle = preview.querySelector("strong");
  const previewBody = preview.querySelector("p");

  const showPreview = (link) => {
    const index = Number(link.dataset.nodeIndex);
    const resolved = resolvedSeeds[index];
    if (!resolved) {
      return;
    }

    const x = Math.min(0.9, Math.max(0.08, Number(resolved.entry.x) || 0.5));
    const y = Math.min(0.86, Math.max(0.1, Number(resolved.entry.y) || 0.5));
    previewTitle.textContent = resolved.node.label;
    previewBody.textContent = previewText(resolved.node, resolved.entry);
    preview.style.left = `${x * 100}%`;
    preview.style.top = `${Math.min(0.8, y + 0.07) * 100}%`;
    preview.classList.toggle("is-left-aligned", x > 0.68);
    preview.hidden = false;
  };

  const hidePreview = () => {
    preview.hidden = true;
  };

  canvas.querySelectorAll(".seed-node").forEach((link) => {
    link.addEventListener("mouseenter", () => showPreview(link));
    link.addEventListener("mouseleave", hidePreview);
    link.addEventListener("focus", () => showPreview(link));
    link.addEventListener("blur", hidePreview);
  });

  return canvas;
}
