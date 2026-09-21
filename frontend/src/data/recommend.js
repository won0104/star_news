/**
 * 나를 위한 추천 — which events are recommended, and why.
 *
 * Only the ids and the reasons live here; the title and summary on each card come from
 * the event itself in data/events.js, so a card cannot say something its own detail page
 * contradicts.
 *
 * One list, not two. The design had a second section recommending from the reader's
 * knowledge gaps; every reason here is instead grounded in something the reader did —
 * what they read, what they follow, what they bookmarked. That is what "사용자 기반" means
 * and it is the whole basis of the list, so there is nothing left to put in a second one.
 *
 * Ten of them, in the order they are shown. `reason` names the evidence, which is the
 * point of the screen rather than decoration: a recommendation nobody can account for is
 * just a list.
 */
/**
 * The scene this screen arrives on: a 2.6s move from the front door's room to the wall the
 * board hangs on, played once when 나를 위한 추천 opens.
 *
 * The still is the clip's own final frame, so the hand-back is seamless by construction —
 * no exposure step and no change of framing, which is what every other clip in this project
 * has had to be corrected for. Measured against the decoded last frame it comes out at
 * 44.3dB with a mean luminance of 142.6 against the clip's 142.5, so there is nothing left
 * for a cross-fade to hide. It is also what shows before the clip can play and instead of it
 * under reduced motion, and being the landing it is the right picture in both cases.
 *
 * Re-cut whenever the clip is replaced — a still from an older take is a visible jump at the
 * moment the video hands over. Taken out of the clip rather than rendered separately: the
 * browser pane blocks downloads, so the frame is seeked to duration-0.02, drawn to a canvas
 * and posted to a throwaway local receiver. 1920x1080, 2.5MB as PNG, 165KB as WebP at 44dB.
 *
 * No webm and no encoder pass on the clip (ffmpeg is not installed here): 5.7MB of 1920x1080
 * H.264 with an audio track the element mutes. scripts/encode-clip.ps1 has the recipe.
 */
/**
 * 나를 위한 추천의 방 — 비어 있는 코르크 보드가 걸린 벽 사진 한 장.
 *
 * <PhotoBackdrop> 은 방과 빈 보드만 바닥으로 깔고, <RecommendPane> 이 제목 종이·추천 종이·핀을
 * 별도 에셋으로 올린다. 카드 자체가 버튼이므로 종이 전체를 눌러 상세를 열 수 있다. 도착
 * 영상(arrival.mp4)과 그 마지막 프레임(desk-still.webp)은 옛 방을 찍은 것이라 여기 맞지 않아
 * 뗐다 — `loop: null` 이면 <PhotoBackdrop> 이 첫 프레임부터 정착(settled)으로 친다.
 *
 * 1672×941. 종이 열 장의 자리는 data/recommendBoard.js 가 이 사진의 비율 좌표로 갖는다.
 */
export const arrivalScene = {
  id: 'foryou',
  src: '/assets/board/recommend-board-empty.png',
  loop: null,
  /**
   * 사진을 어디에 맞춰 걸지.
   *
   * 보드의 가운데는 사진의 (가로 52.4%, 세로 46.8%) 지점이다. 그 지점을 **왼쪽 내비를 뺀
   * 내용 영역**의 가운데에 건다 — 화면 가운데에 걸면 보드 왼쪽이 내비 밑으로 들어간다.
   *
   * 16:9 화면에서 cover 는 여유가 0 이라, 사진을 옮기면 가장자리가 빈다. 그래서 딱 그만큼만
   * 키운다: 1.06 이 1440×900 과 1920×1080 둘 다에서 위·왼쪽이 비지 않는 최솟값이다(그 아래로
   * 내리면 위가 몇 px 드러난다). focusY 는 0.468 이 아니라 0.472 — 세로도 그 한계 안에서
   * 최대한 내린 값.
   *
   * <PhotoBackdrop> 과 <RecommendPane> 이 같은 값으로 같은 사각형을 계산해야 글자가 종이 위에
   * 남는다 — 그래서 둘이 여기서 함께 읽는다.
   */
  frame: { width: 1672, height: 941, focusX: 0.524, focusY: 0.472, zoom: 1.06 },
};

export const recommend = {
  reasonLabel: '추천 이유',
  title: '사용자님이 궁금해할 만한 사건들이에요',
  subtitle: '읽은 기사와 관심 분야, 즐겨찾기를 바탕으로 골랐어요.',
  /** Twice a day. No clock times: nothing schedules this yet, so naming 08:00 would be a
      promise the app cannot keep. */
  refresh: '하루 두 번 새로 골라 드려요',
  countLabel: (n) => `${n}개`,

  cards: [
    { eventId: 'chip-export', reason: "최근 3일간 '반도체' 관련 기사를 5회 읽었어요" },
    { eventId: 'bok-rate', reason: "관심 분야 '경제'와 일치해요" },
    { eventId: 'hbm4-race', reason: "'반도체'를 즐겨찾기해서 추천했어요" },
    { eventId: 'nk-defence', reason: "즐겨찾기한 '북한'을 이번 주에 세 번 읽었어요" },
    { eventId: 'won-rate', reason: "'기준금리'를 읽은 사람들이 이어서 많이 봤어요" },
    { eventId: 'house-debt', reason: "관심 분야 '경제'에서 오늘 가장 많이 읽혔어요" },
    { eventId: 'semi-equip', reason: "'반도체 수출'을 따라 읽고 있어서 골랐어요" },
    { eventId: 'ev-battery', reason: "관심 분야 'IT · 과학'과 일치해요" },
    { eventId: 'ai-rule', reason: "'AI'가 들어간 기사를 지난주에 4회 읽었어요" },
    { eventId: 'shipbuilding', reason: '읽은 기록에서 제조업 비중이 늘고 있어요' },
  ],
};
