/**
 * 모든 화면이 공유하는 고정 사이드바, 헤더, 프로필 바로가기 메뉴를 렌더링합니다.
 * 개별 화면 콘텐츠와 그래프 상호작용은 main 슬롯 밖에서 주입받습니다.
 */

const ASSET_BASE = "/design/figma/assets";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function categoryLinks(categories) {
  return categories
    .map(
      (category) => `
        <a
          class="sidebar__category-link"
          data-route
          data-category-id="${escapeHtml(category.id)}"
          href="/category/${encodeURIComponent(category.id)}"
        >${escapeHtml(category.name)}</a>
      `,
    )
    .join("");
}

function recentLinks(recentExplorations) {
  if (recentExplorations.length === 0) {
    return '<p class="sidebar__recent-empty">아직 탐색 기록이 없어요.</p>';
  }

  return recentExplorations
    .map(
      (entry) => `
        <a
          class="sidebar__recent-link"
          data-route
          data-node-id="${escapeHtml(entry.nodeId)}"
          href="${escapeHtml(entry.href)}"
        >
          <img src="${ASSET_BASE}/recent-clock.svg" alt="" />
          <span>${escapeHtml(entry.label)}</span>
        </a>
      `,
    )
    .join("");
}

/** 공통 셸 DOM을 만들고 현재 경로에 따른 갱신 API를 반환합니다. */
export function createAppShell(model) {
  const shell = document.createElement("div");
  shell.className = "app-shell";
  shell.innerHTML = `
    <a class="skip-link" href="#main-content">본문으로 건너뛰기</a>
    <p class="route-announcer sr-only" role="status" aria-live="polite" aria-atomic="true"></p>
    <aside class="sidebar" aria-label="주요 메뉴">
      <p class="sidebar__eyebrow">MENU</p>

      <nav class="sidebar__primary" aria-label="주요 화면">
        <a class="sidebar__primary-link" data-route data-nav="home" href="/">
          <img src="${ASSET_BASE}/sidebar-home.svg" alt="" />
          <span>홈</span>
        </a>
        <a
          class="sidebar__primary-link"
          data-route
          data-nav="my-world"
          href="/my-world/records"
        >
          <img src="${ASSET_BASE}/sidebar-galaxy.svg" alt="" />
          <span>나의 뉴스 세계</span>
        </a>
      </nav>

      <div class="sidebar__divider" aria-hidden="true"></div>
      <p class="sidebar__section-title">분야별 탐색</p>
      <nav class="sidebar__categories" aria-label="뉴스 분야">
        ${categoryLinks(model.categories)}
      </nav>

      <div class="sidebar__divider sidebar__divider--recent" aria-hidden="true"></div>
      <p class="sidebar__section-title">최근 탐색</p>
      <nav class="sidebar__recent" aria-label="최근 탐색">
        ${recentLinks(model.recentExplorations)}
      </nav>
    </aside>

    <div class="workspace">
      <header class="app-header">
        <a class="brand" data-route href="/" aria-label="별빛 뉴스 홈">
          <strong>별빛 뉴스</strong>
          <span>매일 보는 나의 뉴스 지도</span>
        </a>

        <button
          id="profile-button"
          class="profile-button"
          type="button"
          aria-label="프로필 메뉴 열기"
          aria-haspopup="menu"
          aria-expanded="false"
          aria-controls="profile-menu"
        >
          <img src="${ASSET_BASE}/profile.svg" alt="" />
        </button>

        <div
          class="profile-menu"
          id="profile-menu"
          role="menu"
          aria-labelledby="profile-button"
          hidden
        >
          <a role="menuitem" data-route data-settings-section="account" href="/settings/account">
            <span>계정 설정</span><span aria-hidden="true">›</span>
          </a>
          <a role="menuitem" data-route data-settings-section="dislikes" href="/settings/dislikes">
            <span>관심 없음 관리</span><span aria-hidden="true">›</span>
          </a>
          <a role="menuitem" data-route data-settings-section="display" href="/settings/display">
            <span>화면 설정</span><span aria-hidden="true">›</span>
          </a>
          <div class="profile-menu__divider" aria-hidden="true"></div>
          <button role="menuitem" type="button" data-action="logout">로그아웃</button>
        </div>
      </header>

      <main id="main-content" class="app-main" tabindex="-1"></main>
    </div>

    <div class="mock-toast" role="status" hidden></div>
  `;

  const main = shell.querySelector("#main-content");
  const sidebar = shell.querySelector(".sidebar");
  const header = shell.querySelector(".app-header");
  const profileButton = shell.querySelector(".profile-button");
  const profileMenu = shell.querySelector(".profile-menu");
  const toast = shell.querySelector(".mock-toast");
  const routeAnnouncer = shell.querySelector(".route-announcer");
  let toastTimer;

  const setProfileMenuOpen = (open) => {
    profileMenu.hidden = !open;
    profileButton.setAttribute("aria-expanded", String(open));
    profileButton.setAttribute(
      "aria-label",
      open ? "프로필 메뉴 닫기" : "프로필 메뉴 열기",
    );
  };

  const showToast = (message) => {
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toastTimer = window.setTimeout(() => {
      toast.hidden = true;
    }, 2600);
  };

  const updateSettingsReturnLinks = () => {
    const current = `${window.location.pathname}${window.location.search}`;
    const returnPath = current.startsWith("/settings/") ? "/" : current;
    profileMenu.querySelectorAll("[data-settings-section]").forEach((link) => {
      link.href = `/settings/${link.dataset.settingsSection}?return=${encodeURIComponent(returnPath)}`;
    });
  };

  profileButton.addEventListener("click", () => {
    const willOpen = profileMenu.hidden;
    updateSettingsReturnLinks();
    setProfileMenuOpen(willOpen);
    if (willOpen) {
      profileMenu.querySelector('[role="menuitem"]').focus();
    }
  });

  profileMenu.addEventListener("keydown", (event) => {
    const menuItem = event.target.closest('[role="menuitem"]');
    if (menuItem && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      menuItem.click();
      return;
    }
    const items = [...profileMenu.querySelectorAll('[role="menuitem"]')];
    const currentIndex = items.indexOf(document.activeElement);
    const destinations = {
      ArrowDown: (currentIndex + 1) % items.length,
      ArrowUp: (currentIndex - 1 + items.length) % items.length,
      Home: 0,
      End: items.length - 1,
    };
    if (destinations[event.key] == null) {
      return;
    }
    event.preventDefault();
    items[destinations[event.key]].focus();
  });

  shell.addEventListener("click", (event) => {
    if (event.target.closest('[data-action="logout"]')) {
      setProfileMenuOpen(false);
      showToast("목업에서는 로그아웃 상태만 확인합니다.");
      return;
    }

    if (event.target.closest(".profile-menu a[data-route]")) {
      setProfileMenuOpen(false);
    }
  });

  shell.addEventListener("mocktoast", (event) => {
    if (event.detail?.message) {
      showToast(event.detail.message);
    }
  });

  document.addEventListener("click", (event) => {
    if (!profileMenu.hidden && !event.target.closest(".app-header")) {
      setProfileMenuOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !profileMenu.hidden) {
      setProfileMenuOpen(false);
      profileButton.focus();
    }
  });

  const updateActiveNavigation = (route) => {
    shell.querySelectorAll("[aria-current]").forEach((element) => {
      element.removeAttribute("aria-current");
    });

    if (["home", "search", "explore"].includes(route.id)) {
      shell.querySelector('[data-nav="home"]').setAttribute("aria-current", "page");
    }

    if (["records", "report", "personalMap"].includes(route.id)) {
      shell.querySelector('[data-nav="my-world"]').setAttribute("aria-current", "page");
    }

    if (route.id === "category") {
      shell
        .querySelector(`[data-category-id="${CSS.escape(route.params.categoryId)}"]`)
        ?.setAttribute("aria-current", "page");
    }

    if (route.id === "explore" && route.params.nodeId) {
      shell
        .querySelector(`[data-node-id="${CSS.escape(route.params.nodeId)}"]`)
        ?.setAttribute("aria-current", "page");
    }
  };

  return {
    element: shell,
    render(route, pageElement) {
      setProfileMenuOpen(false);
      updateActiveNavigation(route);
      const isPersonalMap = route.id === "personalMap";
      const isSettings = route.id === "settings";
      shell.classList.toggle("is-personal-map-route", isPersonalMap);
      sidebar.inert = isPersonalMap || isSettings;
      header.inert = isPersonalMap || isSettings;
      document.body.classList.toggle("has-personal-map", isPersonalMap);
      document.body.classList.toggle("has-settings-overlay", isSettings);
      main.replaceChildren(pageElement);
      main.dataset.route = route.id;
      routeAnnouncer.textContent = `${pageElement.dataset.documentTitle || route.title} 화면`;
    },
    focusMain() {
      const routeFocus = main.querySelector("[data-route-focus]");
      const heading = main.querySelector('h1[tabindex="-1"]');
      (routeFocus || heading || main).focus({ preventScroll: true });
    },
  };
}
