import { useRef, useState } from 'react'
import { setArticleBookmark, setNodeBookmark } from '../api/bookmarks'
import { useSession } from '../store/session'

/**
 * 북마크(기사) · 즐겨찾기(Node) 토글 하나.
 *
 *   const { on, pending, hint, toggle } = useBookmark({ kind: 'node', nodeType, key, initial, copy })
 *
 * 낙관적이다: 누르면 먼저 채우고 서버에 **목표 상태**를 보낸다(API 가 토글이 아니라 최종
 * 상태를 받는다). 응답의 확정값으로 다시 맞추고, 실패하면 이전 상태로 되돌리며 `hint` 에
 * 한 줄을 남긴다. 연달아 누르면 마지막 요청만 결과를 결정한다.
 *
 * 로그인이 없으면 요청을 보내지 않고 `hint` 만 세운다 — 401 을 받고 되돌리는 것과 결과는
 * 같지만, 서버까지 갔다 오는 왕복이 없고 화면이 잠깐도 거짓을 말하지 않는다.
 *
 * 사용자가 누르기 전까지는 `initial` 을 그대로 따른다(`override` 가 null). 상세 응답이 늦게
 * 도착해 `initial` 이 바뀌어도 반영되지만, 이미 눌러 바꾼 상태를 덮어쓰지는 않는다 — 그래서
 * effect 로 동기화하지 않고 렌더에서 고른다.
 */
export function useBookmark({ kind, nodeType, key, initial = false, copy }) {
  const account = useSession()
  const [override, setOverride] = useState(null)
  const [pending, setPending] = useState(false)
  const [hint, setHint] = useState(null)
  const seq = useRef(0)

  const on = override ?? !!initial

  const toggle = () => {
    if (!account) {
      setHint(copy.signIn)
      return
    }
    const next = !on
    const before = on
    setOverride(next)
    setHint(null)
    setPending(true)
    const mine = ++seq.current

    const call =
      kind === 'article' ? setArticleBookmark(key, next) : setNodeBookmark(nodeType, key, next)

    call
      .then((confirmed) => {
        if (mine !== seq.current) return
        setOverride(!!confirmed)
      })
      .catch((error) => {
        if (mine !== seq.current) return
        setOverride(before)
        setHint(error?.status === 401 ? copy.signIn : copy.failed)
      })
      .finally(() => {
        if (mine === seq.current) setPending(false)
      })
  }

  return { on, pending, hint, toggle, signedIn: !!account }
}
