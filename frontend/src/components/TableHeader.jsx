import React, { useState } from 'react'

export default function TableHeader({
  visibleColumns,
  sortColumn,
  sortDirection,
  onSort,
  onReorderColumns,
  columnOrder,
  allSelected,
  onToggleSelectAll,
}) {
  const [draggedColId, setDraggedColId] = useState(null)
  const [dragOverColId, setDragOverColId] = useState(null)

  const handleDragStart = (e, colId) => {
    setDraggedColId(colId)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', colId)
  }

  const handleDragOver = (e, colId) => {
    e.preventDefault()
    if (colId !== draggedColId) {
      setDragOverColId(colId)
    }
  }

  const handleDrop = (e, targetColId) => {
    e.preventDefault()
    if (!draggedColId || draggedColId === targetColId) {
      setDraggedColId(null)
      setDragOverColId(null)
      return
    }

    const newOrder = [...columnOrder]
    const fromIndex = newOrder.indexOf(draggedColId)
    const toIndex = newOrder.indexOf(targetColId)

    if (fromIndex !== -1 && toIndex !== -1) {
      newOrder.splice(fromIndex, 1)
      newOrder.splice(toIndex, 0, draggedColId)
      onReorderColumns(newOrder)
    }

    setDraggedColId(null)
    setDragOverColId(null)
  }

  const handleDragEnd = () => {
    setDraggedColId(null)
    setDragOverColId(null)
  }

  return (
    <thead>
      <tr>
        {/* Selection Checkbox */}
        <th className="th-checkbox">
          <input
            type="checkbox"
            className="table-checkbox"
            checked={allSelected}
            onChange={onToggleSelectAll}
          />
        </th>

        {visibleColumns.map(col => {
          const isSorted = sortColumn === col.id
          const isDragging = draggedColId === col.id
          const isDragOver = dragOverColId === col.id

          return (
            <th
              key={col.id}
              className={`th-cell ${col.sortable ? 'th-cell--sortable' : ''} ${isDragging ? 'dragging' : ''} ${isDragOver ? 'drag-over' : ''}`}
              onClick={() => col.sortable && onSort(col.id)}
              draggable
              onDragStart={e => handleDragStart(e, col.id)}
              onDragOver={e => handleDragOver(e, col.id)}
              onDrop={e => handleDrop(e, col.id)}
              onDragEnd={handleDragEnd}
              title={`${col.label}${col.sortable ? ' (click to sort, drag to reorder)' : ' (drag to reorder)'}`}
            >
              <div className="th-content">
                <span>{col.label}</span>
                {col.sortable && (
                  <span className="th-sort-icon">
                    {isSorted ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}
                  </span>
                )}
              </div>
            </th>
          )
        })}

        {/* Actions Menu Column */}
        <th className="th-action">
          <span>⋮</span>
        </th>
      </tr>
    </thead>
  )
}
