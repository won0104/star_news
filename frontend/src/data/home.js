/** Home — a single full-bleed photo with the site chrome over it. */

export const brand = {
  name: '별빛 뉴스',
  section: '나를 위한 추천',
}
/**
 * 내비게이션의 목적지 — 세 갈래와, 갈래마다 딸린 화면.
 *
 * 한동안 잎을 전부 평평하게 늘어놓았다. 화면이 넷이던 때는 그래서 어디서든 한 번에 갈 수
 * 있었지만, 현관이 검색을 받으면서 잎이 다섯이 되었고 나란히 두기에는 많아졌다. 그래서 다시
 * 갈래로 묶되, 예전처럼 판을 열어 들어가는 두 단계가 아니라 **지금 있는 갈래의 아래만** 펼친다.
 * 다른 갈래로 가는 것은 여전히 한 번이다.
 *
 * `id` 는 <AppScene> 이 `?view=` 로 받는 값이다. 탐색만 `route` 를 갖는다 — 현관은 /app 의
 * 한 화면이 아니라 따로 선 라우트라서, 그쪽은 `?view=` 로 갈 수 없다.
 */
export const navItems = [
  {
    id: 'home',
    label: '탐색',
    route: '/',
    children: [{ id: 'trend', label: '오늘의 트렌드' }],
  },
  {
    id: 'foryou',
    label: '나를 위한 추천',
  },
  {
    id: 'log',
    label: '나의 기록',
    children: [{ id: 'report', label: '나의 리포트' }],
  },
]

/**
 * `?view=` 가 실어 나를 수 있는 화면. 갈래와 그 아래를 모두 세고, 자기 라우트를 가진 것만
 * 뺀다 — 목록을 두 벌 들고 어긋나느니 한 벌에서 뽑는다.
 */
export const viewIds = navItems.flatMap((item) => [
  ...(item.route ? [] : [item.id]),
  ...(item.children ?? []).map((child) => child.id),
])

/** 잎이 속한 갈래. 어느 갈래를 켜고 그 아래를 펼칠지 정한다. */
export const navSectionOf = (id) =>
  navItems.find((item) => item.id === id || item.children?.some((child) => child.id === id))
/**
 * 현관의 문구.
 *
 * 화면에는 손글씨 그림으로 걸리지만(MainScene.module.css 의 .tagline) 읽을 글은 여기 남긴다 —
 * 그림이 되었다고 문구가 아닌 것은 아니고, 스크린리더와 검색엔진에게는 이쪽이 전부다.
 */
export const mainCopy = {
  tagline: '오늘도, 세상을 조금 더 가까이.',
}

export const authActions = {
  signIn: '로그인',
  signUp: '회원가입',
}

/**
 * The account menu behind the avatar, once someone is signed in. Each `id` is a pane in
 * the settings overlay (data/settings.js `settingsPanes`), so an entry here opens that
 * overlay on that pane — 뉴스 관리 opens 관심 관리. `signOut` is kept out of the list
 * because it is not a place to go: it ends the session.
 */
export const accountMenu = {
  label: '계정 메뉴',
  unknownUser: '내 계정',
  items: [
    {
      id: 'interest',
      label: '뉴스 관리',
    },
    {
      id: 'account',
      label: '계정',
    },
  ],
  signOut: '로그아웃',
  signingOut: '로그아웃 중…',
  signOutFailed: '로그아웃하지 못했어요. 잠시 후 다시 시도해 주세요.',
}

/**
 * 햇살 든 방 — 현관, 로그인·회원가입, 기사 상세가 함께 서 있는 한 방.
 *
 * 비율마다 한 장씩 그려져 있다. 사진은 cover 로 깔리므로 어느 비율에서도 화면을 덮지만,
 * 비율이 멀수록 창과 소파, 화분처럼 모서리에 놓인 것들이 잘려 나간다 — 책상·보드·창틀과
 * 같은 방식으로 가장 가까운 장을 고른다(useNearestWindow).
 *
 * 파일이 /assets/auth 에 있는 것은 이 방이 로그인 화면용으로 먼저 그려졌기 때문이고, 지금은
 * 세 화면이 같은 장을 쓴다.
 */
export const rooms = [
  { ratio: 1672 / 941, src: '/assets/auth/room-16x9-v2.webp', standIn: 'data:image/webp;base64,UklGRhIDAABXRUJQVlA4WAoAAAAgAAAANwAAHwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggJAEAAJAHAJ0BKjgAIAA+lT6ZSaWjIiEwFAoAsBKJZQC/7CsRyFIAzRtBbw9dPk4sK/+q7BUoSwqZ4fVzc79Hk6VL0WVQ6/VtwAD++ZRLtWdubYfrjkvUlgVfpUmPmAAk8VzdiVSdfYbgNCFd/NS+SDxRpXi5Wkpz/ktV4kBqMgQAyTRvmFL5bnY4/7/Ol3XM1HT+UfjprjQGvPcljh+I9mLE7zgD6BQ9gar+3QeVyg2bycTj34J0RcFgB+cY7QtnUgsKGS8pUsffzo+fVQcMRnu+t1duZTSQI7Hnctp5jpsTopQk7E5aWOH118B20AHqPe+PQfcMDLqJ8FPzNH9pbXY6q0RJn7lLMYgaD7dYX9aQj3UfzRmOUxySeYPR6aHS/OgBN0AAAAA=' },
  { ratio: 1448 / 1086, src: '/assets/auth/room-4x3-v2.webp', standIn: 'data:image/webp;base64,UklGRtADAABXRUJQVlA4WAoAAAAgAAAANwAAKQAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDgg4gEAAPAKAJ0BKjgAKgA+lTyaSSWjIiEquAz4sBKJZQDBw9tIMmd1s+a3sKCW+fr6awOZCjj/ehslRngw94gR+F2p2xmog9RBE54e2/O4VbUXLBjN7u+8+tbBBWqTOr4+/R7E6AD+9khGLghfl73ErQenpq5tsFR2Rg4lVzJmJfaZUQZKnUtumQr/7WU3vs+4Hjyy1KrJBLEOjp2XXZ+hS1JRrMDNCcYzLTbuyF+M2IFTUAUBKycN9yHdt6CjYGo9CDWiizLz7AHxSnNMLH53nn7sI7MvzIXu1yeuKiJbS12U+c0ntVD3Dajb8iT4z51ivxLtpCKDVcwRbv1b06Rv1pM+D7sNSSN17xvZRBS9xXLdEvX3suRGmV2yriIvoy++AogSkc/BEWEGzIOyWIjljwy29PJtOaX23JYtAxYhbRwTyo8kiVHS4vnNwcnCpNvRv9g11eILkXFDcyDfgvjsGeCcc7ZWLUfrYlq3oWESGKn1qUhCbl1PVJ6idqyuFZ0cYIwDBRST/ndXRJTXLjipJCioaoYEX4jRc/IsflAwlSiVhIECs1spNCovv6kc43SyrNr+PfATJxuRK1aI5txgYQWk+4nl8rAC31cKBkvZoJwYrRy6VrOt+tI0Vp9CZ3ewUYAJAAAA' },
  { ratio: 1086 / 1448, src: '/assets/auth/room-3x4-v2.webp', standIn: 'data:image/webp;base64,UklGRtwDAABXRUJQVlA4WAoAAAAgAAAAKQAANwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDgg7gEAAHAKAJ0BKioAOAA+lT6aSKWjIqEoFV8YsBKJZQDE+YN5xOJGc5pUOzZ8bSpDI1WWFUWrB8d4TW7NSsUDxwfM6RoEezxn676Aore7iviDKrMq/WdbJZ7HOTODH2sAAP75mIF0Ef+Lg81qAWJjIA/d3kSTImXWzbadRbCk1nIwmV/WgVXMD7di3d533ODtRS0mZ49dqnghcAM3Azr8xcKNZI2p4rx7ZMcQ4fSm/Cowe8f/vbMxYimW3ycGmyhA3no/VbgOJIQUSsU3d54VOaEVYtaFRgab/FbtM2FCPjhpCu61D++WIGY2xdVzLNFx99TJdn9EdjJeLu74wrzS4+kJHgUd/PyCeSz8IytIt2evIWWvggBG9LrDeA07t5z2Sr70Ygmu3GK89UcnyAtXvzFLhNs0HiGmXSqVeeRTv0wZC3hGHqhddSvs4U6hswTxoHtYJEUGRGXAVV2nuyL1mAaGNA/jW7TXDP/a5x8dIljCgCXJDfwYmBuK31QK5ZVmmB816IEDm1izbfdVRcdLldTPRgLYMbwOUpDjd+0WAirUdIkYeqABTTD9I45su84quYzIiTWbhvsKQTJbWsJrs+wkzvR1ft+3rczcVw2fsqSiH4jeN97xpsAkZ1s0LighqvXRUbPuVB1INBa+Hv5IOgAA' },
  { ratio: 941 / 1672, src: '/assets/auth/room-9x16-v2.webp', standIn: 'data:image/webp;base64,UklGRlADAABXRUJQVlA4WAoAAAAgAAAAHwAANwAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggYgEAADAJAJ0BKiAAOAA+jTiYSCUjIqEz9m1QoBGJZQC44cDXgUT3vPIv/c2iogCEne1ux63tBvnQD1fQYZFMXMMCaf9oauU0B7ed6eVC4WUhxb0slAAA/u5WKWMNTN4TT4aafpipAhtbnjXMnuh4MX3BmxQ7adpZByfKC8RRwBF2dk26HxmyaEqLQqawxahnIzQBUWH3yiChL/RUyiOtvDSW4vapxqbb1k9FSf17KNavbCqxbQVyV7T6p9mZJ7CAJz4gIf4BFSq5He4SbeZ9JFLqVX69dUoZkuwpZnh8dcFuV0Bfp4Of/Hhfv1Yzk4MuAB/T0kBv3Ul+FUR1Q3F0oD8LRLFhujr7urSzZ2XTneVy/ODCwvdVQYHGE0RRBZkTIpjo6JGyLtBr2U1Vli/oR2hMz5Nhgd1vPkKJMQsfAknBSmLacalIsxMsxYHu3kc5rrLDBhNvyGYFiFBAKLu8dqho/AAAAA==' },
]

/**
 * 그 방을 장면으로 세운 것. `id` 는 <PhotoBackdrop> 이 CSS 를, <AppScene> 이 컴포넌트를
 * 키잉하는 값이다. `src` 가 없으므로 <PhotoBackdrop> 이 위 목록에서 비율에 맞는 장을 고른다.
 */
export const backdrop = {
  id: 'home',
  /**
   * 일러스트 방에는 짝이 되는 클립이 아직 없다.
   *
   * 예전 사진풍 스틸(assets/home/backdrop.png)에는 같은 방을 찍은 10초 클립이 있었고, 그
   * 마지막 프레임이 스틸과 34.8dB 로 맞아 넘김이 컷으로 읽히지 않았다. 방을 일러스트로 바꾸면
   * 그 짝이 깨진다 — 사진풍 클립이 끝나면서 일러스트로 넘어가면 전혀 다른 방으로 점프한다.
   * 클립을 다시 그리기 전까지는 움직임 없이 스틸만 선다.
   *
   * 그 스틸과 클립, 그리고 둘의 노출 차를 되돌리던 .loopHome 보정은 함께 내렸다. 되살릴
   * 일이 있으면 git 히스토리에 있지만, 일러스트 방에는 새 클립과 새 측정이 필요하다.
   */
  loop: null,
}

/**
 * Real photographed props (not CSS/SVG), used to make the auth card read as a
 * physical paper pinned to the wall rather than a flat UI panel.
 */
export const deskProps = {
  paperTile: '/assets/home/paper-tile.png',
  paperOverlay: '/assets/home/paper-overlay.png',
  clipFront: '/assets/home/clip-front.png',
  clipAngle: '/assets/home/clip-angle.png',
}
