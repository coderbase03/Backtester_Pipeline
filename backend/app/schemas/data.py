"""
Pydantic schemas for data endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class DataDownloadRequest(BaseModel):
    symbol: str
    source: str = "tradingview"
    exchange: Optional[str] = None
    interval: str = "1h"
    n_bars: int = Field(default=1000, ge=100, le=10000)


class BulkDownloadRequest(BaseModel):
    symbols: list[str]
    source: str = "tradingview"
    exchange: Optional[str] = None
    interval: str = "1h"
    n_bars: int = 1000


class SymbolInfo(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    intervals: list[str] = []
    bar_count: int = 0


class DataDownloadResponse(BaseModel):
    symbol: str
    bars_downloaded: int
    interval: str
    success: bool
    error: Optional[str] = None
