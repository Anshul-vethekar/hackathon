import { useState, useEffect } from 'react'
import { api } from './api'

export function useBaseline() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.getBaseline()
      setData(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetch() }, [])

  return { data, loading, error, refetch: fetch }
}

export function useDisruption() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const analyze = async (params) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.analyzeDisruption(params)
      setResult(res)
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return { result, loading, error, analyze }
}

export function useRecovery() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = async (params) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.scheduleRecovery(params)
      setResult(res)
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return { result, loading, error, run }
}
