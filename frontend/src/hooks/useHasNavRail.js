import { useSyncExternalStore } from 'react';

/**
 * 내비게이션이 상단바가 아니라 왼쪽 세로 레일로 서는 폭인가.
 *
 * useIsNarrow 의 900px 과는 다른 질문이라 따로 둔다. 그쪽은 나란히 놓인 것들이 서로
 * 부딪치기 시작하는 폭이고, 이쪽은 내비게이션이 가로에서 세로로 바뀌는 지점이다.
 *
 * 1024 는 TopBar.module.css 가 레일로 바꾸는 폭과 같은 값이어야 한다 — 어긋나면 검색창이
 * 레일 자리에 앉았는데 레일이 아니거나, 그 반대가 된다. 한쪽을 바꾸면 다른 쪽도 바꾼다.
 */
export const NAV_RAIL_QUERY = '(min-width: 1024px)';

/** 첫 사용 때 만든다 — DOM 이 없는 곳에서도 모듈을 읽을 수 있게. */
let query;
const media = () => (query ??= window.matchMedia(NAV_RAIL_QUERY));

const subscribe = (onChange) => {
  const list = media();
  list.addEventListener('change', onChange);
  return () => list.removeEventListener('change', onChange);
};

const getSnapshot = () => media().matches;

/** 내비게이션이 세로 레일로 서 있는 동안 true. */
export function useHasNavRail() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
