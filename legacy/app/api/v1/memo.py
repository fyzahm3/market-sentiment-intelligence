import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.services.backtest_engine import run_backtest_with_baselines
from app.services.memo_generator import create_client_memo_pdf, generate_memo_text

router = APIRouter(prefix="/api/v1")

@router.post("/memo/generate")
def generate_memo():
    """
    Triggers a backtest, extracts performance statistics, and generates
    a compliance-verified PDF client advisory memo.
    """
    try:
        # Use standard strategy params matching the backtester
        params = {
            "initial_capital": 100000.0,
            "min_trade_amount": 10.0,
            "max_position_weight": 0.30,
            "cash_reserve_floor": 0.10,
            "base_allocation_pct": 0.10,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.15,
            "transaction_cost_bps": 10.0
        }
        res = run_backtest_with_baselines("PORTFOLIO", params)
        
        # Format data summary for memo
        data_summary = {
            "strategy_return": res["strategy"]["total_return_pct"],
            "benchmark_return": res["benchmark_basket"]["total_return_pct"],
            "spy_return": res["benchmark_spy"]["total_return_pct"],
            "sharpe": res["strategy"]["sharpe_ratio"],
            "sortino": res["strategy"]["sortino_ratio"],
            "max_dd": res["strategy"]["max_drawdown_pct"],
            "trades_count": res["strategy"]["trades_count"],
            "win_rate": res["strategy"]["win_rate"],
            "mc_percentile": res["monte_carlo_sharpe_percentile"],
            "cagr": res["strategy"]["cagr"],
            "trades": res["trades"]
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"client_memo_{timestamp}.pdf"
        
        # Write PDF to reports/memos/
        filepath = create_client_memo_pdf(data_summary, filename)
        
        # Generate text prose for preview
        prose = generate_memo_text(data_summary)
        
        return {
            "success": True,
            "filename": filename,
            "prose": prose,
            "metrics": data_summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate memo: {str(e)}")

@router.get("/memo/download/{filename}")
def download_memo(filename: str):
    """
    Serves the generated PDF file for download.
    """
    filepath = os.path.abspath(os.path.join("reports/memos", filename))
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Requested memo file not found")
        
    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename
    )
