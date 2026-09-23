import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { backdrop, extraViews, navItems } from '../data/home'
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
const VIEWS = new Set([...navItems, ...extraViews].map((item) => item.id))

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
  const [selectedNode, setSelectedNode] = useState(null)
  const [enteredFromHome] = useState(() => location.state?.from === 'home')

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
    setWalked(true)
    setParams(id === DEFAULT_VIEW ? {} : { view: id }, { replace: true })
  }

  const openSearchedNode = (node) => {
    setWalked(true)
    setSelectedNode((current) => ({
      ...node,
      selectionId: (current?.selectionId ?? 0) + 1,
    }))
    if (view !== 'trend') setParams({}, { replace: true })
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
        activeId={view}
        nightGlass={view === 'trend'}
        onSelect={open}
        onIntent={warmOnIntent}
        onBrand={() => navigate('/')}
        onAuth={(kind) => navigate(`/${kind}`)}
        search={view === 'trend'}
        onSearchSelect={openSearchedNode}
      />
      <ViewPane
        key={account?.user?.userId ?? (account ? 'signed-in' : 'guest')}
        view={view}
        settled={settled}
        playTrendTransition={arriving && view === 'trend'}
        selectedNode={selectedNode}
      />
    </PhotoBackdrop>
  )
}
