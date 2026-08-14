import React from 'react'

export default function MetricCards({ creators }) {
  const total = creators.length || 0

  // Calculate actual metrics from creators list
  const longformCount = creators.filter(c => c.format_filter === 'longform').length
  const shortformCount = creators.filter(c =>
    c.format_filter === 'shortform' || c.format_filter === 'carousels' || c.format_filter === 'images'
  ).length
  const withBrokerCount = creators.filter(c => c.broker && c.broker !== '-').length
  const withContactCount = creators.filter(c =>
    (c.email && c.email !== '-') || (c.phone && c.phone !== '-')
  ).length

  const longformPct = total > 0 ? Math.round((longformCount / total) * 100) : 0
  const shortformPct = total > 0 ? Math.round((shortformCount / total) * 100) : 0
  const withBrokerPct = total > 0 ? Math.round((withBrokerCount / total) * 100) : 0
  const withContactPct = total > 0 ? Math.round((withContactCount / total) * 100) : 0

  return (
    <div className="metric-cards-grid">
      {/* Card 1: Total Creators */}
      <div className="metric-card">
        <div className="metric-card__icon metric-card__icon--blue">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </div>
        <div className="metric-card__content">
          <div className="metric-card__title">Total Creators</div>
          <div className="metric-card__value-row">
            <span className="metric-card__value">{total}</span>
          </div>
          <div className="metric-card__subtitle">Consolidated profiles</div>
        </div>
      </div>

      {/* Card 2: Long-form Creators */}
      <div className="metric-card">
        <div className="metric-card__icon metric-card__icon--green">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        </div>
        <div className="metric-card__content">
          <div className="metric-card__title">Long-form Creators</div>
          <div className="metric-card__value-row">
            <span className="metric-card__value">{longformCount}</span>
            <span className="metric-card__badge">{longformPct}%</span>
          </div>
          <div className="metric-card__subtitle">≥80% YouTube long-form</div>
        </div>
      </div>

      {/* Card 3: Shorts / Reels */}
      <div className="metric-card">
        <div className="metric-card__icon metric-card__icon--purple">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
            <line x1="7" y1="2" x2="7" y2="22" />
            <line x1="17" y1="2" x2="17" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <line x1="2" y1="7" x2="7" y2="7" />
            <line x1="2" y1="17" x2="7" y2="17" />
            <line x1="17" y1="17" x2="22" y2="17" />
            <line x1="17" y1="7" x2="22" y2="7" />
          </svg>
        </div>
        <div className="metric-card__content">
          <div className="metric-card__title">Shorts / Reels</div>
          <div className="metric-card__value-row">
            <span className="metric-card__value">{shortformCount}</span>
            <span className="metric-card__badge">{shortformPct}%</span>
          </div>
          <div className="metric-card__subtitle">Shorts, Reels &amp; Slides</div>
        </div>
      </div>

      {/* Card 4: With Broker Assoc. */}
      <div className="metric-card">
        <div className="metric-card__icon metric-card__icon--orange">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="21" x2="21" y2="21" />
            <line x1="3" y1="10" x2="21" y2="10" />
            <polyline points="5 6 12 3 19 6" />
            <line x1="4" y1="10" x2="4" y2="21" />
            <line x1="20" y1="10" x2="20" y2="21" />
            <line x1="8" y1="14" x2="8" y2="17" />
            <line x1="12" y1="14" x2="12" y2="17" />
            <line x1="16" y1="14" x2="16" y2="17" />
          </svg>
        </div>
        <div className="metric-card__content">
          <div className="metric-card__title">With Broker Assoc.</div>
          <div className="metric-card__value-row">
            <span className="metric-card__value">{withBrokerCount}</span>
            <span className="metric-card__badge">{withBrokerPct}%</span>
          </div>
          <div className="metric-card__subtitle">Zerodha, AngelOne, Upstox, etc.</div>
        </div>
      </div>

      {/* Card 5: With Contact Info */}
      <div className="metric-card">
        <div className="metric-card__icon metric-card__icon--teal">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
            <polyline points="22,6 12,13 2,6" />
          </svg>
        </div>
        <div className="metric-card__content">
          <div className="metric-card__title">With Contact Info</div>
          <div className="metric-card__value-row">
            <span className="metric-card__value">{withContactCount}</span>
            <span className="metric-card__badge">{withContactPct}%</span>
          </div>
          <div className="metric-card__subtitle">Direct Email or Phone</div>
        </div>
      </div>
    </div>
  )
}
