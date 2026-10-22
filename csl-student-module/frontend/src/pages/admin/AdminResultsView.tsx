import { useState, useEffect } from 'react';
import {
  getAdminResults,
  deleteAdminAttempt,
  bulkDeleteAdminAttempts,
  type AdminResult,
} from '../../api/admin';

interface AdminResultsViewProps {
  onReviewAttempt: (attemptId: string) => void;
}

export function AdminResultsView({ onReviewAttempt }: AdminResultsViewProps) {
  const [results, setResults] = useState<AdminResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Bulk and Selection state
  const [selectedAttemptIds, setSelectedAttemptIds] = useState<string[]>([]);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const loadResults = async (query = '') => {
    try {
      setLoading(true);
      const data = await getAdminResults(query ? { search: query } : undefined);
      setResults(data);
    } catch {
      alert('Failed to load assessment results.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelectAllAttempts = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedAttemptIds(results.map((r) => r.id));
    } else {
      setSelectedAttemptIds([]);
    }
  };

  const handleToggleSelectAttempt = (id: string) => {
    setSelectedAttemptIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleDeleteAttempt = async (res: AdminResult) => {
    const confirmed = window.confirm(
      `Are you sure you want to permanently delete the scorecard and attempt records for ${res.candidate_name} (${res.register_number})?\n\nThis will permanently delete this attempt, its answers, and its integrity events.`
    );
    if (!confirmed) return;

    try {
      await deleteAdminAttempt(res.id);
      setResults((prev) => prev.filter((item) => item.id !== res.id));
      setSelectedAttemptIds((prev) => prev.filter((id) => id !== res.id));
    } catch {
      alert('Failed to delete scorecard and attempt record.');
    }
  };

  const handleBulkDeleteAttempts = async () => {
    if (selectedAttemptIds.length === 0) return;
    const confirmed = window.confirm(
      `Are you sure you want to permanently delete ${selectedAttemptIds.length} selected candidate attempt record(s)?\n\nAll historical answers and score logs will be permanently deleted.`
    );
    if (!confirmed) return;

    try {
      setBulkDeleting(true);
      const resp = await bulkDeleteAdminAttempts(selectedAttemptIds);
      alert(resp.message);
      setSelectedAttemptIds([]);
      loadResults(search);
    } catch {
      alert('Failed to bulk delete selected attempts.');
    } finally {
      setBulkDeleting(false);
    }
  };

  useEffect(() => {
    loadResults();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadResults(search);
  };

  return (
    <div>
      {/* Header & Search */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 6px 0', letterSpacing: '-0.02em' }}>
            Assessment Results & Scorecards
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Authoritative results, section breakdowns, and proctoring summaries for finalized attempts.
          </p>
        </div>

        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px' }}>
          <div style={{ position: 'relative' }}>
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
              placeholder="Search candidate, roll no, college..."
              style={{
                padding: '8px 12px 8px 36px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '13px',
                width: '280px',
                outlineColor: '#1455B8',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <button
            type="submit"
            style={{
              padding: '8px 16px',
              backgroundColor: '#1455B8',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(20, 85, 184, 0.2)',
            }}
          >
            Search
          </button>

          {search && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                loadResults('');
              }}
              style={{
                padding: '8px 12px',
                backgroundColor: '#FFFFFF',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                fontSize: '13px',
                color: '#475569',
                cursor: 'pointer',
              }}
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Bulk Action Bar */}
      {selectedAttemptIds.length > 0 && (
        <div
          style={{
            marginBottom: '16px',
            padding: '12px 18px',
            backgroundColor: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                backgroundColor: '#1D4ED8',
                color: '#FFFFFF',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              {selectedAttemptIds.length}
            </span>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#1E40AF' }}>
              {selectedAttemptIds.length} scorecard attempt{selectedAttemptIds.length === 1 ? '' : 's'} selected
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={() => setSelectedAttemptIds([])}
              style={{
                padding: '6px 12px',
                backgroundColor: '#FFFFFF',
                color: '#475569',
                border: '1px solid #CBD5E1',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Deselect All
            </button>
            <button
              type="button"
              onClick={handleBulkDeleteAttempts}
              disabled={bulkDeleting}
              style={{
                padding: '6px 14px',
                backgroundColor: '#DC2626',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: bulkDeleting ? 'not-allowed' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              <span>{bulkDeleting ? 'Deleting...' : `Delete Selected (${selectedAttemptIds.length})`}</span>
            </button>
          </div>
        </div>
      )}

      {/* Results Table */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '14px',
          border: '1px solid #E2E8F0',
          overflowX: 'auto',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
        }}
      >
        <table style={{ width: '100%', minWidth: '1000px', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569' }}>
              <th style={{ padding: '12px 16px', width: '40px', textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={results.length > 0 && selectedAttemptIds.length === results.length}
                  ref={(el) => {
                    if (el) el.indeterminate = selectedAttemptIds.length > 0 && selectedAttemptIds.length < results.length;
                  }}
                  onChange={handleToggleSelectAllAttempts}
                  style={{ cursor: 'pointer', width: '16px', height: '16px', accentColor: '#1455B8' }}
                  title="Select / Deselect All Results"
                />
              </th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Candidate Details</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Register / Roll No</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Institution</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Aptitude</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Coding</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Total Score</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Percentage</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Status</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  Loading assessment results from database...
                </td>
              </tr>
            ) : results.length === 0 ? (
              <tr>
                <td colSpan={10} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  No assessment scorecards found matching your query.
                </td>
              </tr>
            ) : (
              results.map((res) => {
                const pct = res.percentage || 0;
                const isPass = pct >= 50;
                const isSelected = selectedAttemptIds.includes(res.id);

                return (
                  <tr
                    key={res.id}
                    style={{
                      borderBottom: '1px solid #F1F5F9',
                      backgroundColor: isSelected ? '#F0F7FF' : 'transparent',
                      transition: 'background-color 0.1s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC';
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleSelectAttempt(res.id)}
                        style={{ cursor: 'pointer', width: '16px', height: '16px', accentColor: '#1455B8' }}
                      />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 700, color: '#0B2E6F' }}>{res.candidate_name}</div>
                      <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>{res.department} • {res.year_of_study}</span>
                        {res.delivery_mode === 'PDF_CODING' && (
                          <span style={{ backgroundColor: '#EDE9FE', color: '#6D28D9', fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px' }}>
                            PDF Mode
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontWeight: 700, color: '#1E293B' }}>
                      {res.register_number}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#475569' }}>
                      {res.assessment_code && (
                        <span style={{ backgroundColor: '#EEF2FF', color: '#3730A3', fontWeight: 700, fontSize: '10px', padding: '2px 6px', borderRadius: '4px', marginRight: '6px' }}>
                          {res.assessment_code}
                        </span>
                      )}
                      {res.college}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 700, color: '#1455B8' }}>
                      {res.delivery_mode === 'PDF_CODING' || res.is_manual_evaluation_pending ? (
                        <span style={{ color: '#94A3B8' }}>—</span>
                      ) : (
                        <span style={{ backgroundColor: '#EFF6FF', padding: '2px 8px', borderRadius: '4px' }}>
                          {res.aptitude_score}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 700, color: '#059669' }}>
                      {res.delivery_mode === 'PDF_CODING' || res.is_manual_evaluation_pending ? (
                        <span style={{ color: '#94A3B8' }}>—</span>
                      ) : (
                        <span style={{ backgroundColor: '#ECFDF5', padding: '2px 8px', borderRadius: '4px' }}>
                          {res.coding_score}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 800, color: '#0B2E6F', fontSize: '14px' }}>
                      {res.delivery_mode === 'PDF_CODING' || res.is_manual_evaluation_pending ? (
                        <span style={{ fontSize: '12px', color: '#D97706', fontWeight: 700 }}>Paper Eval</span>
                      ) : (
                        <>{res.total_score} <span style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 500 }}>/ {res.assessment_total_marks ?? 50}</span></>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      {res.delivery_mode === 'PDF_CODING' || res.is_manual_evaluation_pending ? (
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: '#FEF3C7',
                            color: '#92400E',
                          }}
                        >
                          Pending
                        </span>
                      ) : (
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 800,
                            backgroundColor: isPass ? '#DCFCE7' : '#FEE2E2',
                            color: isPass ? '#166534' : '#991B1B',
                          }}
                        >
                          {res.percentage}%
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {res.state === 'COMPLETED_PENDING_MANUAL_EVALUATION' || res.is_manual_evaluation_pending ? (
                        <span
                          style={{
                            padding: '3px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: '#FEF3C7',
                            color: '#92400E',
                            display: 'inline-block',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          Pending Manual Eval
                        </span>
                      ) : (
                        <span
                          style={{
                            padding: '3px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: res.state === 'SUBMITTED' ? '#DCFCE7' : '#FEE2E2',
                            color: res.state === 'SUBMITTED' ? '#166534' : '#991B1B',
                          }}
                        >
                          {res.state}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '8px', alignItems: 'center' }}>
                        <button
                          onClick={() => onReviewAttempt(res.id)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
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
                        <button
                          onClick={() => handleDeleteAttempt(res)}
                          style={{
                            padding: '6px 10px',
                            backgroundColor: '#FFF1F2',
                            color: '#BE123C',
                            border: '1px solid #FDA4AF',
                            borderRadius: '7px',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                          title="Delete scorecard and attempt record"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
