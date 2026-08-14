import React from 'react'
import TableHeader from './TableHeader'
import TableRow from './TableRow'

export default function CreatorTable({
  creators,
  visibleColumns,
  columnOrder,
  sortColumn,
  sortDirection,
  onSort,
  onReorderColumns,
  density,
  selectedCreator,
  onSelectCreator,
  onPerfClick,
  selectedIds,
  onToggleSelectAll,
  onToggleCheck,
}) {
  const allSelected = creators.length > 0 && creators.every(c => selectedIds.includes(c.id))

  return (
    <div className={`table-container density-${density}`}>
      <div className="table-scroll-wrapper">
        <table className="main-data-table">
          <TableHeader
            visibleColumns={visibleColumns}
            sortColumn={sortColumn}
            sortDirection={sortDirection}
            onSort={onSort}
            onReorderColumns={onReorderColumns}
            columnOrder={columnOrder}
            allSelected={allSelected}
            onToggleSelectAll={onToggleSelectAll}
          />
          <tbody>
            {creators.map(creator => (
              <TableRow
                key={`${creator.id}-${creator.platform}`}
                creator={creator}
                visibleColumns={visibleColumns}
                isSelected={selectedCreator?.id === creator.id && selectedCreator?.platform === creator.platform}
                isChecked={selectedIds.includes(creator.id)}
                onToggleCheck={onToggleCheck}
                onSelect={onSelectCreator}
                onPerfClick={onPerfClick}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
