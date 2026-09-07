import { card, grain } from './assets';
const lg = (left, top) => ({
  src: card.fleckLg,
  left,
  top,
  width: 1.7,
  height: 0.935
});
const sm = (left, top) => ({
  src: card.fleckSm,
  left,
  top,
  width: 1.2,
  height: 0.66
});
const line = (index, left, top, boxWidth, boxHeight, lineWidth, rotate) => ({
  src: grain[index],
  left,
  top,
  boxWidth,
  boxHeight,
  lineWidth,
  rotate
});
export const eventCard = {
  id: 'event',
  kind: 'event',
  frame: {
    left: 742,
    top: 172.9,
    width: 289.115,
    height: 428.085
  },
  shadow: {
    left: 751,
    top: 185.9,
    width: 289.115,
    height: 428.085,
    color: 'rgba(41, 36, 31, 0.1)',
    blur: 7
  },
  width: 286,
  height: 426,
  rotate: -0.42,
  paper: ['#fdf7ec', '#f8f0e2', '#f3e9d8'],
  strongBottomShade: true,
  flecks: [lg(60.4, 78.4), sm(13.4, 17.4)],
  grain: [line(0, 57.4, 306.12, 137.267, 1.917, 137.28, 0.8), line(1, 34.4, 185.38, 114.394, 1.198, 114.4, -0.6), line(2, 11.4, 76.08, 91.511, 1.278, 91.52, 0.8)]
};
export const statementCard = {
  id: 'statement',
  kind: 'statement',
  frame: {
    left: 1081.9,
    top: 294,
    width: 195.089,
    height: 249.393
  },
  shadow: {
    left: 1088.9,
    top: 304,
    width: 195.089,
    height: 249.393,
    color: 'rgba(41, 36, 31, 0.09)',
    blur: 5.5
  },
  width: 192,
  height: 247,
  rotate: 0.72,
  paper: ['#fcf5e8', '#f7eddc', '#f1e5d1'],
  flecks: [sm(89.4, 119.4), lg(42.4, 58.4)],
  grain: [line(3, 74.4, 180.6, 61.437, 0.643, 61.44, -0.6), line(4, 51.4, 105.61, 92.151, 1.287, 92.16, 0.8), line(5, 28.4, 47.06, 76.796, 0.804, 76.8, -0.6)]
};
const miniShadow = (left, top, width, height) => ({
  left,
  top,
  width,
  height,
  color: 'rgba(41, 36, 31, 0.06)',
  blur: 5.5
});

/**
 * Geometry for the six small cards. Both screens pin them at exactly the same spots,
 * so the shells live here and each screen supplies its own content layer.
 */
export const miniShells = [{
  id: 'people',
  kind: 'mini',
  frame: {
    left: 529,
    top: 90.49,
    width: 113.032,
    height: 151.497
  },
  shadow: miniShadow(536, 100.49, 113.032, 151.497),
  width: 111,
  height: 150,
  rotate: -0.78,
  paper: ['#fdf8ee', '#f9f2e5', '#f5ecdd'],
  flecks: [lg(41.4, 52.4), sm(71.4, 99.4)],
  grain: [line(6, 50.4, 107.4, 44.396, 0.62, 44.4, 0.8), line(7, 27.4, 67.53, 35.518, 0.372, 35.52, -0.6), line(8, 45.4, 26.4, 53.275, 0.744, 53.28, 0.8)]
}, {
  id: 'policy',
  kind: 'mini',
  frame: {
    left: 493.67,
    top: 372,
    width: 113.314,
    height: 146.764
  },
  shadow: miniShadow(500.67, 382, 113.314, 146.764),
  width: 111,
  height: 145,
  rotate: 0.92,
  paper: ['#fbf4e7', '#f7eddd', '#f2e5d3'],
  flecks: [sm(70.4, 98.4), lg(23.4, 37.4)],
  grain: [line(9, 26.4, 107.24, 53.277, 0.558, 53.28, -0.6), line(6, 44.4, 61.75, 44.396, 0.62, 44.4, 0.8), line(7, 21.4, 29.13, 35.518, 0.372, 35.52, -0.6)]
}, {
  id: 'region',
  kind: 'mini',
  frame: {
    left: 440,
    top: 658.1,
    width: 113.464,
    height: 146.877
  },
  shadow: miniShadow(447, 668.1, 113.464, 146.877),
  width: 111,
  height: 145,
  rotate: -0.98,
  paper: ['#fcf7ed', '#f8f1e4', '#f4ebdb'],
  flecks: [lg(22.4, 36.4), sm(52.4, 78.4)],
  grain: [line(10, 43.4, 103.8, 35.517, 0.496, 35.52, 0.8), line(9, 20.4, 65.19, 53.277, 0.558, 53.28, -0.6), line(6, 38.4, 25.5, 44.396, 0.62, 44.4, 0.8)]
}, {
  id: 'peace',
  kind: 'mini',
  frame: {
    left: 1371.13,
    top: 154,
    width: 105.849,
    height: 145.038
  },
  shadow: miniShadow(1378.13, 164, 105.849, 145.038),
  width: 103,
  height: 143,
  rotate: 1.15,
  paper: ['#fcf7eb', '#f7efe1', '#f2e8d7'],
  flecks: [sm(67.4, 81.4), lg(20.4, 20.4)],
  grain: [line(11, 43.4, 105.93, 41.198, 0.431, 41.2, -0.6), line(12, 20.4, 60.89, 32.957, 0.46, 32.96, 0.8), line(13, 30.4, 28.62, 49.437, 0.518, 49.44, -0.6)]
}, {
  id: 'impact',
  kind: 'mini',
  frame: {
    left: 1392,
    top: 467.85,
    width: 106.555,
    height: 143.146
  },
  shadow: miniShadow(1399, 477.85, 106.555, 143.146),
  width: 105,
  height: 142,
  rotate: -0.63,
  paper: ['#fcf6eb', '#f7efe1', '#f3e9d8'],
  flecks: [lg(21.4, 24.4), sm(45.4, 63.4)],
  grain: [line(14, 19.4, 101.64, 50.395, 0.704, 50.4, 0.8), line(15, 31.4, 64.02, 41.998, 0.44, 42, -0.6), line(16, 43.4, 24.96, 33.597, 0.469, 33.6, 0.8)]
}, {
  id: 'media',
  kind: 'mini',
  frame: {
    left: 1247.85,
    top: 658,
    width: 113.139,
    height: 146.631
  },
  shadow: miniShadow(1254.85, 668, 113.139, 146.631),
  width: 111,
  height: 145,
  rotate: 0.85,
  paper: ['#fdf7ed', '#f8f1e4', '#f4eadb'],
  flecks: [sm(32.4, 56.4), lg(62.4, 98.4)],
  grain: [line(7, 12.4, 107.43, 35.518, 0.372, 35.52, -0.6), line(8, 30.4, 61.75, 53.275, 0.744, 53.28, 0.8), line(17, 48.4, 29.04, 44.398, 0.465, 44.4, -0.6)]
}];

/** Copy for the two content-bearing cards. */
export const eventContent = {
  type: 'EVENT',
  headlineLines: ['Ceasefire talks resume', 'in Doha'],
  date: '▣  Oct 14, 2024',
  place: '⌖  Doha, Qatar'
};
export const statementContent = {
  type: 'STATEMENT',
  bodyLines: ['We remain open', 'to a negotiated', 'path forward.'],
  source: '— Foreign Ministry'
};

/** Screen 1 ("나의 뉴스 다락방") content for the six mini cards. */
export const atticMiniContent = {
  people: {
    id: 'people',
    glyph: '●●',
    label: 'PEOPLE',
    dot: card.dot.people
  },
  policy: {
    id: 'policy',
    glyph: '▥',
    label: 'POLICY',
    dot: card.dot.people
  },
  region: {
    id: 'region',
    glyph: '◎',
    label: 'REGION',
    dot: card.dot.region
  },
  peace: {
    id: 'peace',
    glyph: '❧',
    label: 'PEACE',
    dot: card.dot.peace
  },
  impact: {
    id: 'impact',
    glyph: '▥',
    label: 'IMPACT',
    dot: card.dot.impact
  },
  media: {
    id: 'media',
    glyph: '▤',
    label: 'MEDIA',
    dot: card.dot.media
  }
};
