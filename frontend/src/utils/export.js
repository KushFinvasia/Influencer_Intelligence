/** Export utilities for CSV and styled Excel downloads. */

/**
 * Hand a blob to the browser as a file download.
 *
 * The anchor is attached to the document before clicking (a detached anchor is
 * ignored by some browsers) and the object URL is revoked on a later tick —
 * revoking synchronously invalidates the URL immediately and can abort the
 * download before the browser has finished reading the blob.
 */
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function exportCSV(creators, visibleColumns, allColumns) {
  const cols = visibleColumns
    .map(id => allColumns.find(c => c.id === id))
    .filter(Boolean)

  const headers = cols.map(c => c.label)
  const rows = creators.map((creator, index) =>
    cols.map(col => csvCellValue(creator, col.id, index))
  )

  const csv = [headers, ...rows]
  .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
  .join('\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  triggerDownload(blob, `creators_export_${new Date().toISOString().slice(0, 10)}.csv`)
}

export async function exportExcel(creators, visibleColumns) {
  try {
    const response = await fetch('/api/export/excel', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        creators: creators,
        visible_columns: visibleColumns,
      }),
    })

    if (!response.ok) {
      throw new Error(`Failed to generate Excel: ${response.statusText}`)
    }

    const blob = await response.blob()
    triggerDownload(blob, `creators_export_${new Date().toISOString().slice(0, 10)}.xlsx`)
  } catch (err) {
    console.error('Excel Export Error:', err)
    alert(`Could not download Excel file: ${err.message}`)
  }
}

function csvCellValue(creator, columnId, index = 0) {
  switch (columnId) {
    case 'sno':         return index + 1
    case 'platform':    return creator.platform || ''
    case 'name':        return creator.name || ''
    case 'followers':   return creator.followers || ''
    case 'tier':        return creator.bucket || ''
    case 'format':      return creator.format_label || creator.content_format || ''
    case 'social_handles': return creator.social_handles === '-' ? '' : (creator.social_handles || '')
    case 'website':     return creator.website === '-' ? '' : (creator.website || '')
    case 'avg_views':   return creator.avg_views === '-' ? '' : (creator.avg_views || '')
    case 'avg_likes':   return creator.avg_likes === '-' ? '' : (creator.avg_likes || '')
    case 'avg_comments': return creator.avg_comments === '-' ? '' : (creator.avg_comments || '')
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
