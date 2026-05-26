"""
PostgreSQL-backed database handler for market data and backtest results.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_db_url() -> str:
    return os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or "postgresql://opus:opus@localhost:5432/opus_backtrader"


class Database:
    """SQL database wrapper (PostgreSQL-first) for OHLCV and backtest tables."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or _default_db_url()
        self.engine: Engine = create_engine(self.db_url, pool_pre_ping=True, future=True)
        self._create_tables()
        logger.info("Database initialized: %s", self.db_url)

    def _create_tables(self):
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS ohlcv (
                id BIGSERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                exchange TEXT,
                timeframe TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                UNIQUE(symbol, exchange, timeframe, timestamp)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS backtest_results (
                id BIGSERIAL PRIMARY KEY,
                run_id TEXT UNIQUE,
                strategy_name TEXT,
                symbol TEXT,
                timeframe TEXT,
                start_date TEXT,
                end_date TEXT,
                initial_cash DOUBLE PRECISION,
                final_value DOUBLE PRECISION,
                total_return DOUBLE PRECISION,
                sharpe_ratio DOUBLE PRECISION,
                sortino_ratio DOUBLE PRECISION,
                calmar_ratio DOUBLE PRECISION,
                max_drawdown DOUBLE PRECISION,
                avg_drawdown DOUBLE PRECISION,
                win_rate DOUBLE PRECISION,
                total_trades INTEGER,
                won_trades INTEGER,
                lost_trades INTEGER,
                profit_factor DOUBLE PRECISION,
                avg_win DOUBLE PRECISION,
                avg_loss DOUBLE PRECISION,
                avg_trade DOUBLE PRECISION,
                sqn DOUBLE PRECISION,
                buy_hold_return DOUBLE PRECISION,
                parameters JSONB,
                equity_curve_json JSONB,
                drawdown_curve_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS trades (
                id BIGSERIAL PRIMARY KEY,
                run_id TEXT,
                trade_num INTEGER,
                direction TEXT,
                entry_time TEXT,
                entry_price DOUBLE PRECISION,
                exit_time TEXT,
                exit_price DOUBLE PRECISION,
                size DOUBLE PRECISION,
                pnl DOUBLE PRECISION,
                pnl_pct DOUBLE PRECISION,
                FOREIGN KEY (run_id) REFERENCES backtest_results(run_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS optimization_runs (
                id BIGSERIAL PRIMARY KEY,
                run_id TEXT UNIQUE,
                strategy_name TEXT,
                symbol TEXT,
                exchange TEXT,
                timeframe TEXT,
                n_bars INTEGER,
                metric TEXT,
                trade_direction TEXT,
                param_grid JSONB,
                total_combinations INTEGER,
                best_params JSONB,
                best_metric_value DOUBLE PRECISION,
                best_return DOUBLE PRECISION,
                best_sharpe DOUBLE PRECISION,
                best_win_rate DOUBLE PRECISION,
                all_results_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf ON ohlcv(symbol, timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON backtest_results(strategy_name)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_lookup ON backtest_results(run_id, strategy_name, symbol, timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_trades_run_time ON trades(run_id, entry_time, exit_time)",
        ]
        with self.engine.begin() as conn:
            for stmt in ddl:
                conn.execute(text(stmt))

    def save_ohlcv(self, symbol: str, timeframe: str, df: pd.DataFrame, exchange: str = None):
        if df.empty:
            return
        data = df.reset_index().copy()
        data.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        data["symbol"] = symbol
        data["exchange"] = exchange
        data["timeframe"] = timeframe

        sql = text(
            """
            INSERT INTO ohlcv (symbol, exchange, timeframe, timestamp, open, high, low, close, volume)
            VALUES (:symbol, :exchange, :timeframe, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (symbol, exchange, timeframe, timestamp)
            DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume
            """
        )
        rows = []
        for _, row in data.iterrows():
            rows.append({
                "symbol": row["symbol"],
                "exchange": row["exchange"],
                "timeframe": row["timeframe"],
                "timestamp": pd.to_datetime(row["timestamp"]).to_pydatetime(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        with self.engine.begin() as conn:
            conn.execute(sql, rows)
        logger.info("Saved %d bars for %s (%s)", len(rows), symbol, timeframe)

    def load_ohlcv(self, symbol: str, timeframe: str, start: Optional[str] = None, end: Optional[str] = None, exchange: str = None) -> pd.DataFrame:
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = :symbol AND timeframe = :timeframe
        """
        params = {"symbol": symbol, "timeframe": timeframe}
        if exchange:
            query += " AND exchange = :exchange"
            params["exchange"] = exchange
        if start:
            query += " AND timestamp >= :start"
            params["start"] = start
        if end:
            query += " AND timestamp <= :end"
            params["end"] = end
        query += " ORDER BY timestamp"
        df = pd.read_sql_query(text(query), self.engine, params=params)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        return df

    def save_backtest(self, run_id: str, strategy_name: str, symbol: str, timeframe: str, results: dict, parameters: dict = None, equity_curve: list = None, drawdown_curve: list = None, buy_hold_return: float = None):
        stmt = text(
            """
            INSERT INTO backtest_results
            (run_id, strategy_name, symbol, timeframe, start_date, end_date,
             initial_cash, final_value, total_return, sharpe_ratio, sortino_ratio,
             calmar_ratio, max_drawdown, avg_drawdown, win_rate, total_trades,
             won_trades, lost_trades, profit_factor, avg_win, avg_loss, avg_trade,
             sqn, buy_hold_return, parameters, equity_curve_json, drawdown_curve_json)
            VALUES
            (:run_id, :strategy_name, :symbol, :timeframe, :start_date, :end_date,
             :initial_cash, :final_value, :total_return, :sharpe_ratio, :sortino_ratio,
             :calmar_ratio, :max_drawdown, :avg_drawdown, :win_rate, :total_trades,
             :won_trades, :lost_trades, :profit_factor, :avg_win, :avg_loss, :avg_trade,
             :sqn, :buy_hold_return, CAST(:parameters AS jsonb), CAST(:equity_curve_json AS jsonb), CAST(:drawdown_curve_json AS jsonb))
            ON CONFLICT (run_id) DO UPDATE SET
             final_value=EXCLUDED.final_value, total_return=EXCLUDED.total_return, sharpe_ratio=EXCLUDED.sharpe_ratio,
             max_drawdown=EXCLUDED.max_drawdown, win_rate=EXCLUDED.win_rate, total_trades=EXCLUDED.total_trades,
             profit_factor=EXCLUDED.profit_factor, parameters=EXCLUDED.parameters, equity_curve_json=EXCLUDED.equity_curve_json,
             drawdown_curve_json=EXCLUDED.drawdown_curve_json
            """
        )
        payload = {
            "run_id": run_id,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": results.get("start_date"),
            "end_date": results.get("end_date"),
            "initial_cash": results.get("initial_cash"),
            "final_value": results.get("final_value"),
            "total_return": results.get("total_return"),
            "sharpe_ratio": results.get("sharpe_ratio"),
            "sortino_ratio": results.get("sortino_ratio", 0),
            "calmar_ratio": results.get("calmar_ratio", 0),
            "max_drawdown": results.get("max_drawdown_pct") or results.get("max_drawdown", 0),
            "avg_drawdown": results.get("avg_drawdown", 0),
            "win_rate": results.get("win_rate"),
            "total_trades": results.get("total_trades"),
            "won_trades": results.get("won_trades", 0),
            "lost_trades": results.get("lost_trades", 0),
            "profit_factor": results.get("profit_factor", 0),
            "avg_win": results.get("avg_win", 0),
            "avg_loss": results.get("avg_loss", 0),
            "avg_trade": results.get("avg_trade", 0),
            "sqn": results.get("sqn", 0),
            "buy_hold_return": buy_hold_return or 0,
            "parameters": json.dumps(parameters) if parameters else "null",
            "equity_curve_json": json.dumps(equity_curve) if equity_curve else "[]",
            "drawdown_curve_json": json.dumps(drawdown_curve) if drawdown_curve else "[]",
        }
        with self.engine.begin() as conn:
            conn.execute(stmt, payload)

    def get_cached_symbols_with_stats(self) -> List[dict]:
        query = text(
            """
            SELECT symbol, exchange, array_agg(DISTINCT timeframe) AS intervals, COUNT(*) AS bar_count
            FROM ohlcv
            GROUP BY symbol, exchange
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [{"symbol": r["symbol"], "exchange": r["exchange"], "intervals": list(r["intervals"] or []), "bar_count": r["bar_count"]} for r in rows]

    def get_data_summary(self) -> List[dict]:
        query = text(
            """
            SELECT symbol, exchange, timeframe,
                   COUNT(*) AS bars,
                   MIN(timestamp) AS first_date,
                   MAX(timestamp) AS last_date
            FROM ohlcv
            GROUP BY symbol, exchange, timeframe
            ORDER BY symbol, timeframe
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(r) for r in rows]

    def clear_ohlcv(self, symbol: str = None, timeframe: str = None):
        where = ["1=1"]
        params = {}
        if symbol:
            where.append("symbol = :symbol")
            params["symbol"] = symbol
        if timeframe:
            where.append("timeframe = :timeframe")
            params["timeframe"] = timeframe
        stmt = text(f"DELETE FROM ohlcv WHERE {' AND '.join(where)}")
        with self.engine.begin() as conn:
            conn.execute(stmt, params)

    def get_backtest_history(self, limit: int = 50) -> pd.DataFrame:
        return pd.read_sql_query(text("SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT :limit"), self.engine, params={"limit": limit})

    def delete_backtest(self, run_id: str) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM trades WHERE run_id = :run_id"), {"run_id": run_id})
            res = conn.execute(text("DELETE FROM backtest_results WHERE run_id = :run_id"), {"run_id": run_id})
            return res.rowcount > 0

    def delete_all_backtests(self) -> int:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM trades"))
            res = conn.execute(text("DELETE FROM backtest_results"))
            return res.rowcount

    def delete_all_optimizations(self) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(text("DELETE FROM optimization_runs"))
            return res.rowcount

    def get_backtest_by_id(self, run_id: str) -> Optional[dict]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM backtest_results WHERE run_id = :run_id"), {"run_id": run_id}).mappings().first()
            return dict(row) if row else None

    def get_trades_by_run_id(self, run_id: str) -> pd.DataFrame:
        return pd.read_sql_query(
            text("SELECT trade_num, direction, entry_time, entry_price, exit_time, exit_price, size, pnl, pnl_pct FROM trades WHERE run_id = :run_id ORDER BY trade_num"),
            self.engine,
            params={"run_id": run_id},
        )

    def save_trades(self, run_id: str, trades: List[dict]):
        if not trades:
            return
        stmt = text(
            """
            INSERT INTO trades (run_id, trade_num, direction, entry_time, entry_price, exit_time, exit_price, size, pnl, pnl_pct)
            VALUES (:run_id, :trade_num, :direction, :entry_time, :entry_price, :exit_time, :exit_price, :size, :pnl, :pnl_pct)
            """
        )
        rows = [{"run_id": run_id, **t} for t in trades]
        with self.engine.begin() as conn:
            conn.execute(stmt, rows)

    def close(self):
        self.engine.dispose()
