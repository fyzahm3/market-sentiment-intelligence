import { useEffect, useRef, useState } from 'react'

export function usePollingQuery(fetcher, intervalMs = 8000, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    let timerId

    const run = async () => {
      try {
        const result = await fetcher()
        if (mountedRef.current) {
          setData(result)
          setError(null)
        }
      } catch (err) {
        if (mountedRef.current) setError(err)
      } finally {
        if (mountedRef.current) setLoading(false)
      }
    }

    run()
    timerId = setInterval(() => {
      if (!document.hidden) run()
    }, intervalMs)

    return () => {
      mountedRef.current = false
      clearInterval(timerId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading }
}
