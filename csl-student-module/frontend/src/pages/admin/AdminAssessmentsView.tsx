import React, { useState, useEffect } from 'react';
import {
  getAdminAssessments,
  getAdminAssessmentDetail,
  createAdminAssessment,
  prepareAdminAssessment,
  openAdminAssessment,
  closeAdminAssessment,
  archiveAdminAssessment,
  assignAdminAssessmentColleges,
  releaseAdminAssessmentResults,
  getAdminColleges,
  type AdminAssessment,
  type AdminAssessmentDetail,
  type AdminCollege,
} from '../../api/admin';

export function AdminAssessmentsView() {
  const [assessments, setAssessments] = useState<AdminAssessment[]>([]);
  const [colleges, setColleges] = useState<AdminCollege[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);

  // Selected assessment for actions
  const [selectedAssessment, setSelectedAssessment] = useState<AdminAssessment | null>(null);
  const [assessmentDetail, setAssessmentDetail] = useState<AdminAssessmentDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Close Assessment policy selection
  const [closePolicy, setClosePolicy] = useState<'ALLOW_FINISH' | 'STRICT_CUTOFF'>('ALLOW_FINISH');
  const [closing, setClosing] = useState(false);

  // Detail tab state
  const [detailTab, setDetailTab] = useState<'overview' | 'colleges' | 'audit'>('overview');
  const [selectedCollegeIdsForAssign, setSelectedCollegeIdsForAssign] = useState<number[]>([]);
  const [savingColleges, setSavingColleges] = useState(false);

  // Create Form State
  const [createForm, setCreateForm] = useState({
    code: '',
    title: '',
    description: '',
    duration_minutes: 60,
    total_marks: 50,
    aptitude_count: 25,
    coding_count: 25,
    max_attempts: 1,
    max_tab_switches_warning: 2,
    auto_submit_on_tab_limit: true,
    close_policy: 'ALLOW_FINISH' as 'ALLOW_FINISH' | 'STRICT_CUTOFF',
    eligible_college_ids: [] as number[],
  });
  const [createError, setCreateError] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchAssessments = async () => {
    setLoading(true);
    try {
      const data = await getAdminAssessments({
        search: search.trim() || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
      });
      setAssessments(data);
    } catch (err) {
      console.error('Failed to fetch assessments:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchColleges = async () => {
    try {
      const data = await getAdminColleges({ is_active: 'true' });
      setColleges(data);
    } catch (err) {
      console.error('Failed to fetch colleges list:', err);
    }
  };

  useEffect(() => {
    fetchAssessments();
    fetchColleges();
  }, [search, statusFilter]);

  const handleOpenDetail = async (assessment: AdminAssessment) => {
    setSelectedAssessment(assessment);
    setDetailTab('overview');
    setShowDetailModal(true);
    setLoadingDetail(true);
    try {
      const detail = await getAdminAssessmentDetail(assessment.id);
      setAssessmentDetail(detail);
      setSelectedCollegeIdsForAssign(detail.eligible_colleges.map((c) => c.id));
    } catch (err) {
      console.error('Failed to fetch assessment detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handlePrepare = async (assessment: AdminAssessment) => {
    setActionMessage(null);
    try {
      const res = await prepareAdminAssessment(assessment.id);
      setActionMessage({ text: res.message, type: 'success' });
      fetchAssessments();
      if (assessmentDetail && assessmentDetail.id === assessment.id) {
        handleOpenDetail(assessment);
      }
    } catch (err: any) {
      setActionMessage({ text: err.response?.data?.detail || 'Failed to prepare assessment.', type: 'error' });
    }
  };

  const handleOpen = async (assessment: AdminAssessment) => {
    setActionMessage(null);
    try {
      const res = await openAdminAssessment(assessment.id);
      setActionMessage({ text: res.message, type: 'success' });
      fetchAssessments();
      if (assessmentDetail && assessmentDetail.id === assessment.id) {
        handleOpenDetail(assessment);
      }
    } catch (err: any) {
      setActionMessage({ text: err.response?.data?.detail || 'Failed to open assessment.', type: 'error' });
    }
  };

  const handleOpenCloseModal = (assessment: AdminAssessment) => {
    setSelectedAssessment(assessment);
    setClosePolicy(assessment.close_policy || 'ALLOW_FINISH');
    setShowCloseModal(true);
  };

  const handleConfirmClose = async () => {
    if (!selectedAssessment) return;
    setClosing(true);
    setActionMessage(null);
    try {
      const res = await closeAdminAssessment(selectedAssessment.id, closePolicy);
      setActionMessage({ text: res.message, type: 'success' });
      setShowCloseModal(false);
      fetchAssessments();
      if (assessmentDetail && assessmentDetail.id === selectedAssessment.id) {
        handleOpenDetail(selectedAssessment);
      }
    } catch (err: any) {
      setActionMessage({ text: err.response?.data?.detail || 'Failed to close assessment.', type: 'error' });
    } finally {
      setClosing(false);
    }
  };

  const handleArchive = async (assessment: AdminAssessment) => {
    if (!window.confirm(`Archive assessment "${assessment.title}"?`)) return;
    setActionMessage(null);
    try {
      const res = await archiveAdminAssessment(assessment.id);
      setActionMessage({ text: res.message, type: 'success' });
      fetchAssessments();
    } catch (err: any) {
      setActionMessage({ text: err.response?.data?.detail || 'Failed to archive assessment.', type: 'error' });
    }
  };

  const handleSaveColleges = async () => {
    if (!assessmentDetail) return;
    setSavingColleges(true);
    try {
      const res = await assignAdminAssessmentColleges(assessmentDetail.id, selectedCollegeIdsForAssign);
      setActionMessage({ text: res.message, type: 'success' });
      fetchAssessments();
      handleOpenDetail(assessmentDetail);
    } catch (err: any) {
      setActionMessage({ text: err.response?.data?.detail || 'Failed to assign colleges.', type: 'error' });
    } finally {
      setSavingColleges(false);
    }
  };

  const handleToggleReleaseResults = async (assessment: AdminAssessment, release: boolean) => {
    try {
      await releaseAdminAssessmentResults(assessment.id, release);
      setAssessments((prev) =>
        prev.map((a) => (a.id === assessment.id ? { ...a, is_results_released: release } : a))
      );
      if (selectedAssessment?.id === assessment.id) {
        setSelectedAssessment((prev) => (prev ? { ...prev, is_results_released: release } : null));
      }
      setActionMessage({
        text: `Results for assessment "${assessment.title}" are now ${release ? 'RELEASED to candidates' : 'WITHHELD'}.`,
        type: 'success',
      });
    } catch {
      setActionMessage({ text: 'Failed to update result release status.', type: 'error' });
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    if (!createForm.code.trim()) {
      setCreateError('Assessment code is required.');
      return;
    }
    if (!createForm.title.trim()) {
      setCreateError('Assessment title is required.');
      return;
    }
    const total = Number(createForm.aptitude_count) + Number(createForm.coding_count);
    setCreateSubmitting(true);
    try {
      await createAdminAssessment({
        ...createForm,
        code: createForm.code.trim().toUpperCase(),
        total_marks: total,
      });
      setShowCreateModal(false);
      fetchAssessments();
      setActionMessage({ text: `Assessment "${createForm.title}" created successfully in DRAFT state.`, type: 'success' });
    } catch (err: any) {
      const msg = err.response?.data?.code?.[0] || err.response?.data?.detail || 'Failed to create assessment.';
      setCreateError(msg);
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Metrics
  const totalCount = assessments.length;
  const openCount = assessments.filter((a) => a.is_open).length;
  const totalAttempts = assessments.reduce((acc, a) => acc + (a.attempts_count || 0), 0);

  const getStatusBadge = (status: string, isOpen: boolean) => {
    let bg = '#F1F5F9';
    let color = '#475569';
    if (isOpen || status === 'OPEN') {
      bg = '#DCFCE7';
      color = '#15803D';
    } else if (status === 'READY') {
      bg = '#DBEAFE';
      color = '#1D4ED8';
    } else if (status === 'SCHEDULED') {
      bg = '#FEF9C3';
      color = '#A16207';
    } else if (status === 'CLOSED') {
      bg = '#F3E8FF';
      color = '#7E22CE';
    } else if (status === 'ARCHIVED') {
      bg = '#E2E8F0';
      color = '#334155';
    }

    return (
      <span
        style={{
          display: 'inline-block',
          padding: '3px 8px',
          borderRadius: '12px',
          fontSize: '11px',
          fontWeight: 800,
          backgroundColor: bg,
          color,
          letterSpacing: '0.04em',
        }}
      >
        {status}
      </span>
    );
  };

  return (
    <div style={{ padding: '24px 32px' }}>
      {/* ─── HEADER & ACTIONS ───────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
            Assessment Lifecycle Management
          </h1>
          <p style={{ margin: '4px 0 0', color: '#556987', fontSize: '14px' }}>
            Configure independent diagnostic rounds, assign participating colleges, and control server-side opening states.
          </p>
        </div>
        <button
          onClick={() => {
            setCreateError('');
            setShowCreateModal(true);
          }}
          style={{
            backgroundColor: '#0B2E6F',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 18px',
            fontWeight: 700,
            fontSize: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(11,46,111,0.15)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Create New Assessment
        </button>
      </div>

      {actionMessage && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            marginBottom: '20px',
            fontSize: '14px',
            fontWeight: 600,
            backgroundColor: actionMessage.type === 'success' ? '#F0FDF4' : '#FEF2F2',
            color: actionMessage.type === 'success' ? '#15803D' : '#B91C1C',
            border: `1px solid ${actionMessage.type === 'success' ? '#BBF7D0' : '#FECDD3'}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>{actionMessage.text}</span>
          <button
            onClick={() => setActionMessage(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ─── KPI SUMMARY CARDS ──────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Assessments Total</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0B2E6F', marginTop: '6px' }}>{totalCount}</div>
        </div>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#16A34A', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active (Open)</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#16A34A', marginTop: '6px' }}>{openCount} <span style={{ fontSize: '14px', color: '#64748B', fontWeight: 500 }}>/ {totalCount}</span></div>
        </div>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#6366F1', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Attempts Recorded</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#6366F1', marginTop: '6px' }}>{totalAttempts}</div>
        </div>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Enrolled Colleges</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0B2E6F', marginTop: '6px' }}>{colleges.length}</div>
        </div>
      </div>

      {/* ─── CONTROLS: SEARCH & STATUS ──────────────────────────────── */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            type="text"
            placeholder="Search assessments by code, title, or instructions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 14px 10px 38px',
              borderRadius: '8px',
              border: '1px solid #CBD5E1',
              fontSize: '14px',
              boxSizing: 'border-box',
              outline: 'none',
              backgroundColor: '#FFFFFF',
            }}
          />
          <svg
            width="16"
            height="16"
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
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '14px',
            backgroundColor: '#FFFFFF',
            cursor: 'pointer',
            outline: 'none',
            fontWeight: 500,
          }}
        >
          <option value="all">All Lifecycle States</option>
          <option value="DRAFT">DRAFT</option>
          <option value="READY">READY</option>
          <option value="SCHEDULED">SCHEDULED</option>
          <option value="OPEN">OPEN (Accepting Attempts)</option>
          <option value="CLOSED">CLOSED</option>
          <option value="ARCHIVED">ARCHIVED</option>
        </select>
      </div>

      {/* ─── ASSESSMENTS TABLE ──────────────────────────────────────── */}
      <div style={{ backgroundColor: '#FFFFFF', borderRadius: '10px', border: '1px solid #E2E8F0', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
        {loading ? (
          <div style={{ padding: '48px', textAlign: 'center', color: '#64748B', fontWeight: 600 }}>
            Loading assessments...
          </div>
        ) : assessments.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
            <div style={{ fontWeight: 700, fontSize: '16px', color: '#0B2E6F', marginBottom: '6px' }}>No assessments found</div>
            <p style={{ margin: 0, fontSize: '14px' }}>Click "Create New Assessment" to configure your first round.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', width: '120px' }}>CODE</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>ASSESSMENT TITLE</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>STATUS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>DURATION & MARKS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>COLLEGES</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>ATTEMPTS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>LIFECYCLE CONTROLS</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => (
                <tr key={a.id} style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.15s' }}>
                  <td style={{ padding: '14px 16px' }}>
                    <span
                      style={{
                        backgroundColor: '#EEF2FF',
                        color: '#3730A3',
                        fontWeight: 700,
                        fontSize: '12px',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        letterSpacing: '0.02em',
                      }}
                    >
                      {a.code}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 700, color: '#0F172A' }}>{a.title}</div>
                    {a.description && (
                      <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {a.description}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    {getStatusBadge(a.status, a.is_open)}
                    <div style={{ marginTop: '4px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: a.is_results_released ? '#DCFCE7' : '#FEF3C7',
                          color: a.is_results_released ? '#15803D' : '#92400E',
                        }}
                      >
                        {a.is_results_released ? 'Results Released' : 'Results Withheld'}
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#475569' }}>
                    <div><strong>{a.duration_minutes}</strong> mins • <strong>{a.total_marks}</strong> marks</div>
                    <div style={{ fontSize: '12px', color: '#64748B' }}>
                      {a.aptitude_count} Aptitude + {a.coding_count} Coding
                    </div>
                    <div style={{ fontSize: '11px', marginTop: '3px' }}>
                      <span
                        style={{
                          fontWeight: 700,
                          color: a.pool_sufficient ? '#16A34A' : '#DC2626',
                        }}
                      >
                        Pool: {a.pool_questions_count || 0} Qs ({a.pool_sufficient ? '✓ Sufficient' : '⚠ Insufficient'})
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    <span
                      style={{
                        backgroundColor: a.eligible_colleges_count > 0 ? '#F0F9FF' : '#FEF2F2',
                        color: a.eligible_colleges_count > 0 ? '#0369A1' : '#B91C1C',
                        fontWeight: 700,
                        fontSize: '12px',
                        padding: '4px 8px',
                        borderRadius: '6px',
                      }}
                    >
                      {a.eligible_colleges_count} colleges
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    <div style={{ fontWeight: 700, color: '#0B2E6F' }}>{a.attempts_count}</div>
                    <div style={{ fontSize: '11px', color: '#64748B' }}>
                      {a.in_progress_count} active / {a.submitted_count} submitted
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', alignItems: 'center' }}>
                      {/* State transition triggers */}
                      {a.status === 'DRAFT' && (
                        <button
                          onClick={() => handlePrepare(a)}
                          title="Verify question bank sufficiency and mark READY"
                          style={{
                            backgroundColor: '#EFF6FF',
                            color: '#1D4ED8',
                            border: '1px solid #BFDBFE',
                            padding: '6px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Verify & Ready
                        </button>
                      )}

                      {(a.status === 'READY' || a.status === 'SCHEDULED' || a.status === 'CLOSED') && (
                        <button
                          onClick={() => handleOpen(a)}
                          title="Open assessment for candidate attempts"
                          style={{
                            backgroundColor: '#DCFCE7',
                            color: '#15803D',
                            border: '1px solid #86EFAC',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Open Now
                        </button>
                      )}

                      {a.status === 'OPEN' && (
                        <button
                          onClick={() => handleOpenCloseModal(a)}
                          title="Close assessment and stop new attempts"
                          style={{
                            backgroundColor: '#FEE2E2',
                            color: '#B91C1C',
                            border: '1px solid #FCA5A5',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Close Assessment
                        </button>
                      )}

                      {a.status === 'CLOSED' && (
                        <button
                          onClick={() => handleArchive(a)}
                          title="Archive assessment"
                          style={{
                            backgroundColor: '#F1F5F9',
                            color: '#475569',
                            border: '1px solid #CBD5E1',
                            padding: '6px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Archive
                        </button>
                      )}

                      {a.is_results_released ? (
                        <button
                          onClick={() => handleToggleReleaseResults(a, false)}
                          title="Withhold results so students only see completion pending state"
                          style={{
                            backgroundColor: '#FFFBEB',
                            color: '#92400E',
                            border: '1px solid #FDE68A',
                            padding: '6px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Withhold Results
                        </button>
                      ) : (
                        <button
                          onClick={() => handleToggleReleaseResults(a, true)}
                          title="Release results so students can view scorecards and breakdown"
                          style={{
                            backgroundColor: '#F3E8FF',
                            color: '#6B21A8',
                            border: '1px solid #D8B4FE',
                            padding: '6px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Release Results
                        </button>
                      )}

                      <button
                        onClick={() => handleOpenDetail(a)}
                        title="Manage colleges, parameters, and audit trail"
                        style={{
                          backgroundColor: '#0B2E6F',
                          color: '#FFFFFF',
                          border: 'none',
                          padding: '6px 12px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        Details
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ─── CREATE ASSESSMENT MODAL ─────────────────────────────────── */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
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
              padding: '28px',
              width: '680px',
              maxWidth: '92vw',
              maxHeight: '92vh',
              overflowY: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                  Create New Assessment Round
                </h2>
                <span style={{ fontSize: '13px', color: '#64748B' }}>
                  Self-contained assessment with independent questions, thresholds, and institutional enrollment.
                </span>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#94A3B8' }}
              >
                ✕
              </button>
            </div>

            {createError && (
              <div style={{ padding: '10px 14px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', color: '#B91C1C', borderRadius: '6px', fontSize: '13px', marginBottom: '16px' }}>
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Assessment Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. CSL-DIAG-02"
                    value={createForm.code}
                    onChange={(e) => setCreateForm({ ...createForm, code: e.target.value.toUpperCase() })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box', textTransform: 'uppercase' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Title *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. CSL Diagnostic Assessment — Phase 2"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Candidate Instructions / Description
                </label>
                <textarea
                  rows={2}
                  placeholder="Instructions presented to candidates before starting..."
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Duration (Minutes)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={createForm.duration_minutes}
                    onChange={(e) => setCreateForm({ ...createForm, duration_minutes: Number(e.target.value) })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Aptitude Questions
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={createForm.aptitude_count}
                    onChange={(e) => setCreateForm({ ...createForm, aptitude_count: Number(e.target.value) })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Coding Questions
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={createForm.coding_count}
                    onChange={(e) => setCreateForm({ ...createForm, coding_count: Number(e.target.value) })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Permitted Tab Switch Warnings
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={createForm.max_tab_switches_warning}
                    onChange={(e) => setCreateForm({ ...createForm, max_tab_switches_warning: Number(e.target.value) })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                  <span style={{ fontSize: '11px', color: '#64748B' }}>Default: 2 warnings (3rd switch auto-submits)</span>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Close Policy
                  </label>
                  <select
                    value={createForm.close_policy}
                    onChange={(e) => setCreateForm({ ...createForm, close_policy: e.target.value as any })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  >
                    <option value="ALLOW_FINISH">Allow in-progress attempts to finish</option>
                    <option value="STRICT_CUTOFF">Strict cutoff (terminate active attempts immediately)</option>
                  </select>
                </div>
              </div>

              {/* Eligible Colleges Selection */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                  Assign Participating Colleges ({createForm.eligible_college_ids.length} selected)
                </label>
                <div style={{ border: '1px solid #CBD5E1', borderRadius: '6px', padding: '10px', maxHeight: '140px', overflowY: 'auto', backgroundColor: '#F8FAFC' }}>
                  {colleges.map((c) => {
                    const isChecked = createForm.eligible_college_ids.includes(c.id);
                    return (
                      <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0', fontSize: '13px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setCreateForm({ ...createForm, eligible_college_ids: [...createForm.eligible_college_ids, c.id] });
                            } else {
                              setCreateForm({
                                ...createForm,
                                eligible_college_ids: createForm.eligible_college_ids.filter((id) => id !== c.id),
                              });
                            }
                          }}
                        />
                        <strong>[{c.code}]</strong> {c.name}
                      </label>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ backgroundColor: '#F1F5F9', color: '#475569', border: 'none', borderRadius: '6px', padding: '10px 16px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createSubmitting}
                  style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '10px 20px', fontWeight: 700, cursor: 'pointer' }}
                >
                  {createSubmitting ? 'Creating Assessment...' : 'Create Assessment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── CLOSE ASSESSMENT CONFIRMATION MODAL ─────────────────────── */}
      {showCloseModal && selectedAssessment && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
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
              width: '480px',
              maxWidth: '90vw',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#B91C1C', margin: '0 0 10px' }}>
              Close Assessment: {selectedAssessment.title}
            </h2>
            <p style={{ fontSize: '13px', color: '#475569', margin: '0 0 16px', lineHeight: 1.5 }}>
              Closing this assessment will immediately prevent candidates from beginning new attempts.
              Please select the cutoff policy for candidates currently taking this assessment:
            </p>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', padding: '10px', borderRadius: '6px', border: '1px solid #CBD5E1', marginBottom: '8px', cursor: 'pointer', backgroundColor: closePolicy === 'ALLOW_FINISH' ? '#F0F9FF' : '#FFFFFF' }}>
                <input
                  type="radio"
                  name="closePolicy"
                  value="ALLOW_FINISH"
                  checked={closePolicy === 'ALLOW_FINISH'}
                  onChange={() => setClosePolicy('ALLOW_FINISH')}
                  style={{ marginRight: '8px' }}
                />
                <strong>Allow Finish:</strong> Let candidates with active in-progress attempts complete until their deadline.
              </label>

              <label style={{ display: 'block', padding: '10px', borderRadius: '6px', border: '1px solid #CBD5E1', cursor: 'pointer', backgroundColor: closePolicy === 'STRICT_CUTOFF' ? '#FEF2F2' : '#FFFFFF' }}>
                <input
                  type="radio"
                  name="closePolicy"
                  value="STRICT_CUTOFF"
                  checked={closePolicy === 'STRICT_CUTOFF'}
                  onChange={() => setClosePolicy('STRICT_CUTOFF')}
                  style={{ marginRight: '8px' }}
                />
                <strong>Strict Cutoff:</strong> Immediately terminate and score all active attempts right now.
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setShowCloseModal(false)}
                style={{ backgroundColor: '#F1F5F9', color: '#475569', border: 'none', borderRadius: '6px', padding: '8px 16px', fontWeight: 600, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={closing}
                onClick={handleConfirmClose}
                style={{ backgroundColor: '#B91C1C', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '8px 18px', fontWeight: 700, cursor: 'pointer' }}
              >
                {closing ? 'Closing...' : 'Confirm Close'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── ASSESSMENT DETAIL & AUDIT MODAL ─────────────────────────── */}
      {showDetailModal && selectedAssessment && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
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
              padding: '28px',
              width: '800px',
              maxWidth: '92vw',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                    {selectedAssessment.title}
                  </h2>
                  <span style={{ backgroundColor: '#EEF2FF', color: '#3730A3', fontWeight: 700, fontSize: '12px', padding: '2px 8px', borderRadius: '4px' }}>
                    {selectedAssessment.code}
                  </span>
                  {getStatusBadge(selectedAssessment.status, selectedAssessment.is_open)}
                </div>
                <div style={{ fontSize: '13px', color: '#64748B', marginTop: '4px' }}>
                  {selectedAssessment.duration_minutes} Minutes • {selectedAssessment.total_marks} Marks ({selectedAssessment.aptitude_count} Aptitude + {selectedAssessment.coding_count} Coding)
                </div>
              </div>
              <button
                onClick={() => setShowDetailModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '22px', cursor: 'pointer', color: '#94A3B8' }}
              >
                ✕
              </button>
            </div>

            {/* TAB SELECTOR */}
            <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #E2E8F0', marginBottom: '20px' }}>
              <button
                onClick={() => setDetailTab('overview')}
                style={{
                  padding: '8px 16px',
                  fontWeight: 700,
                  fontSize: '13px',
                  border: 'none',
                  borderBottom: detailTab === 'overview' ? '2px solid #0B2E6F' : '2px solid transparent',
                  color: detailTab === 'overview' ? '#0B2E6F' : '#64748B',
                  background: 'none',
                  cursor: 'pointer',
                }}
              >
                Overview & Sessions
              </button>
              <button
                onClick={() => setDetailTab('colleges')}
                style={{
                  padding: '8px 16px',
                  fontWeight: 700,
                  fontSize: '13px',
                  border: 'none',
                  borderBottom: detailTab === 'colleges' ? '2px solid #0B2E6F' : '2px solid transparent',
                  color: detailTab === 'colleges' ? '#0B2E6F' : '#64748B',
                  background: 'none',
                  cursor: 'pointer',
                }}
              >
                Assigned Colleges ({selectedCollegeIdsForAssign.length})
              </button>
              <button
                onClick={() => setDetailTab('audit')}
                style={{
                  padding: '8px 16px',
                  fontWeight: 700,
                  fontSize: '13px',
                  border: 'none',
                  borderBottom: detailTab === 'audit' ? '2px solid #0B2E6F' : '2px solid transparent',
                  color: detailTab === 'audit' ? '#0B2E6F' : '#64748B',
                  background: 'none',
                  cursor: 'pointer',
                }}
              >
                Audit Trail ({assessmentDetail?.audit_logs?.length || 0})
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: '36px', textAlign: 'center', color: '#64748B' }}>Loading assessment configuration...</div>
            ) : assessmentDetail ? (
              <div>
                {/* 1. OVERVIEW TAB */}
                {detailTab === 'overview' && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
                      <div style={{ background: '#F8FAFC', padding: '12px', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                        <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Total Attempts</div>
                        <div style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', marginTop: '4px' }}>{assessmentDetail.attempts_count}</div>
                      </div>
                      <div style={{ background: '#F8FAFC', padding: '12px', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                        <div style={{ fontSize: '11px', color: '#16A34A', fontWeight: 700, textTransform: 'uppercase' }}>In Progress</div>
                        <div style={{ fontSize: '20px', fontWeight: 800, color: '#16A34A', marginTop: '4px' }}>{assessmentDetail.in_progress_count}</div>
                      </div>
                      <div style={{ background: '#F8FAFC', padding: '12px', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                        <div style={{ fontSize: '11px', color: '#2563EB', fontWeight: 700, textTransform: 'uppercase' }}>Submitted</div>
                        <div style={{ fontSize: '20px', fontWeight: 800, color: '#2563EB', marginTop: '4px' }}>{assessmentDetail.submitted_count}</div>
                      </div>
                    </div>

                    <div style={{ backgroundColor: '#F8FAFC', padding: '14px', borderRadius: '8px', border: '1px solid #E2E8F0', marginBottom: '16px', fontSize: '13px' }}>
                      <div style={{ fontWeight: 700, color: '#334155', marginBottom: '6px' }}>Proctoring & Rules</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <div>Max Tab Warnings: <strong>{assessmentDetail.max_tab_switches_warning}</strong> (Auto-submit: {assessmentDetail.auto_submit_on_tab_limit ? 'Yes' : 'No'})</div>
                        <div>Max Attempts per Student: <strong>{assessmentDetail.max_attempts}</strong></div>
                        <div>Close Policy: <strong>{assessmentDetail.close_policy}</strong></div>
                        <div>Opened: <strong>{assessmentDetail.opened_at ? new Date(assessmentDetail.opened_at).toLocaleString() : 'Not opened yet'}</strong></div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 2. ASSIGNED COLLEGES TAB */}
                {detailTab === 'colleges' && (
                  <div>
                    <p style={{ fontSize: '13px', color: '#64748B', marginTop: 0, marginBottom: '14px' }}>
                      Select which participating institutions are eligible to register candidates and take this assessment.
                    </p>
                    <div style={{ border: '1px solid #E2E8F0', borderRadius: '8px', padding: '12px', maxHeight: '240px', overflowY: 'auto', backgroundColor: '#F8FAFC', marginBottom: '16px' }}>
                      {colleges.map((c) => {
                        const isChecked = selectedCollegeIdsForAssign.includes(c.id);
                        return (
                          <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 4px', fontSize: '13px', cursor: 'pointer', borderBottom: '1px solid #F1F5F9' }}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedCollegeIdsForAssign([...selectedCollegeIdsForAssign, c.id]);
                                } else {
                                  setSelectedCollegeIdsForAssign(selectedCollegeIdsForAssign.filter((id) => id !== c.id));
                                }
                              }}
                            />
                            <span style={{ fontWeight: 700, color: '#3730A3', backgroundColor: '#EEF2FF', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>{c.code}</span>
                            <span>{c.name}</span>
                            <span style={{ marginLeft: 'auto', color: '#64748B', fontSize: '12px' }}>{c.candidates_count || 0} students</span>
                          </label>
                        );
                      })}
                    </div>
                    <button
                      type="button"
                      disabled={savingColleges}
                      onClick={handleSaveColleges}
                      style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '8px 18px', fontWeight: 700, fontSize: '13px', cursor: 'pointer' }}
                    >
                      {savingColleges ? 'Updating Enrollment...' : 'Save College Assignments'}
                    </button>
                  </div>
                )}

                {/* 3. AUDIT TRAIL TAB */}
                {detailTab === 'audit' && (
                  <div>
                    {assessmentDetail.audit_logs && assessmentDetail.audit_logs.length > 0 ? (
                      <div style={{ border: '1px solid #E2E8F0', borderRadius: '8px', overflow: 'hidden', maxHeight: '280px', overflowY: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                          <thead>
                            <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                              <th style={{ padding: '8px 12px', fontWeight: 700 }}>TIMESTAMP</th>
                              <th style={{ padding: '8px 12px', fontWeight: 700 }}>ACTION</th>
                              <th style={{ padding: '8px 12px', fontWeight: 700 }}>PERFORMED BY</th>
                              <th style={{ padding: '8px 12px', fontWeight: 700 }}>DETAILS</th>
                            </tr>
                          </thead>
                          <tbody>
                            {assessmentDetail.audit_logs.map((log) => (
                              <tr key={log.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                                <td style={{ padding: '8px 12px', color: '#64748B', whiteSpace: 'nowrap' }}>
                                  {new Date(log.timestamp).toLocaleString()}
                                </td>
                                <td style={{ padding: '8px 12px', fontWeight: 700, color: '#0B2E6F' }}>
                                  {log.action}
                                </td>
                                <td style={{ padding: '8px 12px' }}>
                                  {log.performed_by_name || 'System'}
                                </td>
                                <td style={{ padding: '8px 12px', color: '#475569' }}>
                                  <code style={{ fontSize: '11px', background: '#F1F5F9', padding: '2px 4px', borderRadius: '3px' }}>
                                    {JSON.stringify(log.details)}
                                  </code>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ padding: '24px', textAlign: 'center', color: '#94A3B8', fontStyle: 'italic' }}>
                        No audit records captured yet.
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : null}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button
                onClick={() => setShowDetailModal(false)}
                style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '8px 18px', fontWeight: 700, cursor: 'pointer' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
