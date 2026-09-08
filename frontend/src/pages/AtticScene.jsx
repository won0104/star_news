import { useNavigate } from 'react-router-dom';
import { photo } from '../data/assets';
import { RAIL_LEFT_VEIL, RAIL_WIDTH, TOP_BAR_HEIGHT } from '../data/scene';
import { useIsCompact } from '../hooks/useIsCompact';
import { SceneCanvas } from '../components/common/SceneCanvas';
import { Sidebar } from '../components/attic/Sidebar';
import { TopBar } from '../components/common/TopBar';
import { AtticCompact } from './AtticCompact';

/**
 * "오늘의 트렌드" — the furnished study, the site's top bar, and the left rail. Nothing
 * else.
 *
 * The pinned composition that used to fill this canvas (yarn strands, depth papers,
 * fibre highlights, the event and statement cards, the seven mini cards, the search
 * pill, the atmosphere papers and the hint captions) is stripped back to the rail on
 * purpose, so the room reads on its own while the trend content is redesigned. Every
 * one of those components is still in the tree untouched — putting a layer back is one
 * line, in the Figma stacking order: yarn -> depth papers -> fibres -> cards -> chrome
 * -> atmosphere -> hints.
 *
 * The top bar sits outside <SceneCanvas>: it is position:fixed, and the canvas applies
 * a transform, which would trap it in that transformed box and scale it with the room.
 *
 * Below <AtticCompact>'s breakpoint the reflowed column takes over, and that layout is
 * unchanged — it carries its own header and has no left rail to keep.
 */
export function AtticScene() {
  const navigate = useNavigate();
  const compact = useIsCompact();

  if (compact) return <AtticCompact />;

  return (
    <>
      <TopBar
        activeId="trend"
        onSelect={(id) => navigate(id === 'trend' ? '/trend' : '/')}
        onAuth={(kind) => navigate(`/${kind}`)}
      />

      <SceneCanvas
        backdrop={photo.backdropTrend}
        topChrome={TOP_BAR_HEIGHT}
        railWidth={RAIL_WIDTH}
        leftVeil={RAIL_LEFT_VEIL}
      >
        <Sidebar />
      </SceneCanvas>
    </>
  );
}
