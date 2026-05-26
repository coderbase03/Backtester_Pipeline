"""
Backtest Engine - Wrapper around Backtrader

Provides simplified interface for running backtests with:
- Easy data loading from DataManager
- Standard analyzers
- Results formatting
- MLflow integration
"""

import backtrader as bt
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, Type, List
import logging
import uuid
import json

from ..data import DataManager
from .analyzers import DetailedAnalyzer


logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Simplified Backtrader wrapper for running backtests.
    
    Usage:
        engine = BacktestEngine()
        results = engine.run(
            strategy=SupertrendStrategy,
            symbol='AAPL',
            source='yahoo',
            interval='1h',
            start='2023-01-01',
            end='2023-12-31'
        )
        engine.plot()
    """
    
    def __init__(self, config_path: str = 'config/settings.yaml'):
        """Initialize backtest engine."""
        self.data_manager = DataManager(config_path)
        self.cerebro = None
        self.results = None
        self.run_id = None
        
        # Load default config
        self.default_cash = 100000
        self.default_commission = 0.001
        
        logger.info("BacktestEngine initialized")
    
    def run(
        self,
        strategy: Type[bt.Strategy],
        symbol: str,
        source: str = 'auto',
        exchange: str = None,
        interval: str = '1d',
        start: str = None,
        end: str = None,
        n_bars: int = 1000,
        initial_cash: float = None,
        commission: float = None,
        slippage_ticks: Optional[int] = None,
        strategy_params: Dict[str, Any] = None,
        analyzers: List[Type[bt.Analyzer]] = None,
        instant_execution: bool = True
    ) -> Dict[str, Any]:
        """
        Run a backtest.
        
        Args:
            strategy: Strategy class to test
            symbol: Asset symbol
            source: Data source ('auto', 'tradingview', 'yahoo', 'ccxt')
            exchange: Exchange name (for tradingview/ccxt)
            interval: Timeframe
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            n_bars: Number of bars (if start/end not specified)
            initial_cash: Starting capital
            commission: Commission per trade (0.001 = 0.1%)
            strategy_params: Strategy parameters dict
            analyzers: Additional analyzers to add
            
        Returns:
            Dict with backtest results and metrics
        """
        self.run_id = str(uuid.uuid4())[:8]
        logger.info(f"Starting backtest {self.run_id}: {strategy.__name__} on {symbol}")
        
        # ======== DATA LOADING ========
        df = self.data_manager.get_data(
            symbol=symbol,
            source=source,
            exchange=exchange,
            interval=interval,
            n_bars=n_bars,
            start=start,
            end=end
        )
        
        if df.empty:
            raise ValueError(f"No data retrieved for {symbol}")
        
        logger.info(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        
        # ======== CEREBRO SETUP ========
        self.cerebro = bt.Cerebro()
        
        # Add data
        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None,  # Use index
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest=-1
        )
        self.cerebro.adddata(data, name=symbol)
        
        # Add strategy
        strategy_params = strategy_params or {}
        self.cerebro.addstrategy(strategy, **strategy_params)
        
        # Set broker parameters
        cash = initial_cash or self.default_cash
        comm = commission if commission is not None else self.default_commission
        
        self.cerebro.broker.setcash(cash)
        self.cerebro.broker.setcommission(commission=comm)
        slippage_applied = False
        slippage_reason = "not_requested"
        if slippage_ticks and slippage_ticks > 0:
            tick_size = self._infer_tick_size(df)
            if tick_size and tick_size > 0:
                self.cerebro.broker.set_slippage_fixed(fixed=tick_size * slippage_ticks)
                slippage_applied = True
                slippage_reason = "applied"
            else:
                slippage_reason = "tick_size_unavailable"
        
        # ======== INSTANT EXECUTION (Cheat-on-Close) ========
        if instant_execution:
            self.cerebro.broker.set_coc(True)  # Execute orders at current bar's close
            logger.info("Instant execution enabled (cheat-on-close)")
        
        # ======== ANALYZERS ========
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                                  riskfreerate=0.0, annualize=True)
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        self.cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
        self.cerebro.addanalyzer(DetailedAnalyzer, _name='detailed')
        
        # Add custom analyzers
        if analyzers:
            for analyzer in analyzers:
                self.cerebro.addanalyzer(analyzer)
        
        # ======== RUN BACKTEST ========
        logger.info("Running backtest...")
        start_value = self.cerebro.broker.getvalue()
        
        results = self.cerebro.run()
        self.results = results[0]  # First strategy result
        
        # ======== EXTRACT RESULTS ========
        final_value = self.cerebro.broker.getvalue()
        
        # Get analyzer results
        sharpe = self._get_sharpe()
        drawdown = self._get_drawdown()
        trades = self._get_trade_analysis()
        returns = self._get_returns()
        
        result = {
            'run_id': self.run_id,
            'strategy': strategy.__name__,
            'symbol': symbol,
            'interval': interval,
            'start_date': str(df.index[0].date()),
            'end_date': str(df.index[-1].date()),
            'initial_cash': cash,
            'final_value': round(final_value, 2),
            'total_return': round((final_value / cash - 1) * 100, 2),
            'total_return_pct': round((final_value / cash - 1) * 100, 2),
            'sharpe_ratio': sharpe,
            'max_drawdown': drawdown['max_drawdown'],
            'max_drawdown_pct': drawdown['max_drawdown_pct'],
            'total_trades': trades['total'],
            'won_trades': trades['won'],
            'lost_trades': trades['lost'],
            'win_rate': trades['win_rate'],
            'profit_factor': trades['profit_factor'],
            'avg_trade': trades['avg_trade'],
            'sqn': self._get_sqn(),
            'annual_return': returns.get('rnorm100', 0),
            'parameters': strategy_params,
            'slippage_applied': slippage_applied,
            'slippage_reason': slippage_reason,
        }
        
        logger.info(f"Backtest complete: Return={result['total_return']:.2f}%, "
                   f"Sharpe={sharpe:.2f}, MaxDD={drawdown['max_drawdown_pct']:.2f}%")
        
        # ======== AUTO-SAVE TO DATABASE ========
        try:
            from ..data.database import Database
            db = Database()
            
            # Get detailed analysis data
            detailed = self.results.analyzers.detailed.get_analysis()
            equity_curve = detailed.get('equity_curve', [])
            drawdown_curve = detailed.get('drawdown_curve', [])
            buy_hold_return = detailed.get('buy_hold_return', 0)
            
            # Save backtest results with all data
            db.save_backtest(
                run_id=self.run_id,
                strategy_name=strategy.__name__,
                symbol=symbol,
                timeframe=interval,
                results=result,
                parameters=strategy_params,
                equity_curve=equity_curve,
                drawdown_curve=drawdown_curve,
                buy_hold_return=buy_hold_return
            )
            
            # Save individual trades
            if detailed.get('trades'):
                db.save_trades(self.run_id, detailed['trades'])
            
            db.close()
            logger.info(f"Saved to database: {self.run_id}")
        except Exception as e:
            logger.warning(f"Database save failed: {e}")
        
        return result

    def _infer_tick_size(self, df: pd.DataFrame) -> Optional[float]:
        """Infer a reasonable tick size from close-price increments."""
        if df is None or df.empty or 'close' not in df.columns:
            return None
        diffs = df['close'].diff().abs()
        diffs = diffs[(diffs > 0) & diffs.notna()]
        if diffs.empty:
            return None
        tick = float(diffs.min())
        if tick <= 0:
            return None
        return tick
    
    def _get_sharpe(self) -> float:
        """Extract Sharpe ratio from results."""
        try:
            sharpe = self.results.analyzers.sharpe.get_analysis()
            return round(sharpe.get('sharperatio', 0) or 0, 2)
        except:
            return 0.0
    
    def _get_drawdown(self) -> Dict[str, float]:
        """Extract drawdown metrics."""
        try:
            dd = self.results.analyzers.drawdown.get_analysis()
            return {
                'max_drawdown': round(dd.get('max', {}).get('moneydown', 0), 2),
                'max_drawdown_pct': round(dd.get('max', {}).get('drawdown', 0), 2),
                'max_drawdown_len': dd.get('max', {}).get('len', 0),
            }
        except:
            return {'max_drawdown': 0, 'max_drawdown_pct': 0, 'max_drawdown_len': 0}
    
    def _get_trade_analysis(self) -> Dict[str, Any]:
        """Extract trade analysis."""
        try:
            ta = self.results.analyzers.trades.get_analysis()
            
            total = ta.get('total', {}).get('total', 0)
            won = ta.get('won', {}).get('total', 0)
            lost = ta.get('lost', {}).get('total', 0)
            
            # Calculate profit factor
            gross_profit = ta.get('won', {}).get('pnl', {}).get('total', 0)
            gross_loss = abs(ta.get('lost', {}).get('pnl', {}).get('total', 1))
            profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
            
            # Average trade
            avg_trade = ta.get('pnl', {}).get('net', {}).get('average', 0)
            
            return {
                'total': total,
                'won': won,
                'lost': lost,
                'win_rate': round((won / total * 100) if total > 0 else 0, 2),
                'profit_factor': profit_factor,
                'avg_trade': round(avg_trade, 2),
            }
        except:
            return {'total': 0, 'won': 0, 'lost': 0, 'win_rate': 0, 
                    'profit_factor': 0, 'avg_trade': 0}
    
    def _get_returns(self) -> Dict[str, float]:
        """Extract returns analysis."""
        try:
            return self.results.analyzers.returns.get_analysis()
        except:
            return {}
    
    def _get_sqn(self) -> float:
        """Extract System Quality Number."""
        try:
            sqn = self.results.analyzers.sqn.get_analysis()
            return round(sqn.get('sqn', 0), 2)
        except:
            return 0.0
    
    def plot(self, style: str = 'candlestick', volume: bool = True, **kwargs):
        """
        Plot backtest results using Backtrader's built-in plotting.
        
        Args:
            style: 'candlestick' or 'line'
            volume: Show volume subplot
            **kwargs: Additional plotting parameters
        """
        if self.cerebro is None:
            raise ValueError("No backtest has been run yet")
        
        self.cerebro.plot(
            style=style,
            volume=volume,
            **kwargs
        )
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get DataFrame of all trades."""
        try:
            detailed = self.results.analyzers.detailed.get_analysis()
            return pd.DataFrame(detailed.get('trades', []))
        except:
            return pd.DataFrame()
    
    def optimize(
        self,
        strategy: Type[bt.Strategy],
        symbol: str,
        source: str = 'auto',
        interval: str = '1d',
        n_bars: int = 1000,
        **param_ranges
    ) -> List[Dict[str, Any]]:
        """
        Run parameter optimization.
        
        Args:
            strategy: Strategy class
            symbol: Asset symbol
            source: Data source
            interval: Timeframe
            n_bars: Number of bars
            **param_ranges: Parameter ranges as name=range(start, end, step)
            
        Returns:
            List of results sorted by Sharpe ratio
        """
        # Get data once
        df = self.data_manager.get_data(
            symbol=symbol,
            source=source,
            interval=interval,
            n_bars=n_bars
        )
        
        self.cerebro = bt.Cerebro()
        
        data = bt.feeds.PandasData(dataname=df)
        self.cerebro.adddata(data)
        
        # Add strategy with optimization parameters
        self.cerebro.optstrategy(strategy, **param_ranges)
        
        self.cerebro.broker.setcash(self.default_cash)
        self.cerebro.broker.setcommission(commission=self.default_commission)
        
        # Add analyzers
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        # Run optimization
        logger.info(f"Running optimization with {param_ranges}")
        results = self.cerebro.run(maxcpus=1)  # Use 1 CPU for stability
        
        # Extract results
        opt_results = []
        for strats in results:
            for strat in strats:
                sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', 0) or 0
                ret = strat.analyzers.returns.get_analysis().get('rnorm100', 0)
                
                opt_results.append({
                    'params': strat.params._getkwargs(),
                    'sharpe': round(sharpe, 2),
                    'return': round(ret, 2),
                })
        
        # Sort by Sharpe ratio
        opt_results.sort(key=lambda x: x['sharpe'], reverse=True)
        
        return opt_results
    
    # ======== MULTI-TIMEFRAME BACKTESTING ========
    
    def run_multi_timeframe(
        self,
        strategy: Type[bt.Strategy],
        symbol: str,
        timeframes: List[str] = None,
        source: str = 'auto',
        exchange: str = None,
        n_bars: int = 500,
        initial_cash: float = None,
        commission: float = None,
        strategy_params: Dict[str, Any] = None,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        Birden fazla timeframe'de backtest çalıştır ve sonuçları karşılaştır.
        
        Args:
            strategy: Strategy class
            symbol: Asset symbol
            timeframes: List of timeframes (default: ['1h', '4h', '1d'])
            source: Data source
            exchange: Exchange name
            n_bars: Bars per timeframe
            initial_cash: Starting capital
            commission: Commission rate
            strategy_params: Strategy parameters
            
        Returns:
            Dict with results per timeframe and comparison table
        """
        if timeframes is None:
            timeframes = ['1h', '4h', '1d']
        
        logger.info(f"Starting Multi-Timeframe backtest: {strategy.__name__} on {symbol}")
        logger.info(f"Timeframes: {timeframes}")
        
        all_results = {}
        errors = {}
        
        total = len(timeframes)
        for i, tf in enumerate(timeframes):
            # Progress callback
            if progress_callback:
                progress_callback((i + 1) / total, f"Testing {tf}... ({i+1}/{total})")
            
            try:
                logger.info(f"Running {tf}...")
                result = self.run(
                    strategy=strategy,
                    symbol=symbol,
                    source=source,
                    exchange=exchange,
                    interval=tf,
                    n_bars=n_bars,
                    initial_cash=initial_cash,
                    commission=commission,
                    strategy_params=strategy_params,
                )
                all_results[tf] = result
                logger.info(f"  {tf}: Return={result['total_return']:.2f}%, Trades={result['total_trades']}")
                
            except Exception as e:
                logger.error(f"Error running {tf}: {e}")
                errors[tf] = str(e)
        
        # Create comparison table
        comparison = self._create_comparison_table(all_results)
        
        # Find best timeframe
        best_tf = None
        best_sharpe = -999
        for tf, result in all_results.items():
            if result.get('sharpe_ratio', 0) > best_sharpe:
                best_sharpe = result['sharpe_ratio']
                best_tf = tf
        
        return {
            'strategy': strategy.__name__,
            'symbol': symbol,
            'timeframes': timeframes,
            'results': all_results,
            'comparison': comparison,
            'best_timeframe': best_tf,
            'best_sharpe': best_sharpe,
            'errors': errors if errors else None,
        }
    
    def _create_comparison_table(self, results: Dict[str, Dict]) -> pd.DataFrame:
        """Timeframe sonuçlarını karşılaştırma tablosu oluştur."""
        if not results:
            return pd.DataFrame()
        
        rows = []
        for tf, r in results.items():
            rows.append({
                'Timeframe': tf,
                'Return %': r.get('total_return', 0),
                'Sharpe': r.get('sharpe_ratio', 0),
                'Max DD %': r.get('max_drawdown_pct', 0),
                'Trades': r.get('total_trades', 0),
                'Win Rate %': r.get('win_rate', 0),
                'Profit Factor': r.get('profit_factor', 0),
                'Avg Trade $': r.get('avg_trade', 0),
                'SQN': r.get('sqn', 0),
            })
        
        df = pd.DataFrame(rows)
        
        # Sort by Sharpe ratio
        df = df.sort_values('Sharpe', ascending=False)
        
        return df
    
    # ======== MULTI-SYMBOL BACKTESTING ========
    
    def run_multi_symbol(
        self,
        strategy: Type[bt.Strategy],
        symbols: List[Dict[str, str]],  # [{'symbol': 'BTCUSDT', 'exchange': 'BINANCE'}, ...]
        interval: str = '1d',
        source: str = 'auto',
        n_bars: int = 500,
        initial_cash: float = None,
        commission: float = None,
        strategy_params: Dict[str, Any] = None,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        Birden fazla sembolde backtest çalıştır ve sonuçları karşılaştır.
        
        Args:
            strategy: Strategy class
            symbols: List of dicts with 'symbol' and 'exchange' keys
            interval: Timeframe
            source: Data source
            n_bars: Bars per symbol
            initial_cash: Starting capital
            commission: Commission rate
            strategy_params: Strategy parameters
            
        Returns:
            Dict with results per symbol and comparison table
        """
        logger.info(f"Starting Multi-Symbol backtest: {strategy.__name__}")
        logger.info(f"Symbols: {[s['symbol'] for s in symbols]}")
        
        all_results = {}
        errors = {}
        
        total = len(symbols)
        for i, sym_data in enumerate(symbols):
            symbol = sym_data['symbol']
            exchange = sym_data.get('exchange')
            
            # Progress callback
            if progress_callback:
                progress_callback((i + 1) / total, f"Testing {symbol}... ({i+1}/{total})")
            
            try:
                logger.info(f"Running {symbol}...")
                result = self.run(
                    strategy=strategy,
                    symbol=symbol,
                    source=source,
                    exchange=exchange,
                    interval=interval,
                    n_bars=n_bars,
                    initial_cash=initial_cash,
                    commission=commission,
                    strategy_params=strategy_params,
                )
                all_results[symbol] = result
                logger.info(f"  {symbol}: Return={result['total_return']:.2f}%, Trades={result['total_trades']}")
                
            except Exception as e:
                logger.error(f"Error running {symbol}: {e}")
                errors[symbol] = str(e)
        
        # Create comparison table
        comparison = self._create_symbol_comparison_table(all_results)
        
        # Find best symbol
        best_symbol = None
        best_sharpe = -999
        for sym, result in all_results.items():
            if result.get('sharpe_ratio', 0) > best_sharpe:
                best_sharpe = result['sharpe_ratio']
                best_symbol = sym
        
        return {
            'strategy': strategy.__name__,
            'interval': interval,
            'symbols': [s['symbol'] for s in symbols],
            'results': all_results,
            'comparison': comparison,
            'best_symbol': best_symbol,
            'best_sharpe': best_sharpe,
            'errors': errors if errors else None,
        }
    
    def _create_symbol_comparison_table(self, results: Dict[str, Dict]) -> pd.DataFrame:
        """Sembol sonuçlarını karşılaştırma tablosu oluştur."""
        if not results:
            return pd.DataFrame()
        
        rows = []
        for symbol, r in results.items():
            rows.append({
                'Symbol': symbol,
                'Return %': r.get('total_return', 0),
                'Sharpe': r.get('sharpe_ratio', 0),
                'Max DD %': r.get('max_drawdown_pct', 0),
                'Trades': r.get('total_trades', 0),
                'Win Rate %': r.get('win_rate', 0),
                'Profit Factor': r.get('profit_factor', 0),
                'Avg Trade $': r.get('avg_trade', 0),
                'SQN': r.get('sqn', 0),
            })
        
        df = pd.DataFrame(rows)
        df = df.sort_values('Sharpe', ascending=False)
        
        return df
    
    # ======== COMPREHENSIVE BACKTEST (MTF + Multi-Symbol) ========
    
    def run_comprehensive(
        self,
        strategy: Type[bt.Strategy],
        symbols: List[Dict[str, str]],
        timeframes: List[str] = None,
        source: str = 'auto',
        n_bars: int = 500,
        initial_cash: float = None,
        commission: float = None,
        strategy_params: Dict[str, Any] = None,
        progress_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        Kapsamlı backtest: Birden fazla sembol + birden fazla timeframe.
        
        Returns:
            Results matrix: symbol x timeframe
        """
        if timeframes is None:
            timeframes = ['1h', '4h', '1d']
        
        logger.info(f"Starting Comprehensive backtest: {strategy.__name__}")
        logger.info(f"Symbols: {[s['symbol'] for s in symbols]}, Timeframes: {timeframes}")
        
        matrix_results = {}
        errors = {}
        
        total_tests = len(symbols) * len(timeframes)
        current = 0
        
        for sym_data in symbols:
            symbol = sym_data['symbol']
            exchange = sym_data.get('exchange')
            matrix_results[symbol] = {}
            
            for tf in timeframes:
                current += 1
                # Progress callback
                if progress_callback:
                    progress_callback(current / total_tests, f"Testing {symbol}@{tf}... ({current}/{total_tests})")
                
                try:
                    logger.info(f"[{current}/{total_tests}] Running {symbol} @ {tf}...")
                    result = self.run(
                        strategy=strategy,
                        symbol=symbol,
                        source=source,
                        exchange=exchange,
                        interval=tf,
                        n_bars=n_bars,
                        initial_cash=initial_cash,
                        commission=commission,
                        strategy_params=strategy_params,
                    )
                    matrix_results[symbol][tf] = result
                    
                except Exception as e:
                    logger.error(f"Error running {symbol}@{tf}: {e}")
                    errors[f"{symbol}@{tf}"] = str(e)
        
        # Create comprehensive comparison table
        comparison = self._create_comprehensive_table(matrix_results)
        
        # Find best combination
        best_combo = None
        best_sharpe = -999
        for symbol, tf_results in matrix_results.items():
            for tf, result in tf_results.items():
                if result.get('sharpe_ratio', 0) > best_sharpe:
                    best_sharpe = result['sharpe_ratio']
                    best_combo = f"{symbol}@{tf}"
        
        return {
            'strategy': strategy.__name__,
            'symbols': [s['symbol'] for s in symbols],
            'timeframes': timeframes,
            'matrix': matrix_results,
            'comparison': comparison,
            'best_combination': best_combo,
            'best_sharpe': best_sharpe,
            'errors': errors if errors else None,
            'total_tests': total_tests,
        }
    
    def _create_comprehensive_table(self, matrix: Dict[str, Dict]) -> pd.DataFrame:
        """Kapsamlı sonuç tablosu oluştur."""
        rows = []
        for symbol, tf_results in matrix.items():
            for tf, r in tf_results.items():
                rows.append({
                    'Symbol': symbol,
                    'TF': tf,
                    'Return %': r.get('total_return', 0),
                    'Sharpe': r.get('sharpe_ratio', 0),
                    'Max DD %': r.get('max_drawdown_pct', 0),
                    'Trades': r.get('total_trades', 0),
                    'Win %': r.get('win_rate', 0),
                    'PF': r.get('profit_factor', 0),
                })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values('Sharpe', ascending=False)
        
        return df
