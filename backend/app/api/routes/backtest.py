"""
Backtest API routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ...schemas.backtest import (
    BacktestRequest,
    BacktestMultiRequest,
    BacktestMultiAnalyzeRequest,
    BacktestResponse,
)
from ...services import backtest_service

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """Run a single backtest."""
    try:
        result = backtest_service.run_backtest(
            strategy_name=req.strategy,
            symbol=req.symbol,
            source=req.source,
            exchange=req.exchange,
            interval=req.interval,
            n_bars=req.n_bars,
            initial_cash=req.initial_cash,
            commission=req.commission,
            slippage_ticks=req.slippage_ticks,
            strategy_params=req.strategy_params,
            instant_execution=req.instant_execution,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e}")


@router.post("/multi")
async def run_multi_backtest(req: BacktestMultiRequest):
    """Run backtests across multiple symbols/intervals."""
    try:
        results = backtest_service.run_multi_backtest(
            strategy_name=req.strategy,
            symbols=req.symbols,
            source=req.source,
            exchange=req.exchange,
            intervals=req.intervals,
            n_bars=req.n_bars,
            initial_cash=req.initial_cash,
            commission=req.commission,
            slippage_ticks=req.slippage_ticks,
            strategy_params=req.strategy_params,
        )
        return {"results": results, "count": len(results)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi backtest failed: {e}")


@router.post("/multi/analyze")
async def run_multi_analyze(req: BacktestMultiAnalyzeRequest):
    """Run matrix analysis via real backtests."""
    try:
        return backtest_service.run_multi_analyze(
            strategy_name=req.strategy,
            symbols=req.symbols,
            source=req.source,
            exchange=req.exchange,
            intervals=req.intervals,
            n_bars=req.n_bars,
            initial_cash=req.initial_cash,
            commission=req.commission,
            slippage_ticks=req.slippage_ticks,
            strategy_params=req.strategy_params,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi analyze failed: {e}")


@router.get("/history")
async def get_history(
    limit: int = Query(default=50, ge=1, le=200),
    strategy: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
):
    """Get backtest history with optional filters."""
    try:
        return backtest_service.get_history(limit=limit, strategy=strategy, symbol=symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{run_id}")
async def get_history_detail(run_id: str):
    """Get single backtest detail including trades and equity curve."""
    try:
        return backtest_service.get_history_detail(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{run_id}")
async def delete_history_item(run_id: str):
    """Delete a single backtest result."""
    deleted = backtest_service.delete_history_item(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return {"deleted": True, "run_id": run_id}


@router.delete("/history")
async def delete_all_history():
    """Delete all backtest history."""
    count = backtest_service.delete_all_history()
    return {"deleted": count}
