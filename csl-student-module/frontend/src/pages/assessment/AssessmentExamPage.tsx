import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import cslTypographyLogo from '../../assets/CSL-TYPOGRAPHY.png';
import {
  getAttemptState,
  saveAnswer,
  recordIntegrityEvent,
  finalizeAssessment,
  type AttemptDetailResponse,
  type QuestionSnapshot,
} from '../../api/assessment';

export function AssessmentExamPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();

  const [attempt, setAttempt] = useState<AttemptDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [markedForLater, setMarkedForLater] = useState<Record<number, boolean>>({});
  const [saveStatus, setSaveStatus] = useState<Record<number, 'saved' | 'saving' | 'failed'>>({});

  // Active section tab for navigation filtering ('APTITUDE' vs 'CODING')
  const [activeSectionTab, setActiveSectionTab] = useState<'APTITUDE' | 'CODING'>('APTITUDE');

  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const [targetEndTimeMs, setTargetEndTimeMs] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [showSubmitModal, setShowSubmitModal] = useState<boolean>(false);

  // Proctoring & Integrity States
  const [tabWarning, setTabWarning] = useState<string>('');
  const [fullscreenWarning, setFullscreenWarning] = useState<string>('');
  const [securityWarning, setSecurityWarning] = useState<string>('');
  const [terminalNotice, setTerminalNotice] = useState<string>('');
  const [isFullscreen, setIsFullscreen] = useState<boolean>(true);

  const isPageHiddenRef = useRef<boolean>(false);

  // 1. Fetch initial attempt state
  const loadAttempt = useCallback(async () => {
    if (!attemptId) return;
    try {
      setLoading(true);
      setError('');
      const data = await getAttemptState(attemptId);
      if (
        data.state === 'SUBMITTED' ||
        data.state === 'TIMED_OUT' ||
        data.state === 'FLAGGED_FOR_REVIEW'
      ) {
        navigate(`/assessment/results/${data.id}`, { replace: true });
        return;
      }
      setAttempt(data);

      // Hydrate answers and save states
      const initialAns: Record<number, string> = {};
      const initialSave: Record<number, 'saved' | 'saving' | 'failed'> = {};
      data.questions.forEach((q) => {
        if (q.selected_option && q.selected_option.trim()) {
          initialAns[q.question_order] = q.selected_option;
          initialSave[q.question_order] = 'saved';
        }
      });
      setAnswers(initialAns);
      setSaveStatus(initialSave);

      // Restore bookmarks from local storage if existing for this attempt
      try {
        const savedMarks = localStorage.getItem(`csl_marked_${data.id}`);
        if (savedMarks) {
          setMarkedForLater(JSON.parse(savedMarks));
        }
      } catch {
        // ignore
      }

      // Authoritative timer synchronization using server remaining_seconds
      const serverRemaining = Math.max(0, data.remaining_seconds ?? 0);
      setRemainingSeconds(serverRemaining);
      setTargetEndTimeMs(Date.now() + serverRemaining * 1000);
    } catch (err: unknown) {
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axErr.response?.status === 403 || axErr.response?.status === 401) {
          setError('Session expired or unauthorized. Please re-register.');
        } else {
          setError(axErr.response?.data?.detail || 'Failed to load attempt.');
        }
      } else {
        setError('Network error loading test.');
      }
    } finally {
      setLoading(false);
    }
  }, [attemptId, navigate]);

  useEffect(() => {
    loadAttempt();
  }, [loadAttempt]);

  // Keep active section tab synchronized with current question section
  useEffect(() => {
    if (attempt && attempt.questions[currentIndex]) {
      const qSection = attempt.questions[currentIndex].section_type;
      if (qSection && qSection !== activeSectionTab) {
        setActiveSectionTab(qSection);
      }
    }
  }, [currentIndex, attempt, activeSectionTab]);

  // Final Submission Handlers
  const handleConfirmSubmit = useCallback(async () => {
    if (!attemptId || submitting) return;
    setSubmitting(true);
    try {
      const res = await finalizeAssessment(attemptId);
      navigate(`/assessment/results/${res.id}`, { replace: true });
    } catch {
      alert('Error submitting assessment. Retrying finalize...');
      setSubmitting(false);
    }
  }, [attemptId, submitting, navigate]);

  const handleAutoSubmitOnTimeout = useCallback(async () => {
    if (!attemptId || submitting) return;
    setSubmitting(true);
    setTerminalNotice(
      'Assessment duration elapsed. Your test is being automatically submitted...'
    );
    try {
      const res = await finalizeAssessment(attemptId);
      navigate(`/assessment/results/${res.id}`, { replace: true });
    } catch {
      navigate(`/assessment/results/${attemptId}`, { replace: true });
    }
  }, [attemptId, submitting, navigate]);

  // 2. Countdown Timer derived from authoritative server deadline
  useEffect(() => {
    if (!targetEndTimeMs || submitting) return;

    const tick = () => {
      const remaining = Math.max(0, Math.ceil((targetEndTimeMs - Date.now()) / 1000));
      setRemainingSeconds(remaining);

      if (remaining <= 0) {
        clearInterval(timer);
        handleAutoSubmitOnTimeout();
      }
    };

    tick();
    const timer = setInterval(tick, 1000);

    return () => clearInterval(timer);
  }, [targetEndTimeMs, submitting, handleAutoSubmitOnTimeout]);

  // 3. Tab switch enforcement (two switches permitted with warning, third auto-submits)
  useEffect(() => {
    if (!attemptId || submitting) return;

    const handleVisibilityChange = async () => {
      if (document.hidden) {
        if (isPageHiddenRef.current) return;
        isPageHiddenRef.current = true;

        const eventId = `${attemptId}_tab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        try {
          const res = await recordIntegrityEvent(attemptId, 'TAB_HIDDEN', eventId);

          if (res.is_finalized || res.state === 'FLAGGED_FOR_REVIEW') {
            setSubmitting(true);
            setTerminalNotice(
              'The assessment was automatically submitted because the tab-switch limit was reached.'
            );
            setTimeout(() => {
              navigate(`/assessment/results/${attemptId}`, { replace: true });
            }, 2500);
            return;
          }

          // Switches 1 and 2: Concise warning only, no remaining counter displayed
          setTabWarning('Warning: Switching tabs is not permitted during the assessment.');
        } catch (err) {
          console.error('Integrity event network error:', err);
          setTabWarning('Warning: Switching tabs is not permitted during the assessment.');
        }
      } else {
        if (!isPageHiddenRef.current) return;
        isPageHiddenRef.current = false;
        try {
          const eventId = `${attemptId}_vis_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
          await recordIntegrityEvent(attemptId, 'TAB_VISIBLE', eventId);
        } catch (err) {
          console.error('Visibility restore event error:', err);
        }
      }
    };

    const handleFullscreenChange = async () => {
      const currentlyFs = !!document.fullscreenElement;
      setIsFullscreen(currentlyFs);

      if (!currentlyFs && !submitting) {
        const eventId = `${attemptId}_fs_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        try {
          await recordIntegrityEvent(attemptId, 'FULLSCREEN_EXIT', eventId);
          setFullscreenWarning(
            'Fullscreen mode exited. Please return to fullscreen mode during the examination.'
          );
        } catch (err) {
          console.error('Fullscreen exit event error:', err);
        }
      } else if (currentlyFs) {
        setFullscreenWarning('');
      }
    };

    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();
      setSecurityWarning('Right-click context menu is disabled for assessment integrity.');
      if (attemptId && !submitting) {
        const eventId = `${attemptId}_ctx_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        recordIntegrityEvent(attemptId, 'CONTEXT_MENU_BLOCKED', eventId, {
          target: (e.target as HTMLElement)?.tagName || 'DOCUMENT',
        }).catch(() => {});
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      const isF12 = e.key === 'F12';
      const isInspect = (e.ctrlKey || e.metaKey) && e.shiftKey && ['I', 'J', 'C', 'i', 'j', 'c'].includes(e.key);
      const isViewSource = (e.ctrlKey || e.metaKey) && ['U', 'u'].includes(e.key);

      if (isF12 || isInspect || isViewSource) {
        e.preventDefault();
        e.stopPropagation();
        const shortcutName = isF12 ? 'F12 Developer Tools' : isInspect ? 'Inspect Shortcut' : 'Page Source Shortcut';
        setSecurityWarning(`${shortcutName} is disabled during the assessment.`);
        if (attemptId && !submitting) {
          const eventId = `${attemptId}_dt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
          recordIntegrityEvent(attemptId, 'DEVTOOLS_SHORTCUT', eventId, {
            key: e.key,
            code: e.code,
            ctrlKey: e.ctrlKey,
            metaKey: e.metaKey,
            shiftKey: e.shiftKey,
          }).catch(() => {});
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('contextmenu', handleContextMenu);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('contextmenu', handleContextMenu);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [attemptId, submitting, navigate]);

  useEffect(() => {
    if (!securityWarning) return;
    const timer = setTimeout(() => setSecurityWarning(''), 4500);
    return () => clearTimeout(timer);
  }, [securityWarning]);

  // Action to re-enter fullscreen
  const handleReenterFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        setIsFullscreen(true);
        setFullscreenWarning('');
      }
    } catch (err) {
      console.error('Failed to re-enter fullscreen:', err);
    }
  };

  // 4. Answer Selection
  const handleSelectOption = async (questionOrder: number, optionKey: string) => {
    if (!attemptId || submitting) return;

    setAnswers((prev) => ({ ...prev, [questionOrder]: optionKey }));
    setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'saving' }));

    try {
      await saveAnswer(attemptId, questionOrder, optionKey);
      setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'saved' }));
    } catch {
      setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'failed' }));
    }
  };

  // 5. Clear Answer
  const handleClearAnswer = async (questionOrder: number) => {
    if (!attemptId || submitting) return;

    setAnswers((prev) => {
      const copy = { ...prev };
      delete copy[questionOrder];
      return copy;
    });
    setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'saving' }));

    try {
      await saveAnswer(attemptId, questionOrder, '');
      setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'saved' }));
    } catch {
      setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'failed' }));
    }
  };

  // 6. Toggle Mark for Later
  const handleToggleMarkForLater = (questionOrder: number) => {
    setMarkedForLater((prev) => {
      const next = { ...prev, [questionOrder]: !prev[questionOrder] };
      if (attempt) {
        try {
          localStorage.setItem(`csl_marked_${attempt.id}`, JSON.stringify(next));
        } catch {
          // ignore
        }
      }
      return next;
    });
  };

  // Retry save
  const handleRetrySave = async (questionOrder: number) => {
    const selected = answers[questionOrder];
    if (selected === undefined || !attemptId || submitting) return;
    setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'saving' }));
    try {
      await saveAnswer(attemptId, questionOrder, selected);
      setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'saved' }));
    } catch {
      setSaveStatus((prev) => ({ ...prev, [questionOrder]: 'failed' }));
    }
  };

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              border: '3px solid #E2E8F0',
              borderTopColor: '#1455B8',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 16px',
            }}
          />
          <p style={{ fontSize: '15px', color: '#0B2E6F', fontWeight: 700 }}>
            Initializing exam environment...
          </p>
        </div>
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          padding: '16px',
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '460px',
            width: '100%',
            backgroundColor: '#FFFFFF',
            padding: '32px',
            borderRadius: '16px',
            border: '1px solid rgba(245, 184, 61, 0.3)',
            boxShadow: '0 10px 25px -5px rgba(11, 46, 111, 0.08)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
          <h2 style={{ color: '#DC2626', fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>
            Unable to Access Assessment
          </h2>
          <p style={{ fontSize: '14px', color: '#6B7280', marginBottom: '20px' }}>{error}</p>
          <button
            onClick={() => navigate('/assessment/register')}
            style={{
              padding: '10px 20px',
              background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Return to Registration
          </button>
        </div>
      </div>
    );
  }

  const currentQ: QuestionSnapshot = attempt.questions[currentIndex];
  const answeredCount = Object.keys(answers).filter((k) => !!answers[Number(k)]).length;

  // Filter questions for active section tab
  const sectionQuestions = attempt.questions.filter((q) => q.section_type === activeSectionTab);
  const sectionAnsweredCount = sectionQuestions.filter(
    (q) => !!answers[q.question_order]
  ).length;

  // Position within section (1-indexed, e.g. "Question 1 of 25")
  const currentSectionIndex =
    sectionQuestions.findIndex((q) => q.question_order === currentQ.question_order) + 1;
  const questionNumberInSection = currentSectionIndex > 0 ? currentSectionIndex : currentQ.question_order;

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const timerDisplay = formatTime(remainingSeconds);
  const isUrgent = remainingSeconds < 300; // < 5 mins
  const isCritical = remainingSeconds < 60; // < 1 min

  return (
    <div
      style={{
        height: '100vh',
        maxHeight: '100vh',
        overflow: 'hidden',
        backgroundColor: '#FCFAF5',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        boxSizing: 'border-box',
      }}
    >
      {/* ─── 1. TOP HEADER (BRAND ALIGNED WITH MOCKUP) ─────────────────── */}
      <header
        style={{
          height: '68px',
          minHeight: '68px',
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid rgba(245, 184, 61, 0.3)',
          padding: '0 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxSizing: 'border-box',
          zIndex: 20,
        }}
      >
        {/* Left: CSL Typography Logo & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <img
            src={cslTypographyLogo}
            alt="CSL Creator Space Lab"
            style={{ height: '36px', width: 'auto', objectFit: 'contain' }}
          />
          <div
            style={{
              height: '32px',
              width: '1px',
              backgroundColor: '#E5E7EB',
            }}
          />
          <div>
            <h1
              style={{
                fontSize: '17px',
                fontWeight: 800,
                color: '#0B2E6F',
                margin: 0,
                lineHeight: 1.2,
              }}
            >
              {attempt?.assessment_title || 'Initial Assessment'}
            </h1>
            <p
              style={{
                fontSize: '12px',
                color: '#6B7280',
                margin: '2px 0 0 0',
                fontWeight: 500,
              }}
            >
              {attempt?.assessment_code ? `${attempt.assessment_code} • ` : ''}Total {attempt?.total_questions || 50} Questions
            </p>
          </div>
        </div>

        {/* Center: Proctoring Status Badges (Mockup Shields) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
          {/* Secure Mode */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: '#DCFCE7',
                color: '#16A34A',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '11px',
                fontWeight: 800,
              }}
            >
              🛡️
            </div>
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#374151', lineHeight: 1.1 }}>
                Secure Mode
              </div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#16A34A' }}>Active</div>
            </div>
          </div>

          {/* Fullscreen Mode */}
          <div
            onClick={!isFullscreen ? handleReenterFullscreen : undefined}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              cursor: !isFullscreen ? 'pointer' : 'default',
            }}
          >
            <div
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: isFullscreen ? '#DCFCE7' : '#FEF3C7',
                color: isFullscreen ? '#16A34A' : '#D97706',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '11px',
                fontWeight: 800,
              }}
            >
              {isFullscreen ? '✓' : '!'}
            </div>
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#374151', lineHeight: 1.1 }}>
                Fullscreen
              </div>
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: isFullscreen ? '#16A34A' : '#D97706',
                }}
              >
                {isFullscreen ? 'Enabled' : 'Click to Re-enter'}
              </div>
            </div>
          </div>

          {/* Monitoring Active */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: '#DCFCE7',
                color: '#16A34A',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '11px',
                fontWeight: 800,
              }}
            >
              👁️
            </div>
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#374151', lineHeight: 1.1 }}>
                Monitoring
              </div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#16A34A' }}>Active</div>
            </div>
          </div>
        </div>

        {/* Right: Time Remaining Card (Exact Mockup Box) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: '#FFFDF9',
              border: `1.5px solid ${isCritical ? '#FCA5A5' : 'rgba(245, 184, 61, 0.45)'}`,
              borderRadius: '12px',
              padding: '6px 18px',
              boxShadow: '0 2px 8px -2px rgba(11, 46, 111, 0.05)',
            }}
          >
            {/* Clock Icon Circle */}
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                border: `2px solid ${isCritical ? '#DC2626' : '#F5B83D'}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '15px',
                color: isCritical ? '#DC2626' : '#B45309',
              }}
            >
              ⏱
            </div>
            <div>
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  color: isCritical ? '#DC2626' : '#6B7280',
                  textTransform: 'capitalize',
                  letterSpacing: '0.02em',
                  lineHeight: 1.1,
                }}
              >
                Time Remaining
              </div>
              <div
                style={{
                  fontSize: '20px',
                  fontWeight: 800,
                  fontFamily: 'monospace',
                  color: isCritical ? '#DC2626' : isUrgent ? '#D97706' : '#0B2E6F',
                  lineHeight: 1.2,
                }}
              >
                {timerDisplay}
              </div>
            </div>
          </div>

          <button
            onClick={() => setShowSubmitModal(true)}
            style={{
              padding: '8px 18px',
              backgroundColor: '#16A34A',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 2px 6px rgba(22, 163, 74, 0.25)',
              transition: 'background-color 0.15s ease',
            }}
          >
            Submit Test
          </button>
        </div>
      </header>

      {/* Warnings & Integrity Notices */}
      {tabWarning && (
        <div
          style={{
            backgroundColor: '#FEF3C7',
            borderBottom: '1px solid #FDE68A',
            color: '#92400E',
            padding: '8px 24px',
            fontSize: '13px',
            fontWeight: 600,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxSizing: 'border-box',
          }}
        >
          <span>⚠️ {tabWarning}</span>
          <button
            onClick={() => setTabWarning('')}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#92400E',
              fontWeight: 700,
              fontSize: '12px',
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {fullscreenWarning && (
        <div
          style={{
            backgroundColor: '#FFFBEB',
            borderBottom: '1px solid #FDE68A',
            color: '#B45309',
            padding: '8px 24px',
            fontSize: '13px',
            fontWeight: 600,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxSizing: 'border-box',
          }}
        >
          <span>⚠️ {fullscreenWarning}</span>
          <button
            onClick={handleReenterFullscreen}
            style={{
              padding: '4px 12px',
              background: '#0B2E6F',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
            }}
          >
            Re-enter Fullscreen
          </button>
        </div>
      )}

      {securityWarning && (
        <div
          style={{
            backgroundColor: '#FEF2F2',
            borderBottom: '1px solid #FECACA',
            color: '#B91C1C',
            padding: '8px 24px',
            fontSize: '13px',
            fontWeight: 700,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxSizing: 'border-box',
          }}
        >
          <span>🛡️ Security Alert: {securityWarning}</span>
          <button
            onClick={() => setSecurityWarning('')}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#B91C1C',
              fontWeight: 700,
              fontSize: '12px',
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ─── 2. MAIN 3-COLUMN WORKSPACE (SINGLE-VIEWPORT FIT) ─────────── */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          gap: '16px',
          padding: '16px 24px',
          overflow: 'hidden',
          boxSizing: 'border-box',
        }}
      >
        {/* ─── COLUMN 1: LEFT SECTION & QUESTION LIST (w-[260px]) ──────── */}
        <aside
          style={{
            width: '260px',
            minWidth: '260px',
            maxWidth: '260px',
            backgroundColor: '#FFFFFF',
            borderRadius: '14px',
            border: '1px solid rgba(245, 184, 61, 0.28)',
            boxShadow: '0 4px 16px -2px rgba(11, 46, 111, 0.05)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* Top: Section Switcher Tabs */}
          <div
            style={{
              padding: '12px',
              borderBottom: '1px solid #FAF7F3',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '8px',
            }}
          >
            {/* Aptitude Tab */}
            <button
              onClick={() => {
                setActiveSectionTab('APTITUDE');
                const firstAptIdx = attempt.questions.findIndex(
                  (q) => q.section_type === 'APTITUDE'
                );
                if (firstAptIdx !== -1 && currentQ.section_type !== 'APTITUDE') {
                  setCurrentIndex(firstAptIdx);
                }
              }}
              style={{
                padding: '8px 6px',
                borderRadius: '8px',
                border: activeSectionTab === 'APTITUDE' ? 'none' : '1px solid #E2E8F0',
                backgroundColor: activeSectionTab === 'APTITUDE' ? '#1455B8' : '#FFFFFF',
                color: activeSectionTab === 'APTITUDE' ? '#FFFFFF' : '#475569',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                <span>🎯</span> Aptitude
              </div>
              <div
                style={{
                  fontSize: '10px',
                  color: activeSectionTab === 'APTITUDE' ? '#E0E7FF' : '#94A3B8',
                  marginTop: '2px',
                }}
              >
                25 Questions
              </div>
            </button>

            {/* Coding Tab */}
            <button
              onClick={() => {
                setActiveSectionTab('CODING');
                const firstCodIdx = attempt.questions.findIndex((q) => q.section_type === 'CODING');
                if (firstCodIdx !== -1 && currentQ.section_type !== 'CODING') {
                  setCurrentIndex(firstCodIdx);
                }
              }}
              style={{
                padding: '8px 6px',
                borderRadius: '8px',
                border: activeSectionTab === 'CODING' ? 'none' : '1px solid #E2E8F0',
                backgroundColor: activeSectionTab === 'CODING' ? '#1455B8' : '#FFFFFF',
                color: activeSectionTab === 'CODING' ? '#FFFFFF' : '#475569',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                <span>&lt;/&gt;</span> Coding
              </div>
              <div
                style={{
                  fontSize: '10px',
                  color: activeSectionTab === 'CODING' ? '#E0E7FF' : '#94A3B8',
                  marginTop: '2px',
                }}
              >
                25 Questions
              </div>
            </button>
          </div>

          {/* Section Progress Bar */}
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #FAF7F3' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '11px',
                fontWeight: 600,
                color: '#6B7280',
                marginBottom: '6px',
              }}
            >
              <span>Section Progress</span>
              <strong style={{ color: '#0B2E6F' }}>
                {sectionAnsweredCount} / {sectionQuestions.length}
              </strong>
            </div>
            <div
              style={{
                width: '100%',
                height: '5px',
                backgroundColor: '#F1F5F9',
                borderRadius: '9999px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${(sectionAnsweredCount / (sectionQuestions.length || 1)) * 100}%`,
                  backgroundColor: '#1455B8',
                  borderRadius: '9999px',
                  transition: 'width 0.2s ease',
                }}
              />
            </div>
          </div>

          {/* Questions Vertical List */}
          <div
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              padding: '6px 8px',
              display: 'flex',
              flexDirection: 'column',
              gap: '2px',
            }}
          >
            {sectionQuestions.map((q, secIdx) => {
              const fullIndex = attempt.questions.findIndex((item) => item.question_order === q.question_order);
              const isSelected = fullIndex === currentIndex;
              const hasAnswer = !!answers[q.question_order];
              const isMarked = !!markedForLater[q.question_order];

              return (
                <button
                  key={q.question_order}
                  onClick={() => setCurrentIndex(fullIndex)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '7px 10px',
                    borderRadius: '8px',
                    border: 'none',
                    borderLeft: isSelected ? '3.5px solid #16A34A' : '3.5px solid transparent',
                    backgroundColor: isSelected
                      ? '#F0FDF4'
                      : 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.1s ease',
                    boxSizing: 'border-box',
                  }}
                >
                  {/* Question Number e.g. Q1 */}
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: isSelected ? 800 : 700,
                      color: isSelected ? '#166534' : '#1F2937',
                      minWidth: '26px',
                    }}
                  >
                    Q{secIdx + 1}
                  </span>

                  {/* Status Indicator Icon */}
                  <span style={{ display: 'flex', alignItems: 'center' }}>
                    {hasAnswer ? (
                      <span
                        style={{
                          width: '16px',
                          height: '16px',
                          borderRadius: '50%',
                          backgroundColor: '#16A34A',
                          color: '#FFFFFF',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '10px',
                          fontWeight: 800,
                        }}
                      >
                        ✓
                      </span>
                    ) : isMarked ? (
                      <span style={{ fontSize: '13px', color: '#D97706' }}>🔖</span>
                    ) : (
                      <span
                        style={{
                          width: '14px',
                          height: '14px',
                          borderRadius: '50%',
                          border: '1.5px solid #CBD5E1',
                          backgroundColor: '#FFFFFF',
                        }}
                      />
                    )}
                  </span>

                  {/* Category / Topic Name */}
                  <span
                    style={{
                      fontSize: '11px',
                      color: isSelected ? '#15803D' : '#64748B',
                      fontWeight: isSelected ? 700 : 500,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      flex: 1,
                    }}
                    title={q.category || q.section_type}
                  >
                    {q.category || (q.section_type === 'APTITUDE' ? 'Aptitude' : 'Coding')}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Bottom Legend */}
          <div
            style={{
              padding: '10px 12px',
              borderTop: '1px solid #FAF7F3',
              backgroundColor: '#FAF7F3',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              fontSize: '10px',
              color: '#64748B',
              fontWeight: 600,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: '#16A34A',
                }}
              />
              <span>Answered</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  border: '1px solid #94A3B8',
                  backgroundColor: '#FFFFFF',
                }}
              />
              <span>Not Answered</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', color: '#D97706' }}>🔖</span>
              <span>Marked for Later</span>
            </div>
          </div>
        </aside>

        {/* ─── COLUMN 2: CENTER WORKSPACE (ACTIVE QUESTION) ─────────────── */}
        <main
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            overflow: 'hidden',
          }}
        >
          {/* Question Card Box */}
          <div
            style={{
              flex: 1,
              minHeight: 0,
              backgroundColor: '#FFFFFF',
              borderRadius: '14px',
              border: '1px solid rgba(245, 184, 61, 0.28)',
              boxShadow: '0 4px 16px -2px rgba(11, 46, 111, 0.05)',
              display: 'flex',
              flexDirection: 'column',
              padding: '24px 28px',
              boxSizing: 'border-box',
              overflow: 'hidden',
            }}
          >
            {/* Header: Question Number & Pills */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '14px', fontWeight: 800, color: '#0B2E6F' }}>
                  Question {questionNumberInSection} of {sectionQuestions.length}
                </span>
                <span
                  style={{
                    backgroundColor: '#EBF3FC',
                    color: '#1455B8',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: '9999px',
                  }}
                >
                  {currentQ.section_type === 'APTITUDE' ? 'Aptitude' : 'Coding Fundamentals'}
                </span>

                {/* Save Status pill */}
                {saveStatus[currentQ.question_order] === 'saving' && (
                  <span style={{ fontSize: '11px', color: '#D97706', fontWeight: 600 }}>
                    ● Saving...
                  </span>
                )}
                {saveStatus[currentQ.question_order] === 'saved' && (
                  <span style={{ fontSize: '11px', color: '#16A34A', fontWeight: 600 }}>
                    ✓ Saved
                  </span>
                )}
                {saveStatus[currentQ.question_order] === 'failed' && (
                  <button
                    onClick={() => handleRetrySave(currentQ.question_order)}
                    style={{
                      fontSize: '11px',
                      color: '#DC2626',
                      fontWeight: 600,
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                    }}
                  >
                    ✕ Save failed (Retry)
                  </button>
                )}
              </div>

              {/* 1 Mark Badge */}
              <div
                style={{
                  backgroundColor: '#FEF3C7',
                  color: '#B45309',
                  fontSize: '11px',
                  fontWeight: 800,
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  border: '1px solid rgba(245, 184, 61, 0.3)',
                }}
              >
                1 Mark
              </div>
            </div>

            {/* Question Text / Problem Prompt */}
            <div
              style={{
                fontSize: '18px',
                fontWeight: 700,
                color: '#111111',
                lineHeight: 1.5,
                marginBottom: '24px',
                whiteSpace: 'pre-wrap',
                userSelect: 'none',
              }}
            >
              {currentQ.prompt}
            </div>

            {/* 4 Selectable Answer Options (Mockup Rounded Cards) */}
            <div
              style={{
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                paddingRight: '4px',
              }}
            >
              {currentQ.options.map((opt) => {
                const isSelected = answers[currentQ.question_order] === opt.key;
                return (
                  <div
                    key={opt.key}
                    onClick={() => handleSelectOption(currentQ.question_order, opt.key)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '14px',
                      padding: '13px 18px',
                      borderRadius: '12px',
                      border: isSelected
                        ? '2px solid #1455B8'
                        : '1.5px solid #E2E8F0',
                      backgroundColor: isSelected ? '#EFF6FF' : '#FFFFFF',
                      cursor: submitting ? 'not-allowed' : 'pointer',
                      transition: 'all 0.12s ease',
                      boxSizing: 'border-box',
                    }}
                  >
                    {/* Radio Circle */}
                    <div
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '50%',
                        border: isSelected ? '5px solid #1455B8' : '2px solid #94A3B8',
                        backgroundColor: '#FFFFFF',
                        boxSizing: 'border-box',
                        flexShrink: 0,
                      }}
                    />

                    {/* Letter Badge (A, B, C, D) */}
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        backgroundColor: isSelected ? '#1455B8' : '#F1F5F9',
                        color: isSelected ? '#FFFFFF' : '#475569',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: '13px',
                        flexShrink: 0,
                      }}
                    >
                      {opt.key}
                    </div>

                    {/* Option Text */}
                    <div
                      style={{
                        fontSize: '15px',
                        color: '#111111',
                        fontWeight: isSelected ? 600 : 500,
                        lineHeight: 1.4,
                      }}
                    >
                      {opt.text}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Actions Row Below Options (Mark for Later & Clear Answer) */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '20px',
                paddingTop: '14px',
                borderTop: '1px solid #FAF7F3',
              }}
            >
              {/* Mark for Later Button */}
              <button
                onClick={() => handleToggleMarkForLater(currentQ.question_order)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: markedForLater[currentQ.question_order]
                    ? '1.5px solid #F59E0B'
                    : '1.5px solid #CBD5E1',
                  backgroundColor: markedForLater[currentQ.question_order]
                    ? '#FFFBEB'
                    : '#FFFFFF',
                  color: markedForLater[currentQ.question_order] ? '#D97706' : '#374151',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>🔖</span>
                <span>
                  {markedForLater[currentQ.question_order]
                    ? 'Marked for Later'
                    : 'Mark for Later'}
                </span>
              </button>

              {/* Clear Answer Button */}
              {answers[currentQ.question_order] && (
                <button
                  onClick={() => handleClearAnswer(currentQ.question_order)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: 'transparent',
                    color: '#6B7280',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#DC2626')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                >
                  <span>🔄</span>
                  <span>Clear Answer</span>
                </button>
              )}
            </div>
          </div>

          {/* Navigation Controls Bar Below Question Card (Previous & Next) */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '12px',
              padding: '0 4px',
            }}
          >
            {/* Previous Button */}
            <button
              onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
              disabled={currentIndex === 0}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '11px 24px',
                borderRadius: '8px',
                border: '1.5px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: '#334155',
                fontSize: '14px',
                fontWeight: 700,
                cursor: currentIndex === 0 ? 'not-allowed' : 'pointer',
                opacity: currentIndex === 0 ? 0.45 : 1,
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
              }}
            >
              <span>←</span>
              <span>Previous</span>
            </button>

            {/* Next or Finish Button */}
            {currentIndex < attempt.questions.length - 1 ? (
              <button
                onClick={() => setCurrentIndex((prev) => prev + 1)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '11px 28px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
                  color: '#FFFFFF',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 4px 10px rgba(11, 46, 111, 0.2)',
                }}
              >
                <span>Next Question</span>
                <span>→</span>
              </button>
            ) : (
              <button
                onClick={() => setShowSubmitModal(true)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '11px 28px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: '#16A34A',
                  color: '#FFFFFF',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 4px 10px rgba(22, 163, 74, 0.25)',
                }}
              >
                <span>Review & Submit Test</span>
                <span>✓</span>
              </button>
            )}
          </div>
        </main>

        {/* ─── COLUMN 3: RIGHT PALETTE & OVERVIEW (w-[270px]) ──────────── */}
        <aside
          style={{
            width: '270px',
            minWidth: '270px',
            maxWidth: '270px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            overflow: 'hidden',
          }}
        >
          {/* Card 1: Question Palette */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '14px',
              border: '1px solid rgba(245, 184, 61, 0.28)',
              boxShadow: '0 4px 16px -2px rgba(11, 46, 111, 0.05)',
              padding: '14px 16px',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '380px',
            }}
          >
            {/* Header: Title and Grid Icon */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '10px',
              }}
            >
              <h2 style={{ fontSize: '14px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Question Palette
              </h2>
              <span style={{ fontSize: '14px', color: '#64748B' }}>▦</span>
            </div>

            {/* Palette Legend */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '10px',
                color: '#64748B',
                fontWeight: 600,
                marginBottom: '12px',
                paddingBottom: '8px',
                borderBottom: '1px solid #FAF7F3',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    backgroundColor: '#16A34A',
                  }}
                />
                <span>Answered</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    border: '1px solid #CBD5E1',
                    backgroundColor: '#FFFFFF',
                  }}
                />
                <span>Not Answered</span>
              </div>
            </div>

            {/* 5x5 Numbers Grid for active section */}
            <div
              style={{
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: '6px',
                alignContent: 'start',
              }}
            >
              {sectionQuestions.map((q, secIdx) => {
                const fullIndex = attempt.questions.findIndex(
                  (item) => item.question_order === q.question_order
                );
                const isCurrent = fullIndex === currentIndex;
                const isAnswered = !!answers[q.question_order];
                const isMarked = !!markedForLater[q.question_order];

                // Exact Mockup Styling:
                // - Answered: green background, green border, dark green text
                // - Marked: light blue background, blue border, bookmark badge
                // - Not answered: white background, gray border, gray text
                let bg = '#FFFFFF';
                let border = '1px solid #E2E8F0';
                let color = '#475569';

                if (isAnswered) {
                  bg = '#DCFCE7';
                  border = '1px solid #86EFAC';
                  color = '#166534';
                } else if (isMarked) {
                  bg = '#EFF6FF';
                  border = '1.5px solid #93C5FD';
                  color = '#1D4ED8';
                }

                if (isCurrent) {
                  border = '2px solid #0B2E6F';
                }

                return (
                  <button
                    key={q.question_order}
                    onClick={() => setCurrentIndex(fullIndex)}
                    style={{
                      height: '34px',
                      borderRadius: '8px',
                      fontSize: '12px',
                      fontWeight: isCurrent ? 800 : 700,
                      fontFamily: 'monospace',
                      border,
                      backgroundColor: bg,
                      color,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      position: 'relative',
                      padding: 0,
                      transition: 'all 0.1s ease',
                    }}
                  >
                    <span>{secIdx + 1}</span>
                    {isMarked && (
                      <span
                        style={{
                          position: 'absolute',
                          top: '2px',
                          right: '2px',
                          fontSize: '8px',
                          lineHeight: 1,
                        }}
                      >
                        🔖
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Card 2: Assessment Overview (Mockup Table) */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '14px',
              border: '1px solid rgba(245, 184, 61, 0.28)',
              boxShadow: '0 4px 16px -2px rgba(11, 46, 111, 0.05)',
              padding: '14px 16px',
            }}
          >
            {/* Header with Compass/Target icon */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '12px',
              }}
            >
              <span
                style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  backgroundColor: '#FEF3C7',
                  color: '#B45309',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                }}
              >
                🎯
              </span>
              <h3 style={{ fontSize: '13px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Assessment Overview
              </h3>
            </div>

            {/* 5 Metadata Rows */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B' }}>
                <span>Aptitude Questions</span>
                <strong style={{ color: '#0B2E6F' }}>25</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B' }}>
                <span>Coding Questions</span>
                <strong style={{ color: '#0B2E6F' }}>25</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B' }}>
                <span>Total Questions</span>
                <strong style={{ color: '#0B2E6F' }}>50</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B' }}>
                <span>Total Marks</span>
                <strong style={{ color: '#0B2E6F' }}>50</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B' }}>
                <span>Time Duration</span>
                <strong style={{ color: '#0B2E6F' }}>60 Minutes</strong>
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* ─── 3. SUBMISSION CONFIRMATION MODAL ─────────────────────────── */}
      {showSubmitModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.45)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              maxWidth: '460px',
              width: '100%',
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              padding: '28px',
              boxShadow: '0 20px 30px -10px rgba(11, 46, 111, 0.15)',
              border: '1px solid rgba(245, 184, 61, 0.3)',
            }}
          >
            <h3
              style={{
                fontSize: '18px',
                fontWeight: 800,
                margin: '0 0 10px 0',
                color: '#0B2E6F',
              }}
            >
              Confirm Final Submission
            </h3>
            <p
              style={{
                fontSize: '14px',
                color: '#4B5563',
                marginBottom: '16px',
                lineHeight: 1.5,
              }}
            >
              You have answered <strong>{answeredCount}</strong> of 50 questions (
              <strong>{50 - answeredCount}</strong> unattempted). Once submitted, answers cannot be
              modified. Are you sure you wish to finalize your assessment?
            </p>

            <div
              style={{
                backgroundColor: '#FAF7F3',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '20px',
                fontSize: '12px',
                color: '#374151',
                display: 'flex',
                justifyContent: 'space-around',
              }}
            >
              <div>
                Answered: <strong style={{ color: '#16A34A' }}>{answeredCount}</strong>
              </div>
              <div>
                Pending: <strong style={{ color: '#D97706' }}>{50 - answeredCount}</strong>
              </div>
              <div>
                Bookmarked:{' '}
                <strong style={{ color: '#1455B8' }}>
                  {Object.values(markedForLater).filter(Boolean).length}
                </strong>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setShowSubmitModal(false)}
                disabled={submitting}
                style={{
                  padding: '9px 18px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#FFFFFF',
                  color: '#374151',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Return to Test
              </button>
              <button
                onClick={handleConfirmSubmit}
                disabled={submitting}
                style={{
                  padding: '9px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #16A34A 0%, #15803D 100%)',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: submitting ? 'not-allowed' : 'pointer',
                }}
              >
                {submitting ? 'Submitting & Scoring...' : 'Yes, Submit Test'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── 4. TERMINAL NOTICE OVERLAY (TAB EXCEEDED OR TIMEOUT) ──────── */}
      {terminalNotice && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.75)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              maxWidth: '480px',
              width: '100%',
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              padding: '32px',
              textAlign: 'center',
              boxShadow: '0 25px 40px -10px rgba(0, 0, 0, 0.25)',
              border: '1px solid rgba(245, 184, 61, 0.4)',
            }}
          >
            <div style={{ fontSize: '38px', marginBottom: '12px' }}>⚠️</div>
            <h3
              style={{
                fontSize: '18px',
                fontWeight: 800,
                margin: '0 0 10px 0',
                color: '#991B1B',
              }}
            >
              Assessment Automatically Submitted
            </h3>
            <p
              style={{
                fontSize: '14px',
                color: '#374151',
                lineHeight: 1.6,
                marginBottom: '20px',
              }}
            >
              {terminalNotice}
            </p>
            <div style={{ fontSize: '13px', color: '#6B7280', fontWeight: 600 }}>
              Redirecting to assessment results scorecard...
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
