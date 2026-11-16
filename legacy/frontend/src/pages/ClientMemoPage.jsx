import { useState } from 'react'
import { apiClient } from '../services/apiClient'

export default function ClientMemoPage() {
  const [memo, setMemo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleGenerateMemo = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiClient.generateMemo()
      if (result.success) {
        setMemo(result)
      } else {
        throw new Error('Failed to generate memo')
      }
    } catch (err) {
      setError(err.message || 'Error occurred while generating memo')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl space-y-6">
      <div className="border-b border-gray-700 pb-4">
        <h3 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
          📄 Portfolio Advisory Client Memo
        </h3>
        <p className="text-gray-400 text-sm mt-1">
          Generate compliance-verified advisory memos summarizing algorithmic trading performance, sentiment indicators, and risk management limits in PDF format.
        </p>
      </div>

      {!memo && !loading && (
        <div className="flex flex-col items-center justify-center p-12 bg-gray-900/50 rounded-lg border border-dashed border-gray-700">
          <p className="text-gray-400 mb-6 text-center max-w-md">
            Click below to run a historical portfolio backtest and compile a professional client advisory memo grounded in performance metrics.
          </p>
          <button
            onClick={handleGenerateMemo}
            className="bg-blue-600 hover:bg-blue-700 hover:scale-105 active:scale-95 transition-all text-white font-bold px-6 py-3 rounded-lg flex items-center gap-2 shadow-lg"
          >
            ⚡ Generate Advisory Memo
          </button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center p-16 space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          <p className="text-blue-400 font-mono text-sm animate-pulse">Running Backtests & Compiling Report...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-900/30 border border-red-700/50 text-red-300 p-4 rounded-lg text-sm">
          ⚠️ {error}
        </div>
      )}

      {memo && !loading && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-4 justify-between items-center bg-gray-900 p-4 rounded-lg border border-gray-700 shadow-inner">
            <div>
              <span className="text-xs text-gray-400 uppercase font-mono">Document Generated</span>
              <h4 className="font-bold text-white text-lg">{memo.filename}</h4>
            </div>
            <a
              href={apiClient.getDownloadMemoUrl(memo.filename)}
              target="_blank"
              rel="noreferrer"
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-5 py-2.5 rounded-lg flex items-center gap-2 transition-all shadow-md"
            >
              📥 Download PDF Report
            </a>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
              <span className="text-xs text-gray-400">AI Fund Return</span>
              <p className="text-2xl font-mono font-bold text-green-400">+{memo.metrics.strategy_return.toFixed(2)}%</p>
            </div>
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
              <span className="text-xs text-gray-400">Vs Benchmark Basket</span>
              <p className="text-2xl font-mono font-bold text-blue-400">+{memo.metrics.benchmark_return.toFixed(2)}%</p>
            </div>
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
              <span className="text-xs text-gray-400">Sharpe / Sortino</span>
              <p className="text-2xl font-mono font-bold text-purple-400">{memo.metrics.sharpe.toFixed(2)} / {memo.metrics.sortino.toFixed(2)}</p>
            </div>
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
              <span className="text-xs text-gray-400">Monte Carlo Rank</span>
              <p className="text-2xl font-mono font-bold text-orange-400">{memo.metrics.mc_percentile.toFixed(1)}th %</p>
            </div>
          </div>

          {/* Memo Preview */}
          <div className="bg-gray-900 p-6 rounded-lg border border-gray-700 shadow-inner max-h-[500px] overflow-y-auto custom-scrollbar">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3 mb-4 text-xs font-mono text-gray-400">
              <span>MEMO PREVIEW</span>
              <span>CONFIDENTIAL</span>
            </div>
            <div className="text-gray-300 font-sans space-y-4 leading-relaxed whitespace-pre-line text-sm md:text-base">
              {memo.prose}
            </div>
          </div>
          
          <div className="flex justify-end">
            <button
              onClick={handleGenerateMemo}
              className="text-gray-400 hover:text-white font-mono text-sm underline transition-all"
            >
              Regenerate Report
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
