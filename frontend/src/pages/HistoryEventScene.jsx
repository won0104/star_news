import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArticlePanel } from '../components/event/ArticlePanel';
import { PhotoBackdrop } from '../components/common/PhotoBackdrop';
import { TopBar } from '../components/common/TopBar';
import { historyCopy, historyStories } from '../data/history';
import styles from './HistoryEventScene.module.css';

const PANEL_ID = 'history-article-detail';
const TONE_CLASS = {
  rose: 'toneRose',
  gold: 'toneGold',
  mint: 'toneMint',
  peach: 'tonePeach',
  violet: 'toneViolet',
  cyan: 'toneCyan',
  blue: 'toneBlue',
};

function findContext(storyId, eventId) {
  for (const cluster of historyStories) {
    const story = cluster.stories.find((item) => item.id === storyId);
    if (!story) continue;
    const event = story.events.find((item) => item.id === eventId);
    if (event) return { cluster, story, event };
  }
  return null;
}

export function HistoryEventScene() {
  const navigate = useNavigate();
  const { storyId, eventId } = useParams();
  const [searchParams] = useSearchParams();
  const context = findContext(storyId, eventId);
  const [articleSelection, setArticleSelection] = useState(null);
  const [saved, setSaved] = useState({});

  const event = context?.event;
  const openArticleId = articleSelection?.eventId === eventId
    ? articleSelection.articleId
    : null;

  const openAppView = (view) => navigate(`/app?view=${view}`);
  const bar = (
    <TopBar
      activeId="log"
      onSelect={openAppView}
      onBrand={() => navigate('/')}
      onAuth={(kind) => navigate(`/${kind}`)}
    />
  );

  if (!context) {
    return (
      <PhotoBackdrop motion={false}>
        {bar}
        <main className={styles.missingPage}>
          <div className={styles.missingCard}>
            <h1>Event 기록을 찾을 수 없어요.</h1>
            <button type="button" onClick={() => navigate('/app?view=log')}>나의 기록으로 돌아가기</button>
          </div>
        </main>
      </PhotoBackdrop>
    );
  }

  const { cluster, story } = context;
  const backTopic = searchParams.get('topic') ?? cluster.topicCode;
  const backUrl = `/app?view=log&topic=${backTopic}`;
  const rawArticle = event.articles.find((article) => article.id === openArticleId);
  const panelArticle = rawArticle ? {
    id: rawArticle.id,
    source: rawArticle.source,
    at: rawArticle.readAt,
    headline: rawArticle.title,
    lead: rawArticle.summary,
    saved: !!saved[rawArticle.id],
  } : null;

  const selectSibling = (nextEventId) => {
    navigate(`/history/${story.id}/events/${nextEventId}?topic=${cluster.topicCode}`);
  };

  return (
    <PhotoBackdrop motion={false}>
      {bar}

      <main className={styles.page}>
        <section className={`${styles.stage} ${styles[TONE_CLASS[cluster.tone]]}`}>
          <header className={styles.topline}>
            <button type="button" className={styles.back} onClick={() => navigate(backUrl)}>
              ← {cluster.topicName} 기록
            </button>
            <p>{cluster.topicName} · {historyCopy.eventLabel}</p>
          </header>

          <div className={styles.detailGrid}>
            <article className={styles.eventPane}>
              <span className={styles.eventEyebrow}>SELECTED EVENT</span>
              <span className={styles.eventMark} aria-hidden>✦</span>
              <h1>{event.title}</h1>
              <dl className={styles.eventMeta}>
                <div><dt>카테고리</dt><dd>{cluster.topicName}</dd></div>
                <div><dt>마지막 열람</dt><dd>{event.lastReadAt}</dd></div>
                <div><dt>관련 기사</dt><dd>{event.articleCount}건</dd></div>
              </dl>
              <div className={styles.eventSummary}>
                <span>EVENT SUMMARY</span>
                <p>{event.articles[0]?.summary}</p>
              </div>
            </article>

            <section className={styles.articlesPane} aria-labelledby="history-articles-title">
              <div className={styles.articlesHead}>
                <div>
                  <span>RELATED ARTICLES</span>
                  <h2 id="history-articles-title">이 Event와 관련된 기사</h2>
                </div>
                <strong>{event.articles.length}</strong>
              </div>

              <ul className={styles.articleList}>
                {event.articles.map((article, index) => (
                  <li key={article.id}>
                    <button
                      type="button"
                      className={openArticleId === article.id ? styles.articleActive : ''}
                      onClick={() => setArticleSelection(
                        openArticleId === article.id
                          ? null
                          : { eventId: event.id, articleId: article.id },
                      )}
                      aria-expanded={openArticleId === article.id}
                      aria-controls={PANEL_ID}
                    >
                      <span className={styles.articleIndex}>{String(index + 1).padStart(2, '0')}</span>
                      <span className={styles.articleCopy}>
                        <small>{article.source} · {article.readAt}</small>
                        <strong>{article.title}</strong>
                        <em>기사 자세히 보기 →</em>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className={styles.eventRail} aria-labelledby="story-events-title">
            <div className={styles.railHead}>
              <div>
                <span>RELATED EVENTS</span>
                <h2 id="story-events-title">{cluster.topicName}에서 함께 읽은 Event</h2>
              </div>
              <p>{story.events.length}개 Event</p>
            </div>

            <div className={styles.railCards}>
              {story.events.map((item, index) => (
                <button
                  type="button"
                  key={item.id}
                  className={item.id === event.id ? styles.railCardActive : ''}
                  aria-current={item.id === event.id ? 'true' : undefined}
                  onClick={() => selectSibling(item.id)}
                >
                  <span>EVENT {String(index + 1).padStart(2, '0')}</span>
                  <strong>{item.title}</strong>
                  <small>{item.articleCount}개 기사</small>
                </button>
              ))}
            </div>
          </section>
        </section>
      </main>

      <ArticlePanel
        id={PANEL_ID}
        article={panelArticle}
        open={!!panelArticle}
        onClose={() => setArticleSelection(null)}
        onToggleSave={(articleId) => setSaved((current) => ({
          ...current,
          [articleId]: !current[articleId],
        }))}
      />
    </PhotoBackdrop>
  );
}
