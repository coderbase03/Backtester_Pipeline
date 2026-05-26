"""
Strategy API routes.
"""

from fastapi import APIRouter, HTTPException
from ...schemas.strategy import StrategyInfo
from ...services import backtest_service

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyInfo])
async def list_strategies():
    """List all available built-in strategies."""
    return backtest_service.list_strategies()


@router.get("/{name}/params")
async def get_strategy_params(name: str):
    """Get parameter definitions for a strategy."""
    try:
        cls = backtest_service.get_strategy_class(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    params = []
    if hasattr(cls, "params") and isinstance(cls.params, tuple):
        for p in cls.params:
            if isinstance(p, tuple) and len(p) == 2:
                pname, default = p
                params.append({
                    "name": pname,
                    "default": default,
                    "param_type": type(default).__name__,
                })
    return {"strategy": name, "class_name": cls.__name__, "params": params}
