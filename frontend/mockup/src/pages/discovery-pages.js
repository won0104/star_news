/**
 * 홈, 분야별 탐색, 검색 결과 화면을 실제 seed 데이터로 구성합니다.
 * 홈 모드와 기간은 URL 상태를 사용하고, 세 화면은 같은 별 노드 캔버스를 공유합니다.
 */

import { createSeedCanvas } from "../components/seed-canvas.js";
import {
  DEFAULT_HOME_TREND_PERIOD_ID,
  selectHomeTrendPeriod,
  selectSearchResults,
} from "../data/selectors.js";
import {
  filterRecommendationSeeds,
  getSettingsStore,
} from "../data/settings-store.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function previewCopy(node) {
  const articleCount = (node.current_article_ids ?? node.article_ids ?? []).length;
  return articleCount > 0
    ? `최근 관련 기사 ${articleCount}개가 연결되어 있어요.`
    : "이 주제와 가까운 뉴스 관계를 살펴보세요.";
}

function renderHomeTabs(activeView) {
  return `
    <nav class="page-tabs" aria-label="화면 모드">
      <a
        class="page-tabs__item ${activeView === "trends" ? "is-active" : ""}"
        data-route
        href="/"
        ${activeView === "trends" ? 'aria-current="page"' : ""}
      >주요 트렌드</a>
      <a
        class="page-tabs__item ${activeView === "for-you" ? "is-active" : ""}"
        data-route
        href="/?view=for-you"
        ${activeView === "for-you" ? 'aria-current="page"' : ""}
      >나를 위한 추천</a>
      ${activeView === "search"
        ? '<span class="page-tabs__item is-active" aria-current="page">검색 결과</span>'
        : ""}
    </nav>
  `;
}

function renderDiscoveryToolbar(activeView) {
  return `
    <div class="discovery-toolbar">
      ${renderHomeTabs(activeView)}
      <div class="discovery-toolbar__search-slot"></div>
    </div>
  `;
}

function createToolbarSearchForm(query, placeholder, statusText = "") {
  const wrapper = document.createElement("div");
  wrapper.className = "toolbar-search";
  wrapper.innerHTML = `
    <form class="search-form search-form--toolbar" role="search" action="/search" method="get" novalidate>
      <label class="sr-only" for="toolbar-news-search">뉴스 주제 검색</label>
      <button class="search-form__submit" type="submit" aria-label="검색">
        <img src="/design/figma/assets/search.svg" alt="" />
      </button>
      <input
        id="toolbar-news-search"
        name="q"
        type="search"
        autocomplete="off"
        placeholder="${escapeHtml(placeholder)}"
        aria-describedby="toolbar-search-status"
      />
    </form>
    <p class="sr-only" id="toolbar-search-status" role="status" aria-live="polite">${escapeHtml(statusText)}</p>
  `;
  wrapper.querySelector("input").value = query;
  return wrapper;
}

function mountToolbarSearch(page, { query = "", placeholder, statusText, navigate }) {
  const search = createToolbarSearchForm(query, placeholder, statusText);
  const form = search.querySelector("form");
  const input = search.querySelector("input");
  const status = search.querySelector('[role="status"]');

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) {
      form.classList.add("is-invalid");
      input.setAttribute("aria-invalid", "true");
      status.textContent = "검색어를 입력해주세요.";
      input.focus();
      return;
    }

    const target = `/search?q=${encodeURIComponent(value)}`;
    if (typeof navigate === "function") {
      navigate(target);
    } else {
      window.location.assign(target);
    }
  });
  input.addEventListener("input", () => {
    form.classList.remove("is-invalid");
    input.removeAttribute("aria-invalid");
    status.textContent = "";
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  page.querySelector(".discovery-toolbar__search-slot").append(search);
}

function periodHref(periodId) {
  return periodId === DEFAULT_HOME_TREND_PERIOD_ID
    ? "/"
    : `/?period=${encodeURIComponent(periodId)}`;
}

function renderPeriodFilter(homeView, activePeriodId) {
  return `
    <nav class="trend-periods" aria-label="트렌드 기간 선택">
      ${homeView.trend_period_order.map((periodId) => {
        const period = homeView.trend_periods[periodId];
        const isActive = periodId === activePeriodId;
        return `
          <a
            class="trend-periods__item ${isActive ? "is-active" : ""}"
            data-route
            href="${periodHref(periodId)}"
            ${isActive ? 'aria-current="page"' : ""}
          >${escapeHtml(period.label)}</a>
        `;
      }).join("")}
    </nav>
  `;
}

function formatSignedRate(value) {
  const rate = Number(value) || 0;
  return `${rate > 0 ? "+" : ""}${rate}%`;
}

function renderRisingSummary(period) {
  return `
    <div class="trend-rising" role="group" aria-label="${escapeHtml(period.comparisonLabel)} 급상승 주제">
      <span class="trend-rising__label">급상승</span>
      <div class="trend-rising__items" role="list">
        ${period.rising.filter(Boolean).map((entry) => `
          <span class="trend-rising__item" role="listitem">
            <strong>${escapeHtml(entry.node.label)}</strong>
            <span>${escapeHtml(formatSignedRate(entry.changeRate))}</span>
          </span>
        `).join("")}
      </div>
    </div>
  `;
}

function toTrendSeed(entry) {
  return {
    node_id: entry.nodeId,
    x: entry.x,
    y: entry.y,
    article_count: entry.articleCount,
    visual_weight: entry.articleCount,
    previous_article_count: entry.previousArticleCount,
    change_rate: entry.changeRate,
    is_rising: entry.isRising,
  };
}

function trendPreviewCopy(_node, entry, comparisonLabel) {
  const rate = Number(entry.change_rate) || 0;
  const change = rate > 0
    ? `${rate}% 증가`
    : rate < 0
      ? `${Math.abs(rate)}% 감소`
      : "변화 없음";
  return `관련 기사 ${entry.article_count}건\n${comparisonLabel} ${change}`;
}

function renderCategoryTabs(model, activeCategoryId) {
  return `
    <nav class="page-tabs page-tabs--categories" aria-label="분야 선택">
      <a class="page-tabs__item page-tabs__item--label" data-route href="/">홈</a>
      <span class="page-tabs__item page-tabs__item--label">분야별 탐색</span>
      ${model.categories
        .map(
          (category) => `
            <a
              class="page-tabs__item ${category.id === activeCategoryId ? "is-active" : ""}"
              data-route
              href="/category/${encodeURIComponent(category.id)}"
              ${category.id === activeCategoryId ? 'aria-current="page"' : ""}
            >${escapeHtml(category.name)}</a>
          `,
        )
        .join("")}
    </nav>
  `;
}

/** 기간별 주요 트렌드와 개인 추천을 URL 상태로 전환하는 홈 화면입니다. */
export function createHomePage(route, model, navigate) {
  const homeView = model.dataset.views.home;
  const activeView = route.searchParams.get("view") === "for-you" ? "for-you" : "trends";
  const isTrends = activeView === "trends";
  const period = selectHomeTrendPeriod(
    model,
    route.searchParams.get("period") ?? DEFAULT_HOME_TREND_PERIOD_ID,
  );
  const seeds = isTrends
    ? period.seeds.map(toTrendSeed)
    : filterRecommendationSeeds(
        model,
        homeView.for_you,
        getSettingsStore(model).getState().dislikes,
      ).map((entry) => ({
        ...entry,
        visual_weight: model.nodeById.get(entry.node_id)?.personal_score ?? 0,
      }));
  const page = document.createElement("section");
  page.className = "page-stage discovery-page";
  page.dataset.screen = "home";
  page.dataset.documentTitle = isTrends ? period.title : "나를 위한 추천";
  page.innerHTML = `
    ${renderDiscoveryToolbar(activeView)}
    ${isTrends
      ? `
        <section class="trend-overview" aria-labelledby="trend-title">
          <div class="trend-overview__heading">
            <header class="page-stage__header discovery-page__header">
              <h1 id="trend-title" tabindex="-1">${escapeHtml(period.title)}</h1>
            </header>
            ${renderPeriodFilter(homeView, period.id)}
          </div>
          ${renderRisingSummary(period)}
        </section>
      `
      : `
        <header class="page-stage__header discovery-page__header">
          <h1 tabindex="-1">나를 위한 추천 흐름</h1>
          <p>읽어온 뉴스와 가까우면서 지금 알아둘 만한 주제예요.</p>
        </header>
      `}
    <div class="discovery-page__graph-slot"></div>
  `;

  mountToolbarSearch(page, {
    placeholder: model.dataset.views.search.placeholder,
    navigate,
  });
  page.querySelector(".discovery-page__graph-slot").append(
    createSeedCanvas({
      model,
      seeds,
      ariaLabel: isTrends
        ? `${period.windowLabel} 주요 트렌드 별 지도`
        : "나를 위한 추천 별 지도",
      instruction: "별을 눌러 탐색하세요",
      updatedAt: isTrends ? period.updatedAt : homeView.updated_at,
      windowLabel: isTrends ? period.windowLabel : homeView.trend_window,
      previewText: isTrends
        ? (node, entry) => trendPreviewCopy(node, entry, period.comparisonLabel)
        : previewCopy,
      variant: "home",
      layoutSeed: isTrends ? `home:trends:${period.id}` : "home:for-you",
    }),
  );

  return page;
}

/** 선택한 분야의 8개 seed 노드를 데이터 좌표대로 배치합니다. */
export function createCategoryPage(route, model) {
  const category = model.categoryById.get(route.params.categoryId);
  const categoryView = model.dataset.views.categories[route.params.categoryId];
  const page = document.createElement("section");
  page.className = "page-stage discovery-page";
  page.dataset.screen = "category";
  page.dataset.documentTitle = `${category.name} 분야별 탐색`;
  page.innerHTML = `
    ${renderCategoryTabs(model, category.id)}
    <header class="page-stage__header discovery-page__header">
      <h1 tabindex="-1">${escapeHtml(category.name)}에서 알아둘 흐름</h1>
      <p>최근 ${escapeHtml(category.name)} 분야에서 주목할 만한 주제들이에요.</p>
    </header>
    <div class="discovery-page__graph-slot"></div>
  `;

  page.querySelector(".discovery-page__graph-slot").append(
    createSeedCanvas({
      model,
      seeds: categoryView.seed_nodes.map((entry) => ({
        ...entry,
        visual_weight: model.nodeById.get(entry.node_id)?.trend_score ?? 0,
      })),
      ariaLabel: `${category.name} 분야 seed 별 지도`,
      instruction: `별을 눌러 ${category.name} 탐색을 시작하세요`,
      updatedAt: model.dataset.views.home.updated_at,
      windowLabel: model.dataset.views.home.trend_window,
      previewText: previewCopy,
      variant: "category",
      layoutSeed: `category:${category.id}`,
    }),
  );

  return page;
}

/** query와 일치하는 노드 및 직접 이웃을 같은 별 지도 위에 펼칩니다. */
export function createSearchPage(route, model, navigate) {
  const query = (route.searchParams.get("q") ?? "").trim();
  const results = selectSearchResults(model, query);
  const nodes = results.map(({ node }) => node);
  const seeds = results.map(({ node, score }) => ({
    node_id: node.id,
    visual_weight: score,
  }));
  const page = document.createElement("section");
  page.className = "page-stage discovery-page search-page";
  page.dataset.screen = "search";
  page.dataset.documentTitle = query ? `${query} 검색 결과` : "검색 결과";
  page.innerHTML = `
    ${renderDiscoveryToolbar("search")}
    <header class="page-stage__header discovery-page__header">
      <h1 tabindex="-1">${query ? `‘${escapeHtml(query)}’ 검색 결과` : "검색 결과"}</h1>
      <p>검색어와 연결된 주제를 관련도순으로 보여드려요.</p>
    </header>
    <div class="discovery-page__graph-slot"></div>
  `;

  const statusText = query
    ? nodes.length > 0
      ? `${nodes.length}개의 관련 주제를 찾았어요.`
      : "일치하는 주제를 찾지 못했어요. 다른 검색어를 입력해보세요."
    : "검색어를 입력해 탐색을 시작하세요";
  mountToolbarSearch(page, {
    query,
    placeholder: model.dataset.views.search.placeholder,
    statusText,
    navigate,
  });

  page.querySelector(".discovery-page__graph-slot").append(
    createSeedCanvas({
      model,
      seeds,
      ariaLabel: query ? `${query} 검색 결과 별 지도` : "뉴스 주제 검색",
      instruction: query
        ? "별을 눌러 검색 결과에서 탐색하세요"
        : "검색어를 입력하면 관련 주제가 별처럼 나타납니다",
      updatedAt: model.dataset.views.home.updated_at,
      windowLabel: model.dataset.views.home.trend_window,
      previewText: previewCopy,
      emptyMessage: nodes.length === 0
        ? "일치하는 주제를 찾지 못했어요. 다른 검색어를 입력해보세요."
        : "",
      variant: query ? "search-results" : "search-empty",
      layoutSeed: `search:${query.toLocaleLowerCase("ko-KR")}`,
    }),
  );

  return page;
}
