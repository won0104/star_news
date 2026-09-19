import { useState } from 'react';
import { withdrawAccount } from '../../api/user';
import { accountPane } from '../../data/settings';
import { endSession, useSession } from '../../store/session';
import { closeSettings } from '../../store/settings';
import { PaneHead, SectionHead } from './PaneChrome';
import paneStyles from './PaneChrome.module.css';
import styles from './AccountPane.module.css';

/**
 * 계정 — 누구로 로그인했는지, 그리고 회원 탈퇴.
 *
 * 탈퇴는 두 단계다. 첫 버튼은 그 자리에 비밀번호 칸을 펼치기만 하고, 두 번째 버튼(문구가
 * 다르다: "탈퇴하기")이 실제로 `DELETE /users/me` 를 보낸다. 되돌릴 수 없는 일이라 모달을
 * 띄우는 대신 같은 자리에서 펼치는 쪽을 택했다 — 무엇을 지우는지 적힌 설명 바로 아래에서
 * 확인하게 되고, 취소하면 아무 일도 없던 자리로 접힌다.
 *
 * 서버가 비밀번호를 다시 묻는 것은 API 계약이다(비밀번호 없으면 400, 틀리면 401). 그래서
 * 이 화면은 비밀번호를 검증하지 않고 비어 있는지만 본다 — 맞는지는 서버가 안다.
 *
 * 성공하면 서버가 refresh 쿠키를 만료시키고, 여기서는 세션을 버리고 첫 화면으로 간다.
 * 라우터 밖에서 렌더되는 오버레이라 `useNavigate` 대신 페이지를 다시 불러온다. 메모리에
 * 남은 상태가 전부 사라지는 것이 오히려 맞다 — 그 계정은 더 이상 없다.
 */
export function AccountPane() {
  const account = useSession();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [state, setState] = useState('idle'); // idle | working | done
  const [error, setError] = useState(null);

  const cancel = () => {
    setOpen(false);
    setPassword('');
    setError(null);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (state !== 'idle') return;
    if (!password) {
      setError(accountPane.passwordRequired);
      return;
    }

    setState('working');
    setError(null);
    try {
      await withdrawAccount(password);
      setState('done');
      // 문구를 한 번 읽을 시간만 주고 떠난다. 세션은 먼저 버린다 — 그 사이 다른 요청이
      // 죽은 토큰을 들고 나가지 않게.
      endSession();
      window.setTimeout(() => {
        closeSettings();
        window.location.assign('/');
      }, 900);
    } catch (failure) {
      setState('idle');
      const code = failure?.code;
      if (code === 'INVALID_CREDENTIALS') {
        setError(accountPane.wrongPassword);
        setPassword('');
      } else if (code === 'USER_DELETED') {
        setError(accountPane.alreadyDeleted);
        window.setTimeout(() => {
          endSession();
          closeSettings();
        }, 900);
      } else if (failure?.status === 401) {
        setError(accountPane.sessionExpired);
      } else {
        setError(accountPane.failed);
      }
    }
  };

  return (
    <>
      <PaneHead eyebrow={accountPane.eyebrow} title={accountPane.title} blurb={accountPane.blurb} />

      <SectionHead label={accountPane.whoLabel} />
      <dl className={styles.who}>
        <div>
          <dt>{accountPane.idLabel}</dt>
          <dd>{account?.user?.loginId ?? '—'}</dd>
        </div>
        <div>
          <dt>{accountPane.nicknameLabel}</dt>
          <dd>{account?.user?.nickname ?? '—'}</dd>
        </div>
      </dl>

      <SectionHead label={accountPane.withdrawLabel} hint={accountPane.withdrawHint} />
      <section className={styles.danger} aria-labelledby="withdraw-title">
        <h4 id="withdraw-title" className={styles.dangerTitle}>
          {accountPane.withdrawLabel}
        </h4>
        <ul className={styles.dangerList}>
          {accountPane.withdrawBlurb.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>

        {!open ? (
          <div className={styles.dangerActions}>
            <button type="button" className={styles.dangerButton} onClick={() => setOpen(true)}>
              {accountPane.withdrawOpen}
            </button>
          </div>
        ) : (
          <form className={styles.confirm} onSubmit={submit} noValidate>
            <label className={styles.field}>
              <span>{accountPane.passwordLabel}</span>
              <input
                type="password"
                className={styles.input}
                placeholder={accountPane.passwordPlaceholder}
                autoComplete="current-password"
                autoFocus
                value={password}
                disabled={state !== 'idle'}
                aria-invalid={error ? 'true' : undefined}
                aria-describedby={error ? 'withdraw-error' : undefined}
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (error) setError(null);
                }}
              />
            </label>

            <p
              id="withdraw-error"
              className={`${styles.message} ${state === 'done' ? styles.messageDone : ''}`}
              role={error ? 'alert' : 'status'}
            >
              {state === 'done' ? accountPane.done : state === 'working' ? accountPane.withdrawing : error}
            </p>

            <div className={styles.dangerActions}>
              <button
                type="button"
                className={paneStyles.primary}
                onClick={cancel}
                disabled={state !== 'idle'}
              >
                {accountPane.withdrawCancel}
              </button>
              <button
                type="submit"
                className={`${styles.dangerButton} ${styles.dangerButtonSolid}`}
                disabled={state !== 'idle'}
              >
                {accountPane.withdrawConfirm}
              </button>
            </div>
          </form>
        )}
      </section>
    </>
  );
}
