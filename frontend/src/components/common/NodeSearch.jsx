import { useEffect, useId, useRef, useState } from 'react'
import { searchNodes } from '../../api/search'
import { nodeTypeLabels } from '../../data/graphLabels'
import styles from './NodeSearch.module.css'

/* 레일만 짧은 쪽을 쓴다 — 176~208px 에 긴 문구는 잘린다. 나머지 자리는 넉넉하다. */
const PLACEHOLDER = '사건, 인물, 기관, 발언 검색'
const SHORT_PLACEHOLDER = '사건·인물 검색'

/**
 * `placement` 는 이 검색창이 어디에 서는가다. 셋뿐이고, 자리마다 결과 목록이 열리는 방향이
 * 다르다 — 그 방향이 이 값이 존재하는 이유다.
 *
 *   floating  스스로 화면 오른쪽 위에 뜬다. 좁은 상단바에서 검색을 펼쳤을 때.
 *   inline    받은 상자를 채우고 결과는 아래로 연다. 현관 한가운데.
 *   rail      받은 상자를 채우되 결과는 오른쪽 옆으로 연다. 세로 레일 안.
 *
 * rail 만 옆으로 여는 것은 레일이 좁아서다 — 아래로 열면 320px 짜리 목록이 그 아래 목적지
 * 단추들을 덮는다. 현관은 상자가 넓고 아래가 비어 있어 그냥 아래로 열면 된다.
 */
export function NodeSearch({ night = false, placement = 'floating', takeFocus = false, onSelect }) {
  const inputId = useId()
  const listId = useId()
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const [query, setQuery] = useState('')
  const [items, setItems] = useState([])
  const [state, setState] = useState('idle')
  const [focused, setFocused] = useState(false)

  const normalized = query.trim()
  const open = focused && normalized.length > 0

  useEffect(() => {
    if (normalized.length < 2) return undefined

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      searchNodes(normalized, { size: 8, signal: controller.signal })
        .then((payload) => {
          if (controller.signal.aborted) return
          setItems(payload?.items ?? [])
          setState((payload?.items?.length ?? 0) > 0 ? 'ready' : 'empty')
        })
        .catch((error) => {
          if (error?.name === 'AbortError') return
          setItems([])
          setState('failed')
        })
    }, 280)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [normalized])

  useEffect(() => {
    const close = (event) => {
      if (!rootRef.current?.contains(event.target)) setFocused(false)
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  // 아이콘을 눌러 막 열린 검색창이면 바로 쓸 수 있어야 한다 — 한 번 더 눌러 커서를 옮기게 두지 않는다.
  useEffect(() => {
    if (takeFocus) inputRef.current?.focus()
  }, [takeFocus])

  return (
    <search
      ref={rootRef}
      className={`${styles.search} ${night ? styles.night : ''} ${styles[placement] ?? ''}`}
      aria-label="뉴스 그래프 검색"
    >
      <label className={styles.label} htmlFor={inputId}>
        뉴스 그래프 검색
      </label>

      <div className={styles.control}>
        <span className={styles.icon} aria-hidden>⌕</span>
        <input
          ref={inputRef}
          id={inputId}
          className={styles.input}
          type="search"
          value={query}
          placeholder={placement === 'rail' ? SHORT_PLACEHOLDER : PLACEHOLDER}
          autoComplete="off"
          aria-controls={open ? listId : undefined}
          aria-expanded={open}
          onFocus={() => setFocused(true)}
          onChange={(event) => {
            const nextQuery = event.target.value
            const nextLength = nextQuery.trim().length
            setQuery(nextQuery)
            setItems([])
            setState(nextLength === 0 ? 'idle' : nextLength < 2 ? 'short' : 'loading')
            setFocused(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.currentTarget.blur()
              setFocused(false)
            }
          }}
        />
        {query && (
          <button
            type="button"
            className={styles.clear}
            aria-label="검색어 지우기"
            onClick={() => {
              setQuery('')
              setItems([])
              setState('idle')
            }}
          >
            ×
          </button>
        )}
      </div>

      {open && (
        <div className={styles.results}>
          {state === 'short' && <Status>두 글자 이상 입력해 주세요.</Status>}
          {state === 'loading' && <Status>검색하는 중…</Status>}
          {state === 'empty' && <Status>일치하는 노드가 없어요.</Status>}
          {state === 'failed' && <Status>검색 결과를 불러오지 못했어요.</Status>}

          {state === 'ready' && (
            <ul id={listId} className={styles.list} aria-label="검색 결과">
              {items.map((item) => (
                <li key={`${item.nodeType}:${item.nodeKey}`} className={styles.item}>
                  <button
                    type="button"
                    className={styles.resultButton}
                    onClick={() => {
                      setQuery(item.label)
                      setFocused(false)
                      onSelect?.(item)
                    }}
                  >
                    <span className={styles.type}>{nodeTypeLabels[item.nodeType] ?? item.nodeType}</span>
                    <span className={styles.name}>{item.label}</span>
                    <span className={styles.enter} aria-hidden>→</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </search>
  )
}

function Status({ children }) {
  return <p className={styles.status} role="status">{children}</p>
}
