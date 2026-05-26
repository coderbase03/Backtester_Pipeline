"""
Example: Quick Start with Supertrend Strategy

This script demonstrates basic usage of the backtesting system.
"""

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import setup_logging
from src.data import DataManager
from src.backtest import BacktestEngine
from src.strategies import SupertrendStrategy
from src.visualization.reports import print_summary
from src.visualization.charts import BacktestChart


def main():
    """Run a simple Supertrend backtest."""
    
    # Setup logging
    setup_logging(level='INFO')
    
    print("\n" + "="*60)
    print("  SUPERTREND STRATEGY EXAMPLE")
    print("="*60 + "\n")
    
    # ======== METHOD 1: Using BacktestEngine (Recommended) ========
    print("Running backtest with BacktestEngine...\n")
    
    engine = BacktestEngine()
    
    results = engine.run(
        strategy=SupertrendStrategy,
        symbol='AAPL',
        source='yahoo',
        interval='1h',
        n_bars=500,
        initial_cash=100000,
        commission=0.001,
        strategy_params={
            'st_period': 10,
            'st_multiplier': 3.0,
            'risk_pct': 0.02,
            'rr_ratio': 2.0,
            'trade_direction': 'both',
        }
    )
    
    # Print results
    print_summary(results)
    
    # Get detailed analysis
    detailed = engine.results.analyzers.detailed.get_analysis()
    trades = detailed.get('trades', [])
    
    print(f"Number of trades: {len(trades)}")
    if trades:
        print("\nLast 5 trades:")
        for trade in trades[-5:]:
            print(f"  #{trade['trade_num']}: {trade['direction']} | "
                  f"Entry: ${trade['entry_price']:.2f} | "
                  f"Exit: ${trade['exit_price']:.2f} | "
                  f"PnL: ${trade['pnl']:.2f}")
    
    # ======== VISUALIZATION ========
    print("\n" + "-"*60)
    print("Creating interactive chart...")
    
    # Get OHLCV data for chart
    df = engine.data_manager.get_data('AAPL', 'yahoo', '1h', n_bars=500)
    
    chart = BacktestChart(
        ohlcv_df=df,
        trades=trades,
        equity_curve=detailed.get('equity_curve', []),
    )
    
    # Save to HTML (opens in browser)
    chart.save_html('reports/example_backtest.html')
    print("Chart saved to: reports/example_backtest.html")
    
    # Optionally show in browser
    # chart.show()
    
    return results


def example_crypto():
    """Example: Backtest crypto with TradingView data."""
    print("\n" + "="*60)
    print("  CRYPTO EXAMPLE (BTCUSDT)")
    print("="*60 + "\n")
    
    engine = BacktestEngine()
    
    results = engine.run(
        strategy=SupertrendStrategy,
        symbol='BTCUSDT',
        source='tradingview',  # Using TradingView via tvdatafeed
        exchange='BINANCE',
        interval='4h',
        n_bars=500,
        strategy_params={
            'st_period': 10,
            'st_multiplier': 2.5,
            'trade_direction': 'both',
        }
    )
    
    print_summary(results)
    return results


def example_forex():
    """Example: Backtest forex pair."""
    print("\n" + "="*60)
    print("  FOREX EXAMPLE (EURUSD)")
    print("="*60 + "\n")
    
    engine = BacktestEngine()
    
    results = engine.run(
        strategy=SupertrendStrategy,
        symbol='EURUSD=X',  # Yahoo Finance format
        source='yahoo',
        interval='1h',
        n_bars=500,
        strategy_params={
            'st_period': 14,
            'st_multiplier': 3.0,
        }
    )
    
    print_summary(results)
    return results


def example_optimization():
    """Example: Parameter optimization."""
    print("\n" + "="*60)
    print("  OPTIMIZATION EXAMPLE")
    print("="*60 + "\n")
    
    engine = BacktestEngine()
    
    results = engine.optimize(
        strategy=SupertrendStrategy,
        symbol='AAPL',
        source='yahoo',
        interval='1d',
        n_bars=500,
        # Parameter ranges to test
        st_period=range(7, 15, 2),  # 7, 9, 11, 13
        st_multiplier=[2.0, 2.5, 3.0, 3.5],
    )
    
    print("Top 5 parameter combinations:")
    print("-" * 50)
    for i, r in enumerate(results[:5], 1):
        print(f"{i}. Period: {r['params']['st_period']}, "
              f"Mult: {r['params']['st_multiplier']}, "
              f"Sharpe: {r['sharpe']:.2f}, "
              f"Return: {r['return']:.2f}%")
    
    return results


if __name__ == '__main__':
    # Run main example
    main()
    
    # Uncomment to run other examples:
    # example_crypto()
    # example_forex()
    # example_optimization()
