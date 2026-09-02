/** 나의 기록 화면의 군집 필터 그래프와 최신순 기록 패널을 결합합니다. */

import { selectReadHistory, selectRecordGraph } from "../data/personal-selectors.js";
import {
  createWeightNormalizer,
  interpolateWeight,
  roundWeightSize,
} from "../data/weight-scale.js";
import { createHistoryPanel } from "./history-panel.js";

const WIDTH = 792;
const HEIGHT = 630;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderEdge(edge, nodeById, selectedCategoryId, normalizedWeight) {
  const source = nodeById.get(edge.source);
  const target = nodeById.get(edge.target);
  if (!source || !target) {
    return "";
  }
  const isDimmed = selectedCategoryId
    && source.category_id !== selectedCategoryId
    && target.category_id !== selectedCategoryId;
  const isCrossCluster = source.category_id !== target.category_id;
  return `
    <line
      class="record-edge ${isDimmed ? "is-dimmed" : ""} ${isCrossCluster ? "is-cross-cluster" : ""}"
      x1="${source.graphX * WIDTH}"
      y1="${source.graphY * HEIGHT}"
      x2="${target.graphX * WIDTH}"
      y2="${target.graphY * HEIGHT}"
      data-edge-weight="${escapeHtml(edge.read_support ?? 0)}"
      style="--cluster-color:${escapeHtml(source.color)};--edge-width:${interpolateWeight(normalizedWeight, 0.95, 1.55).toFixed(2)};--edge-opacity:${interpolateWeight(normalizedWeight, 0.44, 0.72).toFixed(2)}"
    />
  `;
}

function renderNode(node, selectedNodeId, selectedCategoryId, normalizedWeight) {
  const x = node.graphX * WIDTH;
  const y = node.graphY * HEIGHT;
  const isSelected = node.id === selectedNodeId;
  const isDimmed = selectedCategoryId && node.category_id !== selectedCategoryId;
  const size = roundWeightSize(normalizedWeight, 10, 24);
  const ringRadius = (size + 18) / 2;
  const labelOffset = size / 2 + (node.graphKind === "category" ? 8 : 7);
  const count = node.read_count ?? 0;
  return `
    <g
      class="record-node record-node--${node.graphKind} ${isSelected ? "is-selected" : ""} ${isDimmed ? "is-dimmed" : ""}"
      role="button"
      tabindex="0"
      data-record-node="${escapeHtml(node.id)}"
      data-node-size="${size}"
      data-node-weight="${count}"
      aria-label="${escapeHtml(node.label)}, 읽은 기록 ${count}개로 필터"
      aria-pressed="${isSelected}"
      style="--cluster-color:${escapeHtml(node.color)}"
    >
      <circle class="record-node__hit" cx="${x}" cy="${y}" r="${Math.max(24, ringRadius + 5)}" />
      ${node.graphKind === "category" ? `<circle class="record-node__ring" cx="${x}" cy="${y}" r="${ringRadius}" />` : ""}
      ${isSelected ? `<circle class="record-node__selected-orbit" cx="${x}" cy="${y}" r="${ringRadius + 7}" />` : ""}
      <circle class="record-node__dot" cx="${x}" cy="${y}" r="${size / 2}" />
      <text x="${x + labelOffset}" y="${y + 5}">${escapeHtml(node.label)}</text>
    </g>
  `;
}

function renderGraph(graph, selectedNodeId) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const selectedNode = nodeById.get(selectedNodeId);
  const selectedCategoryId = selectedNode?.category_id;
  const normalizeNodeWeight = createWeightNormalizer(
    graph.nodes.map((node) => node.read_count ?? 0),
  );
  const normalizeEdgeWeight = createWeightNormalizer(
    graph.edges.map((edge) => edge.read_support ?? 0),
  );
  return `
    <div class="record-graph">
      <p class="sr-only" role="status" aria-live="polite">${selectedNode
        ? `${escapeHtml(selectedNode.label)} 기록으로 필터했습니다.`
        : "전체 읽은 기록을 표시합니다."}</p>
      <svg width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="group" aria-label="읽은 뉴스의 주요 군집 지도">
        <g class="record-graph__edges">
          ${graph.edges.map((edge) => renderEdge(
            edge,
            nodeById,
            selectedCategoryId,
            normalizeEdgeWeight(edge.read_support ?? 0),
          )).join("")}
        </g>
        <g class="record-graph__nodes">
          ${graph.nodes.map((node) => renderNode(
            node,
            selectedNodeId,
            selectedCategoryId,
            normalizeNodeWeight(node.read_count ?? 0),
          )).join("")}
        </g>
      </svg>
      <a class="record-graph__expand" data-route href="/my-world/map" aria-label="나의 기록 지도 전체 화면으로 열기">
        <span aria-hidden="true"></span>
      </a>
      <p class="record-graph__hint">${selectedNode
        ? "선택한 별을 다시 누르거나 우측에서 필터를 해제하세요"
        : "군집이나 주제를 눌러 기록을 걸러보세요"}</p>
    </div>
  `;
}

/** 군집 선택 상태를 내부에서 관리하며 오른쪽 기록 패널을 다시 필터링합니다. */
export function createRecordClusterView(model) {
  const graph = selectRecordGraph(model);
  const view = document.createElement("div");
  view.className = "record-world";
  let selectedNodeId = null;

  const render = ({ focusNodeId = null, focusHistoryHeading = false } = {}) => {
    const history = selectReadHistory(model, selectedNodeId);
    view.innerHTML = `
      ${renderGraph(graph, selectedNodeId)}
      <div class="record-world__history"></div>
    `;
    view.querySelector(".record-world__history").append(
      createHistoryPanel({
        model,
        history,
        filterClearable: Boolean(selectedNodeId),
      }),
    );
    if (focusNodeId) {
      view.querySelector(`[data-record-node="${CSS.escape(focusNodeId)}"]`)?.focus();
    }
    if (focusHistoryHeading) {
      view.querySelector(".history-panel h2")?.focus({ preventScroll: true });
    }
  };

  const selectNode = (nodeId, keyboard = false) => {
    selectedNodeId = selectedNodeId === nodeId ? null : nodeId;
    render({ focusNodeId: keyboard ? nodeId : null });
  };

  const focusDirectionalNode = (nodeId, key) => {
    const origin = graph.nodes.find((node) => node.id === nodeId);
    if (!origin) {
      return;
    }
    const target = graph.nodes
      .filter((node) => node.id !== nodeId)
      .filter((node) => ({
        ArrowLeft: node.graphX < origin.graphX,
        ArrowRight: node.graphX > origin.graphX,
        ArrowUp: node.graphY < origin.graphY,
        ArrowDown: node.graphY > origin.graphY,
      })[key])
      .map((node) => {
        const dx = Math.abs(node.graphX - origin.graphX);
        const dy = Math.abs(node.graphY - origin.graphY);
        const primary = ["ArrowLeft", "ArrowRight"].includes(key) ? dx : dy;
        const secondary = ["ArrowLeft", "ArrowRight"].includes(key) ? dy : dx;
        return { node, score: primary + secondary * 1.7 };
      })
      .sort((left, right) => left.score - right.score)[0]?.node;
    if (target) {
      view.querySelector(`[data-record-node="${CSS.escape(target.id)}"]`)?.focus();
    }
  };

  view.addEventListener("click", (event) => {
    const node = event.target.closest("[data-record-node]");
    if (node) {
      selectNode(node.dataset.recordNode);
    }
  });
  view.addEventListener("keydown", (event) => {
    const node = event.target.closest("[data-record-node]");
    if (node && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      selectNode(node.dataset.recordNode, true);
      return;
    }
    if (node && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      focusDirectionalNode(node.dataset.recordNode, event.key);
    }
  });
  view.addEventListener("historyfilterclear", () => {
    selectedNodeId = null;
    render({ focusHistoryHeading: true });
  });

  render();
  return view;
}
