const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export const apiClient = {
  getPortfolio: () => request('/api/v1/portfolio'),
  getTrades: () => request('/api/v1/trades'),
  getPerformance: () => request('/api/v1/performance'),
  getHistory: () => request('/api/v1/history'),
  analyze: (ticker) => request(`/api/v1/analyze?stock_symbol=${ticker}`, { method: 'POST' }),
  predict: (stock_symbol) =>
    request('/api/v1/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stock_symbol, lookback_days: 180 }),
    }),
  backtest: (stock_symbol) =>
    request('/api/v1/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stock_symbol, lookback_days: 365 }),
    }),
  generateMemo: () =>
    request('/api/v1/memo/generate', { method: 'POST' }),
  getDownloadMemoUrl: (filename) => `${API_BASE}/api/v1/memo/download/${filename}`,
}

