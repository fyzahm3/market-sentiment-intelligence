export default function BacktestPage({ backtest, onBacktest, ticker }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
      <h3 className="text-lg font-bold mb-4 text-gray-300">Backtest</h3>
      <button onClick={() => onBacktest(ticker)} className="bg-emerald-600 hover:bg-emerald-700 px-4 py-2 rounded-lg font-bold text-white mb-4">
        Run Backtest
      </button>
      {backtest && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-900 p-3 rounded border border-gray-700">Trades: {backtest.trades}</div>
          <div className="bg-gray-900 p-3 rounded border border-gray-700">Win Rate: {(backtest.win_rate * 100).toFixed(1)}%</div>
          <div className="bg-gray-900 p-3 rounded border border-gray-700">Sharpe: {Number(backtest.sharpe_ratio).toFixed(2)}</div>
          <div className="bg-gray-900 p-3 rounded border border-gray-700">Alpha: {Number(backtest.alpha).toFixed(2)}%</div>
        </div>
      )}
    </div>
  )
}
