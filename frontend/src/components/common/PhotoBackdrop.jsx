import { useEffect, useState } from 'react';
import { backdrop, rooms } from '../../data/home';
import { useNearestWindow } from '../../hooks/useNearestWindow';
import { BackgroundVideo } from './BackgroundVideo';
import styles from './PhotoBackdrop.module.css';

/**
 * A room photo, full-bleed, with that room in motion over it. Shared by every screen
 * that sits on top of one.
 *
 * `scene` is which room: a still, the clip of it, and whether that clip holds its last
 * frame. It defaults to the sunlit room every screen used before there was more than
 * one, so home, login and signup did not have to change.
 *
 * 장면이 `src` 를 주지 않으면 그 햇살 방을 비율에 맞춰 고른다. 현관·로그인·회원가입·기사
 * 상세가 모두 그 경우여서, 한 곳에서 고르면 네 화면이 함께 맞는다 — 화면마다 따로 고르면
 * 같은 방을 두고 서로 다른 장을 들 수 있다.
 *
 * A scene's clip needs its own treatment — an exposure or crop correction is measured
 * against that one clip and that one still, and would be wrong on any other — so the
 * class is looked up by scene id rather than shared. A scene with no entry gets none.
 *
 * `motion` is opt-in because the auth screens put a paper card and a form over this
 * photo, and a moving background behind live text is a separate design call.
 *
 * Swapping scenes needs a remount, not just new props: <BackgroundVideo> keeps its own
 * played/retired state, so a clip handed a new src after the first one finished would
 * never play. Callers key this component by scene — see <AppScene>.
 *
 * `onSettled` fires when the room stops moving: the clip has reached its end, or there
 * was never going to be one. Screens that want to come in after the movement rather
 * than over it hang off that.
 */
/*
 * 지금은 비어 있다 — 클립을 가진 장면이 하나도 없어 <BackgroundVideo> 가 서지 않는다.
 * 사진풍 홈 스틸과 짝이던 .loopHome 보정은 그 스틸·클립과 함께 내렸다(git 히스토리 참고).
 */
const LOOP_CLASS = {};

/*
 * 사진의 크롭 기준이 공용 규칙과 달라야 하는 장면. 오늘의 트렌드는 <TrendStage> 의 .still 이
 * 같은 밤 사진을 object-position: center 로 한 겹 더 걸기 때문에, 아래 깔린 이 장이 다른
 * 기준으로 잘리면 위 장이 올라오는 순간 배경이 위아래로 미끄러진다.
 *
 * 사진과 스탠드인을 한 항목으로 묶어 둔다 — 둘의 기준이 어긋나면 흐린 장이 선명한 장으로
 * 바뀌는 순간 배경이 미끄러지고, 그것이 바로 이 스탠드인이 없애려는 현상이다.
 */
const CROP_CLASS = {
  trend: { photo: styles.photoCentred, wash: styles.washCentred },
};

/*
 * 사진이 도착하기 전 깔아 두는 색이 공용 크림색이면 안 되는 장면.
 *
 * 공용 .wash 는 햇살 방을 흉내내는 크림색이고, 코르크 보드나 나무 책상처럼 밝은 사진 밑에서는
 * 바뀌는 것이 보이지 않는다. 밤 창가만 그 반대다 — 밝은 화면이 깔렸다가 어두운 사진이 덮으므로
 * 새로고침마다 한 번씩 번쩍인다. 밤 장면은 밤에서 시작한다.
 */
const WASH_CLASS = {
  trend: styles.washNight,
};

export function PhotoBackdrop({
  scene = backdrop,
  motion = false,
  veil = false,
  hideScrollbar = false,
  onSettled,
  children,
}) {
  const [ready, setReady] = useState(false);
  const room = useNearestWindow(rooms);
  // 장면이 자기 사진을 가져왔으면 그 짝인 스탠드인도 함께 가져온다. 아니면 둘 다 방에서 온다.
  const src = scene.src ?? room.src;
  const standIn = scene.src ? scene.standIn : room.standIn;
  const crop = CROP_CLASS[scene.id];
  const plays = motion && !!scene.loop;

  // No clip means the screen is settled from the first frame, and the caller has to be
  // told once rather than left waiting for an `ended` that will never come.
  useEffect(() => {
    if (!plays) onSettled?.();
  }, [plays, onSettled]);

  return (
    <div className={`${styles.root} ${hideScrollbar ? styles.scrollbarHidden : ''}`}>
      {/*
        장면이 `standIn` 을 주면 그 흐린 축소판을 색 위에 덮는다 — 요청 없이 번들에 실려 오므로
        사진보다 먼저 자리에 있다. 값은 CSS 변수로만 건네고 배치는 .washStandIn 이 정한다.
      */}
      <div
        className={`${styles.wash} ${WASH_CLASS[scene.id] ?? ''} ${standIn ? styles.washStandIn : ''} ${scene.frame ? styles.washFramed : ''} ${crop?.wash ?? ''}`}
        style={standIn ? { '--stand-in': `url(${standIn})` } : undefined}
        aria-hidden
      >
        {/*
          `scene.frame` 이 있으면 cover 대신 그 규칙으로 건다: 사진을 zoom 배 키우고 focusY
          지점을 화면 세로 가운데에 맞춘다. 위에 그려지는 화면이 같은 값으로 같은 사각형을
          계산할 수 있게, 계산은 CSS 변수 넷으로만 한다 (PhotoBackdrop.module.css .photoFramed).
        */}
        <img
          className={`${styles.photo} ${scene.frame ? styles.photoFramed : ''} ${crop?.photo ?? ''} ${ready ? styles.photoReady : ''}`}
          src={src}
          alt=""
          style={
            scene.frame
              ? {
                  '--frame-w': scene.frame.width,
                  '--frame-h': scene.frame.height,
                  '--frame-focus-x': scene.frame.focusX ?? 0.5,
                  '--frame-focus-y': scene.frame.focusY ?? 0.5,
                  '--frame-zoom': scene.frame.zoom ?? 1,
                }
              : undefined
          }
          onLoad={() => setReady(true)}
        />
        {plays && (
          <BackgroundVideo
            webm={scene.loop.webm}
            mp4={scene.loop.mp4}
            playOnce
            hold={!!scene.hold}
            onEnded={onSettled}
            className={`${styles.loop} ${LOOP_CLASS[scene.id] ?? ''}`}
          />
        )}
      </div>
      {veil && <div className={styles.veil} aria-hidden />}
      {children}
    </div>
  );
}
