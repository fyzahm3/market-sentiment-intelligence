export default function SentimentPage({ scanResult, onAnalyze, ticker, setTicker, loading }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
      <h3 className="text-lg font-bold mb-4 text-gray-300">Hybrid Sentiment Analyzer</h3>
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="Ticker"
          className="bg-gray-900 border border-gray-600 text-white px-4 py-2 rounded-lg flex-1 font-mono uppercase"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
        />
        <button onClick={onAnalyze} disabled={loading} className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-bold text-white">
          Analyze
        </button>
      </div>
      {scanResult && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-gray-900 p-4 rounded border border-gray-700">
            <p className="text-xs text-gray-400">Ticker</p>
            <p className="text-xl font-bold">{scanResult.stock_symbol}</p>
            <p className="text-sm text-gray-400">Label: {scanResult.sentiment_label}</p>
          </div>
          <div className="bg-gray-900 p-4 rounded border border-gray-700">
            <p className="text-xs text-gray-400">Scores</p>
            <p>VADER: {Number(scanResult.vader_score || 0).toFixed(3)}</p>
            <p>FinBERT: {Number(scanResult.finbert_score || 0).toFixed(3)}</p>
            <p>Hybrid: {Number(scanResult.hybrid_score || scanResult.sentiment_score || 0).toFixed(3)}</p>
          </div>
        </div>
      )}
    </div>
  )
}
