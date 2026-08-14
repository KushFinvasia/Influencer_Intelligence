import React from 'react'

export default function Sidebar({
  activeNav,
  onNavChange,
  metrics,
  generatedAt,
  onRefresh,
  onScrapeYT,
  onScrapeInsta,
}) {
  const formattedDate = generatedAt
    ? new Date(generatedAt).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
    : 'Aug 7, 2025 10:30 AM'

  return (
    <aside className="sidebar">
      {/* Brand / Logo */}
      <div className="sidebar__brand">
        <div className="sidebar__logo-icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="28" height="28" rx="6" fill="#EFF6FF" />
            <path d="M6 19L10 13L14 16L22 7" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M17 7H22V12" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            <rect x="7" y="19" width="3" height="4" rx="1" fill="#3B82F6" opacity="0.4"/>
            <rect x="12.5" y="16" width="3" height="7" rx="1" fill="#10B981" opacity="0.5"/>
            <rect x="18" y="11" width="3" height="12" rx="1" fill="#3B82F6"/>
          </svg>
        </div>
        <div className="sidebar__brand-text">
          <div className="sidebar__brand-title">FinIntel</div>
          <div className="sidebar__brand-sub">Platform</div>
        </div>
      </div>

      {/* Main Nav Items */}
      <div className="sidebar__section">
        <button
          className={`sidebar__nav-item sidebar__nav-item--dashboard ${activeNav === 'all' ? 'active' : ''}`}
          onClick={() => onNavChange('all')}
        >
          <span className="sidebar__nav-icon">📊</span>
          <span className="sidebar__nav-label">Dashboard</span>
        </button>
      </div>

      {/* Discover Section */}
      <div className="sidebar__section">
        <div className="sidebar__section-title">DISCOVER</div>
        <button
          className={`sidebar__nav-item ${activeNav === 'all' ? 'active' : ''}`}
          onClick={() => onNavChange('all')}
        >
          <span className="sidebar__nav-icon">🔍</span>
          <span className="sidebar__nav-label">All Creators</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'longform' ? 'active' : ''}`}
          onClick={() => onNavChange('longform')}
        >
          <span className="sidebar__nav-icon">🎬</span>
          <span className="sidebar__nav-label">Long-form ({metrics.longformCount || 0})</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'shortform' ? 'active' : ''}`}
          onClick={() => onNavChange('shortform')}
        >
          <span className="sidebar__nav-icon">📱</span>
          <span className="sidebar__nav-label">Shorts / Reels ({metrics.shortformCount || 0})</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'with_broker' ? 'active' : ''}`}
          onClick={() => onNavChange('with_broker')}
        >
          <span className="sidebar__nav-icon">🏦</span>
          <span className="sidebar__nav-label">With Broker ({metrics.withBrokerCount || 0})</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'with_contact' ? 'active' : ''}`}
          onClick={() => onNavChange('with_contact')}
        >
          <span className="sidebar__nav-icon">👤</span>
          <span className="sidebar__nav-label">With Contact ({metrics.withContactCount || 0})</span>
        </button>
      </div>

      {/* Analytics Section */}
      <div className="sidebar__section">
        <div className="sidebar__section-title">ANALYTICS</div>
        <button
          className={`sidebar__nav-item ${activeNav === 'performance' ? 'active' : ''}`}
          onClick={() => onNavChange('performance')}
        >
          <span className="sidebar__nav-icon">📈</span>
          <span className="sidebar__nav-label">Performance</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'engagement' ? 'active' : ''}`}
          onClick={() => onNavChange('engagement')}
        >
          <span className="sidebar__nav-icon">⚡</span>
          <span className="sidebar__nav-label">Engagement</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'followers_tier' ? 'active' : ''}`}
          onClick={() => onNavChange('followers_tier')}
        >
          <span className="sidebar__nav-icon">👥</span>
          <span className="sidebar__nav-label">Followers Tier</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'top_brokers' ? 'active' : ''}`}
          onClick={() => onNavChange('top_brokers')}
        >
          <span className="sidebar__nav-icon">🏛️</span>
          <span className="sidebar__nav-label">Top Brokers</span>
        </button>
      </div>

      {/* Saved Views Section */}
      <div className="sidebar__section">
        <div className="sidebar__section-title">SAVED VIEWS</div>
        <button
          className={`sidebar__nav-item ${activeNav === 'my_views' ? 'active' : ''}`}
          onClick={() => onNavChange('my_views')}
        >
          <span className="sidebar__nav-icon">🔖</span>
          <span className="sidebar__nav-label">My Views</span>
        </button>
        <button
          className={`sidebar__nav-item ${activeNav === 'recently_viewed' ? 'active' : ''}`}
          onClick={() => onNavChange('recently_viewed')}
        >
          <span className="sidebar__nav-icon">🕒</span>
          <span className="sidebar__nav-label">Recently Viewed</span>
        </button>
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar__footer">
        <div className="sidebar__update-label">Data last updated</div>
        <div className="sidebar__update-time">{formattedDate}</div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
          <button className="sidebar__refresh-btn" onClick={onRefresh}>
            Refresh Data
          </button>
          <button className="sidebar__refresh-btn" style={{ background: '#d32f2f' }} onClick={onScrapeYT}>
            Launch YT Search
          </button>
          <button className="sidebar__refresh-btn" style={{ background: '#c13584' }} onClick={onScrapeInsta}>
            Launch Insta Search
          </button>
        </div>
      </div>
    </aside>
  )
}
