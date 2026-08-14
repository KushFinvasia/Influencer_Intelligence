/** Sort comparators for the creator table. */

export function sortCreators(creators, columnId, direction) {
  if (!columnId || !direction) return creators
  const sorted = [...creators]
  sorted.sort((a, b) => {
    const va = getCellValue(a, columnId)
    const vb = getCellValue(b, columnId)
    let cmp = 0
    if (typeof va === 'number' && typeof vb === 'number') {
      cmp = va - vb
    } else {
      cmp = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: 'base' })
    }
    return direction === 'asc' ? cmp : -cmp
  })
  return sorted
}

function getCellValue(creator, columnId) {
  switch (columnId) {
    case 'platform':   return creator.platform || ''
    case 'name':       return creator.name || ''
    case 'followers':  return creator.followers_raw || 0
    case 'tier':       return tierOrder(creator.bucket)
    case 'format':     return creator.content_format || ''
    case 'engagement': return parseFloat(creator.engagement_rate) || 0
    case 'email':      return creator.email === '-' ? '' : (creator.email || '')
    case 'phone':      return creator.phone === '-' ? '' : (creator.phone || '')
    case 'category':   return creator.category === '-' ? '' : (creator.category || '')
    case 'language':   return creator.language === '-' ? '' : (creator.language || '')
    case 'broker':     return creator.broker === '-' ? '' : (creator.broker || '')
    case 'updated':    return creator.metrics_calculated_at || ''
    default:           return ''
  }
}

function tierOrder(bucket) {
  const order = { '1M+': 4, '300K–1M': 3, '10K–300K': 2, '< 10K': 1 }
  return order[bucket] || 0
}
