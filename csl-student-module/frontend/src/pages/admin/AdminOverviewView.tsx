import { useState, useEffect } from 'react';
import { getAdminStats, type AdminStats } from '../../api/admin';

interface AdminOverviewViewProps {
  onNavigateTab: (tab: string) => void;
}

export function AdminOverviewView({ onNavigateTab }: AdminOverviewViewProps) {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const loadStats = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await getAdminStats();
      setStats(data);
    } catch {
      setError('Failed to fetch administrative metrics from server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '64px', textAlign: 'center', color: '#64748B' }}>
        <div style={{ fontSize: '14px', fontWeight: 600 }}>Loading system statistics from PostgreSQL...</div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div
        style={{
          padding: '24px',
          backgroundColor: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: '12px',
          color: '#991B1B',
          maxWidth: '680px',
        }}
      >
        <strong style={{ display: 'block', marginBottom: '6px' }}>Database Query Error</strong>
        <p style={{ margin: 0, fontSize: '13px' }}>{error}</p>
        <button
          onClick={loadStats}
          style={{
            marginTop: '12px',
            padding: '6px 14px',
            backgroundColor: '#0B2E6F',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Colleges & Institutions',
      value: stats.colleges_count || 0,
      subtext: 'Active academic institutions',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v4M12 14v4M16 14v4"></path>
        </svg>
      ),
      color: '#4338CA',
      bg: '#EEF2FF',
      tab: 'colleges',
    },
    {
      title: 'Assessments Configured',
      value: stats.assessments_count || 0,
      subtext: `${stats.open_assessments_count || 0} currently OPEN & accepting`,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 11l3 3L22 4"></path>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
      ),
      color: '#059669',
      bg: '#ECFDF5',
      tab: 'assessments',
    },
    {
      title: 'Total Candidates',
      value: stats.candidates_count,
      subtext: 'Registered candidates in system',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
          <circle cx="9" cy="7" r="4"></circle>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
        </svg>
      ),
      color: '#1455B8',
      bg: '#EFF6FF',
      tab: 'candidates',
    },
    {
      title: 'Total Sessions Created',
      value: stats.attempts_count,
      subtext: 'Cumulative candidate attempts',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
        </svg>
      ),
      color: '#0B2E6F',
      bg: '#F8FAFC',
      tab: 'live',
    },
    {
      title: 'Active In-Progress',
      value: stats.in_progress_count,
      subtext: 'Live assessments currently running',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
      ),
      color: '#D97706',
      bg: '#FFFBEB',
      tab: 'live',
    },
    {
      title: 'Submitted & Completed',
      value: stats.submitted_count,
      subtext: 'Finalized and scored attempts',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      ),
      color: '#16A34A',
      bg: '#F0FDF4',
      tab: 'results',
    },
    {
      title: 'Timed Out Sessions',
      value: stats.timed_out_count,
      subtext: 'Auto-finalized on timer expiry',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      ),
      color: '#64748B',
      bg: '#F1F5F9',
      tab: 'results',
    },
    {
      title: 'Flagged for Integrity',
      value: stats.flagged_count,
      subtext: 'Tab violations & security flags',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        </svg>
      ),
      color: stats.flagged_count > 0 ? '#DC2626' : '#16A34A',
      bg: stats.flagged_count > 0 ? '#FEF2F2' : '#F0FDF4',
      tab: 'integrity',
    },
    {
      title: 'Aptitude Questions',
      value: stats.aptitude_questions_count,
      subtext: 'Active quantitative & logical pool',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <circle cx="12" cy="12" r="6"></circle>
          <circle cx="12" cy="12" r="2"></circle>
        </svg>
      ),
      color: '#1455B8',
      bg: '#EFF6FF',
      tab: 'questions',
    },
    {
      title: 'Coding Questions',
      value: stats.coding_questions_count,
      subtext: 'Active fundamentals & syntax pool',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="16 18 22 12 16 6"></polyline>
          <polyline points="8 6 2 12 8 18"></polyline>
        </svg>
      ),
      color: '#059669',
      bg: '#ECFDF5',
      tab: 'questions',
    },
  ];

  return (
    <div>
      {/* Page Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 6px 0', letterSpacing: '-0.02em' }}>
            System Operational Dashboard
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Authoritative, real-time telemetry aggregated directly from PostgreSQL database tables.
          </p>
        </div>

        <button
          onClick={loadStats}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 16px',
            backgroundColor: '#FFFFFF',
            border: '1px solid #CBD5E1',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 700,
            color: '#0B2E6F',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FFFFFF')}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
          <span>Refresh Metrics</span>
        </button>
      </div>

      {/* 8 Stats Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '16px',
          marginBottom: '28px',
        }}
      >
        {statCards.map((card, idx) => (
          <div
            key={idx}
            onClick={() => onNavigateTab(card.tab)}
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '14px',
              border: '1px solid #E2E8F0',
              padding: '20px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 6px 14px rgba(11, 46, 111, 0.06)';
              e.currentTarget.style.borderColor = '#CBD5E1';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.02)';
              e.currentTarget.style.borderColor = '#E2E8F0';
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#475569' }}>{card.title}</span>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  backgroundColor: card.bg,
                  color: card.color,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {card.icon}
              </div>
            </div>

            <div style={{ fontSize: '28px', fontWeight: 800, color: '#0B2E6F', letterSpacing: '-0.02em' }}>
              {card.value}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
              <span style={{ fontSize: '11px', color: '#94A3B8' }}>{card.subtext}</span>
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#1455B8' }}>→</span>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions & Bank Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px' }}>
        {/* Question Bank Status */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid #E2E8F0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: 'rgba(20, 85, 184, 0.08)',
                color: '#1455B8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
              </svg>
            </div>
            <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              Question Bank Balance & Health
            </h3>
          </div>

          <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.6, margin: '0 0 18px 0' }}>
            Total questions in bank: <strong style={{ color: '#0F172A' }}>{stats.total_questions_count}</strong>.
            The randomized assessment engine samples 25 Aptitude and 25 Coding questions for each candidate session.
            Ensure adequate pool diversity across difficulty tiers.
          </p>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={() => onNavigateTab('questions')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 18px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#1455B8',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(20, 85, 184, 0.2)',
              }}
            >
              <span>Manage Question Bank</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>
            <button
              onClick={() => onNavigateTab('config')}
              style={{
                padding: '9px 16px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: '#334155',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Assessment Configuration
            </button>
          </div>
        </div>

        {/* Proctoring & Integrity Health */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid #E2E8F0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: stats.flagged_count > 0 ? '#FEE2E2' : '#DCFCE7',
                color: stats.flagged_count > 0 ? '#DC2626' : '#166534',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
            </div>
            <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              Integrity Enforcement Audit Trail
            </h3>
          </div>

          <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.6, margin: '0 0 18px 0' }}>
            Page visibility tracking enforces the 2-warning policy, triggering automated attempt finalization on the 3rd switch.
            {stats.flagged_count > 0 ? (
              <span style={{ color: '#DC2626', fontWeight: 600, display: 'block', marginTop: '4px' }}>
                ⚠️ There are {stats.flagged_count} attempts flagged for administrative review.
              </span>
            ) : (
              <span style={{ color: '#166534', fontWeight: 600, display: 'block', marginTop: '4px' }}>
                ✓ Zero unreviewed violations currently pending.
              </span>
            )}
          </p>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => onNavigateTab('integrity')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 18px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: stats.flagged_count > 0 ? '#DC2626' : '#0B2E6F',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(0, 0, 0, 0.1)',
              }}
            >
              <span>Inspect Integrity Log ({stats.flagged_count})</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
