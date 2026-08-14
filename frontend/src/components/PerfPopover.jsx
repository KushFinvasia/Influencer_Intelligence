import React, { useEffect, useRef } from 'react'

export default function PerfPopover({ data, position, onClose }) {
  const popoverRef = useRef(null)

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    const handleClickOutside = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('mousedown', handleClickOutside)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('mousedown', handleClickOutside)
    }
  }, [onClose])

  if (!data) return null

  // Ensure popover does not spill out of the viewport
  const top = Math.min(position.y + 10, window.innerHeight - 250)
  const left = Math.min(position.x - 100, window.innerWidth - 280)

  const isYt = data.platform?.toLowerCase() === 'youtube'

  return (
    <div
      ref={popoverRef}
      className="perf-popover"
      style={{
        top: `${Math.max(10, top)}px`,
        left: `${Math.max(10, left)}px`,
      }}
    >
      <div className="perf-popover__title">
        {data.name} — Performance Breakdown
      </div>

      <div className="perf-popover__row">
        <span className="perf-popover__label">Avg Views:</span>
        <span className="perf-popover__value">{data.avg_views || '-'}</span>
      </div>
      <div className="perf-popover__row">
        <span className="perf-popover__label">Median Views:</span>
        <span className="perf-popover__value">{data.median_views || '-'}</span>
      </div>
      <div className="perf-popover__row">
        <span className="perf-popover__label">Avg Likes:</span>
        <span className="perf-popover__value">{data.avg_likes || '-'}</span>
      </div>
      <div className="perf-popover__row">
        <span className="perf-popover__label">Median Likes:</span>
        <span className="perf-popover__value">{data.median_likes || '-'}</span>
      </div>
      <div className="perf-popover__row">
        <span className="perf-popover__label">Avg Comments:</span>
        <span className="perf-popover__value">{data.avg_comments || '-'}</span>
      </div>
      <div className="perf-popover__row">
        <span className="perf-popover__label">Median Comments:</span>
        <span className="perf-popover__value">{data.median_comments || '-'}</span>
      </div>
      <div className="perf-popover__row">
        <span className="perf-popover__label">Engagement Rate:</span>
        <span className="perf-popover__value" style={{ color: 'var(--accent)' }}>
          {data.engagement_rate || '-'}
        </span>
      </div>

      <div
        style={{
          marginTop: '8px',
          paddingTop: '6px',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '10.5px',
          color: 'var(--text-3)',
        }}
      >
        <div>
          {isYt
            ? `Analyzed ${data.posts_analyzed} videos (${data.engagement_eligible_videos || 0} eligible)`
            : `Analyzed ${data.posts_analyzed} posts (${data.views_analyzed || 0} videos)`}
        </div>
        {data.metrics_calculated_at && data.metrics_calculated_at !== '-' && (
          <div>Snapshot: {data.metrics_calculated_at}</div>
        )}
      </div>
    </div>
  )
}
