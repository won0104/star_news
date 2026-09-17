import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkIdAvailability, signUp } from '../api/auth';
import { authMessages, signupCopy } from '../data/auth';
import { startSession } from '../store/session';
import { validateConfirm, validateId, validateNickname, validatePassword } from '../utils/validation';
import { AuthField } from '../components/auth/AuthField';
import { AuthForm, AuthFormError, AuthPrompt, AuthShell, AuthSubmit } from '../components/auth/AuthShell';
import styles from '../components/auth/Auth.module.css';

/** Result of the last duplicate check, tied to the id it was run for. */

/** Figma V6 / Auth / 회원가입 (627:34), with the duplicate-check flow made real. */
export function SignupScreen() {
  const navigate = useNavigate();
  const [id, setId] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [terms, setTerms] = useState(false);
  const [errors, setErrors] = useState({});
  const [idCheck, setIdCheck] = useState({
    status: 'idle'
  });
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const trimmedId = id.trim();
  const checkMatchesInput = idCheck.status !== 'idle' && idCheck.status !== 'checking' && idCheck.id === trimmedId;
  const idVerified = checkMatchesInput && idCheck.status === 'available';
  const clearError = key => {
    if (errors[key]) setErrors(prev => ({
      ...prev,
      [key]: null
    }));
  };
  const handleIdChange = value => {
    setId(value);
    clearError('id');
    // Any edit invalidates the previous check; the user has to run it again.
    if (idCheck.status !== 'idle') setIdCheck({
      status: 'idle'
    });
  };
  const runIdCheck = async () => {
    const error = validateId(id);
    if (error) {
      setErrors(prev => ({
        ...prev,
        id: error
      }));
      return;
    }
    clearError('id');
    setFormError(null);
    setIdCheck({
      status: 'checking'
    });
    try {
      const available = await checkIdAvailability(trimmedId);
      setIdCheck({
        status: available ? 'available' : 'taken',
        id: trimmedId
      });
    } catch (error) {
      // Unchecked is the honest state after a failed check — treating it as "taken"
      // would blame the id for what the network did.
      setIdCheck({
        status: 'idle'
      });
      setFormError(error?.code === 'NETWORK_ERROR' ? authMessages.networkFailed : authMessages.signupFailed);
    }
  };
  const idMessage = idCheck.status === 'checking' ? {
    tone: 'muted',
    text: authMessages.idChecking
  } : checkMatchesInput && idCheck.status === 'available' ? {
    tone: 'success',
    text: authMessages.idAvailable
  } : checkMatchesInput && idCheck.status === 'taken' ? {
    tone: 'error',
    text: authMessages.idTaken
  } : null;
  const submit = async event => {
    event.preventDefault();
    const idError = validateId(id) ?? (idVerified ? null : checkMatchesInput ? authMessages.idTaken : authMessages.idUnchecked);
    const passwordError = validatePassword(password);
    const next = {
      id: idError,
      nickname: validateNickname(nickname),
      password: passwordError,
      confirm: passwordError ? null : validateConfirm(password, confirm),
      terms: terms ? null : authMessages.termsRequired
    };
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;
    setSubmitting(true);
    setFormError(null);
    try {
      // signUp logs in as well — the signup response carries no token of its own.
      const session = await signUp({
        id: trimmedId,
        nickname: nickname.trim(),
        password
      });
      startSession(session);
      navigate('/app');
    } catch (error) {
      if (error?.code === 'LOGIN_ID_ALREADY_EXISTS') {
        setIdCheck({
          status: 'taken',
          id: trimmedId
        });
        setErrors(prev => ({
          ...prev,
          id: authMessages.idTaken
        }));
        return;
      }
      setFormError(error?.code === 'SIGNUP_LOGIN_FAILED' || error?.code === 'NETWORK_ERROR' ? error.message : authMessages.signupFailed);
    } finally {
      setSubmitting(false);
    }
  };
  return <AuthShell title={signupCopy.title} subtitle={signupCopy.subtitle} onBrand={() => navigate('/')}>
      <AuthForm onSubmit={submit}>
        <AuthField id="signup-id" label={signupCopy.id.label} placeholder={signupCopy.id.placeholder} autoComplete="username" value={id} error={errors.id} message={idMessage} onChange={event => handleIdChange(event.target.value)} trailing={<button type="button" className={styles.secondary} disabled={idCheck.status === 'checking'} onClick={runIdCheck}>
              {signupCopy.duplicateCheck}
            </button>} />
        <AuthField id="signup-nickname" label={signupCopy.nickname.label} placeholder={signupCopy.nickname.placeholder} autoComplete="nickname" value={nickname} error={errors.nickname} onChange={event => {
        setNickname(event.target.value);
        clearError('nickname');
      }} />
        <AuthField id="signup-password" type="password" label={signupCopy.password.label} placeholder={signupCopy.password.placeholder} autoComplete="new-password" value={password} error={errors.password} onChange={event => {
        setPassword(event.target.value);
        clearError('password');
        clearError('confirm');
      }} />
        <AuthField id="signup-confirm" type="password" label={signupCopy.confirm.label} placeholder={signupCopy.confirm.placeholder} autoComplete="new-password" value={confirm} error={errors.confirm} onChange={event => {
        setConfirm(event.target.value);
        clearError('confirm');
      }} />

        <div className={styles.termsBlock}>
          <label className={styles.checkboxRow}>
            <input type="checkbox" className={styles.checkbox} checked={terms} aria-invalid={errors.terms ? true : undefined} onChange={event => {
            setTerms(event.target.checked);
            clearError('terms');
          }} />
            {signupCopy.terms}
          </label>
          {errors.terms && <p className={`${styles.message} ${styles.messageError}`}>{errors.terms}</p>}
        </div>

        <AuthSubmit tight disabled={submitting}>
          {signupCopy.submit}
        </AuthSubmit>
        <AuthFormError message={formError} />
      </AuthForm>

      <AuthPrompt text={signupCopy.prompt} action={signupCopy.promptAction} onAction={() => navigate('/login')} />
    </AuthShell>;
}
