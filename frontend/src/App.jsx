import { SettingsOverlay } from './components/settings/SettingsOverlay';
import { AppRoutes } from './routes/AppRoutes';

/**
 * The settings overlay is a sibling of the routes rather than part of any screen: it
 * opens over whatever you were looking at, from the top bar that every screen shares.
 */
export default function App() {
  return (
    <>
      <AppRoutes />
      <SettingsOverlay />
    </>
  );
}
