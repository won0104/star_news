import { Route, Routes } from 'react-router-dom';
import { AppScene } from '../pages/AppScene';
import { HistoryEventScene } from '../pages/HistoryEventScene';
import { MainScene } from '../pages/MainScene';
import { LoginScreen } from '../pages/LoginScreen';
import { SignupScreen } from '../pages/SignupScreen';

/**
 * Top-level screen map.
 *
 * `/` is the front of the site: the bare room, nothing over it but the bar. `/app` is
 * the product — the bar's four destinations, chosen with `?view=`. The bar is the same
 * bar on both, so pressing one of the four at the front carries it into /app.
 *
 * `/history/:storyId/events/:eventId` is one recorded event in full.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<MainScene />} />
      <Route path="/app" element={<AppScene />} />
      <Route path="/history/:storyId/events/:eventId" element={<HistoryEventScene />} />
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/signup" element={<SignupScreen />} />
    </Routes>
  );
}
