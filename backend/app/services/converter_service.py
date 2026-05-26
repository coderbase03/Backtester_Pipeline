"""
Pine Script converter service.
"""

import sys
import logging
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[3]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

logger = logging.getLogger(__name__)


MODEL_MAP = {
    "glm": "glm-4.7",
    "glm-4.7": "glm-4.7",
    "openai": "gpt-4o-mini",
    "gpt-4o-mini": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet",
    "claude-3-5-sonnet": "claude-3-5-sonnet",
}


def _resolve_model(model: str) -> str:
    return MODEL_MAP.get((model or "").strip().lower(), model or "glm-4.7")


def convert_pine(code: str, direction: str = "pine_to_python", model: str = "glm-4.7") -> dict:
    """Convert between Pine Script and Python."""
    from src.converter.ai_pine_converter import AIPineConverter

    resolved_model = _resolve_model(model)
    converter = AIPineConverter(model=resolved_model, provider="auto")

    if direction == "pine_to_python":
        result = converter.pine_to_python(code)
    elif direction == "python_to_pine":
        result = converter.python_to_pine(code)
    else:
        raise ValueError(f"Invalid direction: {direction}")

    if not result.success:
        if direction == "pine_to_python":
            fallback = converter.pine_to_python(code, use_ai=False)
            if fallback.success and fallback.converted_code:
                result = fallback
                resolved_model = f"{resolved_model} (rule-fallback)"
            else:
                message = "; ".join(result.warnings) if result.warnings else "Conversion failed"
                raise RuntimeError(message)
        else:
            message = "; ".join(result.warnings) if result.warnings else "Conversion failed"
            raise RuntimeError(message)

    validation_errors = []
    if getattr(result, "validation", None) and result.validation.errors:
        validation_errors.extend(result.validation.errors)
    if result.warnings:
        validation_errors.extend(result.warnings)

    validation_error = "; ".join(validation_errors) if validation_errors else None

    return {
        "converted_code": (result.converted_code or "").strip(),
        "direction": direction,
        "model_used": resolved_model,
        "tokens_used": result.tokens_used if hasattr(result, "tokens_used") else 0,
        "cost_usd": result.cost_usd if hasattr(result, "cost_usd") else 0.0,
        "is_valid": bool(getattr(result.validation, "valid", False)),
        "validation_error": validation_error,
    }
