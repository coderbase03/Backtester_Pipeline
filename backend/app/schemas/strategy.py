"""
Pydantic schemas for strategy endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class StrategyInfo(BaseModel):
    name: str
    class_name: str
    description: Optional[str] = None
    category: str = "built-in"
    params: dict = {}


class StrategyParamInfo(BaseModel):
    name: str
    default: float | int | str | bool
    description: Optional[str] = None
    param_type: str = "float"


class FilteredStrategyResponse(BaseModel):
    id: int
    strategy_name: Optional[str] = None
    summary: Optional[str] = None
    entry_rules: Optional[str] = None
    exit_rules: Optional[str] = None
    ai_score: int = 0
    ai_category: Optional[str] = None
    source_url: Optional[str] = None
    status: str = "pending"
    generated_code: Optional[str] = None
    code_valid: bool = False
