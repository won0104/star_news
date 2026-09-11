import { authBrand } from '../../data/auth';
import { deskProps } from '../../data/home';
import { PhotoBackdrop } from '../common/PhotoBackdrop';
import styles from './Auth.module.css';

/**
 * Same sunlit-room photo as the home page, brand centred above a warm paper card.
 * Shared by login and signup.
 *
 * The wordmark in the top-left corner is the way back out — these two screens carry no
 * top bar, so without it the only exits are a successful submit and the browser's back
 * button. It reuses `onBrand`, which both screens already point at home.
 */
export function AuthShell({ title, subtitle, onBrand, children }) {
  return (
    <PhotoBackdrop veil>
      <div className={styles.page}>
        <button type="button" className={styles.homeLink} onClick={onBrand} aria-label="홈으로">
          {authBrand.name}
        </button>

        <div className={styles.inner}>
          <button type="button" className={styles.brand} onClick={onBrand}>
            {authBrand.name}
          </button>
          <p className={styles.tagline}>{authBrand.tagline}</p>

          <div className={styles.cardWrap}>
            <img className={styles.clip} src={deskProps.clipFront} alt="" aria-hidden />

            <section className={styles.card} aria-labelledby="auth-title">
              <div className={styles.paperTexture} aria-hidden />
              <h1 id="auth-title" className={styles.title}>
                {title}
              </h1>
              <p className={styles.subtitle}>{subtitle}</p>
              <div className={styles.content}>{children}</div>
            </section>
          </div>
        </div>
      </div>
    </PhotoBackdrop>
  );
}
export function AuthForm({
  onSubmit,
  children
}) {
  return <form className={styles.form} noValidate onSubmit={onSubmit}>
      {children}
    </form>;
}
export function AuthSubmit({
  children,
  disabled,
  tight
}) {
  return <button type="submit" className={`${styles.submit} ${tight ? styles.submitTight : ''}`} disabled={disabled}>
      {children}
    </button>;
}
export function AuthFormError({
  message
}) {
  return message ? <p className={styles.formError} role="alert">
      {message}
    </p> : null;
}
export function AuthPrompt({
  text,
  action,
  onAction
}) {
  return <p className={styles.prompt}>
      {text}
      <button type="button" className={styles.promptAction} onClick={onAction}>
        {action}
      </button>
    </p>;
}
