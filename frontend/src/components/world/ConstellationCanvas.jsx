import { useEffect, useRef } from 'react';
import styles from './HistoryPane.module.css';

const STAR_DENSITY = 9200;
const CONNECTION_DISTANCE = 118;
const POINTER_RADIUS = 150;

function createStars(width, height) {
  const count = Math.max(46, Math.min(110, Math.round((width * height) / STAR_DENSITY)));
  return Array.from({ length: count }, (_, index) => {
    const seed = (index + 1) * 16807;
    return {
      x: (((seed * 13) % 997) / 997) * width,
      y: (((seed * 29) % 991) / 991) * height,
      vx: ((((seed * 43) % 101) / 101) - 0.5) * 0.12,
      vy: ((((seed * 61) % 103) / 103) - 0.5) * 0.12,
      radius: 0.55 + (((seed * 17) % 100) / 100) * 1.15,
      phase: ((seed * 31) % 628) / 100,
    };
  });
}

export default function ConstellationCanvas({ reduceMotion }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const viewport = canvas?.parentElement;
    const context = canvas?.getContext('2d');
    if (!canvas || !viewport || !context) return undefined;

    let width = 0;
    let height = 0;
    let frameId;
    let stars = [];
    const pointer = { x: 0, y: 0, active: false };

    const resize = () => {
      const rect = viewport.getBoundingClientRect();
      const nextWidth = Math.max(1, Math.round(rect.width));
      const nextHeight = Math.max(1, Math.round(rect.height));
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(nextWidth * pixelRatio);
      canvas.height = Math.round(nextHeight * pixelRatio);
      canvas.style.width = `${nextWidth}px`;
      canvas.style.height = `${nextHeight}px`;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      width = nextWidth;
      height = nextHeight;
      stars = createStars(width, height);
    };

    const updatePointer = (event) => {
      const rect = viewport.getBoundingClientRect();
      pointer.x = event.clientX - rect.left;
      pointer.y = event.clientY - rect.top;
      pointer.active = pointer.x >= 0 && pointer.x <= rect.width && pointer.y >= 0 && pointer.y <= rect.height;
      if (reduceMotion) draw();
    };

    const clearPointer = () => {
      pointer.active = false;
      if (reduceMotion) draw();
    };

    const draw = (time = 0) => {
      context.clearRect(0, 0, width, height);
      if (!reduceMotion) {
        stars.forEach((star) => {
          star.x = (star.x + star.vx + width) % width;
          star.y = (star.y + star.vy + height) % height;
          if (!pointer.active) return;
          const dx = star.x - pointer.x;
          const dy = star.y - pointer.y;
          const distance = Math.hypot(dx, dy);
          if (distance > 0 && distance < POINTER_RADIUS) {
            const force = (1 - distance / POINTER_RADIUS) * 0.42;
            star.x += (dx / distance) * force;
            star.y += (dy / distance) * force;
          }
        });
      }

      for (let first = 0; first < stars.length; first += 1) {
        const star = stars[first];
        for (let second = first + 1; second < stars.length; second += 1) {
          const other = stars[second];
          const distance = Math.hypot(star.x - other.x, star.y - other.y);
          if (distance >= CONNECTION_DISTANCE) continue;
          context.beginPath();
          context.moveTo(star.x, star.y);
          context.lineTo(other.x, other.y);
          context.strokeStyle = `rgba(118, 172, 204, ${(1 - distance / CONNECTION_DISTANCE) * 0.14})`;
          context.lineWidth = 0.65;
          context.stroke();
        }
        if (pointer.active) {
          const pointerDistance = Math.hypot(star.x - pointer.x, star.y - pointer.y);
          if (pointerDistance < POINTER_RADIUS) {
            context.beginPath();
            context.moveTo(star.x, star.y);
            context.lineTo(pointer.x, pointer.y);
            context.strokeStyle = `rgba(150, 205, 235, ${(1 - pointerDistance / POINTER_RADIUS) * 0.28})`;
            context.lineWidth = 0.75;
            context.stroke();
          }
        }
        const shimmer = reduceMotion ? 0.62 : 0.5 + Math.sin(time * 0.0012 + star.phase) * 0.18;
        context.beginPath();
        context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        context.fillStyle = `rgba(218, 235, 245, ${shimmer})`;
        context.fill();
      }
      if (!reduceMotion) frameId = requestAnimationFrame(draw);
    };

    const resizeObserver = new ResizeObserver(() => {
      resize();
      if (reduceMotion) draw();
    });
    resizeObserver.observe(viewport);
    viewport.addEventListener('pointermove', updatePointer);
    viewport.addEventListener('pointerleave', clearPointer);
    resize();
    draw();

    return () => {
      cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      viewport.removeEventListener('pointermove', updatePointer);
      viewport.removeEventListener('pointerleave', clearPointer);
    };
  }, [reduceMotion]);

  return <canvas ref={canvasRef} className={styles.constellationCanvas} aria-hidden="true" />;
}
