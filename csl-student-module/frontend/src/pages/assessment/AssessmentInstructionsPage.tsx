import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  startAssessment,
  getCandidateAssessments,
  type CandidateAssessmentItem,
} from '../../api/assessment';
import {
  checkDeviceEligibility,
  MIN_SUPPORTED_WIDTH,
  MIN_SUPPORTED_HEIGHT,
  type DeviceEligibilityResult,
} from '../../utils/deviceCheck';

export function AssessmentInstructionsPage() {
  const navigate = useNavigate();
  const [agreed, setAgreed] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  // Assessment metadata state
  const [eligibleAssessments, setEligibleAssessments] = useState<CandidateAssessmentItem[]>([]);
  const [selectedAssessment, setSelectedAssessment] = useState<CandidateAssessmentItem | null>(null);
  const [candidateCollege, setCandidateCollege] = useState<string>('');
  const [loadingMetadata, setLoadingMetadata] = useState<boolean>(true);

  // Device eligibility state
  const [eligibility, setEligibility] = useState<DeviceEligibilityResult>(() =>
    checkDeviceEligibility()
  );

  const handleResize = useCallback(() => {
    setEligibility(checkDeviceEligibility());
  }, []);

  useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);

  // Load candidate and assessment details
  useEffect(() => {
    let isMounted = true;
    const storedAssessmentId = sessionStorage.getItem('csl_assessment_id');

    setLoadingMetadata(true);
    getCandidateAssessments()
      .then((data) => {
        if (!isMounted) return;
        setCandidateCollege(data.candidate.college);
        setEligibleAssessments(data.assessments);

        if (data.assessments.length > 0) {
          let chosen = data.assessments.find((a) => a.id === storedAssessmentId);
          if (!chosen) {
            // Find first open assessment or fallback to first
            chosen = data.assessments.find((a) => a.user_can_attempt) || data.assessments[0];
          }
          setSelectedAssessment(chosen);
          if (chosen) {
            sessionStorage.setItem('csl_assessment_id', chosen.id);
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load candidate assessments:', err);
        if (isMounted) {
          // If unauthorized, redirect to registration
          if (err?.response?.status === 401) {
            navigate('/assessment/register', { replace: true });
          }
        }
      })
      .finally(() => {
        if (isMounted) setLoadingMetadata(false);
      });

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  const handleAssessmentChange = (assessmentId: string) => {
    const chosen = eligibleAssessments.find((a) => a.id === assessmentId);
    if (chosen) {
      setSelectedAssessment(chosen);
      sessionStorage.setItem('csl_assessment_id', chosen.id);
    }
  };

  const handleStart = async () => {
    if (!agreed || loading) return;
    setError('');

    // Re-verify device and viewport eligibility
    const currentCheck = checkDeviceEligibility();
    if (!currentCheck.eligible) {
      setEligibility(currentCheck);
      setError('Please maximize your browser window or switch to a supported laptop to begin.');
      return;
    }

    // Fullscreen validation
    if (!document.fullscreenEnabled) {
      setError(
        'Your browser does not support or permit the Fullscreen API. Please use a modern laptop browser such as Chrome, Edge, or Firefox.'
      );
      return;
    }

    setLoading(true);

    try {
      // 1. Request browser fullscreen FIRST
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      }

      // Verify fullscreen was actually granted
      if (!document.fullscreenElement) {
        throw new Error('Fullscreen request was not granted by the browser.');
      }

      // 2. Only start assessment after fullscreen is confirmed
      const targetAssessmentId = selectedAssessment?.id || sessionStorage.getItem('csl_assessment_id') || undefined;
      const attempt = await startAssessment(targetAssessmentId);
      navigate(`/assessment/exam/${attempt.id}`);
    } catch (err: unknown) {
      console.error('Failed to initialize fullscreen assessment:', err);

      // Exit fullscreen if partial entry happened
      if (document.fullscreenElement) {
        try {
          await document.exitFullscreen();
        } catch {
          // ignore
        }
      }

      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string; bank_error?: string } } };
        const msg =
          axErr.response?.data?.detail ||
          axErr.response?.data?.bank_error ||
          'Failed to initialize assessment session.';
        setError(msg);
      } else if (err instanceof Error) {
        setError(
          `Fullscreen is required to start this assessment. ${err.message || 'Please permit fullscreen access in your browser and try again.'}`
        );
      } else {
        setError(
          'Fullscreen access was declined or blocked by your browser. Please allow fullscreen to start the assessment.'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  // Screen 1: Mobile device detected
  if (!eligibility.eligible && eligibility.reason === 'mobile') {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          padding: '24px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '520px',
            width: '100%',
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            border: '1px solid rgba(245, 184, 61, 0.3)',
            boxShadow: '0 10px 25px -5px rgba(11, 46, 111, 0.08)',
            padding: '36px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: '#FAF7F3',
              border: '2px solid rgba(245, 184, 61, 0.4)',
              color: '#0B2E6F',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '30px',
              margin: '0 auto 20px',
            }}
          >
            💻
          </div>
          <span
            style={{
              display: 'inline-block',
              backgroundColor: 'rgba(20, 85, 184, 0.08)',
              color: '#1455B8',
              fontSize: '12px',
              fontWeight: 700,
              padding: '4px 12px',
              borderRadius: '9999px',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '12px',
            }}
          >
            CSL Skill Matrix — Laptop Required
          </span>
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              color: '#0B2E6F',
              margin: '0 0 12px 0',
              lineHeight: 1.3,
            }}
          >
            Please use a laptop to attend this assessment
          </h1>
          <p
            style={{
              fontSize: '14px',
              color: '#6B7280',
              lineHeight: 1.6,
              marginBottom: '28px',
            }}
          >
            This diagnostic assessment is strictly designed for and restricted to laptop or desktop
            environments with a full keyboard, pointer device, and fullscreen proctoring interface.
            Mobile devices and tablets are not eligible.
          </p>
          <button
            onClick={() => navigate('/assessment/register')}
            style={{
              width: '100%',
              padding: '12px 20px',
              background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '14px',
              cursor: 'pointer',
            }}
          >
            Return to Registration
          </button>
        </div>
      </div>
    );
  }

  // Screen 2: Viewport too small (window not maximized on laptop)
  if (!eligibility.eligible && eligibility.reason === 'viewport_small') {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          padding: '24px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '560px',
            width: '100%',
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            border: '1px solid rgba(245, 184, 61, 0.3)',
            boxShadow: '0 10px 25px -5px rgba(11, 46, 111, 0.08)',
            padding: '36px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: '#FAF7F3',
              border: '2px solid rgba(245, 184, 61, 0.4)',
              color: '#0B2E6F',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '30px',
              margin: '0 auto 20px',
            }}
          >
            🖥️
          </div>
          <span
            style={{
              display: 'inline-block',
              backgroundColor: 'rgba(245, 184, 61, 0.15)',
              color: '#B45309',
              fontSize: '12px',
              fontWeight: 700,
              padding: '4px 12px',
              borderRadius: '9999px',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '12px',
            }}
          >
            Viewport Adjustment Needed
          </span>
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              color: '#0B2E6F',
              margin: '0 0 12px 0',
              lineHeight: 1.3,
            }}
          >
            Please maximize your browser window
          </h1>
          <p
            style={{
              fontSize: '14px',
              color: '#6B7280',
              lineHeight: 1.6,
              marginBottom: '20px',
            }}
          >
            The single-viewport assessment layout requires an active window of at least{' '}
            <strong>
              {MIN_SUPPORTED_WIDTH} × {MIN_SUPPORTED_HEIGHT} pixels
            </strong>{' '}
            to display all question controls, timer, and palette without page scrolling.
          </p>

          <div
            style={{
              backgroundColor: '#FAF7F3',
              border: '1px solid #E5E7EB',
              borderRadius: '8px',
              padding: '14px',
              fontSize: '13px',
              color: '#374151',
              marginBottom: '24px',
            }}
          >
            <div>
              Current Window Resolution:{' '}
              <strong style={{ color: '#DC2626', fontFamily: 'monospace' }}>
                {eligibility.currentWidth}px × {eligibility.currentHeight}px
              </strong>
            </div>
            <div style={{ marginTop: '4px', fontSize: '12px', color: '#6B7280' }}>
              Minimum Required: {MIN_SUPPORTED_WIDTH}px × {MIN_SUPPORTED_HEIGHT}px
            </div>
          </div>

          <p style={{ fontSize: '13px', color: '#6B7280', margin: 0 }}>
            Maximize your browser window or adjust your OS display scaling. This screen will
            automatically unlock once suitable dimensions are detected.
          </p>
        </div>
      </div>
    );
  }

  // Display metrics defaults
  const durationMinutes = selectedAssessment?.duration_minutes ?? 60;
  const aptitudeCount = selectedAssessment?.aptitude_count ?? 25;
  const codingCount = selectedAssessment?.coding_count ?? 25;
  const totalQuestions = aptitudeCount + codingCount;
  const totalMarks = selectedAssessment?.total_marks ?? 50;
  const maxAttempts = selectedAssessment?.max_attempts ?? 1;
  const assessmentTitle = selectedAssessment?.title ?? 'Initial Diagnostic Assessment';
  const assessmentCode = selectedAssessment?.code ?? 'CSL-INITIAL-01';

  // Screen 3: Standard Instructions Screen (CSL Brand Aligned)
  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#FCFAF5',
        padding: '36px 16px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: '720px',
          width: '100%',
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          border: '1px solid rgba(245, 184, 61, 0.28)',
          boxShadow: '0 10px 30px -5px rgba(11, 46, 111, 0.07)',
          padding: '36px',
          boxSizing: 'border-box',
        }}
      >
        {/* Brand Header */}
        <div
          style={{
            borderBottom: '1px solid #FAF7F3',
            paddingBottom: '20px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span
                style={{
                  backgroundColor: '#0B2E6F',
                  color: '#FFD45C',
                  fontSize: '11px',
                  fontWeight: 800,
                  padding: '3px 8px',
                  borderRadius: '4px',
                  letterSpacing: '0.05em',
                }}
              >
                CSL
              </span>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#1455B8',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {assessmentCode}
              </span>
              {candidateCollege && (
                <span style={{ fontSize: '12px', color: '#6B7280' }}>
                  · {candidateCollege}
                </span>
              )}
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
              {assessmentTitle}
            </h1>
          </div>

          <div
            style={{
              padding: '6px 12px',
              backgroundColor: '#FAF7F3',
              borderRadius: '8px',
              border: '1px solid rgba(245, 184, 61, 0.25)',
              fontSize: '12px',
              fontWeight: 600,
              color: '#0B2E6F',
              textAlign: 'right',
            }}
          >
            <span>Laptop Verified ✓</span>
          </div>
        </div>

        {/* Assessment Switcher (if college has multiple assessments) */}
        {eligibleAssessments.length > 1 && (
          <div
            style={{
              backgroundColor: '#FAF7F3',
              padding: '12px 16px',
              borderRadius: '8px',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              border: '1px solid #E5E7EB',
            }}
          >
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>
              Selected Assessment:
            </span>
            <select
              value={selectedAssessment?.id || ''}
              onChange={(e) => handleAssessmentChange(e.target.value)}
              style={{
                fontSize: '13px',
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: '#0B2E6F',
                fontWeight: 600,
              }}
            >
              {eligibleAssessments.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title} ({a.code})
                </option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div
            style={{
              backgroundColor: '#FEE2E2',
              border: '1px solid #FECACA',
              color: '#991B1B',
              padding: '14px 18px',
              borderRadius: '8px',
              fontSize: '13px',
              lineHeight: 1.5,
              marginBottom: '24px',
            }}
          >
            <strong>⚠️ Notice:</strong> {error}
          </div>
        )}

        {/* 4 Diagnostic Metrics Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '12px',
            marginBottom: '28px',
          }}
        >
          <div
            style={{
              backgroundColor: '#FAF7F3',
              padding: '14px',
              borderRadius: '10px',
              textAlign: 'center',
              border: '1px solid rgba(245, 184, 61, 0.2)',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                color: '#6B7280',
                textTransform: 'uppercase',
                fontWeight: 700,
                display: 'block',
              }}
            >
              Duration
            </span>
            <strong style={{ fontSize: '20px', color: '#0B2E6F', fontWeight: 800 }}>
              {durationMinutes} Mins
            </strong>
          </div>
          <div
            style={{
              backgroundColor: '#FAF7F3',
              padding: '14px',
              borderRadius: '10px',
              textAlign: 'center',
              border: '1px solid rgba(245, 184, 61, 0.2)',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                color: '#6B7280',
                textTransform: 'uppercase',
                fontWeight: 700,
                display: 'block',
              }}
            >
              Questions
            </span>
            <strong style={{ fontSize: '20px', color: '#0B2E6F', fontWeight: 800 }}>
              {totalQuestions} MCQs
            </strong>
          </div>
          <div
            style={{
              backgroundColor: '#FAF7F3',
              padding: '14px',
              borderRadius: '10px',
              textAlign: 'center',
              border: '1px solid rgba(245, 184, 61, 0.2)',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                color: '#6B7280',
                textTransform: 'uppercase',
                fontWeight: 700,
                display: 'block',
              }}
            >
              Total Marks
            </span>
            <strong style={{ fontSize: '20px', color: '#0B2E6F', fontWeight: 800 }}>
              {totalMarks} Marks
            </strong>
          </div>
          <div
            style={{
              backgroundColor: '#FAF7F3',
              padding: '14px',
              borderRadius: '10px',
              textAlign: 'center',
              border: '1px solid rgba(245, 184, 61, 0.2)',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                color: '#6B7280',
                textTransform: 'uppercase',
                fontWeight: 700,
                display: 'block',
              }}
            >
              Max Attempts
            </span>
            <strong style={{ fontSize: '20px', color: '#0B2E6F', fontWeight: 800 }}>
              {maxAttempts} {maxAttempts === 1 ? 'Attempt' : 'Attempts'}
            </strong>
          </div>
        </div>

        {/* Assessment Structure */}
        <div style={{ marginBottom: '24px' }}>
          <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#0B2E6F', marginBottom: '10px' }}>
            Assessment Structure & Rules
          </h2>
          <ul
            style={{
              margin: 0,
              paddingLeft: '18px',
              fontSize: '13px',
              color: '#374151',
              lineHeight: 1.7,
            }}
          >
            <li>
              <strong>Section 1: General Aptitude ({aptitudeCount} Questions)</strong> — Quantitative Problem
              Solving, Logical Reasoning, and Verbal Comprehension.
            </li>
            <li>
              <strong>Section 2: Coding Fundamentals ({codingCount} Questions)</strong> — Core Programming
              Principles, Control Flow, Functions, OOP Concepts, and Data Structures. (Conceptual
              MCQs; code execution is not required).
            </li>
            <li>
              Each correct question is awarded <strong>1 mark</strong>. There is no negative marking
              for incorrect answers.
            </li>
            <li>
              You may freely navigate between questions and update your selections before
              finalizing.
            </li>
            <li>
              All answers are automatically saved to the secure server as you select them.
            </li>
          </ul>
        </div>

        {/* Integrity and Fullscreen Notice */}
        <div
          style={{
            backgroundColor: '#FAF7F3',
            border: '1px solid rgba(245, 184, 61, 0.35)',
            padding: '16px 20px',
            borderRadius: '10px',
            marginBottom: '24px',
          }}
        >
          <h3
            style={{
              fontSize: '13px',
              fontWeight: 800,
              color: '#0B2E6F',
              margin: '0 0 6px 0',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>🛡️</span> Fullscreen Mode & Proctoring Deterrents
          </h3>
          <p style={{ fontSize: '12px', color: '#4B5563', margin: 0, lineHeight: 1.6 }}>
            The assessment runs in mandatory browser fullscreen. Please note that fullscreen and tab
            monitoring are browser-level deterrents, not foolproof anti-cheating controls. Do not
            switch browser tabs or minimize the assessment window. Two switches are permitted with
            warnings; a third switch will automatically finalize and submit your assessment.
          </p>
        </div>

        {/* Checkbox */}
        <div style={{ marginBottom: '24px' }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              style={{
                marginTop: '3px',
                width: '16px',
                height: '16px',
                accentColor: '#1455B8',
                cursor: 'pointer',
              }}
            />
            <span style={{ fontSize: '13px', color: '#1F2937', fontWeight: 500, lineHeight: 1.5 }}>
              I confirm I am attending on a laptop, agree to enter fullscreen mode, and understand
              that navigating away from the assessment tab will trigger automatic submission.
            </span>
          </label>
        </div>

        {/* Start Button */}
        <button
          onClick={handleStart}
          disabled={!agreed || loading || loadingMetadata}
          style={{
            width: '100%',
            padding: '14px',
            background:
              !agreed || loading || loadingMetadata
                ? '#9CA3AF'
                : 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '10px',
            fontSize: '15px',
            fontWeight: 700,
            cursor: !agreed || loading || loadingMetadata ? 'not-allowed' : 'pointer',
            boxShadow:
              !agreed || loading || loadingMetadata ? 'none' : '0 4px 14px 0 rgba(11, 46, 111, 0.25)',
            transition: 'all 0.15s ease',
          }}
        >
          {loading ? 'Entering Fullscreen & Initializing Exam...' : 'Start Assessment'}
        </button>
      </div>
    </div>
  );
}
