import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  registerCandidate,
  getStudentColleges,
  getCandidateAssessments,
  type RegistrationPayload,
  type CollegeOption,
  type CandidateAssessmentItem,
  type RegisterResponse,
} from '../../api/assessment';
import cslTypographyLogo from '../../assets/CSL-TYPOGRAPHY.png';
import backgroundImage from '../../assets/background.png';

export function AssessmentRegisterPage() {
  const navigate = useNavigate();

  // Registration form state
  const [formData, setFormData] = useState<RegistrationPayload>({
    full_name: '',
    register_number: '',
    college: '',
    college_id: undefined,
    email: '',
    department: '',
    year_of_study: '3rd Year',
    phone_number: '',
  });

  const [colleges, setColleges] = useState<CollegeOption[]>([]);
  const [collegesLoading, setCollegesLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(false);

  // Flow steps: 'register' | 'select_assessment' | 'resume_attempt' | 'already_completed'
  const [step, setStep] = useState<'register' | 'select_assessment' | 'resume_attempt' | 'already_completed'>('register');
  const [resumableAttempt, setResumableAttempt] = useState<RegisterResponse | null>(null);
  const [candidateInfo, setCandidateInfo] = useState<{
    id: string;
    full_name: string;
    register_number: string;
    college: string;
    department: string;
    year_of_study: string;
  } | null>(null);
  const [candidateAssessments, setCandidateAssessments] = useState<CandidateAssessmentItem[]>([]);
  const [loadingAssessments, setLoadingAssessments] = useState<boolean>(false);

  // Fetch active colleges on mount
  useEffect(() => {
    let isMounted = true;
    setCollegesLoading(true);
    getStudentColleges()
      .then((data) => {
        if (isMounted) {
          setColleges(data);
          if (data.length > 0 && !formData.college_id) {
            // Pre-select first college if available
            setFormData((prev) => ({
              ...prev,
              college_id: data[0].id,
              college: data[0].name,
            }));
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load active colleges:', err);
      })
      .finally(() => {
        if (isMounted) setCollegesLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    if (name === 'college_id') {
      const colId = Number(value);
      const selected = colleges.find((c) => c.id === colId);
      setFormData((prev) => ({
        ...prev,
        college_id: colId,
        college: selected ? selected.name : '',
      }));
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }

    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleFetchAssessments = async () => {
    setLoadingAssessments(true);
    try {
      const resp = await getCandidateAssessments();
      setCandidateInfo(resp.candidate);
      setCandidateAssessments(resp.assessments);

      // If exactly 1 assessment is open and ready for attempt, proceed directly
      const openAssessments = resp.assessments.filter((a) => a.user_can_attempt);
      if (resp.assessments.length === 1 && openAssessments.length === 1) {
        const single = openAssessments[0];
        sessionStorage.setItem('csl_assessment_id', single.id);
        navigate('/assessment/instructions');
        return;
      }

      setStep('select_assessment');
    } catch (err: unknown) {
      console.error('Failed to load candidate assessments:', err);
      // Fallback to instructions
      navigate('/assessment/instructions');
    } finally {
      setLoadingAssessments(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    // Client-side phone validation
    const trimmedPhone = formData.phone_number.trim();
    const phoneDigits = trimmedPhone.replace(/\D/g, '');
    if (!trimmedPhone) {
      setFieldErrors((prev) => ({ ...prev, phone_number: 'Mobile phone number is mandatory.' }));
      return;
    }
    if (phoneDigits.length !== 10) {
      setFieldErrors((prev) => ({
        ...prev,
        phone_number: 'Please enter a valid 10-digit mobile phone number.',
      }));
      return;
    }

    if (!formData.college_id && !formData.college) {
      setFieldErrors((prev) => ({ ...prev, college_id: 'Please select an institution.' }));
      return;
    }

    setLoading(true);

    try {
      const res = await registerCandidate(formData);
      if (res.is_active_attempt && res.attempt_id) {
        setResumableAttempt(res);
        setStep('resume_attempt');
        return;
      }
      if (res.already_completed && res.attempt_id) {
        setResumableAttempt(res);
        setStep('already_completed');
        return;
      }

      // Fetch candidate's assigned assessments
      await handleFetchAssessments();
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response) {
        const data = err.response.data;
        if (typeof data === 'object') {
          const newFieldErrors: Record<string, string> = {};
          let generalMsg = '';
          for (const key of Object.keys(data)) {
            const val = data[key];
            const msg = Array.isArray(val) ? val[0] : String(val);
            if (key in formData || key === 'college_id') {
              newFieldErrors[key] = msg;
            } else {
              generalMsg = msg;
            }
          }
          setFieldErrors(newFieldErrors);
          if (generalMsg) setError(generalMsg);
        } else {
          setError('Registration failed. Please check your information.');
        }
      } else {
        setError('Network error. Unable to connect to server. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAssessment = (assessment: CandidateAssessmentItem) => {
    sessionStorage.setItem('csl_assessment_id', assessment.id);
    navigate('/assessment/instructions');
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // RESUME ASSESSMENT CONFIRMATION VIEW
  // ─────────────────────────────────────────────────────────────────────────────
  if (step === 'resume_attempt' && resumableAttempt) {
    return (
      <div
        style={{
          width: '100%',
          minHeight: '100vh',
          backgroundImage: `url(${backgroundImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          boxSizing: 'border-box',
          padding: '24px 16px',
          fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '520px',
            width: '100%',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            borderRadius: '20px',
            boxShadow: '0 25px 60px -15px rgba(11, 46, 111, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.85)',
            padding: '36px 36px 32px',
            margin: '16px 48px',
            boxSizing: 'border-box',
          }}
        >
          {/* CSL Typography Logo */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              padding: '6px 14px',
              borderRadius: '8px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)',
              border: '1px solid #E2E8F0',
              marginBottom: '20px',
            }}
          >
            <img
              src={cslTypographyLogo}
              alt="CSL Creator Space Lab"
              style={{ height: '28px', width: 'auto', objectFit: 'contain' }}
            />
          </div>

          <div style={{ marginBottom: '14px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                backgroundColor: '#ECFDF5',
                border: '1px solid #A7F3D0',
                color: '#065F46',
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '11.5px',
                fontWeight: 800,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#10B981', display: 'inline-block' }} />
              Active Session Verified
            </span>
          </div>

          <h2
            style={{
              fontSize: '24px',
              fontWeight: 800,
              color: '#0B2E6F',
              margin: '0 0 8px 0',
              letterSpacing: '-0.02em',
            }}
          >
            Resume Assessment
          </h2>

          <p style={{ fontSize: '13.5px', color: '#475569', lineHeight: 1.5, margin: '0 0 20px 0' }}>
            Identity verified successfully. You have an active examination session in progress. You can now resume your assessment.
          </p>

          {/* Candidate & Attempt Details Card */}
          <div
            style={{
              backgroundColor: '#F8FAFC',
              borderRadius: '12px',
              border: '1px solid #E2E8F0',
              padding: '16px 18px',
              marginBottom: '18px',
              fontSize: '13px',
              lineHeight: 1.6,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
              <span style={{ color: '#64748B', fontWeight: 600 }}>Candidate Name:</span>
              <span style={{ color: '#0F172A', fontWeight: 700 }}>{resumableAttempt.full_name || formData.full_name}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
              <span style={{ color: '#64748B', fontWeight: 600 }}>Register Number:</span>
              <span style={{ color: '#0F172A', fontWeight: 700 }}>{formData.register_number}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
              <span style={{ color: '#64748B', fontWeight: 600 }}>Institution:</span>
              <span style={{ color: '#0F172A', fontWeight: 700 }}>{resumableAttempt.college || formData.college}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
              <span style={{ color: '#64748B', fontWeight: 600 }}>Assessment Track:</span>
              <span style={{ color: '#1455B8', fontWeight: 700 }}>{resumableAttempt.assessment_title || 'CSL Assessment Track'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B', fontWeight: 600 }}>Attempt Status:</span>
              <span style={{ color: '#16A34A', fontWeight: 700 }}>In Progress (Eligible to Resume)</span>
            </div>
          </div>

          {/* Preserved Session Highlights */}
          <div
            style={{
              backgroundColor: '#EFF6FF',
              borderRadius: '10px',
              border: '1px solid #BFDBFE',
              padding: '12px 16px',
              marginBottom: '22px',
              fontSize: '12px',
              color: '#1E40AF',
              lineHeight: 1.5,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '4px' }}>Session Guarantees:</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              <div>✓ All saved answers and question states are restored.</div>
              <div>✓ Official server countdown timer will resume seamlessly.</div>
              <div>✓ Security monitoring and integrity counters are maintained.</div>
            </div>
          </div>

          <button
            onClick={() => {
              if (resumableAttempt.attempt_id) {
                navigate(`/assessment/exam/${resumableAttempt.attempt_id}`);
              }
            }}
            style={{
              width: '100%',
              padding: '13px 20px',
              background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '10px',
              fontSize: '15px',
              fontWeight: 800,
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(20, 85, 184, 0.3)',
              marginBottom: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'all 0.15s ease',
            }}
          >
            <span>Resume Assessment</span>
            <span>→</span>
          </button>

          <button
            onClick={() => setStep('register')}
            style={{
              width: '100%',
              padding: '9px 16px',
              backgroundColor: 'transparent',
              border: '1px solid #CBD5E1',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              color: '#64748B',
              cursor: 'pointer',
            }}
          >
            Back to Registration Form
          </button>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // ALREADY COMPLETED CONFIRMATION VIEW
  // ─────────────────────────────────────────────────────────────────────────────
  if (step === 'already_completed' && resumableAttempt) {
    return (
      <div
        style={{
          width: '100%',
          minHeight: '100vh',
          backgroundImage: `url(${backgroundImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          boxSizing: 'border-box',
          padding: '24px 16px',
          fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '520px',
            width: '100%',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            borderRadius: '20px',
            boxShadow: '0 25px 60px -15px rgba(11, 46, 111, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.85)',
            padding: '36px 36px 32px',
            margin: '16px 48px',
            boxSizing: 'border-box',
            textAlign: 'center',
          }}
        >
          {/* CSL Typography Logo */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              padding: '6px 14px',
              borderRadius: '8px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)',
              border: '1px solid #E2E8F0',
              marginBottom: '20px',
            }}
          >
            <img
              src={cslTypographyLogo}
              alt="CSL Creator Space Lab"
              style={{ height: '28px', width: 'auto', objectFit: 'contain' }}
            />
          </div>

          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              backgroundColor: '#ECFDF5',
              border: '2px solid #A7F3D0',
              color: '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
              fontSize: '26px',
              fontWeight: 800,
            }}
          >
            ✓
          </div>

          <h2
            style={{
              fontSize: '22px',
              fontWeight: 800,
              color: '#0B2E6F',
              margin: '0 0 8px 0',
              letterSpacing: '-0.02em',
            }}
          >
            Assessment Already Completed
          </h2>

          <p style={{ fontSize: '13.5px', color: '#475569', lineHeight: 1.5, margin: '0 0 24px 0' }}>
            Our records indicate that you have already submitted your assessment attempt for this account.
          </p>

          <button
            onClick={() => {
              if (resumableAttempt.attempt_id) {
                navigate(`/assessment/results/${resumableAttempt.attempt_id}`);
              }
            }}
            style={{
              width: '100%',
              padding: '12px 20px',
              background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '10px',
              fontSize: '14px',
              fontWeight: 800,
              cursor: 'pointer',
              marginBottom: '10px',
            }}
          >
            View Submission Confirmation →
          </button>

          <button
            onClick={() => setStep('register')}
            style={{
              width: '100%',
              padding: '9px 16px',
              backgroundColor: 'transparent',
              border: '1px solid #CBD5E1',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              color: '#64748B',
              cursor: 'pointer',
            }}
          >
            Back to Registration Form
          </button>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // STEP 2: ASSESSMENT SELECTION VIEW
  // ─────────────────────────────────────────────────────────────────────────────
  if (step === 'select_assessment') {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          padding: '40px 20px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '840px',
            width: '100%',
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            boxShadow: '0 10px 30px -5px rgba(11, 46, 111, 0.07)',
            padding: '36px',
            border: '1px solid rgba(245, 184, 61, 0.28)',
            boxSizing: 'border-box',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid #FAF7F3',
              paddingBottom: '20px',
              marginBottom: '24px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <img
                src={cslTypographyLogo}
                alt="CSL Logo"
                style={{ height: '32px', width: 'auto', objectFit: 'contain' }}
              />
              <div>
                <h1 style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                  Assigned Assessments
                </h1>
                <p style={{ fontSize: '13px', color: '#6B7280', margin: '2px 0 0 0' }}>
                  Select an assessment for your institution to proceed.
                </p>
              </div>
            </div>

            <button
              onClick={() => setStep('register')}
              style={{
                fontSize: '12px',
                color: '#6B7280',
                background: 'none',
                border: '1px solid #E5E7EB',
                borderRadius: '6px',
                padding: '6px 12px',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              ← Back to Details
            </button>
          </div>

          {/* Candidate Profile Badge */}
          {candidateInfo && (
            <div
              style={{
                backgroundColor: '#FAF7F3',
                borderRadius: '10px',
                padding: '14px 18px',
                marginBottom: '24px',
                border: '1px solid rgba(245, 184, 61, 0.25)',
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              <div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: '#0B2E6F' }}>
                  {candidateInfo.full_name}
                  <span
                    style={{
                      marginLeft: '8px',
                      fontSize: '12px',
                      color: '#6B7280',
                      fontWeight: 500,
                    }}
                  >
                    ({candidateInfo.register_number})
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#4B5563', marginTop: '2px' }}>
                  {candidateInfo.college} · {candidateInfo.department} · {candidateInfo.year_of_study}
                </div>
              </div>

              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  backgroundColor: 'rgba(16, 185, 129, 0.1)',
                  color: '#059669',
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  fontSize: '11px',
                  fontWeight: 700,
                }}
              >
                ● Active Profile
              </div>
            </div>
          )}

          {/* Assessments List */}
          {loadingAssessments ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6B7280' }}>
              Loading assigned assessments...
            </div>
          ) : candidateAssessments.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '48px 20px',
                backgroundColor: '#FAF7F3',
                borderRadius: '12px',
                border: '1px dashed #CBD5E1',
              }}
            >
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>📋</div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0B2E6F', margin: '0 0 6px 0' }}>
                No Assessments Assigned
              </h3>
              <p style={{ fontSize: '13px', color: '#6B7280', maxWidth: '420px', margin: '0 auto 16px' }}>
                There are currently no active or open assessments enrolled for{' '}
                <strong>{candidateInfo?.college || formData.college}</strong>. Please check back later or
                contact your college placement coordinator.
              </p>
              <button
                onClick={() => setStep('register')}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#0B2E6F',
                  color: '#FFFFFF',
                  borderRadius: '6px',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                Return to Registration
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
              {candidateAssessments.map((assessment) => {
                const canTake = assessment.user_can_attempt;
                const hasCompleted =
                  assessment.latest_attempt_id &&
                  ['SUBMITTED', 'TIMED_OUT', 'FLAGGED_FOR_REVIEW'].includes(
                    assessment.latest_attempt_state || ''
                  );

                return (
                  <div
                    key={assessment.id}
                    style={{
                      border: canTake ? '1px solid #1455B8' : '1px solid #E2E8F0',
                      borderRadius: '12px',
                      padding: '20px',
                      backgroundColor: canTake ? '#FFFFFF' : '#FAFAFA',
                      boxShadow: canTake ? '0 4px 14px rgba(20, 85, 184, 0.08)' : 'none',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            fontFamily: 'monospace',
                            fontSize: '12px',
                            fontWeight: 700,
                            color: '#0B2E6F',
                            backgroundColor: 'rgba(20, 85, 184, 0.08)',
                            padding: '3px 8px',
                            borderRadius: '4px',
                          }}
                        >
                          {assessment.code}
                        </span>
                        <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                          {assessment.title}
                        </h3>
                      </div>

                      {/* Status Badges */}
                      <div>
                        {assessment.status === 'OPEN' && canTake && (
                          <span
                            style={{
                              backgroundColor: '#DCFCE7',
                              color: '#15803D',
                              fontSize: '12px',
                              fontWeight: 700,
                              padding: '4px 10px',
                              borderRadius: '9999px',
                            }}
                          >
                            ● Open for Attempts ({assessment.attempts_count}/{assessment.max_attempts})
                          </span>
                        )}
                        {assessment.status === 'OPEN' && !canTake && hasCompleted && (
                          <span
                            style={{
                              backgroundColor: '#E0E7FF',
                              color: '#3730A3',
                              fontSize: '12px',
                              fontWeight: 700,
                              padding: '4px 10px',
                              borderRadius: '9999px',
                            }}
                          >
                            ✓ Attempt Completed
                          </span>
                        )}
                        {assessment.status === 'CLOSED' && (
                          <span
                            style={{
                              backgroundColor: '#F3F4F6',
                              color: '#4B5563',
                              fontSize: '12px',
                              fontWeight: 700,
                              padding: '4px 10px',
                              borderRadius: '9999px',
                            }}
                          >
                            🔒 Closed
                          </span>
                        )}
                        {assessment.status === 'SCHEDULED' && (
                          <span
                            style={{
                              backgroundColor: '#FEF3C7',
                              color: '#92400E',
                              fontSize: '12px',
                              fontWeight: 700,
                              padding: '4px 10px',
                              borderRadius: '9999px',
                            }}
                          >
                            🕒 Scheduled
                          </span>
                        )}
                      </div>
                    </div>

                    {assessment.description && (
                      <p style={{ fontSize: '13px', color: '#4B5563', margin: 0, lineHeight: 1.5 }}>
                        {assessment.description}
                      </p>
                    )}

                    {/* Metadata Badges */}
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '12px',
                        fontSize: '12px',
                        color: '#6B7280',
                      }}
                    >
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        ⏱️ <strong>{assessment.duration_minutes} Mins</strong>
                      </span>
                      <span>·</span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        📝{' '}
                        <strong>
                          {assessment.aptitude_count + assessment.coding_count} MCQs
                        </strong>{' '}
                        ({assessment.aptitude_count} Apt / {assessment.coding_count} Code)
                      </span>
                      <span>·</span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        🎯 <strong>{assessment.total_marks} Marks</strong>
                      </span>
                      <span>·</span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        🔁 Allowed Attempts: <strong>{assessment.max_attempts}</strong>
                      </span>
                    </div>

                    {/* Action Button */}
                    <div style={{ marginTop: '8px', display: 'flex', gap: '10px' }}>
                      {canTake ? (
                        <button
                          onClick={() => handleSelectAssessment(assessment)}
                          style={{
                            padding: '10px 18px',
                            background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
                            color: '#FFFFFF',
                            border: 'none',
                            borderRadius: '8px',
                            fontSize: '13px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            boxShadow: '0 3px 8px rgba(11, 46, 111, 0.2)',
                          }}
                        >
                          Select & Proceed to Instructions →
                        </button>
                      ) : hasCompleted && assessment.latest_attempt_id ? (
                        <button
                          onClick={() => navigate(`/assessment/results/${assessment.latest_attempt_id}`)}
                          style={{
                            padding: '10px 18px',
                            backgroundColor: '#FFFFFF',
                            color: '#0B2E6F',
                            border: '1px solid #0B2E6F',
                            borderRadius: '8px',
                            fontSize: '13px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          View Verified Scorecard →
                        </button>
                      ) : (
                        <button
                          disabled
                          style={{
                            padding: '10px 18px',
                            backgroundColor: '#E5E7EB',
                            color: '#9CA3AF',
                            border: 'none',
                            borderRadius: '8px',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: 'not-allowed',
                          }}
                        >
                          Assessment Not Accessible
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // STEP 1: CANDIDATE REGISTRATION VIEW
  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        padding: '24px 16px',
        boxSizing: 'border-box',
        fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '520px',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderRadius: '20px',
          boxShadow: '0 25px 60px -15px rgba(11, 46, 111, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.85)',
          padding: '36px 36px 32px',
          margin: '16px 48px',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ marginBottom: '22px' }}>
          {/* CSL Typography Logo at top */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              padding: '6px 14px',
              borderRadius: '8px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.06)',
              border: '1px solid #E2E8F0',
              marginBottom: '14px',
            }}
          >
            <img
              src={cslTypographyLogo}
              alt="CSL Creator Space Lab"
              style={{ height: '26px', width: 'auto', objectFit: 'contain' }}
            />
          </div>

          {/* Exact Title: CSL Assessment Portal */}
          <h1
            style={{
              fontSize: '24px',
              fontWeight: 800,
              color: '#0B2E6F',
              margin: '0 0 6px 0',
              letterSpacing: '-0.02em',
            }}
          >
            CSL Assessment Portal
          </h1>
          <p style={{ fontSize: '13px', color: '#64748B', margin: 0, lineHeight: 1.5 }}>
            Enter your student details to register or continue your assigned assessment round.
          </p>
        </div>

        {error && (
            <div
              style={{
                backgroundColor: '#FEE2E2',
                border: '1px solid #FECACA',
                color: '#991B1B',
                padding: '12px 16px',
                borderRadius: '8px',
                fontSize: '13px',
                lineHeight: 1.5,
                marginBottom: '20px',
              }}
            >
              <strong>⚠️ Registration Notice:</strong> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '14px' }}>
            <div>
              <label
                htmlFor="full_name"
                style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
              >
                Full Name *
              </label>
              <input
                id="full_name"
                name="full_name"
                type="text"
                required
                value={formData.full_name}
                onChange={handleChange}
                placeholder="e.g. Aditi Sharma"
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  border: fieldErrors.full_name ? '1px solid #DC2626' : '1px solid #CBD5E1',
                  fontSize: '13px',
                  color: '#111111',
                  boxSizing: 'border-box',
                  outlineColor: '#1455B8',
                }}
              />
              {fieldErrors.full_name && (
                <span style={{ color: '#DC2626', fontSize: '12px', marginTop: '2px', display: 'block' }}>
                  {fieldErrors.full_name}
                </span>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label
                  htmlFor="register_number"
                  style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
                >
                  Register / Roll Number *
                </label>
                <input
                  id="register_number"
                  name="register_number"
                  type="text"
                  required
                  value={formData.register_number}
                  onChange={handleChange}
                  placeholder="e.g. 721721U101"
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: fieldErrors.register_number ? '1px solid #DC2626' : '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#111111',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
                {fieldErrors.register_number && (
                  <span style={{ color: '#DC2626', fontSize: '12px', marginTop: '2px', display: 'block' }}>
                    {fieldErrors.register_number}
                  </span>
                )}
              </div>

              <div>
                <label
                  htmlFor="college_id"
                  style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
                >
                  College / Institution *
                </label>
                <select
                  id="college_id"
                  name="college_id"
                  required
                  disabled={collegesLoading}
                  value={formData.college_id ?? ''}
                  onChange={handleChange}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: fieldErrors.college_id || fieldErrors.college ? '1px solid #DC2626' : '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#111111',
                    boxSizing: 'border-box',
                    backgroundColor: collegesLoading ? '#F3F4F6' : '#FFFFFF',
                    outlineColor: '#1455B8',
                  }}
                >
                  {collegesLoading ? (
                    <option value="">Loading enrolled colleges...</option>
                  ) : colleges.length === 0 ? (
                    <option value="">No active colleges found</option>
                  ) : (
                    <>
                      <option value="">-- Select Your College --</option>
                      {colleges.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.code}){c.location ? ` — ${c.location}` : ''}
                        </option>
                      ))}
                    </>
                  )}
                </select>
                {(fieldErrors.college_id || fieldErrors.college) && (
                  <span style={{ color: '#DC2626', fontSize: '12px', marginTop: '2px', display: 'block' }}>
                    {fieldErrors.college_id || fieldErrors.college}
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label
                  htmlFor="email"
                  style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
                >
                  Email Address *
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="student@college.edu"
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: fieldErrors.email ? '1px solid #DC2626' : '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#111111',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
                {fieldErrors.email && (
                  <span style={{ color: '#DC2626', fontSize: '12px', marginTop: '2px', display: 'block' }}>
                    {fieldErrors.email}
                  </span>
                )}
              </div>

              <div>
                <label
                  htmlFor="department"
                  style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
                >
                  Department / Course *
                </label>
                <input
                  id="department"
                  name="department"
                  type="text"
                  required
                  value={formData.department}
                  onChange={handleChange}
                  placeholder="e.g. B.Tech CSE / IT"
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: fieldErrors.department ? '1px solid #DC2626' : '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#111111',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
                {fieldErrors.department && (
                  <span style={{ color: '#DC2626', fontSize: '12px', marginTop: '2px', display: 'block' }}>
                    {fieldErrors.department}
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label
                  htmlFor="year_of_study"
                  style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
                >
                  Year of Study *
                </label>
                <select
                  id="year_of_study"
                  name="year_of_study"
                  value={formData.year_of_study}
                  onChange={handleChange}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#111111',
                    boxSizing: 'border-box',
                    backgroundColor: '#FFFFFF',
                    outlineColor: '#1455B8',
                  }}
                >
                  <option value="1st Year">1st Year</option>
                  <option value="2nd Year">2nd Year</option>
                  <option value="3rd Year">3rd Year</option>
                  <option value="Final Year">Final Year</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="phone_number"
                  style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}
                >
                  Mobile Phone Number *
                </label>
                <input
                  id="phone_number"
                  name="phone_number"
                  type="tel"
                  required
                  value={formData.phone_number}
                  onChange={handleChange}
                  placeholder="10-digit mobile number"
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: fieldErrors.phone_number ? '1px solid #DC2626' : '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#111111',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
                {fieldErrors.phone_number && (
                  <span style={{ color: '#DC2626', fontSize: '12px', marginTop: '2px', display: 'block' }}>
                    {fieldErrors.phone_number}
                  </span>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: '10px',
                padding: '12px 20px',
                background: loading
                  ? '#9CA3AF'
                  : 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: loading ? 'none' : '0 4px 12px rgba(11, 46, 111, 0.22)',
                transition: 'all 0.15s ease',
              }}
            >
              {loading ? 'Validating Registration...' : 'Register & Continue to Assessment →'}
            </button>
          </form>
        </div>
      </div>
  );
}
