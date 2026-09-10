import { useNavigate } from 'react-router-dom';
import { PhotoBackdrop } from '../components/common/PhotoBackdrop';
import { TopBar } from '../components/common/TopBar';
import { useSettingsValues } from '../store/settings';

/**
 * 메인 페이지 — the sunlit-room photograph edge to edge, with only the top bar over it.
 *
 * The front of the site, and the screen / answers with.
 *
 * Kept whole rather than dissolved into the app that briefly held this route: the room in
 * motion is the whole of this screen, and nothing here competes with it, so the clip
 * reads as the page instead of as decoration behind content. Over in /app, where the
 * panes sit on the same room, it can only ever be the latter.
 *
 * The bar is the same bar, so its four buttons lead into /app rather than switching
 * anything here, and `?view=` is how the choice survives the hop — exactly as it does
 * from the attic. None of the four is current, because this screen is not one of them.
 *
 * `state: { from: 'home' }` rides along with that hop, and it is the whole of how /app
 * knows to play a transition clip: a move that starts here is the only kind that gets
 * one. Nothing else sets it — the attic's bar, the auth screens and a typed URL all
 * arrive without it, and arrive without motion.
 */
export function MainScene() {
  const navigate = useNavigate();
  const { reduceMotion } = useSettingsValues();

  return (
    <PhotoBackdrop motion={!reduceMotion}>
      <TopBar
        onSelect={(id) => navigate(`/app?view=${id}`, { state: { from: 'home' } })}
        onBrand={() => navigate('/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />
    </PhotoBackdrop>
  );
}
