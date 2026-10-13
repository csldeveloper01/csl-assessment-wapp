import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAssessmentResult, type ResultResponse } from '../../api/assessment';
import cslTypographyLogo from '../../assets/CSL-TYPOGRAPHY.png';

export function AssessmentResultsPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const [result, setResult] = useState<ResultResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [secondsRemaining, setSecondsRemaining] = useState<number>(4);

  // Validate redirect URL safely: strictly http/https and sanitize origin/pathname
  const rawRedirectUrl = import.meta.env.VITE_CSL_MAIN_WEBSITE_URL;
  let safeRedirectUrl: string | null = null;
  if (rawRedirectUrl && typeof rawRedirectUrl === 'string') {
    try {
      const parsed = new URL(rawRedirectUrl.trim());
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        // Sanitize to origin + pathname only to guarantee no sensitive data is leaked
        safeRedirectUrl = `${parsed.origin}${parsed.pathname === '/' ? '' : parsed.pathname}`;
      }
    } catch {
      safeRedirectUrl = null;
    }
  }

  useEffect(() => {
    if (!attemptId) return;
    setLoading(true);
    getAssessmentResult(attemptId)
      .then((data) => {
        setResult(data);
      })
      .catch((err: unknown) => {
        if (typeof err === 'object' && err !== null && 'response' in err) {
          const axErr = err as { response?: { status?: number; data?: { detail?: string } } };
          if (axErr.response?.status === 403 || axErr.response?.status === 401) {
            setError('Access forbidden: You are not authorized to view this assessment.');
          } else {
            setError(axErr.response?.data?.detail || 'Failed to retrieve assessment submission.');
          }
        } else {
          setError('Network error retrieving confirmation. Please check your connection.');
        }
      })
      .finally(() => {
        setLoading(false);
      });
  }, [attemptId]);

  // Safe redirect after 3.5 seconds if VITE_CSL_MAIN_WEBSITE_URL is configured
  useEffect(() => {
    if (!safeRedirectUrl || loading || error) return;

    const interval = setInterval(() => {
      setSecondsRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    const redirectTimer = setTimeout(() => {
      window.location.replace(safeRedirectUrl!);
    }, 3500);

    return () => {
      clearInterval(interval);
      clearTimeout(redirectTimer);
    };
  }, [safeRedirectUrl, loading, error]);

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              border: '3px solid #E2E8F0',
              borderTopColor: '#1455B8',
              borderRadius: '50%',
              margin: '0 auto 16px',
              animation: 'spin 1s linear infinite',
            }}
          />
          <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
          <p style={{ fontSize: '15px', color: '#64748B', fontWeight: 600 }}>
            Verifying assessment submission...
          </p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          padding: '16px',
          fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '460px',
            width: '100%',
            backgroundColor: '#FFFFFF',
            padding: '36px',
            borderRadius: '16px',
            border: '1px solid rgba(245, 184, 61, 0.3)',
            boxShadow: '0 10px 25px -5px rgba(11, 46, 111, 0.08)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '36px', marginBottom: '12px' }}>⚠️</div>
          <h2 style={{ color: '#DC2626', fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>
            Unable to Load Submission
          </h2>
          <p style={{ fontSize: '14px', color: '#6B7280', marginBottom: '24px', lineHeight: 1.5 }}>
            {error || 'Unable to confirm submission.'}
          </p>
          <Link
            to="/assessment/register"
            style={{
              display: 'inline-block',
              padding: '10px 24px',
              background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
              color: '#FFFFFF',
              borderRadius: '8px',
              textDecoration: 'none',
              fontSize: '14px',
              fontWeight: 700,
            }}
          >
            Return to Portal Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#FCFAF5',
        padding: '36px 16px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: '560px',
          width: '100%',
          backgroundColor: '#FFFFFF',
          borderRadius: '20px',
          boxShadow: '0 20px 45px -10px rgba(11, 46, 111, 0.08)',
          border: '1.5px solid rgba(245, 184, 61, 0.28)',
          padding: '44px 36px',
          textAlign: 'center',
          boxSizing: 'border-box',
        }}
      >
        {/* CSL Typography Logo */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            padding: '8px 18px',
            borderRadius: '10px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
            border: '1px solid #E2E8F0',
            marginBottom: '24px',
          }}
        >
          <img
            src={cslTypographyLogo}
            alt="CSL Creator Space Lab"
            style={{ height: '30px', width: 'auto', objectFit: 'contain' }}
          />
        </div>

        {/* Success Checkmark Circle */}
        <div
          style={{
            width: '72px',
            height: '72px',
            borderRadius: '50%',
            backgroundColor: '#ECFDF5',
            border: '2.5px solid #A7F3D0',
            color: '#059669',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            fontSize: '34px',
            fontWeight: 800,
            boxShadow: '0 6px 16px rgba(16, 185, 129, 0.15)',
          }}
        >
          ✓
        </div>

        {/* Primary Heading: EXACTLY 'Assessment Completed' */}
        <h1
          style={{
            fontSize: '26px',
            fontWeight: 800,
            color: '#0B2E6F',
            margin: '0 0 10px 0',
            letterSpacing: '-0.02em',
          }}
        >
          Assessment Completed
        </h1>

        <p
          style={{
            fontSize: '14px',
            color: '#475569',
            lineHeight: 1.5,
            margin: '0 0 24px 0',
          }}
        >
          Your responses have been recorded and your assessment session has concluded successfully.
        </p>

        {/* Candidate & Verification Card */}
        <div
          style={{
            backgroundColor: '#F8FAFC',
            borderRadius: '12px',
            border: '1px solid #E2E8F0',
            padding: '16px 20px',
            marginBottom: '26px',
            textAlign: 'left',
            fontSize: '13px',
            lineHeight: 1.6,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
            <span style={{ color: '#64748B', fontWeight: 600 }}>Candidate Name:</span>
            <span style={{ color: '#0F172A', fontWeight: 700 }}>{result.candidate_name}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
            <span style={{ color: '#64748B', fontWeight: 600 }}>Register Number:</span>
            <span style={{ color: '#0F172A', fontWeight: 700 }}>{result.register_number}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', paddingBottom: '6px', marginBottom: '6px' }}>
            <span style={{ color: '#64748B', fontWeight: 600 }}>Institution:</span>
            <span style={{ color: '#0F172A', fontWeight: 700 }}>{result.college}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#64748B', fontWeight: 600 }}>Submission Status:</span>
            <span style={{ color: '#059669', fontWeight: 700 }}>Recorded & Verified</span>
          </div>
        </div>

        {/* Redirect Notice or Return Button */}
        {safeRedirectUrl ? (
          <div
            style={{
              padding: '14px 18px',
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              borderRadius: '10px',
              marginBottom: '10px',
            }}
          >
            <div style={{ fontSize: '13px', color: '#1E40AF', fontWeight: 600, marginBottom: '6px' }}>
              Redirecting to CSL portal in {secondsRemaining} seconds...
            </div>
            <a
              href={safeRedirectUrl}
              style={{
                fontSize: '12px',
                color: '#1455B8',
                fontWeight: 700,
                textDecoration: 'underline',
              }}
            >
              Click here if you are not redirected automatically
            </a>
          </div>
        ) : (
          <div>
            <p style={{ fontSize: '12.5px', color: '#64748B', marginBottom: '16px' }}>
              You may now safely close this window or return to the registration portal.
            </p>
            <Link
              to="/assessment/register"
              style={{
                display: 'inline-block',
                padding: '10px 24px',
                background: 'linear-gradient(135deg, #0B2E6F 0%, #1455B8 100%)',
                color: '#FFFFFF',
                borderRadius: '8px',
                textDecoration: 'none',
                fontSize: '13px',
                fontWeight: 700,
                boxShadow: '0 2px 8px rgba(11, 46, 111, 0.2)',
              }}
            >
              Return to Registration Portal
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
