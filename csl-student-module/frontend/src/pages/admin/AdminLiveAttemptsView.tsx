import { useState, useEffect, useCallback, useMemo } from 'react';
import { getAdminLiveAttempts, type AdminLiveAttempt } from '../../api/admin';

interface AdminLiveAttemptsViewProps {
  onReviewAttempt: (attemptId: string) => void;
}

export function AdminLiveAttemptsView({ onReviewAttempt }: AdminLiveAttemptsViewProps) {
  const [attempts, setAttempts] = useState<AdminLiveAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  const loadAttempts = useCallback(async () => {
    try {
      const data = await getAdminLiveAttempts({
        state: stateFilter || undefined,
        search: search || undefined,
      });
      setAttempts(data);
      setLastRefreshedAt(new Date());
    } catch {
      console.error('Failed to load attempts.');
    } finally {
      setLoading(false);
    }
  }, [stateFilter, search]);

  useEffect(() => {
    loadAttempts();
  }, [loadAttempts]);

  // Polling every 10s if auto-refresh is active
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadAttempts();
    }, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadAttempts]);

  // Real-data summary counts
  const summaryCounts = useMemo(() => {
    let inProgress = 0;
    let submitted = 0;
    let timedOut = 0;
    let flagged = 0;

    for (const a of attempts) {
      if (a.state === 'IN_PROGRESS') inProgress++;
      if (a.state === 'SUBMITTED') submitted++;
      if (a.state === 'TIMED_OUT') timedOut++;
      if (a.is_flagged || a.state === 'FLAGGED_FOR_REVIEW') flagged++;
    }

    return { inProgress, submitted, timedOut, flagged, total: attempts.length };
  }, [attempts]);

  const formatSeconds = (secs: number) => {
    if (secs <= 0) return '00:00';
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  return (
    <div>
      {/* Header & Operational Telemetry */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 6px 0', letterSpacing: '-0.02em' }}>
            Live Assessment Sessions Monitor
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Real-time proctoring telemetry, authoritative server countdown timers, and live question answer ratios.
          </p>
        </div>

        {/* Polling & Manual Refresh Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: '#475569',
              cursor: 'pointer',
              backgroundColor: '#FFFFFF',
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid #E2E8F0',
            }}
          >
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{ accentColor: '#1455B8', cursor: 'pointer' }}
            />
            <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
              {autoRefresh && (
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: '#10B981',
                    display: 'inline-block',
                    animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                  }}
                />
              )}
              Auto-refresh (10s)
            </span>
          </label>

          <button
            onClick={() => loadAttempts()}
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
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ─── REAL-DATA METRIC SUMMARY CHIPS ─────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '14px',
          marginBottom: '20px',
        }}
      >
        {/* Chip 1: In Progress */}
        <div
          onClick={() => setStateFilter(stateFilter === 'IN_PROGRESS' ? '' : 'IN_PROGRESS')}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            border: stateFilter === 'IN_PROGRESS' ? '1.5px solid #D97706' : '1px solid #E2E8F0',
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#D97706', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Active In Progress
            </div>
            <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
              {summaryCounts.inProgress}
            </div>
          </div>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#FEF3C7',
              color: '#D97706',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
            </svg>
          </div>
        </div>

        {/* Chip 2: Submitted */}
        <div
          onClick={() => setStateFilter(stateFilter === 'SUBMITTED' ? '' : 'SUBMITTED')}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            border: stateFilter === 'SUBMITTED' ? '1.5px solid #16A34A' : '1px solid #E2E8F0',
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#16A34A', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Submitted & Finalized
            </div>
            <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
              {summaryCounts.submitted}
            </div>
          </div>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#DCFCE7',
              color: '#16A34A',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
        </div>

        {/* Chip 3: Timed Out */}
        <div
          onClick={() => setStateFilter(stateFilter === 'TIMED_OUT' ? '' : 'TIMED_OUT')}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            border: stateFilter === 'TIMED_OUT' ? '1.5px solid #64748B' : '1px solid #E2E8F0',
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Timed Out Sessions
            </div>
            <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
              {summaryCounts.timedOut}
            </div>
          </div>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#F1F5F9',
              color: '#64748B',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
          </div>
        </div>

        {/* Chip 4: Flagged for Review */}
        <div
          onClick={() => setStateFilter(stateFilter === 'FLAGGED_FOR_REVIEW' ? '' : 'FLAGGED_FOR_REVIEW')}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            border: stateFilter === 'FLAGGED_FOR_REVIEW' ? '1.5px solid #DC2626' : '1px solid #E2E8F0',
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#DC2626', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Flagged for Review
            </div>
            <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
              {summaryCounts.flagged}
            </div>
          </div>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#FEE2E2',
              color: '#DC2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
          </div>
        </div>
      </div>

      {/* ─── FILTER & SEARCH TOOLBAR ─────────────────────────────────── */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1px solid #E2E8F0',
          padding: '12px 18px',
          marginBottom: '16px',
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
        }}
      >
        <div style={{ position: 'relative', flex: 1 }}>
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }}
          >
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search candidate by name, register / roll number, or institution..."
            style={{
              padding: '8px 12px 8px 36px',
              borderRadius: '8px',
              border: '1px solid #CBD5E1',
              fontSize: '13px',
              width: '100%',
              boxSizing: 'border-box',
              outlineColor: '#1455B8',
            }}
          />
        </div>

        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          style={{
            padding: '8px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            backgroundColor: '#FFFFFF',
            outlineColor: '#1455B8',
            fontWeight: 500,
            color: '#334155',
          }}
        >
          <option value="">All Session States</option>
          <option value="IN_PROGRESS">In Progress Only</option>
          <option value="SUBMITTED">Submitted Only</option>
          <option value="TIMED_OUT">Timed Out Only</option>
          <option value="FLAGGED_FOR_REVIEW">Flagged for Review Only</option>
        </select>

        {stateFilter && (
          <button
            onClick={() => setStateFilter('')}
            style={{
              padding: '7px 12px',
              backgroundColor: '#F1F5F9',
              border: 'none',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 600,
              color: '#475569',
              cursor: 'pointer',
            }}
          >
            Clear State Filter
          </button>
        )}
      </div>

      {/* ─── HIGH-DENSITY MONITORING TABLE ──────────────────────────── */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '14px',
          border: '1px solid #E2E8F0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569' }}>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Candidate</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Status</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Time Remaining</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Questions Progress</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Tab Switches</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Fullscreen Exits</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Integrity Status</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  Loading real-time assessment sessions...
                </td>
              </tr>
            ) : attempts.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  No active assessment sessions found matching the filter criteria.
                </td>
              </tr>
            ) : (
              attempts.map((att) => {
                const totalQ = att.total_questions || 50;
                const progressPct = Math.min(100, Math.round((att.answered_count / totalQ) * 100));

                return (
                  <tr
                    key={att.id}
                    style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.1s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    {/* Candidate Identity */}
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontWeight: 700, color: '#0B2E6F' }}>{att.candidate_name}</span>
                        {att.assessment_code && (
                          <span style={{ fontSize: '10px', fontWeight: 700, backgroundColor: '#EEF2FF', color: '#3730A3', padding: '1px 6px', borderRadius: '4px' }}>
                            {att.assessment_code}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
                        Roll No: <strong style={{ color: '#0F172A' }}>{att.register_number}</strong> • {att.college}
                      </div>
                    </td>

                    {/* Status Badge */}
                    <td style={{ padding: '12px 16px' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '3px 10px',
                          borderRadius: '9999px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor:
                            att.state === 'IN_PROGRESS'
                              ? '#FEF3C7'
                              : att.state === 'SUBMITTED'
                              ? '#DCFCE7'
                              : att.state === 'TIMED_OUT'
                              ? '#F1F5F9'
                              : '#FEE2E2',
                          color:
                            att.state === 'IN_PROGRESS'
                              ? '#B45309'
                              : att.state === 'SUBMITTED'
                              ? '#166534'
                              : att.state === 'TIMED_OUT'
                              ? '#475569'
                              : '#DC2626',
                        }}
                      >
                        {att.state === 'IN_PROGRESS' && (
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#D97706' }} />
                        )}
                        {att.state}
                      </span>
                    </td>

                    {/* Time Remaining */}
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontWeight: 700, fontSize: '14px' }}>
                      {att.state === 'IN_PROGRESS' ? (
                        <span style={{ color: att.remaining_seconds < 300 ? '#DC2626' : '#0B2E6F' }}>
                          {formatSeconds(att.remaining_seconds)}
                        </span>
                      ) : (
                        <span style={{ color: '#94A3B8', fontSize: '12px', fontWeight: 500 }}>Session Finished</span>
                      )}
                    </td>

                    {/* Answered Progress */}
                    <td style={{ padding: '12px 16px', minWidth: '140px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px', color: '#475569' }}>
                        <span>
                          <strong style={{ color: '#16A34A' }}>{att.answered_count}</strong> of {totalQ} answered
                        </span>
                        <span style={{ fontWeight: 700 }}>{progressPct}%</span>
                      </div>
                      <div
                        style={{
                          height: '6px',
                          width: '100%',
                          backgroundColor: '#E2E8F0',
                          borderRadius: '9999px',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            height: '100%',
                            width: `${progressPct}%`,
                            backgroundColor: progressPct === 100 ? '#16A34A' : '#1455B8',
                            borderRadius: '9999px',
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    </td>

                    {/* Tab Switches */}
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 700 }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          backgroundColor: att.tab_switch_count >= 2 ? '#FEE2E2' : '#F1F5F9',
                          color: att.tab_switch_count >= 2 ? '#DC2626' : '#334155',
                          border: att.tab_switch_count >= 2 ? '1px solid #FECACA' : '1px solid #E2E8F0',
                        }}
                      >
                        {att.tab_switch_count} / 2
                      </span>
                    </td>

                    {/* Fullscreen Exits */}
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 700, color: '#475569' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          backgroundColor: att.fullscreen_exit_count > 0 ? '#FEF3C7' : '#F1F5F9',
                          color: att.fullscreen_exit_count > 0 ? '#B45309' : '#475569',
                        }}
                      >
                        {att.fullscreen_exit_count}
                      </span>
                    </td>

                    {/* Integrity Flag */}
                    <td style={{ padding: '12px 16px' }}>
                      {att.is_flagged ? (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: '#DC2626',
                            backgroundColor: '#FEF2F2',
                            padding: '3px 8px',
                            borderRadius: '9999px',
                            fontWeight: 700,
                            fontSize: '11px',
                            border: '1px solid #FECACA',
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                          </svg>
                          Flagged
                        </span>
                      ) : (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: '#166534',
                            backgroundColor: '#F0FDF4',
                            padding: '3px 8px',
                            borderRadius: '9999px',
                            fontWeight: 700,
                            fontSize: '11px',
                            border: '1px solid #BBF7D0',
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                          </svg>
                          Normal
                        </span>
                      )}
                    </td>

                    {/* Inspect Review Action */}
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <button
                        onClick={() => onReviewAttempt(att.id)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          backgroundColor: '#1455B8',
                          color: '#FFFFFF',
                          border: 'none',
                          borderRadius: '7px',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          boxShadow: '0 1px 3px rgba(20, 85, 184, 0.2)',
                          transition: 'background-color 0.15s ease',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#0B2E6F')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#1455B8')}
                      >
                        <span>Inspect Review</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="9 18 15 12 9 6"></polyline>
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {/* Footer Status Bar */}
        <div
          style={{
            padding: '10px 18px',
            backgroundColor: '#F8FAFC',
            borderTop: '1px solid #E2E8F0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '11px',
            color: '#64748B',
          }}
        >
          <span>Showing {attempts.length} recorded session attempts</span>
          <span>Last polled: {lastRefreshedAt.toLocaleTimeString()}</span>
        </div>
      </div>
    </div>
  );
}
