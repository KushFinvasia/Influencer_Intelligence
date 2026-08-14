/** Filter logic for creator data. */

export function applyFilters(creators, filters) {
  return creators.filter(c => {
    if (filters.search) {
      const q = filters.search.toLowerCase()
      const searchable = [
        c.name, c.email, c.phone, c.category, c.language,
        c.broker, c.platform, c.content_format, c.format_label,
        c.website, c.social_handles,
      ].join(' ').toLowerCase()
      if (!searchable.includes(q)) return false
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
