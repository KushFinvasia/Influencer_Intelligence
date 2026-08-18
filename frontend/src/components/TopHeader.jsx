import React, { useState } from 'react'

export default function TopHeader({
  theme,
  onToggleTheme,
  onOpenColumnSettings,
  onExportCSV,
  onExportExcel,
}) {
  const [showExportMenu, setShowExportMenu] = useState(false)

  return (
    <header className="top-header">
      <div className="top-header__title-group">
        <h1 className="top-header__title">Financial Influencer Intelligence</h1>
        <p className="top-header__subtitle">
          Consolidated creator directory with format classification, verified contacts, brokers &amp; performance analytics.
        </p>
      </div>

      <div className="top-header__actions">
        {/* Dark Mode Switch */}
        <div className="dark-mode-toggle" onClick={onToggleTheme} title="Toggle Dark/Light Mode">
          <div className={`toggle-switch ${theme === 'dark' ? 'toggle-switch--active' : ''}`}>
            <div className="toggle-switch__handle" />
          </div>
          <span className="toggle-switch__label">Dark mode</span>
        </div>

        {/* Export Dropdown */}
        <div className="export-dropdown-container">
          <button
            className="btn btn--outline"
            onClick={() => setShowExportMenu(prev => !prev)}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <span>Export</span>
            <span style={{ fontSize: '10px', marginLeft: '2px' }}>▼</span>
          </button>

          {showExportMenu && (
            <>
              <div className="popover-backdrop popover-backdrop--transparent" onClick={() => setShowExportMenu(false)} />
              <div className="export-menu">
                <button
                  type="button"
                  className="export-menu__item"
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowExportMenu(false)
                    onExportCSV()
                  }}
                >
                  <span className="export-menu__icon">📄</span>
                  <span>Export as CSV</span>
                </button>
                {onExportExcel && (
                  <button
                    type="button"
                    className="export-menu__item"
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowExportMenu(false)
                      onExportExcel()
                    }}
                  >
                    <span className="export-menu__icon">📊</span>
                    <span>Export as Excel</span>
                  </button>
                )}
              </div>
            </>
          )}
        </div>

        {/* Column Settings Button */}
        <button className="btn btn--outline" onClick={onOpenColumnSettings}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          <span>Column Settings</span>
        </button>
      </div>
    </header>
  )
}
