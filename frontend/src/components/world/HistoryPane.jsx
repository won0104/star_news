import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { historyGraph, historyOverview, historyStories } from '../../data/history';
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

export function HistoryPane({
  viewId = 'log',
  fullscreenLayout = false,
  onExitFullscreen,
}) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { reduceMotion } = useSettingsValues();
  const mapShellRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const cluster = historyStories.find((item) => item.topicCode === params.get('topic')) ?? historyStories[0];
  const [selectedNode, setSelectedNode] = useState(
    () => historyGraph.nodes.find((node) => node.id === `topic:${cluster.topicCode}`) ?? null,
  );
  const selectedEvent = selectedNode?.localContext
    ? historyStories
      .find((item) => item.topicCode === selectedNode.topicCode)
      ?.stories.find((story) => story.id === selectedNode.localContext.storyId)
      ?.events.find((event) => event.id === selectedNode.localContext.eventId) ?? null
    : null;
  const selectTopic = (nextCluster) => {
    setSelectedNode(
      historyGraph.nodes.find((node) => node.id === `topic:${nextCluster.topicCode}`) ?? null,
    );
    setParams({ view: viewId, topic: nextCluster.topicCode }, { replace: true });
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

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === mapShellRef.current);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    if (document.fullscreenElement === mapShellRef.current) {
      await document.exitFullscreen();
      return;
    }
    await mapShellRef.current?.requestFullscreen();
  };

  return (
    <section className={`${styles.page} ${fullscreenLayout ? styles.fullscreenPage : ''}`} aria-label="나의 기록">
      <div className={`${styles.stage} ${styles[TONE_CLASS[cluster.tone]]}`}>
        <section ref={mapShellRef} className={styles.mapShell} aria-labelledby="history-map-title">
          <header className={styles.mapHeader}>
            <div>
              <h2 id="history-map-title">나의 기록 행성</h2>
              <p className={styles.mapSubtitle}>
                <span className={styles.mockBadge}>MOCK</span>
                {historyGraph.mockNotice}
              </p>
            </div>
            <div className={styles.mapHeaderActions}>
              <p className={styles.mapMeta} aria-label="기록 요약">
                <span><strong>{historyOverview.totalArticleCount}</strong>개 기사</span>
                <span><strong>{historyOverview.topicCount}</strong>개 분야</span>
              </p>
              <button
                type="button"
                className={styles.fullscreenButton}
                aria-pressed={fullscreenLayout || isFullscreen}
                onClick={fullscreenLayout ? onExitFullscreen : toggleFullscreen}
              >
                <span aria-hidden="true">{fullscreenLayout || isFullscreen ? '↙' : '⛶'}</span>
                {fullscreenLayout || isFullscreen ? '전체 화면 닫기' : '전체 보기'}
              </button>
            </div>
          </header>

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

          <Suspense fallback={<div className={styles.planetLoading}>3D 기록 행성을 불러오는 중…</div>}>
            <HistoryPlanet
              graph={historyGraph}
              activeTopic={cluster.topicCode}
              reduceMotion={reduceMotion}
              selectedNode={selectedNode}
              selectedEvent={selectedEvent}
              onSelectNode={selectGraphNode}
              onOpenEvent={openEvent}
              eventDisplay={fullscreenLayout || isFullscreen ? 'card' : 'star'}
            />
          </Suspense>
        </section>
      </div>
    </section>
  );
}
