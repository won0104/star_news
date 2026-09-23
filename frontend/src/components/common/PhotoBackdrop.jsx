import { useEffect, useState } from 'react';
import { backdrop } from '../../data/home';
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
 * A scene's clip needs its own treatment — the home loop came back a stop under its
 * still and is corrected in CSS, which would be wrong on any other clip — so the class
 * is looked up by scene id rather than shared. A scene with no entry gets none.
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
const LOOP_CLASS = {
  home: styles.loopHome,
};

/*
 * 사진의 크롭 기준이 공용 규칙과 달라야 하는 장면. 오늘의 트렌드는 <TrendStage> 의 .still 이
 * 같은 밤 사진을 object-position: center 로 한 겹 더 걸기 때문에, 아래 깔린 이 장이 다른
 * 기준으로 잘리면 위 장이 올라오는 순간 배경이 위아래로 미끄러진다.
 */
const PHOTO_CLASS = {
  trend: styles.photoCentred,
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
        className={`${styles.wash} ${WASH_CLASS[scene.id] ?? ''} ${scene.standIn ? styles.washStandIn : ''}`}
        style={scene.standIn ? { '--stand-in': `url(${scene.standIn})` } : undefined}
        aria-hidden
      >
        {/*
          `scene.frame` 이 있으면 cover 대신 그 규칙으로 건다: 사진을 zoom 배 키우고 focusY
          지점을 화면 세로 가운데에 맞춘다. 위에 그려지는 화면이 같은 값으로 같은 사각형을
          계산할 수 있게, 계산은 CSS 변수 넷으로만 한다 (PhotoBackdrop.module.css .photoFramed).
        */}
        <img
          className={`${styles.photo} ${scene.frame ? styles.photoFramed : ''} ${PHOTO_CLASS[scene.id] ?? ''} ${ready ? styles.photoReady : ''}`}
          src={scene.src}
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
