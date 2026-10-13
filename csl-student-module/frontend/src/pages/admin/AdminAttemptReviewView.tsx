import { useState, useEffect } from 'react';
import {
  getAdminAttemptReview,
  updateAdminAttemptReviewStatus,
  reviewAdminIntegrityEvent,
  type AdminAttemptReview,
  type AdminIntegrityEvent,
} from '../../api/admin';

interface AdminAttemptReviewViewProps {
  attemptId: string;
  onBack: () => void;
}

export function AdminAttemptReviewView({ attemptId, onBack }: AdminAttemptReviewViewProps) {
  const [review, setReview] = useState<AdminAttemptReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [sectionFilter, setSectionFilter] = useState<'ALL' | 'APTITUDE' | 'CODING'>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'CORRECT' | 'INCORRECT' | 'UNANSWERED'>('ALL');

  // Flag action modal
  const [showFlagModal, setShowFlagModal] = useState(false);
  const [pendingFlagAction, setPendingFlagAction] = useState<'FLAG' | 'CLEAR_FLAG'>('FLAG');
  const [flagNotes, setFlagNotes] = useState('');
  const [updatingFlag, setUpdatingFlag] = useState(false);

  // Integrity event review modal
  const [selectedEvent, setSelectedEvent] = useState<AdminIntegrityEvent | null>(null);
  const [eventIsReviewed, setEventIsReviewed] = useState(true);
  const [eventReviewNotes, setEventReviewNotes] = useState('');
  const [savingEventReview, setSavingEventReview] = useState(false);

  const loadReview = async () => {
    try {
      setLoading(true);
      const data = await getAdminAttemptReview(attemptId);
      setReview(data);
    } catch {
      alert('Failed to load attempt snapshot and review data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReview();
  }, [attemptId]);

  const openFlagModal = (action: 'FLAG' | 'CLEAR_FLAG') => {
    setPendingFlagAction(action);
    setFlagNotes(review?.flag_reason || '');
    setShowFlagModal(true);
  };

  const handleConfirmFlagAction = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setUpdatingFlag(true);
      await updateAdminAttemptReviewStatus(attemptId, pendingFlagAction, flagNotes);
      setShowFlagModal(false);
      loadReview();
    } catch {
      alert('Failed to update attempt integrity flag status.');
    } finally {
      setUpdatingFlag(false);
    }
  };

  const openEventReviewModal = (ev: AdminIntegrityEvent) => {
    setSelectedEvent(ev);
    setEventIsReviewed(ev.is_reviewed ?? true);
    setEventReviewNotes(ev.review_notes || '');
  };

  const handleSaveEventReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent) return;

    try {
      setSavingEventReview(true);
      await reviewAdminIntegrityEvent(selectedEvent.id, eventIsReviewed, eventReviewNotes);
      setSelectedEvent(null);
      loadReview();
    } catch {
      alert('Failed to update integrity event review.');
    } finally {
      setSavingEventReview(false);
    }
  };

  if (loading) {
    return (
      <div
        style={{
          padding: '48px',
          textAlign: 'center',
          color: '#64748B',
          fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1455B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 1.5s linear infinite' }}>
            <line x1="12" y1="2" x2="12" y2="6"></line>
            <line x1="12" y1="18" x2="12" y2="22"></line>
            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
            <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
            <line x1="2" y1="12" x2="6" y2="12"></line>
            <line x1="18" y1="12" x2="22" y2="12"></line>
            <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
            <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
          </svg>
        </div>
        <div style={{ fontSize: '15px', fontWeight: 700, color: '#0B2E6F' }}>
          Loading authoritative attempt snapshot and question telemetry...
        </div>
      </div>
    );
  }

  if (!review) {
    return (
      <div
        style={{
          padding: '32px',
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #FCA5A5',
          textAlign: 'center',
          maxWidth: '500px',
          margin: '40px auto',
        }}
      >
        <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#991B1B', margin: '0 0 8px 0' }}>
          Assessment Attempt Not Found
        </h3>
        <p style={{ fontSize: '13px', color: '#64748B', margin: '0 0 16px 0' }}>
          Unable to locate the specified attempt ID ({attemptId}).
        </p>
        <button
          onClick={onBack}
          style={{
            padding: '8px 18px',
            backgroundColor: '#0B2E6F',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          ← Return to Attempts
        </button>
      </div>
    );
  }

  const filteredQuestions = review.questions.filter((q) => {
    if (sectionFilter !== 'ALL' && q.section_type !== sectionFilter) return false;
    if (statusFilter === 'CORRECT' && q.is_correct !== true) return false;
    if (statusFilter === 'INCORRECT' && (q.is_correct === true || !q.selected_option)) return false;
    if (statusFilter === 'UNANSWERED' && (q.selected_option && q.selected_option.trim())) return false;
    return true;
  });

  return (
    <div>
      {/* Top Navigation & Action Toolbar */}
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
        <button
          onClick={onBack}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: '#FFFFFF',
            border: '1.5px solid #CBD5E1',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 700,
            color: '#0B2E6F',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FAF7F3')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FFFFFF')}
        >
          ← Back to Previous List
        </button>

        <div style={{ display: 'flex', gap: '10px' }}>
          {review.is_flagged ? (
            <button
              onClick={() => openFlagModal('CLEAR_FLAG')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 18px',
                backgroundColor: '#16A34A',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(22, 163, 74, 0.25)',
              }}
            >
              ✓ Clear Integrity Flag
            </button>
          ) : (
            <button
              onClick={() => openFlagModal('FLAG')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 18px',
                backgroundColor: '#DC2626',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(220, 38, 38, 0.25)',
              }}
            >
              ⚠️ Flag for Proctoring Review
            </button>
          )}
        </div>
      </div>

      {/* Candidate & Attempt Banner */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          border: '1.5px solid rgba(245, 184, 61, 0.35)',
          padding: '26px',
          marginBottom: '24px',
          boxShadow: '0 6px 18px rgba(11, 46, 111, 0.05)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '20px',
          }}
        >
          {/* Candidate Info */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span
                style={{
                  padding: '3px 12px',
                  borderRadius: '9999px',
                  fontSize: '11px',
                  fontWeight: 800,
                  backgroundColor: review.state === 'SUBMITTED' ? '#DCFCE7' : '#FEF3C7',
                  color: review.state === 'SUBMITTED' ? '#166534' : '#B45309',
                }}
              >
                {review.state}
              </span>
              {review.is_flagged && (
                <span
                  style={{
                    padding: '3px 12px',
                    borderRadius: '9999px',
                    fontSize: '11px',
                    fontWeight: 800,
                    backgroundColor: '#FEE2E2',
                    color: '#991B1B',
                  }}
                >
                  ⚠️ Flagged for Integrity
                </span>
              )}
            </div>

            <h2 style={{ fontSize: '24px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 6px 0' }}>
              {review.candidate.full_name}
            </h2>
            <div style={{ fontSize: '13px', color: '#475569', marginBottom: '4px' }}>
              Register / Roll No: <strong style={{ color: '#0B2E6F' }}>{review.candidate.register_number}</strong> • College:{' '}
              <strong style={{ color: '#0B2E6F' }}>{review.candidate.college}</strong>
            </div>
            <div style={{ fontSize: '12px', color: '#64748B' }}>
              {review.candidate.department} • {review.candidate.year_of_study} • {review.candidate.email}
            </div>
          </div>

          {/* Scorecards */}
          <div style={{ display: 'flex', gap: '14px', textAlign: 'center', flexWrap: 'wrap' }}>
            <div
              style={{
                backgroundColor: '#FAF7F3',
                padding: '14px 22px',
                borderRadius: '12px',
                border: '1.5px solid rgba(245, 184, 61, 0.3)',
                minWidth: '110px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Total Score
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#0B2E6F', margin: '2px 0' }}>
                {review.total_score} <span style={{ fontSize: '14px', color: '#94A3B8' }}>/ 50</span>
              </div>
              <div style={{ fontSize: '12px', color: '#16A34A', fontWeight: 800 }}>{review.percentage}%</div>
            </div>

            <div
              style={{
                backgroundColor: '#FAF7F3',
                padding: '14px 20px',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                minWidth: '100px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Aptitude
              </div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: '#1455B8', margin: '2px 0' }}>
                {review.aptitude_score} <span style={{ fontSize: '13px', color: '#94A3B8' }}>/ 25</span>
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>Section 1</div>
            </div>

            <div
              style={{
                backgroundColor: '#FAF7F3',
                padding: '14px 20px',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                minWidth: '100px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Coding
              </div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: '#059669', margin: '2px 0' }}>
                {review.coding_score} <span style={{ fontSize: '13px', color: '#94A3B8' }}>/ 25</span>
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>Section 2</div>
            </div>
          </div>
        </div>

        {/* Telemetry Row */}
        <div
          style={{
            marginTop: '22px',
            paddingTop: '16px',
            borderTop: '1px solid #E2E8F0',
            display: 'flex',
            gap: '24px',
            fontSize: '12px',
            color: '#475569',
            flexWrap: 'wrap',
          }}
        >
          <div>
            Started: <strong>{new Date(review.started_at).toLocaleString()}</strong>
          </div>
          <div>
            Submitted:{' '}
            <strong>
              {review.submitted_at ? new Date(review.submitted_at).toLocaleString() : 'In Progress'}
            </strong>
          </div>
          <div>
            Tab Switches Recorded:{' '}
            <strong style={{ color: review.tab_switch_count >= 2 ? '#DC2626' : '#0B2E6F' }}>
              {review.tab_switch_count}
            </strong>
          </div>
          <div>
            Fullscreen Exits: <strong>{review.fullscreen_exit_count}</strong>
          </div>
          <div>
            Questions Answered:{' '}
            <strong>
              {review.answered_count} / {review.total_questions || 50}
            </strong>
          </div>
        </div>

        {review.flag_reason && (
          <div
            style={{
              marginTop: '16px',
              backgroundColor: '#FEF2F2',
              border: '1.5px solid #FECACA',
              padding: '12px 16px',
              borderRadius: '10px',
              fontSize: '12px',
              color: '#991B1B',
            }}
          >
            <strong>Proctoring Audit Log / Reason:</strong> {review.flag_reason}
          </div>
        )}
      </div>

      {/* Proctoring & Integrity Events Section */}
      {review.integrity_events && review.integrity_events.length > 0 && (
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid rgba(245, 184, 61, 0.25)',
            padding: '20px 24px',
            marginBottom: '24px',
            boxShadow: '0 4px 12px rgba(11, 46, 111, 0.03)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              Recorded Session Telemetry & Integrity Events ({review.integrity_events.length})
            </h3>
            <span style={{ fontSize: '12px', color: '#64748B' }}>
              Client Visibility Transitions & Fullscreen Events
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {review.integrity_events.map((ev) => {
              const isViolation =
                ev.event_type.includes('HIDDEN') ||
                ev.event_type.includes('EXIT') ||
                ev.event_type.includes('EXCEEDED');

              return (
                <div
                  key={ev.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    backgroundColor: '#FAF7F3',
                    border: '1px solid #E2E8F0',
                    borderRadius: '8px',
                    fontSize: '12px',
                    flexWrap: 'wrap',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontWeight: 800,
                        fontFamily: 'monospace',
                        fontSize: '11px',
                        backgroundColor: isViolation ? '#FEF2F2' : '#EFF6FF',
                        color: isViolation ? '#DC2626' : '#1455B8',
                        border: `1px solid ${isViolation ? '#FECACA' : '#BFDBFE'}`,
                      }}
                    >
                      {ev.event_type}
                    </span>

                    {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                      <span style={{ color: '#475569', fontFamily: 'monospace' }}>
                        {JSON.stringify(ev.metadata)}
                      </span>
                    )}

                    {ev.review_notes && (
                      <span style={{ color: '#166534', fontSize: '11px' }}>
                        (Note: {ev.review_notes})
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ color: '#94A3B8', fontSize: '11px' }}>
                      {new Date(ev.created_at || (ev as any).timestamp).toLocaleTimeString()}
                    </span>

                    {ev.is_reviewed ? (
                      <span
                        style={{
                          fontSize: '11px',
                          color: '#166534',
                          fontWeight: 700,
                          backgroundColor: '#DCFCE7',
                          padding: '2px 8px',
                          borderRadius: '9999px',
                        }}
                      >
                        ✓ Reviewed
                      </span>
                    ) : (
                      <button
                        onClick={() => openEventReviewModal(ev)}
                        style={{
                          padding: '3px 10px',
                          backgroundColor: '#FFFFFF',
                          border: '1px solid #CBD5E1',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 700,
                          color: '#0B2E6F',
                          cursor: 'pointer',
                        }}
                      >
                        Review Event
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Questions Filter Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setSectionFilter('ALL')}
            style={{
              padding: '6px 14px',
              borderRadius: '8px',
              border: sectionFilter === 'ALL' ? 'none' : '1px solid #CBD5E1',
              backgroundColor: sectionFilter === 'ALL' ? '#0B2E6F' : '#FFFFFF',
              color: sectionFilter === 'ALL' ? '#FFFFFF' : '#475569',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            All 50 Questions
          </button>
          <button
            onClick={() => setSectionFilter('APTITUDE')}
            style={{
              padding: '6px 14px',
              borderRadius: '8px',
              border: sectionFilter === 'APTITUDE' ? 'none' : '1px solid #CBD5E1',
              backgroundColor: sectionFilter === 'APTITUDE' ? '#1455B8' : '#FFFFFF',
              color: sectionFilter === 'APTITUDE' ? '#FFFFFF' : '#475569',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Aptitude (25)
          </button>
          <button
            onClick={() => setSectionFilter('CODING')}
            style={{
              padding: '6px 14px',
              borderRadius: '8px',
              border: sectionFilter === 'CODING' ? 'none' : '1px solid #CBD5E1',
              backgroundColor: sectionFilter === 'CODING' ? '#059669' : '#FFFFFF',
              color: sectionFilter === 'CODING' ? '#FFFFFF' : '#475569',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Coding (25)
          </button>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: '#64748B', fontWeight: 600 }}>Filter by Outcome:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid #CBD5E1',
              fontSize: '12px',
              backgroundColor: '#FFFFFF',
            }}
          >
            <option value="ALL">All Outcomes</option>
            <option value="CORRECT">Correct Only</option>
            <option value="INCORRECT">Incorrect Only</option>
            <option value="UNANSWERED">Unanswered Only</option>
          </select>
        </div>
      </div>

      {/* Question Snapshots List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {filteredQuestions.length === 0 ? (
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '36px',
              textAlign: 'center',
              color: '#64748B',
              border: '1px solid #E2E8F0',
            }}
          >
            No questions match the current filter selection.
          </div>
        ) : (
          filteredQuestions.map((q) => {
            const isCorrect = q.is_correct === true;
            const isUnanswered = !q.selected_option || !q.selected_option.trim();
            const isIncorrect = !isUnanswered && !isCorrect;
            const marksAwarded = q.marks_awarded !== undefined ? q.marks_awarded : isCorrect ? 1 : 0;

            const optionsMap = [
              { key: 'A', text: q.option_a_text },
              { key: 'B', text: q.option_b_text },
              { key: 'C', text: q.option_c_text },
              { key: 'D', text: q.option_d_text },
            ];

            return (
              <div
                key={q.id}
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: `1.5px solid ${
                    isCorrect ? '#86EFAC' : isIncorrect ? '#FCA5A5' : '#E2E8F0'
                  }`,
                  padding: '20px 24px',
                  boxShadow: '0 2px 8px rgba(11, 46, 111, 0.03)',
                }}
              >
                {/* Question Header */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '12px',
                    flexWrap: 'wrap',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 800, fontSize: '13px', color: '#0B2E6F' }}>
                      Question #{q.question_order}
                    </span>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: q.section_type === 'APTITUDE' ? '#EFF6FF' : '#ECFDF5',
                        color: q.section_type === 'APTITUDE' ? '#1455B8' : '#059669',
                      }}
                    >
                      {q.section_type}
                    </span>
                    <span style={{ fontSize: '11px', color: '#64748B' }}>Topic: {q.category}</span>
                  </div>

                  <div>
                    {isCorrect ? (
                      <span
                        style={{
                          padding: '3px 12px',
                          borderRadius: '9999px',
                          backgroundColor: '#DCFCE7',
                          color: '#166534',
                          fontWeight: 800,
                          fontSize: '11px',
                        }}
                      >
                        ✓ Correct (+{marksAwarded} Mark)
                      </span>
                    ) : isIncorrect ? (
                      <span
                        style={{
                          padding: '3px 12px',
                          borderRadius: '9999px',
                          backgroundColor: '#FEE2E2',
                          color: '#991B1B',
                          fontWeight: 800,
                          fontSize: '11px',
                        }}
                      >
                        ✕ Incorrect (0 Marks)
                      </span>
                    ) : (
                      <span
                        style={{
                          padding: '3px 12px',
                          borderRadius: '9999px',
                          backgroundColor: '#F1F5F9',
                          color: '#64748B',
                          fontWeight: 700,
                          fontSize: '11px',
                        }}
                      >
                        Unanswered (0 Marks)
                      </span>
                    )}
                  </div>
                </div>

                {/* Question Prompt */}
                <div
                  style={{
                    fontSize: '15px',
                    fontWeight: 600,
                    color: '#111111',
                    marginBottom: '16px',
                    lineHeight: 1.5,
                  }}
                >
                  {q.prompt}
                </div>

                {/* Shuffled Options for this attempt */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '10px',
                    marginBottom: '14px',
                  }}
                >
                  {optionsMap.map((opt) => {
                    const isCandidateSelected = q.selected_option === opt.key;
                    const isCorrectAnswer = Boolean(q.correct_option_key && q.correct_option_key === opt.key);

                    let optBg = '#FFFFFF';
                    let optBorder = '1px solid #E2E8F0';
                    let optColor = '#334155';

                    if (isCorrectAnswer) {
                      optBg = '#F0FDF4';
                      optBorder = '1.5px solid #16A34A';
                      optColor = '#166534';
                    } else if (isCandidateSelected && !isCorrectAnswer) {
                      optBg = '#FEF2F2';
                      optBorder = '1.5px solid #DC2626';
                      optColor = '#991B1B';
                    }

                    return (
                      <div
                        key={opt.key}
                        style={{
                          padding: '10px 14px',
                          borderRadius: '8px',
                          border: optBorder,
                          backgroundColor: optBg,
                          color: optColor,
                          fontSize: '13px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                        }}
                      >
                        <strong style={{ fontFamily: 'monospace', fontSize: '13px' }}>{opt.key}:</strong>
                        <span>{opt.text}</span>

                        {isCorrectAnswer && (
                          <span
                            style={{
                              marginLeft: 'auto',
                              fontWeight: 800,
                              fontSize: '11px',
                              backgroundColor: '#DCFCE7',
                              color: '#166534',
                              padding: '2px 6px',
                              borderRadius: '4px',
                            }}
                          >
                            Correct Answer
                          </span>
                        )}

                        {isCandidateSelected && (
                          <span
                            style={{
                              marginLeft: isCorrectAnswer ? '4px' : 'auto',
                              fontWeight: 800,
                              fontSize: '11px',
                              backgroundColor: isCorrectAnswer ? '#DCFCE7' : '#FEE2E2',
                              color: isCorrectAnswer ? '#166534' : '#991B1B',
                              padding: '2px 6px',
                              borderRadius: '4px',
                            }}
                          >
                            Candidate Selected
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Explanation */}
                {q.explanation && (
                  <div
                    style={{
                      fontSize: '12px',
                      color: '#475569',
                      backgroundColor: '#FAF7F3',
                      border: '1px solid #E2E8F0',
                      padding: '10px 14px',
                      borderRadius: '8px',
                    }}
                  >
                    <strong style={{ color: '#0B2E6F' }}>Explanation:</strong> {q.explanation}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Flag / Clear Flag Modal */}
      {showFlagModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              border: '1.5px solid rgba(245, 184, 61, 0.4)',
              boxShadow: '0 16px 36px rgba(11, 46, 111, 0.2)',
              width: '100%',
              maxWidth: '520px',
              padding: '26px',
            }}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 8px 0' }}>
              {pendingFlagAction === 'FLAG'
                ? 'Flag Attempt for Integrity Review'
                : 'Clear Attempt Integrity Flag'}
            </h3>
            <p style={{ fontSize: '13px', color: '#64748B', margin: '0 0 16px 0' }}>
              {pendingFlagAction === 'FLAG'
                ? 'Record an administrative flag and justification note for suspicious activity.'
                : 'Confirm that this attempt has been reviewed and cleared of integrity violations.'}
            </p>

            <form onSubmit={handleConfirmFlagAction}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#0B2E6F', marginBottom: '6px' }}>
                  Administrative Review Notes
                </label>
                <textarea
                  rows={3}
                  value={flagNotes}
                  onChange={(e) => setFlagNotes(e.target.value)}
                  placeholder="Enter audit notes..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowFlagModal(false)}
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
                  disabled={updatingFlag}
                  style={{
                    padding: '8px 20px',
                    backgroundColor: pendingFlagAction === 'FLAG' ? '#DC2626' : '#16A34A',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {updatingFlag ? 'Saving...' : 'Confirm Action'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Review Event Modal from Attempt Review Screen */}
      {selectedEvent && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              border: '1.5px solid rgba(245, 184, 61, 0.4)',
              boxShadow: '0 16px 36px rgba(11, 46, 111, 0.2)',
              width: '100%',
              maxWidth: '500px',
              padding: '24px',
            }}
          >
            <h3 style={{ fontSize: '17px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 12px 0' }}>
              Review Integrity Event
            </h3>

            <form onSubmit={handleSaveEventReview}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0B2E6F', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={eventIsReviewed}
                    onChange={(e) => setEventIsReviewed(e.target.checked)}
                    style={{ width: '16px', height: '16px', accentColor: '#16A34A' }}
                  />
                  <span>Mark as Reviewed</span>
                </label>
              </div>

              <div style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#0B2E6F', marginBottom: '6px' }}>
                  Review Notes
                </label>
                <textarea
                  rows={3}
                  value={eventReviewNotes}
                  onChange={(e) => setEventReviewNotes(e.target.value)}
                  placeholder="Audit justification..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
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
                  disabled={savingEventReview}
                  style={{
                    padding: '8px 18px',
                    backgroundColor: '#16A34A',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {savingEventReview ? 'Saving...' : 'Save Review'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
