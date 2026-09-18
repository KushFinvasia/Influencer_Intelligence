import React, { useCallback, useEffect, useRef, useState } from 'react'

// Initials-avatar palette, mirroring the table row treatment.
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
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function getInitials(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

function formatFollowers(value) {
  const n = Number(value) || 0
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export default function CreatorDrawer({ creator, onClose, onOpenCreator, onBack, canGoBack }) {
  const [isComposingEmail, setIsComposingEmail] = useState(false)
  const [emailSubject, setEmailSubject] = useState('')
  const [emailMessage, setEmailMessage] = useState('')
  const [emailStatus, setEmailStatus] = useState('idle') // idle, loading, confirm, success, error
  const [emailErrorMsg, setEmailErrorMsg] = useState('')

  // Similar creators
  const [similar, setSimilar] = useState([])
  const [similarStatus, setSimilarStatus] = useState('idle') // idle, loading, ready, error
  const [similarErrorMsg, setSimilarErrorMsg] = useState('')

  useEffect(() => {
    if (!creator) {
      setIsComposingEmail(false)
      setEmailStatus('idle')
      setEmailSubject('')
      setEmailMessage('')
      setEmailErrorMsg('')
    }
  }, [creator])

  // Results already fetched in this drawer session, keyed by creator id, so
  // stepping back to a creator restores their list instead of re-fetching.
  const similarCache = useRef(new Map())

  // Restore (or reset) recommendations when the drawer switches creator.
  useEffect(() => {
    const cached = similarCache.current.get(creator?.id)
    setSimilar(cached || [])
    setSimilarStatus(cached ? 'ready' : 'idle')
    setSimilarErrorMsg('')
  }, [creator?.id])

  const handleFindSimilar = useCallback(async () => {
    if (!creator) return
    setSimilarStatus('loading')
    setSimilarErrorMsg('')
    try {
      const res = await fetch(`/api/creators/${creator.id}/similar?limit=10`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
      const results = data.results || []
      similarCache.current.set(creator.id, results)
      setSimilar(results)
      setSimilarStatus('ready')
    } catch (err) {
      setSimilarStatus('error')
      setSimilarErrorMsg(err.message || 'Failed to load similar creators')
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
  const [headerGradStart, headerGradEnd] = getAvatarColors(creator.name)
  const identityTags = [creator.category, creator.language].filter(v => v && v !== '-')

  return (
    <>
      <div className="drawer-overlay open" onClick={onClose} />
      <div className="drawer open">
        <div className="drawer__header">
          {canGoBack && (
            <button
              className="drawer__back"
              onClick={onBack}
              title="Back to previous creator"
              aria-label="Back to previous creator"
            >
              ←
            </button>
          )}
          <div className="drawer__heading">
            <span
              className={`cell-platform cell-platform--${(creator.platform || 'youtube').toLowerCase()}`}
            >
              {creator.platform}
            </span>
            <span className="drawer__title">{creator.name || 'Creator Detail'}</span>
          </div>
          <button className="drawer__close" onClick={onClose} title="Close (Esc)" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="drawer__body">
          {/* Identity strip */}
          <div className="drawer__identity">
            <div
              className="drawer__identity-avatar"
              style={{
                background: `linear-gradient(135deg, ${headerGradStart}, ${headerGradEnd})`,
              }}
            >
              {getInitials(creator.name)}
            </div>
            <div className="drawer__identity-main">
              {identityTags.length > 0 ? (
                <div className="drawer__identity-tags">
                  {identityTags.map(tag => (
                    <span key={tag} className="drawer__identity-tag">{tag}</span>
                  ))}
                </div>
              ) : (
                <span className="drawer__identity-empty">Not classified yet</span>
              )}
            </div>
            <div className="drawer__keystats">
              <div className="drawer__keystat">
                <div className="drawer__keystat-value">{creator.followers || '-'}</div>
                <div className="drawer__keystat-label">Followers</div>
              </div>
              <div className="drawer__keystat">
                <div className="drawer__keystat-value">{creator.score || '-'}</div>
                <div className="drawer__keystat-label">Score</div>
              </div>
              <div className="drawer__keystat">
                <div className="drawer__keystat-value">{creator.bucket || '-'}</div>
                <div className="drawer__keystat-label">Tier</div>
              </div>
            </div>
          </div>

          {/* Overview Section */}
          <div className="drawer__section">
            <div className="drawer__section-title">Overview</div>
            <div className="drawer__row">
              <span className="drawer__label">Exact Followers</span>
              <span className="drawer__value">
                {creator.followers_raw ? Number(creator.followers_raw).toLocaleString() : '-'}
              </span>
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
            <div className="drawer__section drawer__section--wide">
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

          {/* Similar Creators */}
          <div className="drawer__section drawer__section--wide">
            <div className="drawer__section-title">Similar Creators</div>

            {similarStatus === 'idle' && (
              <>
                <div className="similar-creators__hint">
                  Find creators with a comparable category, audience size and
                  performance profile.
                </div>
                <button
                  className="btn-sm similar-creators__cta"
                  onClick={handleFindSimilar}
                >
                  ⌕ Find Similar Creators
                </button>
              </>
            )}

            {similarStatus === 'loading' && (
              <div className="similar-creators__loading">
                <span className="similar-creators__spinner" />
                Finding similar creators...
              </div>
            )}

            {similarStatus === 'error' && (
              <div className="similar-creators__error">
                <span>{similarErrorMsg}</span>
                <button className="btn-sm" onClick={handleFindSimilar}>
                  Retry
                </button>
              </div>
            )}

            {similarStatus === 'ready' && similar.length === 0 && (
              <div className="similar-creators__empty">
                No similar creators found for this profile.
              </div>
            )}

            {similarStatus === 'ready' && similar.length > 0 && (
              <div className="similar-creators__list">
                {similar.map((s) => {
                  const [gradStart, gradEnd] = getAvatarColors(s.name)
                  return (
                    <button
                      key={s.id}
                      className="similar-card"
                      onClick={() => onOpenCreator && onOpenCreator(s.id)}
                      title={`Open ${s.name}`}
                    >
                      <div className="similar-card__head">
                        <div
                          className="similar-card__avatar similar-card__avatar--initials"
                          style={{
                            background: `linear-gradient(135deg, ${gradStart}, ${gradEnd})`,
                          }}
                        >
                          {getInitials(s.name)}
                        </div>
                        <div className="similar-card__identity">
                          <div className="similar-card__name">{s.name}</div>
                          <div className="similar-card__subtitle">
                            {formatFollowers(s.followers)} followers
                          </div>
                          <div className="similar-card__meta">
                            {(s.platforms || []).map((p) => (
                              <span key={p} className="similar-card__tag">
                                {p}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="similar-card__similarity">
                          <div className="similar-card__similarity-value">
                            {Math.round(s.similarity_score)}%
                          </div>
                          <div className="similar-card__similarity-label">Match</div>
                        </div>
                      </div>

                      <div className="similar-card__stats">
                        <div className="similar-card__stat">
                          <span className="similar-card__stat-label">Category</span>
                          <span className="similar-card__stat-value">
                            {s.category || '-'}
                          </span>
                        </div>
                        <div className="similar-card__stat">
                          <span className="similar-card__stat-label">Language</span>
                          <span className="similar-card__stat-value">
                            {s.language || '-'}
                          </span>
                        </div>
                      </div>

                      {s.match_reasons && s.match_reasons.length > 0 && (
                        <div className="similar-card__reasons">
                          {s.match_reasons.map((r) => (
                            <span key={r} className="similar-card__reason">
                              {r}
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          {/* Email Composer */}
          {isComposingEmail && (
            <div className="email-composer drawer__section--wide">
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
