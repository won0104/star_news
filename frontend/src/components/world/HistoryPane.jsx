import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { historyCopy, historyOverview, historyStories } from '../../data/history';
import { useSettingsValues } from '../../store/settings';
import styles from './HistoryPane.module.css';

const TONE_CLASS = {
  rose: 'toneRose', gold: 'toneGold', mint: 'toneMint', peach: 'tonePeach',
  violet: 'toneViolet', cyan: 'toneCyan', blue: 'toneBlue',
};
const INITIAL_VIEW = { rotationX: -11, rotationY: -18, rotationZ: 3, zoom: 1 };
const COMPANION_STARS = [
  { x: 6, y: 29, size: 17, driftX: -5, driftY: -7, duration: 3.2 },
  { x: 82, y: 17, size: 13, driftX: 6, driftY: -5, duration: 3.8 },
  { x: 79, y: 73, size: 15, driftX: 4, driftY: 7, duration: 4.4 },
];
const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

function fibonacciPoint(index, count) {
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const y = 1 - ((index + 0.5) / count) * 2;
  const horizontalRadius = Math.sqrt(Math.max(0, 1 - y * y));
  const angle = goldenAngle * index + Math.PI / 2;
  return { x: Math.cos(angle) * horizontalRadius, y: -y, z: Math.sin(angle) * horizontalRadius };
}

function rotatedDepth(point, view) {
  const rad = Math.PI / 180;
  const [xAngle, yAngle, zAngle] = [view.rotationX * rad, view.rotationY * rad, view.rotationZ * rad];
  const xAfterZ = point.x * Math.cos(zAngle) - point.y * Math.sin(zAngle);
  const yAfterZ = point.x * Math.sin(zAngle) + point.y * Math.cos(zAngle);
  const zAfterY = -xAfterZ * Math.sin(yAngle) + point.z * Math.cos(yAngle);
  return clamp((yAfterZ * Math.sin(xAngle) + zAfterY * Math.cos(xAngle) + 1) / 2, 0, 1);
}

function MeteorField({ reduceMotion }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const context = canvas.getContext('2d');
    let width = 0;
    let height = 0;
    let stars = [];
    let meteors = [];
    let elapsed = 0;
    let previousTime = performance.now();
    let frameId;

    const makeStars = () => {
      const count = clamp(Math.round((width * height) / 5200), 90, 180);
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        radius: 0.4 + Math.random() * 1.1,
        phase: Math.random() * Math.PI * 2,
      }));
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * ratio));
      canvas.height = Math.max(1, Math.round(height * ratio));
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      makeStars();
    };

    const draw = (deltaTime) => {
      context.clearRect(0, 0, width, height);
      for (const star of stars) {
        const pulse = reduceMotion ? 0.45 : 0.25 + 0.4 * (0.5 + 0.5 * Math.sin(elapsed * 1.5 + star.phase));
        context.fillStyle = 'rgba(234, 234, 240, ' + pulse + ')';
        context.beginPath();
        context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        context.fill();
      }

      if (!reduceMotion && Math.random() < 1.2 * deltaTime) {
        const angle = (35 * Math.PI) / 180;
        const speed = 240 + Math.random() * 180;
        meteors.push({
          x: Math.random() * (width + height) - height * 0.3,
          y: -10,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          size: 0.8 + Math.random() * 1.2,
        });
      }

      meteors = meteors.filter((meteor) => meteor.x < width + 90 && meteor.y < height + 90);
      for (const meteor of meteors) {
        meteor.x += meteor.vx * deltaTime;
        meteor.y += meteor.vy * deltaTime;
        const distance = Math.hypot(meteor.vx, meteor.vy);
        const tailX = meteor.x - (meteor.vx / distance) * 90;
        const tailY = meteor.y - (meteor.vy / distance) * 90;
        const gradient = context.createLinearGradient(meteor.x, meteor.y, tailX, tailY);
        gradient.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
        gradient.addColorStop(0.25, 'rgba(169, 156, 255, 0.55)');
        gradient.addColorStop(1, 'rgba(169, 156, 255, 0)');
        context.strokeStyle = gradient;
        context.lineWidth = meteor.size;
        context.lineCap = 'round';
        context.beginPath();
        context.moveTo(meteor.x, meteor.y);
        context.lineTo(tailX, tailY);
        context.stroke();
      }
    };

    const animate = (now) => {
      const deltaTime = Math.min(0.05, (now - previousTime) / 1000);
      previousTime = now;
      elapsed += deltaTime;
      draw(deltaTime);
      if (!reduceMotion) frameId = requestAnimationFrame(animate);
    };

    const observer = new ResizeObserver(() => {
      resize();
      if (reduceMotion) draw(0);
    });
    observer.observe(canvas);
    resize();
    animate(previousTime);

    return () => {
      observer.disconnect();
      if (frameId) cancelAnimationFrame(frameId);
    };
  }, [reduceMotion]);

  return <canvas ref={canvasRef} className={styles.meteorCanvas} aria-hidden="true" />;
}
function EventSphere({ events, storyTitle, tone, reduceMotion, onSelect }) {
  const [view, setView] = useState(INITIAL_VIEW);
  const [radius, setRadius] = useState(240);
  const [autoRotating, setAutoRotating] = useState(!reduceMotion);
  const viewportRef = useRef(null);
  const viewRef = useRef(INITIAL_VIEW);
  const dragRef = useRef(null);
  const velocityRef = useRef({ x: 0, y: 0 });
  const autoRotateRef = useRef(!reduceMotion);
  const blockClickRef = useRef(false);

  const updateView = (next) => {
    viewRef.current = next;
    setView(next);
  };

  useEffect(() => {
    autoRotateRef.current = reduceMotion ? false : autoRotating;
    if (reduceMotion) {
      velocityRef.current = { x: 0, y: 0 };
    }
  }, [autoRotating, reduceMotion]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return undefined;
    const resize = () => {
      const rect = viewport.getBoundingClientRect();
      setRadius(clamp(Math.min(rect.width, rect.height) * 0.32, 150, 300));
    };
    const observer = new ResizeObserver(resize);
    observer.observe(viewport);
    resize();
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let previousTime = performance.now();
    let frameId;
    const animate = (currentTime) => {
      const frameScale = clamp((currentTime - previousTime) / 16.667, 0, 2.5);
      previousTime = currentTime;
      const current = viewRef.current;
      let next = current;

      if (!dragRef.current) {
        const velocity = velocityRef.current;
        next = {
          ...current,
          rotationX: clamp(current.rotationX + velocity.x * frameScale, -75, 75),
          rotationY: current.rotationY + velocity.y * frameScale
            + (autoRotateRef.current ? 0.055 * frameScale : 0),
          rotationZ: current.rotationZ + (autoRotateRef.current ? 0.014 * frameScale : 0),
        };
        const friction = Math.pow(0.945, frameScale);
        velocityRef.current = { x: velocity.x * friction, y: velocity.y * friction };
      }
      if (next !== current) updateView(next);
      frameId = requestAnimationFrame(animate);
    };
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, []);

  const handlePointerDown = (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    const eventMarker = event.target.closest('[data-event-id]');
    event.currentTarget.focus({ preventScroll: true });
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId, startX: event.clientX, startY: event.clientY,
      previousX: event.clientX, previousY: event.clientY, moved: false,
      eventId: eventMarker?.dataset.eventId ?? null,
    };
    velocityRef.current = { x: 0, y: 0 };
  };

  const handlePointerMove = (event) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.previousX;
    const deltaY = event.clientY - drag.previousY;
    if (Math.abs(event.clientX - drag.startX) > 6 || Math.abs(event.clientY - drag.startY) > 6) {
      drag.moved = true;
    }
    const stepY = deltaX * 0.24;
    const stepX = -deltaY * 0.24;
    velocityRef.current = {
      x: velocityRef.current.x * 0.68 + stepX * 0.32,
      y: velocityRef.current.y * 0.68 + stepY * 0.32,
    };
    drag.previousX = event.clientX;
    drag.previousY = event.clientY;
    updateView({
      ...viewRef.current,
      rotationX: clamp(viewRef.current.rotationX + stepX, -75, 75),
      rotationY: viewRef.current.rotationY + stepY,
    });
  };

  const handlePointerUp = (event) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
    if (reduceMotion) velocityRef.current = { x: 0, y: 0 };
    if (!drag.moved && drag.eventId) {
      const selectedEvent = events.find((item) => item.id === drag.eventId);
      if (selectedEvent) {
        blockClickRef.current = true;
        onSelect(selectedEvent);
        window.setTimeout(() => { blockClickRef.current = false; }, 0);
      }
      return;
    }
    if (!drag.moved) return;
    blockClickRef.current = true;
    window.setTimeout(() => { blockClickRef.current = false; }, 0);
  };

  const handleKeyboard = (event) => {
    const current = viewRef.current;
    const step = 8;
    switch (event.key) {
      case 'ArrowLeft': updateView({ ...current, rotationY: current.rotationY - step }); break;
      case 'ArrowRight': updateView({ ...current, rotationY: current.rotationY + step }); break;
      case 'ArrowUp':
        updateView({ ...current, rotationX: clamp(current.rotationX - step, -75, 75) }); break;
      case 'ArrowDown':
        updateView({ ...current, rotationX: clamp(current.rotationX + step, -75, 75) }); break;
      case ' ':
        autoRotateRef.current = !autoRotateRef.current;
        setAutoRotating(autoRotateRef.current);
        break;
      case 'Home':
        velocityRef.current = { x: 0, y: 0 };
        updateView(INITIAL_VIEW);
        break;
      default: return;
    }
    event.preventDefault();
  };

  const points = events.map((_, index) => fibonacciPoint(index, Math.max(events.length, 1)));

  return (
    <div
      ref={viewportRef}
      className={styles.sphereViewport}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onKeyDown={handleKeyboard}
      tabIndex={0}
      role="group"
      aria-label={`${storyTitle}의 Event 별 구. 드래그와 방향키로 회전할 수 있습니다.`}
      style={{ '--sphere-radius': `${radius}px` }}
    >
      <MeteorField reduceMotion={reduceMotion} />
      <div
        className={styles.sphereWorld}
        style={{ transform: `rotateX(${view.rotationX}deg) rotateY(${view.rotationY}deg) rotateZ(${view.rotationZ}deg)` }}
      >
        <div className={styles.sphereHalo} aria-hidden />
        <div className={styles.wireframe} aria-hidden>
          {Array.from({ length: 6 }, (_, index) => (
            <span
              key={`meridian-${index}`}
              className={styles.sphereRing}
              style={{
                width: radius * 2, height: radius * 2,
                marginLeft: -radius, marginTop: -radius,
                transform: `rotateY(${index * 30}deg)`,
              }}
            />
          ))}
          {[-0.66, -0.33, 0, 0.33, 0.66].map((normalizedY) => {
            const ringRadius = radius * Math.sqrt(1 - normalizedY * normalizedY);
            return (
              <span
                key={`latitude-${normalizedY}`}
                className={styles.sphereRing}
                style={{
                  width: ringRadius * 2, height: ringRadius * 2,
                  marginLeft: -ringRadius, marginTop: -ringRadius,
                  top: normalizedY * radius, transform: 'rotateX(90deg)',
                }}
              />
            );
          })}
        </div>

        <div className={styles.eventStars} role="list">
          {events.map((event, index) => {
            const point = points[index];
            const depth = rotatedDepth(point, view);
            return (
              <div
                key={event.id}
                className={styles.eventNode}
                role="listitem"
                style={{
                  transform: `translate3d(${point.x * radius}px, ${point.y * radius}px, ${point.z * radius}px)`,
                  zIndex: Math.round(depth * 1000),
                }}
              >
                <button
                  type="button"
                  data-event-id={event.id}
                  className={styles.eventMarker}
                  style={{
                    transform: `rotateZ(${-view.rotationZ}deg) rotateY(${-view.rotationY}deg) rotateX(${-view.rotationX}deg) translate(-50%, -50%) scale(${0.72 + depth * 0.34})`,
                    opacity: 0.13 + (depth ** 1.35) * 0.87,
                    filter: `blur(${((1 - depth) * 0.75).toFixed(2)}px)`,
                  }}
                  onClick={() => { if (!blockClickRef.current) onSelect(event); }}
                  aria-label={historyCopy.openEvent(event.title)}
                >
                  <img className={styles.eventStar} src="/assets/history/topic-star.png" alt="" draggable="false" />
                  <span className={styles.companionField} aria-hidden="true">
                    {COMPANION_STARS.slice(0, 2 + (index % 2)).map((companion, companionIndex) => (
                      <img
                        key={companionIndex}
                        className={styles.companionStar}
                        src="/assets/history/topic-star.png"
                        alt=""
                        draggable="false"
                        style={{
                          '--companion-x': `${companion.x}%`,
                          '--companion-y': `${companion.y}%`,
                          '--companion-size': `${companion.size}px`,
                          '--companion-drift-x': `${companion.driftX}px`,
                          '--companion-drift-y': `${companion.driftY}px`,
                          '--companion-duration': `${companion.duration + index * 0.16}s`,
                          '--companion-delay': `${-(index * 0.43 + companionIndex * 0.8)}s`,
                        }}
                      />
                    ))}
                  </span>
                  <span className={styles.eventLabel}>
                    <strong>{event.title}</strong>
                    <small>관련 기사 {event.articleCount}개</small>
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <p className={styles.dragHint}>
        DRAG · SPACE {autoRotating && !reduceMotion ? 'PAUSE' : 'PLAY'} · 별을 누르면 EVENT 상세로 이동
      </p>
      <span className={`${styles.toneMarker} ${styles[TONE_CLASS[tone]]}`} aria-hidden />
    </div>
  );
}

export function HistoryPane() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { reduceMotion } = useSettingsValues();
  const cluster = historyStories.find((item) => item.topicCode === params.get('topic')) ?? historyStories[0];
  const story = cluster.stories.find((item) => item.id === params.get('story')) ?? cluster.stories[0];
  const storyIndex = cluster.stories.findIndex((item) => item.id === story.id);

  const selectTopic = (nextCluster) => {
    setParams({ view: 'log', topic: nextCluster.topicCode, story: nextCluster.stories[0].id }, { replace: true });
  };
  const selectStory = (nextStory) => {
    setParams({ view: 'log', topic: cluster.topicCode, story: nextStory.id }, { replace: true });
  };
  const moveStory = (direction) => {
    const nextIndex = (storyIndex + direction + cluster.stories.length) % cluster.stories.length;
    selectStory(cluster.stories[nextIndex]);
  };
  const openEvent = (event) => {
    navigate(`/history/${story.id}/events/${event.id}?topic=${cluster.topicCode}`);
  };

  return (
    <section className={styles.page} aria-labelledby="history-title">
      <div className={`${styles.stage} ${styles[TONE_CLASS[cluster.tone]]}`}>
        <header className={styles.head}>
          <div>
            <p className={styles.eyebrow}>{historyOverview.periodLabel} · {historyOverview.generatedAt} 기준</p>
            <h1 id="history-title">{historyCopy.title}</h1>
            <p className={styles.description}>카테고리와 Story를 선택하고, Event 별 구를 돌려 기록을 탐색해보세요.</p>
          </div>
          <div className={styles.summary} aria-label="기록 요약">
            <span><strong>{historyOverview.totalArticleCount}</strong>개 기사</span>
            <span><strong>{historyOverview.topicCount}</strong>개 분야</span>
          </div>
        </header>

        <nav className={styles.categoryBar} aria-label="뉴스 카테고리">
          {historyStories.map((item) => (
            <button
              type="button"
              key={item.topicCode}
              className={`${styles.categoryButton} ${styles[TONE_CLASS[item.tone]]}`}
              aria-current={item.topicCode === cluster.topicCode ? 'true' : undefined}
              onClick={() => selectTopic(item)}
            >
              <span>{item.topicName}</span>
              <small>{item.articleCount}</small>
            </button>
          ))}
        </nav>

        <div className={styles.storyBar}>
          <span className={styles.storyEyebrow}>{historyCopy.storyLabel}</span>
          <button type="button" className={styles.storyArrow} onClick={() => moveStory(-1)} aria-label={historyCopy.previousStory}>‹</button>
          <div className={styles.storyTabs} role="tablist" aria-label={`${cluster.topicName} Story`}>
            {cluster.stories.map((item, index) => (
              <button
                type="button"
                key={item.id}
                role="tab"
                aria-selected={item.id === story.id}
                className={styles.storyTab}
                onClick={() => selectStory(item)}
              >
                <span>{item.title}</span>
                <small>{index + 1}</small>
              </button>
            ))}
          </div>
          <button type="button" className={styles.storyArrow} onClick={() => moveStory(1)} aria-label={historyCopy.nextStory}>›</button>
          <span className={styles.storyCount}>{storyIndex + 1} / {cluster.stories.length}</span>
        </div>

        <div className={styles.galleryHead}>
          <div>
            <span>{cluster.topicName} · {historyCopy.storyLabel}</span>
            <h2>{story.title}</h2>
          </div>
          <p>{story.eventCount}개의 Event 별</p>
        </div>

        <EventSphere
          key={story.id}
          events={story.events}
          storyTitle={story.title}
          tone={cluster.tone}
          reduceMotion={reduceMotion}
          onSelect={openEvent}
        />
      </div>
    </section>
  );
}
