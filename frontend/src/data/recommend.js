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
export const arrivalScene = {
  id: 'foryou-arrival',
  src: '/assets/board/desk-still.webp',
  loop: { mp4: '/assets/board/arrival.mp4' },
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
