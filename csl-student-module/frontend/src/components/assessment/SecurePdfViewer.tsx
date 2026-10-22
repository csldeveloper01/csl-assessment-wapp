import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?url';

// Configure worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

export interface SecurePdfViewerProps {
  pdfBlob: Blob | null;
  candidateName: string;
  candidateIdentifier?: string; // register number or candidate ID
  assessmentCode?: string;
  attemptId?: string;
  onLoadError?: (error: string) => void;
}

export const SecurePdfViewer: React.FC<SecurePdfViewerProps> = ({
  pdfBlob,
  candidateName,
  candidateIdentifier,
  assessmentCode,
  attemptId,
  onLoadError,
}) => {
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.25);
  const [rotation, setRotation] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Watermark text composed solely of authorized candidate & attempt details
  const watermarkText = `${candidateName}${candidateIdentifier ? ` • ${candidateIdentifier}` : ''} • ${assessmentCode || 'CSL'}`;
  const subWatermarkText = `Session: ${attemptId ? attemptId.slice(0, 8) : 'ACTIVE'} • DO NOT DISTRIBUTE`;

  // 1. Load document when blob changes
  useEffect(() => {
    if (!pdfBlob) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    const loadDoc = async () => {
      try {
        const arrayBuffer = await pdfBlob.arrayBuffer();
        if (!isMounted) return;

        const loadingTask = pdfjsLib.getDocument({
          data: new Uint8Array(arrayBuffer),
        });

        const doc = await loadingTask.promise;
        if (!isMounted) return;

        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setCurrentPage(1);
        setLoading(false);
      } catch (err: any) {
        if (!isMounted) return;
        console.error('Failed to parse and load PDF document:', err);
        const msg = 'Unable to render question paper. The document could not be decoded.';
        setError(msg);
        setLoading(false);
        if (onLoadError) onLoadError(msg);
      }
    };

    loadDoc();

    return () => {
      isMounted = false;
      if (pdfDoc) {
        pdfDoc.cleanup();
      }
    };
  }, [pdfBlob]);

  // 2. Render active page onto canvas and draw watermark
  const renderPage = useCallback(async () => {
    if (!pdfDoc || !canvasRef.current) return;

    try {
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }

      const page = await pdfDoc.getPage(currentPage);
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d', { willReadFrequently: false });
      if (!ctx) return;

      const viewport = page.getViewport({ scale, rotation });
      const outputScale = window.devicePixelRatio || 1;

      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      ctx.save();
      ctx.scale(outputScale, outputScale);

      const renderContext = {
        canvasContext: ctx,
        viewport,
      };

      const task = page.render(renderContext as any);
      renderTaskRef.current = task;
      await task.promise;

      // ─── Draw persistent, tamper-deterrent watermark into canvas pixels ───
      ctx.save();
      ctx.translate(viewport.width / 2, viewport.height / 2);
      ctx.rotate((-30 * Math.PI) / 180);
      ctx.textAlign = 'center';

      // Repeating background watermark pattern
      const stepX = 260;
      const stepY = 160;
      const range = Math.max(viewport.width, viewport.height) * 1.5;

      for (let x = -range; x <= range; x += stepX) {
        for (let y = -range; y <= range; y += stepY) {
          ctx.font = '600 13px system-ui, -apple-system, sans-serif';
          ctx.fillStyle = 'rgba(15, 23, 42, 0.085)';
          ctx.fillText(watermarkText, x, y);

          ctx.font = '500 10px system-ui, -apple-system, sans-serif';
          ctx.fillStyle = 'rgba(15, 23, 42, 0.06)';
          ctx.fillText(subWatermarkText, x, y + 16);
        }
      }

      ctx.restore();
      ctx.restore();
    } catch (err: any) {
      if (err?.name !== 'RenderingCancelledException') {
        console.error('Page render error:', err);
      }
    }
  }, [pdfDoc, currentPage, scale, rotation, watermarkText, subWatermarkText]);

  useEffect(() => {
    renderPage();
  }, [renderPage]);

  // 3. Client-side deterrents: Prevent right-click, Ctrl+P, Ctrl+S
  const handleKeyDown = useCallback((e: React.KeyboardEvent | KeyboardEvent) => {
    // Left/Right or PageUp/PageDown for navigation
    if (e.key === 'ArrowRight' || e.key === 'PageDown') {
      setCurrentPage((p) => Math.min(numPages, p + 1));
    } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
      setCurrentPage((p) => Math.max(1, p - 1));
    }

    // Intercept common extraction/print shortcuts
    if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, [numPages]);

  useEffect(() => {
    const handleGlobalPrint = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
        e.preventDefault();
      }
    };
    window.addEventListener('keydown', handleGlobalPrint);
    return () => window.removeEventListener('keydown', handleGlobalPrint);
  }, []);

  return (
    <div
      ref={containerRef}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#1E293B',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: '0 4px 16px -2px rgba(11, 46, 111, 0.12)',
        position: 'relative',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        outline: 'none',
      }}
    >
      {/* ─── Top Control Toolbar ─── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 16px',
          backgroundColor: '#0F172A',
          borderBottom: '1px solid #334155',
          color: '#F8FAFC',
          fontSize: '12px',
          flexWrap: 'wrap',
          gap: '8px',
          zIndex: 10,
        }}
      >
        {/* Navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            disabled={currentPage <= 1 || loading}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            style={{
              padding: '5px 10px',
              borderRadius: '6px',
              border: '1px solid #475569',
              backgroundColor: currentPage <= 1 ? '#1E293B' : '#334155',
              color: currentPage <= 1 ? '#64748B' : '#FFFFFF',
              fontWeight: 700,
              cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
              fontSize: '12px',
            }}
          >
            ← Prev
          </button>

          <span style={{ fontWeight: 600, color: '#E2E8F0' }}>
            Page {currentPage} of {numPages || 1}
          </span>

          <button
            type="button"
            disabled={currentPage >= numPages || loading}
            onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
            style={{
              padding: '5px 10px',
              borderRadius: '6px',
              border: '1px solid #475569',
              backgroundColor: currentPage >= numPages ? '#1E293B' : '#334155',
              color: currentPage >= numPages ? '#64748B' : '#FFFFFF',
              fontWeight: 700,
              cursor: currentPage >= numPages ? 'not-allowed' : 'pointer',
              fontSize: '12px',
            }}
          >
            Next →
          </button>
        </div>

        {/* Security Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            color: '#94A3B8',
            fontSize: '11px',
            fontWeight: 500,
          }}
        >
          <span style={{ color: '#10B981' }}>●</span>
          <span>Verified Protected Session</span>
        </div>

        {/* Zoom & Rotation Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            type="button"
            onClick={() => setScale((s) => Math.max(0.6, s - 0.15))}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid #475569',
              backgroundColor: '#334155',
              color: '#FFFFFF',
              fontWeight: 700,
              cursor: 'pointer',
              fontSize: '12px',
            }}
            title="Zoom Out"
          >
            −
          </button>

          <span style={{ fontWeight: 700, color: '#F1F5F9', minWidth: '40px', textAlign: 'center' }}>
            {Math.round(scale * 100)}%
          </span>

          <button
            type="button"
            onClick={() => setScale((s) => Math.min(2.5, s + 0.15))}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid #475569',
              backgroundColor: '#334155',
              color: '#FFFFFF',
              fontWeight: 700,
              cursor: 'pointer',
              fontSize: '12px',
            }}
            title="Zoom In"
          >
            +
          </button>

          <button
            type="button"
            onClick={() => {
              setScale(1.25);
              setRotation(0);
            }}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid #475569',
              backgroundColor: '#1E293B',
              color: '#CBD5E1',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '11px',
              marginLeft: '4px',
            }}
            title="Reset Zoom"
          >
            Reset
          </button>

          <button
            type="button"
            onClick={() => setRotation((r) => (r + 90) % 360)}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid #475569',
              backgroundColor: '#1E293B',
              color: '#CBD5E1',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '11px',
              marginLeft: '4px',
            }}
            title="Rotate Page"
          >
            ↻
          </button>
        </div>
      </div>

      {/* ─── Canvas Viewport Container ─── */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: 'auto',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: '24px 16px',
          backgroundColor: '#334155',
          position: 'relative',
        }}
      >
        {loading ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
              minHeight: '300px',
              color: '#FFFFFF',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                border: '3px solid rgba(255,255,255,0.3)',
                borderTopColor: '#FFD45C',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
            <span style={{ fontSize: '13px', fontWeight: 600 }}>Loading Question Paper Pages...</span>
          </div>
        ) : error ? (
          <div
            style={{
              backgroundColor: '#FFFFFF',
              padding: '32px',
              borderRadius: '12px',
              textAlign: 'center',
              maxWidth: '420px',
              margin: 'auto',
            }}
          >
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>⚠️</div>
            <h4 style={{ color: '#DC2626', margin: '0 0 8px 0', fontSize: '16px', fontWeight: 700 }}>
              Unable to Display Document
            </h4>
            <p style={{ color: '#64748B', fontSize: '13px', margin: '0 0 16px 0' }}>{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: '8px 16px',
                backgroundColor: '#0B2E6F',
                color: '#FFFFFF',
                borderRadius: '8px',
                border: 'none',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Retry
            </button>
          </div>
        ) : (
          <div
            style={{
              position: 'relative',
              boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
              backgroundColor: '#FFFFFF',
              borderRadius: '4px',
              overflow: 'hidden',
              display: 'inline-block',
            }}
          >
            <canvas ref={canvasRef} style={{ display: 'block' }} />

            {/* Overlaid transparent watermark layer for CSS screen protection */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-around',
                opacity: 0.12,
              }}
            >
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  style={{
                    transform: 'rotate(-25deg)',
                    whiteSpace: 'nowrap',
                    fontSize: '16px',
                    fontWeight: 700,
                    color: '#000000',
                    textAlign: 'center',
                    padding: '20px 0',
                    userSelect: 'none',
                  }}
                >
                  {watermarkText} • {subWatermarkText}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ─── Print Suppressing Stylesheet ─── */}
      <style>{`
        @media print {
          body * {
            visibility: hidden !important;
          }
          canvas {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
};
