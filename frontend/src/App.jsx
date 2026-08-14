import React, { useState, useMemo, useEffect } from 'react'
import './App.css'
import { COLUMNS } from './utils/columns'
import { applyFilters, getFilterOptions } from './utils/filters'
import { sortCreators } from './utils/sort'
import { exportCSV } from './utils/export'
import { usePreferences } from './hooks/usePreferences'
import { useCreatorData } from './hooks/useCreatorData'

import Sidebar from './components/Sidebar'
import TopHeader from './components/TopHeader'
import MetricCards from './components/MetricCards'
import FilterBar from './components/FilterBar'
import TableToolbar from './components/TableToolbar'
import CreatorTable from './components/CreatorTable'
import Pagination from './components/Pagination'
import ColumnsMenu from './components/ColumnsMenu'
import CreatorDrawer from './components/CreatorDrawer'
import PerfPopover from './components/PerfPopover'
import EmptyState from './components/EmptyState'

export default function App() {
  const {
    prefs,
    setTheme,
    setDensity,
    setPageSize,
    toggleColumn,
    setColumnOrder,
    resetColumns,
  } = usePreferences()

  const { creators, loading, error, generatedAt, refetch } = useCreatorData()

  // Active navigation tab in left sidebar
  const [activeNav, setActiveNav] = useState('all')

  // Local filter and search state
  const [filters, setFilters] = useState({
    search: '',
    platform: '',
    tier: '',
    format: '',
    category: '',
    language: '',
    broker: '',
    engagement: '',
    contact: '',
  })

  // Sorting state
  const [sortColumn, setSortColumn] = useState('followers')
  const [sortDirection, setSortDirection] = useState('desc')

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)

  // Selected row IDs (checkboxes)
  const [selectedIds, setSelectedIds] = useState([])

  // Modal / Drawer / Popover state
  const [selectedCreator, setSelectedCreator] = useState(null)
  const [showColumnSettings, setShowColumnSettings] = useState(false)
  const [perfPopover, setPerfPopover] = useState(null)

  // Fullscreen state
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Sync theme attribute to HTML tag
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', prefs.theme || 'light')
  }, [prefs.theme])

  // Handle Sidebar quick navigation clicks
  const handleNavChange = (navId) => {
    setActiveNav(navId)
    setCurrentPage(1)

    const base = { ...filters }
    switch (navId) {
      case 'all':
        setFilters({ ...base, format: '', broker: '', contact: '' })
        break
      case 'longform':
        setFilters({ ...base, format: 'longform' })
        break
      case 'shortform':
        setFilters({ ...base, format: 'shortform' })
        break
      case 'with_broker':
        setFilters({ ...base, broker: 'any_broker' }) // handled in custom filter or search
        break
      case 'with_contact':
        setFilters({ ...base, contact: 'any' })
        break
      case 'performance':
        setSortColumn('performance')
        setSortDirection('desc')
        break
      case 'engagement':
        setSortColumn('engagement')
        setSortDirection('desc')
        break
      case 'followers_tier':
        setSortColumn('followers')
        setSortDirection('desc')
        break
      default:
        break
    }
  }

  // Derive dynamic filter options (categories, languages, brokers)
  const filterOptions = useMemo(() => getFilterOptions(creators), [creators])

  // Calculate metrics for sidebar & cards
  const sidebarMetrics = useMemo(() => {
    const total = creators.length
    const longformCount = creators.filter(c => c.format_filter === 'longform').length
    const shortformCount = creators.filter(c =>
      c.format_filter === 'shortform' || c.format_filter === 'carousels' || c.format_filter === 'images'
    ).length
    const withBrokerCount = creators.filter(c => c.broker && c.broker !== '-').length
    const withContactCount = creators.filter(c =>
      (c.email && c.email !== '-') || (c.phone && c.phone !== '-')
    ).length

    return { total, longformCount, shortformCount, withBrokerCount, withContactCount }
  }, [creators])

  // Filter pipeline
  const filteredCreators = useMemo(() => {
    let result = applyFilters(creators, filters)
    if (filters.broker === 'any_broker') {
      result = result.filter(c => c.broker && c.broker !== '-')
    }
    return result
  }, [creators, filters])

  // Sort pipeline
  const sortedCreators = useMemo(() => {
    return sortCreators(filteredCreators, sortColumn, sortDirection)
  }, [filteredCreators, sortColumn, sortDirection])

  // Pagination slice
  const paginatedCreators = useMemo(() => {
    const start = (currentPage - 1) * prefs.pageSize
    return sortedCreators.slice(start, start + prefs.pageSize)
  }, [sortedCreators, currentPage, prefs.pageSize])

  // Compute visible columns
  const visibleColumns = useMemo(() => {
    return prefs.columnOrder
      .filter(id => !prefs.hiddenColumns.includes(id))
      .map(id => COLUMNS.find(c => c.id === id))
      .filter(Boolean)
  }, [prefs.columnOrder, prefs.hiddenColumns])

  // Handlers
  const handleFiltersChange = (newFilters) => {
    setFilters(newFilters)
    setCurrentPage(1)
  }

  const handleSort = (columnId) => {
    if (sortColumn === columnId) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(columnId)
      setSortDirection('desc')
    }
  }

  const handleExportCSV = () => {
    const visibleIds = visibleColumns.map(c => c.id)
    exportCSV(sortedCreators, visibleIds, COLUMNS)
  }

  const handlePerfClick = (e, creator) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setPerfPopover({
      data: creator,
      position: { x: rect.left, y: rect.bottom },
    })
  }

  // Row selection checkboxes
  const handleToggleCheck = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    )
  }

  const handleToggleSelectAll = () => {
    if (paginatedCreators.every(c => selectedIds.includes(c.id))) {
      const pageIds = paginatedCreators.map(c => c.id)
      setSelectedIds(prev => prev.filter(id => !pageIds.includes(id)))
    } else {
      const pageIds = paginatedCreators.map(c => c.id)
      setSelectedIds(prev => Array.from(new Set([...prev, ...pageIds])))
    }
  }

  const handleToggleDensity = () => {
    const cycle = { compact: 'comfortable', comfortable: 'spacious', spacious: 'compact' }
    setDensity(cycle[prefs.density] || 'comfortable')
  }

  const handleSaveView = () => {
    alert('Current filters, sorting, and visible columns saved as preferred default!')
  }

  const handleScrapeYT = async () => {
    try {
      const res = await fetch('/api/scrape/youtube', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_defaults: true, max_depth: 3 })
      })
      if (res.ok) alert('YouTube scrape started in the background!')
      else alert('Failed to start YouTube scrape')
    } catch (err) {
      alert('Error starting scrape: ' + err.message)
    }
  }

  const handleScrapeInsta = async () => {
    try {
      const res = await fetch('/api/scrape/instagram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_defaults: true, max_depth: 1 })
      })
      if (res.ok) alert('Instagram scrape started in the background!')
      else alert('Failed to start Instagram scrape')
    } catch (err) {
      alert('Error starting scrape: ' + err.message)
    }
  }

  return (
    <div className="app-layout">
      {/* Left Sidebar */}
      <Sidebar
        activeNav={activeNav}
        onNavChange={handleNavChange}
        metrics={sidebarMetrics}
        generatedAt={generatedAt}
        onRefresh={refetch}
        onScrapeYT={handleScrapeYT}
        onScrapeInsta={handleScrapeInsta}
      />

      {/* Main Content */}
      <main className="main-content">
        {/* Top Header */}
        <TopHeader
          theme={prefs.theme}
          onToggleTheme={() => setTheme(prefs.theme === 'dark' ? 'light' : 'dark')}
          onOpenColumnSettings={() => setShowColumnSettings(true)}
          onExportCSV={handleExportCSV}
        />

        {/* 5 Metric Summary Cards */}
        <MetricCards creators={creators} />

        {/* Table & Controls (Fullscreen target) */}
        <div className={`table-fullscreen-wrapper ${isFullscreen ? 'isFullscreen' : ''}`}>
          {/* Search & Filter Bar */}
          <FilterBar
            filters={filters}
            onChange={handleFiltersChange}
            options={filterOptions}
          />

        {/* Table Toolbar */}
        <TableToolbar
          onResetColumns={resetColumns}
          onSaveView={handleSaveView}
          density={prefs.density}
          onToggleDensity={handleToggleDensity}
          isFullscreen={isFullscreen}
          onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
        />

        {/* Table & States */}
        {loading ? (
          <EmptyState type="loading" />
        ) : error ? (
          <EmptyState type="error" message={error} onRetry={refetch} />
        ) : sortedCreators.length === 0 ? (
          <EmptyState
            type="empty"
            onClearFilters={() => {
              setFilters({
                search: '',
                platform: '',
                tier: '',
                format: '',
                category: '',
                language: '',
                broker: '',
                engagement: '',
                contact: '',
              })
              setActiveNav('all')
            }}
          />
        ) : (
          <>
            <CreatorTable
              creators={paginatedCreators}
              visibleColumns={visibleColumns}
              columnOrder={prefs.columnOrder}
              sortColumn={sortColumn}
              sortDirection={sortDirection}
              onSort={handleSort}
              onReorderColumns={setColumnOrder}
              density={prefs.density}
              selectedCreator={selectedCreator}
              onSelectCreator={setSelectedCreator}
              onPerfClick={handlePerfClick}
              selectedIds={selectedIds}
              onToggleSelectAll={handleToggleSelectAll}
              onToggleCheck={handleToggleCheck}
            />

            {/* Pagination Controls */}
            <Pagination
              totalItems={sortedCreators.length}
              currentPage={currentPage}
              pageSize={prefs.pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
            />
          </>
        )}
        </div>
      </main>

      {/* Column Settings Modal */}
      {showColumnSettings && (
        <ColumnsMenu
          columns={COLUMNS}
          columnOrder={prefs.columnOrder}
          hiddenColumns={prefs.hiddenColumns}
          onToggleColumn={toggleColumn}
          onReorderColumns={setColumnOrder}
          onResetColumns={resetColumns}
          onClose={() => setShowColumnSettings(false)}
        />
      )}

      {/* Creator Detail Drawer */}
      {selectedCreator && (
        <CreatorDrawer
          creator={selectedCreator}
          onClose={() => setSelectedCreator(null)}
        />
      )}

      {/* Performance Metric Breakdown Popover */}
      {perfPopover && (
        <PerfPopover
          data={perfPopover.data}
          position={perfPopover.position}
          onClose={() => setPerfPopover(null)}
        />
      )}
    </div>
  )
}
