import { Link } from 'react-router-dom';
import { events } from '../../data/events';
import { recommend } from '../../data/recommend';
import styles from './RecommendPane.module.css';

const BOARD = { width: 1446.576, height: 814 };
const ASSET = '/assets/board/figma';

const NOTES = [
  {
    paper: 'paper-1.png',
    shadow: 'paper-1-shadow.png',
    frame: { x: 43.87, y: 143.21, w: 354.922, h: 354.922 },
    shadowFrame: { x: 39.34, y: 150.01, w: 354.922, h: 354.922 },
    pin: { image: 'pin-yellow.png', cropHeight: '131.93%', frame: { x: 195.29, y: 138.97, w: 37.077, h: 28.02 } },
  },
  {
    paper: 'paper-2.png',
    shadow: 'paper-2-shadow.png',
    frame: { x: 403.04, y: 342.75, w: 289.542, h: 289.542 },
    shadowFrame: { x: 398.79, y: 398.23, w: 289.542, h: 239.728 },
  },
  {
    paper: 'paper-3.png',
    shadow: 'paper-3-shadow.png',
    frame: { x: 48.12, y: 472.1, w: 393.981, h: 315.298 },
    shadowFrame: { x: 42.45, y: 551.63, w: 393.981, h: 241.426 },
  },
  {
    paper: 'paper-square.png',
    shadow: 'paper-square-shadow.png',
    frame: { x: 366.76, y: 100.76, w: 252.802, h: 252.802 },
    shadowFrame: { x: 363.13, y: 105.8, w: 252.802, h: 252.802 },
    pin: { image: 'pin-brass.png', cropHeight: '145.9%', frame: { x: 475.02, y: 114.43, w: 35.884, h: 24.595 } },
  },
  {
    paper: 'paper-5.png',
    shadow: 'paper-5-shadow.png',
    frame: { x: 697.39, y: 161.33, w: 354.922, h: 354.922 },
    shadowFrame: { x: 693.15, y: 168.12, w: 354.922, h: 354.922 },
    pin: { image: 'pin-green.png', cropHeight: '132.77%', frame: { x: 857.3, y: 158.5, w: 44.719, h: 33.681 } },
  },
  {
    paper: 'paper-square.png',
    shadow: 'paper-square-shadow.png',
    frame: { x: 1073.6, y: 83.78, w: 251.272, h: 251.272 },
    shadowFrame: { x: 1068.73, y: 87.52, w: 251.272, h: 251.272 },
    pin: { image: 'pin-red.png', cropHeight: '100%', frame: { x: 1183.92, y: 86.61, w: 40.191, h: 40.191 } },
  },
  {
    paper: 'paper-7.png',
    shadow: 'paper-7-shadow.png',
    frame: { x: 1068.73, y: 338.79, w: 354.922, h: 354.922 },
    shadowFrame: { x: 1063.92, y: 402.75, w: 354.922, h: 299.448 },
  },
  {
    paper: 'paper-8.png',
    shadow: 'paper-8-shadow.png',
    frame: { x: 789.09, y: 495.02, w: 296.334, h: 296.334 },
    shadowFrame: { x: 784.85, y: 502.1, w: 296.334, h: 296.334 },
  },
];

const DECORATIONS = [
  { image: 'tape.png', frame: { x: 619.56, y: 272.28, w: 116.609, h: 33.115 } },
  { image: 'tape-short.png', frame: { x: 1025.13, y: 328.92, w: 120.588, h: 52.861 }, rotate: '10deg' },
  { image: 'leaf.png', frame: { x: 423.42, y: 660.03, w: 88.306, h: 88.306 } },
  { image: 'tape.png', frame: { x: 454.83, y: 704.18, w: 91.488, h: 37.146 }, rotate: '-7.89deg' },
];

const TITLES = [
  {
    image: 'title-pink.png',
    frame: { x: 51.51, y: 48.68, w: 311.618, h: 103.873 },
    fontSize: '20px',
  },
  {
    image: 'title-blue.png',
    frame: { x: 702.49, y: 40.47, w: 335.959, h: 112.081 },
    fontSize: '25px',
  },
];

function placement(frame) {
  return {
    left: `${(frame.x / BOARD.width) * 100}%`,
    top: `${(frame.y / BOARD.height) * 100}%`,
    width: `${(frame.w / BOARD.width) * 100}%`,
    height: `${(frame.h / BOARD.height) * 100}%`,
  };
}

function relativePlacement(frame, parent) {
  return {
    left: `${((frame.x - parent.x) / parent.w) * 100}%`,
    top: `${((frame.y - parent.y) / parent.h) * 100}%`,
    width: `${(frame.w / parent.w) * 100}%`,
    height: `${(frame.h / parent.h) * 100}%`,
  };
}

export function RecommendPane({ settled = true }) {
  const visibleCards = recommend.cards.slice(0, NOTES.length);

  return (
    <section className={styles.page} aria-label={recommend.title}>
      <div className={`${styles.board} ${settled ? styles.boardIn : styles.boardWaiting}`}>
        <img className={styles.boardBase} src={`${ASSET}/board.png`} alt="" draggable="false" />

        {TITLES.map((title) => (
          <div
            key={title.image}
            className={styles.titleTag}
            style={{ ...placement(title.frame), '--title-size': title.fontSize }}
            aria-hidden
          >
            <img src={`${ASSET}/${title.image}`} alt="" draggable="false" />
            <span>나를 위한 추천</span>
          </div>
        ))}

        <ul className={styles.notes}>
          {visibleCards.map((card, index) => {
            const event = events[card.eventId];
            const note = NOTES[index];

            return (
              <li key={card.eventId} className={`${styles.note} ${styles[`note${index + 1}`]}`} style={placement(note.frame)}>
                <img
                  className={styles.paperShadow}
                  src={`${ASSET}/${note.shadow}`}
                  style={relativePlacement(note.shadowFrame, note.frame)}
                  alt=""
                  draggable="false"
                />
                <img className={styles.paperImage} src={`${ASSET}/${note.paper}`} alt="" draggable="false" />

                <Link className={styles.paperContent} to={`/event/${event.id}`} aria-label={`${event.title}. ${card.reason}`}>
                  <p className={styles.reason}>
                    <span className={styles.reasonKey}>{recommend.reasonLabel} · </span>
                    {card.reason}
                  </p>
                  <h3 className={styles.noteTitle}>{event.title}</h3>
                  <p className={styles.noteSummary}>{event.summary}</p>
                  <span className={styles.noteFoot}>
                    <span className={styles.noteTags}>{event.hashtags.slice(0, 2).join('  ')}</span>
                    <span className={styles.noteGo} aria-hidden>자세히 →</span>
                  </span>
                </Link>

                {note.pin && (
                  <span
                    className={styles.fastener}
                    style={relativePlacement(note.pin.frame, note.frame)}
                    aria-hidden
                  >
                    <img
                      src={`${ASSET}/${note.pin.image}`}
                      style={{ height: note.pin.cropHeight }}
                      alt=""
                      draggable="false"
                    />
                  </span>
                )}
              </li>
            );
          })}
        </ul>

        <div className={styles.decorations} aria-hidden>
          {DECORATIONS.map((item, index) => (
            <img
              key={`${item.image}-${index}`}
              className={styles.decoration}
              src={`${ASSET}/${item.image}`}
              style={{ ...placement(item.frame), '--decor-rotate': item.rotate ?? '0deg' }}
              alt=""
              draggable="false"
            />
          ))}
        </div>

        <img
          className={styles.treeShadow}
          src={`${ASSET}/tree-shadow.png`}
          style={placement({ x: 16, y: 5, w: 1414.028, h: 795.886 })}
          alt=""
          draggable="false"
        />
      </div>
    </section>
  );
}
