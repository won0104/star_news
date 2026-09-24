import styles from './DemoEntry.module.css'

/*
 * 이름은 보이는 두 글자보다 길다. "시연" 만으로는 어디로 가는 문인지 알 수 없고, 새 창으로
 * 열린다는 것도 눌러 보기 전에는 모른다. 보이는 글자를 앞에 두어 읽은 것과 들리는 것이
 * 어긋나지 않게 한다.
 */
const LABEL = '시연 — 기사에서 지식그래프까지 (새 창)'

/**
 * 시연 페이지(기사 → 지식그래프)로 가는 작은 입구.
 *
 * public/demo-graph.html 은 앱의 화면이 아니라 그 옆에 선 독립 정적 페이지다 — 라우터가
 * 모르는 주소이므로 <Link> 가 아니라 <a> 여야 하고, 새 창으로 연다. 같은 창에서 열면 방을
 * 통째로 잃고 돌아올 길이 뒤로가기뿐이다.
 */
export function DemoEntry() {
  return (
    <a
      className={styles.root}
      href="/demo-graph.html"
      target="_blank"
      rel="noopener noreferrer"
      aria-label={LABEL}
      title={LABEL}
    >
      시연
    </a>
  )
}
