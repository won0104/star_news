import { card } from '../../data/assets';
import styles from './BrassPin.module.css';

/**
 * The pin cluster is identical on every card and always centred on the card's top edge,
 * so its parts are derived from one anchor rather than stored per card.
 */
export function BrassPin({
  cardWidth
}) {
  const anchor = cardWidth / 2 - 9.1;
  return <>
      <div className={styles.contactBox} style={{
      left: anchor + 2.5,
      top: -2.1
    }}>
        <div className={styles.contactBleed}>
          <img className={styles.art} src={card.pinContactShadow} alt="" />
        </div>
      </div>
      <div className={styles.pinBox} style={{
      left: anchor,
      top: -14.6
    }}>
        <div className={styles.pinBleed}>
          <img className={styles.art} src={card.pin} alt="" />
        </div>
      </div>
      <div className={styles.clip} style={{
      left: anchor - 1.5,
      top: -1.6
    }} />
      <img className={styles.highlight} style={{
      left: anchor + 3.2,
      top: -11.8
    }} src={card.pinHighlight} alt="" />
      <div className={styles.clipTop} style={{
      left: anchor + 1,
      top: 0.6
    }} />
    </>;
}
