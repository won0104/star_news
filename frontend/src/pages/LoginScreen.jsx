import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { signIn } from '../api/auth';
import { authMessages, loginCopy } from '../data/auth';
import { startSession } from '../store/session';
import { validateId, validatePassword } from '../utils/validation';
import { AuthField } from '../components/auth/AuthField';
import { AuthForm, AuthFormError, AuthPrompt, AuthShell, AuthSubmit } from '../components/auth/AuthShell';
/** Figma V6 / Auth / 로그인 (627:3). */
export function LoginScreen() {
  const navigate = useNavigate();
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const submit = async event => {
    event.preventDefault();
    const next = {
      id: validateId(id),
      password: validatePassword(password)
    };
    setErrors(next);
    if (next.id || next.password) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await signIn({
        id: id.trim(),
        password
      });
      // The id is all the stub tells us about the account; the top bar needs only that
      // much to show the mark. Widen this when signIn starts returning a real user.
      startSession({
        id: id.trim()
      });
      navigate('/app');
    } catch {
      setFormError(authMessages.loginFailed);
    } finally {
      setSubmitting(false);
    }
  };
  return <AuthShell title={loginCopy.title} subtitle={loginCopy.subtitle} onBrand={() => navigate('/')}>
      <AuthForm onSubmit={submit}>
        <AuthField id="login-id" label={loginCopy.id.label} placeholder={loginCopy.id.placeholder} autoComplete="username" value={id} error={errors.id} onChange={event => {
        setId(event.target.value);
        if (errors.id) setErrors(prev => ({
          ...prev,
          id: null
        }));
      }} />
        <AuthField id="login-password" type="password" label={loginCopy.password.label} placeholder={loginCopy.password.placeholder} autoComplete="current-password" value={password} error={errors.password} onChange={event => {
        setPassword(event.target.value);
        if (errors.password) setErrors(prev => ({
          ...prev,
          password: null
        }));
      }} />

        <AuthSubmit disabled={submitting}>{loginCopy.submit}</AuthSubmit>
        <AuthFormError message={formError} />
      </AuthForm>

      <AuthPrompt text={loginCopy.prompt} action={loginCopy.promptAction} onAction={() => navigate('/signup')} />
    </AuthShell>;
}
