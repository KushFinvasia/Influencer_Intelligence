import React from 'react'

export default function EmptyState({ type, message, onRetry, onClearFilters }) {
  if (type === 'loading') {
    return (
      <div style={{ padding: '16px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
        {[...Array(8)].map((_, i) => (
          <div key={i} className="skeleton-row">
            <div className="skeleton-cell" style={{ width: '80px' }} />
            <div className="skeleton-cell" style={{ width: '180px' }} />
            <div className="skeleton-cell" style={{ width: '90px' }} />
            <div className="skeleton-cell" style={{ width: '70px' }} />
            <div className="skeleton-cell" style={{ width: '110px' }} />
            <div className="skeleton-cell" style={{ width: '140px' }} />
            <div className="skeleton-cell" style={{ width: '70px' }} />
            <div className="skeleton-cell" style={{ width: '160px' }} />
          </div>
        ))}
      </div>
    )
  }

  if (type === 'error') {
    return (
      <div className="state-container">
        <div style={{ fontSize: '24px' }}>⚠️</div>
        <div className="state-container__text">
          Failed to load creators: <strong>{message || 'Unknown error'}</strong>
        </div>
        {onRetry && (
          <button className="state-container__btn" onClick={onRetry}>
            ↻ Try Again
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="state-container">
      <div style={{ fontSize: '24px' }}>🔍</div>
      <div className="state-container__text">
        No creators match your current search and filter criteria.
      </div>
      {onClearFilters && (
        <button className="state-container__btn" onClick={onClearFilters}>
          Clear All Filters
        </button>
      )}
    </div>
  )
}
