const TABS = ['Dashboard', 'Sentiment Analyzer', 'Predictions', 'Backtest', 'Trade Log', 'Client Memo']


export default function Tabs({ activeTab, onChange }) {
  return (
    <div className="flex flex-wrap gap-2 mb-6">
      {TABS.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={`px-3 py-2 rounded-lg text-sm border ${
            activeTab === tab
              ? 'bg-blue-600 text-white border-blue-500'
              : 'bg-gray-800 text-gray-300 border-gray-700'
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
  )
}
