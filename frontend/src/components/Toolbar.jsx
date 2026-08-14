import React, { useState } from 'react'
import ColumnsMenu from './ColumnsMenu'

export default function Toolbar({
  totalCount,
  filteredCount,
  columns,
  columnOrder,
  hiddenColumns,
  onToggleColumn,
  onReorderColumns,
  onResetColumns,
  density,
  onDensityChange,
  onExport,
}) {
  const [showColumnsMenu, setShowColumnsMenu] = useState(false)

  return (
    <div className="toolbar">
      <div className="toolbar__group">
        <span className="toolbar__text">
          Showing <strong>{filteredCount}</strong> of <strong>{totalCount}</strong> creators
        </span>
      </div>

      <div className="toolbar__spacer" />

      <div className="toolbar__group">
        <div className="popover-anchor">
          <button
            className={`toolbar__btn ${showColumnsMenu ? 'toolbar__btn--active' : ''}`}
            onClick={() => setShowColumnsMenu(prev => !prev)}
            title="Manage column visibility & order"
          >
            <span>☷ Columns ({columns.length - hiddenColumns.length}/{columns.length})</span>
          </button>
          {showColumnsMenu && (
            <ColumnsMenu
              columns={columns}
              columnOrder={columnOrder}
              hiddenColumns={hiddenColumns}
              onToggleColumn={onToggleColumn}
              onReorderColumns={onReorderColumns}
              onResetColumns={onResetColumns}
              onClose={() => setShowColumnsMenu(false)}
            />
          )}
        </div>

        <div className="density-group">
          <button
            className={`density-group__btn ${density === 'compact' ? 'density-group__btn--active' : ''}`}
            onClick={() => onDensityChange('compact')}
            title="Compact row height"
          >
            Compact
          </button>
          <button
            className={`density-group__btn ${density === 'comfortable' ? 'density-group__btn--active' : ''}`}
            onClick={() => onDensityChange('comfortable')}
            title="Comfortable row height"
          >
            Comfortable
          </button>
          <button
            className={`density-group__btn ${density === 'spacious' ? 'density-group__btn--active' : ''}`}
            onClick={() => onDensityChange('spacious')}
            title="Spacious row height"
          >
            Spacious
          </button>
        </div>

        <button
          className="toolbar__btn"
          onClick={onExport}
          title="Export currently filtered & visible data to CSV"
        >
          <span>📥 Export CSV</span>
        </button>
      </div>
    </div>
  )
}
