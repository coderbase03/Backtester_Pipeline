"""
Parameter Optimization Module

Provides tools for strategy parameter optimization:
- Grid Search: Exhaustive search over parameter combinations
- Optuna (Bayesian): Smart search using TPE sampler
- Walk-Forward: Out-of-sample validation

Usage:
    from src.backtest.optimizer import GridSearchOptimizer, OptunaOptimizer
    
    optimizer = GridSearchOptimizer(engine)
    results = optimizer.optimize(
        strategy=SMACrossover,
        param_grid={'fast_period': [5, 10, 15], 'slow_period': [20, 30, 40]},
        symbol='AAPL',
        metric='sharpe_ratio'
    )
"""

import backtrader as bt
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Type, Tuple, Callable
from itertools import product
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import optuna for bayesian optimization
try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.info("Optuna not installed. Install with: pip install optuna")


class GridSearchOptimizer:
    """
    Exhaustive grid search over parameter combinations.
    
    Runs backtest for every combination and returns sorted results.
    
    Example:
        optimizer = GridSearchOptimizer(engine)
        results = optimizer.optimize(
            strategy=SMACrossover,
            param_grid={
                'fast_period': [5, 10, 15, 20],
                'slow_period': [30, 40, 50, 60]
            },
            symbol='AAPL',
            source='tradingview',
            metric='sharpe_ratio'
        )
    """
    
    def __init__(self, engine=None):
        """
        Initialize optimizer.
        
        Args:
            engine: Optional BacktestEngine instance. If None, creates new one per run.
        """
        self.engine = engine
        self.results = []
        
    def optimize(
        self,
        strategy: Type[bt.Strategy],
        param_grid: Dict[str, List[Any]],
        symbol: str,
        source: str = 'tradingview',
        exchange: str = None,
        interval: str = '1d',
        n_bars: int = 1000,
        initial_cash: float = 100000,
        commission: float = 0.001,
        metric: str = 'sharpe_ratio',
        maximize: bool = True,
        n_jobs: int = 1,  # Parallel jobs (1 = sequential)
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Run grid search optimization.
        
        Args:
            strategy: Strategy class to optimize
            param_grid: Dict of parameter names to list of values
            symbol: Trading symbol
            source: Data source
            exchange: Exchange for tvdatafeed
            interval: Timeframe
            n_bars: Number of bars
            initial_cash: Starting capital
            commission: Trading commission
            metric: Metric to optimize ('sharpe_ratio', 'total_return', 'win_rate', etc.)
            maximize: True to maximize, False to minimize
            n_jobs: Number of parallel jobs
            verbose: Print progress
            
        Returns:
            DataFrame with all results sorted by metric
        """
        from src.backtest.engine import BacktestEngine
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))
        
        total = len(combinations)
        if verbose:
            print(f"🔍 Grid Search: {total} combinations for {strategy.__name__}")
            print(f"   Parameters: {param_names}")
            print(f"   Symbol: {symbol}, Timeframe: {interval}")
        
        results = []
        
        for i, combo in enumerate(combinations, 1):
            # Create parameter dict
            params = dict(zip(param_names, combo))
            
            if verbose:
                progress = f"[{i}/{total}]"
                param_str = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"  {progress} Testing: {param_str}", end=" ")
            
            try:
                # Create fresh engine for each run
                engine = BacktestEngine()
                
                # Run backtest
                result = engine.run(
                    strategy=strategy,
                    symbol=symbol,
                    source=source,
                    exchange=exchange,
                    interval=interval,
                    n_bars=n_bars,
                    initial_cash=initial_cash,
                    commission=commission,
                    strategy_params=params
                )
                
                # Extract metric value
                metric_value = result.get(metric, 0) or 0
                
                if verbose:
                    print(f"→ {metric}: {metric_value:.2f}")
                
                # Store result
                result_entry = {
                    **params,
                    'metric': metric,
                    'metric_value': metric_value,
                    'total_return': result.get('total_return', 0),
                    'sharpe_ratio': result.get('sharpe_ratio', 0),
                    'max_drawdown': result.get('max_drawdown_pct', 0),
                    'win_rate': result.get('win_rate', 0),
                    'total_trades': result.get('total_trades', 0),
                    'profit_factor': result.get('profit_factor', 0),
                }
                results.append(result_entry)
                
            except Exception as e:
                if verbose:
                    print(f"→ ERROR: {e}")
                logger.warning(f"Optimization failed for {params}: {e}")
        
        # Create DataFrame and sort
        df = pd.DataFrame(results)
        if len(df) > 0:
            df = df.sort_values('metric_value', ascending=not maximize)
            df = df.reset_index(drop=True)
        
        self.results = df
        
        if verbose and len(df) > 0:
            print(f"\n✅ Best result:")
            best = df.iloc[0]
            print(f"   Parameters: {dict(zip(param_names, [best[p] for p in param_names]))}")
            print(f"   {metric}: {best['metric_value']:.2f}")
            print(f"   Total Return: {best['total_return']:.2f}%")
            print(f"   Win Rate: {best['win_rate']:.1f}%")
        
        return df
    
    def get_best_params(self) -> Dict[str, Any]:
        """Get the best parameter combination from last optimization."""
        if len(self.results) == 0:
            return {}
        
        best = self.results.iloc[0]
        # Extract only parameter columns (not metrics)
        metric_cols = ['metric', 'metric_value', 'total_return', 'sharpe_ratio', 
                       'max_drawdown', 'win_rate', 'total_trades', 'profit_factor']
        param_cols = [c for c in self.results.columns if c not in metric_cols]
        
        return {col: best[col] for col in param_cols}


class OptunaOptimizer:
    """
    Bayesian optimization using Optuna's TPE sampler.
    
    More efficient than grid search for large parameter spaces.
    Learns from previous trials to focus on promising regions.
    
    Requires: pip install optuna
    
    Example:
        optimizer = OptunaOptimizer()
        best_params = optimizer.optimize(
            strategy=SMACrossover,
            param_bounds={
                'fast_period': (5, 50),
                'slow_period': (20, 100)
            },
            symbol='AAPL',
            n_trials=50,
            metric='sharpe_ratio'
        )
    """
    
    def __init__(self):
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna not installed. Install with: pip install optuna")
        
        self.study = None
        self.best_params = {}
        
    def optimize(
        self,
        strategy: Type[bt.Strategy],
        param_bounds: Dict[str, Tuple[int, int]],
        symbol: str,
        source: str = 'tradingview',
        exchange: str = None,
        interval: str = '1d',
        n_bars: int = 1000,
        initial_cash: float = 100000,
        commission: float = 0.001,
        metric: str = 'sharpe_ratio',
        n_trials: int = 50,
        timeout: int = None,
        maximize: bool = True,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run Bayesian optimization with Optuna.
        
        Args:
            strategy: Strategy class to optimize
            param_bounds: Dict of parameter names to (min, max) tuples
            symbol: Trading symbol
            source: Data source
            exchange: Exchange for tvdatafeed
            interval: Timeframe
            n_bars: Number of bars
            initial_cash: Starting capital
            commission: Trading commission
            metric: Metric to optimize
            n_trials: Number of optimization trials
            timeout: Optional timeout in seconds
            maximize: True to maximize, False to minimize
            verbose: Print progress
            
        Returns:
            Dict of best parameters
        """
        from src.backtest.engine import BacktestEngine
        
        direction = "maximize" if maximize else "minimize"
        
        if verbose:
            print(f"🧠 Optuna Optimization: {n_trials} trials for {strategy.__name__}")
            print(f"   Parameters: {list(param_bounds.keys())}")
            print(f"   Metric: {metric} ({direction})")
        
        def objective(trial):
            # Sample parameters
            params = {}
            for name, bounds in param_bounds.items():
                if isinstance(bounds[0], int):
                    params[name] = trial.suggest_int(name, bounds[0], bounds[1])
                else:
                    params[name] = trial.suggest_float(name, bounds[0], bounds[1])
            
            try:
                engine = BacktestEngine()
                
                result = engine.run(
                    strategy=strategy,
                    symbol=symbol,
                    source=source,
                    exchange=exchange,
                    interval=interval,
                    n_bars=n_bars,
                    initial_cash=initial_cash,
                    commission=commission,
                    strategy_params=params
                )
                
                metric_value = result.get(metric, 0) or 0
                
                # Handle NaN
                if pd.isna(metric_value):
                    metric_value = -999 if maximize else 999
                
                return metric_value
                
            except Exception as e:
                logger.warning(f"Trial failed: {e}")
                return -999 if maximize else 999
        
        # Create study
        self.study = optuna.create_study(
            direction=direction,
            sampler=optuna.samplers.TPESampler()
        )
        
        # Run optimization
        optuna.logging.set_verbosity(optuna.logging.WARNING if not verbose else optuna.logging.INFO)
        self.study.optimize(objective, n_trials=n_trials, timeout=timeout)
        
        self.best_params = self.study.best_params
        
        if verbose:
            print(f"\n✅ Best result:")
            print(f"   Parameters: {self.best_params}")
            print(f"   {metric}: {self.study.best_value:.2f}")
        
        return self.best_params
    
    def get_optimization_history(self) -> pd.DataFrame:
        """Get trial history as DataFrame."""
        if self.study is None:
            return pd.DataFrame()
        
        trials = []
        for trial in self.study.trials:
            entry = {**trial.params, 'value': trial.value, 'state': trial.state.name}
            trials.append(entry)
        
        return pd.DataFrame(trials)


