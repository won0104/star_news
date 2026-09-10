import { useState } from 'react';
import {
  constellationCopy,
  constellationEvents,
  constellationSlots,
  constellationStart,
  eventPanels,
  panelCopy,
  stars,
} from '../../data/trend';
import { useIsNarrow } from '../../hooks/useIsNarrow';
import { TrendPanel } from './TrendPanel';
import styles from './TrendConstellation.module.css';

/**
 * One event as stars: the centre, the events it connects to, and the entities and
 * statements it is made of.
 *
 * The star's size is the kind and nothing else carries it — centre event, related event,
 * statement, entity, largest to smallest. Each star's text sits in the wall beside it
 * rather than inside it: these stars are light with a soft edge, and text set on that
 * edge is unreadable, which is the whole reason the earlier sticker version put its text
 * inside a hard-edged shape instead.
 *
 * What can be pressed is the model rather than a stage of it. An event is somewhere to
 * go: the centre opens its articles, a related one takes the centre's place and the
 * picture is drawn again around it. An entity or a statement is not — it describes the
 * centre — so those stars are plain images with no handler and no focus stop.
 *
 * The nodes are not positioned; they are dropped into `constellationSlots` in a fixed
 * order, and the slot carries the position, which side its text hangs on and how wide
 * that text may be. That indirection is what makes re-centring safe: the geometry that
 * says no line crosses a label was checked against the slots, so it holds for whichever
 * event is in the middle. It also means every event needs the same shape — see the note
 * in data/trend.js.
 *
 * A narrow field uses fewer slots than a wide one, so the slot set is chosen before the
 * nodes are placed rather than after.
 *
 * Walking closes the panel. It belongs to the centre it was opened from, and carrying it
 * across a re-centre would leave one event's articles beside another event's picture.
 *
 * A group rather than an image, because things inside it can be pressed — `role="img"`
 * takes its descendants out of the accessibility tree, buttons and all. The stars are the
 * decoration, so they carry the aria-hidden; the text is real text and is left to read.
 */

const PANEL_ID = 'trend-articles';

const SIDE_CLASS = {
  above: styles.textAbove,
  below: styles.textBelow,
  left: styles.textLeft,
  right: styles.textRight,
};

const ROLE_CLASS = {
  centre: styles.centreNode,
  related: styles.relatedNode,
  entity: styles.entityNode,
  statement: styles.statementNode,
};

/** The star image each role wears. A related event is the event star, one size down. */
const ROLE_STAR = {
  centre: stars.event,
  related: stars.event,
  entity: stars.entity,
  statement: stars.statement,
};

/**
 * Fill the slots from one event. The order is the slots' order: the centre, then its
 * related events, then its entities, then its statements. An event carrying more than the
 * slots can hold shows the first of each rather than dropping them at random.
 */
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

export function TrendConstellation() {
  const [centreId, setCentreId] = useState(constellationStart);
  const [open, setOpen] = useState(false);
  const narrow = useIsNarrow();

  const nodes = nodesFor(centreId, narrow);
  const centre = nodes[0];
  const at = (node) => (narrow ? node.slot.atNarrow : node.slot.at);
  const side = (node) => (narrow ? node.slot.sideNarrow : node.slot.side);

  const walkTo = (id) => {
    setCentreId(id);
    setOpen(false);
  };

  return (
    <div className={styles.field} role="group" aria-label={panelCopy.fieldLabel}>
      <svg className={styles.links} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        {/* Every satellite hangs off the centre, so the links are the centre's own. */}
        {nodes.slice(1).map((node) => {
          const a = at(centre);
          const b = at(node);
          return (
            <line
              key={`link-${node.id}`}
              className={styles.link}
              x1={a[0]}
              y1={a[1]}
              x2={b[0]}
              y2={b[1]}
            />
          );
        })}
      </svg>

      {nodes.map((node, index) => {
        const { role } = node.slot;
        const isCentre = role === 'centre';
        const isEvent = isCentre || role === 'related';
        const star = <img className={styles.star} src={ROLE_STAR[role]} alt="" aria-hidden />;

        return (
          <div
            key={node.id}
            className={`${styles.node} ${ROLE_CLASS[role]}`}
            style={{
              left: `${at(node)[0]}%`,
              top: `${at(node)[1]}%`,
              // Read outward from the centre, which is first in the list.
              animationDelay: `${index * 110}ms`,
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
                {star}
              </button>
            ) : (
              star
            )}

            <div className={`${styles.text} ${SIDE_CLASS[side(node)]}`}>
              <p className={styles.label}>{node.label}</p>
              <p className={styles.meta}>{node.meta}</p>
            </div>
          </div>
        );
      })}

      <div className={styles.caption}>
        <p className={styles.captionTitle}>{constellationCopy.caption}</p>
        <p className={styles.captionHint}>{constellationCopy.hint}</p>
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
}
