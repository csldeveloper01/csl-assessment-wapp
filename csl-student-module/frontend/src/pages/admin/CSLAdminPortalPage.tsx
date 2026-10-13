import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import cslTypographyLogo from '../../assets/CSL-TYPOGRAPHY.png';
import cslBookLogo from '../../assets/CSL-BOOK.png';
import { api } from '../../api';
import { getAdminMe, type AdminUser } from '../../api/admin';
import { AdminLoginPage } from './AdminLoginPage';
import { AdminOverviewView } from './AdminOverviewView';
import { AdminCollegesView } from './AdminCollegesView';
import { AdminCandidatesView } from './AdminCandidatesView';
import { AdminAssessmentsView } from './AdminAssessmentsView';
import { AdminQuestionsView } from './AdminQuestionsView';
import { AdminConfigView } from './AdminConfigView';
import { AdminLiveAttemptsView } from './AdminLiveAttemptsView';
import { AdminAttemptReviewView } from './AdminAttemptReviewView';
import { AdminResultsView } from './AdminResultsView';
import { AdminIntegrityEventsView } from './AdminIntegrityEventsView';

// Minimum supported dimensions for desktop workstation usage
const MIN_DESKTOP_WIDTH = 1024;
const MIN_DESKTOP_HEIGHT = 650;

export function CSLAdminPortalPage() {
  const [adminUser, setAdminUser] = useState<AdminUser | null>(null);
  const [loadingAuth, setLoadingAuth] = useState<boolean>(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('csl_admin_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('csl_admin_sidebar_collapsed', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Viewport dimensions for desktop eligibility verification
  const [viewportDimensions, setViewportDimensions] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1280,
    height: typeof window !== 'undefined' ? window.innerHeight : 800,
  });

  // Track window resize dynamically
  useEffect(() => {
    const handleResize = () => {
      setViewportDimensions({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isDesktopEligible =
    viewportDimensions.width >= MIN_DESKTOP_WIDTH &&
    viewportDimensions.height >= MIN_DESKTOP_HEIGHT;

  const activeTab = searchParams.get('tab') || 'overview';
  const reviewAttemptId = searchParams.get('attemptId');
  const fromTab = searchParams.get('fromTab') || 'live';

  const CSL_ADMIN_TAB_AUTH_KEY = 'csl_admin_tab_authenticated';

  // Check existing authenticated session on mount (gated per-tab via sessionStorage)
  useEffect(() => {
    let isTabVerified = false;
    try {
      isTabVerified = sessionStorage.getItem(CSL_ADMIN_TAB_AUTH_KEY) === 'true';
    } catch {
      isTabVerified = false;
    }

    if (!isTabVerified) {
      // Closing and reopening a tab requires explicit admin password re-entry
      setAdminUser(null);
      setLoadingAuth(false);
      return;
    }

    // In the active tab, verify backend session is still active
    getAdminMe()
      .then((data) => {
        if (data && (data.is_staff || data.is_superuser || data.role === 'ADMIN')) {
          setAdminUser(data);
        } else {
          try {
            sessionStorage.removeItem(CSL_ADMIN_TAB_AUTH_KEY);
          } catch {
            // ignore
          }
          setAdminUser(null);
        }
      })
      .catch(() => {
        try {
          sessionStorage.removeItem(CSL_ADMIN_TAB_AUTH_KEY);
        } catch {
          // ignore
        }
        setAdminUser(null);
      })
      .finally(() => {
        setLoadingAuth(false);
      });
  }, []);

  const handleLoginSuccess = (admin: AdminUser) => {
    try {
      sessionStorage.setItem(CSL_ADMIN_TAB_AUTH_KEY, 'true');
    } catch {
      // ignore
    }
    setAdminUser(admin);
  };

  const handleLogout = async () => {
    try {
      await api.post('/logout/');
    } catch {
      // ignore
    } finally {
      try {
        sessionStorage.removeItem(CSL_ADMIN_TAB_AUTH_KEY);
      } catch {
        // ignore
      }
      setAdminUser(null);
      setSearchParams({ tab: 'overview' });
    }
  };

  const setActiveTab = (tabKey: string) => {
    setSearchParams({ tab: tabKey });
  };

  const handleOpenReview = (attemptId: string) => {
    setSearchParams({
      tab: 'review',
      attemptId,
      fromTab: activeTab !== 'review' ? activeTab : 'live',
    });
  };

  const handleBackFromReview = () => {
    setSearchParams({ tab: fromTab });
  };

  // ─── 1. AUTH LOADING STATE ──────────────────────────────────────────
  if (loadingAuth) {
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
        <div style={{ textAlign: 'center', color: '#0B2E6F', fontWeight: 700 }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1455B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 1.5s linear infinite' }}>
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
          Verifying administrator credentials...
        </div>
      </div>
    );
  }

  // ─── 2. DESKTOP / PC ELIGIBILITY ENFORCEMENT SCREEN ─────────────────
  if (!isDesktopEligible) {
    const isWidthShort = viewportDimensions.width < MIN_DESKTOP_WIDTH;
    const isHeightShort = viewportDimensions.height < MIN_DESKTOP_HEIGHT;

    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FCFAF5',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px 20px',
          boxSizing: 'border-box',
          fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: '560px',
            width: '100%',
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            border: '1px solid #E2E8F0',
            boxShadow: '0 20px 40px -12px rgba(11, 46, 111, 0.1)',
            padding: '36px 32px',
            textAlign: 'center',
            boxSizing: 'border-box',
          }}
        >
          {/* Logo */}
          <div style={{ marginBottom: '24px' }}>
            <img
              src={cslTypographyLogo}
              alt="CSL Creator Space Lab"
              style={{ height: '36px', width: 'auto', objectFit: 'contain' }}
            />
          </div>

          {/* Desktop Monitor Illustration */}
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '16px',
              backgroundColor: 'rgba(20, 85, 184, 0.08)',
              color: '#1455B8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
              border: '1px solid rgba(20, 85, 184, 0.15)',
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
              <line x1="8" y1="21" x2="16" y2="21"></line>
              <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
          </div>

          <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 8px 0', letterSpacing: '-0.02em' }}>
            Desktop Display Required
          </h2>

          <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.6, margin: '0 0 20px 0' }}>
            The CSL Admin Panel is engineered strictly for <strong>PC, laptop, and desktop workstations</strong> with sufficient screen real estate to manage live session telemetry, proctoring audits, and multi-question matrices securely.
          </p>

          {/* Viewport Diagnostic Card */}
          <div
            style={{
              backgroundColor: '#F8FAFC',
              borderRadius: '10px',
              border: '1px solid #E2E8F0',
              padding: '14px 18px',
              fontSize: '12px',
              color: '#334155',
              textAlign: 'left',
              marginBottom: '24px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontWeight: 600 }}>
              <span>Current Window Resolution:</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#DC2626' }}>
                {viewportDimensions.width} × {viewportDimensions.height} px
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontWeight: 600 }}>
              <span>Minimum Required Resolution:</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#16A34A' }}>
                {MIN_DESKTOP_WIDTH} × {MIN_DESKTOP_HEIGHT} px
              </span>
            </div>

            <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '8px', fontSize: '11px', color: '#64748B' }}>
              {isWidthShort && (
                <div style={{ color: '#B45309', marginBottom: '2px' }}>
                  • Width is {MIN_DESKTOP_WIDTH - viewportDimensions.width}px below the 1024px minimum.
                </div>
              )}
              {isHeightShort && (
                <div style={{ color: '#B45309' }}>
                  • Height is {MIN_DESKTOP_HEIGHT - viewportDimensions.height}px below the 650px minimum.
                </div>
              )}
            </div>
          </div>

          {/* Action Instructions */}
          <div style={{ fontSize: '12px', color: '#475569', lineHeight: 1.5, textAlign: 'center' }}>
            <div style={{ fontWeight: 700, color: '#0B2E6F', marginBottom: '4px' }}>
              How to proceed:
            </div>
            If you are currently on a laptop or desktop computer, please <strong>maximize your browser window</strong> or adjust your operating system display zoom to at least 100%. This screen updates automatically as soon as the window expands.
          </div>
        </div>
      </div>
    );
  }

  // ─── 3. ADMIN LOGIN SCREEN ──────────────────────────────────────────
  if (!adminUser) {
    return <AdminLoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  // ─── 4. SHARED NAVIGATION ITEMS ─────────────────────────────────────
  const navItems = [
    {
      key: 'overview',
      label: 'Overview',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7"></rect>
          <rect x="14" y="3" width="7" height="7"></rect>
          <rect x="14" y="14" width="7" height="7"></rect>
          <rect x="3" y="14" width="7" height="7"></rect>
        </svg>
      ),
    },
    {
      key: 'colleges',
      label: 'Colleges',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v4M12 14v4M16 14v4"></path>
        </svg>
      ),
    },
    {
      key: 'candidates',
      label: 'Candidates',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
          <circle cx="9" cy="7" r="4"></circle>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
        </svg>
      ),
    },
    {
      key: 'assessments',
      label: 'Assessments',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 11l3 3L22 4"></path>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
      ),
    },
    {
      key: 'questions',
      label: 'Question Bank',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
        </svg>
      ),
    },
    {
      key: 'live',
      label: 'Live Sessions',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      ),
    },
    {
      key: 'results',
      label: 'Results & Review',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="8" r="7"></circle>
          <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"></polyline>
        </svg>
      ),
    },
    {
      key: 'integrity',
      label: 'Integrity Events',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        </svg>
      ),
    },
    {
      key: 'config',
      label: 'Configuration',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      ),
    },
  ];

  const currentTabLabel =
    activeTab === 'review'
      ? 'Attempt Detailed Review'
      : navItems.find((n) => n.key === activeTab)?.label || activeTab;

  const sidebarWidth = isSidebarCollapsed ? 70 : 240;

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        maxHeight: '100vh',
        overflow: 'hidden',
        backgroundColor: '#FCFAF5',
        fontFamily: "'Manrope', 'Plus Jakarta Sans', system-ui, sans-serif",
      }}
    >
      {/* ─── 5. REFINED DESKTOP LEFT SIDEBAR (240px) ───────────────── */}
      <aside
        style={{
          width: `${sidebarWidth}px`,
          minWidth: `${sidebarWidth}px`,
          maxWidth: `${sidebarWidth}px`,
          backgroundColor: '#F5F8FF',
          color: '#0B2E6F',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          borderRight: '1px solid #DCE4F2',
          boxSizing: 'border-box',
          overflow: 'hidden',
          transition: 'width 0.2s ease, min-width 0.2s ease, max-width 0.2s ease',
          boxShadow: '1px 0 4px rgba(11, 46, 111, 0.03)',
          zIndex: 40,
        }}
      >
        {/* Top: Logo & Branding */}
        <div>
          <div
            style={{
              padding: isSidebarCollapsed ? '16px 8px' : '20px 18px',
              borderBottom: '1px solid #E2E8F0',
              display: 'flex',
              flexDirection: 'column',
              alignItems: isSidebarCollapsed ? 'center' : 'flex-start',
              gap: '12px',
            }}
          >
            {/* White Logo Container */}
            <div
              style={{
                backgroundColor: '#FFFFFF',
                padding: isSidebarCollapsed ? '8px' : '8px 14px',
                borderRadius: '10px',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 1px 4px rgba(0, 0, 0, 0.05)',
                border: '1px solid #E2E8F0',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onClick={() => setActiveTab('overview')}
              title="CSL Assessment Portal"
            >
              <img
                src={isSidebarCollapsed ? cslBookLogo : cslTypographyLogo}
                alt="CSL"
                style={{
                  height: isSidebarCollapsed ? '28px' : '32px',
                  width: 'auto',
                  objectFit: 'contain',
                }}
              />
            </div>

            {/* Product Hierarchy Tag */}
            {!isSidebarCollapsed && (
              <div>
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#0B2E6F',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}
                >
                  CSL ADMINISTRATION
                </div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginTop: '3px' }}>
                  Assessment Management System
                </div>
              </div>
            )}
          </div>

          {/* Navigation Items */}
          <nav
            style={{
              padding: isSidebarCollapsed ? '14px 6px' : '14px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            {navItems.map((item) => {
              const isActive = activeTab === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setActiveTab(item.key)}
                  title={item.label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: isSidebarCollapsed ? 'center' : 'flex-start',
                    gap: isSidebarCollapsed ? '0' : '10px',
                    padding: isSidebarCollapsed ? '10px 0' : '9px 12px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: isActive ? '#E8EFFD' : 'transparent',
                    color: isActive ? '#0B2E6F' : '#334155',
                    fontSize: '13px',
                    fontWeight: isActive ? 700 : 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                    position: 'relative',
                    boxShadow: isActive ? 'inset 0 0 0 1px rgba(20, 85, 184, 0.15)' : 'none',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = '#F0F4FC';
                      e.currentTarget.style.color = '#0B2E6F';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = '#334155';
                    }
                  }}
                >
                  {/* Active Indicator Bar on Left */}
                  {isActive && !isSidebarCollapsed && (
                    <span
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: '6px',
                        bottom: '6px',
                        width: '3.5px',
                        borderRadius: '0 2px 2px 0',
                        backgroundColor: '#F5B83D',
                      }}
                    />
                  )}

                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      color: isActive ? '#0B2E6F' : '#64748B',
                    }}
                  >
                    {item.icon}
                  </span>

                  {!isSidebarCollapsed && (
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.label}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom: Profile & Logout */}
        <div
          style={{
            padding: isSidebarCollapsed ? '12px 6px' : '14px 16px',
            borderTop: '1px solid #E2E8F0',
            backgroundColor: '#FFFFFF',
          }}
        >
          {!isSidebarCollapsed ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div
                  style={{
                    width: '30px',
                    height: '30px',
                    borderRadius: '50%',
                    backgroundColor: '#0B2E6F',
                    border: '1px solid #DCE4F2',
                    color: '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '11px',
                    fontWeight: 800,
                    flexShrink: 0,
                  }}
                >
                  {(adminUser.name || 'AD').slice(0, 2).toUpperCase()}
                </div>
                <div style={{ overflow: 'hidden' }}>
                  <div
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      color: '#0F172A',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {adminUser.name}
                  </div>
                  <div
                    style={{
                      fontSize: '11px',
                      color: '#64748B',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {adminUser.email}
                  </div>
                </div>
              </div>

              <button
                onClick={handleLogout}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '7px 12px',
                  backgroundColor: '#FEF2F2',
                  border: '1px solid #FECACA',
                  borderRadius: '6px',
                  color: '#DC2626',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#FEE2E2';
                  e.currentTarget.style.color = '#B91C1C';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FEF2F2';
                  e.currentTarget.style.color = '#DC2626';
                }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
                <span>Sign Out</span>
              </button>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
              <div
                title={`${adminUser.name} (${adminUser.email})`}
                style={{
                  width: '30px',
                  height: '30px',
                  borderRadius: '50%',
                  backgroundColor: '#0B2E6F',
                  border: '1px solid #DCE4F2',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                {(adminUser.name || 'AD').slice(0, 2).toUpperCase()}
              </div>

              <button
                onClick={handleLogout}
                title="Sign Out"
                style={{
                  width: '30px',
                  height: '30px',
                  borderRadius: '6px',
                  backgroundColor: '#FEF2F2',
                  border: '1px solid #FECACA',
                  color: '#DC2626',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#FEE2E2';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FEF2F2';
                }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ─── 6. MAIN CONTENT AREA (BESIDE SIDEBAR) ──────────────────── */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          maxHeight: '100vh',
          overflow: 'hidden',
          backgroundColor: '#FCFAF5',
        }}
      >
        {/* Top Header Breadcrumbs Bar */}
        <header
          style={{
            height: '60px',
            minHeight: '60px',
            backgroundColor: '#FFFFFF',
            borderBottom: '1px solid #E2E8F0',
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxSizing: 'border-box',
            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.02)',
          }}
        >
          {/* Left: Collapse Toggle & Breadcrumbs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={toggleSidebar}
              title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: '#0B2E6F',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#F8FAFC';
                e.currentTarget.style.borderColor = '#1455B8';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#FFFFFF';
                e.currentTarget.style.borderColor = '#CBD5E1';
              }}
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{
                  transform: isSidebarCollapsed ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 200ms cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              >
                <polyline points="11 17 6 12 11 7"></polyline>
                <polyline points="18 17 13 12 18 7"></polyline>
              </svg>
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#64748B' }}>
                CSL Administration /
              </span>
              <span style={{ fontSize: '13px', fontWeight: 800, color: '#0B2E6F' }}>
                {currentTabLabel}
              </span>
            </div>
          </div>

          {/* Right: Telemetry & Active Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                backgroundColor: '#ECFDF5',
                border: '1px solid #A7F3D0',
                color: '#065F46',
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '9999px',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: '#10B981',
                  display: 'inline-block',
                }}
              />
              PostgreSQL Connected
            </span>

            <span
              style={{
                fontSize: '11px',
                color: '#64748B',
                fontWeight: 600,
                borderLeft: '1px solid #E2E8F0',
                paddingLeft: '12px',
              }}
            >
              {viewportDimensions.width} × {viewportDimensions.height} px
            </span>
          </div>
        </header>

        {/* Scrollable Main View Container */}
        <main
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: '24px 28px',
            boxSizing: 'border-box',
          }}
        >
          {activeTab === 'overview' && (
            <AdminOverviewView onNavigateTab={(tab) => setActiveTab(tab)} />
          )}

          {activeTab === 'colleges' && <AdminCollegesView />}

          {activeTab === 'candidates' && (
            <AdminCandidatesView onReviewAttempt={handleOpenReview} />
          )}

          {activeTab === 'assessments' && <AdminAssessmentsView />}

          {activeTab === 'questions' && <AdminQuestionsView />}

          {activeTab === 'config' && <AdminConfigView />}

          {activeTab === 'live' && (
            <AdminLiveAttemptsView onReviewAttempt={handleOpenReview} />
          )}

          {activeTab === 'review' && (
            reviewAttemptId ? (
              <AdminAttemptReviewView
                attemptId={reviewAttemptId}
                onBack={handleBackFromReview}
              />
            ) : (
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '16px',
                  border: '1px solid #E2E8F0',
                  padding: '48px 32px',
                  textAlign: 'center',
                  boxShadow: '0 4px 14px rgba(11, 46, 111, 0.04)',
                  maxWidth: '560px',
                  margin: '40px auto',
                }}
              >
                <div
                  style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(20, 85, 184, 0.08)',
                    color: '#1455B8',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 16px',
                  }}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                  </svg>
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 8px 0' }}>
                  No Assessment Attempt Selected
                </h3>
                <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.5, margin: '0 0 24px 0' }}>
                  Please select an attempt from Live Attempts, Candidates, Results, or Integrity Events to inspect its immutable snapshot and question responses.
                </p>
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                  <button
                    onClick={() => setActiveTab('live')}
                    style={{
                      padding: '9px 20px',
                      backgroundColor: '#1455B8',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      boxShadow: '0 2px 6px rgba(20, 85, 184, 0.2)',
                    }}
                  >
                    View Live Attempts
                  </button>
                  <button
                    onClick={() => setActiveTab('results')}
                    style={{
                      padding: '9px 20px',
                      backgroundColor: '#FFFFFF',
                      color: '#0B2E6F',
                      border: '1.5px solid #CBD5E1',
                      borderRadius: '8px',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    View Results
                  </button>
                </div>
              </div>
            )
          )}

          {activeTab === 'results' && (
            <AdminResultsView onReviewAttempt={handleOpenReview} />
          )}

          {activeTab === 'integrity' && (
            <AdminIntegrityEventsView onReviewAttempt={handleOpenReview} />
          )}
        </main>
      </div>
    </div>
  );
}
