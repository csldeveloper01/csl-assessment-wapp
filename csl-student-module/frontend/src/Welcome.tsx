import { useNavigate } from 'react-router-dom';
import { api } from './api';

interface WelcomeProps {
  user: {
    email: string;
    name: string;
  } | null;
  onLogout: () => void;
}

export function Welcome({ user, onLogout }: WelcomeProps) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await api.post('/logout/');
    } catch {
      // ignore
    } finally {
      onLogout();
      navigate('/login');
    }
  };

  return (
    <div style={{ maxWidth: 500, margin: '60px auto', textAlign: 'center' }}>
      <h1>Welcome to CSL</h1>
      {user && (
        <div style={{ margin: '20px 0' }}>
          <p><strong>Name:</strong> {user.name || '(not set)'}</p>
          <p><strong>Email:</strong> {user.email}</p>
        </div>
      )}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 20, flexWrap: 'wrap' }}>
        <a
          href={import.meta.env.VITE_API_BASE_URL ? `${import.meta.env.VITE_API_BASE_URL}/admin/` : "/admin/"}
          target="_blank"
          rel="noreferrer"
          style={{ padding: '8px 16px', backgroundColor: '#0f766e', color: '#fff', textDecoration: 'none', borderRadius: 6, fontWeight: 600, display: 'inline-flex', alignItems: 'center' }}
        >
          Open Django Admin Portal &rarr;
        </a>
        <button
          onClick={() => navigate('/staff/activities')}
          style={{ padding: '8px 16px', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}
        >
          Manage Activities
        </button>
        <button onClick={handleLogout} style={{ padding: '8px 16px', borderRadius: 6, border: '1px solid #d1d5db', cursor: 'pointer' }}>
          Logout
        </button>
      </div>
    </div>
  );
}
