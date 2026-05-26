"""
Pydantic schemas for backtest endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BacktestRequest(BaseModel):
    strategy: str = Field(..., description="Strategy name: supertrend, sma, rsi, smc")
    symbol: str = Field(..., description="Trading symbol e.g. BTCUSDT, AAPL")
    source: str = Field(default="tradingview", description="Data source: tradingview, yahoo, ccxt")
    exchange: Optional[str] = Field(default=None, description="Exchange e.g. BINANCE, NASDAQ")
    interval: str = Field(default="1h", description="Timeframe: 1m,5m,15m,30m,1h,4h,1d,1w")
    n_bars: int = Field(default=1000, ge=100, le=10000)
    initial_cash: float = Field(default=100)
    commission: float = Field(default=0.0005)
    slippage_ticks: Optional[int] = Field(default=2, ge=0)
    strategy_params: Optional[dict] = None
    instant_execution: bool = True


class BacktestMultiRequest(BaseModel):
    strategy: str
    symbols: list[str]
    source: str = "tradingview"
    exchange: Optional[str] = None
    intervals: list[str] = ["1h"]
    n_bars: int = Field(default=1000, ge=100, le=10000)
    initial_cash: float = 100
    commission: float = 0.0005
    slippage_ticks: Optional[int] = Field(default=2, ge=0)
    strategy_params: Optional[dict] = None


class BacktestMultiAnalyzeRequest(BaseModel):
    strategy: str
    symbols: list[str]
    source: str = "tradingview"
    exchange: Optional[str] = None
    intervals: list[str] = ["1h"]
    n_bars: int = Field(default=1000, ge=100, le=10000)
    initial_cash: float = 100
    commission: float = 0.0005
    slippage_ticks: Optional[int] = Field(default=2, ge=0)
    strategy_params: Optional[dict] = None


class TradeInfo(BaseModel):
    trade_num: int
    direction: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    commission: float
    bars_held: Optional[int] = None


class BacktestResponse(BaseModel):
    run_id: str
    strategy: str
    symbol: str
    interval: str
    total_return: float
    sharpe_ratio: float
    sortino_ratio: Optional[float] = None
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    sqn: Optional[float] = None
    initial_cash: float
    final_value: float
    trades: list[TradeInfo] = []
    equity_curve: list[dict] = []
    buy_hold_return: Optional[float] = None
    parameters: Optional[dict] = None
    created_at: Optional[datetime] = None


class BacktestHistoryItem(BaseModel):
    run_id: str
    strategy_name: str
    symbol: str
    interval: Optional[str] = None
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    created_at: Optional[datetime] = None
