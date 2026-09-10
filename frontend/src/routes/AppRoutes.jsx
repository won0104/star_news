import { Route, Routes } from 'react-router-dom';
import { AppScene } from '../pages/AppScene';
import { EventScene } from '../pages/EventScene';
import { MainScene } from '../pages/MainScene';
import { AtticScene } from '../pages/AtticScene';
import { GraphScene } from '../pages/GraphScene';
import { LoginScreen } from '../pages/LoginScreen';
import { SignupScreen } from '../pages/SignupScreen';

/**
 * Top-level screen map.
 *
 * `/` is the front of the site: the bare room, nothing over it but the bar. `/app` is
 * the product — the bar's four destinations, chosen with `?view=`. The bar is the same
 * bar on both, so pressing one of the four at the front carries it into /app.
 *
 * `/event/:id` is one event in full, opened from a card in 나를 위한 추천. It is a page
 * under the bar rather than one of its destinations, so nothing in the bar is current
 * there, the way /trend behaves.
 *
 * `/trend` is the "오늘의 트렌드" attic view; `/explore` is the event-centred graph view
 * (reached today from the attic's POLICY card — once real event ids exist this becomes
 * `/explore/:eventId`).
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<MainScene />} />
      <Route path="/app" element={<AppScene />} />
      <Route path="/event/:id" element={<EventScene />} />
      <Route path="/trend" element={<AtticScene />} />
      <Route path="/explore" element={<GraphScene />} />
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/signup" element={<SignupScreen />} />
    </Routes>
  );
}
