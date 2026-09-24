import { paneNotes } from '../../data/world'
import { TrendStage } from '../trend/TrendStage'
import { DiaryHistoryPane } from './DiaryHistoryPane'
import { DiaryReportPane } from './DiaryReportPane'
import { RecommendPane } from './RecommendPane'
import styles from './ViewPane.module.css'

/**
 * Whichever screen `?view=` names is open.
 *
 * This replaces the two tabbed panes the left menu board used to open (홈 and
 * 나의 뉴스 세계, each with its own two-tab strip). The leaves are in the bar now, so
 * there is one level of navigation and no tab strip: a plain switch on the selected id.
 *
 * 오늘의 트렌드 is <TrendStage> — the clip, the still it settles on, and the constellation
 * drawn over it. 나를 위한 추천, 나의 기록 and 나의 리포트 are each their own pane; 나의 리포트
 * is reached from the bookmark attached to 나의 기록 instead of the bar.
 *
 * 나를 위한 추천's board waits for `settled` — the arrival clip reaching its end — and then
 * comes in, so it does not appear over a room that is still moving.
 */
export function ViewPane({ view, visit = 0, settled = true, playTrendTransition = false, selectedNode }) {
  return (
    <div className={`${styles.page} ${view === 'trend' ? styles.trendPage : ''}`}>
      {/*
        `key` 가 방문 횟수다 — 목적지를 다시 누르면 별자리가 펼쳐 보던 사건을 접고 처음 상태로
        다시 선다. 그 상태는 <TrendSky> 안에만 있어 바깥에서 되돌릴 길이 없다.
      */}
      {view === 'trend' && (
        <TrendStage key={visit} playTransition={playTrendTransition} selectedNode={selectedNode} />
      )}
      {view === 'foryou' && <RecommendPane settled={settled} />}
      {view === 'log' && <DiaryHistoryPane />}
      {view === 'report' && <DiaryReportPane />}
      {view !== 'log' && paneNotes[view] && <p className={styles.stub}>{paneNotes[view]}</p>}
    </div>
  )
}
