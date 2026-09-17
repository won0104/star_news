import { useCallback, useEffect, useRef, useState } from 'react'

const INTERACTIVE_SELECTOR = 'button, a, input, select, textarea'
const ARROW_KEYS = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'])

/**
 * 떠 있는 카드를 화면 안에서 옮기고 모서리로 크기를 조절한다.
 *
 * 첫 조작 시 CSS로 배치된 현재 위치를 절대 좌표로 고정한다. 이후 이동과 크기 변경이
 * 서로의 기준점을 잃지 않으며, viewport가 바뀌면 반응형 CSS 배치로 안전하게 돌아간다.
 */
export function useResizableCard({ minWidth = 300, minHeight = 280 } = {}) {
  const cardRef = useRef(null)
  const operationRef = useRef(null)
  const [rect, setRect] = useState(null)
  const [interaction, setInteraction] = useState(null)

  const beginOperation = useCallback((event, mode) => {
    if (event.button !== 0) return
    if (mode === 'move' && event.target.closest(INTERACTIVE_SELECTOR)) return

    const snapshot = getCardSnapshot(cardRef.current)
    if (!snapshot) return

    operationRef.current = {
      ...snapshot,
      mode,
      direction: event.currentTarget.dataset.resizeDirection,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    }

    setRect(toLocalRect(snapshot.cardRect, snapshot.boundaryRect))
    setInteraction(mode)
    event.currentTarget.setPointerCapture?.(event.pointerId)
    event.preventDefault()
  }, [])

  const moveOperation = useCallback(
    (event) => {
      const operation = operationRef.current
      if (!operation || operation.pointerId !== event.pointerId) return

      const deltaX = event.clientX - operation.startX
      const deltaY = event.clientY - operation.startY
      const nextRect =
        operation.mode === 'resize'
          ? resizeRect(operation, deltaX, deltaY, minWidth, minHeight)
          : moveRect(operation, deltaX, deltaY)

      setRect(toLocalRect(nextRect, operation.boundaryRect))
    },
    [minHeight, minWidth],
  )

  const endOperation = useCallback((event) => {
    const operation = operationRef.current
    if (!operation || operation.pointerId !== event.pointerId) return

    event.currentTarget.releasePointerCapture?.(event.pointerId)
    operationRef.current = null
    setInteraction(null)
  }, [])

  const resizeWithKeyboard = useCallback(
    (event) => {
      if (!ARROW_KEYS.has(event.key)) return

      const snapshot = getCardSnapshot(cardRef.current)
      if (!snapshot) return

      const step = event.shiftKey ? 24 : 8
      const deltaX = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0
      const deltaY = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0
      const nextRect = resizeRect(
        {
          ...snapshot,
          direction: event.currentTarget.dataset.resizeDirection,
        },
        deltaX,
        deltaY,
        minWidth,
        minHeight,
      )

      setRect(toLocalRect(nextRect, snapshot.boundaryRect))
      event.preventDefault()
    },
    [minHeight, minWidth],
  )

  useEffect(() => {
    const reset = () => {
      operationRef.current = null
      setInteraction(null)
      setRect(null)
    }

    window.addEventListener('resize', reset)
    return () => window.removeEventListener('resize', reset)
  }, [])

  const pointerProps = {
    onPointerMove: moveOperation,
    onPointerUp: endOperation,
    onPointerCancel: endOperation,
  }

  return {
    cardRef,
    cardStyle: rect
      ? {
          left: `${rect.left}px`,
          top: `${rect.top}px`,
          width: `${rect.width}px`,
          height: `${rect.height}px`,
        }
      : undefined,
    dragging: interaction === 'move',
    resizing: interaction === 'resize',
    positioned: Boolean(rect),
    handleProps: {
      ...pointerProps,
      onPointerDown: (event) => beginOperation(event, 'move'),
    },
    resizeHandleProps: (direction) => ({
      ...pointerProps,
      'data-resize-direction': direction,
      onKeyDown: resizeWithKeyboard,
      onPointerDown: (event) => beginOperation(event, 'resize'),
    }),
  }
}

function getCardSnapshot(card) {
  const boundary = card?.offsetParent
  if (!card || !boundary) return null

  const cardRect = card.getBoundingClientRect()
  const boundaryRect = boundary.getBoundingClientRect()

  return {
    cardRect,
    boundaryRect,
    bounds: {
      left: Math.max(0, boundaryRect.left),
      top: Math.max(0, boundaryRect.top),
      right: Math.min(window.innerWidth, boundaryRect.right),
      bottom: Math.min(window.innerHeight, boundaryRect.bottom),
    },
  }
}

function moveRect({ cardRect, bounds }, deltaX, deltaY) {
  const width = cardRect.width
  const height = cardRect.height
  const left = clamp(cardRect.left + deltaX, bounds.left, bounds.right - width)
  const top = clamp(cardRect.top + deltaY, bounds.top, bounds.bottom - height)

  return { left, top, width, height }
}

function resizeRect({ cardRect, bounds, direction }, deltaX, deltaY, minWidth, minHeight) {
  let left = cardRect.left
  let right = cardRect.right
  let top = cardRect.top
  let bottom = cardRect.bottom
  const safeMinWidth = Math.min(minWidth, bounds.right - bounds.left)
  const safeMinHeight = Math.min(minHeight, bounds.bottom - bounds.top)

  if (direction.includes('w')) {
    left = clamp(cardRect.left + deltaX, bounds.left, cardRect.right - safeMinWidth)
  }
  if (direction.includes('e')) {
    right = clamp(cardRect.right + deltaX, cardRect.left + safeMinWidth, bounds.right)
  }
  if (direction.includes('n')) {
    top = clamp(cardRect.top + deltaY, bounds.top, cardRect.bottom - safeMinHeight)
  }
  if (direction.includes('s')) {
    bottom = clamp(cardRect.bottom + deltaY, cardRect.top + safeMinHeight, bounds.bottom)
  }

  return { left, top, width: right - left, height: bottom - top }
}

function toLocalRect(rect, boundaryRect) {
  return {
    left: rect.left - boundaryRect.left,
    top: rect.top - boundaryRect.top,
    width: rect.width,
    height: rect.height,
  }
}

function clamp(value, min, max) {
  if (min > max) return min
  return Math.min(max, Math.max(min, value))
}
