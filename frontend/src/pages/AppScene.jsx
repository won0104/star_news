import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { backdrop, extraViews, navItems } from '../data/home'
import { arrivalScene } from '../data/recommend'
import { nightfall } from '../data/trend'
import { PhotoBackdrop } from '../components/common/PhotoBackdrop'
import { TopBar } from '../components/common/TopBar'
import { ViewPane } from '../components/world/ViewPane'
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
const TREND_BACKDROP = { id: 'trend', src: nightfall.backdrops.landscape, loop: null }
const HISTORY_BACKDROP = {
  id: 'history',
  src: '/assets/history/history-desk-background.png',
  loop: null,
}

/**
 * 공용 햇살 방 대신 자기 사진을 바닥으로 쓰는 목적지. 오늘의 트렌드는 밤 창가, 나를 위한
 * 추천은 코르크 보드가 걸린 벽, 나의 기록은 나무 책상 — 모두 화면이 그 사진 위에 직접
 * 그려지므로, 사진이 다르면 화면이 어긋난다.
 */
const SCENE_BY_VIEW = {
  trend: TREND_BACKDROP,
  foryou: arrivalScene,
  log: HISTORY_BACKDROP,
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

  const arriving = !walked && enteredFromHome
  const scene = (arriving && ARRIVAL[view]) || SCENE_BY_VIEW[view] || backdrop
  const motion = SCREEN_TRANSITIONS && !reduceMotion && scene !== backdrop
  const [settled, setSettled] = useState(false)
  const onSettled = useCallback(() => setSettled(true), [])

  return (
    <PhotoBackdrop
      key={scene.id}
      scene={scene}
      motion={motion}
      hideScrollbar={view === 'trend'}
      onSettled={onSettled}
    >
      <TopBar
        activeId={view === 'foryou2' ? 'foryou' : view}
        nightGlass={view === 'trend'}
        onSelect={open}
        onBrand={() => navigate('/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />
      <ViewPane
        key={account?.user?.userId ?? (account ? 'signed-in' : 'guest')}
        view={view}
        settled={settled}
        playTrendTransition={arriving && view === 'trend'}
      />
    </PhotoBackdrop>
  )
}
