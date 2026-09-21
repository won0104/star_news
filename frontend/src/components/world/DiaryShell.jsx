import styles from './DiaryShell.module.css'

const DIARY_FRAME_URL = '/assets/history/diary-spread-v2.webp'

/**
 * The single diary object shared by 나의 기록 and 나의 리포트.
 *
 * Keeping the frame and its sizing here means changing views only replaces what is
 * printed inside the book; the book itself cannot jump or be swapped for a lookalike.
 */
export function DiaryShell({
  children,
  frameSrc = DIARY_FRAME_URL,
  stageClassName = '',
  frameClassName = '',
}) {
  return (
    <div className={`${styles.stage} ${stageClassName}`}>
      <img
        className={`${styles.frame} ${frameClassName}`}
        src={frameSrc}
        alt=""
        aria-hidden="true"
      />
      {children}
    </div>
  )
}
