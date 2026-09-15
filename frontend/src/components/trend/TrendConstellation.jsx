import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ambientStars,
  constellationEvents,
  constellationSlots,
  constellationStart,
  eventPanels,
  panelCopy,
  stars,
  trendFigmaAssets,
} from '../../data/trend';
import { useIsNarrow } from '../../hooks/useIsNarrow';
import { TrendPanel } from './TrendPanel';
import styles from './TrendConstellation.module.css';

const PANEL_ID = 'trend-articles';

const ROLE_CLASS = {
  centre: styles.centreNode,
  related: styles.relatedNode,
  entity: styles.entityNode,
  statement: styles.statementNode,
};

const ROLE_STAR = {
  centre: stars.event,
  related: stars.event,
  entity: stars.entity,
  statement: stars.statement,
};

const AMBIENT_ART = {
  event: trendFigmaAssets.relatedLeftSticker,
  entity: trendFigmaAssets.entitySticker,
  statement: trendFigmaAssets.statementSticker,
};

const VISUAL_LAYERS = {
  centre: [{ src: trendFigmaAssets.centreGlow, className: styles.centreGlow }],
  relatedLeft: [
    { src: trendFigmaAssets.relatedLeftGlow, className: styles.relatedLeftGlow },
    { src: trendFigmaAssets.relatedLeftSticker, className: styles.relatedLeftSticker },
  ],
  relatedRight: [
    { src: trendFigmaAssets.relatedRightGlow, className: styles.relatedRightGlow },
    { src: trendFigmaAssets.relatedRightSticker, className: styles.relatedRightSticker },
  ],
  entityLeft: [
    { src: trendFigmaAssets.entityGlow, className: styles.entityGlow },
    { src: trendFigmaAssets.entitySticker, className: styles.entitySticker },
  ],
  entityTop: [],
  statement: [
    { src: trendFigmaAssets.statementGlow, className: styles.statementGlow },
    { src: trendFigmaAssets.statementSticker, className: styles.statementSticker },
  ],
};

function nodesFor(centreId, narrow) {
  const centre = constellationEvents[centreId];
  const slots = constellationSlots.filter((slot) => !(narrow && slot.hideNarrow));
  const bySlot = {
    centre: [{ id: centre.id, label: centre.label, meta: centre.meta, event: centre.id }],
    related: centre.related.map((id) => {
      const event = constellationEvents[id];
      return { id: event.id, label: event.label, meta: event.meta, event: event.id };
    }),
    entity: centre.entities,
    statement: centre.statements,
  };
  const taken = { centre: 0, related: 0, entity: 0, statement: 0 };

  return slots
    .map((slot) => {
      const node = bySlot[slot.role][taken[slot.role]];
      taken[slot.role] += 1;
      return node ? { ...node, slot } : null;
    })
    .filter(Boolean);
}

function StarArt({ role, visual }) {
  return (
    <span className={styles.art} aria-hidden>
      {VISUAL_LAYERS[visual].map((layer) => (
        <img key={layer.src} className={`${styles.layer} ${layer.className}`} src={layer.src} alt="" />
      ))}
      <img className={styles.mobileStar} src={ROLE_STAR[role]} alt="" />
    </span>
  );
}

export function TrendConstellation() {
  const [centreId, setCentreId] = useState(constellationStart);
  const [open, setOpen] = useState(false);
  const [full, setFull] = useState(false);
  const narrow = useIsNarrow();
  const nodes = nodesFor(centreId, narrow);
  const centre = nodes[0];
  const at = (node) => (narrow ? node.slot.atNarrow : node.slot.at);

  const walkTo = (id) => {
    setCentreId(id);
    setOpen(false);
  };

  const enterFull = useCallback(() => {
    setFull(true);
    document.documentElement.requestFullscreen?.().catch(() => {});
  }, []);

  const leaveFull = useCallback(() => {
    setFull(false);
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
  }, []);

  useEffect(() => {
    const onFullscreenChange = () => {
      if (!document.fullscreenElement) setFull(false);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') leaveFull();
    };

    document.addEventListener('fullscreenchange', onFullscreenChange);
    document.addEventListener('keydown', onKeyDown);

    return () => {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
      document.removeEventListener('keydown', onKeyDown);
      if (document.fullscreenElement) {
        document.exitFullscreen?.().catch(() => {});
      }
    };
  }, [leaveFull]);

  const board = (
    <div
      className={`${styles.field} ${full ? styles.fieldFull : ''}`}
      role="group"
      aria-label={panelCopy.fieldLabel}
    >
      <button
        type="button"
        className={styles.fullToggle}
        onClick={full ? leaveFull : enterFull}
        aria-pressed={full}
      >
        <span aria-hidden>{full ? '↙' : '↗'}</span>
        {full ? '전체화면 나가기' : '전체보기'}
      </button>

      <div className={styles.canvas}>
        <img className={styles.relations} src={trendFigmaAssets.relations} alt="" aria-hidden />

        <div className={styles.ambientLayer} aria-hidden>
          {ambientStars.map((star) => (
            <span
              key={star.id}
              className={`${styles.ambientStar} ${styles[`ambient${star.role[0].toUpperCase()}${star.role.slice(1)}`]}`}
              data-star-id={star.id}
              data-related-events={star.events.join(' ')}
              style={{
                left: `${star.at[0]}%`,
                top: `${star.at[1]}%`,
                width: `${star.size / 14.4}cqw`,
                opacity: star.opacity ?? 0.9,
                transform: `translate(-50%, -50%) rotate(${star.rotate}deg)`,
              }}
            >
              <img src={AMBIENT_ART[star.role]} alt="" />
            </span>
          ))}
        </div>

        <svg className={styles.mobileLinks} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {nodes.slice(1).map((node) => (
            <line
              key={`link-${node.id}`}
              x1={at(centre)[0]}
              y1={at(centre)[1]}
              x2={at(node)[0]}
              y2={at(node)[1]}
            />
          ))}
        </svg>

        {nodes.map((node, index) => {
          const { role, visual } = node.slot;
          const isCentre = role === 'centre';
          const isEvent = isCentre || role === 'related';
          const art = <StarArt role={role} visual={visual} />;

          return (
            <div
              key={node.id}
              className={`${styles.node} ${ROLE_CLASS[role]} ${styles[`${visual}Node`]}`}
              style={{
                left: `${at(node)[0]}%`,
                top: `${at(node)[1]}%`,
                animationDelay: `${index * 90}ms`,
              }}
            >
              {isEvent ? (
                <button
                  type="button"
                  className={styles.starButton}
                  aria-expanded={isCentre ? open : undefined}
                  aria-controls={isCentre ? PANEL_ID : undefined}
                  aria-label={
                    isCentre
                      ? `${node.label} — ${panelCopy.open(eventPanels[node.event]?.count)}`
                      : `${node.label} — ${panelCopy.recentre}`
                  }
                  onClick={isCentre ? () => setOpen((was) => !was) : () => walkTo(node.event)}
                >
                  {art}
                </button>
              ) : (
                art
              )}

              <div className={`${styles.text} ${styles[`${visual}Text`]}`}>
                <p className={styles.label}>{node.label}</p>
                <p className={styles.meta}>{node.meta}</p>
              </div>
            </div>
          );
        })}
      </div>

      <TrendPanel
        id={PANEL_ID}
        eventId={centre.event}
        title={centre.label}
        open={open}
        onClose={() => setOpen(false)}
      />
    </div>
  );

  return full ? createPortal(board, document.body) : board;
}
