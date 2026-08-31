/**
 * 별빛 뉴스 목업의 진입점입니다.
 * 통합 데이터를 한 번 로드하고 공통 셸, 화면 레지스트리, 라우터를 연결합니다.
 */

import { createAppShell } from "./components/app-shell.js";
import { loadMockModel } from "./data/repository.js";
import { applyDisplayPreferences, getSettingsStore } from "./data/settings-store.js";
import { createPage } from "./pages/page-registry.js";
import { createRouter } from "./router.js";

const app = document.querySelector("#app");

function renderFatalError(error) {
  console.error(error);
  app.innerHTML = `
    <main class="fatal-state">
      <p class="fatal-state__eyebrow">DATA LOAD ERROR</p>
      <h1>목업 데이터를 불러오지 못했어요.</h1>
      <p>로컬 서버를 통해 실행했는지 확인한 뒤 페이지를 다시 열어 주세요.</p>
      <button type="button">다시 시도</button>
    </main>
  `;
  app.querySelector("button").addEventListener("click", () => window.location.reload());
}

try {
  const model = await loadMockModel();
  applyDisplayPreferences(getSettingsStore(model).getState().display);
  const shell = createAppShell(model);
  app.replaceChildren(shell.element);

  const router = createRouter({
    onRoute(route) {
      if (route.id === "search" && !(route.searchParams.get("q") ?? "").trim()) {
        router.navigate("/", { replace: true });
        return;
      }

      const categoryExists =
        route.id !== "category" || model.categoryById.has(route.params.categoryId);
      const explorationExists =
        route.id !== "explore"
        || !route.params.nodeId
        || model.nodeById.has(route.params.nodeId);
      const renderRoute = categoryExists && explorationExists
        ? route
        : {
            ...route,
            id: "notFound",
            title: "페이지를 찾을 수 없음",
            isNotFound: true,
          };

      const page = createPage(renderRoute, model, { navigate: router.navigate });
      shell.render(renderRoute, page);
      document.title = `${page.dataset.documentTitle || renderRoute.title} · 별빛 뉴스`;
      shell.focusMain();
    },
  });

  router.start();
} catch (error) {
  renderFatalError(error);
}
