import { useState, useEffect } from 'react';
import {
  getAdminIntegrityEvents,
  reviewAdminIntegrityEvent,
  type AdminIntegrityEvent,
} from '../../api/admin';

interface AdminIntegrityEventsViewProps {
  onReviewAttempt: (attemptId: string) => void;
}

export function AdminIntegrityEventsView({ onReviewAttempt }: AdminIntegrityEventsViewProps) {
  const [events, setEvents] = useState<AdminIntegrityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [reviewFilter, setReviewFilter] = useState<'ALL' | 'UNREVIEWED' | 'REVIEWED'>('ALL');
  const [search, setSearch] = useState('');

  // Review Modal state
  const [selectedEvent, setSelectedEvent] = useState<AdminIntegrityEvent | null>(null);
  const [modalIsReviewed, setModalIsReviewed] = useState(true);
  const [modalReviewNotes, setModalReviewNotes] = useState('');
  const [savingReview, setSavingReview] = useState(false);

  const loadEvents = async () => {
    try {
      setLoading(true);
      let isReviewedParam: boolean | undefined = undefined;
      if (reviewFilter === 'UNREVIEWED') isReviewedParam = false;
      if (reviewFilter === 'REVIEWED') isReviewedParam = true;

      const data = await getAdminIntegrityEvents({
        event_type: eventTypeFilter || undefined,
        is_reviewed: isReviewedParam,
        search: search || undefined,
      });
      setEvents(data);
    } catch {
      alert('Failed to load integrity audit events.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [eventTypeFilter, reviewFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadEvents();
  };

  const openReviewModal = (ev: AdminIntegrityEvent) => {
    setSelectedEvent(ev);
    setModalIsReviewed(ev.is_reviewed ?? true);
    setModalReviewNotes(ev.review_notes || '');
  };

  const handleSaveReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent) return;

    try {
      setSavingReview(true);
      const res = await reviewAdminIntegrityEvent(
        selectedEvent.id,
        modalIsReviewed,
        modalReviewNotes
      );

      // Update in local state
      setEvents((prev) =>
        prev.map((ev) => (ev.id === selectedEvent.id ? { ...ev, ...res.event } : ev))
      );
      setSelectedEvent(null);
    } catch {
      alert('Failed to update integrity event review status.');
    } finally {
      setSavingReview(false);
    }
  };

  return (
    <div>
      {/* Header & Controls */}
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
            Proctoring & Integrity Audit Trail
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
            Monitor tab switches, document visibility changes, and proctoring telemetry with administrative review workflows.
          </p>
        </div>

        <button
          onClick={loadEvents}
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
          <span>Refresh Audit Trail</span>
        </button>
      </div>

      {/* Filter Toolbar */}
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
          flexWrap: 'wrap',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px', flex: 1, minWidth: '260px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
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
              placeholder="Search candidate, roll no, college, or audit notes..."
              style={{
                padding: '8px 12px 8px 36px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '13px',
                width: '100%',
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
        </form>

        <select
          value={eventTypeFilter}
          onChange={(e) => setEventTypeFilter(e.target.value)}
          style={{
            padding: '8px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            color: '#1E293B',
            backgroundColor: '#FFFFFF',
            outlineColor: '#1455B8',
          }}
        >
          <option value="">All Event Types</option>
          <option value="TAB_HIDDEN">TAB_HIDDEN (Tab Switch Out)</option>
          <option value="TAB_VISIBLE">TAB_VISIBLE (Tab Switch In)</option>
          <option value="FULLSCREEN_EXIT">FULLSCREEN_EXIT</option>
          <option value="FULLSCREEN_ENTER">FULLSCREEN_ENTER</option>
          <option value="ATTEMPT_STARTED">ATTEMPT_STARTED</option>
          <option value="SUBMITTED">SUBMITTED</option>
          <option value="TIMED_OUT">TIMED_OUT</option>
        </select>

        <div style={{ display: 'flex', borderRadius: '8px', border: '1px solid #CBD5E1', overflow: 'hidden' }}>
          <button
            type="button"
            onClick={() => setReviewFilter('ALL')}
            style={{
              padding: '8px 14px',
              backgroundColor: reviewFilter === 'ALL' ? '#0B2E6F' : '#FFFFFF',
              color: reviewFilter === 'ALL' ? '#FFFFFF' : '#475569',
              border: 'none',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setReviewFilter('UNREVIEWED')}
            style={{
              padding: '8px 14px',
              backgroundColor: reviewFilter === 'UNREVIEWED' ? '#D97706' : '#FFFFFF',
              color: reviewFilter === 'UNREVIEWED' ? '#FFFFFF' : '#475569',
              border: 'none',
              borderLeft: '1px solid #CBD5E1',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Pending Review
          </button>
          <button
            type="button"
            onClick={() => setReviewFilter('REVIEWED')}
            style={{
              padding: '8px 14px',
              backgroundColor: reviewFilter === 'REVIEWED' ? '#16A34A' : '#FFFFFF',
              color: reviewFilter === 'REVIEWED' ? '#FFFFFF' : '#475569',
              border: 'none',
              borderLeft: '1px solid #CBD5E1',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Reviewed
          </button>
        </div>

        {(eventTypeFilter || reviewFilter !== 'ALL' || search) && (
          <button
            type="button"
            onClick={() => {
              setEventTypeFilter('');
              setReviewFilter('ALL');
              setSearch('');
            }}
            style={{
              padding: '8px 12px',
              backgroundColor: '#F1F5F9',
              border: 'none',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 600,
              color: '#475569',
              cursor: 'pointer',
            }}
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Events Table */}
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
              <th style={{ padding: '12px 16px', width: '180px', fontWeight: 700 }}>Event Type</th>
              <th style={{ padding: '12px 16px', width: '220px', fontWeight: 700 }}>Candidate Details</th>
              <th style={{ padding: '12px 16px', fontWeight: 700 }}>Telemetry & Context</th>
              <th style={{ padding: '12px 16px', width: '140px', fontWeight: 700 }}>Review Status</th>
              <th style={{ padding: '12px 16px', width: '160px', fontWeight: 700 }}>Timestamp</th>
              <th style={{ padding: '12px 16px', width: '200px', fontWeight: 700, textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  Loading integrity audit trail...
                </td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
                  No integrity events recorded matching the current filter.
                </td>
              </tr>
            ) : (
              events.map((ev) => {
                const isViolation =
                  ev.event_type.includes('HIDDEN') ||
                  ev.event_type.includes('EXIT') ||
                  ev.event_type.includes('EXCEEDED');

                const isReviewed = Boolean(ev.is_reviewed);

                return (
                  <tr
                    key={ev.id}
                    style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.1s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '12px 16px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 800,
                          backgroundColor: isViolation ? '#FEF2F2' : '#EFF6FF',
                          color: isViolation ? '#DC2626' : '#1455B8',
                          border: `1px solid ${isViolation ? '#FECACA' : '#BFDBFE'}`,
                          fontFamily: 'monospace',
                        }}
                      >
                        {ev.event_type}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 700, color: '#0B2E6F' }}>{ev.candidate_name}</div>
                      <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
                        Roll No: <strong style={{ color: '#0F172A' }}>{ev.register_number}</strong>
                      </div>
                      <div style={{ fontSize: '11px', color: '#94A3B8' }}>{ev.college}</div>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#334155', fontSize: '12px' }}>
                      {ev.metadata && Object.keys(ev.metadata).length > 0 ? (
                        <div
                          style={{
                            backgroundColor: '#F8FAFC',
                            border: '1px solid #E2E8F0',
                            borderRadius: '6px',
                            padding: '6px 10px',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            color: '#334155',
                            maxWidth: '320px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {JSON.stringify(ev.metadata)}
                        </div>
                      ) : (
                        <span style={{ color: '#94A3B8' }}>—</span>
                      )}
                      {ev.review_notes && (
                        <div style={{ marginTop: '6px', fontSize: '11px', color: '#166534' }}>
                          <strong>Audit Note:</strong> {ev.review_notes}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {isReviewed ? (
                        <div>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              borderRadius: '9999px',
                              fontSize: '11px',
                              fontWeight: 700,
                              backgroundColor: '#DCFCE7',
                              color: '#166534',
                              border: '1px solid #BBF7D0',
                            }}
                          >
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            Reviewed
                          </span>
                          {ev.reviewed_by_name && (
                            <div style={{ fontSize: '10px', color: '#64748B', marginTop: '2px' }}>
                              by {ev.reviewed_by_name}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '2px 8px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: '#FEF3C7',
                            color: '#92400E',
                            border: '1px solid #FDE68A',
                          }}
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="8" x2="12" y2="12"></line>
                            <line x1="12" y1="16" x2="12.01" y2="16"></line>
                          </svg>
                          Pending
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748B', fontSize: '12px' }}>
                      {new Date(ev.created_at || (ev as any).timestamp).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '8px', alignItems: 'center' }}>
                        <button
                          onClick={() => openReviewModal(ev)}
                          style={{
                            padding: '5px 12px',
                            backgroundColor: '#FFFFFF',
                            border: '1px solid #CBD5E1',
                            borderRadius: '6px',
                            color: '#0B2E6F',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          {isReviewed ? 'Edit Note' : 'Review'}
                        </button>
                        <button
                          onClick={() => onReviewAttempt(ev.attempt_id)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '5px 12px',
                            backgroundColor: '#1455B8',
                            border: 'none',
                            borderRadius: '6px',
                            color: '#FFFFFF',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          <span>Inspect</span>
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="9 18 15 12 9 6"></polyline>
                          </svg>
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

      {/* Review Action Modal */}
      {selectedEvent && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.4)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
            boxSizing: 'border-box',
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              border: '1px solid #E2E8F0',
              boxShadow: '0 20px 35px -10px rgba(11, 46, 111, 0.15)',
              width: '100%',
              maxWidth: '520px',
              padding: '24px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '17px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Review Integrity Event
              </h3>
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '18px',
                  color: '#64748B',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </div>

            <div
              style={{
                backgroundColor: '#F8FAFC',
                border: '1px solid #E2E8F0',
                padding: '12px 16px',
                borderRadius: '8px',
                marginBottom: '16px',
                fontSize: '12px',
                color: '#334155',
              }}
            >
              <div>
                <strong>Candidate:</strong> {selectedEvent.candidate_name} ({selectedEvent.register_number})
              </div>
              <div style={{ marginTop: '4px' }}>
                <strong>Event:</strong>{' '}
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#DC2626' }}>
                  {selectedEvent.event_type}
                </span>
              </div>
              <div style={{ marginTop: '4px' }}>
                <strong>Recorded:</strong>{' '}
                {new Date(selectedEvent.created_at || (selectedEvent as any).timestamp).toLocaleString()}
              </div>
            </div>

            <form onSubmit={handleSaveReview}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0B2E6F', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={modalIsReviewed}
                    onChange={(e) => setModalIsReviewed(e.target.checked)}
                    style={{ width: '16px', height: '16px', accentColor: '#16A34A' }}
                  />
                  <span>Mark as Administratively Reviewed</span>
                </label>
                <p style={{ fontSize: '12px', color: '#64748B', margin: '4px 0 0 24px' }}>
                  Acknowledge that this violation or telemetry event has been reviewed by staff.
                </p>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#0B2E6F', marginBottom: '6px' }}>
                  Audit Review Notes / Justification
                </label>
                <textarea
                  rows={3}
                  value={modalReviewNotes}
                  onChange={(e) => setModalReviewNotes(e.target.value)}
                  placeholder="e.g. Benign tab blur verified. Student re-entered immediately."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setSelectedEvent(null)}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#F1F5F9',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#475569',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingReview}
                  style={{
                    padding: '8px 18px',
                    backgroundColor: '#16A34A',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    opacity: savingReview ? 0.7 : 1,
                  }}
                >
                  {savingReview ? 'Saving...' : 'Save Review Status'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
