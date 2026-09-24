import { useEffect, useRef, useState } from 'react'
import { TOPICS, TOPIC_ALL, topicName } from '../../data/topics'
import styles from './TopicNote.module.css'

/**
 * 창틀에 붙은 쪽지 — 오늘의 트렌드를 어느 분야로 볼지 고른다.
 *
 * 접혀 있을 때도 지금 고른 분야가 쪽지에 쓰여 있다. 접히는 물건의 약점은 상태가 안 보이는
 * 것인데, 이름을 적어 두면 그 약점이 없어지고 왜 화면이 비었는지도 함께 읽힌다.
 *
 * 창틀에 책갈피 여덟 개를 세우는 대신 이 하나를 붙인 것은 자리 때문이다. 별 열 개와 긴 제목이
 * 유리를 거의 채워서, 상시로 서 있는 것을 더하면 화면이 먼저 무너진다.
 *
 * 고른 분야는 여기 담기지 않는다 — URL 이 갖는다. 이 쪽지는 고른 값을 받아 보여주고 새 값을
 * 알릴 뿐이다.
 *
 * `pillar` 는 왼쪽 나무 기둥의 안쪽 모서리, 곧 유리가 시작되는 선이다. 창틀이 비율마다 다른
 * 장이라 그 선도 함께 옮겨 서므로 CSS 에 적어 둘 수 없다 — 장을 고르는 <TrendStage> 가
 * 재어 둔 값을 건네준다. 그 선에 쪽지를 어떻게 거는지는 CSS 가 정한다.
 */
export function TopicNote({ topic, onSelect, pillar }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  // 바깥을 누르거나 Esc 를 누르면 접는다 — 쪽지는 화면을 가리는 물건이라 빠져나갈 길이 있어야 한다.
  useEffect(() => {
    if (!open) return undefined
    const onPointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const choices = [TOPIC_ALL, ...TOPICS]

  return (
    <div ref={rootRef} className={styles.root} style={{ '--pillar-inner': `${pillar}%` }}>
      <button
        type="button"
        className={styles.note}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((current) => !current)}
      >
        <span className={styles.noteLabel}>{topic ? topicName(topic) : TOPIC_ALL.topicName}</span>
        <span className={styles.noteHint} aria-hidden>
          분야
        </span>
      </button>

      {open && (
        <ul className={styles.sheet} role="listbox" aria-label="분야 고르기">
          {choices.map((item) => {
            const selected = item.topicCode === (topic ?? null)

            return (
              <li key={item.topicCode ?? 'ALL'}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`${styles.choice} ${selected ? styles.choiceSelected : ''}`}
                  onClick={() => {
                    onSelect(item.topicCode)
                    setOpen(false)
                  }}
                >
                  {item.topicName}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
