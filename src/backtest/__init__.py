"""
Backtest Package
"""
from .engine import BacktestEngine
from .analyzers import DetailedAnalyzer
from .optimizer import GridSearchOptimizer, OPTUNA_AVAILABLE

if OPTUNA_AVAILABLE:
    from .optimizer import OptunaOptimizer
else:
    OptunaOptimizer = None

__all__ = [
    'BacktestEngine', 
    'DetailedAnalyzer',
    'GridSearchOptimizer',
    'OptunaOptimizer',
    'OPTUNA_AVAILABLE',
]

