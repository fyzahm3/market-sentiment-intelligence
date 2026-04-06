import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './App.css'

function App() {
  // --- STATE ---
  const [portfolio, setPortfolio] = useState([])
  const [trades, setTrades] = useState([])
  const [performance, setPerformance] = useState(null)
  const [history, setHistory] = useState([]) // New: Chart Data
  
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [scanResult, setScanResult] = useState(null)

  // --- FETCH DATA ---
  useEffect(() => {
    fetchDashboardData()
    const interval = setInterval(fetchDashboardData, 5000) // Refresh every 5s
    return () => clearInterval(interval)
  }, [])

  const fetchDashboardData = async () => {
    try {
      // 1. Portfolio
      const pRes = await fetch('http://127.0.0.1:8000/api/v1/portfolio')
      const pData = await pRes.json()
      setPortfolio(pData.portfolio || [])

      // 2. Trades
      const tRes = await fetch('http://127.0.0.1:8000/api/v1/trades')
      const tData = await tRes.json()
      setTrades(tData.trades || [])

      // 3. Performance Stats
      const perfRes = await fetch('http://127.0.0.1:8000/api/v1/performance')
      const perfData = await perfRes.json()
      setPerformance(perfData)

      // 4. History Chart (The new part)
      const hRes = await fetch('http://127.0.0.1:8000/api/v1/history')
      const hData = await hRes.json()
      setHistory(hData.history || [])

    } catch (err) {
      console.error("Error fetching dashboard:", err)
    }
  }

  // --- MANUAL SCAN ---
  const handleAnalyze = async () => {
    if (!ticker) return
    setLoading(true)
    setScanResult(null)
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/analyze?stock_symbol=${ticker}`, {
        method: 'POST',
      })
      const result = await response.json()
      setScanResult(result)
      fetchDashboardData()
    } catch (error) {
      alert("Analysis failed")
    } finally {
      setLoading(false)
    }
  }

  // --- CALCULATIONS ---
  const cash = portfolio.find(p => p.symbol === 'USD')?.quantity || 0
  const stockValue = portfolio.filter(p => p.symbol !== 'USD').reduce((acc, curr) => acc + curr.value, 0)
  const totalValue = cash + stockValue

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8 font-sans">
      
      {/* HEADER */}
      <div className="flex flex-col md:flex-row justify-between items-center mb-8 border-b border-gray-700 pb-6 gap-4">
        <div>
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-teal-400">
            AI Hedge Fund
          </h1>
          <p className="text-gray-400 mt-1">Autonomous Sentiment Trading Agent</p>
        </div>
        <div className="text-right bg-gray-800 p-4 rounded-xl border border-gray-700 shadow-lg">
          <p className="text-xs text-gray-400 uppercase tracking-wider">Total Net Worth</p>
          <h2 className="text-3xl font-mono font-bold text-green-400">
            ${totalValue.toLocaleString(undefined, {maximumFractionDigits: 0})}
          </h2>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN (2/3 Width) */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* 1. PERFORMANCE CHART (NEW) */}
          <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-white">
              📈 Performance History
            </h3>
            <div className="h-64 w-full">
              {history.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time" stroke="#9CA3AF" />
                    <YAxis domain={['auto', 'auto']} stroke="#9CA3AF" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', color: '#fff' }} 
                    />
                    <Legend />
                    <Line type="monotone" dataKey="AI Fund" stroke="#4ADE80" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="S&P 500" stroke="#9CA3AF" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 italic">
                  Waiting for data... (Engine runs every 60s)
                </div>
              )}
            </div>
          </div>

          {/* 2. PORTFOLIO TABLE */}
          <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-blue-300">
              📊 Current Holdings
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700 text-sm uppercase">
                    <th className="py-3">Asset</th>
                    <th className="py-3">Shares</th>
                    <th className="py-3">Avg Price</th>
                    <th className="py-3 text-right">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700/50">
                  {portfolio.filter(p => p.symbol !== 'USD').map((asset) => (
                    <tr key={asset.symbol} className="hover:bg-gray-700/30">
                      <td className="py-3 font-bold text-white">{asset.symbol}</td>
                      <td className="py-3 font-mono text-gray-300">{asset.quantity.toFixed(4)}</td>
                      <td className="py-3 font-mono text-gray-400">${asset.avg_price.toFixed(2)}</td>
                      <td className="py-3 font-mono text-right text-green-400 font-bold">
                        ${asset.value.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                  {portfolio.filter(p => p.symbol !== 'USD').length === 0 && (
                    <tr><td colSpan="4" className="text-center py-6 text-gray-500 italic">No stocks owned yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 3. TRADE LOGS */}
          <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-purple-300">
              📝 Recent Decisions
            </h3>
            <div className="overflow-x-auto max-h-60 overflow-y-auto pr-2 custom-scrollbar">
              <table className="w-full text-left text-sm">
                <tbody className="divide-y divide-gray-700/30">
                  {trades.map((trade, i) => (
                    <tr key={i} className="hover:bg-gray-700/30">
                      <td className="py-2 text-gray-500 text-xs font-mono">
                        {new Date(trade.date).toLocaleTimeString()}
                      </td>
                      <td className="py-2 font-bold text-white">{trade.symbol}</td>
                      <td className="py-2">
                        <span className="bg-green-900/50 text-green-400 px-2 py-1 rounded text-xs font-bold border border-green-900">
                          BUY
                        </span>
                      </td>
                      <td className="py-2 text-xs text-gray-400 max-w-xs truncate">
                        {trade.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN (1/3 Width) */}
        <div className="space-y-6">
          
          {/* PERFORMANCE SCOREBOARD */}
          {performance && (
            <div className={`rounded-xl p-6 border shadow-2xl transition-all ${
              performance.is_beating_market 
                ? 'bg-gradient-to-br from-green-900/40 to-gray-900 border-green-500/50' 
                : 'bg-gradient-to-br from-red-900/40 to-gray-900 border-red-500/50'
            }`}>
              <h3 className="text-lg font-bold text-gray-200 mb-6 border-b border-white/10 pb-2">
                🏆 vs. S&P Equal Weight
              </h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">AI Fund</span>
                  <div className="text-right">
                    <div className="font-mono font-bold text-xl text-white">
                      ${performance.ai_fund.value.toLocaleString(undefined, {maximumFractionDigits: 0})}
                    </div>
                  </div>
                </div>
                <div className="flex justify-between items-center opacity-75">
                  <span className="text-gray-400">Index Fund</span>
                  <div className="text-right">
                    <div className="font-mono font-bold text-xl text-gray-300">
                      ${performance.benchmark_index.value.toLocaleString(undefined, {maximumFractionDigits: 0})}
                    </div>
                  </div>
                </div>
                <div className="pt-4 border-t border-white/10 mt-2 flex justify-between items-center">
                  <span className="font-bold text-gray-300 text-sm">Alpha (Edge)</span>
                  <span className={`font-bold text-2xl ${performance.is_beating_market ? 'text-green-400' : 'text-red-400'}`}>
                    {performance.alpha > 0 ? '+' : ''}{performance.alpha.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* MANUAL SCANNER */}
          <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
            <h3 className="text-lg font-bold mb-4 text-gray-300">🔎 Manual Scanner</h3>
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                placeholder="Ticker"
                className="bg-gray-900 border border-gray-600 text-white px-4 py-2 rounded-lg flex-1 focus:outline-none focus:border-blue-500 font-mono uppercase"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
              />
              <button
                onClick={handleAnalyze}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-bold text-white"
              >
                Go
              </button>
            </div>
            {scanResult && (
              <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-600">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-xl text-white">{scanResult.stock_symbol}</span>
                  <span className="text-gray-400">{scanResult.sentiment_label}</span>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}

export default App