# Opus Backtrader - Quantitative Trading System

A comprehensive Python backtesting and trading system built with Backtrader.

## Features

- **Multi-Market Support**: Stocks, Crypto, Forex, Futures
- **Multiple Data Sources**: TradingView (tvdatafeed), Yahoo Finance, CCXT
- **Strategy Library**: Technical indicators, SMC, Price Action, Pairs Trading
- **Complex Orders**: Bracket orders, OCO, Trailing Stop Loss
- **Visualization**: Interactive charts with Plotly, real-time dashboard
- **Research System**: Reddit scraping, news analysis
- **Experiment Tracking**: MLflow integration

## Quick Start

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run a backtest
python main.py --strategy supertrend --symbol AAPL --timeframe 1h
```

## UI Runtime Notes (Next.js + Docker)

- Primary UI is **Next.js** on `http://localhost:3000`.
- If you run with `docker compose up` (production-style image), frontend code changes are **not** reflected until rebuild.

```bash
# Rebuild only frontend image and restart
docker compose build --no-cache frontend
docker compose up -d frontend

# If needed, rebuild full stack
docker compose down
docker compose up --build -d
```

## Project Structure

```
├── config/           # Configuration files
├── data/             # Market and research data
├── src/              # Source code
│   ├── data/         # Data fetchers and management
│   ├── strategies/   # Trading strategies
│   ├── indicators/   # Custom indicators
│   ├── research/     # Research system
│   ├── backtest/     # Backtest engine
│   ├── visualization/# Charts and dashboards
│   └── utils/        # Utilities
├── notebooks/        # Jupyter notebooks
├── tests/            # Unit tests
└── main.py           # Entry point
```

## Documentation

See [implementation_plan.md](docs/implementation_plan.md) for detailed architecture.
