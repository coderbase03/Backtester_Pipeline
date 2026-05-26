# Data Sources Documentation

> Read this when: fetching market data, adding new exchanges, timeframe issues

## DataManager Usage

```python
from src.data.manager import DataManager

manager = DataManager()
df = manager.get_data(
    symbol='BTCUSDT',
    source='tradingview',  # or 'yahoo', 'ccxt'
    interval='1h',
    exchange='BINANCE',
    n_bars=1000
)
```

## Supported Sources

### 1. TradingView (tvdatafeed) - PREFERRED
**Best for:** All markets, most reliable

```python
# Crypto
symbol='BTCUSDT', exchange='BINANCE'
symbol='ETHUSDT', exchange='BYBIT'

# Stocks  
symbol='AAPL', exchange='NASDAQ'
symbol='TSLA', exchange='NASDAQ'

# Forex
symbol='EURUSD', exchange='FX_IDC'

# Turkish stocks
symbol='THYAO', exchange='BIST'
```

### 2. Yahoo Finance (yfinance)
**Best for:** US stocks, ETFs (free, no auth)

```python
symbol='AAPL'  # No exchange needed
symbol='SPY'
```

### 3. CCXT
**Best for:** Crypto exchanges direct API

```python
symbol='BTC/USDT', exchange='binance'
```

## Supported Timeframes

| Code | Meaning |
|------|---------|
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `30m` | 30 minutes |
| `1h` | 1 hour |
| `4h` | 4 hours |
| `1d` | 1 day |
| `1w` | 1 week |

## Data Storage

All fetched data is cached in SQLite:
- **Location:** `data/trading.db`
- **Table:** `ohlcv`
- **Columns:** symbol, exchange, interval, datetime, open, high, low, close, volume

## Configuration

TradingView credentials in `config/secrets.yaml`:

```yaml
tradingview:
  username: "your_username"
  password: "your_password"
```

## Common Issues

| Issue | Solution |
|-------|----------|
| No data returned | Check symbol/exchange spelling |
| Timeframe not working | Some exchanges don't support all timeframes |
| Rate limiting | Add delays between requests |
