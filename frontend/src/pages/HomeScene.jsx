import { useNavigate } from 'react-router-dom';
import { PhotoBackdrop } from '../components/common/PhotoBackdrop';
import { TopBar } from '../components/common/TopBar';

/**
 * Home: the sunlit-room photograph edge to edge, with only the top bar over it. This is
 * the one screen that gets the room in motion — nothing here competes with it, so the
 * loop reads as the page rather than as decoration behind content.
 */
export function HomeScene() {
  const navigate = useNavigate();

  return (
    <PhotoBackdrop motion>
      <TopBar
        activeId="foryou"
        onSelect={(id) => navigate(id === 'trend' ? '/trend' : '/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />
    </PhotoBackdrop>
  );
}
