import { lazy, Suspense, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { historyCopy, historyGraph, historyOverview, historyStories } from '../../data/history';
import { useSettingsValues } from '../../store/settings';
import styles from './HistoryPane.module.css';

const HistoryPlanet = lazy(() => import('./HistoryPlanet'));

const TONE_CLASS = {
  rose: 'toneRose',
  gold: 'toneGold',
  mint: 'toneMint',
  peach: 'tonePeach',
  violet: 'toneViolet',
  cyan: 'toneCyan',
  blue: 'toneBlue',
};

export function HistoryPane() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { reduceMotion } = useSettingsValues();
  const cluster = historyStories.find((item) => item.topicCode === params.get('topic')) ?? historyStories[0];
  const [selectedNode, setSelectedNode] = useState(
    () => historyGraph.nodes.find((node) => node.id === `topic:${cluster.topicCode}`) ?? null,
  );
  const topicNodeIds = new Set(
    historyGraph.nodes
      .filter((node) => node.topicCode === cluster.topicCode)
      .map((node) => node.id),
  );
  const topicLinkCount = historyGraph.edges.filter((edge) => (
    topicNodeIds.has(edge.sourceId) && topicNodeIds.has(edge.targetId)
  )).length;

  const selectTopic = (nextCluster) => {
    setSelectedNode(
      historyGraph.nodes.find((node) => node.id === `topic:${nextCluster.topicCode}`) ?? null,
    );
    setParams({ view: 'log', topic: nextCluster.topicCode }, { replace: true });
  };

  const selectGraphNode = (node) => {
    setSelectedNode(node);
    if (node?.topicCode && node.topicCode !== cluster.topicCode) {
      setParams({ view: 'log', topic: node.topicCode }, { replace: true });
    }
  };

  const openEvent = (node) => {
    if (!node.localContext) return;
    navigate(
      `/history/${node.localContext.storyId}/events/${node.localContext.eventId}?topic=${node.topicCode}`,
    );
  };

  return (
    <section className={styles.page} aria-labelledby="history-title">
      <div className={`${styles.stage} ${styles[TONE_CLASS[cluster.tone]]}`}>
        <header className={styles.head}>
          <div className={styles.headTop}>
            <div>
              <p className={styles.eyebrow}>{historyOverview.periodLabel} · {historyOverview.generatedAt} 기준</p>
              <h1 id="history-title">{historyCopy.title}</h1>
              <p className={styles.description}>{historyCopy.description}</p>
            </div>
            <div className={styles.summary} aria-label="기록 요약">
              <span><strong>{historyOverview.totalArticleCount}</strong>개 기사</span>
              <span><strong>{historyOverview.topicCount}</strong>개 분야</span>
            </div>
          </div>

          <nav className={styles.categoryBar} aria-label="뉴스 카테고리">
            {historyStories.map((item) => (
              <button
                type="button"
                key={item.topicCode}
                className={`${styles.categoryButton} ${styles[TONE_CLASS[item.tone]]}`}
                aria-current={item.topicCode === cluster.topicCode ? 'true' : undefined}
                onClick={() => selectTopic(item)}
              >
                <span>{item.topicName}</span>
                <small>{item.articleCount}</small>
              </button>
            ))}
          </nav>
        </header>

        <section className={styles.mapShell} aria-labelledby="history-map-title">
          <header className={styles.mapHeader}>
            <div>
              <h2 id="history-map-title">나의 기록 행성</h2>
              <p className={styles.mapSubtitle}>
                <span className={styles.mockBadge}>MOCK</span>
                {historyGraph.mockNotice}
              </p>
            </div>
            <p className={styles.mapMeta}>
              <span>{topicNodeIds.size} NODES</span>
              <span>{topicLinkCount} LINKS</span>
            </p>
          </header>

          <Suspense fallback={<div className={styles.planetLoading}>3D 기록 행성을 불러오는 중…</div>}>
            <HistoryPlanet
              graph={historyGraph}
              activeTopic={cluster.topicCode}
              reduceMotion={reduceMotion}
              selectedNode={selectedNode}
              onSelectNode={selectGraphNode}
              onOpenEvent={openEvent}
            />
          </Suspense>
        </section>
      </div>
    </section>
  );
}
