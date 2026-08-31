/** 나의 기록, 나의 리포트, 전체 개인 기록 지도 화면을 구성합니다. */

import { createPersonalMap } from "../components/personal-map.js";
import { createRecordClusterView } from "../components/record-cluster-graph.js";
import { createReportView } from "../components/report-view.js";

function renderTabs(active) {
  return `
    <nav class="page-tabs" aria-label="나의 뉴스 세계 보기">
      <a
        class="page-tabs__item ${active === "records" ? "is-active" : ""}"
        data-route
        href="/my-world/records"
        ${active === "records" ? 'aria-current="page"' : ""}
      >나의 기록</a>
      <a
        class="page-tabs__item ${active === "report" ? "is-active" : ""}"
        data-route
        href="/my-world/report"
        ${active === "report" ? 'aria-current="page"' : ""}
      >나의 리포트</a>
    </nav>
  `;
}

/** 상위 군집을 시각적 필터로 쓰고 오른쪽에 전체 방문 기록을 보여줍니다. */
export function createRecordsPage(model) {
  const page = document.createElement("section");
  page.className = "page-stage my-world-page records-page";
  page.dataset.screen = "records";
  page.dataset.documentTitle = "나의 기록";
  page.innerHTML = `
    ${renderTabs("records")}
    <header class="page-stage__header my-world-page__header">
      <h1 tabindex="-1">내가 읽어온 뉴스 세계</h1>
      <p>읽은 기록을 큰 주제별로 묶어 보여드려요. 군집을 누르면 오른쪽 기록이 필터링됩니다.</p>
    </header>
    <div class="records-page__content"></div>
  `;
  page.querySelector(".records-page__content").append(createRecordClusterView(model));
  return page;
}

/** 최근 3개월 고정 기간의 개인 기록 집계를 네 개의 차트로 보여줍니다. */
export function createReportPage(model) {
  const { element, report } = createReportView(model);
  const page = document.createElement("section");
  page.className = "page-stage my-world-page report-page";
  page.dataset.screen = "report";
  page.dataset.documentTitle = "나의 리포트";
  page.innerHTML = `
    ${renderTabs("report")}
    <header class="page-stage__header my-world-page__header">
      <h1 tabindex="-1">${report.period.label}의 뉴스 리포트</h1>
      <p>${report.period.label} 동안 ${report.overview.articles_read}개의 기사에서 ${report.overview.topics_visited}개 주제를 살펴봤어요. · 탐색 ${report.overview.exploration_sessions}회</p>
    </header>
    <div class="report-page__content"></div>
  `;
  page.querySelector(".report-page__content").append(element);
  return page;
}

/** 공통 셸 위를 덮는 pan/zoom 전체 개인 기록 지도입니다. */
export function createPersonalMapPage(model, navigate) {
  return createPersonalMap(model, { navigate });
}
