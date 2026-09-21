import { useEffect, useId, useRef, useState } from 'react'
import { searchNodes } from '../../api/search'
import styles from './NodeSearch.module.css'

const TYPE_LABEL = {
  EVENT: '사건',
  ENTITY: '인물·기관',
  STATEMENT: '발언',
}

export function NodeSearch({ night = false, onSelect }) {
  const inputId = useId()
  const listId = useId()
  const rootRef = useRef(null)
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

  return (
    <search
      ref={rootRef}
      className={`${styles.search} ${night ? styles.night : ''}`}
      aria-label="뉴스 그래프 검색"
    >
      <label className={styles.label} htmlFor={inputId}>
        뉴스 그래프 검색
      </label>

      <div className={styles.control}>
        <span className={styles.icon} aria-hidden>⌕</span>
        <input
          id={inputId}
          className={styles.input}
          type="search"
          value={query}
          placeholder="사건, 인물, 기관, 발언 검색"
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
                    <span className={styles.type}>{TYPE_LABEL[item.nodeType] ?? item.nodeType}</span>
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
