import styles from './Hints.module.css';
/**
 * Faint wayfinding copy plus the closing tagline. The attic view sets these in the
 * display serif; the graph view uses the Korean sans at a smaller size.
 */
export function Hints({
  hints,
  tagline,
  variant
}) {
  const hintFont = variant === 'attic' ? styles.serif : styles.sans;
  const taglineFont = variant === 'attic' ? styles.taglineSerifScene : styles.taglineSansScene;
  return <>
      {hints.map(hint => <div key={hint.id} className={`${styles.hint} ${hintFont}`} style={{
      left: hint.left,
      top: hint.top,
      width: hint.width,
      opacity: hint.opacity
    }}>
          {hint.lines.map(line => <p key={line}>{line}</p>)}
        </div>)}

      <div className={`${styles.tagline} ${taglineFont}`} style={{
      left: tagline.left,
      top: tagline.top,
      width: tagline.width,
      opacity: tagline.opacity
    }}>
        {tagline.lines.map(line => <p key={line}>{line}</p>)}
      </div>
    </>;
}
