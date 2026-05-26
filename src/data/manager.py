"""
Unified Data Manager - Single interface for all data sources
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Literal, Union
import logging
import yaml

from .database import Database
from .fetchers import TradingViewFetcher, YahooFetcher, CCXTFetcher

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"

DataSource = Literal['tradingview', 'yahoo', 'ccxt', 'auto']


class DataManager:
    """
    Unified data interface with caching and multiple source support.
    
    Usage:
        dm = DataManager()
        df = dm.get_data('AAPL', source='yahoo', interval='1h')
        df = dm.get_data('BTCUSDT', source='tradingview', exchange='BINANCE')
    """
    
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH):
        """Initialize data manager with configuration."""
        self.config_path = Path(config_path)
        if not self.config_path.is_absolute():
            self.config_path = (PROJECT_ROOT / self.config_path).resolve()

        self.config = self._load_config(self.config_path)
        
        # Initialize database (PostgreSQL-first)
        # Legacy sqlite path in settings is ignored in v2 architecture.
        self.db = Database()
        
        # Lazy-load fetchers
        self._tv_fetcher = None
        self._yahoo_fetcher = None
        self._ccxt_fetchers = {}
        
        # Cache settings
        self.cache_enabled = self.config.get('data', {}).get('cache_enabled', True)
        
        logger.info("DataManager initialized")
    
    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("Config file not found: %s, using defaults", config_path)
            return {}
    
    @property
    def tv(self) -> TradingViewFetcher:
        """Lazy-load TradingView fetcher."""
        if self._tv_fetcher is None:
            try:
                # Try to load credentials
                secrets = self._load_secrets()
                tv_config = secrets.get('tradingview', {})
                self._tv_fetcher = TradingViewFetcher(
                    username=tv_config.get('username'),
                    password=tv_config.get('password')
                )
            except Exception as e:
                logger.warning("TradingView init failed: %s", e)
                self._tv_fetcher = TradingViewFetcher()
        return self._tv_fetcher
    
    @property
    def yahoo(self) -> YahooFetcher:
        """Lazy-load Yahoo fetcher."""
        if self._yahoo_fetcher is None:
            self._yahoo_fetcher = YahooFetcher()
        return self._yahoo_fetcher
    
    def ccxt(self, exchange: str = 'binance') -> CCXTFetcher:
        """Get CCXT fetcher for specific exchange."""
        if exchange not in self._ccxt_fetchers:
            self._ccxt_fetchers[exchange] = CCXTFetcher(exchange)
        return self._ccxt_fetchers[exchange]
    
    def _load_secrets(self) -> dict:
        """Load secrets from secrets.yaml or settings.yaml."""
        # First try dedicated secrets file
        try:
            with open(PROJECT_ROOT / 'config' / 'secrets.yaml', 'r') as f:
                secrets = yaml.safe_load(f) or {}
                if secrets:
                    return secrets
        except FileNotFoundError:
            pass
        
        # Fallback: read from settings.yaml data.tvdatafeed section
        tv_config = self.config.get('data', {}).get('tvdatafeed', {})
        if tv_config and tv_config.get('username'):
            return {'tradingview': tv_config}
        
        return {}
    
    def get_data(
        self,
        symbol: str,
        source: DataSource = 'auto',
        interval: str = '1d',
        exchange: str = None,
        n_bars: int = 1000,
        start: str = None,
        end: str = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch data from specified source with optional caching.
        
        Args:
            symbol: Asset symbol
            source: Data source ('tradingview', 'yahoo', 'ccxt', 'auto')
            interval: Timeframe
            exchange: Exchange name (for tvdatafeed and ccxt)
            n_bars: Number of bars to fetch
            start: Start date (for yahoo)
            end: End date (for yahoo)
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with OHLCV data
        """
        # Check cache first
        if use_cache and self.cache_enabled:
            cached = self.db.load_ohlcv(symbol, interval, start, end, exchange)
            if not cached.empty and len(cached) >= n_bars * 0.9:
                logger.info("Using cached data for %s", symbol)
                return cached
        
        # Auto-detect best source
        if source == 'auto':
            source = self._detect_source(symbol, exchange)
        
        # Fetch from source
        if source == 'tradingview':
            exchange = exchange or self._guess_exchange(symbol)
            df = self.tv.get_data(symbol, exchange, interval, n_bars)
        
        elif source == 'yahoo':
            if start and end:
                df = self.yahoo.get_data(symbol, interval, start=start, end=end)
            else:
                # Convert n_bars to period
                period = self._bars_to_period(n_bars, interval)
                df = self.yahoo.get_data(symbol, interval, period=period)
        
        elif source == 'ccxt':
            exchange = exchange or 'binance'
            # Format symbol for CCXT (e.g., BTCUSDT -> BTC/USDT)
            ccxt_symbol = self._format_ccxt_symbol(symbol)
            df = self.ccxt(exchange).get_data(ccxt_symbol, interval, n_bars)
        
        else:
            raise ValueError(f"Unknown source: {source}")
        
        # Cache the data
        if self.cache_enabled and not df.empty:
            self.db.save_ohlcv(symbol, interval, df, exchange)
            
        return df
    
    def _detect_source(self, symbol: str, exchange: str = None) -> str:
        """Auto-detect best data source for symbol."""
        symbol_upper = symbol.upper()
        
        # Crypto detection
        if any(x in symbol_upper for x in ['USDT', 'BTC', 'ETH', 'BUSD']):
            return 'tradingview'  # Better for crypto than yahoo
        
        # Forex detection
        if any(x in symbol_upper for x in ['USD', 'EUR', 'GBP', 'JPY']) and len(symbol) == 6:
            return 'tradingview'
        
        # Stock - yahoo is reliable
        return 'yahoo'
    
    def _guess_exchange(self, symbol: str) -> str:
        """Guess exchange for TradingView."""
        symbol_upper = symbol.upper()
        
        if 'USDT' in symbol_upper or 'BTC' in symbol_upper:
            return 'BINANCE'
        if any(x in symbol_upper for x in ['USD', 'EUR', 'GBP', 'JPY']):
            return 'FX_IDC'
        
        return 'NASDAQ'  # Default to US stocks
    
    def _format_ccxt_symbol(self, symbol: str) -> str:
        """Format symbol for CCXT (add slash)."""
        if '/' in symbol:
            return symbol
        
        # Common patterns
        for quote in ['USDT', 'BUSD', 'USD', 'BTC', 'ETH']:
            if symbol.upper().endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"
        
        return symbol
    
    def _bars_to_period(self, n_bars: int, interval: str) -> str:
        """Convert number of bars to Yahoo period string."""
        # Approximate days needed
        interval_days = {
            '1m': 1, '5m': 1, '15m': 7, '30m': 14,
            '1h': 30, '4h': 90, '1d': 365, '1w': 365*2
        }
        
        days = (n_bars / 24) * interval_days.get(interval, 30)
        
        if days <= 7:
            return '5d'
        elif days <= 30:
            return '1mo'
        elif days <= 90:
            return '3mo'
        elif days <= 180:
            return '6mo'
        elif days <= 365:
            return '1y'
        elif days <= 730:
            return '2y'
        else:
            return '5y'
    
    def clear_cache(self, symbol: str = None, interval: str = None):
        """Clear data cache."""
        self.db.clear_ohlcv(symbol, interval)
    
    def close(self):
        """Close database connection."""
        self.db.close()
