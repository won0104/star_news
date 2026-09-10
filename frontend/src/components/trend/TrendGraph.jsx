import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { FIELD, events, relations, trendCopy } from '../../data/trend';
import styles from './TrendGraph.module.css';

/**
 * 주요 트렌드 — events as star stickers, event to event.
 *
 * The star carries the event: an actor and a two-line phrase are set inside the shape,
 * so a node reads as something that happened. Both ends of every line are events, not
 * entities, and the whole sentence is read in the caption under the field.
 *
 * One event is centred and whatever it relates to sits around it; clicking a
 * surrounding star re-centres on it, so the graph is walked outward rather than piled
 * onto one screen. The trail sits in the field's own top-left corner, opposite the
 * fullscreen button, so the path walked so far stays with the stars — including in
 * fullscreen, where there is nothing above the field to put it in.
 *
 * That is geometry rather than preference — a star wide enough to hold
 * legible text is about 320px across on this field and five of those fit where nine
 * collide, and at a size where nine fit the text overflows the star by roughly double.
 * The trail above the field keeps the path visible, so walking still reads as expanding.
 *
 * Fullscreen is worth having here because the field's height follows its width — at
 * 1440x960 it is the tallest thing on the page and does not fit under the chrome. Going
 * full screen both covers the chrome and lets the graph fit the viewport instead of
 * overflowing it. It is a fixed overlay first and a native fullscreen request second:
 * the overlay always works and is what hides the app's own bars, and the native request
 * is a bonus that takes the browser's chrome with it when the browser allows it.
 *
 * Portalled to the body while it is open, and this is not optional: ViewPane's .page
 * is `position: relative; z-index: 1`, which makes a stacking context, and no z-index
 * inside one can rise above what sits outside it. Left in place the overlay competed
 * only with its own siblings and the top bar (z-index 10) stayed painted over it.
 */

/**
 * Where the related stars go, by how many there are. Balanced per count rather than
 * taking the first N of one fixed ring, which would leave a lopsided gap.
 */
const SLOTS = {
  1: [[76, 26]],
  2: [
    [76, 26],
    [24, 74],
  ],
  3: [
    [78, 26],
    [22, 30],
    [50, 82],
  ],
  4: [
    [78, 22],
    [22, 24],
    [23, 78],
    [77, 76],
  ],
};

const CENTRE = [50, 50];
const R_CENTRE = 185;
const R_RELATED = 160;

/**
 * A five-pointed star, outer radius `r`, inner radius a full 0.68 of it. A spikier star
 * looks more like a star and holds no text; the interior is the point of this shape.
 * Its rounded points come from stroking it in its own colour, in the stylesheet.
 */
function starPoints(r) {
  const inner = r * 0.68;
  return Array.from({ length: 10 }, (_, i) => {
    const radius = i % 2 === 0 ? r : inner;
    const angle = ((-90 + i * 36) * Math.PI) / 180;
    return `${(radius * Math.cos(angle)).toFixed(1)},${(radius * Math.sin(angle)).toFixed(1)}`;
  }).join(' ');
}

export function TrendGraph() {
  const [trail, setTrail] = useState([trendCopy.start]);
  const [full, setFull] = useState(false);
  const centreId = trail[trail.length - 1];

  /**
   * The request goes to <html>, not to this component's own element, and that matters.
   * Opening also portals this subtree to the body, so the node the request was made on
   * is torn out of the DOM the moment it succeeds — the browser stays full screen but
   * loses `document.fullscreenElement`, and then nothing can exit it. <html> is never
   * removed. It also has to stay in the click handler rather than move into an effect:
   * requestFullscreen needs the user gesture, and an effect runs too late to have it.
   */
  const enter = () => {
    setFull(true);
    // Best effort: the overlay is what actually hides the app's own bars, so a refusal
    // here is not a failure and there is nothing to tell the user about.
    document.documentElement.requestFullscreen?.().catch(() => {});
  };

  const leave = () => {
    setFull(false);
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  };

  useEffect(() => {
    if (!full) return undefined;

    // Esc exits native fullscreen on its own, but not the overlay when the native
    // request was refused, so it is handled either way.
    const onKeyDown = (event) => {
      if (event.key === 'Escape') leave();
    };
    // And if the browser drops out of fullscreen by any other route, follow it.
    const onChange = () => {
      if (!document.fullscreenElement) setFull(false);
    };

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('fullscreenchange', onChange);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('fullscreenchange', onChange);
      // Leaving this screen while full must not strand the browser full screen.
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    };
  }, [full]);

  const { byId, neighbours } = useMemo(() => {
    const map = new Map(events.map((event) => [event.id, event]));
    const adjacency = new Map(events.map((event) => [event.id, []]));
    relations.forEach(({ from, to, label }) => {
      adjacency.get(from).push({ id: to, label });
      adjacency.get(to).push({ id: from, label });
    });
    return { byId: map, neighbours: adjacency };
  }, []);

  const centre = byId.get(centreId);
  const related = neighbours.get(centreId);
  const shown = related.slice(0, 4);
  const notShown = related.length - shown.length;
  const slots = SLOTS[shown.length] ?? SLOTS[4];

  const walkTo = (id) => {
    // Stepping onto somewhere already walked rewinds the trail rather than looping it.
    const seen = trail.indexOf(id);
    setTrail(seen === -1 ? [...trail, id] : trail.slice(0, seen + 1));
  };

  const at = ([x, y]) => ({ x: (x / 100) * FIELD.width, y: (y / 100) * FIELD.height });
  const centrePoint = at(CENTRE);

  const star = (event, point, radius, { isCentre = false, label } = {}) => (
    <g
      key={event.id}
      className={`${styles.node} ${isCentre ? styles.nodeCentre : ''}`}
      transform={`translate(${point.x} ${point.y})`}
      role={isCentre ? undefined : 'button'}
      tabIndex={isCentre ? undefined : 0}
      aria-label={isCentre ? undefined : `${event.text} — ${label} 관계`}
      onClick={isCentre ? undefined : () => walkTo(event.id)}
      onKeyDown={
        isCentre
          ? undefined
          : (keyEvent) => {
              if (keyEvent.key === 'Enter' || keyEvent.key === ' ') {
                keyEvent.preventDefault();
                walkTo(event.id);
              }
            }
      }
    >
      <polygon className={styles.sticker} points={starPoints(radius)} />
      <text className={styles.actor} y={-radius * 0.3} textAnchor="middle">
        {event.actor}
      </text>
      {event.lines.map((line, index) => (
        <text
          key={line}
          className={styles.line}
          y={-radius * 0.04 + index * (isCentre ? 31 : 28)}
          textAnchor="middle"
        >
          {line}
        </text>
      ))}
      <text className={styles.date} y={radius * 0.44} textAnchor="middle">
        {event.date}
      </text>
    </g>
  );

  const board = (
    <div className={`${styles.wrap} ${full ? styles.wrapFull : ''}`}>
      {!full && <p className={styles.blurb}>{trendCopy.blurb}</p>}

      <div className={styles.field}>
        <div className={styles.trail}>
          <span className={styles.trailLabel}>{trendCopy.trailLabel}</span>
          {trail.map((id, index) => (
            <button
              key={id}
              type="button"
              className={`${styles.crumb} ${index === trail.length - 1 ? styles.crumbNow : ''}`}
              aria-current={index === trail.length - 1 ? 'true' : undefined}
              onClick={() => walkTo(id)}
            >
              {byId.get(id).actor}
            </button>
          ))}
        </div>

        <button
          type="button"
          className={styles.fullToggle}
          onClick={full ? leave : enter}
          aria-pressed={full}
        >
          {full ? trendCopy.exitFull : trendCopy.enterFull}
        </button>

        <svg
          className={`${styles.canvas} ${full ? styles.canvasFull : ''}`}
          viewBox={`0 0 ${FIELD.width} ${FIELD.height}`}
          role="img"
          aria-label={`${centre.text} — ${trendCopy.relatedLabel(related.length)}`}
        >
          {/* Lines first, so each star sits on top of its own ends. */}
          {shown.map((edge, index) => {
            const point = at(slots[index]);
            return (
              <g key={`link-${edge.id}`}>
                <line
                  className={styles.link}
                  x1={centrePoint.x}
                  y1={centrePoint.y}
                  x2={point.x}
                  y2={point.y}
                />
                <text
                  className={styles.linkLabel}
                  x={(centrePoint.x + point.x) / 2}
                  y={(centrePoint.y + point.y) / 2 - 8}
                  textAnchor="middle"
                >
                  {edge.label}
                </text>
              </g>
            );
          })}

          {star(centre, centrePoint, R_CENTRE, { isCentre: true })}
          {shown.map((edge, index) =>
            star(byId.get(edge.id), at(slots[index]), R_RELATED, { label: edge.label }),
          )}
        </svg>
      </div>

      <div className={styles.caption}>
        <p className={styles.captionMeta}>
          <span className={styles.captionBadge}>{trendCopy.centreBadge}</span>
          {centre.actor}
          <span className={styles.captionDate}>{centre.date}</span>
          <span className={styles.captionCount}>
            {trendCopy.relatedLabel(related.length)}
            {notShown > 0 && ` · ${notShown}개는 자리가 없어 표시하지 않았습니다`}
          </span>
        </p>
        <p className={styles.captionText}>{centre.text}</p>
        {trail.length > 1 && (
          <button
            type="button"
            className={styles.resetButton}
            onClick={() => setTrail([trendCopy.start])}
          >
            {trendCopy.reset}
          </button>
        )}
      </div>
    </div>
  );

  return full ? createPortal(board, document.body) : board;
}
