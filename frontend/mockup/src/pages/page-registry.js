/** 현재 경로에 맞는 구현 화면을 선택하고, 알 수 없는 경로에는 안내 화면을 제공합니다. */

import {
  createCategoryPage,
  createHomePage,
  createSearchPage,
} from "./discovery-pages.js";
import { createExplorationPage } from "./exploration-page.js";
import {
  createPersonalMapPage,
  createRecordsPage,
  createReportPage,
} from "./my-world-pages.js";
import { createSettingsPage } from "./settings-page.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function routeTabs(route, model) {
  if (route.id === "home") {
    return `
      <nav class="page-tabs" aria-label="홈 보기">
        <span class="page-tabs__item is-active">주요 트렌드</span>
        <span class="page-tabs__item">나를 위한 추천</span>
      </nav>
    `;
  }

  if (route.id === "category") {
    return `
      <nav class="page-tabs page-tabs--categories" aria-label="분야 선택">
        <span class="page-tabs__item page-tabs__item--label">분야별 탐색</span>
        ${model.categories
          .map(
            (category) => `
              <a
                class="page-tabs__item ${category.id === route.params.categoryId ? "is-active" : ""}"
                data-route
                href="/category/${encodeURIComponent(category.id)}"
                ${category.id === route.params.categoryId ? 'aria-current="page"' : ""}
              >${escapeHtml(category.name)}</a>
            `,
          )
          .join("")}
      </nav>
    `;
  }

  if (["records", "report"].includes(route.id)) {
    return `
      <nav class="page-tabs" aria-label="나의 뉴스 세계 보기">
        <a
          class="page-tabs__item ${route.id === "records" ? "is-active" : ""}"
          data-route
          href="/my-world/records"
          ${route.id === "records" ? 'aria-current="page"' : ""}
        >나의 기록</a>
        <a
          class="page-tabs__item ${route.id === "report" ? "is-active" : ""}"
          data-route
          href="/my-world/report"
          ${route.id === "report" ? 'aria-current="page"' : ""}
        >나의 리포트</a>
      </nav>
    `;
  }

  return "";
}

function pageCopy(route, model) {
  const category = model.categoryById.get(route.params.categoryId);
  const node = model.nodeById.get(route.params.nodeId);
  const screenCopy = {
    home: {
      eyebrow: model.dataset.views.home.trend_window,
      title: "오늘 알아두면 좋은 흐름",
      description: "한국 주요 매체와 관심사를 바탕으로 고른 뉴스 관계를 보여드려요.",
      canvasLabel: "홈 추천 그래프",
    },
    search: {
      eyebrow: "키워드로 시작하기",
      title: "찾아보기",
      description: "알고 있는 주제를 검색하면 관련 키워드가 별처럼 펼쳐집니다.",
      canvasLabel: "통합 검색",
    },
    explore: {
      eyebrow: node ? "선택한 별에서 이어보기" : "관계를 따라 이동하기",
      title: node?.label ?? "뉴스 관계 탐색",
      description: node
        ? "이 노드와 가까운 뉴스 관계를 펼쳐 보여드려요."
        : "홈, 분야 또는 검색 결과의 별을 선택하면 탐색을 시작합니다.",
      canvasLabel: "관계 탐색 그래프",
    },
    records: {
      eyebrow: "읽어온 뉴스의 부분집합",
      title: "나의 기록",
      description: "읽은 뉴스의 큰 군집을 지도처럼 보고 기록 목록을 함께 확인해요.",
      canvasLabel: "개인 기록 그래프와 최신순 목록",
    },
    report: {
      eyebrow: `최근 ${model.user.report_period_days}일 기준`,
      title: "나의 리포트",
      description: "관심 분야와 최근 주제 지형을 간결한 차트로 돌아봅니다.",
      canvasLabel: "개인 뉴스 리포트",
    },
    personalMap: {
      eyebrow: "확대·축소하며 둘러보기",
      title: "나의 기록 지도",
      description: "개인 기록 그래프 전체를 자유롭게 이동하며 탐험합니다.",
      canvasLabel: "Pan·zoom 개인 지도",
    },
    settings: {
      eyebrow: "프로필과 환경 관리",
      title: {
        account: "계정 설정",
        dislikes: "관심 없음 관리",
        display: "화면 설정",
      }[route.params.section],
      description: "변경 내용은 저장 버튼을 눌렀을 때 반영되는 설정 화면입니다.",
      canvasLabel: "설정 오버레이",
    },
    notFound: {
      eyebrow: "404",
      title: "페이지를 찾을 수 없어요",
      description: "주소를 확인하거나 홈에서 다시 시작해 주세요.",
      canvasLabel: "알 수 없는 경로",
    },
  };

  if (route.id === "category" && category) {
    return {
      eyebrow: "분야별 탐색",
      title: `${category.name} 분야별 탐색`,
      description: `${category.name} 분야에서 지금 이어 볼 만한 주제를 보여드려요.`,
      canvasLabel: `${category.name} seed 그래프`,
    };
  }

  if (route.id === "category" && !category) {
    return screenCopy.notFound;
  }

  return screenCopy[route.id] ?? screenCopy.notFound;
}

function footerLinks(route) {
  if (route.id === "personalMap") {
    return '<a class="stage-link" data-route href="/my-world/records">나의 기록으로</a>';
  }

  if (route.id === "notFound") {
    return '<a class="stage-link" data-route href="/">홈으로 돌아가기</a>';
  }

  if (route.id === "explore" && !route.params.nodeId) {
    return '<a class="stage-link" data-route href="/">시작할 별 고르기</a>';
  }

  return "";
}

function createPlaceholderPage(route, model) {
  const copy = pageCopy(route, model);
  const page = document.createElement("section");
  page.className = "page-stage";
  page.dataset.screen = route.id;
  page.innerHTML = `
    ${routeTabs(route, model)}
    <header class="page-stage__header">
      <p class="page-stage__eyebrow">${escapeHtml(copy.eyebrow)}</p>
      <h1 tabindex="-1">${escapeHtml(copy.title)}</h1>
      <p>${escapeHtml(copy.description)}</p>
    </header>

    <div class="page-stage__canvas" aria-label="${escapeHtml(copy.canvasLabel)}">
      <div class="page-stage__constellation" aria-hidden="true">
        <span></span><span></span><span></span><span></span><span></span>
      </div>
      <div class="page-stage__status">
        <span class="page-stage__status-dot" aria-hidden="true"></span>
        <strong>${escapeHtml(copy.canvasLabel)}</strong>
        <p>요청한 화면을 표시할 수 없습니다.</p>
        ${footerLinks(route)}
      </div>
    </div>
  `;

  return page;
}

/** 현재 경로에 대응하는 화면 DOM을 반환합니다. */
export function createPage(route, model, { navigate } = {}) {
  switch (route.id) {
    case "home":
      return createHomePage(route, model, navigate);
    case "category":
      return createCategoryPage(route, model);
    case "search":
      return createSearchPage(route, model, navigate);
    case "explore":
      return createExplorationPage(route, model);
    case "records":
      return createRecordsPage(model);
    case "report":
      return createReportPage(model);
    case "personalMap":
      return createPersonalMapPage(model, navigate);
    case "settings":
      return createSettingsPage(route, model, navigate);
    default:
      return createPlaceholderPage(route, model);
  }
}
