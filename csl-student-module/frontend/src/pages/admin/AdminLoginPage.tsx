import { useState, useEffect, type FormEvent } from 'react';
import cslTypographyLogo from '../../assets/CSL-TYPOGRAPHY.png';
import { api } from '../../api';
import { getAdminMe, type AdminUser } from '../../api/admin';

interface AdminLoginPageProps {
  onLoginSuccess: (admin: AdminUser) => void;
}

export function AdminLoginPage({ onLoginSuccess }: AdminLoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    try {
      sessionStorage.removeItem('csl_admin_tab_authenticated');
    } catch {
      // ignore
    }
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // 1. Authenticate with session credentials
      await api.post('/login/', {
        email: email.trim().toLowerCase(),
        password,
      });

      // 2. Verify admin role on dedicated administrative endpoint
      const adminInfo = await getAdminMe();
      if (!adminInfo.is_staff && !adminInfo.is_superuser && adminInfo.role !== 'ADMIN') {
        // Not authorized as admin
        await api.post('/logout/');
        setError('Access denied: Your account does not have administrator privileges.');
        return;
      }

      onLoginSuccess(adminInfo);
    } catch (err: unknown) {
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axErr = err as { response?: { status?: number; data?: { error?: string; detail?: string } } };
        if (axErr.response?.status === 401) {
          setError('Invalid administrator email or password.');
        } else if (axErr.response?.status === 403) {
          setError(axErr.response?.data?.detail || 'Administrator access forbidden for this account.');
        } else {
          setError(axErr.response?.data?.error || axErr.response?.data?.detail || 'Login failed. Please verify credentials.');
        }
      } else {
        setError('Network error connecting to authentication server.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#FCFAF5',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px 16px',
        fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: '440px',
          width: '100%',
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          border: '1px solid #E2E8F0',
          boxShadow: '0 12px 35px -5px rgba(11, 46, 111, 0.08)',
          padding: '36px',
          boxSizing: 'border-box',
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <img
            src={cslTypographyLogo}
            alt="CSL Creator Space Lab"
            style={{ height: '42px', width: 'auto', objectFit: 'contain', margin: '0 auto 16px' }}
          />

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'rgba(20, 85, 184, 0.08)',
              color: '#0B2E6F',
              fontSize: '11px',
              fontWeight: 800,
              padding: '3px 10px',
              borderRadius: '9999px',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '10px',
            }}
          >
            <span>🛡️</span>
            <span>Administrator Control Center</span>
          </div>

          <h1
            style={{
              fontSize: '22px',
              fontWeight: 800,
              color: '#0B2E6F',
              margin: '0 0 6px 0',
            }}
          >
            CSL Admin Login
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280', margin: 0, lineHeight: 1.5 }}>
            Sign in with authorized administrator credentials to manage assessments, question bank, and candidates.
          </p>
        </div>

        {error && (
          <div
            style={{
              backgroundColor: '#FEE2E2',
              border: '1px solid #FECACA',
              color: '#991B1B',
              padding: '12px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              lineHeight: 1.5,
              marginBottom: '20px',
            }}
          >
            <strong>⚠️ Access Notice:</strong> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label
              htmlFor="admin_email"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#374151', marginBottom: '4px' }}
            >
              Administrator Email
            </label>
            <input
              id="admin_email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@csl.com or csldeveloper01@gmail.com"
              style={{
                width: '100%',
                padding: '11px 14px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '14px',
                color: '#111111',
                boxSizing: 'border-box',
                outlineColor: '#1455B8',
              }}
            />
          </div>

          <div>
            <label
              htmlFor="admin_password"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#374151', marginBottom: '4px' }}
            >
              Password
            </label>
            <input
              id="admin_password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              style={{
                width: '100%',
                padding: '11px 14px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '14px',
                color: '#111111',
                boxSizing: 'border-box',
                outlineColor: '#1455B8',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '8px',
              padding: '13px 20px',
              background: loading
                ? '#9CA3AF'
                : 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : '0 4px 12px rgba(11, 46, 111, 0.25)',
              transition: 'all 0.15s ease',
            }}
          >
            {loading ? 'Authenticating Admin Session...' : 'Sign In to Admin Dashboard →'}
          </button>
        </form>

        <div style={{ marginTop: '24px', textAlign: 'center', borderTop: '1px solid #FAF7F3', paddingTop: '16px' }}>
          <p style={{ fontSize: '12px', color: '#94A3B8', margin: 0 }}>
            Restricted access. All administrative activity is audited.
          </p>
        </div>
      </div>
    </div>
  );
}
