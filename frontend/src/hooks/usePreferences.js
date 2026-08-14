import { useState, useCallback } from 'react'
import { DEFAULT_ORDER, DEFAULT_HIDDEN } from '../utils/columns'

const STORAGE_KEY = 'creator_ui_preferences'

const DEFAULTS = {
  theme: 'light',
  density: 'comfortable',
  pageSize: 20,
  columnOrder: DEFAULT_ORDER,
  hiddenColumns: DEFAULT_HIDDEN,
}

function loadPrefs() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      return { ...DEFAULTS, ...parsed }
    }
  } catch { /* ignore */ }
  return { ...DEFAULTS }
}

function savePrefs(prefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch { /* ignore */ }
}

export function usePreferences() {
  const [prefs, setPrefsState] = useState(loadPrefs)

  const setPrefs = useCallback((updater) => {
    setPrefsState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater }
      savePrefs(next)
      return next
    })
  }, [])

  const setTheme = useCallback((theme) => setPrefs(p => ({ ...p, theme })), [setPrefs])
  const setDensity = useCallback((density) => setPrefs(p => ({ ...p, density })), [setPrefs])
  const setPageSize = useCallback((pageSize) => setPrefs(p => ({ ...p, pageSize })), [setPrefs])

  const toggleColumn = useCallback((colId) => {
    setPrefs(p => {
      const hidden = p.hiddenColumns.includes(colId)
        ? p.hiddenColumns.filter(id => id !== colId)
        : [...p.hiddenColumns, colId]
      return { ...p, hiddenColumns: hidden }
    })
  }, [setPrefs])

  const setColumnOrder = useCallback((columnOrder) => {
    setPrefs(p => ({ ...p, columnOrder }))
  }, [setPrefs])

  const resetColumns = useCallback(() => {
    setPrefs(p => ({ ...p, columnOrder: DEFAULT_ORDER, hiddenColumns: DEFAULT_HIDDEN }))
  }, [setPrefs])

  return {
    prefs,
    setTheme,
    setDensity,
    setPageSize,
    toggleColumn,
    setColumnOrder,
    resetColumns,
  }
}
