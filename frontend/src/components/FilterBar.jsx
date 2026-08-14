import React, { useState } from 'react'

export default function FilterBar({ filters, onChange, options }) {
  const [showMoreFilters, setShowMoreFilters] = useState(false)

  const set = (key, val) => onChange({ ...filters, [key]: val || '' })

  const hasExtraFilters = Boolean(filters.engagement || filters.contact || filters.language)

  return (
    <div className="filter-section">
      <div className="filter-bar-row">
        {/* Search Input */}
        <div className="filter-search-box">
          <svg className="filter-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            className="filter-search-input"
            placeholder="Search name, handle, category, language, broker, website..."
            value={filters.search || ''}
            onChange={e => set('search', e.target.value)}
          />
          {filters.search && (
            <button className="filter-search-clear" onClick={() => set('search', '')}>
              ✕
            </button>
          )}
        </div>

        {/* Dropdown Filters */}
        <div className="filter-select-wrapper">
          <select
            className="filter-select"
            value={filters.format || ''}
            onChange={e => set('format', e.target.value)}
          >
            <option value="">All Formats</option>
            <option value="longform">🎬 Longform (YouTube)</option>
            <option value="shortform">📱 Short-Form / Reels</option>
            <option value="hybrid">⚖️ Hybrid / Mixed</option>
            <option value="carousels">📑 Educational Carousels</option>
            <option value="images">🖼️ Image Posts</option>
          </select>
        </div>

        <div className="filter-select-wrapper">
          <select
            className="filter-select"
            value={filters.broker || ''}
            onChange={e => set('broker', e.target.value)}
          >
            <option value="">All Brokers</option>
            {options.brokers.map(b => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        <div className="filter-select-wrapper">
          <select
            className="filter-select"
            value={filters.category || ''}
            onChange={e => set('category', e.target.value)}
          >
            <option value="">All Categories</option>
            {options.categories.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className="filter-select-wrapper">
          <select
            className="filter-select"
            value={filters.tier || ''}
            onChange={e => set('tier', e.target.value)}
          >
            <option value="">All Followers Tier</option>
            <option value="1M+">1M+ Followers</option>
            <option value="300K–1M">300K–1M Followers</option>
            <option value="10K–300K">10K–300K Followers</option>
            <option value="< 10K">&lt; 10K Followers</option>
          </select>
        </div>

        <div className="filter-select-wrapper">
          <select
            className="filter-select"
            value={filters.platform || ''}
            onChange={e => set('platform', e.target.value)}
          >
            <option value="">All Platforms</option>
            <option value="youtube">YouTube</option>
            <option value="instagram">Instagram</option>
          </select>
        </div>

        {/* More Filters Button */}
        <button
          className={`btn btn--outline filter-more-btn ${showMoreFilters || hasExtraFilters ? 'filter-more-btn--active' : ''}`}
          onClick={() => setShowMoreFilters(prev => !prev)}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          <span>More Filters</span>
          {hasExtraFilters && <span className="filter-dot" />}
        </button>
      </div>

      {/* Extra Filters Row (collapsible) */}
      {showMoreFilters && (
        <div className="filter-extra-row">
          <div className="filter-select-wrapper">
            <select
              className="filter-select"
              value={filters.language || ''}
              onChange={e => set('language', e.target.value)}
            >
              <option value="">All Languages</option>
              {options.languages.map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>

          <div className="filter-select-wrapper">
            <select
              className="filter-select"
              value={filters.engagement || ''}
              onChange={e => set('engagement', e.target.value)}
            >
              <option value="">All Engagement Rates</option>
              <option value="high">High Engagement (≥ 5%)</option>
              <option value="medium">Medium Engagement (2% – 5%)</option>
              <option value="low">Low Engagement (&lt; 2%)</option>
            </select>
          </div>

          <div className="filter-select-wrapper">
            <select
              className="filter-select"
              value={filters.contact || ''}
              onChange={e => set('contact', e.target.value)}
            >
              <option value="">All Contact Statuses</option>
              <option value="any">Has Any Contact</option>
              <option value="email">Has Email</option>
              <option value="phone">Has Phone</option>
              <option value="both">Has Both Email &amp; Phone</option>
              <option value="none">No Direct Contact</option>
            </select>
          </div>
        </div>
      )}
    </div>
  )
}
