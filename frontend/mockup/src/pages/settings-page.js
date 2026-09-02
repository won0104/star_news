/** 계정·관심 없음·화면 설정을 하나의 저장형 모달 화면으로 구성합니다. */

import {
  applyDisplayPreferences,
  getSettingsStore,
} from "../data/settings-store.js";

const SECTION_COPY = {
  account: {
    title: "계정 설정",
    description: "로그인 정보와 기본 프로필을 관리합니다.",
  },
  dislikes: {
    title: "관심 없음 관리",
    description: "추천에서 덜 보고 싶은 분야와 주제를 관리합니다.",
  },
  display: {
    title: "화면 설정",
    description: "화면의 밝기와 읽기 방식을 조절합니다.",
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/** 설정 오버레이를 닫을 때 앱 내부의 안전한 화면으로만 돌아갑니다. */
export function resolveSettingsReturnPath(rawValue) {
  const value = String(rawValue ?? "");
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/settings/")) {
    return "/";
  }
  return value;
}

function settingsHref(section, returnPath) {
  return `/settings/${section}?return=${encodeURIComponent(returnPath)}`;
}

function renderNavigation(active, returnPath) {
  const entries = [
    ["account", "계정 설정"],
    ["dislikes", "관심 없음 관리"],
    ["display", "화면 설정"],
  ];
  return entries.map(([section, label]) => `
    <a
      class="settings-nav__item ${active === section ? "is-active" : ""}"
      data-route
      href="${settingsHref(section, returnPath)}"
      ${active === section ? 'aria-current="page"' : ""}
    >${label}</a>
  `).join("");
}

function renderAccount(state) {
  return `
    <form class="settings-form settings-form--account" data-settings-form="account" novalidate>
      <label class="settings-field">
        <span>프로필 이름</span>
        <input
          name="displayName"
          maxlength="40"
          value="${escapeHtml(state.account.displayName)}"
          autocomplete="nickname"
          aria-describedby="account-name-error"
        />
      </label>
      <label class="settings-field">
        <span>이메일</span>
        <input value="목업 데이터에 이메일 정보가 없습니다" disabled />
      </label>
      <p class="settings-form__help">이메일은 현재 목업 데이터에 포함되지 않아 수정할 수 없습니다.</p>
      <p class="settings-form__error" id="account-name-error" role="alert"></p>
      <button class="settings-save" type="submit">변경사항 저장</button>
    </form>
  `;
}

function renderDislikeItems(store, draftIds) {
  if (draftIds.length === 0) {
    return '<p class="settings-dislikes__empty">등록된 관심 없음 항목이 없습니다.</p>';
  }
  return draftIds.map((id) => {
    const candidate = store.getCandidate(id);
    if (!candidate) {
      return "";
    }
    return `
      <li class="settings-dislike-item">
        <div>
          <strong>${escapeHtml(candidate.label)}</strong>
          <span>${escapeHtml(candidate.kind)} · 저장 후 추천 후보에서 제외</span>
        </div>
        <button type="button" data-remove-dislike="${escapeHtml(id)}">목록에서 제거</button>
      </li>
    `;
  }).join("");
}

function renderDislikes(store, draftIds, message = "") {
  const available = store.candidates.filter((candidate) => !draftIds.includes(candidate.id));
  return `
    <form class="settings-form settings-form--dislikes" data-settings-form="dislikes" novalidate>
      <label class="settings-dislikes__add-label" for="dislike-candidate">관심 없음 항목 추가</label>
      <div class="settings-dislikes__add-row">
        <input
          id="dislike-candidate"
          name="candidate"
          list="dislike-candidates"
          placeholder="분야 또는 주제를 입력하세요"
          autocomplete="off"
          aria-describedby="dislike-candidate-error"
          aria-invalid="${message ? "true" : "false"}"
        />
        <datalist id="dislike-candidates">
          ${available.map((candidate) => `<option value="${escapeHtml(candidate.label)}">${candidate.kind}</option>`).join("")}
        </datalist>
        <button type="button" data-add-dislike>추가</button>
      </div>
      <p class="settings-form__error" id="dislike-candidate-error" role="alert">${escapeHtml(message)}</p>
      <div class="settings-dislikes__heading">
        <strong>등록된 항목</strong><span>${draftIds.length}개</span>
      </div>
      <ul class="settings-dislikes__list">${renderDislikeItems(store, draftIds)}</ul>
      <div class="settings-info-box">
        추가하거나 제거한 내용은 저장 후 추천에 반영됩니다.<br />
        읽지 않았다는 이유만으로 자동 등록되지는 않습니다.
      </div>
      <button class="settings-save" type="submit">변경사항 저장</button>
    </form>
  `;
}

function renderSegmentedControl({ name, label, entries, selected }) {
  return `
    <fieldset class="settings-choice-row">
      <legend>${escapeHtml(label)}</legend>
      <div class="settings-segmented" style="--segment-count:${entries.length}">
        ${entries.map(([value, entryLabel]) => `
          <label>
            <input type="radio" name="${escapeHtml(name)}" value="${escapeHtml(value)}" ${selected === value ? "checked" : ""} />
            <span>${escapeHtml(entryLabel)}</span>
          </label>
        `).join("")}
      </div>
    </fieldset>
  `;
}

function renderDisplay(state) {
  return `
    <form class="settings-form settings-form--display" data-settings-form="display">
      ${renderSegmentedControl({
        name: "theme",
        label: "화면 테마",
        entries: [["light", "밝게"], ["dark", "어둡게"], ["system", "시스템"]],
        selected: state.display.theme,
      })}
      ${renderSegmentedControl({
        name: "fontSize",
        label: "글자 크기",
        entries: [["normal", "보통"], ["large", "크게"]],
        selected: state.display.fontSize,
      })}
      <label class="settings-toggle-row">
        <span><strong>애니메이션 줄이기</strong><small>별과 그래프의 이동 효과를 단순한 전환으로 바꿉니다.</small></span>
        <input type="checkbox" name="reducedMotion" ${state.display.reducedMotion ? "checked" : ""} />
        <i aria-hidden="true"></i>
      </label>
      <p class="settings-form__error" id="display-settings-error" role="alert"></p>
      <button class="settings-save" type="submit">변경사항 저장</button>
    </form>
  `;
}

function showToast(page, message) {
  page.dispatchEvent(new CustomEvent("mocktoast", {
    bubbles: true,
    detail: { message },
  }));
}

/** 현재 설정 section과 return query를 반영한 모달 페이지를 생성합니다. */
export function createSettingsPage(route, model, navigate) {
  const section = route.params.section;
  const copy = SECTION_COPY[section];
  const store = getSettingsStore(model);
  const returnPath = resolveSettingsReturnPath(route.searchParams.get("return"));
  const page = document.createElement("section");
  page.className = "settings-overlay";
  page.dataset.screen = "settings";
  page.dataset.documentTitle = copy.title;
  page.innerHTML = `
    <button class="settings-backdrop" type="button" aria-label="설정 닫기"></button>
    <div
      class="settings-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
      aria-describedby="settings-description"
    >
      <aside class="settings-nav">
        <h1>설정</h1>
        <nav aria-label="설정 항목">${renderNavigation(section, returnPath)}</nav>
        <a class="settings-nav__return" data-route href="${escapeHtml(returnPath)}">←&nbsp;&nbsp;별빛 뉴스로 돌아가기</a>
      </aside>
      <div class="settings-content">
        <button class="settings-dialog__close" data-route-focus type="button" aria-label="설정 닫기">×</button>
        <header>
          <h2 id="settings-title" tabindex="-1">${copy.title}</h2>
          <p id="settings-description">${copy.description}</p>
        </header>
        <div class="settings-content__body"></div>
      </div>
    </div>
  `;

  const content = page.querySelector(".settings-content__body");
  let draftDislikes = store.getState().dislikes;
  const renderContent = (message = "") => {
    const state = store.getState();
    if (section === "account") {
      content.innerHTML = renderAccount(state);
    } else if (section === "dislikes") {
      content.innerHTML = renderDislikes(store, draftDislikes, message);
    } else {
      content.innerHTML = renderDisplay(state);
    }
  };
  renderContent();

  const close = () => navigate(returnPath);
  page.querySelector(".settings-backdrop").addEventListener("click", close);
  page.querySelector(".settings-dialog__close").addEventListener("click", close);
  page.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key === "Tab") {
      const focusable = [...page.querySelectorAll(
        '.settings-dialog a[href], .settings-dialog button:not([disabled]), .settings-dialog input:not([disabled])',
      )].filter((element) => !element.hidden);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  });

  page.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-add-dislike]");
    if (addButton) {
      const input = page.querySelector('[name="candidate"]');
      const candidate = store.findCandidateByLabel(input.value);
      if (!candidate) {
        renderContent("목업 데이터에 있는 분야 또는 주제를 선택해 주세요.");
        page.querySelector('[name="candidate"]')?.focus();
        return;
      }
      if (!draftDislikes.includes(candidate.id)) {
        draftDislikes = [...draftDislikes, candidate.id];
      }
      renderContent();
      page.querySelector('[name="candidate"]')?.focus();
      return;
    }

    const removeButton = event.target.closest("[data-remove-dislike]");
    if (removeButton) {
      draftDislikes = draftDislikes.filter((id) => id !== removeButton.dataset.removeDislike);
      renderContent();
      page.querySelector('[name="candidate"]')?.focus();
    }
  });

  page.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.target.closest("[data-settings-form]");
    if (!form) {
      return;
    }
    const error = form.querySelector(".settings-form__error");
    try {
      if (form.dataset.settingsForm === "account") {
        const displayName = new FormData(form).get("displayName");
        store.saveAccount(displayName);
      } else if (form.dataset.settingsForm === "dislikes") {
        store.saveDislikes(draftDislikes);
      } else {
        const values = new FormData(form);
        const nextState = store.saveDisplay({
          theme: values.get("theme"),
          fontSize: values.get("fontSize"),
          reducedMotion: values.get("reducedMotion") === "on",
        });
        applyDisplayPreferences(nextState.display);
      }
      if (error) {
        error.textContent = "";
      }
      form.querySelector('[name="displayName"]')?.setAttribute("aria-invalid", "false");
      showToast(page, `${copy.title} 변경사항을 저장했습니다.`);
    } catch (saveError) {
      if (error) {
        error.textContent = saveError.message;
      }
      form.querySelector('[name="displayName"]')?.setAttribute("aria-invalid", "true");
    }
  });

  queueMicrotask(() => page.querySelector(".settings-dialog__close")?.focus());
  return page;
}
