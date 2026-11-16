export default function PredictionsPage({ prediction, onPredict, ticker }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
      <h3 className="text-lg font-bold mb-4 text-gray-300">LSTM Prediction</h3>
      <button onClick={() => onPredict(ticker)} className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg font-bold text-white mb-4">
        Predict Next Day
      </button>
      {prediction && (
        <div className="bg-gray-900 p-4 rounded border border-gray-700">
          <p>Direction: <span className="font-bold">{prediction.predicted_direction}</span></p>
          <p>Predicted Return: {(prediction.predicted_return * 100).toFixed(2)}%</p>
          <p>Confidence: {(prediction.confidence * 100).toFixed(1)}%</p>
          <p>Hybrid Sentiment: {Number(prediction.hybrid_sentiment_score || 0).toFixed(3)}</p>
        </div>
      )}
    </div>
  )
}
