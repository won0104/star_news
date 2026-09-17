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
      <div className={styles.wash} aria-hidden>
        <img
          className={`${styles.photo} ${ready ? styles.photoReady : ''}`}
          src={scene.src}
          alt=""
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
