import { useCallback, useEffect, useRef, useState } from 'react'
import { generateArticleSummary } from '../api/articles'

/** 남이 만드는 중일 때 다시 물어보는 간격과 횟수. */
const RETRY_MS = 2500
const MAX_TRIES = 3

/**
 * 기사 요약 한 건.
 *
 * `POST /articles/{id}/summary` 는 읽기 전용 경로가 없어 조회와 생성을 겸한다. 저장된 요약이
 * 있으면 그대로 오고, 없으면 그때 GMS 로 만든다. 그래서 이 훅은 **부르기 전까지 아무것도 하지
 * 않는다** — 화면에 뜨자마자 요청하면 아무도 읽지 않을 요약까지 만들게 된다. 펼치는 순간
 * `load()` 를 부르는 쪽이 사용자 의도와 비용을 일치시킨다.
 *
 * `seed` 는 이미 손에 있는 요약(북마크 행이 들고 온 것 등)이다. 있으면 요청하지 않는다.
 *
 * 상태는 다섯이다. 요약이 없는 이유가 한 가지가 아니라서다 —
 * 본문이 없어 만들 수 없는 것(422)과 만들다 실패한 것(502)과 남이 만드는 중인 것(PROCESSING)은
 * 읽는 사람이 할 일이 다르다.
 *
 *   idle        아직 요청하지 않음
 *   loading     요청 중
 *   ready       summary 에 글이 있음
 *   pending     다른 요청이 생성 중 (재시도 중이거나 횟수를 다 씀)
 *   none        생성은 됐는데 내용이 비어 있음
 *   unavailable 원문 본문이 없어 만들 수 없음 (422)
 *   failed      그 밖의 실패 (502 / 500)
 */
export function useArticleSummary(articleId, { seed = null } = {}) {
  const [summary, setSummary] = useState(seed)
  const [state, setState] = useState(seed ? 'ready' : 'idle')
  // 진행 중인 요청과 예약된 재시도. 언마운트나 기사 교체 때 둘 다 끊는다.
  const run = useRef(null)

  const stop = useCallback(() => {
    if (!run.current) return
    run.current.dropped = true
    run.current.controller.abort()
    if (run.current.timer) clearTimeout(run.current.timer)
    run.current = null
  }, [])

  // 기사를 바꾸는 쪽은 `key={articleId}` 로 이 컴포넌트를 다시 마운트한다(TrendPanel 의
  // ArticleRow, SavedPane 의 ArticleDetail 둘 다). 그래서 여기서 articleId 변경을 따로
  // 되돌릴 필요가 없다 — 느린 응답이 다른 기사 자리에 앉는 일은 그 키가 막는다.
  // 남는 일은 사라질 때 진행 중인 요청과 예약된 재시도를 끊는 것뿐이다.
  useEffect(() => stop, [stop])

  const load = useCallback(() => {
    if (run.current || summary) return

    const session = { controller: new AbortController(), timer: null, dropped: false, tries: 0 }
    run.current = session
    setState('loading')

    const ask = () => {
      session.tries += 1
      generateArticleSummary(articleId, { signal: session.controller.signal })
        .then((result) => {
          if (session.dropped) return
          if (result?.summaryStatus === 'PROCESSING') {
            setState('pending')
            // 서버가 중복 생성을 막으므로 다시 물어도 GMS 를 두 번 부르지 않는다.
            if (session.tries < MAX_TRIES) {
              session.timer = setTimeout(ask, RETRY_MS)
            } else {
              run.current = null
            }
            return
          }
          run.current = null
          setSummary(result?.summary ?? null)
          setState(result?.summary ? 'ready' : 'none')
        })
        .catch((error) => {
          if (session.dropped || error?.name === 'AbortError') return
          run.current = null
          setState(error?.status === 422 ? 'unavailable' : 'failed')
        })
    }
    ask()
  }, [articleId, summary])

  /**
   * 실패하거나 기다리다 만 뒤 다시 시도.
   *
   * 서버는 FAILED 상태도 다시 생성 대상으로 잡으므로(CLAIMABLE_STATUSES) 두 번째 시도가
   * 실제로 새 생성을 일으킨다 — 같은 실패를 되풀이해 보여주는 버튼이 아니다.
   */
  const retry = useCallback(() => {
    stop()
    load()
  }, [stop, load])

  return { summary, state, load, retry }
}
