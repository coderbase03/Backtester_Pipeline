"""
OHLCV market data model.

Unified from the old trading.db ohlcv table.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func

from ..core.database import Base


class OHLCV(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(50), nullable=True)
    interval = Column(String(10), nullable=False)
    datetime = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0)

    __table_args__ = (
        Index("ix_ohlcv_lookup", "symbol", "exchange", "interval", "datetime", unique=True),
    )
