import { useCallback, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { backdrop, navItems } from '../data/home';
import { arrivalScene } from '../data/recommend';
import { PhotoBackdrop } from '../components/common/PhotoBackdrop';
import { TopBar } from '../components/common/TopBar';
import { ViewPane } from '../components/world/ViewPane';
import { useSettingsValues } from '../store/settings';

/** Falls back rather than rendering nothing when `?view=` is absent or unrecognised. */
const DEFAULT_VIEW = 'trend';
const VIEWS = new Set(navItems.map((item) => item.id));

/**
 * The clip a destination is arrived on, by destination. A destination with no entry is
 * simply arrived on without one — which is every destination but 나를 위한 추천 today.
 */
const ARRIVAL = { foryou: arrivalScene };

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
  const navigate = useNavigate();
  const location = useLocation();
  const { reduceMotion } = useSettingsValues();
  const [params, setParams] = useSearchParams();
  const [walked, setWalked] = useState(false);

  const asked = params.get('view');
  const view = VIEWS.has(asked) ? asked : DEFAULT_VIEW;

  // `replace`, so walking the bar does not pile up history entries to back out of.
  const open = (id) => {
    setWalked(true);
    setParams(id === DEFAULT_VIEW ? {} : { view: id }, { replace: true });
  };

  const arriving = !walked && location.state?.from === 'home';
  const scene = (arriving && ARRIVAL[view]) || backdrop;
  const motion = !reduceMotion && scene !== backdrop;
  const [settled, setSettled] = useState(false);
  const onSettled = useCallback(() => setSettled(true), []);

  return (
    <PhotoBackdrop key={scene.id} scene={scene} motion={motion} onSettled={onSettled}>
      <TopBar
        activeId={view}
        onSelect={open}
        onBrand={() => navigate('/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />
      <ViewPane view={view} settled={settled} />
    </PhotoBackdrop>
  );
}
