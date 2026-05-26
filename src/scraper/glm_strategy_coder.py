# -*- coding: utf-8 -*-
"""
GLM-4.7 Strategy Coder (Backtrader-focused)

Converts extracted strategy ideas into executable Backtrader strategy code using Z.AI GLM API.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class CodegenResult:
    code: str
    valid: bool
    error: str | None
    model_used: str
    tokens_used: int
    cost_usd: float


class GLMStrategyCoder:
    MODEL = "glm-4.7"
    BASE_URL = "https://api.z.ai/api/paas/v4"
    INPUT_PRICE_PER_1M = 0.11
    OUTPUT_PRICE_PER_1M = 0.28

    SYSTEM_PROMPT = """You are an expert Backtrader developer.
Generate ONLY valid Python code for a strategy file.
Hard rules:
1) Must import backtrader as bt and BaseStrategy from src.strategies.base
2) Strategy class must inherit BaseStrategy
3) Must define params tuple including tp_pct, sl_pct, risk_pct, use_bracket
4) Must implement __init__ and next methods
5) If entry/exit rules are ambiguous, include safe fallback booleans (False) and comments
6) Use buy_with_bracket()/sell_with_bracket() when possible, else close() for exits
7) No markdown, no explanations, return code only
"""

    def __init__(self, model: str | None = None):
        if OpenAI is None:
            raise ImportError("openai package required")
        self.model = model or self.MODEL
        key = self._load_glm_key()
        if not key:
            raise ValueError("GLM_API_KEY not found in config/secrets.yaml")
        self.client = OpenAI(api_key=key, base_url=self.BASE_URL)

    def _load_glm_key(self) -> str | None:
        p = Path("config/secrets.yaml")
        if not p.exists():
            return None
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return (
            cfg.get("glm_api_key")
            or cfg.get("GLM_API_KEY")
            or (cfg.get("glm") or {}).get("api_key")
            or (cfg.get("api_keys") or {}).get("glm")
        )

    def _build_user_prompt(self, strategy_data: dict[str, Any], source_url: str = "") -> str:
        return f"""
Create a Backtrader strategy file from this extracted idea:

strategy_name: {strategy_data.get('strategy_name')}
summary: {strategy_data.get('summary')}
entry_rules: {strategy_data.get('entry_rules')}
exit_rules: {strategy_data.get('exit_rules')}
indicators: {strategy_data.get('indicators')}
tp_pct: {strategy_data.get('tp_pct', 3.0)}
sl_pct: {strategy_data.get('sl_pct', 1.5)}
source_url: {source_url}

Output must be executable Python code.
""".strip()

    def _extract_code(self, content: str) -> str:
        content = (content or "").strip()
        if content.startswith("```"):
            lines = [ln for ln in content.splitlines() if not ln.strip().startswith("```")]
            return "\n".join(lines).strip()
        return content

    def _validate(self, code: str) -> tuple[bool, str | None]:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"SyntaxError line {e.lineno}: {e.msg}"

        required = ["class ", "BaseStrategy", "def __init__", "def next", "params = ("]
        for r in required:
            if r not in code:
                return False, f"Missing required pattern: {r}"
        return True, None

    def generate_with_validation(self, strategy_data: dict[str, Any], source_url: str = "") -> CodegenResult:
        user_prompt = self._build_user_prompt(strategy_data, source_url)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2200,
        )

        content = response.choices[0].message.content or ""
        code = self._extract_code(content)

        usage = response.usage
        in_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
        out_tok = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = (in_tok / 1_000_000 * self.INPUT_PRICE_PER_1M) + (out_tok / 1_000_000 * self.OUTPUT_PRICE_PER_1M)

        valid, err = self._validate(code)
        return CodegenResult(
            code=code,
            valid=valid,
            error=err,
            model_used=self.model,
            tokens_used=in_tok + out_tok,
            cost_usd=cost,
        )
