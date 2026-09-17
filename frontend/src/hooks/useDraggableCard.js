import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * 포인터로 떠 있는 카드를 옮기되, 현재 보이는 장면 밖으로는 빠지지 않게 한다.
 *
 * `handleProps`는 카드 전체나 별도의 제목 영역에 붙일 수 있다. 버튼·링크·입력 요소에서
 * 시작한 포인터는 드래그로 바꾸지 않아 닫기와 북마크 같은 기존 동작을 보존한다.
 */
export function useDraggableCard() {
  const cardRef = useRef(null);
  const dragRef = useRef(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);

  const beginDrag = useCallback(
    (event) => {
      if (event.button !== 0 || event.target.closest('button, a, input, select, textarea')) {
        return;
      }

      const card = cardRef.current;
      const boundary = card?.offsetParent;
      if (!card || !boundary) return;

      const cardRect = card.getBoundingClientRect();
      const boundaryRect = boundary.getBoundingClientRect();

      dragRef.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        offset,
        cardRect,
        limits: {
          left: Math.max(0, boundaryRect.left),
          top: Math.max(0, boundaryRect.top),
          right: Math.min(window.innerWidth, boundaryRect.right),
          bottom: Math.min(window.innerHeight, boundaryRect.bottom),
        },
      };

      event.currentTarget.setPointerCapture?.(event.pointerId);
      event.preventDefault();
      setDragging(true);
    },
    [offset],
  );

  const moveDrag = useCallback((event) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    const minX = drag.limits.left - drag.cardRect.left;
    const maxX = drag.limits.right - drag.cardRect.right;
    const minY = drag.limits.top - drag.cardRect.top;
    const maxY = drag.limits.bottom - drag.cardRect.bottom;

    setOffset({
      x: drag.offset.x + clamp(deltaX, minX, maxX),
      y: drag.offset.y + clamp(deltaY, minY, maxY),
    });
  }, []);

  const endDrag = useCallback((event) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    event.currentTarget.releasePointerCapture?.(event.pointerId);
    dragRef.current = null;
    setDragging(false);
  }, []);

  useEffect(() => {
    const reset = () => setOffset({ x: 0, y: 0 });
    window.addEventListener('resize', reset);
    return () => window.removeEventListener('resize', reset);
  }, []);

  return {
    cardRef,
    cardStyle: { translate: `${offset.x}px ${offset.y}px` },
    dragging,
    handleProps: {
      onPointerDown: beginDrag,
      onPointerMove: moveDrag,
      onPointerUp: endDrag,
      onPointerCancel: endDrag,
    },
  };
}

function clamp(value, min, max) {
  if (min > max) return 0;
  return Math.min(max, Math.max(min, value));
}
