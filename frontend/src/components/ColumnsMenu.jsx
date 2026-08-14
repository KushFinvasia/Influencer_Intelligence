import React, { useState } from 'react'

export default function ColumnsMenu({
  columns,
  columnOrder,
  hiddenColumns,
  onToggleColumn,
  onReorderColumns,
  onResetColumns,
  onClose,
}) {
  const [draggedColId, setDraggedColId] = useState(null)
  const [dragOverColId, setDragOverColId] = useState(null)

  const orderedCols = columnOrder
    .map(id => columns.find(c => c.id === id))
    .filter(Boolean)

  const handleDragStart = (e, colId) => {
    setDraggedColId(colId)
    e.dataTransfer.effectAllowed = 'move'
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
    <>
      <div className="popover-backdrop" onClick={onClose} />
      <div className="column-settings-modal">
        <div className="modal-header">
          <div className="modal-title">Column Settings</div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-subtitle">
          Toggle column visibility and drag items to reorder them in the table.
        </div>

        <div className="column-list">
          {orderedCols.map(col => {
            const isVisible = !hiddenColumns.includes(col.id)
            const isDragging = draggedColId === col.id
            const isDragOver = dragOverColId === col.id

            return (
              <div
                key={col.id}
                className={`column-item ${isDragging ? 'column-item--dragging' : ''} ${isDragOver ? 'column-item--dragover' : ''}`}
                draggable
                onDragStart={e => handleDragStart(e, col.id)}
                onDragOver={e => handleDragOver(e, col.id)}
                onDrop={e => handleDrop(e, col.id)}
                onDragEnd={handleDragEnd}
              >
                <span className="drag-handle">⠿</span>
                <input
                  type="checkbox"
                  id={`col-${col.id}`}
                  className="table-checkbox"
                  checked={isVisible}
                  onChange={() => onToggleColumn(col.id)}
                />
                <label htmlFor={`col-${col.id}`} className="column-label">
                  {col.label}
                </label>
              </div>
            )
          })}
        </div>

        <div className="modal-footer">
          <button className="btn btn--outline" onClick={onResetColumns}>
            Reset to Default
          </button>
          <button className="btn btn--primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </>
  )
}
