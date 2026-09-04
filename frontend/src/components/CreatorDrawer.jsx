import React, { useEffect, useState } from 'react'

export default function CreatorDrawer({ creator, onClose }) {
  const [isComposingEmail, setIsComposingEmail] = useState(false)
  const [emailSubject, setEmailSubject] = useState('')
  const [emailMessage, setEmailMessage] = useState('')
  const [emailStatus, setEmailStatus] = useState('idle') // idle, loading, confirm, success, error
  const [emailErrorMsg, setEmailErrorMsg] = useState('')

  useEffect(() => {
    if (!creator) {
      setIsComposingEmail(false)
      setEmailStatus('idle')
      setEmailSubject('')
      setEmailMessage('')
      setEmailErrorMsg('')
    }
  }, [creator])

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const handleSendEmail = async () => {
    setEmailStatus('loading')
    setEmailErrorMsg('')
    try {
      const res = await fetch(`/api/creators/${creator.id}/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: emailSubject, message: emailMessage })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to send email')
      setEmailStatus('success')
    } catch (err) {
      setEmailStatus('error')
      setEmailErrorMsg(err.message)
    }
  }

  if (!creator) return null

  const isYt = creator.platform?.toLowerCase() === 'youtube'

  return (
    <>
      <div className="drawer-overlay open" onClick={onClose} />
      <div className="drawer open">
        <div className="drawer__header">
          <div>
            <span
              className={`cell-platform cell-platform--${(creator.platform || 'youtube').toLowerCase()}`}
              style={{ marginRight: '6px' }}
            >
              {creator.platform}
            </span>
            <span className="drawer__title">{creator.name || 'Creator Detail'}</span>
          </div>
          <button className="drawer__close" onClick={onClose} title="Close drawer (Esc)">
            ✕
          </button>
        </div>

        <div className="drawer__body">
          {/* Overview Section */}
          <div className="drawer__section">
            <div className="drawer__section-title">Overview</div>
            <div className="drawer__row">
              <span className="drawer__label">Followers</span>
              <span className="drawer__value">
                <strong>{creator.followers || '-'}</strong>
                {creator.followers_raw ? ` (${Number(creator.followers_raw).toLocaleString()})` : ''}
              </span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Tier Bucket</span>
              <span className="drawer__value">{creator.bucket || '-'}</span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Influencer Score</span>
              <span className="drawer__value"><strong>{creator.score || '-'}</strong></span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Content Format</span>
              <span className="drawer__value">
                {creator.format_label || creator.content_format || '-'}
              </span>
            </div>
            {creator.format_breakdown && (
              <div className="drawer__row">
                <span className="drawer__label">Format Detail</span>
                <span className="drawer__value" style={{ fontSize: '11px', color: 'var(--text-2)' }}>
                  {creator.format_breakdown}
                </span>
              </div>
            )}
            {creator.profile_url && (
              <div className="drawer__row">
                <span className="drawer__label">Platform Link</span>
                <span className="drawer__value">
                  <a href={creator.profile_url} target="_blank" rel="noopener noreferrer">
                    Open Profile ↗
                  </a>
                </span>
              </div>
            )}
          </div>

          {/* Performance Analytics Section */}
          <div className="drawer__section">
            <div className="drawer__section-title">Performance Analytics</div>
            {creator.posts_analyzed > 0 ? (
              <>
                <div className="drawer__row">
                  <span className="drawer__label">Engagement Rate</span>
                  <span className="drawer__value">
                    <strong style={{ color: 'var(--accent)' }}>{creator.engagement_rate || '-'}</strong>
                  </span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Average Views</span>
                  <span className="drawer__value">{creator.avg_views || '-'}</span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Median Views</span>
                  <span className="drawer__value">{creator.median_views || '-'}</span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Average Likes</span>
                  <span className="drawer__value">{creator.avg_likes || '-'}</span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Median Likes</span>
                  <span className="drawer__value">{creator.median_likes || '-'}</span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Average Comments</span>
                  <span className="drawer__value">{creator.avg_comments || '-'}</span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Median Comments</span>
                  <span className="drawer__value">{creator.median_comments || '-'}</span>
                </div>
                <div className="drawer__row">
                  <span className="drawer__label">Sample Analyzed</span>
                  <span className="drawer__value" style={{ fontSize: '11px' }}>
                    {isYt
                      ? `${creator.posts_analyzed} videos (${creator.engagement_eligible_videos || 0} eligible for eng.)`
                      : `${creator.posts_analyzed} posts (${creator.views_analyzed || 0} videos)`}
                  </span>
                </div>
                {creator.metrics_calculated_at && creator.metrics_calculated_at !== '-' && (
                  <div className="drawer__row">
                    <span className="drawer__label">Calculated At</span>
                    <span className="drawer__value" style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                      {creator.metrics_calculated_at}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: 'var(--text-3)', fontSize: '12px', padding: '6px 0' }}>
                No performance snapshot available yet.
              </div>
            )}
          </div>

          {/* Contact Details */}
          <div className="drawer__section">
            <div className="drawer__section-title">Contact Information</div>
            <div className="drawer__row">
              <span className="drawer__label">Email</span>
              <span className="drawer__value" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {creator.email && creator.email !== '-' ? (
                  <>
                    <a href={`mailto:${creator.email}`}>{creator.email}</a>
                    <button 
                      className="btn-sm" 
                      onClick={() => { setIsComposingEmail(true); setEmailStatus('idle'); }}
                    >
                      ✉ Send Email
                    </button>
                  </>
                ) : (
                  <span className="cell-muted">-</span>
                )}
              </span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Phone</span>
              <span className="drawer__value">
                {creator.phone && creator.phone !== '-' ? (
                  <a href={`tel:${creator.phone}`}>{creator.phone}</a>
                ) : (
                  <span className="cell-muted">-</span>
                )}
              </span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Website</span>
              <span className="drawer__value">
                {creator.website && creator.website !== '-' ? (
                  <a href={creator.website.startsWith('http') ? creator.website : `https://${creator.website}`} target="_blank" rel="noopener noreferrer">
                    {creator.website} ↗
                  </a>
                ) : (
                  <span className="cell-muted">-</span>
                )}
              </span>
            </div>
          </div>

          {/* Classification & Associations */}
          <div className="drawer__section">
            <div className="drawer__section-title">Classification & Brokerage</div>
            <div className="drawer__row">
              <span className="drawer__label">Primary Category</span>
              <span className="drawer__value">{creator.category || '-'}</span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Language</span>
              <span className="drawer__value">{creator.language || '-'}</span>
            </div>
            <div className="drawer__row">
              <span className="drawer__label">Associated Brokers</span>
              <span className="drawer__value">
                {creator.broker && creator.broker !== '-' ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', justifyContent: 'flex-end' }}>
                    {creator.broker.split(',').map(b => (
                      <span
                        key={b}
                        style={{
                          background: 'var(--surface-2)',
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '11px',
                          border: '1px solid var(--border)',
                        }}
                      >
                        {b.trim()}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="cell-muted">-</span>
                )}
              </span>
            </div>
          </div>

          {/* Social Profiles & Handles */}
          {creator.structured_socials && creator.structured_socials.length > 0 && (
            <div className="drawer__section">
              <div className="drawer__section-title">Social Profiles & Channels</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                {creator.structured_socials.map((s, idx) => (
                  <div key={idx} className="drawer__row">
                    <span className="drawer__label" style={{ textTransform: 'capitalize' }}>
                      {s.platform}
                    </span>
                    <span className="drawer__value">
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        {s.label || s.url} ↗
                      </a>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Email Composer */}
          {isComposingEmail && (
            <div className="email-composer">
              <div className="email-composer__header">
                <strong>Compose Email to {creator.name}</strong>
                <button className="email-composer__close" onClick={() => setIsComposingEmail(false)}>✕</button>
              </div>
              <div className="email-composer__body">
                <div className="drawer__row" style={{ marginBottom: '12px' }}>
                  <span className="drawer__label">To:</span>
                  <span className="drawer__value">{creator.email}</span>
                </div>
                <div className="email-composer__field">
                  <input 
                    type="text" 
                    placeholder="Subject" 
                    value={emailSubject}
                    onChange={(e) => setEmailSubject(e.target.value)}
                    disabled={emailStatus === 'loading' || emailStatus === 'success'}
                  />
                </div>
                <div className="email-composer__field">
                  <textarea 
                    placeholder="Message..." 
                    rows={5}
                    value={emailMessage}
                    onChange={(e) => setEmailMessage(e.target.value)}
                    disabled={emailStatus === 'loading' || emailStatus === 'success'}
                  />
                </div>

                {emailStatus === 'error' && (
                  <div className="email-composer__error">
                    {emailErrorMsg}
                  </div>
                )}
                {emailStatus === 'success' && (
                  <div className="email-composer__success">
                    Email sent successfully!
                  </div>
                )}

                {(emailStatus === 'idle' || emailStatus === 'error') && (
                  <div className="email-composer__actions">
                    <button 
                      className="btn-primary" 
                      disabled={!emailSubject || !emailMessage}
                      onClick={() => setEmailStatus('confirm')}
                    >
                      Review & Send
                    </button>
                  </div>
                )}

                {emailStatus === 'confirm' && (
                  <div className="email-composer__confirm">
                    <p>Are you sure you want to send this email to <strong>{creator.email}</strong>?</p>
                    <div className="email-composer__actions">
                      <button className="btn-secondary" onClick={() => setEmailStatus('idle')}>Cancel</button>
                      <button className="btn-primary" onClick={handleSendEmail}>Confirm Send</button>
                    </div>
                  </div>
                )}

                {emailStatus === 'loading' && (
                  <div className="email-composer__loading">
                    Sending...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
