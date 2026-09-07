import { SCENE_HEIGHT, SCENE_WIDTH } from '../../data/scene';
import { useSceneScale } from '../../hooks/useSceneScale';
import styles from './SceneCanvas.module.css';

/** Fixed 1672x941 stage, scaled to fit the viewport. Shared by every scene. */
export function SceneCanvas({
  children
}) {
  const scale = useSceneScale(SCENE_WIDTH, SCENE_HEIGHT);
  return <div className={styles.viewport}>
      <div className={styles.canvas} style={{
      transform: `scale(${scale})`
    }}>
        {children}
      </div>
    </div>;
}
