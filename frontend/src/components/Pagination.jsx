import React from 'react'

export default function Pagination({
  totalItems,
  currentPage,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endItem = Math.min(totalItems, currentPage * pageSize)

  // Generate pagination items with ellipses matching modern UI
  const getPaginationItems = () => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }

    if (currentPage <= 3) {
      return [1, 2, 3, '...', totalPages]
    }

    if (currentPage >= totalPages - 2) {
      return [1, '...', totalPages - 2, totalPages - 1, totalPages]
    }

    return [1, '...', currentPage, '...', totalPages]
  }

  return (
    <div className="table-pagination">
      <div className="pagination-info">
        Showing <strong>{startItem}</strong> to <strong>{endItem}</strong> of <strong>{totalItems}</strong> creators
      </div>

      <div className="pagination-controls">
        {/* Page size dropdown */}
        <div className="page-size-selector">
          <select
            className="page-size-select"
            value={pageSize}
            onChange={e => {
              onPageSizeChange(Number(e.target.value))
              onPageChange(1)
            }}
          >
            <option value={10}>10 per page</option>
            <option value={20}>20 per page</option>
            <option value={50}>50 per page</option>
            <option value={100}>100 per page</option>
          </select>
        </div>

        {/* Prev button */}
        <button
          className="page-btn page-btn--nav"
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
          title="Previous Page"
        >
          ‹
        </button>

        {/* Numbered pages */}
        {getPaginationItems().map((item, idx) => {
          if (item === '...') {
            return (
              <span key={`ellipsis-${idx}`} className="page-ellipsis">
                ...
              </span>
            )
          }

          const isActive = item === currentPage
          return (
            <button
              key={item}
              className={`page-btn ${isActive ? 'page-btn--active' : ''}`}
              onClick={() => onPageChange(item)}
            >
              {item}
            </button>
          )
        })}

        {/* Next button */}
        <button
          className="page-btn page-btn--nav"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          title="Next Page"
        >
          ›
        </button>
      </div>
    </div>
  )
}
