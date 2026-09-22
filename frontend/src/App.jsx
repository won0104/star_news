import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { refreshAccessToken } from './api/client';
import { fetchMyProfile } from './api/user';
import { SettingsOverlay } from './components/settings/SettingsOverlay';
import { AppRoutes } from './routes/AppRoutes';
import { attachUser, getSessionRevision, startSession, useSession } from './store/session';
import styles from './App.module.css';

function isPublicLocation({ pathname, search }) {
  if (pathname === '/app') {
    const view = new URLSearchParams(search).get('view');
    return view === null || view === 'trend';
  }
  return (
    pathname === '/' ||
    pathname === '/login' ||
    pathname === '/signup' ||
    pathname.startsWith('/history/')
  );
}

/**
 * The settings overlay is a sibling of the routes rather than part of any screen: it
 * opens over whatever you were looking at, from the top bar that every screen shares.
 * Private screens wait while token restoration is in progress. If that check fails,
 * screens still mount and show their own unavailable or sample states.
 */
export default function App() {
  const location = useLocation();
  const account = useSession();
  const [sessionState, setSessionState] = useState('checking');
  const isPublic = isPublicLocation(location);
  const isAuthForm = location.pathname === '/login' || location.pathname === '/signup';

  const restoreSession = useCallback((isActive = () => true) => {
    const revision = getSessionRevision();
    refreshAccessToken()
      .then((session) => {
        if (!isActive()) return;
        if (getSessionRevision() !== revision) {
          setSessionState('ready');
          return;
        }
        startSession(session);
        setSessionState('ready');

        // refresh 응답은 토큰만 준다. 누구인지는 여기서 따로 받아 채운다 — 이게 없으면
        // 새로고침한 사용자는 로그인 상태이면서 이름이 '내 계정' 으로만 보인다.
        // 화면을 붙잡아 두지 않는다: 이름은 늦게 와도 되는 정보다.
        //
        // 기준 revision 은 startSession **뒤에** 읽는다. 그 호출이 revision 을 올리므로
        // 앞에서 읽은 값과 비교하면 언제나 달라져 결과를 통째로 버리게 된다.
        const signedIn = getSessionRevision();
        fetchMyProfile()
          .then((user) => {
            if (!isActive() || getSessionRevision() !== signedIn) return;
            attachUser(session.accessToken, user);
          })
          .catch(() => {});
      })
      .catch((error) => {
        if (!isActive()) return;
        const changed = getSessionRevision() !== revision;
        setSessionState(
          changed || error?.status === 401 || error?.status === 403 ? 'ready' : 'failed',
        );
      });
  }, []);

  useEffect(() => {
    let active = true;
    restoreSession(() => active);
    return () => { active = false; };
  }, [restoreSession]);

  const retrySessionCheck = () => {
    setSessionState('checking');
    restoreSession();
  };

  const showRoute = sessionState !== 'checking' || (isPublic && !isAuthForm);
  if (!showRoute) {
    return (
      <main className={styles.sessionGate}>
        <p role="status">로그인 상태를 확인하는 중…</p>
      </main>
    );
  }

  return (
    <>
      <AppRoutes key={account?.user?.userId ?? (account ? 'authenticated' : 'public')} />
      <SettingsOverlay />
      {sessionState === 'failed' && (
        <div className={styles.sessionNotice} role="alert">
          <p>로그인 상태를 확인하지 못했어요.</p>
          <button type="button" onClick={retrySessionCheck}>다시 시도</button>
        </div>
      )}
    </>
  );
}
