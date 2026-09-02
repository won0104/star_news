/** 탐색 경로와 현재 노드의 SVG 이웃 그래프를 조립하는 전체 캔버스 화면입니다. */

import { createExplorationGraph } from "../components/exploration-graph.js";
import { resolveExplorationPath } from "../data/selectors.js";

export function createExplorationPage(route, model) {
  const currentNode = model.nodeById.get(route.params.nodeId);
  const page = document.createElement("section");
  page.className = "page-stage exploration-page";
  page.dataset.screen = "explore";

  if (!currentNode) {
    page.dataset.documentTitle = "뉴스 관계 탐색";
    page.innerHTML = `
      <div class="exploration-entry">
        <h1 tabindex="-1">탐색을 시작할 별을 선택해 주세요.</h1>
        <p>홈, 분야별 탐색 또는 찾아보기에서 관심 있는 주제를 고를 수 있어요.</p>
        <a data-route href="/">홈에서 별 고르기</a>
      </div>
    `;
    return page;
  }

  const path = resolveExplorationPath(model, route);
  const graph = createExplorationGraph({
    model,
    currentNodeId: currentNode.id,
    path,
  });
  page.dataset.documentTitle = `${currentNode.label} 탐색`;
  const heading = document.createElement("h1");
  heading.className = "sr-only";
  heading.tabIndex = -1;
  heading.textContent = `${currentNode.label} 뉴스 관계 탐색`;
  page.append(heading, graph);
  return page;
}
