import { useState, useEffect } from 'react';
import {
  getAdminCandidates,
  getAdminCandidateDetail,
  getAdminColleges,
  toggleAdminCandidateStatus,
  exportAdminCandidatesCSV,
  type AdminCandidate,
  type AdminCollege,
} from '../../api/admin';

interface AdminCandidatesViewProps {
  onReviewAttempt: (attemptId: string) => void;
}

export function AdminCandidatesView({ onReviewAttempt }: AdminCandidatesViewProps) {
  const [candidates, setCandidates] = useState<AdminCandidate[]>([]);
  const [colleges, setColleges] = useState<AdminCollege[]>([]);
  const [search, setSearch] = useState('');
  const [selectedCollegeId, setSelectedCollegeId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [selectedCandidate, setSelectedCandidate] = useState<any | null>(null);
  const [exportingCSV, setExportingCSV] = useState(false);

  const handleExportCSV = async () => {
    try {
      setExportingCSV(true);
      const blob = await exportAdminCandidatesCSV({
        search: search.trim() || undefined,
        college_id: selectedCollegeId || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `csl-candidates-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Failed to export candidate records to CSV.');
    } finally {
      setExportingCSV(false);
    }
  };

  const loadCandidates = async () => {
    try {
      setLoading(true);
      const data = await getAdminCandidates({
        search: search.trim() || undefined,
        college_id: selectedCollegeId || undefined,
      });
      setCandidates(data);
    } catch {
      alert('Failed to load candidate list.');
    } finally {
      setLoading(false);
    }
  };

  const loadColleges = async () => {
    try {
      const data = await getAdminColleges();
      setColleges(data);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadColleges();
  }, []);

  useEffect(() => {
    loadCandidates();
  }, [selectedCollegeId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadCandidates();
  };

  const handleToggleCandidate = async (candId: string) => {
    try {
      const res = await toggleAdminCandidateStatus(candId);
      setCandidates((prev) =>
        prev.map((c) => (c.id === candId ? { ...c, is_active: res.is_active } : c))
      );
    } catch {
      alert('Failed to toggle candidate status.');
    }
  };

  const handleSelectCandidate = async (candidateId: string) => {
    try {
      const detail = await getAdminCandidateDetail(candidateId);
      setSelectedCandidate(detail);
    } catch {
      alert('Failed to load candidate details.');
    }
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
            Registered Candidates Directory
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Inspect candidate enrollment, institutional affiliations, attempt history, and finalized scores.
          </p>
        </div>

        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <select
            value={selectedCollegeId}
            onChange={(e) => setSelectedCollegeId(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid #CBD5E1',
              fontSize: '13px',
              backgroundColor: '#FFFFFF',
              outlineColor: '#1455B8',
              cursor: 'pointer',
            }}
          >
            <option value="">All Institutions</option>
            {colleges.map((col) => (
              <option key={col.id} value={col.id}>
                {col.code} — {col.name}
              </option>
            ))}
          </select>

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
                width: '260px',
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

          {(search || selectedCollegeId) && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setSelectedCollegeId('');
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

          <button
            type="button"
            onClick={handleExportCSV}
            disabled={exportingCSV}
            style={{
              padding: '8px 14px',
              backgroundColor: '#F8FAFC',
              color: '#0B2E6F',
              border: '1px solid #CBD5E1',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: exportingCSV ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (!exportingCSV) e.currentTarget.style.backgroundColor = '#E8EFFD';
            }}
            onMouseLeave={(e) => {
              if (!exportingCSV) e.currentTarget.style.backgroundColor = '#F8FAFC';
            }}
            title="Download candidate details as CSV"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            {exportingCSV ? 'Exporting...' : 'Export CSV'}
          </button>
        </form>
      </div>

      {/* Table Container */}
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
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Candidate Name</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Roll / Register No</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>College / Institution</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Department & Year</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Attempts</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Latest Status</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Latest Score</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  Loading candidates from database...
                </td>
              </tr>
            ) : candidates.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  No candidates found matching the query criteria.
                </td>
              </tr>
            ) : (
              candidates.map((cand) => (
                <tr
                  key={cand.id}
                  style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.1s ease' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0B2E6F' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {cand.full_name}
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '1px 6px',
                          borderRadius: '8px',
                          backgroundColor: cand.is_active ? '#DCFCE7' : '#F1F5F9',
                          color: cand.is_active ? '#15803D' : '#64748B',
                        }}
                      >
                        {cand.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 500, marginTop: '2px' }}>
                      {cand.email} {cand.phone_number && `• ${cand.phone_number}`}
                    </div>
                  </td>
                  <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontWeight: 700 }}>
                    {cand.register_number}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#334155' }}>
                    {cand.college_code && (
                      <span style={{ backgroundColor: '#EEF2FF', color: '#3730A3', fontWeight: 700, fontSize: '11px', padding: '2px 6px', borderRadius: '4px', marginRight: '6px' }}>
                        {cand.college_code}
                      </span>
                    )}
                    {cand.college}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#475569' }}>
                    {cand.department}
                    <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px' }}>{cand.year_of_study}</div>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 700 }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: '6px',
                        backgroundColor: '#F1F5F9',
                        color: '#334155',
                      }}
                    >
                      {cand.attempts_count}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    {cand.latest_state ? (
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '3px 8px',
                          borderRadius: '9999px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor:
                            cand.latest_state === 'SUBMITTED'
                              ? '#DCFCE7'
                              : cand.latest_state === 'IN_PROGRESS'
                              ? '#FEF3C7'
                              : '#F1F5F9',
                          color:
                            cand.latest_state === 'SUBMITTED'
                              ? '#166534'
                              : cand.latest_state === 'IN_PROGRESS'
                              ? '#B45309'
                              : '#475569',
                        }}
                      >
                        {cand.latest_state}
                      </span>
                    ) : (
                      <span style={{ color: '#94A3B8', fontSize: '11px' }}>Registered</span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0B2E6F' }}>
                    {cand.latest_score !== null && cand.latest_score !== undefined
                      ? `${cand.latest_score} / 50`
                      : '—'}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => handleSelectCandidate(cand.id)}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#FFFFFF',
                          border: '1px solid #1455B8',
                          borderRadius: '6px',
                          color: '#1455B8',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        View Details
                      </button>
                      <button
                        onClick={() => handleToggleCandidate(cand.id)}
                        title={cand.is_active ? 'Deactivate candidate' : 'Activate candidate'}
                        style={{
                          padding: '6px 10px',
                          backgroundColor: cand.is_active ? '#FFF1F2' : '#F0FDF4',
                          border: `1px solid ${cand.is_active ? '#FECDD3' : '#BBF7D0'}`,
                          borderRadius: '6px',
                          color: cand.is_active ? '#E11D48' : '#16A34A',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        {cand.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Candidate Detail Modal */}
      {selectedCandidate && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.4)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 100,
            padding: '20px',
            boxSizing: 'border-box',
          }}
        >
          <div
            style={{
              maxWidth: '680px',
              width: '100%',
              maxHeight: '85vh',
              overflowY: 'auto',
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              padding: '28px',
              boxShadow: '0 20px 35px -10px rgba(11, 46, 111, 0.15)',
              border: '1px solid #E2E8F0',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <span
                  style={{
                    backgroundColor: 'rgba(20, 85, 184, 0.08)',
                    color: '#1455B8',
                    fontSize: '11px',
                    fontWeight: 800,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    textTransform: 'uppercase',
                  }}
                >
                  Candidate Profile
                </span>
                <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', margin: '6px 0 2px 0' }}>
                  {selectedCandidate.full_name}
                </h3>
                <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
                  {selectedCandidate.email} • {selectedCandidate.register_number}
                </p>
              </div>
              <button
                onClick={() => setSelectedCandidate(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '20px',
                  color: '#94A3B8',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                ✕
              </button>
            </div>

            {/* Candidate Metadata Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                backgroundColor: '#F8FAFC',
                padding: '16px',
                borderRadius: '10px',
                marginBottom: '24px',
                fontSize: '13px',
                border: '1px solid #E2E8F0',
              }}
            >
              <div>
                <span style={{ color: '#64748B' }}>College:</span>{' '}
                <strong style={{ color: '#0B2E6F' }}>{selectedCandidate.college}</strong>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Department:</span>{' '}
                <strong style={{ color: '#0B2E6F' }}>{selectedCandidate.department}</strong>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Year of Study:</span>{' '}
                <strong style={{ color: '#0B2E6F' }}>{selectedCandidate.year_of_study}</strong>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Phone:</span>{' '}
                <strong style={{ color: '#0B2E6F' }}>{selectedCandidate.phone_number || 'N/A'}</strong>
              </div>
            </div>

            {/* Assessment Attempts List */}
            <h4 style={{ fontSize: '15px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 12px 0' }}>
              Associated Assessment Attempts ({selectedCandidate.attempts?.length || 0})
            </h4>

            {selectedCandidate.attempts && selectedCandidate.attempts.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {selectedCandidate.attempts.map((att: any) => (
                  <div
                    key={att.id}
                    style={{
                      border: '1px solid #E2E8F0',
                      borderRadius: '10px',
                      padding: '14px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: '#FFFFFF',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor:
                              att.state === 'SUBMITTED' ? '#DCFCE7' : '#FEF3C7',
                            color: att.state === 'SUBMITTED' ? '#166534' : '#B45309',
                          }}
                        >
                          {att.state}
                        </span>
                        <strong style={{ fontSize: '14px', color: '#0B2E6F' }}>
                          Score: {att.total_score} / 50 ({att.percentage}%)
                        </strong>
                        {att.is_flagged && (
                          <span
                            style={{
                              color: '#DC2626',
                              backgroundColor: '#FEF2F2',
                              padding: '2px 8px',
                              borderRadius: '9999px',
                              fontSize: '11px',
                              fontWeight: 700,
                              border: '1px solid #FECACA',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                            </svg>
                            Flagged
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748B', marginTop: '4px' }}>
                        Aptitude: {att.aptitude_score}/25 • Coding: {att.coding_score}/25 • Tab Switches: {att.tab_switch_count}
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setSelectedCandidate(null);
                        onReviewAttempt(att.id);
                      }}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '6px 14px',
                        backgroundColor: '#1455B8',
                        color: '#FFFFFF',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      <span>Inspect Review</span>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '13px', color: '#6B7280', margin: 0 }}>
                This candidate has not started any attempts yet.
              </p>
            )}

            <div style={{ marginTop: '24px', textAlign: 'right' }}>
              <button
                onClick={() => setSelectedCandidate(null)}
                style={{
                  padding: '8px 18px',
                  backgroundColor: '#E2E8F0',
                  color: '#334155',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
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
