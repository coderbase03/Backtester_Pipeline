"""
TradingView Data Fetcher using tvdatafeed

Supports: Stocks, Crypto, Forex, Futures from TradingView
Timeframes: 1m, 3m, 5m, 15m, 30m, 45m, 1h, 2h, 3h, 4h, 1d, 1w, 1M
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Literal
import logging

try:
    from tvDatafeed import TvDatafeed, Interval
    TV_AVAILABLE = True
except ImportError:
    TV_AVAILABLE = False
    
logger = logging.getLogger(__name__)


# Interval mapping
INTERVAL_MAP = {
    '1m': 'in_1_minute',
    '3m': 'in_3_minute',
    '5m': 'in_5_minute',
    '15m': 'in_15_minute',
    '30m': 'in_30_minute',
    '45m': 'in_45_minute',
    '1h': 'in_1_hour',
    '2h': 'in_2_hour',
    '3h': 'in_3_hour',
    '4h': 'in_4_hour',
    '1d': 'in_daily',
    '1w': 'in_weekly',
    '1M': 'in_monthly',
}


class TradingViewFetcher:
    """
    Fetches historical data from TradingView via tvdatafeed.
    
    Usage:
        fetcher = TradingViewFetcher()
        df = fetcher.get_data('AAPL', 'NASDAQ', '1h', n_bars=1000)
    """
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize TradingView connection.
        
        Args:
            username: TradingView username (optional, for extended data)
            password: TradingView password (optional)
        """
        if not TV_AVAILABLE:
            raise ImportError("tvdatafeed not installed. Run: pip install tvdatafeed")
        
        # Login for extended data, or use anonymous
        if username and password:
            self.tv = TvDatafeed(username, password)
            logger.info("TradingView: Logged in as %s", username)
        else:
            self.tv = TvDatafeed()
            logger.info("TradingView: Connected anonymously")
    
    def get_data(
        self,
        symbol: str,
        exchange: str,
        interval: str = '1d',
        n_bars: int = 1000,
        fut_contract: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from TradingView.
        
        Args:
            symbol: Asset symbol (e.g., 'AAPL', 'BTCUSDT', 'EURUSD')
            exchange: Exchange name (e.g., 'NASDAQ', 'BINANCE', 'FX')
            interval: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d', '1w')
            n_bars: Number of bars to fetch (max 5000)
            fut_contract: Futures contract month (1=front, 2=next, etc.)
            
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: datetime
        """
        # Map interval string to tvdatafeed Interval
        if interval not in INTERVAL_MAP:
            raise ValueError(f"Invalid interval: {interval}. Valid: {list(INTERVAL_MAP.keys())}")
        
        tv_interval = getattr(Interval, INTERVAL_MAP[interval])
        
        try:
            df = self.tv.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=tv_interval,
                n_bars=min(n_bars, 5000),  # Max 5000 bars
                fut_contract=fut_contract
            )
            
            if df is None or df.empty:
                logger.warning("No data returned for %s:%s", exchange, symbol)
                return pd.DataFrame()
            
            # Standardize column names (lowercase)
            df.columns = df.columns.str.lower()
            
            # Ensure required columns exist
            required = ['open', 'high', 'low', 'close', 'volume']
            for col in required:
                if col not in df.columns:
                    df[col] = 0
            
            logger.info("Fetched %d bars for %s:%s (%s)", len(df), exchange, symbol, interval)
            return df[required]
            
        except Exception as e:
            logger.error("Failed to fetch %s:%s - %s", exchange, symbol, str(e))
            raise
    
    def get_crypto(
        self,
        symbol: str,
        exchange: str = 'BINANCE',
        interval: str = '1h',
        n_bars: int = 1000
    ) -> pd.DataFrame:
        """Convenience method for crypto data."""
        return self.get_data(symbol, exchange, interval, n_bars)
    
    def get_forex(
        self,
        pair: str,
        interval: str = '1h',
        n_bars: int = 1000
    ) -> pd.DataFrame:
        """Convenience method for forex data."""
        return self.get_data(pair, 'FX_IDC', interval, n_bars)
    
    def get_stock(
        self,
        symbol: str,
        exchange: str = 'NASDAQ',
        interval: str = '1d',
        n_bars: int = 1000
    ) -> pd.DataFrame:
        """Convenience method for stock data."""
        return self.get_data(symbol, exchange, interval, n_bars)


# Common exchange mappings for convenience
EXCHANGES = {
    # US Stocks
    'NYSE': 'NYSE',
    'NASDAQ': 'NASDAQ',
    'AMEX': 'AMEX',
    
    # Crypto
    'BINANCE': 'BINANCE',
    'COINBASE': 'COINBASE',
    'BYBIT': 'BYBIT',
    'OKX': 'OKX',
    
    # Forex
    'FOREX': 'FX_IDC',
    'FX': 'FX_IDC',
    
    # Futures
    'CME': 'CME',
    'COMEX': 'COMEX',
    'NYMEX': 'NYMEX',
    
    # International
    'LSE': 'LSE',
    'BIST': 'BIST',  # Turkey
    'NSE': 'NSE',    # India
}
