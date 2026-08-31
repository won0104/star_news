/** 최근 3개월 개인 리포트의 막대, 누적 막대, 주간 변화, 주제 지형을 렌더링합니다. */

import { CLUSTER_COLORS, selectPersonalReport } from "../data/personal-selectors.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCategoryDistribution(entries) {
  const max = Math.max(1, ...entries.map((entry) => entry.count));
  return entries.map((entry, index) => `
    <div
      class="category-bar"
      role="img"
      aria-label="${escapeHtml(entry.category_name)} 분야에서 ${entry.count}개 기사를 읽음"
      style="--chart-delay:${index * 45}ms"
    >
      <span>${escapeHtml(entry.category_name)}</span>
      <div class="category-bar__track">
        <i style="--bar-ratio:${entry.count / max};--bar-color:${CLUSTER_COLORS[entry.category_id]}"></i>
      </div>
      <strong>${entry.count}</strong>
    </div>
  `).join("");
}

function renderSourceDistribution(sourceDistribution) {
  const stacked = sourceDistribution.segments.map((entry, index) => `
    <i
      title="${escapeHtml(entry.name)} ${Math.round(entry.ratio * 100)}%"
      style="width:${entry.ratio * 100}%;background:${entry.color};--chart-delay:${index * 35}ms"
    ></i>
  `).join("");
  const legend = sourceDistribution.segments.map((entry) => `
    <li>
      <i style="background:${entry.color}"></i>
      <span>${escapeHtml(entry.name)}</span>
      <strong>${Math.round(entry.ratio * 100)}%</strong>
    </li>
  `).join("");
  const topTwoRatio = sourceDistribution.segments
    .slice(0, 2)
    .reduce((sum, entry) => sum + entry.ratio, 0);
  return `
    <div class="source-stack" aria-hidden="true">${stacked}</div>
    <ul class="source-legend">${legend}</ul>
    <p class="report-card__insight">상위 두 출처가 전체 읽기 기록의 ${Math.round(topTwoRatio * 100)}%를 차지합니다. 시연용 합성 기록을 포함합니다.</p>
  `;
}

function renderWeeklyReading(weeklyReading) {
  const colors = ["#668aaf", "#8ea8c1", "#aaa7c2", "#d1d7de"];
  const legend = weeklyReading.categories.map((category, index) => `
    <span><i style="background:${colors[index]}"></i>${escapeHtml(category.name)}</span>
  `).join("");
  const bars = weeklyReading.buckets.map((bucket, index) => `
    <div class="weekly-bar" style="--chart-delay:${index * 35}ms" aria-label="${bucket.total}개 기사">
      <div class="weekly-bar__stack">
        ${weeklyReading.categories.map((category, categoryIndex) => {
          const count = bucket.values[category.id];
          return count > 0 ? `
            <i
              style="height:${(count / weeklyReading.maxTotal) * 100}%;background:${colors[categoryIndex]}"
              title="${escapeHtml(category.name)} ${count}개"
            ></i>
          ` : "";
        }).join("")}
      </div>
      <span>${escapeHtml(bucket.monthLabel)}</span>
    </div>
  `).join("");
  const summary = weeklyReading.buckets.map((bucket) => {
    const details = weeklyReading.categories
      .map((category) => `${category.name} ${bucket.values[category.id] ?? 0}개`)
      .join(", ");
    return `<li>${escapeHtml(bucket.monthLabel)} · 전체 ${bucket.total}개 · ${escapeHtml(details)}</li>`;
  }).join("");
  return `
    <div class="weekly-chart__legend">${legend}</div>
    <div class="weekly-chart__plot" role="img" aria-label="최근 12주의 분야별 읽은 기사 수 변화">
      <div class="weekly-chart__grid" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
      <div class="weekly-chart__bars">${bars}</div>
    </div>
    <ul class="sr-only">${summary}</ul>
  `;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function renderTerrain(points) {
  const occupied = [];
  const pointMarkup = points.map((point, index) => {
    let x = 28 + clamp(point.x_read_frequency, 0, 1) * 324;
    const normalizedGrowth = clamp((point.y_recent_growth + 0.5) / 1.5, 0, 1);
    let y = 72 + (1 - normalizedGrowth) * 133;
    let collisionAttempt = 0;
    while (occupied.some((position) => Math.hypot(position.x - x, position.y - y) < 18)) {
      collisionAttempt += 1;
      x = clamp(x + (collisionAttempt % 2 ? 10 : -7), 36, 344);
      y = clamp(y + 15, 72, 205);
    }
    occupied.push({ x, y });
    const alignEnd = x > 290 || (y < 100 && x < 200);
    const labelY = y < 100 ? y + (index % 2 ? 18 : -9) : y + 3;
    const color = CLUSTER_COLORS[point.node.category_id] ?? "#7899ba";
    return `
      <g class="terrain-point" style="--chart-delay:${index * 45}ms;--point-color:${color}">
        <circle cx="${x}" cy="${y}" r="${3.5 + Math.min(3, point.read_count / 8)}" />
        <text x="${x + (alignEnd ? -9 : 9)}" y="${labelY}" text-anchor="${alignEnd ? "end" : "start"}">${escapeHtml(point.node.label)}</text>
      </g>
    `;
  }).join("");
  const summary = points.map((point) => `<li>${escapeHtml(point.node.label)} · 최근 3개월 ${point.read_count}회 열람 · 관심 증가율 ${Math.round(point.y_recent_growth * 100)}%</li>`).join("");
  return `
    <svg class="terrain-chart" viewBox="0 0 380 270" role="img" aria-labelledby="terrain-title terrain-description">
      <title id="terrain-title">최근 주제 지형</title>
      <desc id="terrain-description">가로축은 최근 3개월 열람 빈도, 세로축은 최근 4주 관심 증가율입니다.</desc>
      <rect class="terrain-chart__new" x="28" y="32" width="162" height="100" rx="6" />
      <line x1="190" y1="32" x2="190" y2="218" />
      <line x1="28" y1="132" x2="352" y2="132" />
      <text class="terrain-chart__quadrant terrain-chart__quadrant--accent" x="38" y="48">새로 살펴볼 흐름</text>
      <text class="terrain-chart__quadrant" x="203" y="48">자주 만난 주요 흐름</text>
      <text class="terrain-chart__quadrant" x="38" y="208">가볍게 스친 흐름</text>
      <text class="terrain-chart__quadrant" x="203" y="208">꾸준히 따라본 흐름</text>
      ${pointMarkup}
      <text class="terrain-chart__axis" x="352" y="245" text-anchor="end">가로축 · 최근 3개월 열람 빈도</text>
      <text class="terrain-chart__axis" x="352" y="261" text-anchor="end">세로축 · 최근 4주 관심 증가율</text>
    </svg>
    <ul class="sr-only">${summary}</ul>
  `;
}

/** 데이터 집계가 반영된 네 개의 리포트 카드를 반환합니다. */
export function createReportView(model) {
  const report = selectPersonalReport(model);
  const view = document.createElement("div");
  view.className = "personal-report-grid";
  view.innerHTML = `
    <section class="report-card report-card--categories">
      <header><h2>분야별 읽은 기사</h2><p>읽은 기록을 큰 분야별로 집계했어요.</p></header>
      <div class="category-bars">${renderCategoryDistribution(report.categoryDistribution)}</div>
    </section>

    <section class="report-card report-card--sources">
      <header><h2>출처별 읽기 비중</h2><p>${report.sourceDistribution.uniqueCount}개 출처의 기사를 어떻게 접했는지 보여줘요.</p></header>
      ${renderSourceDistribution(report.sourceDistribution)}
    </section>

    <section class="report-card report-card--weekly">
      <header><h2>최근 12주의 분야별 읽기 변화</h2><p>주별 기사 수와 분야 구성이 어떻게 달라졌는지 보여줘요.</p></header>
      ${renderWeeklyReading(report.weeklyReading)}
    </section>

    <section class="report-card report-card--terrain">
      <header><h2>최근 주제 지형</h2><p>최근 읽은 분야 안에서 주제들이 어떻게 분포했는지 보여드려요.</p></header>
      ${renderTerrain(report.terrain)}
    </section>
  `;
  return { element: view, report };
}
