/**
 * 개인 기록 전체 부분집합을 1800×1200 SVG 작업공간에 렌더링합니다.
 * 탐색 화면의 단계 전환과 달리 viewBox 기반 drag pan, wheel·pinch zoom을 제공합니다.
 */

import { selectPersonalMap, selectReadHistory } from "../data/personal-selectors.js";
import {
  createWeightNormalizer,
  interpolateWeight,
  roundWeightSize,
} from "../data/weight-scale.js";
import { createHistoryPanel } from "./history-panel.js";

const WORKSPACE_WIDTH = 1800;
const WORKSPACE_HEIGHT = 1200;
const VIEW_WIDTH = 1384;
const VIEW_HEIGHT = 788;
const MIN_ZOOM = 0.75;
const MAX_ZOOM = 2.2;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function positionNode(node) {
  return {
    x: 60 + node.layout.personal_map.x * 1680,
    y: 35 + node.layout.personal_map.y * 1080,
  };
}

function renderEdge(edge, nodeById, positionById, normalizedWeight) {
  const source = nodeById.get(edge.source);
  const target = nodeById.get(edge.target);
  const sourcePosition = positionById.get(edge.source);
  const targetPosition = positionById.get(edge.target);
  if (!source || !target || !sourcePosition || !targetPosition) {
    return "";
  }
  const opacity = interpolateWeight(normalizedWeight, 0.42, 0.72).toFixed(2);
  const width = interpolateWeight(normalizedWeight, 1, 2.4).toFixed(2);
  return `
    <line
      class="personal-map-edge"
      data-edge-source="${escapeHtml(edge.source)}"
      data-edge-target="${escapeHtml(edge.target)}"
      data-edge-weight="${escapeHtml(edge.read_support ?? 0)}"
      x1="${sourcePosition.x}"
      y1="${sourcePosition.y}"
      x2="${targetPosition.x}"
      y2="${targetPosition.y}"
      style="--edge-color:${escapeHtml(source.color)};--edge-opacity:${opacity};--edge-width:${width}"
    />
  `;
}

function renderNode(node, position, normalizedWeight) {
  const isCategory = node.graphKind === "category";
  const size = roundWeightSize(normalizedWeight, 7, 28);
  const radius = size / 2;
  const ringRadius = (size + 22) / 2;
  const labelOffset = radius + (isCategory ? 10 : 8);
  return `
    <g
      class="personal-map-node personal-map-node--${node.graphKind}"
      transform="translate(${position.x} ${position.y})"
      role="button"
      tabindex="0"
      data-map-node="${escapeHtml(node.id)}"
      data-node-size="${size}"
      data-node-weight="${escapeHtml(node.read_count ?? 0)}"
      aria-label="${escapeHtml(node.label)} 기록 ${node.read_count ?? 0}개 보기"
      aria-pressed="false"
      style="--node-color:${escapeHtml(node.color)}"
    >
      <circle class="personal-map-node__hit" r="${Math.max(25, ringRadius + 7)}" />
      <circle class="personal-map-node__selected-orbit" r="${ringRadius + 7}" />
      ${isCategory ? `<circle class="personal-map-node__ring" r="${ringRadius}" />` : ""}
      <circle class="personal-map-node__dot" r="${radius}" />
      <text x="${labelOffset}" y="${isCategory ? 7 : 5}">${escapeHtml(node.label)}</text>
    </g>
  `;
}

function renderLegend() {
  return `
    <div class="personal-map-legend" aria-label="노드 종류 안내">
      <span><i class="is-category"></i>분야</span>
      <span><i class="is-topic"></i>주제</span>
      <span><i class="is-entity"></i>인물·기업·기관·지역</span>
      <span><i class="is-event"></i>정책·사건</span>
    </div>
  `;
}

/** 전체 개인 지도 오버레이를 생성합니다. */
export function createPersonalMap(model, { navigate } = {}) {
  const graph = selectPersonalMap(model);
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const positionById = new Map(graph.nodes.map((node) => [node.id, positionNode(node)]));
  const normalizeNodeWeight = createWeightNormalizer(
    graph.nodes.map((node) => node.read_count ?? 0),
  );
  const normalizeEdgeWeight = createWeightNormalizer(
    graph.edges.map((edge) => edge.read_support ?? 0),
  );
  const view = document.createElement("section");
  view.className = "personal-map-overlay";
  view.dataset.screen = "personal-map";
  view.dataset.documentTitle = "나의 기록 지도";
  view.setAttribute("role", "dialog");
  view.setAttribute("aria-modal", "true");
  view.setAttribute("aria-labelledby", "personal-map-title");
  view.setAttribute("aria-describedby", "personal-map-hint");
  view.innerHTML = `
    <div class="personal-map-shell">
      <header class="personal-map-header">
        <h1 id="personal-map-title">나의 기록 지도</h1>
        <p>읽은 기록에서 이어진 ${graph.nodes.length}개 노드</p>
        <a data-route data-route-focus href="/my-world/records">← 나의 기록으로</a>
      </header>
      <div class="personal-map-viewport">
        <svg
          class="personal-map-svg"
          viewBox="0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}"
          role="group"
          tabindex="0"
          aria-label="확대와 이동이 가능한 나의 전체 뉴스 기록 지도"
        >
          <defs>
            <pattern id="personal-map-dots" width="80" height="80" patternUnits="userSpaceOnUse">
              <circle cx="40" cy="40" r="1.3" fill="#607180" opacity="0.25" />
            </pattern>
          </defs>
          <rect width="${WORKSPACE_WIDTH}" height="${WORKSPACE_HEIGHT}" fill="url(#personal-map-dots)" />
          <g class="personal-map-edges">
            ${graph.edges.map((edge) => renderEdge(
              edge,
              nodeById,
              positionById,
              normalizeEdgeWeight(edge.read_support ?? 0),
            )).join("")}
          </g>
          <g class="personal-map-nodes">
            ${graph.nodes.map((node) => renderNode(
              node,
              positionById.get(node.id),
              normalizeNodeWeight(node.read_count ?? 0),
            )).join("")}
          </g>
        </svg>
      </div>
      ${renderLegend()}
      <p class="personal-map-hint" id="personal-map-hint">드래그로 이동 · 휠 또는 트랙패드로 확대·축소 · 노드를 누르면 읽은 기록이 열립니다</p>
      <div class="personal-map-zoom" aria-label="지도 확대 축소">
        <button type="button" data-map-action="zoom-out" aria-label="축소">−</button>
        <output aria-live="polite">100%</output>
        <button type="button" data-map-action="zoom-in" aria-label="확대">＋</button>
      </div>
    </div>
  `;

  const shell = view.querySelector(".personal-map-shell");
  const svg = view.querySelector(".personal-map-svg");
  const zoomOutput = view.querySelector(".personal-map-zoom output");
  const pointers = new Map();
  const state = { x: 0, y: 0, zoom: 1, selectedNodeId: null };
  let panStart = null;
  let pinchStart = null;

  const dimensions = () => ({
    width: VIEW_WIDTH / state.zoom,
    height: VIEW_HEIGHT / state.zoom,
  });

  const clampPosition = () => {
    const { width, height } = dimensions();
    state.x = clamp(state.x, 0, Math.max(0, WORKSPACE_WIDTH - width));
    state.y = clamp(state.y, 0, Math.max(0, WORKSPACE_HEIGHT - height));
  };

  const updateViewBox = () => {
    clampPosition();
    const { width, height } = dimensions();
    svg.setAttribute("viewBox", `${state.x} ${state.y} ${width} ${height}`);
    zoomOutput.value = `${Math.round(state.zoom * 100)}%`;
    zoomOutput.textContent = zoomOutput.value;
  };

  const zoomAt = (nextZoom, screenX = 0.5, screenY = 0.5) => {
    const previous = dimensions();
    const anchorX = state.x + previous.width * screenX;
    const anchorY = state.y + previous.height * screenY;
    state.zoom = clamp(nextZoom, MIN_ZOOM, MAX_ZOOM);
    const next = dimensions();
    state.x = anchorX - next.width * screenX;
    state.y = anchorY - next.height * screenY;
    updateViewBox();
  };

  const updateSelection = () => {
    svg.querySelectorAll("[data-map-node]").forEach((node) => {
      const selected = node.dataset.mapNode === state.selectedNodeId;
      node.classList.toggle("is-selected", selected);
      node.setAttribute("aria-pressed", String(selected));
    });
    svg.querySelectorAll(".personal-map-edge").forEach((edge) => {
      edge.classList.toggle(
        "is-related",
        edge.dataset.edgeSource === state.selectedNodeId
        || edge.dataset.edgeTarget === state.selectedNodeId,
      );
    });
    svg.classList.toggle("has-selection", Boolean(state.selectedNodeId));
  };

  const closePanel = ({ focusNode = false } = {}) => {
    shell.querySelector(".history-panel")?.remove();
    shell.classList.remove("has-history-panel");
    if (focusNode && state.selectedNodeId) {
      svg.querySelector(`[data-map-node="${CSS.escape(state.selectedNodeId)}"]`)?.focus();
    }
    state.selectedNodeId = null;
    updateSelection();
  };

  const openNode = (nodeId, { keyboard = false } = {}) => {
    state.selectedNodeId = nodeId;
    updateSelection();
    shell.querySelector(".history-panel")?.remove();
    const panel = createHistoryPanel({
      model,
      history: selectReadHistory(model, nodeId),
      closeable: true,
    });
    shell.append(panel);
    shell.classList.add("has-history-panel");
    if (keyboard) {
      panel.querySelector(".history-panel__close")?.focus();
    }
  };

  const pointerCenter = () => {
    const values = [...pointers.values()];
    return {
      x: values.reduce((sum, point) => sum + point.x, 0) / values.length,
      y: values.reduce((sum, point) => sum + point.y, 0) / values.length,
    };
  };

  const pointerDistance = () => {
    const [first, second] = [...pointers.values()];
    return Math.hypot(second.x - first.x, second.y - first.y);
  };

  const focusDirectionalNode = (nodeId, key) => {
    const origin = positionById.get(nodeId);
    if (!origin) {
      return;
    }
    const candidates = graph.nodes
      .filter((node) => node.id !== nodeId)
      .map((node) => ({ node, position: positionById.get(node.id) }))
      .filter(({ position }) => {
        const dx = position.x - origin.x;
        const dy = position.y - origin.y;
        return {
          ArrowLeft: dx < 0,
          ArrowRight: dx > 0,
          ArrowUp: dy < 0,
          ArrowDown: dy > 0,
        }[key];
      })
      .map(({ node, position }) => {
        const dx = Math.abs(position.x - origin.x);
        const dy = Math.abs(position.y - origin.y);
        const primary = ["ArrowLeft", "ArrowRight"].includes(key) ? dx : dy;
        const secondary = ["ArrowLeft", "ArrowRight"].includes(key) ? dy : dx;
        return { node, position, score: primary + secondary * 1.7 };
      })
      .sort((left, right) => left.score - right.score);
    const target = candidates[0];
    if (!target) {
      return;
    }

    const { width, height } = dimensions();
    const margin = 72 / state.zoom;
    if (target.position.x < state.x + margin) state.x = target.position.x - margin;
    if (target.position.x > state.x + width - margin) state.x = target.position.x - width + margin;
    if (target.position.y < state.y + margin) state.y = target.position.y - margin;
    if (target.position.y > state.y + height - margin) state.y = target.position.y - height + margin;
    updateViewBox();
    svg.querySelector(`[data-map-node="${CSS.escape(target.node.id)}"]`)?.focus();
  };

  const beginPinch = () => {
    const rect = svg.getBoundingClientRect();
    const center = pointerCenter();
    const normalized = {
      x: (center.x - rect.left) / rect.width,
      y: (center.y - rect.top) / rect.height,
    };
    const current = dimensions();
    pinchStart = {
      distance: Math.max(1, pointerDistance()),
      zoom: state.zoom,
      normalized,
      anchorX: state.x + current.width * normalized.x,
      anchorY: state.y + current.height * normalized.y,
    };
    panStart = null;
  };

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    const screenX = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    const screenY = clamp((event.clientY - rect.top) / rect.height, 0, 1);
    zoomAt(state.zoom * Math.exp(-event.deltaY * 0.0012), screenX, screenY);
  }, { passive: false });

  svg.addEventListener("pointerdown", (event) => {
    if (event.target.closest("[data-map-node]")) {
      return;
    }
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    svg.setPointerCapture(event.pointerId);
    shell.classList.add("is-panning");
    if (pointers.size === 1) {
      panStart = { x: event.clientX, y: event.clientY, viewX: state.x, viewY: state.y };
    } else if (pointers.size === 2) {
      beginPinch();
    }
  });

  svg.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) {
      return;
    }
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const rect = svg.getBoundingClientRect();
    if (pointers.size === 2 && pinchStart) {
      const ratio = pointerDistance() / pinchStart.distance;
      state.zoom = clamp(pinchStart.zoom * ratio, MIN_ZOOM, MAX_ZOOM);
      const next = dimensions();
      const center = pointerCenter();
      const normalizedX = clamp((center.x - rect.left) / rect.width, 0, 1);
      const normalizedY = clamp((center.y - rect.top) / rect.height, 0, 1);
      state.x = pinchStart.anchorX - next.width * normalizedX;
      state.y = pinchStart.anchorY - next.height * normalizedY;
      updateViewBox();
      return;
    }
    if (pointers.size === 1 && panStart) {
      const current = dimensions();
      state.x = panStart.viewX - ((event.clientX - panStart.x) / rect.width) * current.width;
      state.y = panStart.viewY - ((event.clientY - panStart.y) / rect.height) * current.height;
      updateViewBox();
    }
  });

  const endPointer = (event) => {
    pointers.delete(event.pointerId);
    if (pointers.size === 1) {
      const [point] = pointers.values();
      panStart = { x: point.x, y: point.y, viewX: state.x, viewY: state.y };
      pinchStart = null;
    } else if (pointers.size === 0) {
      panStart = null;
      pinchStart = null;
      shell.classList.remove("is-panning");
    }
  };
  svg.addEventListener("pointerup", endPointer);
  svg.addEventListener("pointercancel", endPointer);

  svg.addEventListener("click", (event) => {
    const node = event.target.closest("[data-map-node]");
    if (node) {
      openNode(node.dataset.mapNode);
    }
  });

  svg.addEventListener("keydown", (event) => {
    const node = event.target.closest("[data-map-node]");
    if (node && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      openNode(node.dataset.mapNode, { keyboard: true });
      return;
    }
    if (node && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      focusDirectionalNode(node.dataset.mapNode, event.key);
      return;
    }
    const amount = 42 / state.zoom;
    const moves = {
      ArrowLeft: [-amount, 0],
      ArrowRight: [amount, 0],
      ArrowUp: [0, -amount],
      ArrowDown: [0, amount],
    };
    if (moves[event.key]) {
      event.preventDefault();
      state.x += moves[event.key][0];
      state.y += moves[event.key][1];
      updateViewBox();
    }
    if (["+", "="].includes(event.key)) {
      event.preventDefault();
      zoomAt(state.zoom + 0.2);
    }
    if (event.key === "-") {
      event.preventDefault();
      zoomAt(state.zoom - 0.2);
    }
  });

  view.addEventListener("click", (event) => {
    if (event.target.closest('[data-map-action="zoom-in"]')) {
      zoomAt(state.zoom + 0.2);
    }
    if (event.target.closest('[data-map-action="zoom-out"]')) {
      zoomAt(state.zoom - 0.2);
    }
  });
  view.addEventListener("historyclose", (event) => {
    closePanel({ focusNode: Boolean(event.detail?.keyboard) });
  });
  view.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    event.preventDefault();
    if (state.selectedNodeId) {
      closePanel({ focusNode: true });
    } else if (typeof navigate === "function") {
      navigate("/my-world/records");
    }
  });

  updateViewBox();
  return view;
}
