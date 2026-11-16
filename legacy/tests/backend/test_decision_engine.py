import pytest
from app.services.decision_engine import decide_trade

@pytest.fixture
def base_params():
    return {
        "sentiment_buy_threshold": 0.10,
        "max_position_weight": 0.30,
        "cash_reserve_floor": 0.10,
        "base_allocation_pct": 0.10,
        "min_trade_amount": 10.0,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
    }

def test_stop_loss_triggered(base_params):
    # If we hold stock bought at $100 and it falls to $94 (6% decline > 5% SL)
    decision = decide_trade(
        symbol="AAPL",
        position_qty=10.0,
        avg_buy_price=100.0,
        current_price=94.0,
        sentiment_label="neutral",
        hybrid_score=0.0,
        prediction_direction="up",
        cash_balance=50000.0,
        total_portfolio_value=100000.0,
        params=base_params
    )
    assert decision is not None
    assert decision["action"] == "SELL"
    assert "Stop-loss" in decision["reason"]
    assert decision["quantity"] == 10.0

def test_take_profit_triggered(base_params):
    # If we hold stock bought at $100 and it rises to $116 (16% rise > 15% TP)
    decision = decide_trade(
        symbol="AAPL",
        position_qty=10.0,
        avg_buy_price=100.0,
        current_price=116.0,
        sentiment_label="neutral",
        hybrid_score=0.0,
        prediction_direction="up",
        cash_balance=50000.0,
        total_portfolio_value=100000.0,
        params=base_params
    )
    assert decision is not None
    assert decision["action"] == "SELL"
    assert "Take-profit" in decision["reason"]
    assert decision["quantity"] == 10.0

def test_bearish_sentiment_exit(base_params):
    # If stock news sentiment turns bearish
    decision = decide_trade(
        symbol="AAPL",
        position_qty=10.0,
        avg_buy_price=100.0,
        current_price=100.0,
        sentiment_label="bearish",
        hybrid_score=-0.2,
        prediction_direction="up",
        cash_balance=50000.0,
        total_portfolio_value=100000.0,
        params=base_params
    )
    assert decision is not None
    assert decision["action"] == "SELL"
    assert "Sentiment exit" in decision["reason"]

def test_bullish_entry_signal(base_params):
    # Sentiment is bullish and predictive direction is UP, with enough cash
    decision = decide_trade(
        symbol="AAPL",
        position_qty=0.0,
        avg_buy_price=0.0,
        current_price=100.0,
        sentiment_label="bullish",
        hybrid_score=0.5,
        prediction_direction="up",
        cash_balance=50000.0,
        total_portfolio_value=100000.0,
        params=base_params
    )
    assert decision is not None
    assert decision["action"] == "BUY"
    # Target allocation is 100000 (total_val) * 0.10 (base_alloc) * 0.5 (hybrid) = $5000
    # $5000 / $100 = 50 shares
    assert decision["quantity"] == pytest.approx(50.0)

def test_bullish_entry_skip_on_down_prediction(base_params):
    # Sentiment is bullish, but trend prediction is DOWN
    decision = decide_trade(
        symbol="AAPL",
        position_qty=0.0,
        avg_buy_price=0.0,
        current_price=100.0,
        sentiment_label="bullish",
        hybrid_score=0.5,
        prediction_direction="down",
        cash_balance=50000.0,
        total_portfolio_value=100000.0,
        params=base_params
    )
    assert decision is None

def test_bullish_entry_skip_on_insufficient_cash(base_params):
    # Sentiment bullish, prediction UP, but cash is below reserve floor (10% of 100k = 10k)
    decision = decide_trade(
        symbol="AAPL",
        position_qty=0.0,
        avg_buy_price=0.0,
        current_price=100.0,
        sentiment_label="bullish",
        hybrid_score=0.5,
        prediction_direction="up",
        cash_balance=9000.0, # Less than 10k floor
        total_portfolio_value=100000.0,
        params=base_params
    )
    assert decision is None
