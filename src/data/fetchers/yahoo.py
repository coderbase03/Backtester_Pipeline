"""
Yahoo Finance Data Fetcher

Free unlimited data for stocks, ETFs, crypto, forex
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

logger = logging.getLogger(__name__)


# Interval mapping to yfinance format
INTERVAL_MAP = {
    '1m': '1m',      # Last 7 days only
    '2m': '2m',      # Last 60 days
    '5m': '5m',      # Last 60 days
    '15m': '15m',    # Last 60 days
    '30m': '30m',    # Last 60 days
    '1h': '1h',      # Last 730 days
    '4h': '4h',      # Last 730 days (actually 60m * 4)
    '1d': '1d',      # Full history
    '1w': '1wk',
    '1M': '1mo',
}


class YahooFetcher:
    """
    Fetches historical data from Yahoo Finance.
    
    Usage:
        fetcher = YahooFetcher()
        df = fetcher.get_data('AAPL', interval='1d', period='1y')
    """
    
    def __init__(self):
        if not YF_AVAILABLE:
            raise ImportError("yfinance not installed. Run: pip install yfinance")
        logger.info("Yahoo Finance fetcher initialized")
    
    def get_data(
        self,
        symbol: str,
        interval: str = '1d',
        start: Optional[str] = None,
        end: Optional[str] = None,
        period: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Yahoo Finance.
        
        Args:
            symbol: Yahoo Finance symbol (e.g., 'AAPL', 'BTC-USD', 'EURUSD=X')
            interval: Timeframe ('1m', '5m', '15m', '1h', '1d', '1w')
            start: Start date (YYYY-MM-DD) - use with end
            end: End date (YYYY-MM-DD) - use with start
            period: Period string ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
            
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: datetime
        """
        if interval not in INTERVAL_MAP:
            raise ValueError(f"Invalid interval: {interval}. Valid: {list(INTERVAL_MAP.keys())}")
        
        yf_interval = INTERVAL_MAP[interval]
        
        # Handle 4h specially (yfinance doesn't support it natively)
        if interval == '4h':
            yf_interval = '1h'
        
        try:
            ticker = yf.Ticker(symbol)
            
            if start and end:
                df = ticker.history(start=start, end=end, interval=yf_interval)
            elif period:
                df = ticker.history(period=period, interval=yf_interval)
            else:
                # Default to 1 year
                df = ticker.history(period='1y', interval=yf_interval)
            
            if df.empty:
                logger.warning("No data returned for %s", symbol)
                return pd.DataFrame()
            
            # Standardize column names
            df.columns = df.columns.str.lower()
            
            # Select and rename columns
            result = df[['open', 'high', 'low', 'close', 'volume']].copy()
            
            # Resample to 4h if needed
            if interval == '4h':
                result = self._resample_to_4h(result)
            
            logger.info("Fetched %d bars for %s (%s)", len(result), symbol, interval)
            return result
            
        except Exception as e:
            logger.error("Failed to fetch %s - %s", symbol, str(e))
            raise
    
    def _resample_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample 1h data to 4h."""
        return df.resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    
    def get_crypto(
        self,
        symbol: str,
        interval: str = '1h',
        period: str = '1y'
    ) -> pd.DataFrame:
        """
        Convenience method for crypto data.
        Automatically appends -USD if not present.
        """
        if not symbol.endswith('-USD') and not symbol.endswith('-USDT'):
            symbol = f"{symbol}-USD"
        return self.get_data(symbol, interval=interval, period=period)
    
    def get_forex(
        self,
        pair: str,
        interval: str = '1h',
        period: str = '1y'
    ) -> pd.DataFrame:
        """
        Convenience method for forex data.
        Automatically appends =X if not present.
        """
        if not pair.endswith('=X'):
            pair = f"{pair}=X"
        return self.get_data(pair, interval=interval, period=period)
    
    def search(self, query: str) -> list:
        """Search for ticker symbols."""
        try:
            results = yf.Ticker(query).info
            return [{'symbol': query, 'name': results.get('shortName', '')}]
        except:
            return []


# Common symbol mappings
SYMBOL_TYPES = {
    # Crypto (append -USD)
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'SOL': 'SOL-USD',
    
    # Forex (append =X)
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    
    # Indices
    'SPY': 'SPY',
    'QQQ': 'QQQ',
    'DIA': 'DIA',
}
