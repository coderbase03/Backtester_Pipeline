# Backtest System Documentation

> Last updated: January 2026
> Read this when: implementing strategies, bracket orders, TP/SL, validation

## BacktestEngine Usage

**File:** `src/backtest/engine.py`

```python
from src.backtest.engine import BacktestEngine

engine = BacktestEngine()
results = engine.run(
    strategy=SupertrendStrategy,
    symbol='BTCUSDT',
    source='tradingview',
    exchange='BINANCE',
    interval='4h',
    n_bars=1000,
    initial_cash=100000,
    strategy_params={
        'st_period': 10,
        'st_multiplier': 3.0,
        'risk_pct': 0.02,
        'tp_pct': 3.0,
        'sl_pct': 1.5
    },
    instant_execution=True
)
```

---

## BaseStrategy Parameters

All strategies inherit from `src/strategies/base.py`:

```python
params = (
    ('risk_pct', 0.02),          # Risk per trade
    ('tp_pct', 3.0),             # Take profit %
    ('sl_pct', 1.5),             # Stop loss %
    ('trade_direction', 'long'), # 'long', 'short', 'both'
    ('use_bracket', True),       # Enable TP/SL
    ('leverage', 1),             # 1x-125x
)
```

---

## Key Methods in BaseStrategy

| Method | Purpose |
|--------|---------|
| `calculate_position_size(stop_price)` | Risk-based sizing |
| `buy_with_bracket(size, sl, tp)` | Long entry with TP/SL |
| `sell_with_bracket(size, sl, tp)` | Short entry with TP/SL |
| `close_position()` | Exit current position |
| `reverse_to_long()` | Close short, open long |
| `reverse_to_short()` | Close long, open short |

---

## StrategyBuilder (Dynamic Strategies)

**File:** `src/agents/strategy_builder.py`

Create strategies from configuration without writing code:

```python
from src.agents import StrategyBuilder, StrategyConfig

config = StrategyConfig(
    name="MyRSIStrategy",
    indicators={
        'rsi': {'type': 'rsi', 'period': 14},
        'sma': {'type': 'sma', 'period': 20}
    },
    entry_long="rsi < 30 and close > sma",
    exit_long="rsi > 70",
    tp_pcts=[2.0, 4.0],  # Multiple TPs
    tp_sizes=[0.5, 0.5],
    sl_pct=1.5
)

builder = StrategyBuilder()
strategy_class = builder.build(config)

# Quick test
result = builder.quick_test(config)
```

### Supported Indicators

| Name | Type | Parameters |
|------|------|------------|
| SMA | `sma` | period |
| EMA | `ema` | period |
| RSI | `rsi` | period |
| Supertrend | `supertrend` | period, multiplier |
| Bollinger Bands | `bb` | period, devfactor |
| MACD | `macd` | fast, slow, signal |
| ATR | `atr` | period |
| Stochastic | `stochastic` | period |

---

## Available Analyzers

Results dict contains:

| Metric | Description |
|--------|-------------|
| `sharpe_ratio` | Risk-adjusted return |
| `sortino_ratio` | Downside risk-adjusted |
| `max_drawdown` | Maximum drawdown ($) |
| `max_drawdown_pct` | Maximum drawdown (%) |
| `win_rate` | Winning trades % |
| `profit_factor` | Gross profit / gross loss |
| `total_return` | Total return % |
| `total_trades` | Number of trades |
| `sqn` | System Quality Number |
| `trades` | List of trade details |

---

## Strategy Template

```python
import backtrader as bt
from src.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    params = (
        ('my_param', 14),
        # inherits: risk_pct, tp_pct, sl_pct, etc.
    )
    
    def __init__(self):
        super().__init__()
        self.indicator = bt.indicators.RSI(period=self.params.my_param)
    
    def next(self):
        if not self.position:
            if self.indicator < 30:
                self.buy_with_bracket()
        else:
            if self.indicator > 70:
                self.close_position()
```

---

## Existing Strategies

| File | Strategy | Description |
|------|----------|-------------|
| `supertrend_strategy.py` | Supertrend | ATR-based trend-following |
| `sma_crossover.py` | SMA Crossover | Moving average cross signals |
| `rsi_strategy.py` | RSI | Mean reversion on RSI levels |
| `smc_strategy.py` | SMC | Smart Money Concepts (order blocks) |

---

## Code Generator

**File:** `src/scraper/code_generator.py`

Template-based code generation from AI-extracted strategies:

```python
from src.scraper.code_generator import StrategyCodeGenerator

generator = StrategyCodeGenerator()

result = generator.generate_with_validation(
    strategy_data={
        "strategy_name": "RSI Mean Reversion",
        "entry_rules": "RSI < 30",
        "exit_rules": "RSI > 70",
        "indicators": [{"name": "rsi", "params": {"period": 14}}],
        "tp_pct": 3.0,
        "sl_pct": 1.5
    },
    source_url="https://reddit.com/..."
)

print(result['code'])
print(f"Valid: {result['valid']}")
```

---

## Validation Flow

```
Generated Code
    │
    ▼
ast.parse() ─────────► Syntax Error?
    │                       │
    │ OK                    └── Fix or reject
    ▼
Import Check ────────► Missing imports?
    │                       │
    │ OK                    └── Add suggestions
    ▼
compile() ───────────► Compilation error?
    │                       │
    │ OK                    └── Use AI fix_code()
    ▼
Quick Backtest ──────► Runtime error?
    │                       │
    │ OK                    └── Debug
    ▼
✅ Valid Strategy
```
