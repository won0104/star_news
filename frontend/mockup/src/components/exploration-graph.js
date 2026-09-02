/**
 * 현재 노드와 데이터상 직접 이웃만 SVG로 그리는 탐색 그래프입니다.
 * 우측 기사 패널 폭을 항상 확보해 노드 이동 시에도 그래프와 기사 목록을 함께 유지합니다.
 */

import {
  buildExploreHref,
  selectExploration,
} from "../data/selectors.js";
import {
  createWeightNormalizer,
  interpolateWeight,
  roundWeightSize,
} from "../data/weight-scale.js";

const ASSET_BASE = "/design/figma/assets";
const VIEWBOX_WIDTH = 1152;
const VIEWBOX_HEIGHT = 764;
const ARTICLE_PANEL_WIDTH = 360;
const GRAPH_VIEWBOX_WIDTH = VIEWBOX_WIDTH - ARTICLE_PANEL_WIDTH;
const RELATED_NODE_SIZE_MIN = 11;
const RELATED_NODE_SIZE_MAX = 24;
const RELATED_DISTANCE_MIN = 140;
const RELATED_DISTANCE_MAX = 320;
const GRAPH_SAFE_INSET = Object.freeze({
  left: 56,
  right: 56,
  top: 72,
  bottom: 64,
});

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function truncate(value, limit) {
  const normalized = String(value ?? "").replace(/\s+/g, " ").trim();
  return normalized.length > limit ? `${normalized.slice(0, limit).trim()}…` : normalized;
}

function safeExternalUrl(article) {
  if (!article.external_link_available || !article.url) {
    return null;
  }

  try {
    const url = new URL(article.url);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function formatRelativeTime(publishedAt, referenceAt) {
  const published = new Date(publishedAt);
  const reference = new Date(referenceAt);
  if (Number.isNaN(published.getTime()) || Number.isNaN(reference.getTime())) {
    return "시간 정보 없음";
  }

  const minutes = Math.max(0, Math.round((reference - published) / 60_000));
  if (minutes < 60) {
    return `${Math.max(1, minutes)}분 전`;
  }
  if (minutes < 24 * 60) {
    return `${Math.round(minutes / 60)}시간 전`;
  }
  return `${Math.round(minutes / (24 * 60))}일 전`;
}

function createStableRandom(seed) {
  let state = 2166136261;
  for (const character of seed) {
    state ^= character.charCodeAt(0);
    state = Math.imul(state, 16777619);
  }

  return () => {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleAngles(angles, seed) {
  const random = createStableRandom(seed);
  const shuffled = [...angles];

  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }

  return shuffled;
}

function limitDistanceToGraphBounds(center, direction, requestedDistance, graphWidth) {
  const bounds = {
    minX: GRAPH_SAFE_INSET.left,
    maxX: graphWidth - GRAPH_SAFE_INSET.right,
    minY: GRAPH_SAFE_INSET.top,
    maxY: VIEWBOX_HEIGHT - GRAPH_SAFE_INSET.bottom,
  };
  const availableDistances = [requestedDistance];

  if (direction.x > 0) {
    availableDistances.push((bounds.maxX - center.x) / direction.x);
  } else if (direction.x < 0) {
    availableDistances.push((center.x - bounds.minX) / -direction.x);
  }

  if (direction.y > 0) {
    availableDistances.push((bounds.maxY - center.y) / direction.y);
  } else if (direction.y < 0) {
    availableDistances.push((center.y - bounds.minY) / -direction.y);
  }

  return Math.max(0, Math.min(...availableDistances));
}

function getNeighborPositions(
  normalizedWeights,
  graphWidth,
  layoutKey,
  reservePreviousNode = false,
) {
  // 각도 슬롯은 의도적으로 축과 정반대 방향을 살짝 피합니다.
  // 이 안에서 노드 순서만 섞어 자연스러움과 화면 안정성을 함께 유지합니다.
  const defaultAnglesByCount = {
    1: [-82],
    2: [-132, 30],
    3: [-148, -24, 96],
    4: [-150, -48, 14, 105],
    5: [-152, -81, -9, 62, 137],
    6: [-158, -106, -41, 17, 84, 149],
    7: [-155, -105, -54, -6, 47, 99, 151],
    8: [-159, -114, -70, -25, 20, 65, 111, 157],
  };
  const pathAnglesByCount = {
    1: [12],
    2: [-54, 52],
    3: [-68, 18, 142],
    4: [-104, -18, 52, 132],
    5: [-108, -39, 29, 91, 158],
    6: [-109, -57, -8, 47, 103, 156],
    7: [-111, -66, -21, 26, 72, 118, 158],
    8: [-111, -75, -38, 7, 43, 82, 124, 160],
  };
  const anglesByCount = reservePreviousNode ? pathAnglesByCount : defaultAnglesByCount;
  const baseAngles = anglesByCount[Math.min(8, Math.max(1, normalizedWeights.length))] ?? [];
  // 가중치순 이웃에 각도를 그대로 배정하면 큰 별이 한 방향으로 정렬돼 보입니다.
  // 현재 탐색 상태를 seed로 각도만 섞고, 거리는 가중치 계약을 그대로 따릅니다.
  const angles = shuffleAngles(baseAngles, layoutKey);
  const center = { x: graphWidth / 2, y: 432 };

  return angles.map((degrees, index) => {
    const radians = (degrees * Math.PI) / 180;
    const requestedDistance = interpolateWeight(
      normalizedWeights[index],
      RELATED_DISTANCE_MAX,
      RELATED_DISTANCE_MIN,
    );
    const directionX = Math.cos(radians);
    const directionY = Math.sin(radians) * 0.72;
    const directionLength = Math.hypot(directionX, directionY) || 1;
    const direction = {
      x: directionX / directionLength,
      y: directionY / directionLength,
    };
    const distance = limitDistanceToGraphBounds(
      center,
      direction,
      requestedDistance,
      graphWidth,
    );
    return {
      x: center.x + direction.x * distance,
      y: center.y + direction.y * distance,
      angle: degrees,
      requestedDistance,
      boundaryLimited: distance < requestedDistance - 0.5,
    };
  });
}

function renderBreadcrumb(path, model) {
  return path
    .map((nodeId, index) => {
      const node = model.nodeById.get(nodeId);
      if (!node) {
        return "";
      }

      const isCurrent = index === path.length - 1;
      const item = isCurrent
        ? `<span aria-current="page">${escapeHtml(node.label)}</span>`
        : `<a data-route href="${escapeHtml(buildExploreHref(nodeId, path.slice(0, index + 1)))}">${escapeHtml(node.label)}</a>`;
      return `${index > 0 ? '<i aria-hidden="true"></i>' : ""}${item}`;
    })
    .join("");
}

function renderPreviousGhost(path, center, model) {
  const previousNode = model.nodeById.get(path.at(-2));
  if (!previousNode) {
    return "";
  }

  // 그래프에는 직전 별 하나만 남기고, 더 오래된 경로는 breadcrumb에서 복귀합니다.
  const previousPoint = {
    x: Math.max(28, center.x - 252),
    y: center.y - 120,
  };
  const previousPath = path.slice(0, -1);

  return `
    <line
      class="exploration-path-edge"
      x1="${previousPoint.x}"
      y1="${previousPoint.y}"
      x2="${center.x}"
      y2="${center.y}"
    />
    <a
      class="exploration-path-node"
      data-route
      data-transition-focus
      tabindex="0"
      href="${escapeHtml(buildExploreHref(previousNode.id, previousPath))}"
      aria-label="${escapeHtml(previousNode.label)}, 이전 탐색으로 돌아가기"
    >
      <title>${escapeHtml(previousNode.label)} 탐색으로 돌아가기</title>
      <g transform="translate(${previousPoint.x} ${previousPoint.y})">
        <circle class="exploration-path-node__hit" r="24" />
        <image class="exploration-path-node__ring" href="${ASSET_BASE}/node-focus-ring.svg" x="-11" y="-11" width="22" height="22" />
        <image class="exploration-path-node__star" href="${ASSET_BASE}/node-star.svg" x="-4" y="-4" width="8" height="8" />
        <text class="exploration-path-node__label" x="20" y="5">${escapeHtml(previousNode.label)}</text>
      </g>
    </a>
  `;
}

function renderSvg(exploration, path, model) {
  const graphWidth = GRAPH_VIEWBOX_WIDTH;
  const center = { x: graphWidth / 2, y: 432 };
  const normalizeWeight = createWeightNormalizer(
    exploration.neighbors.map(({ edge }) => edge?.weight ?? 0),
  );
  const visualNeighbors = exploration.neighbors.map((entry) => ({
    ...entry,
    normalizedWeight: normalizeWeight(entry.edge?.weight ?? 0),
  }));
  const positions = getNeighborPositions(
    visualNeighbors.map(({ normalizedWeight }) => normalizedWeight),
    graphWidth,
    [
      exploration.currentNode.id,
      path.at(-2) ?? "entry",
      ...visualNeighbors.map(({ node }) => node.id),
    ].join("|"),
    path.length > 1,
  );
  const edges = visualNeighbors
    .map(({ edge, normalizedWeight }, index) => {
      const position = positions[index];
      const width = interpolateWeight(normalizedWeight, 1.05, 1.65).toFixed(2);
      const opacity = interpolateWeight(normalizedWeight, 0.58, 0.82).toFixed(2);
      return `
        <line
          class="exploration-edge"
          data-edge-weight="${escapeHtml(edge?.weight ?? 0)}"
          data-edge-distance="${Math.round(Math.hypot(position.x - center.x, position.y - center.y))}"
          data-edge-target-distance="${Math.round(position.requestedDistance)}"
          data-edge-boundary-limited="${position.boundaryLimited}"
          data-edge-angle="${position.angle}"
          x1="${center.x}"
          y1="${center.y}"
          x2="${position.x}"
          y2="${position.y}"
          stroke-width="${width}"
          style="--edge-index: ${index}; --edge-opacity: ${opacity};"
        />
      `;
    })
    .join("");
  const neighbors = visualNeighbors
    .map(({ node, edge, normalizedWeight }, index) => {
      const position = positions[index];
      const size = roundWeightSize(
        normalizedWeight,
        RELATED_NODE_SIZE_MIN,
        RELATED_NODE_SIZE_MAX,
      );
      const glowSize = Math.round(Math.max(52, size * 3));
      const pathToNode = [...path, node.id];
      const alignEnd = position.x > graphWidth * 0.76;
      const relation = (edge?.relations ?? []).find((value) => value !== "article_cooccurrence");
      const labelOffset = size / 2 + 10;
      const labelX = alignEnd ? -labelOffset : labelOffset;
      const anchor = alignEnd ? "end" : "start";
      return `
        <a
          class="exploration-node"
          data-route
          data-transition-focus
          data-node-size="${size}"
          data-node-weight="${escapeHtml(edge?.weight ?? 0)}"
          data-node-angle="${position.angle}"
          data-node-boundary-limited="${position.boundaryLimited}"
          href="${escapeHtml(buildExploreHref(node.id, pathToNode))}"
          aria-label="${escapeHtml(node.label)}, 다음 탐색 노드${relation ? `, ${relation}` : ""}"
        >
          <title>${escapeHtml([node.label, relation].filter(Boolean).join(" · "))}</title>
          <g transform="translate(${position.x} ${position.y})">
            <g class="exploration-node__arrival" style="--node-index: ${index};">
              <circle class="exploration-node__hit" r="${Math.max(24, size / 2 + 12)}" />
              <image class="exploration-node__glow" href="${ASSET_BASE}/node-selected-glow.svg" x="${-glowSize / 2}" y="${-glowSize / 2}" width="${glowSize}" height="${glowSize}" />
              <circle class="exploration-node__star" r="${size / 2}" />
              <text class="exploration-node__label" x="${labelX}" y="5" text-anchor="${anchor}">${escapeHtml(node.label)}</text>
            </g>
          </g>
        </a>
      `;
    })
    .join("");

  return `
    <svg
      class="exploration-svg"
      viewBox="0 0 ${GRAPH_VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}"
      role="group"
      aria-label="${escapeHtml(exploration.currentNode.label)}에서 이어지는 뉴스 관계"
    >
      <g class="exploration-svg__edges">${edges}</g>
      <g class="exploration-svg__path">${renderPreviousGhost(path, center, model)}</g>
      <g class="exploration-svg__neighbors">${neighbors}</g>
      <g transform="translate(${center.x} ${center.y})">
        <g
          class="exploration-current"
          style="view-transition-name: exploration-focus"
          role="img"
          aria-label="현재 주제 ${escapeHtml(exploration.currentNode.label)}, 관련 기사 ${exploration.articles.length}개"
        >
          <title>현재 선택된 주제 ${escapeHtml(exploration.currentNode.label)}</title>
          <circle class="exploration-current__hit" r="58" />
          <image class="exploration-current__glow" href="${ASSET_BASE}/node-selected-glow.svg" x="-42" y="-42" width="84" height="84" />
          <image class="exploration-current__orbit exploration-current__orbit--outer" href="${ASSET_BASE}/node-selected-orbit-outer.png" x="-130" y="-59" width="260" height="118" />
          <image class="exploration-current__orbit exploration-current__orbit--inner" href="${ASSET_BASE}/node-selected-orbit-inner.svg" x="-90" y="-39" width="180" height="78" />
          <image href="${ASSET_BASE}/node-selected-ring.svg" x="-11" y="-11" width="22" height="22" />
          <circle class="exploration-current__star" r="10" />
          <text class="exploration-current__label" x="32" y="8">${escapeHtml(exploration.currentNode.label)}</text>
        </g>
      </g>
    </svg>
  `;
}

function renderArticle(article, referenceAt) {
  const externalUrl = safeExternalUrl(article);
  const sourceName = article.source?.name ?? "출처 정보 없음";
  const summary = truncate(article.summary || article.description, 92);

  return `
    <article class="article-panel__item">
      <p class="article-panel__meta">${escapeHtml(sourceName)} · ${escapeHtml(formatRelativeTime(article.published_at, referenceAt))}</p>
      <h3>${escapeHtml(article.title)}</h3>
      ${summary ? `<p class="article-panel__summary">${escapeHtml(summary)}</p>` : ""}
      ${externalUrl
        ? `<a href="${escapeHtml(externalUrl)}" target="_blank" rel="noopener noreferrer">원문 보기 <span aria-hidden="true">→</span><span class="sr-only"> (새 창)</span></a>`
        : '<span class="article-panel__unavailable">시연용 기사</span>'}
    </article>
  `;
}

function renderArticlePanel(exploration, model) {
  const firstSummary = exploration.articles[0]?.description
    || exploration.articles[0]?.summary
    || `${exploration.currentNode.label}와 연결된 최근 기사 모음입니다.`;
  const referenceAt = model.dataset.views.home.updated_at;

  return `
    <aside
      class="article-panel"
      id="exploration-article-panel"
      aria-label="${escapeHtml(exploration.currentNode.label)} 관련 기사"
    >
      <div class="article-panel__header">
        <p>RELATED ARTICLES</p>
        <h2>${escapeHtml(exploration.currentNode.label)}</h2>
        <span>관련 기사 ${exploration.articles.length}개 · ${escapeHtml(model.dataset.views.home.trend_window)}</span>
        <p class="article-panel__topic-summary">${escapeHtml(truncate(firstSummary, 112))}</p>
      </div>
      <div class="article-panel__list">
        ${exploration.articles.length > 0
          ? exploration.articles.slice(0, 4).map((article) => renderArticle(article, referenceAt)).join("")
          : '<p class="article-panel__empty">현재 연결된 기사가 없어요.</p>'}
      </div>
    </aside>
  `;
}

/** 탐색 그래프와 현재 노드의 우측 고정 기사 패널을 만듭니다. */
export function createExplorationGraph({ model, currentNodeId, path }) {
  const exploration = selectExploration(model, currentNodeId, path);
  if (!exploration) {
    return null;
  }

  const canvas = document.createElement("div");
  canvas.className = "graph-canvas exploration-canvas has-article-panel";
  canvas.innerHTML = `
    <nav class="exploration-breadcrumb" aria-label="탐색 경로">
      ${renderBreadcrumb(path, model)}
    </nav>
    <p class="exploration-instruction">별을 눌러 다음 관계를 탐색하세요</p>
    ${renderSvg(exploration, path, model)}
    ${renderArticlePanel(exploration, model)}
  `;

  canvas.addEventListener("keydown", (event) => {
    const graphLink = event.target.closest(".exploration-svg a[data-route]");
    if (graphLink && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      graphLink.dispatchEvent(new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        button: 0,
      }));
    }
  });
  return canvas;
}
