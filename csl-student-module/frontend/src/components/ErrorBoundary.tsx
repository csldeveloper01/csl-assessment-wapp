import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    if (this.props.onReset) {
      this.props.onReset();
    }
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/csl-admin?tab=overview';
  };

  private handleGoPortal = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/';
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#FCFAF5',
            padding: '24px',
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
              boxShadow: '0 20px 40px -12px rgba(11, 46, 111, 0.12)',
              padding: '36px 32px',
              textAlign: 'center',
              boxSizing: 'border-box',
            }}
          >
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '14px',
                backgroundColor: '#FEF2F2',
                color: '#DC2626',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 18px',
                border: '1px solid #FECACA',
              }}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>

            <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 8px 0', letterSpacing: '-0.02em' }}>
              {this.props.fallbackTitle || 'Component Rendering Error'}
            </h2>

            <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.6, margin: '0 0 20px 0' }}>
              An unexpected error prevented this view from rendering. Your session data and platform settings remain safely preserved.
            </p>

            {this.state.error && (
              <div
                style={{
                  backgroundColor: '#F8FAFC',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  padding: '12px 16px',
                  fontSize: '12px',
                  color: '#991B1B',
                  textAlign: 'left',
                  marginBottom: '24px',
                  fontFamily: 'monospace',
                  wordBreak: 'break-word',
                  maxHeight: '120px',
                  overflowY: 'auto',
                }}
              >
                {this.state.error.message || String(this.state.error)}
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={this.handleReload}
                style={{
                  padding: '9px 18px',
                  backgroundColor: '#0B2E6F',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 2px 6px rgba(11, 46, 111, 0.2)',
                }}
              >
                Reload View
              </button>
              <button
                onClick={this.handleGoHome}
                style={{
                  padding: '9px 16px',
                  backgroundColor: '#FFFFFF',
                  color: '#0B2E6F',
                  border: '1.5px solid #CBD5E1',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Admin Overview
              </button>
              <button
                onClick={this.handleGoPortal}
                style={{
                  padding: '9px 16px',
                  backgroundColor: '#F1F5F9',
                  color: '#475569',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Student Portal
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
