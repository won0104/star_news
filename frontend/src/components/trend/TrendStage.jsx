import { useRef, useState } from 'react'
import { nightBackdrop, nightfall } from '../../data/trend'
import { useNearestWindow } from '../../hooks/useNearestWindow'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { useSettingsValues } from '../../store/settings'
import { SCREEN_TRANSITIONS } from '../../utils/motion'
import { BackgroundVideo } from '../common/BackgroundVideo'
import { TopicNote } from './TopicNote'
import { TrendSky } from './TrendSky'
import styles from './TrendStage.module.css'

/**
 * 주요 트렌드 — 밤 풍경을 담은 창과, 유리 안에서만 움직이는 별자리.
 *
 * The room is stacked: the night outside, the live sky over it, then the wooden frame
 * on top as a transparent asset. Only the backdrop crops, so two of those cover every
 * viewport; the frame is picked from a set drawn at five ratios and stretched the rest
 * of the way. See `nightfall` in data/trend for why, and `useNearestWindow` for how.
 *
 * A transition is optional. It only plays when an asset that ends on this exact still is
 * configured; otherwise the screen settles immediately instead of cross-fading between
 * unrelated rooms.
 */
const glassInset = ({ top, right, bottom, left }) =>
  [top, right, bottom, left].map((edge) => `${edge}%`).join(' ')

export function TrendStage({ playTransition = false, selectedNode, topic = null, onTopicChange }) {
  const [ready, setReady] = useState(false)
  const [ended, setEnded] = useState(false)
  const [overlayRoot, setOverlayRoot] = useState(null)
  // 쪽지를 누를 때마다 센다. 같은 분야를 다시 골라도 URL 은 그대로라, 이 수가 있어야 하늘이
  // 펼쳐 둔 별자리를 접고 분야의 첫 화면으로 돌아간다.
  const [topicPick, setTopicPick] = useState(0)
  const { reduceMotion } = useSettingsValues()
  const prefersReducedMotion = usePrefersReducedMotion()
  const sceneRef = useRef(null)
  const sceneWindow = useNearestWindow(nightfall.frames, sceneRef)
  // 나무틀은 이 상자에 그려지므로 레일을 뺀 씬 박스로 고르지만, 배경은 그 아래 <AppScene> 이
  // 깔아 둔 같은 사진과 합의해야 한다. 그래서 배경만 ref 없이 뷰포트로 잰다.
  const nightWindow = useNearestWindow(nightfall.frames)

  const canPlayTransition = Boolean(
    nightfall.clip?.mp4 &&
    SCREEN_TRANSITIONS &&
    playTransition &&
    !reduceMotion &&
    !prefersReducedMotion,
  )
  const settled = !canPlayTransition || ended
  const backdrop = nightBackdrop(nightWindow).src

  const pickTopic = (topicCode) => {
    setTopicPick((count) => count + 1)
    onTopicChange(topicCode)
  }

  return (
    <div className={styles.stage}>
      <div ref={sceneRef} className={styles.sceneFrame}>
        <img className={styles.sidebarExtension} src={nightfall.sidebarStill} alt="" aria-hidden />

        <img
          className={`${styles.still} ${ready ? styles.stillReady : ''}`}
          src={backdrop}
          alt=""
          aria-hidden
          onLoad={() => setReady(true)}
        />

        {canPlayTransition && (
          <BackgroundVideo
            mp4={nightfall.clip.mp4}
            playOnce
            fadeMs={1400}
            onEnded={() => setEnded(true)}
            className={styles.clip}
          />
        )}

        <div className={styles.windowLayer}>
          {settled && (
            <div className={styles.windowGlass} style={{ inset: glassInset(sceneWindow.opening) }}>
              <TrendSky overlayRoot={overlayRoot} selectedNode={selectedNode} topic={topic} topicPick={topicPick} />
            </div>
          )}

          <img className={styles.frame} src={sceneWindow.src} alt="" aria-hidden />
        </div>

        {/*
          쪽지는 방의 물건이지 창밖이 아니다. 이 층이 나무틀 위에 뜨면서 별은 유리 안에 갇히는
          자리라, 쪽지가 창틀에 붙은 것으로 읽힌다.
        */}
        <div ref={setOverlayRoot} className={styles.sceneOverlay}>
          {onTopicChange && (
            <TopicNote topic={topic} onSelect={pickTopic} pillar={sceneWindow.opening.left} />
          )}
        </div>
      </div>
    </div>
  )
}
