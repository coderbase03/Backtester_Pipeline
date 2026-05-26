"""
Backtest service - wraps the core BacktestEngine for API use.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Optional
from math import isfinite

import pandas as pd

ENGINE_ROOT = Path(__file__).resolve().parents[3]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.backtest.engine import BacktestEngine
from src.data.database import Database
from src.strategies import SupertrendStrategy, SMACrossover, RSIMeanReversion, SMCStrategy

logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "supertrend": SupertrendStrategy,
    "sma": SMACrossover,
    "rsi": RSIMeanReversion,
    "smc": SMCStrategy,
}


def get_strategy_class(name: str):
    """Resolve strategy name to class."""
    key = name.lower().replace(" ", "_").replace("-", "_")
    cls = STRATEGY_MAP.get(key)
    if cls is None:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(STRATEGY_MAP.keys())}")
    return cls


def list_strategies() -> list[dict]:
    """Return metadata for all available strategies."""
    result = []
    for name, cls in STRATEGY_MAP.items():
        params = {}
        if hasattr(cls, "params") and isinstance(cls.params, tuple):
            for p in cls.params:
                if isinstance(p, tuple) and len(p) == 2:
                    params[p[0]] = p[1]
        result.append({
            "name": name,
            "class_name": cls.__name__,
            "description": (cls.__doc__ or "").strip().split("\n")[0],
            "category": "built-in",
            "params": params,
        })
    return result


def run_backtest(
    strategy_name: str,
    symbol: str,
    source: str = "tradingview",
    exchange: Optional[str] = None,
    interval: str = "1h",
    n_bars: int = 1000,
    initial_cash: float = 100,
    commission: float = 0.0005,
    slippage_ticks: Optional[int] = None,
    strategy_params: Optional[dict] = None,
    instant_execution: bool = True,
) -> dict:
    """Run a single backtest and return results dict."""
    strategy_cls = get_strategy_class(strategy_name)
    ok, reason = ensure_data_available(
        symbol=symbol,
        exchange=exchange,
        interval=interval,
        n_bars=n_bars,
        source=source,
    )
    if not ok:
        raise RuntimeError(f"Data unavailable for {symbol}/{interval}: {reason}")
    engine = BacktestEngine()

    result = engine.run(
        strategy=strategy_cls,
        symbol=symbol,
        source=source,
        exchange=exchange,
        interval=interval,
        n_bars=n_bars,
        initial_cash=initial_cash,
        commission=commission,
        slippage_ticks=slippage_ticks,
        strategy_params=strategy_params,
        instant_execution=instant_execution,
    )

    if result is None:
        raise RuntimeError("Backtest returned no results")

    detailed = engine.results.analyzers.detailed.get_analysis()

    return {
        "run_id": engine.run_id,
        "strategy": strategy_cls.__name__,
        "symbol": symbol,
        "interval": interval,
        "total_return": result.get("total_return", 0) or 0,
        "sharpe_ratio": result.get("sharpe_ratio", 0) or 0,
        "sortino_ratio": result.get("sortino_ratio"),
        "max_drawdown_pct": result.get("max_drawdown_pct", 0) or 0,
        "win_rate": result.get("win_rate", 0) or 0,
        "profit_factor": result.get("profit_factor", 0) or 0,
        "total_trades": result.get("total_trades", 0) or 0,
        "sqn": result.get("sqn"),
        "initial_cash": initial_cash,
        "final_value": result.get("final_value", initial_cash),
        "trades": detailed.get("trades", []),
        "equity_curve": detailed.get("equity_curve", []),
        "buy_hold_return": detailed.get("buy_hold_return"),
        "parameters": strategy_params,
    }


def run_multi_backtest(
    strategy_name: str,
    symbols: list[str],
    source: str = "tradingview",
    exchange: Optional[str] = None,
    intervals: list[str] | None = None,
    n_bars: int = 1000,
    initial_cash: float = 100,
    commission: float = 0.0005,
    slippage_ticks: Optional[int] = None,
    strategy_params: Optional[dict] = None,
) -> list[dict]:
    """Run backtests across multiple symbols/intervals."""
    intervals = intervals or ["1h"]
    results = []

    for symbol in symbols:
        for interval in intervals:
            try:
                r = run_backtest(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    source=source,
                    exchange=exchange,
                    interval=interval,
                    n_bars=n_bars,
                    initial_cash=initial_cash,
                    commission=commission,
                    slippage_ticks=slippage_ticks,
                    strategy_params=strategy_params,
                )
                results.append(r)
            except Exception as e:
                logger.warning("Backtest failed for %s/%s: %s", symbol, interval, e)
                results.append({
                    "run_id": "",
                    "strategy": strategy_name,
                    "symbol": symbol,
                    "interval": interval,
                    "error": str(e),
                    "total_return": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown_pct": 0,
                    "win_rate": 0,
                    "profit_factor": 0,
                    "total_trades": 0,
                    "initial_cash": initial_cash,
                    "final_value": initial_cash,
                    "trades": [],
                    "equity_curve": [],
                })
    return results


def _cached_bar_count(symbol: str, interval: str, exchange: Optional[str]) -> int:
    db = _get_db()
    try:
        df = db.load_ohlcv(symbol=symbol, timeframe=interval, exchange=exchange)
        return 0 if df.empty else len(df)
    finally:
        db.close()


def ensure_data_available(
    symbol: str,
    exchange: Optional[str],
    interval: str,
    n_bars: int,
    source: str = "tradingview",
) -> tuple[bool, str]:
    """Ensure local DB has enough bars; try download when missing."""
    available = _cached_bar_count(symbol=symbol, interval=interval, exchange=exchange)
    if available >= n_bars:
        return True, "cache_ok"

    from . import data_service

    dl = data_service.download_data(
        symbol=symbol,
        source=source,
        exchange=exchange,
        interval=interval,
        n_bars=n_bars,
    )
    if not dl.get("success"):
        return False, f"download_failed: {dl.get('error') or 'unknown'}"

    after = _cached_bar_count(symbol=symbol, interval=interval, exchange=exchange)
    if after < n_bars:
        return False, f"insufficient_bars_after_download: {after}/{n_bars}"

    return True, "download_ok"


def run_multi_analyze(
    strategy_name: str,
    symbols: list[str],
    source: str = "tradingview",
    exchange: Optional[str] = None,
    intervals: list[str] | None = None,
    n_bars: int = 1000,
    initial_cash: float = 100,
    commission: float = 0.0005,
    slippage_ticks: Optional[int] = 2,
    strategy_params: Optional[dict] = None,
) -> dict:
    intervals = intervals or ["1h"]
    rows: list[dict] = []
    failures: list[dict] = []

    for symbol in symbols:
        for interval in intervals:
            ok, reason = ensure_data_available(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars,
                source=source,
            )
            if not ok:
                failures.append({"symbol": symbol, "interval": interval, "reason": reason})
                rows.append({
                    "symbol": symbol,
                    "interval": interval,
                    "run_id": "",
                    "total_return": 0,
                    "sharpe": 0,
                    "max_dd": 0,
                    "win_rate": 0,
                    "pf": 0,
                    "trades": 0,
                    "status": "failed",
                    "error": reason,
                })
                continue

            try:
                r = run_backtest(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    source=source,
                    exchange=exchange,
                    interval=interval,
                    n_bars=n_bars,
                    initial_cash=initial_cash,
                    commission=commission,
                    slippage_ticks=slippage_ticks,
                    strategy_params=strategy_params,
                )
                rows.append({
                    "symbol": symbol,
                    "interval": interval,
                    "run_id": r.get("run_id", ""),
                    "total_return": r.get("total_return", 0),
                    "sharpe": r.get("sharpe_ratio", 0),
                    "max_dd": r.get("max_drawdown_pct", 0),
                    "win_rate": r.get("win_rate", 0),
                    "pf": r.get("profit_factor", 0),
                    "trades": r.get("total_trades", 0),
                    "status": "success",
                })
            except Exception as e:
                reason = str(e)
                failures.append({"symbol": symbol, "interval": interval, "reason": reason})
                rows.append({
                    "symbol": symbol,
                    "interval": interval,
                    "run_id": "",
                    "total_return": 0,
                    "sharpe": 0,
                    "max_dd": 0,
                    "win_rate": 0,
                    "pf": 0,
                    "trades": 0,
                    "status": "failed",
                    "error": reason,
                })

    success_rows = [r for r in rows if r["status"] == "success"]
    total = len(rows)
    success = len(success_rows)
    failed = total - success
    avg_return = sum(r["total_return"] for r in success_rows) / success if success else 0
    avg_sharpe = sum(r["sharpe"] for r in success_rows) / success if success else 0
    best = max(success_rows, key=lambda x: x["sharpe"], default=None)
    worst = min(success_rows, key=lambda x: x["sharpe"], default=None)

    return {
        "rows": rows,
        "summary": {
            "total": total,
            "success": success,
            "failed": failed,
            "avg_return": avg_return,
            "avg_sharpe": avg_sharpe,
            "best": best,
            "worst": worst,
        },
        "failures": failures,
    }


def _get_db() -> Database:
    return Database()


def _sanitize_value(value):
    """Convert NaN/inf and pandas null-like values to JSON-safe values."""
    if value is None:
        return None

    if isinstance(value, (dict, list, tuple)):
        return value

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, float) and not isfinite(value):
        return None

    return value


def _sanitize_record(record: dict) -> dict:
    cleaned = {}
    for key, value in record.items():
        if isinstance(value, dict):
            cleaned[key] = {k: _sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            cleaned[key] = [
                {k: _sanitize_value(v) for k, v in item.items()} if isinstance(item, dict) else _sanitize_value(item)
                for item in value
            ]
        else:
            cleaned[key] = _sanitize_value(value)
    return cleaned


def get_history(
    limit: int = 50,
    strategy: Optional[str] = None,
    symbol: Optional[str] = None,
) -> list[dict]:
    """Get backtest history (summary list) from DB, with optional filters."""
    db = _get_db()
    try:
        df = db.get_backtest_history(limit=limit)
        if df.empty:
            return []

        if strategy:
            df = df[df["strategy_name"].str.lower() == strategy.lower()]
        if symbol:
            df = df[df["symbol"].str.upper() == symbol.upper()]

        # Summary payload only (avoid heavy list payload in history table)
        for col in ("equity_curve_json", "drawdown_curve_json"):
            if col in df.columns:
                df = df.drop(columns=[col])

        records = df.to_dict(orient="records")
        for r in records:
            for k in ("parameters",):
                val = r.get(k)
                if val and isinstance(val, str):
                    try:
                        r[k] = json.loads(val)
                    except Exception:
                        pass
        return [_sanitize_record(r) for r in records]
    finally:
        db.close()


def get_history_detail(run_id: str) -> dict:
    """Get single backtest detail including trades."""
    db = _get_db()
    try:
        bt = db.get_backtest_by_id(run_id)
        if not bt:
            raise ValueError(f"Backtest not found: {run_id}")

        for k in ("equity_curve_json", "drawdown_curve_json", "parameters"):
            val = bt.get(k)
            if val and isinstance(val, str):
                try:
                    bt[k] = json.loads(val)
                except Exception:
                    pass

        trades_df = db.get_trades_by_run_id(run_id)
        bt["trades"] = trades_df.to_dict(orient="records") if not trades_df.empty else []
        return _sanitize_record(bt)
    finally:
        db.close()


def delete_history_item(run_id: str) -> bool:
    db = _get_db()
    try:
        return db.delete_backtest(run_id)
    finally:
        db.close()


def delete_all_history() -> int:
    db = _get_db()
    try:
        count = db.delete_all_backtests()
        db.delete_all_optimizations()
        return count
    finally:
        db.close()
