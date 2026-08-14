import { getActiveFilterLabels } from '../utils/filters'

export default function FilterChips({ filters, onChange }) {
  const chips = getActiveFilterLabels(filters)
  if (!chips.length) return null

  const removeFilter = (key) => {
    onChange({ ...filters, [key]: '' })
  }

  const clearAll = () => {
    const cleared = {}
    Object.keys(filters).forEach(k => { if (k !== 'search') cleared[k] = '' })
    onChange({ ...filters, ...cleared })
  }

  return (
    <div className="filter-chips">
      {chips.map(chip => (
        <span key={chip.key} className="filter-chip">
          {chip.label}
          <button className="filter-chip__remove" onClick={() => removeFilter(chip.key)}>×</button>
        </span>
      ))}
      <button className="filter-chips__clear" onClick={clearAll}>Clear all</button>
    </div>
  )
}
