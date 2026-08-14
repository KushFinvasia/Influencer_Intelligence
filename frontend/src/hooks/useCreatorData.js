import { useState, useEffect, useCallback } from 'react'

export function useCreatorData() {
  const [creators, setCreators] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generatedAt, setGeneratedAt] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/table-data')
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data = await res.json()
      setCreators(data.creators || [])
      setGeneratedAt(data.generated_at || null)
    } catch (err) {
      setError(err.message || 'Failed to load data')
      setCreators([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  return { creators, loading, error, generatedAt, refetch: fetchData }
}
