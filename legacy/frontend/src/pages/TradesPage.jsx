export default function TradesPage({ trades }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
      <h3 className="text-lg font-bold mb-4 text-gray-300">Trade Log</h3>
      <div className="overflow-x-auto max-h-96">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-gray-400 border-b border-gray-700">
              <th className="py-2">Time</th>
              <th className="py-2">Ticker</th>
              <th className="py-2">Action</th>
              <th className="py-2">Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/30">
            {trades.map((trade, idx) => (
              <tr key={idx}>
                <td className="py-2">{new Date(trade.date).toLocaleTimeString()}</td>
                <td className="py-2">{trade.symbol}</td>
                <td className="py-2">{trade.action}</td>
                <td className="py-2 truncate max-w-xs">{trade.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
