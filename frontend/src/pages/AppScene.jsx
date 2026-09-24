import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { backdrop, viewIds } from '../data/home'
import { arrivalScene } from '../data/recommend'
import { BOARDS } from '../data/recommendBoard'
import { desks } from '../data/history'
import { useNearestWindow } from '../hooks/useNearestWindow'
import { nightBackdrop, nightfall } from '../data/trend'
import { PhotoBackdrop } from '../components/common/PhotoBackdrop'
import { TopBar } from '../components/common/TopBar'
import { ViewPane } from '../components/world/ViewPane'
import { warmHistoryPlanet } from '../components/world/historyPlanetChunk'
import { useSession } from '../store/session'
import { useSettingsValues } from '../store/settings'
import { SCREEN_TRANSITIONS } from '../utils/motion'

/** Falls back rather than rendering nothing when `?view=` is absent or unrecognised. */
const DEFAULT_VIEW = 'trend'
const VIEWS = new Set(viewIds)

/**
 * The clip a destination is arrived on, by destination. A destination with no entry is
 * simply arrived on without one — which is every destination but 나를 위한 추천 today.
 */
const ARRIVAL = { foryou: arrivalScene }
/** 사진은 비율에 맞춰 아래에서 고른다 — 여기서는 어느 방인지만 정한다. */
const TREND_BACKDROP = { id: 'trend', loop: null }
const HISTORY_BACKDROP = { id: 'history', loop: null }

/**
 * 공용 햇살 방 대신 자기 사진을 바닥으로 쓰는 목적지. 오늘의 트렌드는 밤 창가, 나를 위한
 * 추천은 코르크 보드가 걸린 벽, 나의 기록은 나무 책상 — 모두 화면이 그 사진 위에 직접
 * 그려지므로, 사진이 다르면 화면이 어긋난다.
 */
const SCENE_BY_VIEW = {
  trend: TREND_BACKDROP,
  foryou: arrivalScene,
  log: HISTORY_BACKDROP,
  // 나의 리포트는 나의 기록과 같은 책이다 — 방이 다르면 같은 책이 두 곳에 있는 것으로 읽힌다.
  // id 가 같아 두 화면을 오갈 때 <PhotoBackdrop> 이 remount 되지 않고 책상이 그대로 남는다.
  report: HISTORY_BACKDROP,
}

/**
 * /app — the sunlit room, the bar over it, and one of the bar's four destinations on top.
 *
 * The room is still the ground rather than a texture behind a dashboard: the views draw
 * paper cards, so the photograph (and the clip that plays once over it) reads around
 * them. The room with nothing over it at all is the front door, at /; see <MainScene>.
 *
 * The brand mark leaves for it, which is why <TopBar> is given an `onBrand` of its own
 * here: inside the app the four buttons are destinations, and the mark is the way out to
 * the front of the site rather than a fifth one.
 *
 * Which destination is open lives in the URL, not in state, and that is what lets the
 * bar work the same from here and from /trend — the attic has no pane of its own to
 * switch, so its bar navigates here with the choice attached instead of dropping it.
 * It also makes a screen linkable and survives a reload, which `useState` did not.
 *
 * 화면 설정's 애니메이션 없애기 is read here rather than inside <BackgroundVideo>: with
 * `motion` false the clip is never handed over, so it is not fetched at all instead of
 * fetched and then hidden. The OS's own reduced-motion setting is still honoured
 * separately, further in.
 *
 * A transition clip plays for one kind of move only: the one that starts at the front
 * door. <MainScene> marks its navigation with `from: 'home'`, and that mark is read once,
 * here. Walking the bar afterwards switches destinations with no motion at all — which is
 * also why the room's own loop is not played inside /app any more; it belongs to the front
 * door, where it still runs.
 *
 * `walked` is what makes the arrival one-shot. The mark stays in the history entry, so
 * without it a reader who left 나를 위한 추천 and came back would be given the clip a second
 * time. The first press of the bar ends the arrival for good.
 *
 * The `key` is what actually plays the clip: <PhotoBackdrop> holds its own played/retired
 * state, so handing a finished video a new src would do nothing. Keying by scene remounts
 * it. That costs the scroll position when the scene changes, which happens on the way out
 * of an arrival — a destination opening at its top is the ordinary thing.
 *
 * `settled` is passed on to the destination so it can come in after the room has stopped
 * moving rather than over the top of it. With no clip to wait for it is true immediately,
 * which is every case but an arrival.
 */
export function AppScene() {
  const account = useSession()
  const navigate = useNavigate()
  const location = useLocation()
  const { reduceMotion } = useSettingsValues()
  const [params, setParams] = useSearchParams()
  const [walked, setWalked] = useState(false)
  /*
   * 현관에서 고른 사건을 안고 올 수 있다. 도착과 함께 아래 효과가 history state 를 비우므로,
   * 첫 렌더에서 한 번만 도는 초기값으로 집는다 — 그 다음에는 읽을 자리에 없다.
   */
  const [selectedNode, setSelectedNode] = useState(() => {
    const arrived = location.state?.node
    return arrived ? { ...arrived, selectionId: 1 } : null
  })
  const [enteredFromHome] = useState(() => location.state?.from === 'home')
  /*
   * 검색으로 실려 온 것인지.
   *
   * 화면은 오늘의 트렌드가 맞지만 읽는 이가 고른 것은 그 목적지가 아니라 사건 하나다. 내비에
   * 오늘의 트렌드가 켜져 있으면 "내가 오늘의 트렌드를 눌렀다"고 읽히므로, 갈래인 탐색만 켠다.
   * 내비를 직접 누르는 순간 그 말은 더 이상 참이 아니어서 open 에서 끈다.
   */
  const [fromSearch, setFromSearch] = useState(() => Boolean(location.state?.node))
  /*
   * 목적지를 누른 횟수. 별자리를 처음 상태로 되돌리는 열쇠다.
   *
   * 별자리는 어느 사건을 펼쳐 보고 있는지를 스스로 쥐고 있고(<TrendSky> 의 trail), 그 안에만
   * 돌아가는 길이 있다. 이미 오늘의 트렌드에 서 있는 채로 오늘의 트렌드를 누르면 `?view=` 가
   * 그대로라 다시 그려지지도 않아, 아무 일도 일어나지 않은 것처럼 보인다.
   *
   * 상태를 밖으로 끌어내는 대신 key 를 바꿔 새로 세운다 — 목적지를 누른다는 것은 그 화면을
   * 처음부터 본다는 뜻이고, 그 말을 그대로 옮긴 것이다.
   */
  const [visit, setVisit] = useState(0)

  const asked = params.get('view')
  const view = asked === 'log2' ? 'log' : VIEWS.has(asked) ? asked : DEFAULT_VIEW

  useEffect(() => {
    if (asked !== 'log2') return
    const canonicalParams = new URLSearchParams(params)
    canonicalParams.set('view', 'log')
    setParams(canonicalParams, { replace: true })
  }, [asked, params, setParams])

  useEffect(() => {
    if (!enteredFromHome || location.state?.from !== 'home') return
    navigate(
      { pathname: location.pathname, search: location.search, hash: location.hash },
      { replace: true, state: null },
    )
  }, [enteredFromHome, location.hash, location.pathname, location.search, location.state, navigate])

  // `replace`, so walking the bar does not pile up history entries to back out of.
  const open = (id) => {
    // 탐색은 /app 의 한 화면이 아니라 현관이다 — `?view=` 로는 갈 수 없다.
    if (id === 'home') {
      navigate('/')
      return
    }
    /*
     * 목적지를 고른 것이므로 보고 있던 사건은 놓는다.
     *
     * 검색으로 실려 온 사건을 그대로 안고 있으면, 오늘의 트렌드를 눌러도 화면이 그 사건에
     * 머물러 아무 일도 일어나지 않은 것처럼 보인다. 누른 것은 사건이 아니라 그 목적지다.
     */
    setSelectedNode(null)
    setFromSearch(false)
    setVisit((count) => count + 1)
    setWalked(true)
    setParams(id === DEFAULT_VIEW ? {} : { view: id }, { replace: true })
  }

  const arriving = !walked && enteredFromHome
  // 코르크 방은 비율마다 따로 그려져 있다. 고르는 기준이 뷰포트이므로 <RecommendPane> 이
  // 같은 훅으로 같은 보드를 고르고, 종이는 그 보드의 코르크 위에 앉는다.
  const board = useNearestWindow(BOARDS)
  // 책상도 비율마다 그려져 있다. 책은 자기 상자를 가지므로 사진만 갈아끼우면 된다.
  const desk = useNearestWindow(desks)
  // 밤 창가. <TrendStage> 가 같은 장을 골라야 하므로 양쪽 모두 ref 없이 뷰포트로 잰다 —
  // useNearestWindow 주석의 "합의해야 하는 두 겹은 둘 다 ref 를 생략한다" 가 이 경우다.
  const nightWindow = useNearestWindow(nightfall.frames)
  const chosen = (arriving && ARRIVAL[view]) || SCENE_BY_VIEW[view] || backdrop
  const scene =
    chosen === arrivalScene
      ? { ...arrivalScene, src: board.src, standIn: board.standIn }
      : chosen === HISTORY_BACKDROP
        ? { ...HISTORY_BACKDROP, src: desk.src, standIn: desk.standIn }
        : chosen === TREND_BACKDROP
          ? { ...TREND_BACKDROP, ...nightBackdrop(nightWindow) }
          : chosen
  const motion = SCREEN_TRANSITIONS && !reduceMotion && scene !== backdrop
  const [settled, setSettled] = useState(false)
  const onSettled = useCallback(() => setSettled(true), [])

  /*
   * 나의 기록과 나의 리포트는 같은 책이고, 그 위에 행성이 선다. 둘 중 어느 쪽에 손이
   * 닿아도 같은 청크가 필요하므로 함께 본다.
   */
  const warmOnIntent = useCallback((id) => {
    if (id === 'log' || id === 'report') warmHistoryPlanet()
  }, [])


  return (
    <PhotoBackdrop
      key={scene.id}
      scene={scene}
      motion={motion}
      hideScrollbar={view === 'trend'}
      onSettled={onSettled}
    >
      <TopBar
        activeId={fromSearch ? 'home' : view}
        nightGlass={view === 'trend'}
        onSelect={open}
        onIntent={warmOnIntent}
        onBrand={() => navigate('/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />
      <ViewPane
        key={account?.user?.userId ?? (account ? 'signed-in' : 'guest')}
        view={view}
        visit={visit}
        settled={settled}
        playTrendTransition={arriving && view === 'trend'}
        selectedNode={selectedNode}
      />
    </PhotoBackdrop>
  )
}
