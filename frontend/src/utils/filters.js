/** Filter logic for creator data. */

const SEARCH_KEYS = [
  'name',
  'email',
  'phone',
  'category',
  'language',
  'broker',
  'platform',
  'content_format',
  'format_filter',
  'format_label',
  'website',
  'profile_url',
  'social_handles',
  'structured_socials',
  'followers',
  'bucket',
]

function normalizeText(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[|/_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function collectTextFragments(value, bucket) {
  if (value === null || value === undefined) return
  if (Array.isArray(value)) {
    value.forEach(item => collectTextFragments(item, bucket))
    return
  }
  if (typeof value === 'object') {
    Object.values(value).forEach(item => collectTextFragments(item, bucket))
    return
  }
  const normalized = normalizeText(value)
  if (normalized && normalized !== '-') {
    bucket.push(normalized)
  }
}

function expandQueryTerms(rawSearch) {
  const terms = normalizeText(rawSearch).split(' ').filter(Boolean)
  const expanded = []

  for (const term of terms) {
    expanded.push(term)
    if (term === 'yt') expanded.push('youtube')
    if (term === 'insta') expanded.push('instagram')
    if (term === 'reel') expanded.push('reels')
    if (term === 'short') expanded.push('shorts')
  }

  return [...new Set(expanded)]
}

function buildSearchText(creator) {
  const fragments = []
  SEARCH_KEYS.forEach(key => collectTextFragments(creator[key], fragments))

  // Add a punctuation-light variant so queries like "pushkarrajthakur"
  // can match handles written as "@pushkarrajthakur".
  const base = fragments.join(' ')
  const compact = base.replace(/[^a-z0-9]+/g, ' ')
  return `${base} ${compact}`
}

export function applyFilters(creators, filters) {
  return creators.filter(c => {
    if (filters.search) {
      const terms = expandQueryTerms(filters.search)
      const searchable = buildSearchText(c)
      if (!terms.every(term => searchable.includes(term))) return false
    }
    if (filters.platform && c.platform.toLowerCase() !== filters.platform.toLowerCase()) return false
    if (filters.tier && c.bucket !== filters.tier) return false
    if (filters.format && c.format_filter !== filters.format) return false
    if (filters.category && c.category !== filters.category) return false
    if (filters.language && c.language !== filters.language) return false
    if (filters.broker) {
      if (!c.broker || c.broker === '-' || !c.broker.toLowerCase().includes(filters.broker.toLowerCase())) return false
    }
    if (filters.engagement) {
      const rate = parseFloat(c.engagement_rate)
      if (filters.engagement === 'high' && (isNaN(rate) || rate < 5)) return false
      if (filters.engagement === 'medium' && (isNaN(rate) || rate < 2 || rate >= 5)) return false
      if (filters.engagement === 'low' && (isNaN(rate) || rate >= 2)) return false
    }
    if (filters.contact) {
      const hasEmail = c.email && c.email !== '-'
      const hasPhone = c.phone && c.phone !== '-'
      if (filters.contact === 'email' && !hasEmail) return false
      if (filters.contact === 'phone' && !hasPhone) return false
      if (filters.contact === 'both' && (!hasEmail || !hasPhone)) return false
      if (filters.contact === 'none' && (hasEmail || hasPhone)) return false
      if (filters.contact === 'any' && !hasEmail && !hasPhone) return false
    }
    if (filters.stockMarketOnly && (c.is_relevant === false || c.is_relevant === 0)) return false
    if (filters.indiaOnly && (c.targets_india === false || c.targets_india === 0)) return false
    return true
  })
}

export function getFilterOptions(creators) {
  const categories = [...new Set(creators.map(c => c.category).filter(v => v && v !== '-'))].sort()
  const languages = [...new Set(creators.map(c => c.language).filter(v => v && v !== '-'))].sort()
  const brokers = [...new Set(
    creators.flatMap(c => (c.broker || '').split(',').map(b => b.trim())).filter(v => v && v !== '-')
  )].sort()
  return { categories, languages, brokers }
}

export function getActiveFilterLabels(filters) {
  const chips = []
  if (filters.platform) chips.push({ key: 'platform', label: filters.platform })
  if (filters.tier) chips.push({ key: 'tier', label: filters.tier })
  if (filters.format) {
    const labels = { longform: 'Longform', shortform: 'Short-Form', hybrid: 'Hybrid', carousels: 'Carousels', images: 'Images' }
    chips.push({ key: 'format', label: labels[filters.format] || filters.format })
  }
  if (filters.category) chips.push({ key: 'category', label: filters.category })
  if (filters.language) chips.push({ key: 'language', label: filters.language })
  if (filters.broker) chips.push({ key: 'broker', label: filters.broker })
  if (filters.engagement) chips.push({ key: 'engagement', label: `Eng: ${filters.engagement}` })
  if (filters.contact) chips.push({ key: 'contact', label: `Contact: ${filters.contact}` })
  return chips
}
