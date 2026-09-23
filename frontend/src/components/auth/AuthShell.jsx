import { authBrand, authScene } from '../../data/auth';
import { PhotoBackdrop } from '../common/PhotoBackdrop';
import styles from './Auth.module.css';

/**
 * 로그인·회원가입이 함께 쓰는 껍데기 — 햇살 든 방과, 그 벽에 걸린 클립보드.
 *
 * 예전에는 CSS 카드(테두리·모서리·그림자)에 종이 텍스처를 깔고 클립 사진을 따로 얹었다.
 * 이제 클립보드가 한 장의 일러스트라 카드가 필요 없다: 보드는 그려진 비율을 지키는 그림이고,
 * 폼은 그 종이 자리(authBoard.paper)에 얹힌다. 자리 값은 에셋을 재서 얻었다 — data/auth 참고.
 *
 * 왼쪽 위 워드마크가 나가는 길이다. 이 두 화면은 상단 바가 없어서, 그것이 없으면 나가는 길이
 * 성공한 제출과 브라우저 뒤로가기뿐이다. 두 화면이 이미 홈을 가리키는 `onBrand` 를 쓴다.
 */
export function AuthShell({ title, subtitle, onBrand, children }) {
  return (
    <PhotoBackdrop scene={authScene} veil>
      <div className={styles.page}>
        <button type="button" className={styles.homeLink} onClick={onBrand} aria-label="홈으로">
          <span className={`${styles.wordmark} ${styles.homeMark}`} aria-hidden />
        </button>

        <div className={styles.inner}>
          <button type="button" className={styles.brand} onClick={onBrand}>
            <span className={`${styles.wordmark} ${styles.brandMark}`} aria-hidden />
            <span className={styles.srOnly}>{authBrand.name}</span>
          </button>
          <p className={styles.tagline}>{authBrand.tagline}</p>

          {/*
            보드는 세 조각이다 — 클립이 든 위와 모서리가 든 아래는 그려진 비율을 지키고,
            가운데만 내용만큼 늘어난다. 한 장을 통째로 늘리면 황동 클립이 고무처럼 늘어나고,
            비율을 고정하면 긴 폼(회원가입)이 좁은 화면에서 종이 밖으로 밀린다. Auth.module.css
            의 .boardTop/.boardMid/.boardBot 참고.
          */}
          <div className={styles.board}>
            <div className={styles.boardTop} aria-hidden />
            <div className={styles.boardMid}>
              <section className={styles.paper} aria-labelledby="auth-title">
                <h1 id="auth-title" className={styles.title}>
                  {title}
                </h1>
                <p className={styles.subtitle}>{subtitle}</p>
                <div className={styles.content}>{children}</div>
              </section>
            </div>
            <div className={styles.boardBot} aria-hidden />
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
