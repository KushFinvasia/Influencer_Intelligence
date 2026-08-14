/** CSV export utility. */

export function exportCSV(creators, visibleColumns, allColumns) {
  const cols = visibleColumns
    .map(id => allColumns.find(c => c.id === id))
    .filter(Boolean)

  const headers = cols.map(c => c.label)
  const rows = creators.map(creator =>
    cols.map(col => csvCellValue(creator, col.id))
  )

  const csv = [headers, ...rows]
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `creators_export_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function csvCellValue(creator, columnId) {
  switch (columnId) {
    case 'platform':    return creator.platform || ''
    case 'name':        return creator.name || ''
    case 'followers':   return creator.followers || ''
    case 'tier':        return creator.bucket || ''
    case 'format':      return creator.content_format || ''
    case 'performance': return [
      creator.avg_views !== '-' ? `Avg Views: ${creator.avg_views}` : '',
      creator.avg_likes !== '-' ? `Avg Likes: ${creator.avg_likes}` : '',
      creator.avg_comments !== '-' ? `Avg Comments: ${creator.avg_comments}` : '',
    ].filter(Boolean).join('; ')
    case 'engagement':  return creator.engagement_rate || ''
    case 'email':       return creator.email === '-' ? '' : (creator.email || '')
    case 'phone':       return creator.phone === '-' ? '' : (creator.phone || '')
    case 'category':    return creator.category === '-' ? '' : (creator.category || '')
    case 'language':    return creator.language === '-' ? '' : (creator.language || '')
    case 'broker':      return creator.broker === '-' ? '' : (creator.broker || '')
    case 'profile':     return creator.profile_url || ''
    case 'updated':     return creator.metrics_calculated_at || ''
    default:            return ''
  }
}
