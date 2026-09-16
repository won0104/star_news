/**
 * 화면 전환 애니메이션 일시 정지 스위치.
 *
 * The clips played on the way into a screen — the room's loop at the front door, the
 * arrival into 나를 위한 추천, the attic falling to night on 오늘의 트렌드 — plus the
 * entrance animations panes come in with. Turned off in one place so turning them back
 * on is one edit rather than a hunt: flip this to true and everything resumes.
 *
 * This is separate from 화면 설정's 애니메이션 없애기 (`reduceMotion`), which is the
 * reader's own setting and also quiets ambient motion — the planet turning, the stars
 * shimmering. Those keep running here; only the transitions stop.
 */
export const SCREEN_TRANSITIONS = false;
