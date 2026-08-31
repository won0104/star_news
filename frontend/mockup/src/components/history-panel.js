/** 개인 기록과 전체 개인 지도가 공유하는 최신순 기사 기록 패널입니다. */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function zonedDateParts(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

function dateOrdinal(value) {
  const { year, month, day } = zonedDateParts(value);
  return Date.UTC(Number(year), Number(month) - 1, Number(day)) / 86_400_000;
}

function dateGroupLabel(value, referenceValue) {
  const difference = dateOrdinal(referenceValue) - dateOrdinal(value);
  if (difference === 0) {
    return "오늘";
  }
  if (difference === 1) {
    return "어제";
  }
  const { month, day } = zonedDateParts(value);
  return `${Number(month)}월 ${Number(day)}일`;
}

function renderEntry(entry) {
  const { article } = entry;
  const sourceName = entry.sourceName === "별빛 뉴스 시연 데이터"
    ? "시연용 합성 기록"
    : entry.sourceName;
  const summary = article.summary || article.description || article.content_preview || "요약이 없는 기록입니다.";
  const externalUrl = safeExternalUrl(article);
  const action = externalUrl
    ? `<a href="${escapeHtml(externalUrl)}" target="_blank" rel="noopener noreferrer">원문 보기 →<span class="sr-only"> (새 창)</span></a>`
    : '<span class="history-card__mock-label">시연 기록</span>';

  return `
    <article class="history-card" data-article-id="${escapeHtml(article.id)}">
      <p class="history-card__meta">${escapeHtml(sourceName)} · ${escapeHtml(entry.categoryName)}</p>
      <h3>${escapeHtml(article.title)}</h3>
      <p class="history-card__summary">${escapeHtml(summary)}</p>
      ${action}
    </article>
  `;
}

/**
 * history는 selectReadHistory의 반환값입니다.
 * 닫기와 필터 해제 버튼은 bubbling하는 이벤트로 부모 화면에 상태 변경을 요청합니다.
 */
export function createHistoryPanel({
  model,
  history,
  closeable = false,
  filterClearable = false,
}) {
  const panel = document.createElement("aside");
  panel.className = "history-panel";
  panel.setAttribute("aria-label", `${history.title} 기사 목록`);
  const referenceValue = model.dataset.user_report.period.to;
  let previousGroup = null;
  const content = history.entries.map((entry) => {
    const group = dateGroupLabel(entry.occurredAt, referenceValue);
    const heading = group === previousGroup
      ? ""
      : `<h3 class="history-panel__date">${escapeHtml(group)}</h3>`;
    previousGroup = group;
    return `${heading}${renderEntry(entry)}`;
  }).join("");

  panel.innerHTML = `
    <header class="history-panel__header ${filterClearable ? "has-filter-clear" : ""}">
      <p>READING HISTORY</p>
      <h2 tabindex="-1">${escapeHtml(history.title)}</h2>
      <span>읽은 기사 ${history.entries.length}개 · 최신순</span>
      ${filterClearable ? `
        <button class="history-panel__filter-clear" type="button">
          필터 해제 <span aria-hidden="true">×</span>
        </button>
      ` : ""}
      ${closeable ? `
        <button class="history-panel__close" type="button" aria-label="기록 기사 패널 닫기">
          <img src="/design/figma/assets/close.svg" alt="" />
        </button>
      ` : ""}
    </header>
    <div class="history-panel__scroll" tabindex="0">
      ${content || '<p class="history-panel__empty">이 조건에 해당하는 읽은 기록이 없어요.</p>'}
    </div>
  `;

  panel.querySelector(".history-panel__close")?.addEventListener("click", (event) => {
    panel.dispatchEvent(new CustomEvent("historyclose", {
      bubbles: true,
      detail: { keyboard: event.detail === 0 },
    }));
  });
  panel.querySelector(".history-panel__filter-clear")?.addEventListener("click", () => {
    panel.dispatchEvent(new CustomEvent("historyfilterclear", { bubbles: true }));
  });
  return panel;
}
