/**
 * 행성 청크를 가리키는 한 곳.
 *
 * <HistoryPlanet> 은 three.js 를 들고 있어 이 화면만 619KB 를 더 받는다. 그래서 따로
 * 갈라 두었고, 필요할 때 받는다.
 *
 * 받는 곳이 둘이라 지정자를 여기 한 번만 적는다 — <DiaryHistoryPane> 의 lazy 와, 목적지를
 * 누르기 전에 시작하는 예열. 같은 지정자여야 모듈 레지스트리가 같은 것으로 묶어 두 번
 * 받지 않는다. 한쪽에 경로를 다시 적으면 그 보장이 조용히 깨진다.
 *
 * 파일을 나눈 것은 Fast Refresh 때문이기도 하다. 컴포넌트를 내보내는 파일이 함수도 함께
 * 내보내면 갱신이 동작하지 않는다(react-refresh/only-export-components).
 */
export const loadHistoryPlanet = () => import('./HistoryPlanet')

/**
 * 목적지에 손이 닿은 순간 청크를 미리 받아 둔다.
 *
 * <Suspense> 가 그동안 어두운 상자에 글자를 세워 두므로 자리는 흔들리지 않지만, 기다림
 * 자체는 남는다. 포인터가 올라오거나 초점이 닿는 순간은 목적지를 고른 순간에 가장 가까워서,
 * 그때 시작하면 도착했을 때 이미 와 있는 경우가 많다.
 *
 * 실패는 삼킨다. 예열은 거들 뿐이고 진짜 로드는 <Suspense> 가 다시 시도한다 — 여기서 던지면
 * 아무도 받지 않는 거부가 된다.
 */
export const warmHistoryPlanet = () => {
  loadHistoryPlanet().catch(() => {})
}
