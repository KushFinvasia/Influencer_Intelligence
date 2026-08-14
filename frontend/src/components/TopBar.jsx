import { useEffect, useRef } from 'react'

export default function TopBar({ search, onSearchChange, theme, onThemeToggle }) {
  const inputRef = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="top-bar">
      <span className="top-bar__title">Financial Influencer Intelligence</span>

      <div className="top-bar__search">
        <span className="top-bar__search-icon">⌕</span>
        <input
          ref={inputRef}
          type="text"
          placeholder="Search creators, handles, brokers, categories, emails..."
          value={search}
          onChange={e => onSearchChange(e.target.value)}
        />
        <span className="top-bar__search-hint">Ctrl+K</span>
      </div>

      <div className="top-bar__spacer" />

      <button
        className="top-bar__btn"
        onClick={onThemeToggle}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? '☀' : '☾'} {theme === 'dark' ? 'Light' : 'Dark'}
      </button>
    </div>
  )
}
