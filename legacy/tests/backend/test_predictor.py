from app.services.predictor import predict_next_day


def test_predictor_returns_contract():
    result = predict_next_day("AAPL", 90, 0.2)
    assert "predicted_direction" in result
    assert "confidence" in result
