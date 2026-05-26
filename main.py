"""
Opus Backtrader - Main Entry Point

Usage:
    python main.py                                    # Run with defaults
    python main.py --strategy supertrend --symbol AAPL
    python main.py --strategy smc --symbol BTCUSDT --source tradingview --exchange BINANCE
    python main.py --strategy sma --symbol AAPL --timeframe 1d
    python main.py --strategy rsi --symbol AAPL --timeframe 1h
    python main.py --optimize --symbol AAPL
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import setup_logging
from src.backtest import BacktestEngine
from src.strategies import SupertrendStrategy, SMCStrategy, SMACrossover, RSIMeanReversion
from src.visualization.reports import print_summary, generate_report
from src.visualization.charts import BacktestChart


# Available strategies
STRATEGIES = {
    'supertrend': SupertrendStrategy,
    'smc': SMCStrategy,
    'sma': SMACrossover,
    'rsi': RSIMeanReversion,
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Opus Backtrader - Quantitative Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --strategy supertrend --symbol AAPL --timeframe 1d
  python main.py --symbol BTCUSDT --source tradingview --exchange BINANCE --timeframe 4h
  python main.py --symbol EURUSD --source yahoo --timeframe 1h
  python main.py --optimize --symbol AAPL
        """
    )
    
    # Strategy selection
    parser.add_argument('--strategy', '-s', type=str, default='supertrend',
                       choices=list(STRATEGIES.keys()),
                       help='Strategy to use (default: supertrend)')
    
    # Data parameters
    parser.add_argument('--symbol', type=str, default='AAPL',
                       help='Asset symbol (default: AAPL)')
    parser.add_argument('--source', type=str, default='yahoo',
                       choices=['yahoo', 'tradingview', 'ccxt', 'auto'],
                       help='Data source (default: yahoo)')
    parser.add_argument('--exchange', type=str, default=None,
                       help='Exchange for tradingview/ccxt (default: auto-detect)')
    
    # Timeframe - support both --timeframe and --interval
    parser.add_argument('--timeframe', '--interval', '-t', type=str, default='1h',
                       dest='interval',
                       help='Timeframe: 1m, 5m, 15m, 1h, 4h, 1d (default: 1h)')
    
    parser.add_argument('--bars', type=int, default=1000,
                       help='Number of bars to fetch (default: 1000)')
    parser.add_argument('--start', type=str, default=None,
                       help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, default=None,
                       help='End date YYYY-MM-DD')
    
    # Backtest parameters
    parser.add_argument('--cash', type=float, default=100000,
                       help='Initial cash (default: 100000)')
    parser.add_argument('--commission', type=float, default=0.001,
                       help='Commission rate (default: 0.001 = 0.1%%)')
    
    # Strategy parameters (Supertrend specific)
    parser.add_argument('--st-period', type=int, default=10,
                       help='Supertrend ATR period (default: 10)')
    parser.add_argument('--st-multiplier', type=float, default=3.0,
                       help='Supertrend ATR multiplier (default: 3.0)')
    parser.add_argument('--risk-pct', type=float, default=0.02,
                       help='Risk per trade as decimal (default: 0.02 = 2%%)')
    parser.add_argument('--rr-ratio', type=float, default=2.0,
                       help='Risk:Reward ratio (default: 2.0)')
    parser.add_argument('--direction', type=str, default='long',
                       choices=['both', 'long', 'short'],
                       help='Trade direction (default: long)')
    
    # Output options
    parser.add_argument('--plot', action='store_true',
                       help='Show backtrader plot')
    parser.add_argument('--chart', action='store_true',
                       help='Show interactive Plotly chart')
    parser.add_argument('--report', action='store_true',
                       help='Generate Excel report')
    parser.add_argument('--optimize', action='store_true',
                       help='Run parameter optimization')
    
    # Misc
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    return parser.parse_args()


def run_backtest(args):
    """Run single backtest with given parameters."""
    strategy_class = STRATEGIES[args.strategy]
    
    print(f"\n🚀 Running backtest: {args.symbol} ({args.interval})")
    print(f"   Strategy: {args.strategy}")
    print(f"   Source: {args.source}" + (f" ({args.exchange})" if args.exchange else ""))
    print(f"   Capital: ${args.cash:,.0f}, Risk: {args.risk_pct*100:.1f}%")
    print()
    
    # Initialize engine
    engine = BacktestEngine()
    
    # Base strategy parameters (common to all)
    strategy_params = {
        'risk_pct': args.risk_pct,
        'rr_ratio': args.rr_ratio,
        'trade_direction': args.direction,
        'use_bracket': True,
        'log_trades': args.log_level == 'DEBUG',
    }
    
    # Add strategy-specific parameters
    if args.strategy == 'supertrend':
        strategy_params['st_period'] = args.st_period
        strategy_params['st_multiplier'] = args.st_multiplier
    elif args.strategy == 'smc':
        strategy_params['atr_period'] = args.st_period  # Reuse st_period for ATR
        strategy_params['swing_lookback'] = 5
    elif args.strategy == 'sma':
        strategy_params['fast_period'] = 10
        strategy_params['slow_period'] = 30
    elif args.strategy == 'rsi':
        strategy_params['rsi_period'] = 14
        strategy_params['oversold'] = 30
        strategy_params['overbought'] = 70
    
    # Run backtest
    results = engine.run(
        strategy=strategy_class,
        symbol=args.symbol,
        source=args.source,
        exchange=args.exchange,
        interval=args.interval,
        n_bars=args.bars,
        start=args.start,
        end=args.end,
        initial_cash=args.cash,
        commission=args.commission,
        strategy_params=strategy_params,
    )
    
    # Print summary
    print_summary(results)
    
    # Get trade details
    trades_df = engine.get_trades_df()
    
    # Generate report
    if args.report:
        detailed = engine.results.analyzers.detailed.get_analysis()
        report_path = generate_report(
            results=results,
            trades=detailed.get('trades', []),
            equity_curve=detailed.get('equity_curve', []),
        )
        print(f"📊 Report saved: {report_path}")
    
    # Show plots
    if args.plot:
        print("📈 Opening Backtrader plot...")
        engine.plot()
    
    if args.chart:
        print("📈 Opening interactive chart...")
        # Get data for chart
        df = engine.data_manager.get_data(
            args.symbol, args.source, args.interval,
            args.exchange, args.bars, args.start, args.end
        )
        detailed = engine.results.analyzers.detailed.get_analysis()
        
        chart = BacktestChart(
            ohlcv_df=df,
            trades=detailed.get('trades', []),
            equity_curve=detailed.get('equity_curve', []),
        )
        chart.show()
    
    return results


def run_optimization(args):
    """Run parameter optimization."""
    strategy_class = STRATEGIES[args.strategy]
    
    print(f"\n🔬 Running optimization: {args.symbol} ({args.interval})")
    print(f"   Strategy: {args.strategy}")
    
    engine = BacktestEngine()
    
    # Define parameter ranges
    results = engine.optimize(
        strategy=strategy_class,
        symbol=args.symbol,
        source=args.source,
        interval=args.interval,
        n_bars=args.bars,
        st_period=range(7, 21, 2),
        st_multiplier=[2.0, 2.5, 3.0, 3.5, 4.0],
    )
    
    print("\n📊 Optimization Results (Top 10):")
    print("-" * 60)
    print(f"{'Period':<10} {'Multiplier':<12} {'Sharpe':<10} {'Return':<10}")
    print("-" * 60)
    
    for i, r in enumerate(results[:10]):
        params = r['params']
        print(f"{params.get('st_period', 'N/A'):<10} "
              f"{params.get('st_multiplier', 'N/A'):<12} "
              f"{r['sharpe']:<10.2f} "
              f"{r['return']:<10.2f}%")
    
    print("-" * 60)
    
    if results:
        best = results[0]
        print(f"\n✅ Best parameters: period={best['params'].get('st_period')}, "
              f"multiplier={best['params'].get('st_multiplier')}")
    
    return results


def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    print("\n" + "="*60)
    print("  OPUS BACKTRADER - Quantitative Trading System")
    print("="*60)
    
    try:
        if args.optimize:
            run_optimization(args)
        else:
            run_backtest(args)
        
        print("\n✅ Done!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.log_level == 'DEBUG':
            raise
        sys.exit(1)


if __name__ == '__main__':
    main()
