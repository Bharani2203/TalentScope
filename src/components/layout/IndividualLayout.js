import React, { useState, useEffect, useRef } from 'react';
import { Outlet } from 'react-router-dom';
import CleanAIHelp, {
  renderCleanAIHelpPage,
  formatMarkdown,
  renderEvidenceCards,
} from '../../pages/individual/assistant/CleanAIHelp.js';
import { sendSupervisorMessage, buildUserContext } from '../../services/supervisor-api.js';

export default function IndividualLayout({ children }) {
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const drawerContentRef = useRef(null);
  const mountedRef = useRef(false);

  useEffect(() => {
    // Mount the persistent chat drawer once into drawerContentRef
    if (drawerContentRef.current && !mountedRef.current) {
      mountedRef.current = true;
      if (typeof renderCleanAIHelpPage === 'function') {
        renderCleanAIHelpPage(drawerContentRef.current);
      }
    }
  }, []);

  return (
    <div className="individual-layout-shell" style={{ position: 'relative', minHeight: '100vh' }}>
      {/* 1. Main Page Content (via Outlet or children) */}
      <div className="individual-content-area">
        {children || <Outlet />}
      </div>

      {/* 2. Floating Action Button (FAB) in the bottom-right corner */}
      <button
        id="copilotFab"
        className="copilot-fab-button fixed bottom-4 right-4"
        type="button"
        aria-label={isCopilotOpen ? 'Close AI Co-Pilot' : 'Open AI Co-Pilot'}
        aria-expanded={isCopilotOpen}
        onClick={() => setIsCopilotOpen(!isCopilotOpen)}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 9990,
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          backgroundColor: '#2563eb',
          color: '#ffffff',
          border: 'none',
          boxShadow: '0 4px 16px rgba(37, 99, 235, 0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          fontSize: '26px',
          transition: 'transform 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.08)';
          e.currentTarget.style.backgroundColor = '#1d4ed8';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1)';
          e.currentTarget.style.backgroundColor = '#2563eb';
        }}
        title="Open AI Co-Pilot"
      >
        <span role="img" aria-label="AI Co-Pilot robot icon">🤖</span>
      </button>

      {/* 3. Backdrop for mobile/responsive overlay */}
      {isCopilotOpen && (
        <div
          id="copilotBackdrop"
          className="copilot-drawer-backdrop"
          onClick={() => setIsCopilotOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.25)',
            backdropFilter: 'blur(2px)',
            zIndex: 9994,
            transition: 'opacity 0.25s ease',
          }}
          aria-hidden="true"
        />
      )}

      {/* 4. Persistent Slide-Out Drawer (Mounted OUTSIDE <Outlet /> so chat history is never destroyed) */}
      <aside
        id="copilotSlideoutDrawer"
        className="copilot-slideout-drawer"
        aria-hidden={!isCopilotOpen}
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          height: '100vh',
          width: '440px',
          maxWidth: '92vw',
          backgroundColor: '#ffffff',
          boxShadow: isCopilotOpen ? '-6px 0 24px rgba(15, 23, 42, 0.15)' : 'none',
          zIndex: 9995,
          transform: isCopilotOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
          display: 'flex',
          flexDirection: 'column',
          boxSizing: 'border-box',
          overflow: 'hidden',
        }}
      >
        {/* Drawer Header with Close Button */}
        <div
          className="copilot-drawer-header"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: '1px solid #e2e8f0',
            backgroundColor: '#f8fafc',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '20px' }}>🤖</span>
            <strong style={{ fontSize: '16px', color: '#0f172a' }}>AI Co-Pilot</strong>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                backgroundColor: '#ecfdf5',
                color: '#059669',
                padding: '2px 7px',
                borderRadius: '6px',
                border: '1px solid #a7f3d0',
              }}
            >
              Live
            </span>
          </div>
          <button
            id="closeCopilotDrawer"
            type="button"
            aria-label="Close AI Co-Pilot"
            onClick={() => setIsCopilotOpen(false)}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '20px',
              lineHeight: 1,
              color: '#64748b',
              cursor: 'pointer',
              padding: '6px 10px',
              borderRadius: '6px',
              transition: 'background-color 0.15s ease, color 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#e2e8f0';
              e.currentTarget.style.color = '#0f172a';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = '#64748b';
            }}
          >
            ✕
          </button>
        </div>

        {/* Persistent Chat Content Container */}
        <div
          ref={drawerContentRef}
          id="copilotDrawerContent"
          className="copilot-drawer-content"
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        />
      </aside>
    </div>
  );
}

export { IndividualLayout };
