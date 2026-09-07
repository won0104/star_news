import { atmosphere, yarn } from './assets';
export const SCENE_WIDTH = 1672;
export const SCENE_HEIGHT = 941;

/** Yarn strands, back-to-front: each colour is a shadow pass followed by the strand itself. */
export const yarnStrands = [{
  src: yarn.redShadow,
  left: 463.8,
  top: -8.8,
  width: 1223,
  height: 671.476,
  inset: '-0.57% -0.31%'
}, {
  src: yarn.red,
  left: 462,
  top: -12,
  width: 1223,
  height: 671.476,
  inset: '-0.34% -0.31% -0.79% -0.31%'
}, {
  src: yarn.goldShadow,
  left: 426.8,
  top: -12.8,
  width: 1261,
  height: 291.896,
  inset: '-1.13% -0.26%'
}, {
  src: yarn.gold,
  left: 425,
  top: -16,
  width: 1261,
  height: 291.896,
  inset: '-0.62% -0.26% -1.64% -0.26%'
}, {
  src: yarn.tealShadow,
  left: 387.8,
  top: -18.8,
  width: 1299,
  height: 709,
  inset: '-0.49% -0.27%'
}, {
  src: yarn.teal,
  left: 386,
  top: -22,
  width: 1299,
  height: 709,
  inset: '-0.28% -0.27% -0.71% -0.27%'
}, {
  src: yarn.blueShadow,
  left: 364.8,
  top: 199.2,
  width: 1323,
  height: 176,
  inset: '-1.82% -0.24%'
}, {
  src: yarn.blue,
  left: 363,
  top: 196,
  width: 1323,
  height: 176,
  inset: '-0.97% -0.24% -2.67% -0.24%'
}, {
  src: yarn.greenShadow,
  left: 521.8,
  top: 129.2,
  width: 1164,
  height: 222,
  inset: '-1.44% -0.27%'
}, {
  src: yarn.green,
  left: 520,
  top: 126,
  width: 1164,
  height: 222,
  inset: '-0.77% -0.27% -2.12% -0.27%'
}];

/** Thin light passes drawn on top of the depth papers so the yarn reads as fibre. */
export const yarnFibers = [{
  src: yarn.redFiber,
  left: 462,
  top: -12.7,
  width: 1223,
  height: 671.476,
  inset: '-0.1% 0'
}, {
  src: yarn.goldFiber,
  left: 425,
  top: -16.7,
  width: 1261,
  height: 291.896,
  inset: '-0.18% 0'
}, {
  src: yarn.tealFiber,
  left: 386,
  top: -22.7,
  width: 1299,
  height: 709,
  inset: '0'
}, {
  src: yarn.blueFiber,
  left: 363,
  top: 195.3,
  width: 1323,
  height: 176,
  inset: '-0.28% 0'
}, {
  src: yarn.greenFiber,
  left: 520,
  top: 125.3,
  width: 1164,
  height: 222,
  inset: '-0.22% 0'
}];

/** Out-of-focus paper shapes sitting behind the yarn — pure CSS, no artwork. */
export const depthPapers = [{
  left: 364.76,
  top: 70,
  width: 91.205,
  height: 118.412,
  innerWidth: 88,
  innerHeight: 116,
  rotate: 1.6,
  blur: 1.6,
  opacity: 0.11
}, {
  left: 452,
  top: 300.27,
  width: 92.21,
  height: 117.706,
  innerWidth: 90,
  innerHeight: 116,
  rotate: -1.1,
  blur: 1.95,
  opacity: 0.13
}, {
  left: 637.41,
  top: 624,
  width: 89.583,
  height: 115.218,
  innerWidth: 88,
  innerHeight: 114,
  rotate: 0.8,
  blur: 2.3,
  opacity: 0.1
}, {
  left: 1116,
  top: 93.64,
  width: 93.006,
  height: 118.316,
  innerWidth: 90,
  innerHeight: 116,
  rotate: -1.5,
  blur: 1.6,
  opacity: 0.12
}, {
  left: 1454.61,
  top: 221,
  width: 90.368,
  height: 115.818,
  innerWidth: 88,
  innerHeight: 114,
  rotate: 1.2,
  blur: 1.95,
  opacity: 0.09
}, {
  left: 1066,
  top: 666.55,
  width: 93.842,
  height: 119.431,
  innerWidth: 92,
  innerHeight: 118,
  rotate: -0.9,
  blur: 2.3,
  opacity: 0.1
}, {
  left: 1294.5,
  top: 632,
  width: 95.46,
  height: 120.677,
  innerWidth: 92,
  innerHeight: 118,
  rotate: 1.7,
  blur: 1.6,
  opacity: 0.08
}];

/** Faint pinned papers layered above the cards to suggest depth beyond the focus plane. */
export const atmospherePapers = [{
  src: atmosphere[0],
  left: 320.05,
  top: 78,
  width: 85.942,
  height: 113.449,
  innerWidth: 84,
  innerHeight: 112,
  rotate: 1,
  inset: '-3.57% -9.52% -11.61% -9.52%'
}, {
  src: atmosphere[1],
  left: 400,
  top: 290.07,
  width: 94.493,
  height: 121.9,
  innerWidth: 92,
  innerHeight: 120,
  rotate: -1.2,
  inset: '-3.33% -8.7% -10.83% -8.7%'
}, {
  src: atmosphere[2],
  left: 610.3,
  top: 520,
  width: 95.694,
  height: 123.301,
  innerWidth: 94,
  innerHeight: 122,
  rotate: 0.8,
  inset: '-2.87% -8.51% -10.66% -8.51%'
}, {
  src: atmosphere[3],
  left: 1110,
  top: 60.74,
  width: 91.611,
  height: 117.245,
  innerWidth: 90,
  innerHeight: 116,
  rotate: -0.8,
  inset: '-3.88% -8.89% -11.21% -8.89%'
}, {
  src: atmosphere[4],
  left: 1487.94,
  top: 108,
  width: 94.045,
  height: 119.588,
  innerWidth: 92,
  innerHeight: 118,
  rotate: 1,
  inset: '-3.39% -8.7% -11.02% -8.7%'
}, {
  src: atmosphere[5],
  left: 1515,
  top: 356.99,
  width: 97.272,
  height: 122.999,
  innerWidth: 96,
  innerHeight: 122,
  rotate: -0.6,
  inset: '-3.69% -8.33% -10.66% -8.33%'
}, {
  src: atmosphere[6],
  left: 1083.44,
  top: 690,
  width: 89.555,
  height: 113.218,
  innerWidth: 88,
  innerHeight: 112,
  rotate: 0.8,
  inset: '-4.46% -9.09% -11.61% -9.09%'
}];
export const hero = {
  titleLines: ['The bigger', 'picture, together.'],
  subtitleLines: ['Explore how news events,', 'people, and ideas are connected.']
};
export const navItems = [{
  id: 'people',
  label: '◯   People',
  top: 383
}, {
  id: 'places',
  label: '⌖   Places',
  top: 442
}, {
  id: 'topics',
  label: '▱   Topics',
  top: 501
}, {
  id: 'timeline',
  label: '◷   Timeline',
  top: 560
}];
export const activeNav = {
  label: '⌘   Explore'
};
export const searchPlaceholder = '⌕   Search the news graph...';
export const footerMotto = ['NEWS', 'IN CONTEXT', 'FOR A BRIGHTER', 'TOMORROW'];
export const hints = [{
  id: 'related',
  left: 316,
  top: 510,
  width: 150,
  opacity: 0.55,
  lines: ['Related', 'stories slide in', '→']
}, {
  id: 'tuck',
  left: 1518,
  top: 478,
  width: 125,
  opacity: 0.55,
  lines: ['Tuck away', 'to declutter.']
}, {
  id: 'more',
  left: 766,
  top: 760,
  width: 180,
  opacity: 0.47,
  lines: ['More connections', 'appear as you explore', '↓']
}];
export const tagline = {
  left: 1438,
  top: 815,
  width: 190,
  opacity: 0.62,
  lines: ['DIFFERENT STORIES.', 'A MORE COMPLETE WORLD.']
};
