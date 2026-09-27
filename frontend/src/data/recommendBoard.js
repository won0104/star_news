/**
 * 나를 위한 추천 — 빈 코르크 보드 위에 에셋 카드를 거는 자리표.
 *
 * 배경에는 빈 보드만 있다. 제목 띠, 추천 종이, 압정은 각각 투명 에셋이며 아래 좌표에
 * 독립적으로 놓인다. 이 구조 덕분에 종이 전체가 버튼이 되고, 추천 수가 줄면 빈 종이가
 * 배경에 문신처럼 남지 않는다.
 *
 * 열 자리 = 추천 열 개. 서버가 사용자당 최대 10개를 주므로(app.recommendation.limit-per-user)
 * 자리가 남거나 모자라는 일은 정상 범위에서 생기지 않는다. 적게 오면 사용하지 않는 슬롯에는
 * 아무 에셋도 그리지 않는다.
 */

/**
 * 제목 띠, 추천 종이, 압정. 압정은 tone 마다 실제로 그려진 색이 따로 있다 — 예전에는 붉은
 * 한 장에 hue-rotate 를 걸어 여섯 색을 흉내 냈는데, 필터는 하이라이트와 그림자까지 같이
 * 돌려 색마다 광택이 어긋났다.
 */
export const BOARD_ASSETS = {
  title: '/assets/board/recommend-v2-banner.webp',
  paper: '/assets/board/recommend-v2-paper.webp',
}

/** tone 이름은 장면이 쓰던 것을 그대로 두고, 그 색으로 그려진 압정을 건다. */
export const PIN_BY_TONE = {
  rose: '/assets/board/recommend-pin-v2-red.webp',
  sky: '/assets/board/recommend-pin-v2-blue.webp',
  mint: '/assets/board/recommend-pin-v2-green.webp',
  sand: '/assets/board/recommend-pin-v2-yellow.webp',
  lilac: '/assets/board/recommend-pin-v2-purple.webp',
  coral: '/assets/board/recommend-pin-v2-orange.webp',
}

/**
 * 방이 그려진 배경들. 사진은 뷰포트를 그대로 채우므로(늘어난다) 화면 비율에서 먼 그림을
 * 고르면 나무틀과 화분이 눈에 띄게 뭉개진다 — 그래서 비율별로 한 장씩 두고 가장 가까운 것을
 * 고른다. 16:9 한 장만 쓰던 때 1280×1024 에서 가로가 30% 줄었다.
 *
 * `cork` 는 코르크 면의 사각형이며 그림에 대한 비율이다. 사진이 뷰포트를 채우므로 이 값은
 * 화면에 대한 비율이기도 하다. 알파가 아니라 색(r-b ≥ 90)으로 실측한 값 — 코르크만 주황이고
 * 벽과 나무틀은 그렇지 않다.
 *
 * 보드를 추가하려면 여기 한 항목만 넣으면 된다. 종이 자리는 아래 LAYOUT 이 코르크에 대한
 * 비율로 들고 있으므로 좌표를 다시 잴 필요가 없다.
 */
export const BOARDS = [
  {
    ratio: 1672 / 941,
    src: '/assets/board/recommend-board-empty-16x9-v2.webp',
    standIn: 'data:image/webp;base64,UklGRg4DAABXRUJQVlA4WAoAAAAgAAAANwAAHwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggIAEAAFAHAJ0BKjgAIAA+lTyZSKWjIiEwG/gAsBKJQBeadWrAbc83QMSnEKxYspxPUltGiDau/7j2k3BTSPE6W/SdttJz/gAA/vlxX+kYLXUHFBqUSr5Iy1n3RWRVbBq0kIgr0mt+Bns7C221ukKyJ6hag9Tca4aZ5mbASGaY5S4DaeFUe0jmMZUDC3Jcs+9f/XmF8SbSrXuBrzEPkP5lAafDuiiN9LJH4aTnP5Aha3ay3NvXf57p7xKud+THUIJ7fjSGcVG8zMO2a3EfW62pzPfCq7qa80+t07JM8tnLAHDwG0lgRdfE4gs0JCAxIqTeqEK5AZMbGpzSr2VnIzw2O2feUdVFaR/g62S0VWEZ6vYybqktmjAFVFdqMpi0VFxeoJsAAA==',
    cork: { x: 0.19498, y: 0.09564, w: 0.72548, h: 0.77258 },
  },
  {
    ratio: 1448 / 1086,
    src: '/assets/board/recommend-board-empty-4x3-v2.webp',
    standIn: 'data:image/webp;base64,UklGRpoDAABXRUJQVlA4WAoAAAAgAAAANwAAKQAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggrAEAAJAKAJ0BKjgAKgA+lTybSKWjIqIqtA34sBKJQBe5C/E96LW1m2+GOrom9/4PkdzJeYO1fn7SmAAcnfBUQhkhZrZnq4pSZ9yW010F7ZfCGKe/BxrhWMyOjAdO/oghAAD+yqrIKUhVEWODj8i0EWLZEeq5Jxr9i6DjXrdX6RRnXcMU75BjcTmo3Jd9tw8YRJT0TFZiD4w0yKNWPNriJA0tR+JFwJx6cxdqNSqgL6T+wCDAGBC82K1j/oH78l5r8MBEIvaQiLasajSoGGnnK3zIQhsC43/+pzGPPHyLGO2H/Qz47NHSBwtYO2CSuiZebi0SMj4g0vX0v6HAN198XXljEUAMGF3H9CRj90g77npeEqVxds+57rDh2aRPgfKu56bwI1APM9dgcjooXqemFH6VWhtU2QPvfGuf5GsbIIOPXYZY8tm76rH4YjFuWiRgSBQU6fddtgwufh2gZ3LizaWoHIl/zSUUx0egNcpOe0TKrchiRyRRLlgxn07hC+UPpIAZ+KbcEvej6PTT0+e4Mq+MgZzB+46LfF4zN6QhfleORi0lw4NaiVXbIGPV0AAA',
    cork: { x: 0.14917, y: 0.13076, w: 0.74862, h: 0.63996 },
  },
  {
    ratio: 1086 / 1448,
    src: '/assets/board/recommend-board-empty-3x4-v2.webp',
    standIn: 'data:image/webp;base64,UklGRs4DAABXRUJQVlA4WAoAAAAgAAAAKQAANwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDgg4AEAADAKAJ0BKioAOAA+lTqZSKWjIqEyskzIsBKJTQ4LT761uNN2pKxOGMu7akSXfmE99xgkc9FSH0py51KUEpLrzLs8rYJqsFURbML7P8DxLIT2Rd6W4oY1JpdogAD+t/fYI513LF1qAsTCCN/wsRAVIFHSdPdSekcDIm18PfOEMTQ448nQJIAHfTuYKyH7uHmmdMv1ogsL4mWAgVfBw//m+4c1T44HN28W6+pt4xvBRcQjB5p+NvK9RyTPPKXbCo0BtZ/dbIIwmG2yIpqta4JXK4zwcBmz9/9eyai+1adtPnK+H7Tc4pg1GQG2Q1XqI9FuVi87vq1n5ZFg+pmTJzLoln73rnqjfN0ZmC6oonNFO/T4LxJvzAyye35vrAnJRBYYV1vUjVX+IucxtCkEZa28xcFlnkwUWxfWjjdCwfOBWEtQBLAFThp6npTRxg6x3SfuDxTwa1QsjzZGCDFXD6eAE7tUTyKt+1DzuGHc+G3LVSFhhpQnMIVeCffZ+y2r/mcI2Y8j6cPo3qjUNtBXh3wCgPuA4WLMNqiqr2XLA4+hmaTxwWhtMh58kV9WrwcO/a8fy6aJOy/egNCyaQgRztLiW3PTQoXTqFTcLmXjtmYZqMT35N2hSALpcEBaEwfQagAAAA==',
    cork: { x: 0.17587, y: 0.11326, w: 0.66022, h: 0.71202 },
  },
  {
    ratio: 941 / 1672,
    src: '/assets/board/recommend-board-empty-9x16-v2.webp',
    standIn: 'data:image/webp;base64,UklGRjwDAABXRUJQVlA4WAoAAAAgAAAAHwAANwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggTgEAAFAIAJ0BKiAAOAA+lUKbS6WjoiGoGAlYsBKJQBWGb+CSo3tszdAITS3eDqgIAeXgA2yO5Ko79dYm7ux/pJLaymYPOixTzE7bExhuQADifiQyu5y78BbIcvCk7JtnMitViiyLsOfRWjVPH5pF2ecfFTKQ/2+3jKv97l3oQaQJltKkEKSFwPoI6fRrvNDcfldTNwTDJDX0Ydu32djnPuODKhMSds0yhpcrfDJCC9LSyGBuf8xGOahNmB5zHBHxA5NKAUjvvnMclOx7eNwmBMv8vrMTD3HjgW7YzjUc+S7c2wpoXGe8zvPsT7CKEY6kIL8Ml2AfEP3q0h1KheaVTp0n+iFM0PJ+PDvbVJjoe+JhUe5ulC6ufwVqK0yLjNjfmLuLQIqhb005I6vbooMs3lCMqPLvOy3b/3WSvX23DZYgAoWYipZkVYQaDTr+A8GAAAA=',
    cork: { x: 0.16366, y: 0.11065, w: 0.68225, h: 0.72428 },
  },
]

/**
 * `tone` 은 순위 글자 색과 압정을 함께 정한다. `doodle` 은 슬롯의 안정적인 key다.
 *
 * 자리 좌표는 없다. 종이는 코르크 안에서 그리드로 흐르므로 보드가 좁아지면 열 수가 줄고,
 * 열 장이 한 화면에 안 들어가면 코르크 안에서 스크롤된다. 자리를 좌표로 박아두던 때에는
 * 보드보다 목록이 길어지면 종이가 나무틀을 넘어 책상 위로 흘러내렸다.
 */
const TOP_ROW = [
  { tone: 'rose', doodle: '반짝이' },
  { tone: 'sky', doodle: '음표' },
  { tone: 'mint', doodle: '잎사귀' },
  { tone: 'sand', doodle: '바구니' },
  { tone: 'lilac', doodle: '달과 별' },
]
const BOTTOM_ROW = [
  { tone: 'mint', doodle: '펼친 책' },
  { tone: 'coral', doodle: '꽃병' },
  { tone: 'lilac', doodle: '라벤더' },
  { tone: 'rose', doodle: '발자국' },
  { tone: 'sky', doodle: '포크와 나이프' },
]

export const SLOTS = [...TOP_ROW, ...BOTTOM_ROW]

/** 코르크 면의 자리 — 화면에 대한 %. 사진이 뷰포트를 채우므로 보드의 `cork` 가 곧 그 값이다. */
export const corkPlacement = (board) => ({
  left: `${board.cork.x * 100}%`,
  top: `${board.cork.y * 100}%`,
  width: `${board.cork.w * 100}%`,
  height: `${board.cork.h * 100}%`,
})

/** 코르크 면의 한가운데 — 화면에 대한 %. 상태 문구처럼 보드 가운데에 세울 것에 쓴다. */
export const corkCentre = (board) => ({
  left: `${(board.cork.x + board.cork.w / 2) * 100}%`,
  top: `${(board.cork.y + board.cork.h / 2) * 100}%`,
})

export const boardCopy = {
  title: '나를 위한 추천',
  eyebrow: 'PINNED FOR YOU',
  updateSchedule: '매일 06:00 · 18:00 업데이트',
  loading: '추천을 불러오는 중…',
  signedOut: '로그인하면 나만의 추천이 걸려요',
  signedOutHint: '읽은 기사와 관심 분야로 하루 두 번 골라 드립니다.',
  failed: '추천을 불러오지 못했어요. 잠시 뒤 다시 시도해주세요.',
  reasonLabel: '추천 이유',
  open: (label) => `${label} — 요약과 기사 보기`,
  close: '닫기',
  peek: '종이를 위아래로 끌어 높이 조절',
  summaryPending: '요약을 준비하고 있어요. 조금 뒤에 다시 열어보세요.',
  articles: '이 사건을 다룬 기사',
  articlesEmpty: '아직 연결된 기사가 없어요.',
  origin: '원문 보기',
  detailFailed: '상세를 불러오지 못했어요.',
}
