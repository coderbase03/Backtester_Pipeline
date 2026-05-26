"""
CCXT Data Fetcher - Crypto Exchange Unified API

Supports 100+ crypto exchanges
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import logging

try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

logger = logging.getLogger(__name__)


# Timeframe mapping
TIMEFRAME_MAP = {
    '1m': '1m',
    '3m': '3m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1h': '1h',
    '2h': '2h',
    '4h': '4h',
    '6h': '6h',
    '8h': '8h',
    '12h': '12h',
    '1d': '1d',
    '3d': '3d',
    '1w': '1w',
    '1M': '1M',
}


class CCXTFetcher:
    """
    Fetches crypto data from 100+ exchanges via CCXT.
    
    Usage:
        fetcher = CCXTFetcher('binance')
        df = fetcher.get_data('BTC/USDT', '1h', limit=1000)
    """
    
    def __init__(
        self,
        exchange: str = 'binance',
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        """
        Initialize CCXT exchange connection.
        
        Args:
            exchange: Exchange name (binance, bybit, okx, etc.)
            api_key: Optional API key for authenticated requests
            api_secret: Optional API secret
        """
        if not CCXT_AVAILABLE:
            raise ImportError("ccxt not installed. Run: pip install ccxt")
        
        exchange_class = getattr(ccxt, exchange.lower(), None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{exchange}' not supported. Available: {ccxt.exchanges}")
        
        config = {'enableRateLimit': True}
        if api_key and api_secret:
            config['apiKey'] = api_key
            config['secret'] = api_secret
        
        self.exchange = exchange_class(config)
        self.exchange_name = exchange
        logger.info("CCXT: Connected to %s", exchange)
    
    def get_data(
        self,
        symbol: str,
        interval: str = '1h',
        limit: int = 1000,
        since: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from exchange.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT', 'ETH/BTC')
            interval: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles (exchange-dependent max)
            since: Start datetime (optional)
            
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: datetime
        """
        if interval not in TIMEFRAME_MAP:
            raise ValueError(f"Invalid interval: {interval}. Valid: {list(TIMEFRAME_MAP.keys())}")
        
        timeframe = TIMEFRAME_MAP[interval]
        
        # Check if exchange supports the timeframe
        if timeframe not in self.exchange.timeframes:
            available = list(self.exchange.timeframes.keys())
            raise ValueError(f"{self.exchange_name} doesn't support {interval}. Available: {available}")
        
        try:
            since_ts = int(since.timestamp() * 1000) if since else None
            
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since_ts,
                limit=limit
            )
            
            if not ohlcv:
                logger.warning("No data returned for %s on %s", symbol, self.exchange_name)
                return pd.DataFrame()
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info("Fetched %d bars for %s from %s (%s)", 
                       len(df), symbol, self.exchange_name, interval)
            
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            logger.error("Failed to fetch %s from %s - %s", 
                        symbol, self.exchange_name, str(e))
            raise
    
    def get_all_symbols(self) -> List[str]:
        """Get all available trading pairs on the exchange."""
        self.exchange.load_markets()
        return list(self.exchange.symbols)
    
    def get_ticker(self, symbol: str) -> dict:
        """Get current ticker information."""
        return self.exchange.fetch_ticker(symbol)


# Supported exchanges (most popular)
SUPPORTED_EXCHANGES = [
    'binance',
    'bybit',
    'okx',
    'kucoin',
    'coinbase',
    'kraken',
    'bitfinex',
    'huobi',
    'gate',
    'mexc',
]
