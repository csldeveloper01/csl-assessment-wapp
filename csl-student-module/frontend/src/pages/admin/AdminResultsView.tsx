import { useState, useEffect } from 'react';
import { getAdminResults, type AdminResult } from '../../api/admin';

interface AdminResultsViewProps {
  onReviewAttempt: (attemptId: string) => void;
}

export function AdminResultsView({ onReviewAttempt }: AdminResultsViewProps) {
  const [results, setResults] = useState<AdminResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

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

      {/* Results Table */}
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
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Candidate Details</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Register / Roll No</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Institution</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Aptitude (25)</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Coding (25)</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Total Score</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Percentage</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Status</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  Loading assessment results from database...
                </td>
              </tr>
            ) : results.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  No assessment scorecards found matching your query.
                </td>
              </tr>
            ) : (
              results.map((res) => {
                const pct = res.percentage || 0;
                const isPass = pct >= 50;

                return (
                  <tr
                    key={res.id}
                    style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.1s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 700, color: '#0B2E6F' }}>{res.candidate_name}</div>
                      <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
                        {res.department} • {res.year_of_study}
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
                      <span style={{ backgroundColor: '#EFF6FF', padding: '2px 8px', borderRadius: '4px' }}>
                        {res.aptitude_score}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 700, color: '#059669' }}>
                      <span style={{ backgroundColor: '#ECFDF5', padding: '2px 8px', borderRadius: '4px' }}>
                        {res.coding_score}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 800, color: '#0B2E6F', fontSize: '14px' }}>
                      {res.total_score} <span style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 500 }}>/ 50</span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
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
                    </td>
                    <td style={{ padding: '12px 16px' }}>
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
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
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
