import { useState, useEffect, useMemo } from 'react';
import { getAdminConfig, updateAdminConfig, type AdminAssessmentConfig } from '../../api/admin';

export function AdminConfigView() {
  const [config, setConfig] = useState<AdminAssessmentConfig | null>(null);
  const [initialConfig, setInitialConfig] = useState<AdminAssessmentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await getAdminConfig();
      setConfig(data);
      setInitialConfig(data);
    } catch {
      setError('Failed to fetch active assessment configuration.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const isDirty = useMemo(() => {
    if (!config || !initialConfig) return false;
    return JSON.stringify(config) !== JSON.stringify(initialConfig);
  }, [config, initialConfig]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    if (!config) return;
    const { name, value, type } = e.target;
    let val: any = value;
    if (type === 'number') {
      val = parseInt(value, 10) || 0;
    } else if (type === 'checkbox') {
      val = (e.target as HTMLInputElement).checked;
    }
    setConfig({ ...config, [name]: val });
  };

  const handleReset = () => {
    if (initialConfig) {
      setConfig({ ...initialConfig });
      setError('');
      setMessage('');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;
    setMessage('');
    setError('');

    // Pre-validation: Total Marks must equal Aptitude + Coding count
    if (config.total_marks !== config.aptitude_count + config.coding_count) {
      setError(
        `Total marks (${config.total_marks}) must equal Aptitude count (${config.aptitude_count}) + Coding count (${config.coding_count}) = ${
          config.aptitude_count + config.coding_count
        }.`
      );
      return;
    }

    setSaving(true);
    try {
      const updated = await updateAdminConfig(config);
      setConfig(updated);
      setInitialConfig(updated);
      setMessage('Assessment configuration updated and persisted successfully.');
    } catch (err: unknown) {
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axErr = err as { response?: { data?: Record<string, string> } };
        setError(JSON.stringify(axErr.response?.data || 'Failed to update configuration.'));
      } else {
        setError('Failed to update configuration.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '64px', textAlign: 'center', color: '#64748B' }}>
        <div style={{ fontSize: '14px', fontWeight: 600 }}>Loading assessment configuration...</div>
      </div>
    );
  }

  if (!config) {
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
        <strong style={{ display: 'block', marginBottom: '6px' }}>Configuration Error</strong>
        <p style={{ margin: 0, fontSize: '13px' }}>{error || 'Unable to load configuration from the database.'}</p>
        <button
          onClick={loadConfig}
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

  const marksSum = config.aptitude_count + config.coding_count;
  const isMarksValid = config.total_marks === marksSum;

  return (
    <div style={{ maxWidth: '1040px', margin: '0 auto' }}>
      {/* Header & Status Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 6px 0', letterSpacing: '-0.02em' }}>
            Assessment Policy & Configuration
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Authoritative parameters controlling duration, question distribution, passing marks, and proctoring thresholds.
          </p>
        </div>

        {/* Action & Dirty Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isDirty ? (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 12px',
                borderRadius: '9999px',
                fontSize: '11px',
                fontWeight: 700,
                backgroundColor: '#FEF3C7',
                color: '#92400E',
                border: '1px solid #FDE68A',
              }}
            >
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#D97706' }} />
              Unsaved Changes
            </span>
          ) : (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 12px',
                borderRadius: '9999px',
                fontSize: '11px',
                fontWeight: 700,
                backgroundColor: '#F1F5F9',
                color: '#475569',
                border: '1px solid #E2E8F0',
              }}
            >
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10B981' }} />
              Synchronized
            </span>
          )}

          {isDirty && (
            <button
              type="button"
              onClick={handleReset}
              style={{
                padding: '8px 14px',
                backgroundColor: '#FFFFFF',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                color: '#475569',
                cursor: 'pointer',
              }}
            >
              Revert
            </button>
          )}

          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '9px 20px',
              backgroundColor: !isDirty || saving ? '#94A3B8' : '#1455B8',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: !isDirty || saving ? 'not-allowed' : 'pointer',
              boxShadow: isDirty ? '0 2px 8px rgba(20, 85, 184, 0.25)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            {saving ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 1s linear infinite' }}>
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
                </svg>
                <span>Saving...</span>
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                  <polyline points="17 21 17 13 7 13 7 21"></polyline>
                  <polyline points="7 3 7 8 15 8"></polyline>
                </svg>
                <span>Save Changes</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {message && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: '#ECFDF5',
            border: '1px solid #A7F3D0',
            color: '#065F46',
            padding: '12px 18px',
            borderRadius: '10px',
            fontSize: '13px',
            fontWeight: 600,
            marginBottom: '20px',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FECACA',
            color: '#991B1B',
            padding: '12px 18px',
            borderRadius: '10px',
            fontSize: '13px',
            fontWeight: 600,
            marginBottom: '20px',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* Snapshot Safety Callout */}
      <div
        style={{
          display: 'flex',
          gap: '14px',
          backgroundColor: '#FFFFFF',
          border: '1px solid rgba(245, 184, 61, 0.45)',
          padding: '16px 20px',
          borderRadius: '12px',
          marginBottom: '24px',
          boxShadow: '0 2px 8px rgba(11, 46, 111, 0.02)',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            backgroundColor: 'rgba(245, 184, 61, 0.15)',
            color: '#B45309',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            marginTop: '2px',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          </svg>
        </div>
        <div style={{ fontSize: '13px', lineHeight: 1.5, color: '#475569' }}>
          <strong style={{ color: '#0B2E6F', display: 'block', marginBottom: '2px', fontSize: '13px' }}>
            Snapshot Isolation Guarantee Active
          </strong>
          Modifications made here immediately apply to subsequent candidate sessions. All candidate attempts
          currently in progress or finalized retain their immutable snapshot configuration, ensuring zero score disruption
          or mid-assessment inconsistency.
        </div>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Section 1: Assessment Identity & Time */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid #E2E8F0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                backgroundColor: 'rgba(20, 85, 184, 0.08)',
                color: '#1455B8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
            </div>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              1. Assessment Identity & Duration
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Assessment Portal Title
              </label>
              <input
                type="text"
                name="title"
                value={config.title}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                }}
              />
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Displayed to candidates on the login screen, test instructions, and certificate headers.
              </span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Duration (Minutes)
              </label>
              <input
                type="number"
                name="duration_minutes"
                min={1}
                max={300}
                value={config.duration_minutes}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                  fontWeight: 700,
                }}
              />
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Standard: 60 minutes (1 hour)
              </span>
            </div>
          </div>
        </div>

        {/* Section 2: Question Distribution & Scoring */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid #E2E8F0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                backgroundColor: 'rgba(20, 85, 184, 0.08)',
                color: '#1455B8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
              </svg>
            </div>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              2. Section Distribution & Scoring Structure
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Aptitude Question Count
              </label>
              <input
                type="number"
                name="aptitude_count"
                min={1}
                value={config.aptitude_count}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                  fontWeight: 700,
                }}
              />
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Default quota: 25 items
              </span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Coding Fundamentals Count
              </label>
              <input
                type="number"
                name="coding_count"
                min={1}
                value={config.coding_count}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                  fontWeight: 700,
                }}
              />
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Default quota: 25 items
              </span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Total Assessment Marks
              </label>
              <input
                type="number"
                name="total_marks"
                min={1}
                value={config.total_marks}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: `1px solid ${isMarksValid ? '#CBD5E1' : '#EF4444'}`,
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                  fontWeight: 700,
                }}
              />
              <span style={{ fontSize: '11px', color: isMarksValid ? '#64748B' : '#DC2626', marginTop: '4px', display: 'block' }}>
                {isMarksValid ? '✓ Exactly equals sum' : `⚠️ Must equal ${marksSum} marks`}
              </span>
            </div>
          </div>

          {/* Scoring balance helper bar */}
          <div
            style={{
              marginTop: '16px',
              padding: '12px 16px',
              borderRadius: '8px',
              backgroundColor: isMarksValid ? '#F0FDF4' : '#FEF2F2',
              border: `1px solid ${isMarksValid ? '#BBF7D0' : '#FECACA'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '12px',
            }}
          >
            <div style={{ color: isMarksValid ? '#166534' : '#991B1B', fontWeight: 600 }}>
              Distribution Check: {config.aptitude_count} Aptitude + {config.coding_count} Coding = {marksSum} items / {config.total_marks} marks total
            </div>
            <span
              style={{
                fontWeight: 700,
                color: isMarksValid ? '#15803D' : '#DC2626',
              }}
            >
              {isMarksValid ? 'Valid Configuration ✓' : 'Sum Mismatch Error ⚠️'}
            </span>
          </div>
        </div>

        {/* Section 3: Attempt & Integrity Policy */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid #E2E8F0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                backgroundColor: 'rgba(20, 85, 184, 0.08)',
                color: '#1455B8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
            </div>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              3. Proctoring & Attempt Integrity Policy
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Max Attempts per Candidate
              </label>
              <input
                type="number"
                name="max_attempts"
                min={1}
                value={config.max_attempts}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                  fontWeight: 700,
                }}
              />
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Default: 1 Attempt (Strict Single-Session)
              </span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Permitted Tab-Switch Warnings
              </label>
              <input
                type="number"
                name="max_tab_switches_warning"
                min={1}
                value={config.max_tab_switches_warning}
                onChange={handleChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  fontFamily: 'monospace',
                  fontWeight: 700,
                }}
              />
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Default: 2 warnings. The 3rd tab switch triggers immediate automated submission.
              </span>
            </div>
          </div>

          {/* Auto submit checkbox toggle */}
          <div
            style={{
              marginTop: '20px',
              padding: '14px 18px',
              borderRadius: '10px',
              backgroundColor: '#F8FAFC',
              border: '1px solid #E2E8F0',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              cursor: 'pointer',
            }}
            onClick={() => setConfig({ ...config, auto_submit_on_tab_limit: !config.auto_submit_on_tab_limit })}
          >
            <input
              type="checkbox"
              name="auto_submit_on_tab_limit"
              checked={config.auto_submit_on_tab_limit}
              onChange={handleChange}
              style={{
                width: '18px',
                height: '18px',
                accentColor: '#1455B8',
                cursor: 'pointer',
              }}
              onClick={(e) => e.stopPropagation()}
            />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#0F172A' }}>
                Automated Submission on Threshold Violation
              </div>
              <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
                When enabled, the student portal immediately halts testing, collects answered responses, and submits the attempt on the 3rd tab switch without manual intervention.
              </div>
            </div>
          </div>
        </div>

        {/* Floating/Bottom Action Bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 24px',
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            border: '1px solid #E2E8F0',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.03)',
          }}
        >
          <div style={{ fontSize: '12px', color: '#64748B' }}>
            Configuration Version ID: <strong style={{ color: '#0B2E6F' }}>#{config.id}</strong> • Last Updated:{' '}
            {config.updated_at ? new Date(config.updated_at).toLocaleString() : 'Recently'}
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            {isDirty && (
              <button
                type="button"
                onClick={handleReset}
                style={{
                  padding: '9px 18px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #CBD5E1',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#475569',
                  cursor: 'pointer',
                }}
              >
                Revert Changes
              </button>
            )}

            <button
              type="submit"
              disabled={saving || !isDirty}
              style={{
                padding: '9px 24px',
                backgroundColor: !isDirty || saving ? '#94A3B8' : '#1455B8',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: !isDirty || saving ? 'not-allowed' : 'pointer',
                boxShadow: isDirty ? '0 2px 8px rgba(20, 85, 184, 0.25)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {saving ? 'Saving...' : 'Save & Persist Configuration'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
