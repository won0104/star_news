import { useState } from 'react';
import { changeEmail, changePassword } from '../../api/auth';
import { accountPane } from '../../data/settings';
import { validateConfirm, validateEmail, validatePassword } from '../../utils/validation';
import { AuthField } from '../auth/AuthField';
import { PaneHead, SectionHead } from './PaneChrome';
import paneStyles from './PaneChrome.module.css';
import styles from './AccountPane.module.css';

/**
 * 계정 설정 — Figma V3 / Overlay / Settings / Account.
 *
 * Two changes, two independent forms: submitting one must not clear or block the other,
 * which is why each keeps its own busy flag and its own result line.
 *
 * The fields are <AuthField> and the rules are utils/validation — the same component
 * and the same validators the sign-up screen uses, so "8자 이상" means the same thing
 * in both places and the error wording cannot drift apart.
 */
export function AccountPane() {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState(null);
  const [emailDone, setEmailDone] = useState(false);
  const [emailBusy, setEmailBusy] = useState(false);

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [passwordDone, setPasswordDone] = useState(false);
  const [passwordBusy, setPasswordBusy] = useState(false);

  const submitEmail = async (event) => {
    event.preventDefault();
    const error = validateEmail(email);
    setEmailError(error);
    setEmailDone(false);
    if (error) return;

    setEmailBusy(true);
    try {
      await changeEmail(email.trim());
      setEmailDone(true);
      setEmail('');
    } catch {
      setEmailError(accountPane.failed);
    } finally {
      setEmailBusy(false);
    }
  };

  const submitPassword = async (event) => {
    event.preventDefault();
    const nextError = validatePassword(next);
    const nextErrors = {
      current: current ? null : accountPane.currentRequired,
      next: nextError ?? (next === current ? accountPane.sameAsCurrent : null),
      // No point reporting a mismatch against a password that is itself invalid.
      confirm: nextError ? null : validateConfirm(next, confirm),
    };
    setErrors(nextErrors);
    setPasswordDone(false);
    if (Object.values(nextErrors).some(Boolean)) return;

    setPasswordBusy(true);
    try {
      await changePassword({ current, next });
      setPasswordDone(true);
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch {
      setErrors({ current: accountPane.failed });
    } finally {
      setPasswordBusy(false);
    }
  };

  const clear = (key) => {
    if (errors[key]) setErrors((previous) => ({ ...previous, [key]: null }));
  };

  return (
    <>
      <PaneHead
        eyebrow={accountPane.eyebrow}
        title={accountPane.title}
        blurb={accountPane.blurb}
      />

      <SectionHead label={accountPane.emailLabel} hint={accountPane.emailHint} />

      <form className={styles.form} onSubmit={submitEmail} noValidate>
        <AuthField
          id="settings-email"
          type="email"
          label={accountPane.emailField}
          placeholder={accountPane.emailPlaceholder}
          autoComplete="email"
          value={email}
          error={emailError}
          message={emailDone ? { tone: 'success', text: accountPane.emailDone } : null}
          onChange={(event) => {
            setEmail(event.target.value);
            setEmailError(null);
            setEmailDone(false);
          }}
        />
        <div className={styles.actions}>
          <button type="submit" className={paneStyles.primary} disabled={emailBusy}>
            {accountPane.emailSubmit}
          </button>
        </div>
      </form>

      <SectionHead label={accountPane.passwordLabel} hint={accountPane.passwordHint} />

      <form className={styles.form} onSubmit={submitPassword} noValidate>
        <AuthField
          id="settings-current-password"
          type="password"
          label={accountPane.currentField}
          placeholder={accountPane.currentPlaceholder}
          autoComplete="current-password"
          value={current}
          error={errors.current}
          onChange={(event) => {
            setCurrent(event.target.value);
            clear('current');
            setPasswordDone(false);
          }}
        />
        <AuthField
          id="settings-next-password"
          type="password"
          label={accountPane.nextField}
          placeholder={accountPane.nextPlaceholder}
          autoComplete="new-password"
          value={next}
          error={errors.next}
          onChange={(event) => {
            setNext(event.target.value);
            clear('next');
            clear('confirm');
            setPasswordDone(false);
          }}
        />
        <AuthField
          id="settings-confirm-password"
          type="password"
          label={accountPane.confirmField}
          placeholder={accountPane.confirmPlaceholder}
          autoComplete="new-password"
          value={confirm}
          error={errors.confirm}
          message={passwordDone ? { tone: 'success', text: accountPane.passwordDone } : null}
          onChange={(event) => {
            setConfirm(event.target.value);
            clear('confirm');
            setPasswordDone(false);
          }}
        />
        <div className={styles.actions}>
          <button type="submit" className={paneStyles.primary} disabled={passwordBusy}>
            {accountPane.passwordSubmit}
          </button>
        </div>
      </form>
    </>
  );
}
