import { useNavigate } from 'react-router-dom';
import { atticMiniContent, miniShells } from '../data/cards';
import { hints, tagline } from '../data/scene';
import { AtmospherePapers } from '../components/common/AtmospherePapers';
import { Backdrop } from '../components/common/Backdrop';
import { DepthPapers } from '../components/common/DepthPapers';
import { EventCard } from '../components/attic/EventCard';
import { Hints } from '../components/common/Hints';
import { MiniCard } from '../components/attic/MiniCard';
import { SceneCanvas } from '../components/common/SceneCanvas';
import { SearchPill } from '../components/attic/SearchPill';
import { Sidebar } from '../components/attic/Sidebar';
import { StatementCard } from '../components/attic/StatementCard';
import { YarnFibers, YarnStrands } from '../components/common/YarnLayer';

/**
 * "나의 뉴스 다락방" main view. Layer order follows the Figma stack exactly:
 * room -> yarn -> depth papers -> fibre highlights -> cards -> chrome -> atmosphere -> hints.
 */
export function AtticScene() {
  const navigate = useNavigate();

  return (
    <SceneCanvas>
      <Backdrop />
      <YarnStrands />
      <DepthPapers />
      <YarnFibers />

      <EventCard />
      <StatementCard />
      {miniShells.map((shell) => (
        <MiniCard
          key={shell.id}
          shell={shell}
          content={atticMiniContent[shell.id]}
          onSelect={shell.id === 'policy' ? () => navigate('/explore') : undefined}
        />
      ))}

      <SearchPill />
      <Sidebar />
      <AtmospherePapers />
      <Hints hints={hints} tagline={tagline} variant="attic" />
    </SceneCanvas>
  );
}
