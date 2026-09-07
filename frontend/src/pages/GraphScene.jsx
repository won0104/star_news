import { useNavigate } from 'react-router-dom';
import { miniShells } from '../data/cards';
import { graphEntityContent, graphHints, graphTagline } from '../data/graph';
import { AtmospherePapers } from '../components/common/AtmospherePapers';
import { Backdrop } from '../components/common/Backdrop';
import { DepthPapers } from '../components/common/DepthPapers';
import { EntityCard } from '../components/graph/EntityCard';
import { ExplorationControls, GraphSearchPill } from '../components/graph/ExplorationControls';
import { GraphEventCard } from '../components/graph/GraphEventCard';
import { GraphSidebar } from '../components/graph/GraphSidebar';
import { GraphStatementCard } from '../components/graph/GraphStatementCard';
import { Hangers } from '../components/graph/Hangers';
import { Hints } from '../components/common/Hints';
import { RelationChips } from '../components/graph/RelationChips';
import { SceneCanvas } from '../components/common/SceneCanvas';
import { YarnFibers, YarnStrands } from '../components/common/YarnLayer';

/**
 * "Graph Exploration / Event centered" view (Figma 680:2). Same room and card
 * geometry as the attic; the centred event gains neighbours, relation chips and
 * coloured hanging threads. Hangers sit last so they read above every card.
 */
export function GraphScene() {
  const navigate = useNavigate();

  return (
    <SceneCanvas>
      <Backdrop />
      <YarnStrands />
      <DepthPapers />
      <YarnFibers />

      <GraphEventCard />
      <ExplorationControls />
      <GraphStatementCard />
      {miniShells.map((shell) => (
        <EntityCard key={shell.id} shell={shell} content={graphEntityContent[shell.id]} />
      ))}

      <GraphSearchPill />
      <GraphSidebar onBack={() => navigate('/')} />
      <AtmospherePapers />
      <Hints hints={graphHints} tagline={graphTagline} variant="graph" />
      <RelationChips />
      <Hangers />
    </SceneCanvas>
  );
}
