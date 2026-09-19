import { useEffect, useState } from 'react';
import { refreshAccessToken } from './api/client';
import { SettingsOverlay } from './components/settings/SettingsOverlay';
import { AppRoutes } from './routes/AppRoutes';
import { startSession } from './store/session';
import styles from './App.module.css';

/**
 * The settings overlay is a sibling of the routes rather than part of any screen: it
 * opens over whatever you were looking at, from the top bar that every screen shares.
 * Restore the access token before mounting routes so private screens do not issue a
 * signed-out request while a valid refresh cookie is being checked.
 */
export default function App() {
  const [sessionState, setSessionState] = useState('checking');

  useEffect(() => {
    let active = true;
    refreshAccessToken()
      .then((session) => {
        if (!active) return;
        startSession(session);
        setSessionState('ready');
      })
      .catch((error) => {
        if (!active) return;
        setSessionState(error?.status === 401 || error?.status === 403 ? 'ready' : 'failed');
      });
    return () => { active = false; };
  }, []);

  const retrySessionCheck = () => {
    setSessionState('checking');
    refreshAccessToken()
      .then((session) => {
        startSession(session);
        setSessionState('ready');
      })
      .catch((error) => {
        setSessionState(error?.status === 401 || error?.status === 403 ? 'ready' : 'failed');
      });
  };

  if (sessionState !== 'ready') {
    return (
      <main className={styles.sessionGate}>
        {sessionState === 'checking' ? (
          <p role="status">로그인 상태를 확인하는 중…</p>
        ) : (
          <div role="alert">
            <p>서버에 연결하지 못했어요.</p>
            <button type="button" onClick={retrySessionCheck}>다시 시도</button>
          </div>
        )}
      </main>
    );
  }

  return (
    <>
      <AppRoutes />
      <SettingsOverlay />
    </>
  );
}
