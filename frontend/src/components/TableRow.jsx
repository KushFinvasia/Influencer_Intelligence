import React from 'react'

// Color palettes for initials avatars
const AVATAR_COLORS = [
  ['#3B82F6', '#1D4ED8'],
  ['#10B981', '#047857'],
  ['#8B5CF6', '#6D28D9'],
  ['#F59E0B', '#D97706'],
  ['#EC4899', '#BE185D'],
  ['#06B6D4', '#0E7490'],
  ['#6366F1', '#4338CA'],
]

function getAvatarColors(name) {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const index = Math.abs(hash) % AVATAR_COLORS.length
  return AVATAR_COLORS[index]
}

function getInitials(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

function extractHandle(creator) {
  // 1. Try to extract clean @handle from the creator's own profile_url
  if (creator.profile_url) {
    try {
      const url = new URL(creator.profile_url)
      const pathname = url.pathname.replace(/^\/+/, '').replace(/\/+$/, '')

      // YouTube @handle: e.g. /@neerajjoshi
      if (pathname.startsWith('@')) {
        return pathname
      }
      // Instagram handle: e.g. instagram.com/mahendradogney
      if (url.hostname.includes('instagram.com') && pathname && !pathname.includes('/')) {
        return `@${pathname}`
      }
      // YouTube /c/ or /user/ custom URL: e.g. /c/MahendraDogney
      if (pathname.startsWith('c/') || pathname.startsWith('user/')) {
        return `@${pathname.split('/')[1]}`
      }
    } catch { /* ignore */ }
  }

  // 2. Derive a clean @handle from the creator's own name (e.g. "Dr. Mukul Agrawal : Stock Market Coach" -> "@mukulagrawal")
  if (creator.name) {
    let clean = creator.name
      .split(/[:|–-]/)[0] // Take part before colon or dash
      .replace(/^(Dr\.|CA|Coach|Prof\.)\s+/i, '') // Remove professional prefixes
      .replace(/\(.*?\)/g, '') // Remove parentheses e.g. (Telugu)
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '') // Only alphanumeric

    if (clean) return `@${clean}`
  }

  return '@creator'
}

export default function TableRow({
  creator,
  visibleColumns,
  isSelected,
  isChecked,
  onToggleCheck,
  onSelect,
  onPerfClick,
}) {
  const [gradStart, gradEnd] = getAvatarColors(creator.name)
  const initials = getInitials(creator.name)
  const handle = extractHandle(creator)
  const isYt = (creator.platform || 'youtube').toLowerCase() === 'youtube'

  // Is verified (score >= 40 or high follower)
  const isVerified = (creator.followers_raw && creator.followers_raw >= 300000) || parseFloat(creator.score) >= 40

  const renderCell = (colId) => {
    switch (colId) {
      case 'platform': {
        return (
          <div className="table-platform-icon" title={creator.platform || 'YouTube'}>
            {isYt ? (
              <svg width="22" height="16" viewBox="0 0 24 17" fill="none">
                <rect width="24" height="17" rx="4" fill="#FF0000" />
                <polygon points="9.5,4.5 16,8.5 9.5,12.5" fill="#FFFFFF" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <rect x="2" y="2" width="20" height="20" rx="5" fill="url(#ig-grad)" />
                <circle cx="12" cy="12" r="4.5" stroke="#FFF" strokeWidth="2" />
                <circle cx="18" cy="6" r="1.2" fill="#FFF" />
                <defs>
                  <linearGradient id="ig-grad" x1="2" y1="22" x2="22" y2="2" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#FED373" />
                    <stop offset="0.5" stopColor="#F15245" />
                    <stop offset="1" stopColor="#D92E7F" />
                  </linearGradient>
                </defs>
              </svg>
            )}
          </div>
        )
      }

      case 'name': {
        return (
          <div className="creator-cell" onClick={(e) => { e.stopPropagation(); onSelect(creator); }}>
            <div className="creator-info">
              <div className="creator-name-row">
                <span className="creator-name">{creator.name || 'N/A'}</span>
                {isVerified && (
                  <svg className="verified-badge" width="14" height="14" viewBox="0 0 24 24" fill="#3B82F6" title="Verified Influencer">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                  </svg>
                )}
              </div>
              <div className="creator-handle">{handle}</div>
            </div>
          </div>
        )
      }

      case 'followers': {
        return (
          <div className="followers-cell">
            <div className="followers-count">{creator.followers || '-'}</div>
            <div className="tier-badge">{creator.bucket || '< 10K'}</div>
          </div>
        )
      }

      case 'format': {
        const label = creator.format_label || creator.content_format || '-'
        return (
          <span className="format-badge" title={creator.format_breakdown || label}>
            {label}
          </span>
        )
      }

      case 'performance': {
        if (!creator.posts_analyzed || creator.posts_analyzed === 0) {
          return <span className="cell-muted">—</span>
        }
        return (
          <div
            className="perf-cell-grid"
            onClick={(e) => {
              e.stopPropagation()
              onPerfClick(e, creator)
            }}
            title="Click for full breakdown"
          >
            <div className="perf-icons-row">
              <span className="perf-metric-item">
                <span className="perf-icon">👁</span>
                <span className="perf-val">{creator.avg_views || '-'}</span>
              </span>
              <span className="perf-metric-item">
                <span className="perf-icon">❤️</span>
                <span className="perf-val">{creator.avg_likes || '-'}</span>
              </span>
              <span className="perf-metric-item">
                <span className="perf-icon">💬</span>
                <span className="perf-val">{creator.avg_comments || '-'}</span>
              </span>
            </div>
            <div className="perf-sample-text">
              {isYt
                ? `20 videos analyzed (${creator.engagement_eligible_videos || 0} eligible)`
                : `${creator.posts_analyzed} posts (${creator.views_analyzed || 0} eligible)`}
            </div>
          </div>
        )
      }

      case 'engagement': {
        const rate = parseFloat(creator.engagement_rate)
        let colorClass = 'eng--low'
        if (!isNaN(rate)) {
          if (rate >= 5.0) colorClass = 'eng--high'
          else if (rate >= 2.0) colorClass = 'eng--medium'
        }
        return (
          <span className={`eng-rate ${colorClass}`}>
            {creator.engagement_rate || '—'}
          </span>
        )
      }

      case 'email': {
        if (!creator.email || creator.email === '-') {
          return <span className="cell-muted">—</span>
        }
        return (
          <a
            href={`mailto:${creator.email}`}
            className="email-link"
            onClick={(e) => e.stopPropagation()}
            title={creator.email}
          >
            {creator.email}
          </a>
        )
      }

      case 'phone': {
        if (!creator.phone || creator.phone === '-') {
          return <span className="cell-muted">—</span>
        }
        return (
          <a
            href={`tel:${creator.phone}`}
            className="phone-link"
            onClick={(e) => e.stopPropagation()}
            title={creator.phone}
          >
            {creator.phone}
          </a>
        )
      }

      case 'category': {
        if (!creator.category || creator.category === '-') {
          return <span className="cell-muted">—</span>
        }
        return <span className="category-badge">{creator.category}</span>
      }

      case 'language': {
        return <span className="language-text">{creator.language && creator.language !== '-' ? creator.language : 'Hindi'}</span>
      }

      case 'broker': {
        if (!creator.broker || creator.broker === '-') {
          return <span className="cell-muted">—</span>
        }
        return <span className="broker-text">{creator.broker}</span>
      }

      case 'social_handles': {
        if (!creator.social_handles || creator.social_handles === '-') {
          return <span className="cell-muted">—</span>
        }
        const handles = creator.social_handles.split(',').map(s => s.trim()).filter(Boolean)
        return (
          <div className="socials-cell" style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            {handles.map((h, i) => (
              <span key={i} className="social-badge" style={{ backgroundColor: 'var(--bg-hover)', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                {h}
              </span>
            ))}
          </div>
        )
      }

      case 'website': {
        if (!creator.website || creator.website === '-') {
          return <span className="cell-muted">—</span>
        }
        return (
          <a
            href={creator.website.startsWith('http') ? creator.website : `https://${creator.website}`}
            target="_blank"
            rel="noopener noreferrer"
            className="website-link"
            onClick={(e) => e.stopPropagation()}
          >
            {creator.website.replace(/^https?:\/\/(www\.)?/, '').slice(0, 20)} ↗
          </a>
        )
      }

      default:
        return <span>—</span>
    }
  }

  return (
    <tr
      className={`table-row ${isSelected ? 'table-row--selected' : ''}`}
      onClick={() => onSelect(creator)}
    >
      {/* Selection Checkbox */}
      <td className="td-checkbox" onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          className="table-checkbox"
          checked={isChecked}
          onChange={() => onToggleCheck(creator.id)}
        />
      </td>

      {visibleColumns.map(col => (
        <td key={col.id} className={`td-cell td-cell--${col.id}`}>
          {renderCell(col.id)}
        </td>
      ))}

      {/* Row Action Menu */}
      <td className="td-action" onClick={(e) => { e.stopPropagation(); onSelect(creator); }}>
        <button className="row-action-btn" title="View details">
          ⋮
        </button>
      </td>
    </tr>
  )
}
