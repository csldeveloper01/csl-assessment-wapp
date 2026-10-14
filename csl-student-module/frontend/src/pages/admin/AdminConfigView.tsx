import React, { useState, useEffect, useMemo } from 'react';
import {
  getAdminConfig,
  updateAdminConfig,
  getAdminSections,
  createAdminSection,
  updateAdminSection,
  deleteAdminSection,
  type AdminAssessmentConfig,
  type AdminSection,
} from '../../api/admin';

export function AdminConfigView() {
  const [config, setConfig] = useState<AdminAssessmentConfig | null>(null);
  const [initialConfig, setInitialConfig] = useState<AdminAssessmentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // Reusable Section Library State
  const [sections, setSections] = useState<AdminSection[]>([]);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [sectionModalOpen, setSectionModalOpen] = useState(false);
  const [editingSection, setEditingSection] = useState<AdminSection | null>(null);
  const [sectionForm, setSectionForm] = useState({
    name: '',
    code: '',
    description: '',
    is_active: true,
  });
  const [sectionSaving, setSectionSaving] = useState(false);
  const [sectionError, setSectionError] = useState('');
  const [sectionSuccess, setSectionSuccess] = useState('');

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await getAdminConfig();
      setConfig(data);
      setInitialConfig(data);
    } catch {
      setError('Failed to fetch platform configuration.');
    } finally {
      setLoading(false);
    }
  };

  const loadSections = async () => {
    try {
      setSectionsLoading(true);
      const data = await getAdminSections();
      setSections(data);
    } catch {
      console.error('Failed to fetch reusable sections.');
    } finally {
      setSectionsLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
    loadSections();
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

    setSaving(true);
    try {
      const updated = await updateAdminConfig(config);
      setConfig(updated);
      setInitialConfig(updated);
      setMessage('Platform-wide configuration updated and persisted successfully.');
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

  // Reusable Section handlers
  const handleOpenCreateSection = () => {
    setEditingSection(null);
    setSectionForm({
      name: '',
      code: '',
      description: '',
      is_active: true,
    });
    setSectionError('');
    setSectionModalOpen(true);
  };

  const handleOpenEditSection = (section: AdminSection) => {
    setEditingSection(section);
    setSectionForm({
      name: section.name,
      code: section.code,
      description: section.description || '',
      is_active: section.is_active,
    });
    setSectionError('');
    setSectionModalOpen(true);
  };

  const handleSaveSection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sectionForm.name.trim() || !sectionForm.code.trim()) {
      setSectionError('Section name and code are required.');
      return;
    }

    setSectionSaving(true);
    setSectionError('');
    try {
      if (editingSection) {
        await updateAdminSection(editingSection.id, {
          name: sectionForm.name.trim(),
          code: sectionForm.code.trim().toUpperCase(),
          description: sectionForm.description.trim(),
          is_active: sectionForm.is_active,
        });
        setSectionSuccess(`Section "${sectionForm.name}" updated successfully.`);
      } else {
        await createAdminSection({
          name: sectionForm.name.trim(),
          code: sectionForm.code.trim().toUpperCase(),
          description: sectionForm.description.trim(),
          is_active: sectionForm.is_active,
        });
        setSectionSuccess(`New section "${sectionForm.name}" created and added to the reusable library.`);
      }
      setSectionModalOpen(false);
      loadSections();
    } catch (err: any) {
      const msg = err.response?.data?.code?.[0] || err.response?.data?.detail || 'Failed to save section.';
      setSectionError(msg);
    } finally {
      setSectionSaving(false);
    }
  };

  const handleDeleteSection = async (section: AdminSection) => {
    const confirmDelete = window.confirm(
      `Are you sure you want to delete the reusable section "${section.name}" (${section.code})?\n\nNote: If this section is referenced by existing assessments or question records, deletion will be safely rejected.`
    );
    if (!confirmDelete) return;

    setSectionError('');
    setSectionSuccess('');
    try {
      const res = await deleteAdminSection(section.id);
      setSectionSuccess(res.message || `Section "${section.name}" deleted successfully.`);
      loadSections();
    } catch (err: any) {
      const detailMsg = err.response?.data?.detail || err.message || 'Cannot delete section.';
      alert(`Deletion Denied: ${detailMsg}`);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '64px', textAlign: 'center', color: '#64748B' }}>
        <div style={{ fontSize: '14px', fontWeight: 600 }}>Loading platform configuration...</div>
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

  return (
    <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '24px 16px' }}>
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
            Platform Policy & Section Library
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Authoritative platform-wide parameters, attempt policies, and the centralized library of reusable assessment sections.
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
                <span>Save Platform Policies</span>
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

      {/* Architecture Separation Callout */}
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
            Platform-Wide Governance Active
          </strong>
          Parameters configured here apply as global defaults and security guardrails across the platform.
          Specific assessment rounds independently define their own timing, total marks, and section allocations under
          the <strong>Assessments</strong> tab.
        </div>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginBottom: '40px' }}>
        {/* Section 1: Assessment Portal Identity & Defaults */}
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
              1. Platform Assessment Identity & Status
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Default Assessment Portal Title
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
                Displayed as the fallback title on candidate registration and test instructions.
              </span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Assessment Engine Active
              </label>
              <select
                name="is_active"
                value={config.is_active ? 'true' : 'false'}
                onChange={(e) => setConfig({ ...config, is_active: e.target.value === 'true' })}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  outlineColor: '#1455B8',
                  boxSizing: 'border-box',
                  backgroundColor: '#FFFFFF',
                  fontWeight: 600,
                }}
              >
                <option value="true">Enabled (Accepting Test Sessions)</option>
                <option value="false">Disabled (Maintenance Mode)</option>
              </select>
              <span style={{ fontSize: '11px', color: '#64748B', marginTop: '4px', display: 'block' }}>
                Global switch governing student assessment eligibility.
              </span>
            </div>
          </div>

          <div style={{ marginTop: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
              Default Instructions & Guidelines
            </label>
            <textarea
              name="description"
              rows={3}
              value={config.description || ''}
              onChange={handleChange}
              placeholder="Candidate instructions shown when assessment-specific description is omitted..."
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '13px',
                outlineColor: '#1455B8',
                boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Section 2: Proctoring & Attempt Policy */}
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
              2. Platform Proctoring & Attempt Policies
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Default Max Attempts per Candidate
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
      </form>

      {/* ─────────────────────────────────────────────────────────────────────────────
          SECTION 3: REUSABLE ASSESSMENT SECTION LIBRARY
          ───────────────────────────────────────────────────────────────────────────── */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '14px',
          border: '1px solid #E2E8F0',
          padding: '24px',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
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
                  <rect x="3" y="3" width="7" height="7"></rect>
                  <rect x="14" y="3" width="7" height="7"></rect>
                  <rect x="14" y="14" width="7" height="7"></rect>
                  <rect x="3" y="14" width="7" height="7"></rect>
                </svg>
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Reusable Assessment Section Library
              </h3>
            </div>
            <p style={{ fontSize: '13px', color: '#64748B', margin: '4px 0 0 0' }}>
              Define reusable sections (e.g. Aptitude, Coding, Logical Reasoning, Verbal). Selected sections can be dynamically allocated to any assessment.
            </p>
          </div>

          <button
            type="button"
            onClick={handleOpenCreateSection}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '9px 16px',
              backgroundColor: '#0B2E6F',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 2px 6px rgba(11, 46, 111, 0.15)',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            + Create Reusable Section
          </button>
        </div>

        {sectionSuccess && (
          <div
            style={{
              padding: '10px 14px',
              backgroundColor: '#ECFDF5',
              border: '1px solid #A7F3D0',
              color: '#065F46',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              marginBottom: '16px',
            }}
          >
            {sectionSuccess}
          </div>
        )}

        {/* Section Table */}
        {sectionsLoading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748B', fontSize: '13px' }}>
            Loading sections library...
          </div>
        ) : sections.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748B', fontSize: '13px' }}>
            No reusable sections defined yet. Click "+ Create Reusable Section" to create one.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', border: '1px solid #E2E8F0', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569' }}>SECTION CODE</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569' }}>NAME & DESCRIPTION</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>QUESTIONS POOL</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>ASSESSMENTS USING</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>STATUS</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {sections.map((sec) => (
                  <tr key={sec.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '12px 14px' }}>
                      <span
                        style={{
                          backgroundColor: '#EEF2FF',
                          color: '#3730A3',
                          fontWeight: 700,
                          fontSize: '11px',
                          padding: '3px 8px',
                          borderRadius: '4px',
                        }}
                      >
                        {sec.code}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontWeight: 700, color: '#0F172A' }}>{sec.name}</div>
                      {sec.description && (
                        <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>
                          {sec.description}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 700, color: '#0B2E6F' }}>
                      {sec.question_count ?? 0}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 700, color: '#0B2E6F' }}>
                      {sec.assessment_count ?? 0}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '10px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: sec.is_active ? '#DCFCE7' : '#F1F5F9',
                          color: sec.is_active ? '#15803D' : '#64748B',
                        }}
                      >
                        {sec.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          onClick={() => handleOpenEditSection(sec)}
                          style={{
                            padding: '4px 10px',
                            backgroundColor: '#FEF3C7',
                            color: '#92400E',
                            border: '1px solid #FDE68A',
                            borderRadius: '5px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteSection(sec)}
                          style={{
                            padding: '4px 10px',
                            backgroundColor: '#FFF1F2',
                            color: '#BE123C',
                            border: '1px solid #FDA4AF',
                            borderRadius: '5px',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          CREATE / EDIT SECTION MODAL
          ───────────────────────────────────────────────────────────────────────────── */}
      {sectionModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '24px 28px',
              width: '460px',
              maxWidth: '90vw',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '17px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                {editingSection ? `Edit Section: ${editingSection.name}` : 'Create Reusable Section'}
              </h3>
              <button
                type="button"
                onClick={() => setSectionModalOpen(false)}
                style={{ background: 'none', border: 'none', fontSize: '18px', cursor: 'pointer', color: '#94A3B8' }}
              >
                ✕
              </button>
            </div>

            {sectionError && (
              <div
                style={{
                  padding: '8px 12px',
                  backgroundColor: '#FEF2F2',
                  border: '1px solid #FCA5A5',
                  color: '#B91C1C',
                  borderRadius: '6px',
                  fontSize: '12px',
                  marginBottom: '14px',
                }}
              >
                {sectionError}
              </div>
            )}

            <form onSubmit={handleSaveSection}>
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Section Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Logical Reasoning, Verbal Ability"
                  value={sectionForm.name}
                  onChange={(e) => setSectionForm({ ...sectionForm, name: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Section Code * (Uppercase, Unique)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. LOGICAL, VERBAL, CODING"
                  value={sectionForm.code}
                  onChange={(e) => setSectionForm({ ...sectionForm, code: e.target.value.toUpperCase() })}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                    textTransform: 'uppercase',
                  }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Description (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="Purpose or focus topics of this section..."
                  value={sectionForm.description}
                  onChange={(e) => setSectionForm({ ...sectionForm, description: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="section-is-active"
                  checked={sectionForm.is_active}
                  onChange={(e) => setSectionForm({ ...sectionForm, is_active: e.target.checked })}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="section-is-active" style={{ fontSize: '13px', color: '#334155', cursor: 'pointer', fontWeight: 600 }}>
                  Active (Available for assessment allocation)
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setSectionModalOpen(false)}
                  style={{
                    backgroundColor: '#F1F5F9',
                    color: '#475569',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '8px 14px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sectionSaving}
                  style={{
                    backgroundColor: '#0B2E6F',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '8px 18px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {sectionSaving ? 'Saving...' : editingSection ? 'Save Changes' : 'Create Section'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
