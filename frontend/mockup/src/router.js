/**
 * 별빛 뉴스 화면 경로를 해석하고 브라우저 History API 이동을 관리합니다.
 * 화면 렌더링이나 데이터 검증은 담당하지 않습니다.
 */

const routeDefinitions = [
  { id: "home", pattern: /^\/$/, title: "홈" },
  {
    id: "category",
    pattern: /^\/category\/([^/]+)\/?$/,
    paramNames: ["categoryId"],
    title: "분야별 탐색",
  },
  { id: "search", pattern: /^\/search\/?$/, title: "검색 결과" },
  {
    id: "explore",
    pattern: /^\/explore(?:\/([^/]+))?\/?$/,
    paramNames: ["nodeId"],
    title: "뉴스 탐색",
  },
  {
    id: "records",
    pattern: /^\/my-world(?:\/records)?\/?$/,
    title: "나의 기록",
  },
  {
    id: "report",
    pattern: /^\/my-world\/report\/?$/,
    title: "나의 리포트",
  },
  {
    id: "personalMap",
    pattern: /^\/my-world\/map\/?$/,
    title: "나의 기록 지도",
  },
  {
    id: "settings",
    pattern: /^\/settings\/(account|dislikes|display)\/?$/,
    paramNames: ["section"],
    title: "설정",
  },
];

function safeDecode(value) {
  if (value == null) {
    return undefined;
  }

  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** 주어진 URL 경로를 화면 식별자, 경로 매개변수, query로 변환합니다. */
export function resolveRoute(pathname, search = "") {
  const normalizedPath = pathname || "/";
  const normalizedSearch = search.startsWith("?") ? search : search ? `?${search}` : "";

  for (const definition of routeDefinitions) {
    const match = normalizedPath.match(definition.pattern);
    if (!match) {
      continue;
    }

    const params = Object.fromEntries(
      (definition.paramNames ?? []).map((name, index) => [
        name,
        safeDecode(match[index + 1]),
      ]),
    );

    return {
      id: definition.id,
      title: definition.title,
      pathname: normalizedPath,
      search: normalizedSearch,
      searchParams: new URLSearchParams(normalizedSearch),
      params,
      isNotFound: false,
    };
  }

  return {
    id: "notFound",
    title: "페이지를 찾을 수 없음",
    pathname: normalizedPath,
    search: normalizedSearch,
    searchParams: new URLSearchParams(normalizedSearch),
    params: {},
    isNotFound: true,
  };
}

/**
 * 같은 origin의 `a[data-route]`만 가로채는 클라이언트 라우터를 만듭니다.
 * 새 탭, 다운로드, 보조 클릭과 외부 링크는 브라우저 기본 동작을 유지합니다.
 */
export function createRouter({ onRoute, windowObject = window }) {
  const documentObject = windowObject.document;

  const emit = () => {
    onRoute(resolveRoute(windowObject.location.pathname, windowObject.location.search));
  };

  const navigate = (href, { replace = false, transitionSource = null } = {}) => {
    const target = new URL(href, windowObject.location.href);
    if (target.origin !== windowObject.location.origin) {
      windowObject.location.assign(target.href);
      return;
    }

    const current = `${windowObject.location.pathname}${windowObject.location.search}${windowObject.location.hash}`;
    const next = `${target.pathname}${target.search}${target.hash}`;
    if (current === next) {
      emit();
      return;
    }

    const commit = () => {
      windowObject.history[replace ? "replaceState" : "pushState"]({}, "", next);
      emit();
    };
    const root = documentObject.documentElement;
    const prefersReducedMotion = root.dataset.reducedMotion === "true"
      || windowObject.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (
      transitionSource
      && typeof documentObject.startViewTransition === "function"
      && !prefersReducedMotion
    ) {
      const previousTransitionTarget = documentObject.querySelector(
        '[style*="view-transition-name: exploration-focus"]',
      );
      if (previousTransitionTarget && previousTransitionTarget !== transitionSource) {
        previousTransitionTarget.style.removeProperty("view-transition-name");
      }
      transitionSource.style.viewTransitionName = "exploration-focus";
      const clearTransitionName = () => {
        transitionSource.style.removeProperty("view-transition-name");
      };
      try {
        const transition = documentObject.startViewTransition(commit);
        transition.finished.then(clearTransitionName, clearTransitionName);
        return;
      } catch {
        clearTransitionName();
      }
    }
    commit();
  };

  const handleClick = (event) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    const link = event.target.closest("a[data-route]");
    if (
      !link
      || link.hasAttribute("download")
      || link.getAttribute("target") === "_blank"
    ) {
      return;
    }

    const target = new URL(link.getAttribute("href"), windowObject.location.href);
    if (target.origin !== windowObject.location.origin) {
      return;
    }

    event.preventDefault();
    navigate(target.href, {
      transitionSource: link.closest("[data-transition-focus]"),
    });
  };

  documentObject.addEventListener("click", handleClick);
  windowObject.addEventListener("popstate", emit);

  return {
    start: emit,
    navigate,
    destroy() {
      documentObject.removeEventListener("click", handleClick);
      windowObject.removeEventListener("popstate", emit);
    },
  };
}
