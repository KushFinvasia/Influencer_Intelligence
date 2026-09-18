import React from 'react'

/**
 * Social / contact links rendered as platform icons.
 *
 * The platform is resolved from the stored `platform` field first and from the
 * URL host as a fallback, so a link saved as a generic "website" that actually
 * points at Instagram still gets the right icon. Nothing is keyed per creator.
 */

// 24x24 single-path glyphs, drawn with currentColor.
const PLATFORMS = {
  youtube: {
    label: 'YouTube',
    color: '#FF0000',
    path: 'M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2 31.3 31.3 0 0 0 0 12a31.3 31.3 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31.3 31.3 0 0 0 24 12a31.3 31.3 0 0 0-.5-5.8zM9.5 15.6V8.4l6.3 3.6-6.3 3.6z',
  },
  instagram: {
    label: 'Instagram',
    color: '#E4405F',
    path: 'M12 2.2c3.2 0 3.6 0 4.9.1 1.2.1 1.8.2 2.2.4.6.2 1 .5 1.4.9.4.4.7.8.9 1.4.2.4.3 1 .4 2.2.1 1.3.1 1.7.1 4.9s0 3.6-.1 4.9c-.1 1.2-.2 1.8-.4 2.2-.2.6-.5 1-.9 1.4-.4.4-.8.7-1.4.9-.4.2-1 .3-2.2.4-1.3.1-1.7.1-4.9.1s-3.6 0-4.9-.1c-1.2-.1-1.8-.2-2.2-.4-.6-.2-1-.5-1.4-.9-.4-.4-.7-.8-.9-1.4-.2-.4-.3-1-.4-2.2-.1-1.3-.1-1.7-.1-4.9s0-3.6.1-4.9c.1-1.2.2-1.8.4-2.2.2-.6.5-1 .9-1.4.4-.4.8-.7 1.4-.9.4-.2 1-.3 2.2-.4 1.3-.1 1.7-.1 4.9-.1zm0 3.4A6.4 6.4 0 1 0 18.4 12 6.4 6.4 0 0 0 12 5.6zm0 10.5A4.1 4.1 0 1 1 16.1 12 4.1 4.1 0 0 1 12 16.1zm6.7-10.8a1.5 1.5 0 1 1-1.5-1.5 1.5 1.5 0 0 1 1.5 1.5z',
  },
  whatsapp: {
    label: 'WhatsApp',
    color: '#25D366',
    path: 'M17.5 14.4c-.3-.1-1.8-.9-2-1s-.5-.1-.7.1-.8 1-.9 1.2-.3.2-.6.1a8.2 8.2 0 0 1-2.4-1.5 9 9 0 0 1-1.7-2.1c-.2-.3 0-.4.1-.6l.5-.5a2 2 0 0 0 .3-.5.5.5 0 0 0 0-.5c0-.1-.7-1.6-.9-2.2s-.5-.5-.7-.5h-.6a1.1 1.1 0 0 0-.8.4 3.4 3.4 0 0 0-1 2.5 5.8 5.8 0 0 0 1.2 3.1 13.4 13.4 0 0 0 5.2 4.6c.7.3 1.3.5 1.7.6a4.2 4.2 0 0 0 1.9.1 3.1 3.1 0 0 0 2-1.4 2.5 2.5 0 0 0 .2-1.4c-.1-.1-.3-.2-.6-.3zM12 0a12 12 0 0 0-10.3 18L0 24l6.2-1.6A12 12 0 1 0 12 0zm0 22a10 10 0 0 1-5.1-1.4l-.4-.2-3.8 1 1-3.7-.2-.4A10 10 0 1 1 12 22z',
  },
  telegram: {
    label: 'Telegram',
    color: '#26A5E4',
    path: 'M12 0a12 12 0 1 0 12 12A12 12 0 0 0 12 0zm5.6 8.2-1.9 8.8c-.1.6-.5.8-1 .5l-2.8-2.1-1.4 1.3c-.2.2-.3.3-.6.3l.2-3 5.4-4.9c.2-.2 0-.3-.4-.1L8.5 12.2 5.8 11.3c-.6-.2-.6-.6.1-.9l10.6-4.1c.5-.2.9.1.7 1z',
  },
  linkedin: {
    label: 'LinkedIn',
    color: '#0A66C2',
    path: 'M20.4 20.5h-3.6v-5.6c0-1.3 0-3-1.9-3s-2.1 1.4-2.1 2.9v5.7H9.4V9h3.4v1.6h.1a3.8 3.8 0 0 1 3.4-1.9c3.6 0 4.3 2.4 4.3 5.5v6.3zM5.3 7.4a2.1 2.1 0 1 1 2.1-2.1 2.1 2.1 0 0 1-2.1 2.1zm1.8 13.1H3.5V9h3.6v11.5zM22.2 0H1.8A1.8 1.8 0 0 0 0 1.8v20.4A1.8 1.8 0 0 0 1.8 24h20.4a1.8 1.8 0 0 0 1.8-1.8V1.8A1.8 1.8 0 0 0 22.2 0z',
  },
  twitter: {
    label: 'X (Twitter)',
    color: null, // inherits text colour so it stays legible in both themes
    path: 'M18.9 2H22l-7 8 8.2 12h-6.4l-5-7.3L5.9 22H2.8l7.5-8.6L2.4 2h6.6l4.5 6.7L18.9 2zm-1.1 18h1.7L7.3 3.8H5.5L17.8 20z',
  },
  facebook: {
    label: 'Facebook',
    color: '#1877F2',
    path: 'M24 12a12 12 0 1 0-13.9 11.9v-8.4H7.1V12h3V9.4c0-3 1.8-4.7 4.5-4.7 1.3 0 2.7.2 2.7.2v2.9h-1.5c-1.5 0-2 .9-2 1.9V12h3.3l-.5 3.5h-2.8v8.4A12 12 0 0 0 24 12z',
  },
  discord: {
    label: 'Discord',
    color: '#5865F2',
    path: 'M20.3 4.4A19.8 19.8 0 0 0 15.4 3l-.2.4a13.3 13.3 0 0 1 4.3 2.2 15.6 15.6 0 0 0-11-1.3A15 15 0 0 0 5 5.6a13.5 13.5 0 0 1 4.4-2.2L9.2 3a19.8 19.8 0 0 0-4.9 1.4C1.3 8.9.5 13.2.9 17.5a19.9 19.9 0 0 0 6 3l1.2-1.7a12.9 12.9 0 0 1-2-1l.5-.4a14.2 14.2 0 0 0 12.2 0l.5.4a12.9 12.9 0 0 1-2 1l1.2 1.7a19.9 19.9 0 0 0 6-3c.5-5-.8-9.3-4.2-13.1zM8.3 15c-1.2 0-2.1-1.1-2.1-2.4S7.1 10.2 8.3 10.2s2.2 1.1 2.1 2.4S9.5 15 8.3 15zm7.4 0c-1.2 0-2.1-1.1-2.1-2.4s.9-2.4 2.1-2.4 2.2 1.1 2.1 2.4S16.9 15 15.7 15z',
  },
  linktree: {
    label: 'Linktree',
    color: '#43E660',
    path: 'M13.7 2v5.5l3.9-3.9 2.2 2.2-3.9 3.9H21v3.1h-5.1l3.9 3.9-2.2 2.2-5.6-5.6-5.6 5.6-2.2-2.2 3.9-3.9H3v-3.1h5.1L4.2 5.8l2.2-2.2 3.9 3.9V2zM10.3 16.3h3.4V22h-3.4z',
  },
  email: {
    label: 'Email',
    color: null,
    path: 'M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4-8 5-8-5V6l8 5 8-5z',
  },
  phone: {
    label: 'Phone',
    color: null,
    path: 'M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.2 11.4 11.4 0 0 0 3.6.6 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1 11.4 11.4 0 0 0 .6 3.6 1 1 0 0 1-.2 1z',
  },
  website: {
    label: 'Website',
    color: null,
    path: 'M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm7.9 9h-3.3a15.6 15.6 0 0 0-1.2-5.4A8 8 0 0 1 19.9 11zM12 4c.8 1.2 1.9 3.4 2.2 7H9.8C10.1 7.4 11.2 5.2 12 4zM4.1 13h3.3a15.6 15.6 0 0 0 1.2 5.4A8 8 0 0 1 4.1 13zm3.3-2H4.1a8 8 0 0 1 4.5-5.4A15.6 15.6 0 0 0 7.4 11zM12 20c-.8-1.2-1.9-3.4-2.2-7h4.4c-.3 3.6-1.4 5.8-2.2 7zm3.4-1.6a15.6 15.6 0 0 0 1.2-5.4h3.3a8 8 0 0 1-4.5 5.4z',
  },
}

// Registrable domain -> platform key.
const HOST_MAP = {
  'instagram.com': 'instagram',
  'youtube.com': 'youtube',
  'youtu.be': 'youtube',
  't.me': 'telegram',
  'telegram.me': 'telegram',
  'telegram.org': 'telegram',
  'whatsapp.com': 'whatsapp',
  'wa.me': 'whatsapp',
  'linkedin.com': 'linkedin',
  'twitter.com': 'twitter',
  'x.com': 'twitter',
  'facebook.com': 'facebook',
  'fb.com': 'facebook',
  'fb.me': 'facebook',
  'discord.gg': 'discord',
  'discord.com': 'discord',
  'linktr.ee': 'linktree',
}

/**
 * Host of a URL, without "www.".
 *
 * Matching must happen on the host, not the raw string: "coindcx.com" contains
 * "x.com" as a substring and would otherwise be mistaken for Twitter/X.
 */
function hostOf(url) {
  const value = String(url || '').trim()
  if (!value) return ''
  try {
    const withScheme = /^https?:\/\//i.test(value) ? value : `https://${value}`
    return new URL(withScheme).hostname.toLowerCase().replace(/^www\./, '')
  } catch {
    return ''
  }
}

/** Resolve a link to a platform key, preferring the stored type over the URL. */
function detectPlatform(platform, url) {
  const key = String(platform || '').trim().toLowerCase()
  if (key && PLATFORMS[key] && key !== 'website') {
    return key
  }

  // A stored "website" may still point at a known platform — check the host.
  const host = hostOf(url)
  if (host) {
    if (HOST_MAP[host]) return HOST_MAP[host]
    for (const domain of Object.keys(HOST_MAP)) {
      if (host.endsWith(`.${domain}`)) return HOST_MAP[domain]
    }
  }

  if (key === 'website') return 'website'
  if (key === 'email' || (!host && String(url || '').includes('@'))) return 'email'
  return 'website'
}

/** Build a usable href for the platform (mailto/tel/https). */
function buildHref(key, url) {
  const value = String(url || '').trim()
  if (!value) return null
  if (key === 'email') return value.startsWith('mailto:') ? value : `mailto:${value}`
  if (key === 'phone') return value.startsWith('tel:') ? value : `tel:${value}`
  if (/^https?:\/\//i.test(value)) return value
  return `https://${value}`
}

function SocialIcon({ name, href, label, color }) {
  const def = PLATFORMS[name] || PLATFORMS.website
  return (
    <a
      className="social-icon"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={label}
      aria-label={label}
      onClick={(e) => e.stopPropagation()}
      style={color ? { color } : undefined}
    >
      <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
        <path d={def.path} />
      </svg>
    </a>
  )
}

/**
 * Renders a creator's social/contact links as icons.
 * Links without a usable URL are skipped rather than shown as empty icons.
 */
export default function SocialIconLinks({ creator, maxVisible = 5 }) {
  const links = []
  const seen = new Set()

  const push = (platform, url) => {
    const key = detectPlatform(platform, url)
    const href = buildHref(key, url)
    if (!href) return
    const dedupeKey = href.toLowerCase()
    if (seen.has(dedupeKey)) return
    seen.add(dedupeKey)
    const def = PLATFORMS[key] || PLATFORMS.website
    links.push({ key, href, label: def.label, color: def.color })
  }

  // The creator's own channel first, then their stored social/contact links.
  if (creator.profile_url) push(creator.platform, creator.profile_url)
  for (const social of creator.structured_socials || []) {
    push(social.platform, social.url || social.value)
  }

  if (links.length === 0) return <span className="cell-muted">—</span>

  const visible = links.slice(0, maxVisible)
  const overflow = links.slice(maxVisible)

  return (
    <div className="socials-cell">
      {visible.map((link, i) => (
        <SocialIcon
          key={`${link.href}-${i}`}
          name={link.key}
          href={link.href}
          label={link.label}
          color={link.color}
        />
      ))}
      {overflow.length > 0 && (
        <span
          className="social-more"
          title={overflow.map(l => `${l.label}: ${l.href}`).join('\n')}
        >
          +{overflow.length}
        </span>
      )}
    </div>
  )
}
