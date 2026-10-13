import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { api } from '../api';

interface StudentLayoutProps {
  onLogout: () => void;
}

const NAV_ITEMS = [
  { to: '/student', label: 'Dashboard', end: true },
  { to: '/student/skills', label: 'Skills', end: false },
  { to: '/student/activities', label: 'Activities', end: false },
  { to: '/student/performance', label: 'Performance', end: false },
  { to: '/student/leaderboard', label: 'Leaderboard', end: false },
  { to: '/student/profile', label: 'Profile', end: false },
];

/**
 * Authenticated Student application shell: simple top bar with the student
 * navigation and a main content area. Intentionally plain — no design work.
 */
export function StudentLayout({ onLogout }: StudentLayoutProps) {
  const navigate = useNavigate();

  // Uses the existing logout mechanism (POST /api/auth/logout/), then clears
  // client auth state and returns the user to /login.
  const handleLogout = async () => {
    try {
      await api.post('/logout/');
    } catch {
      // ignore — still clear local state and go to login
    } finally {
      onLogout();
      navigate('/login', { replace: true });
    }
  };

  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{ display: 'flex', alignItems: 'center', padding: '8px 16px' }}>
        <strong>CSL</strong>
        <nav style={{ display: 'flex', gap: 12, marginLeft: 16 }}>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button type="button" onClick={handleLogout} style={{ marginLeft: 'auto' }}>
          Logout
        </button>
      </header>
      <hr />
      <main style={{ padding: '16px 24px' }}>
        <Outlet />
      </main>
    </div>
  );
}
