import { Route, Routes } from 'react-router-dom';
import { HomeScene } from '../pages/HomeScene';
import { AtticScene } from '../pages/AtticScene';
import { GraphScene } from '../pages/GraphScene';
import { LoginScreen } from '../pages/LoginScreen';
import { SignupScreen } from '../pages/SignupScreen';

/**
 * Top-level screen map. `/trend` is the "오늘의 트렌드" attic view; `/explore` is the
 * event-centred graph view (reached today from the attic's POLICY card — once real
 * event ids exist this becomes `/explore/:eventId`).
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeScene />} />
      <Route path="/trend" element={<AtticScene />} />
      <Route path="/explore" element={<GraphScene />} />
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/signup" element={<SignupScreen />} />
    </Routes>
  );
}
