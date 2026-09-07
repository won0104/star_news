import styles from './Auth.module.css';
const TONE_CLASS = {
  success: styles.messageSuccess,
  error: styles.messageError,
  muted: styles.messageMuted
};
export function AuthField({
  id,
  label,
  error,
  message,
  trailing,
  ...input
}) {
  const shown = error ? {
    tone: 'error',
    text: error
  } : message ?? null;
  const messageId = `${id}-message`;
  return <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <div className={styles.inputRow}>
        <input id={id} className={`${styles.input} ${error ? styles.inputError : ''}`} aria-invalid={error ? true : undefined} aria-describedby={shown ? messageId : undefined} {...input} />
        {trailing}
      </div>
      {shown && <p id={messageId} className={`${styles.message} ${TONE_CLASS[shown.tone]}`}>
          {shown.text}
        </p>}
    </div>;
}
