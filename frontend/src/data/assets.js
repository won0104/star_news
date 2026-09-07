/**
 * Every asset here was exported from the Figma node and downloaded into /public/assets.
 * Keep the paths in one place so a re-export only touches this file.
 */
const base = '/assets';
export const photo = {
  backdrop: `${base}/photo/backdrop-attic.png`,
  eventThumb: `${base}/photo/event-thumb.png`
};
export const yarn = {
  redShadow: `${base}/yarn/red-shadow.svg`,
  red: `${base}/yarn/red.svg`,
  redFiber: `${base}/yarn/red-fiber.svg`,
  goldShadow: `${base}/yarn/gold-shadow.svg`,
  gold: `${base}/yarn/gold.svg`,
  goldFiber: `${base}/yarn/gold-fiber.svg`,
  tealShadow: `${base}/yarn/teal-shadow.svg`,
  teal: `${base}/yarn/teal.svg`,
  tealFiber: `${base}/yarn/teal-fiber.svg`,
  blueShadow: `${base}/yarn/blue-shadow.svg`,
  blue: `${base}/yarn/blue.svg`,
  blueFiber: `${base}/yarn/blue-fiber.svg`,
  greenShadow: `${base}/yarn/green-shadow.svg`,
  green: `${base}/yarn/green.svg`,
  greenFiber: `${base}/yarn/green-fiber.svg`
};
export const atmosphere = Array.from({
  length: 7
}, (_, i) => `${base}/paper/atmos-${i + 1}.svg`);
export const card = {
  fleckLg: `${base}/card/fleck-lg.svg`,
  fleckSm: `${base}/card/fleck-sm.svg`,
  pin: `${base}/card/brass-pin.svg`,
  pinContactShadow: `${base}/card/pin-contact-shadow.svg`,
  pinHighlight: `${base}/card/pin-highlight.svg`,
  footerRule: `${base}/card/footer-rule.svg`,
  dot: {
    event: `${base}/card/dot-event.svg`,
    statement: `${base}/card/dot-statement.svg`,
    people: `${base}/card/dot-people.svg`,
    region: `${base}/card/dot-region.svg`,
    peace: `${base}/card/dot-peace.svg`,
    impact: `${base}/card/dot-impact.svg`,
    media: `${base}/card/dot-media.svg`
  }
};

/** Hairline paper-grain strokes, indexed exactly as exported (grain-0 … grain-17). */
export const grain = Array.from({
  length: 18
}, (_, i) => `${base}/card/grain-${i}.svg`);

/** Screen 2 ("그래프 탐색") — assets that exist only on the graph view. */
export const graph = {
  bankRoof: `${base}/graph/bank-roof.svg`,
  dot: {
    entityBank: `${base}/graph/dot-entity-bank.svg`,
    entityCommittee: `${base}/graph/dot-entity-committee.svg`,
    relatedEvent: `${base}/graph/dot-related-event.svg`,
    topic: `${base}/graph/dot-topic.svg`,
    time: `${base}/graph/dot-time.svg`,
    story: `${base}/graph/dot-story.svg`
  },
  relationDot: {
    entity: `${base}/graph/rel-dot-entity.svg`,
    statement: `${base}/graph/rel-dot-statement.svg`,
    topic: `${base}/graph/rel-dot-topic.svg`,
    event: `${base}/graph/rel-dot-event.svg`
  },
  hanger: {
    eventCenter: `${base}/graph/hanger-event-center.svg`,
    eventCenterKnot: `${base}/graph/hanger-event-center-knot.svg`,
    statement: `${base}/graph/hanger-statement.svg`,
    statementKnot: `${base}/graph/hanger-statement-knot.svg`,
    entityBank: `${base}/graph/hanger-entity-bank.svg`,
    entityBankKnot: `${base}/graph/hanger-entity-bank-knot.svg`,
    entityCommittee: `${base}/graph/hanger-entity-committee.svg`,
    entityCommitteeKnot: `${base}/graph/hanger-entity-committee-knot.svg`,
    relatedEvent: `${base}/graph/hanger-related-event.svg`,
    relatedEventKnot: `${base}/graph/hanger-related-event-knot.svg`,
    topic: `${base}/graph/hanger-topic.svg`,
    topicKnot: `${base}/graph/hanger-topic-knot.svg`,
    time: `${base}/graph/hanger-time.svg`,
    timeKnot: `${base}/graph/hanger-time-knot.svg`,
    story: `${base}/graph/hanger-story.svg`,
    storyKnot: `${base}/graph/hanger-story-knot.svg`
  }
};
