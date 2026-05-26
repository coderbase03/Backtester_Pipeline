"""
Data service - wraps the core DataManager for API use.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

ENGINE_ROOT = Path(__file__).resolve().parents[3]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.data.manager import DataManager

logger = logging.getLogger(__name__)

_manager: DataManager | None = None


def _get_manager() -> DataManager:
    global _manager
    if _manager is None:
        _manager = DataManager()
    return _manager


def download_data(symbol: str, source: str = "tradingview", exchange: Optional[str] = None, interval: str = "1h", n_bars: int = 1000) -> dict:
    dm = _get_manager()
    try:
        df = dm.get_data(symbol=symbol, source=source, exchange=exchange, interval=interval, n_bars=n_bars, use_cache=False)
        rows = len(df) if df is not None and not df.empty else 0
        return {"symbol": symbol, "bars_downloaded": rows, "interval": interval, "success": rows > 0, "error": None if rows > 0 else "No data returned"}
    except Exception as e:
        logger.error("Download failed for %s: %s", symbol, e)
        return {"symbol": symbol, "bars_downloaded": 0, "interval": interval, "success": False, "error": str(e)}


def get_cached_symbols() -> list[dict]:
    dm = _get_manager()
    try:
        return dm.db.get_cached_symbols_with_stats()
    except Exception:
        return []


def get_data_summary() -> list[dict]:
    dm = _get_manager()
    try:
        return dm.db.get_data_summary()
    except Exception:
        return []
