import { useNavigate } from 'react-router-dom';
import { PhotoBackdrop } from '../components/common/PhotoBackdrop';
import { TopBar } from '../components/common/TopBar';

/**
 * Home: the sunlit-room photograph edge to edge, with only the top bar over it.
 */
export function HomeScene() {
  const navigate = useNavigate();

  return (
    <PhotoBackdrop>
      <TopBar
        activeId="foryou"
        onSelect={(id) => navigate(id === 'trend' ? '/trend' : '/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />
    </PhotoBackdrop>
  );
}
