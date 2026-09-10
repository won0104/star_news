import { paneNotes } from '../../data/world';
import { TrendStage } from '../trend/TrendStage';
import { RecommendPane } from './RecommendPane';
import { ReportPane } from './ReportPane';
import styles from './ViewPane.module.css';

/**
 * Whichever of the bar's four destinations is open.
 *
 * This replaces the two tabbed panes the left menu board used to open (홈 and
 * 나의 뉴스 세계, each with its own two-tab strip). The four leaves are in the bar now, so
 * there is one level of navigation and no tab strip: a plain switch on the selected id.
 *
 * 주요 트렌드 is <TrendStage> — the clip, the still it settles on, and the constellation
 * drawn over it. 나의 리포트 is its own pane. 나의 기록 has no screen yet, so it says so
 * rather than showing something invented, and its copy is keyed by the same id in
 * data/world.js — a destination with no branch here still reads as deliberate.
 *
 * 나를 위한 추천's board waits for `settled` — the arrival clip reaching its end — and then
 * comes in, so it does not appear over a room that is still moving.
 */
export function ViewPane({ view, settled = true }) {
  return (
    <div className={styles.page}>
      {view === 'trend' && <TrendStage />}
      {view === 'foryou' && <RecommendPane settled={settled} />}
      {view === 'report' && <ReportPane />}
      {paneNotes[view] && <p className={styles.stub}>{paneNotes[view]}</p>}
    </div>
  );
}
