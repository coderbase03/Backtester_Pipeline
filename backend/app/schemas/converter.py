"""
Pydantic schemas for Pine Script converter.
"""

from pydantic import BaseModel
from typing import Optional


class PineConvertRequest(BaseModel):
    code: str
    direction: str = "pine_to_python"  # pine_to_python, python_to_pine
    model: str = "glm-4.7"  # glm-4.7, gpt-4o-mini, claude-3-5-sonnet


class PineConvertResponse(BaseModel):
    converted_code: str
    direction: str
    model_used: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    is_valid: bool = False
    validation_error: Optional[str] = None
