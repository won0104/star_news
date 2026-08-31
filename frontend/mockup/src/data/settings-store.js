/**
 * 설정 화면의 저장 전 draft와 저장된 목업 상태를 분리합니다.
 * 원본 데이터는 수정하지 않고 같은 탭의 sessionStorage에만 저장합니다.
 */

const STORAGE_PREFIX = "starlight-news:settings:v1";
const VALID_THEMES = new Set(["light", "dark", "system"]);
const VALID_FONT_SIZES = new Set(["normal", "large"]);
const storesByModel = new WeakMap();

function cloneState(state) {
  return {
    account: { ...state.account },
    dislikes: [...state.dislikes],
    display: { ...state.display },
  };
}

function buildCandidates(model) {
  const candidates = model.categories.map((category) => ({
    id: category.id,
    label: category.name,
    kind: "분야",
  }));
  const topicTypes = new Set(["topic", "technology", "industry", "sport"]);

  for (const node of model.dataset.nodes) {
    if (!topicTypes.has(node.type)) {
      continue;
    }
    candidates.push({ id: node.id, label: node.label, kind: "주제" });
  }

  const seen = new Set();
  return candidates.filter((candidate) => {
    const normalized = candidate.label.trim().toLocaleLowerCase("ko-KR");
    if (!normalized || seen.has(normalized)) {
      return false;
    }
    seen.add(normalized);
    return true;
  });
}

function createDefaultState(model, candidateIds) {
  return {
    account: {
      displayName: model.user.display_name || "별빛 사용자",
    },
    dislikes: (model.user.not_interested ?? []).filter((id) => candidateIds.has(id)),
    display: {
      theme: "light",
      fontSize: "normal",
      reducedMotion: false,
    },
  };
}

function normalizeStoredState(value, defaults, candidateIds) {
  if (!value || typeof value !== "object") {
    return defaults;
  }
  const displayName = typeof value.account?.displayName === "string"
    && value.account.displayName.trim()
    ? value.account.displayName.trim().slice(0, 40)
    : defaults.account.displayName;
  const dislikes = Array.isArray(value.dislikes)
    ? [...new Set(value.dislikes.filter((id) => candidateIds.has(id)))]
    : defaults.dislikes;
  return {
    account: { displayName },
    dislikes,
    display: {
      theme: VALID_THEMES.has(value.display?.theme)
        ? value.display.theme
        : defaults.display.theme,
      fontSize: VALID_FONT_SIZES.has(value.display?.fontSize)
        ? value.display.fontSize
        : defaults.display.fontSize,
      reducedMotion: typeof value.display?.reducedMotion === "boolean"
        ? value.display.reducedMotion
        : defaults.display.reducedMotion,
    },
  };
}

function readStoredState(storage, key, defaults, candidateIds) {
  if (!storage) {
    return defaults;
  }
  try {
    return normalizeStoredState(JSON.parse(storage.getItem(key)), defaults, candidateIds);
  } catch {
    return defaults;
  }
}

function writeStoredState(storage, key, state) {
  if (!storage) {
    return;
  }
  try {
    storage.setItem(key, JSON.stringify(state));
  } catch {
    // 저장소가 차단된 환경에서도 현재 문서 안의 목업 상태는 유지합니다.
  }
}

/** 사용자 데이터와 선택 가능한 분야·주제만 사용해 독립된 설정 저장소를 만듭니다. */
export function createSettingsStore(model, { storage = null } = {}) {
  const candidates = buildCandidates(model);
  const candidateIds = new Set(candidates.map((candidate) => candidate.id));
  const defaults = createDefaultState(model, candidateIds);
  const key = `${STORAGE_PREFIX}:${model.user.id}`;
  let state = readStoredState(storage, key, defaults, candidateIds);

  const persist = () => writeStoredState(storage, key, state);

  return {
    candidates,
    getState() {
      return cloneState(state);
    },
    findCandidateByLabel(label) {
      const normalized = String(label ?? "").trim().toLocaleLowerCase("ko-KR");
      return candidates.find(
        (candidate) => candidate.label.toLocaleLowerCase("ko-KR") === normalized,
      ) ?? null;
    },
    getCandidate(id) {
      return candidates.find((candidate) => candidate.id === id) ?? null;
    },
    saveAccount(displayName) {
      const normalized = String(displayName ?? "").trim().slice(0, 40);
      if (!normalized) {
        throw new TypeError("프로필 이름을 입력해 주세요.");
      }
      state = { ...state, account: { displayName: normalized } };
      persist();
      return this.getState();
    },
    saveDislikes(ids) {
      state = {
        ...state,
        dislikes: [...new Set(ids)].filter((id) => candidateIds.has(id)),
      };
      persist();
      return this.getState();
    },
    saveDisplay(display) {
      state = normalizeStoredState({ ...state, display }, state, candidateIds);
      persist();
      return this.getState();
    },
  };
}

/** 앱에서 같은 model 인스턴스에 하나의 설정 저장소를 공유합니다. */
export function getSettingsStore(model) {
  if (!storesByModel.has(model)) {
    let storage = null;
    try {
      storage = globalThis.sessionStorage ?? null;
    } catch {
      storage = null;
    }
    storesByModel.set(model, createSettingsStore(model, { storage }));
  }
  return storesByModel.get(model);
}

/** 저장된 화면 설정을 전역 data 속성으로 반영해 CSS가 소비하도록 합니다. */
export function applyDisplayPreferences(display, root = document.documentElement) {
  const theme = VALID_THEMES.has(display?.theme) ? display.theme : "light";
  const fontSize = VALID_FONT_SIZES.has(display?.fontSize) ? display.fontSize : "normal";
  const systemIsDark = theme === "system"
    && typeof globalThis.matchMedia === "function"
    && globalThis.matchMedia("(prefers-color-scheme: dark)").matches;

  root.dataset.displayTheme = theme;
  root.dataset.effectiveTheme = theme === "dark" || systemIsDark ? "dark" : "light";
  root.dataset.fontSize = fontSize;
  root.dataset.reducedMotion = String(Boolean(display?.reducedMotion));
}

/** 명시적 비선호와 같은 노드 또는 분야에 속한 개인 추천 seed만 제외합니다. */
export function filterRecommendationSeeds(model, seeds, dislikeIds) {
  const dislikes = new Set(dislikeIds);
  return seeds.filter((entry) => {
    const node = model.nodeById.get(entry.node_id);
    return node && !dislikes.has(node.id) && !dislikes.has(node.category_id);
  });
}
