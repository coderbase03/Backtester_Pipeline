"""
Backtest result persistence model.

Stores historical backtest runs, trades, and equity curves.
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func

from ..core.database import Base


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), unique=True, nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(50))
    interval = Column(String(10))
    source = Column(String(20))

    initial_cash = Column(Float)
    final_value = Column(Float)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown_pct = Column(Float)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    total_trades = Column(Integer)
    sqn = Column(Float)

    parameters = Column(Text)  # JSON string
    trades_json = Column(Text)  # JSON array
    equity_curve_json = Column(Text)  # JSON array

    created_at = Column(DateTime, server_default=func.now())
