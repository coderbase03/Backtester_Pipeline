# Architecture Overview

> Last updated: January 2026
> Read this when: designing new modules, understanding data flow, major refactoring

## Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Presentation Layer                   │
│   dashboard.py │ main.py CLI │ tv_charts/           │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                 Application Layer                    │
│   BacktestEngine │ AIExtractor │ AIPineConverter    │
│   StrategyBuilder │ CodeGenerator                    │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                    Data Layer                        │
│   DataManager │ StrategyStorage │ RedditCollector   │
│   tvdatafeed  │ yfinance │ ccxt                     │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                  Storage Layer                       │
│   SQLite (trading.db, strategies.db)                │
└─────────────────────────────────────────────────────┘
```

## Module Dependency Map

```
dashboard.py (Main UI - ~180KB)
    │
    ├── src/backtest/engine.py
    │       └── Runs Backtrader backtests
    │
    ├── src/scraper/
    │       ├── reddit_collector.py   → Fetch Reddit posts
    │       ├── ai_extractor.py       → GPT-4o-mini classification
    │       ├── code_generator.py     → Template-based code gen
    │       ├── strategy_storage.py   → SQLite CRUD
    │       └── discovery_page.py     → Streamlit UI components
    │
    ├── src/converter/
    │       ├── ai_pine_converter.py  → GLM-4.7 Pine↔Python
    │       └── pine_converter.py     → Rule-based fallback
    │
    ├── src/agents/
    │       └── strategy_builder.py   → Dynamic strategy creation
    │
    ├── src/data/manager.py           → Unified data fetching
    │
    └── src/visualization/charts.py   → Plotly charts
```

## Data Flow: Backtest

```
User Input → DataManager.get_data() → SQLite cache
          → BacktestEngine.run() → Strategy.next()
          → Analyzers → Results dict → Display
```

## Data Flow: Strategy Discovery

```
Reddit → RedditCollector.collect_posts()
      → SQLite (raw posts)
      → AIExtractor.stage1_classify() [GPT-4o-mini]
      → AIExtractor.stage2_extract_strategy() [GPT-4o-mini]
      → StrategyStorage.save_filtered_strategy()
      → CodeGenerator.generate() [Template-based]
      → BacktestEngine.run() [Validation]
```

## Data Flow: Pine Script Conversion

```
Pine Script → AIPineConverter.pine_to_python() [GLM-4.7]
           → ValidationResult (syntax check)
           → Python/Backtrader code
           → BacktestEngine.run() [Quick test]
```

## Important Base Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `BaseStrategy` | `src/strategies/base.py` | All strategies inherit |
| `BacktestEngine` | `src/backtest/engine.py` | Central execution |
| `DataManager` | `src/data/manager.py` | Unified data access |
| `AIPineConverter` | `src/converter/ai_pine_converter.py` | Code conversion |
| `SmartExtractor` | `src/scraper/ai_extractor.py` | Strategy extraction |
| `StrategyBuilder` | `src/agents/strategy_builder.py` | Dynamic strategy creation |
| `StrategyStorage` | `src/scraper/strategy_storage.py` | Database operations |

## Database Schema

### trading.db
OHLCV market data cache

| Table | Columns |
|-------|---------|
| `ohlcv` | symbol, exchange, interval, datetime, open, high, low, close, volume |

### strategies.db
AI-discovered strategies

| Table | Purpose |
|-------|---------|
| `posts` | Raw Reddit posts |
| `filtered_strategies` | AI-processed with scores |

## Key Configurations

| File | Purpose |
|------|---------|
| `config/secrets.yaml` | API keys (OpenAI, GLM, TV) |
| `config/settings.yaml` | App settings |
| `config/subreddits.yaml` | Target subreddits list |

## Strategy Types

| Strategy | File | Description |
|----------|------|-------------|
| Supertrend | `supertrend_strategy.py` | Trend-following |
| SMA Crossover | `sma_crossover.py` | Moving average cross |
| RSI | `rsi_strategy.py` | Mean reversion |
| SMC | `smc_strategy.py` | Smart Money Concepts |
| Dynamic | `strategy_builder.py` | User-configured |
