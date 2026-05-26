# Dashboard Pages Documentation

> Read this when: modifying UI, adding new pages, fixing Streamlit issues

## Main File

`dashboard.py` - Single-file Streamlit application (~180KB)

## Page Structure

| Page | Function | Purpose |
|------|----------|---------|
| 🏠 Dashboard | `show_dashboard()` | Home, quick backtest |
| 🔬 Backtest | `show_backtest_page()` | Detailed backtest config |
| 🔍 Strategy Discovery | `show_strategy_discovery()` | Reddit scraper + AI |
| 🎯 Optimize | `show_optimize_page()` | Parameter optimization |
| 📥 Data Manager | `show_data_manager()` | Data download |
| 💹 Paper Trade | `show_paper_trading()` | Simulation |
| 🔄 Pine Convert | `show_pine_converter()` | Pine → Python |
| 📊 Compare | `show_compare_page()` | Strategy comparison |
| 📋 History | `show_history_page()` | Past backtests |
| ⚙️ Settings | `show_settings_page()` | Configuration |
| 💰 Cost Analysis | `show_cost_analysis()` | API usage tracking |
| 🎯 Code Generator | `show_code_generator_page()` | AI code generation |

## Session State Keys

Common session state variables:
```python
st.session_state.backtest_results  # Last backtest output
st.session_state.selected_strategy # Current strategy
st.session_state.tv_username       # TradingView auth
st.session_state.api_costs         # Token usage tracking
```

## Adding a New Page

1. Add function: `def show_new_page():`
2. Add to sidebar menu in `main()`
3. Add page emoji and title

## Key UI Components

| Component | Usage |
|-----------|-------|
| `st.sidebar` | Navigation menu |
| `st.tabs` | Sub-sections within page |
| `st.columns` | Side-by-side layout |
| `st.expander` | Collapsible sections |
| `st.dataframe` | Display results table |

## Chart Integration

TradingView-style charts via `src/tv_charts/`:
- `trading_chart.py` - Main chart component
- Uses lightweight-charts library
- Renders in Streamlit via components.html()

## Running Dashboard

```bash
streamlit run dashboard.py --server.port 8501
```
