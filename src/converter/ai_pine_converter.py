# -*- coding: utf-8 -*-
"""
AI-Powered PineScript ↔ Python Converter

Bidirectional conversion between TradingView PineScript and Python/Backtrader
using GPT-4o-mini for intelligent code translation.

Features:
- Pine Script v5 → Python/Backtrader
- Python/Backtrader → Pine Script v5
- Syntax validation
- Token usage tracking
- Hybrid approach: Rule-based + AI

Usage:
    from src.converter.ai_pine_converter import AIPineConverter
    
    converter = AIPineConverter()
    
    # Pine to Python
    result = converter.pine_to_python(pine_code)
    print(result.converted_code)
    
    # Python to Pine
    result = converter.python_to_pine(python_code)
    print(result.converted_code)
"""

import os
import re
import ast
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .pine_converter import PineConverter, PineParser

logger = logging.getLogger(__name__)


class ConversionDirection(Enum):
    PINE_TO_PYTHON = "pine_to_python"
    PYTHON_TO_PINE = "python_to_pine"


@dataclass
class ValidationResult:
    """Validation result for converted code."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    

@dataclass
class ConversionResult:
    """Result of code conversion."""
    success: bool
    source_code: str
    converted_code: str
    direction: ConversionDirection
    tokens_used: int = 0
    cost_usd: float = 0.0
    validation: ValidationResult = None
    warnings: List[str] = field(default_factory=list)
    ai_notes: str = ""
    
    def __post_init__(self):
        if self.validation is None:
            self.validation = ValidationResult(valid=True)


# ============================================================
# PROMPTS
# ============================================================

PINE_TO_PYTHON_SYSTEM = """You are an expert code translator specializing in algorithmic trading strategies.
Your task is to convert TradingView PineScript v5 code to Python/Backtrader format.

CRITICAL RULES:
1. Generate ONLY valid Python code - no explanations outside the code
2. Use `bt.indicators` for all technical indicators
3. Strategies must inherit from `BaseStrategy` (from src.strategies.base)
4. Use `self.buy()` / `self.sell()` or `self.buy_with_bracket()` / `self.sell_with_bracket()` for entries
5. Convert `ta.*` functions to `bt.indicators` equivalents
6. Convert ternary operators `condition ? a : b` to Python `a if condition else b`
7. Convert `input.*` declarations to `params` tuple entries
8. Replace `na` with `float('nan')` or check with `math.isnan()`
9. Replace `true`/`false` with `True`/`False`
10. Pine Script array indexing `[1]` means previous bar, convert to `[-1]` in Python

INDICATOR MAPPING:
- ta.sma(src, len) → bt.indicators.SMA(src, period=len)
- ta.ema(src, len) → bt.indicators.EMA(src, period=len)
- ta.rsi(src, len) → bt.indicators.RSI(src, period=len)
- ta.atr(len) → bt.indicators.ATR(self.data, period=len)
- ta.macd(src, fast, slow, sig) → bt.indicators.MACD(src, period_me1=fast, period_me2=slow, period_signal=sig)
- ta.crossover(a, b) → bt.indicators.CrossOver(a, b)
- ta.crossunder(a, b) → use CrossOver and check for negative
- ta.highest(src, len) → bt.indicators.Highest(src, period=len)
- ta.lowest(src, len) → bt.indicators.Lowest(src, period=len)
- ta.stoch(close, high, low, len) → bt.indicators.Stochastic(self.data, period=len)
- ta.bb(src, len, mult) → bt.indicators.BollingerBands(src, period=len, devfactor=mult)
- ta.supertrend(factor, period) → Use custom SupertrendIndicator

STRATEGY TEMPLATE:
```python
from src.strategies.base import BaseStrategy
import backtrader as bt

class StrategyName(BaseStrategy):
    params = (
        ('param1', default_value),
        ('risk_pct', 0.02),
        ('tp_pct', 3.0),
        ('sl_pct', 1.5),
        ('trade_direction', 'both'),
        ('use_bracket', True),
    )
    
    def __init__(self):
        super().__init__()
        # Initialize indicators here
        
    def next(self):
        if self.order:
            return
        # Entry/exit logic here
```

Return ONLY the Python code wrapped in ```python``` markers."""

PYTHON_TO_PINE_SYSTEM = """You are an expert code translator specializing in algorithmic trading strategies.
Your task is to convert Python/Backtrader code to TradingView PineScript v5 format.

CRITICAL RULES:
1. Generate ONLY valid Pine Script v5 code - no explanations outside the code
2. Start with `//@version=5`
3. Use `strategy(...)` or `indicator(...)` declaration
4. Convert `bt.indicators` to `ta.*` functions
5. Convert `params` tuple to `input.*` declarations
6. Use `strategy.entry()` for entries, `strategy.close()` for exits
7. Convert Python conditions to Pine Script syntax
8. Use `?` ternary operator where appropriate

INDICATOR MAPPING (reverse):
- bt.indicators.SMA → ta.sma
- bt.indicators.EMA → ta.ema
- bt.indicators.RSI → ta.rsi
- bt.indicators.ATR → ta.atr
- bt.indicators.MACD → ta.macd
- bt.indicators.CrossOver → ta.crossover / ta.crossunder
- bt.indicators.Highest → ta.highest
- bt.indicators.Lowest → ta.lowest
- bt.indicators.BollingerBands → ta.bb
- bt.indicators.Stochastic → ta.stoch
- bt.indicators.Supertrend → ta.supertrend

VISUALIZATION REQUIREMENTS (CRITICAL):
1. Plot ALL indicators used in the strategy
2. Add entry/exit markers using plotshape()
3. Add position background coloring
4. Use proper colors and styling

PINE SCRIPT TEMPLATE:
```pinescript
//@version=5
strategy("Strategy Name", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=2)

// ===== INPUTS =====
param1 = input.int(14, "Parameter 1")
tpPct = input.float(3.0, "Take Profit %") / 100
slPct = input.float(1.5, "Stop Loss %") / 100

// ===== INDICATORS =====
indicator1 = ta.sma(close, param1)

// ===== ENTRY CONDITIONS =====
longCondition = ta.crossover(close, indicator1)
shortCondition = ta.crossunder(close, indicator1)

// ===== STRATEGY ENTRIES =====
if longCondition
    strategy.entry("Long", strategy.long)
    strategy.exit("Long Exit", "Long", profit=close * tpPct, loss=close * slPct)
    
if shortCondition
    strategy.entry("Short", strategy.short)
    strategy.exit("Short Exit", "Short", profit=close * tpPct, loss=close * slPct)

// ===== VISUALIZATION =====
// Plot indicators
plot(indicator1, color=color.blue, linewidth=2, title="Indicator")

// Entry/Exit markers
plotshape(longCondition, title="Long Entry", location=location.belowbar, 
          color=color.green, style=shape.triangleup, size=size.small)
plotshape(shortCondition, title="Short Entry", location=location.abovebar, 
          color=color.red, style=shape.triangledown, size=size.small)

// Position background
bgcolor(strategy.position_size > 0 ? color.new(color.green, 90) : 
        strategy.position_size < 0 ? color.new(color.red, 90) : na)
```

Return ONLY the Pine Script code wrapped in ```pinescript``` or ```pine``` markers."""


class AIPineConverter:
    """AI-powered bidirectional PineScript ↔ Python converter.
    
    Supports multiple AI providers:
    - GLM-4.7 (Zhipu AI) - Default for code generation (best price/performance)
    - GPT-4o-mini (OpenAI) - For text analysis tasks
    - Claude Sonnet (Anthropic) - Fallback for complex tasks
    """
    
    # Pricing per 1M tokens
    PRICING = {
        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
        'glm-4-plus': {'input': 0.50, 'output': 2.00},  # ¥5/1M ≈ $0.70
        'glm-4.7': {'input': 0.11, 'output': 0.28},     # Promotional rate
        'claude-3-5-sonnet': {'input': 3.00, 'output': 15.00},
    }
    
    # GLM API endpoint (z.ai international - OpenAI compatible)
    GLM_API_BASE = "https://api.z.ai/api/paas/v4"
    
    def __init__(self, model: str = "glm-4.7", provider: str = "auto"):
        """
        Initialize the AI converter.
        
        Args:
            model: Model to use for code conversion
                   - 'glm-4.7' (default): Best for coding, very cheap
                   - 'gpt-4o-mini': Good for text analysis
                   - 'claude-3-5-sonnet': High quality, expensive
            provider: 'auto', 'glm', 'openai', or 'anthropic'
        """
        self.model = model
        self.provider = provider
        self.rule_converter = PineConverter()
        
        # Clients for different providers
        self.glm_client = None
        self.openai_client = None
        self.active_client = None
        
        self._init_clients()
        
        # Token tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
    
    def _init_clients(self):
        """Initialize AI clients based on available API keys."""
        if OpenAI is None:
            logger.warning("OpenAI package not installed. AI features disabled.")
            return
        
        keys = self._load_api_keys()
        
        # Initialize GLM client (priority for coding)
        if keys.get('glm'):
            try:
                self.glm_client = OpenAI(
                    api_key=keys['glm'],
                    base_url=self.GLM_API_BASE
                )
                logger.info("GLM-4.7 client initialized (Zhipu AI)")
            except Exception as e:
                logger.warning(f"Failed to init GLM client: {e}")
        
        # Initialize OpenAI client
        if keys.get('openai'):
            try:
                self.openai_client = OpenAI(api_key=keys['openai'])
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to init OpenAI client: {e}")
        
        # Select active client based on provider preference
        self._select_active_client()
    
    def _select_active_client(self):
        """Select the active client based on model and provider settings."""
        if self.provider == 'glm' or self.model.startswith('glm'):
            self.active_client = self.glm_client
            if self.active_client:
                logger.info(f"Using GLM provider with model: {self.model}")
        elif self.provider == 'openai' or self.model.startswith('gpt'):
            self.active_client = self.openai_client
            if self.active_client:
                logger.info(f"Using OpenAI provider with model: {self.model}")
        elif self.provider == 'auto':
            # Auto: prefer GLM for coding, fallback to OpenAI
            if self.glm_client:
                self.active_client = self.glm_client
                self.model = 'glm-4.7' if not self.model.startswith('glm') else self.model
                logger.info("Auto-selected GLM-4.7 for code conversion")
            elif self.openai_client:
                self.active_client = self.openai_client
                self.model = 'gpt-4o-mini'
                logger.info("Fallback to GPT-4o-mini")
    
    def _load_api_keys(self) -> dict:
        """Load API keys from secrets.yaml."""
        keys = {'openai': None, 'glm': None, 'anthropic': None}
        
        try:
            from pathlib import Path
            import yaml
            
            config_path = Path(__file__).parent.parent.parent / "config" / "secrets.yaml"
            
            if not config_path.exists():
                logger.debug(f"Config file not found: {config_path}")
                return keys
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # OpenAI key
            keys['openai'] = (
                config.get('openai_api_key') or
                config.get('openai', {}).get('api_key') or
                config.get('OPENAI_API_KEY') or
                config.get('api_keys', {}).get('openai') or
                os.getenv('OPENAI_API_KEY')
            )
            
            # GLM key (Zhipu AI)
            keys['glm'] = (
                config.get('glm_api_key') or
                config.get('zhipu_api_key') or
                config.get('GLM_API_KEY') or
                config.get('glm', {}).get('api_key') or
                config.get('api_keys', {}).get('glm') or
                os.getenv('GLM_API_KEY')
            )
            
            # Anthropic key (for future use)
            keys['anthropic'] = (
                config.get('anthropic_api_key') or
                config.get('ANTHROPIC_API_KEY') or
                config.get('api_keys', {}).get('anthropic') or
                os.getenv('ANTHROPIC_API_KEY')
            )
            
            # Log what was found
            for provider, key in keys.items():
                if key:
                    logger.info(f"Loaded {provider.upper()} API key from secrets.yaml")
            
            return keys
            
        except Exception as e:
            logger.debug(f"Could not load secrets.yaml: {e}")
            return keys
    
    @property
    def client(self):
        """Backward compatibility: return active client."""
        return self.active_client
    
    def get_pricing(self) -> dict:
        """Get pricing for current model."""
        return self.PRICING.get(self.model, self.PRICING['gpt-4o-mini'])
    
    @property
    def INPUT_PRICE(self):
        return self.get_pricing()['input']
    
    @property
    def OUTPUT_PRICE(self):
        return self.get_pricing()['output']
    
    def pine_to_python(
        self, 
        pine_code: str,
        use_ai: bool = True,
        validate: bool = True
    ) -> ConversionResult:
        """
        Convert PineScript v5 to Python/Backtrader.
        
        Args:
            pine_code: PineScript source code
            use_ai: Use AI for conversion (True) or rule-based only (False)
            validate: Validate the converted code
            
        Returns:
            ConversionResult with converted code and metadata
        """
        if not pine_code.strip():
            return ConversionResult(
                success=False,
                source_code=pine_code,
                converted_code="",
                direction=ConversionDirection.PINE_TO_PYTHON,
                warnings=["Empty input code"]
            )
        
        # Try rule-based first if AI is disabled or unavailable
        if not use_ai or not self.client:
            return self._rule_based_pine_to_python(pine_code, validate)
        
        # AI-powered conversion
        return self._ai_convert(
            source_code=pine_code,
            direction=ConversionDirection.PINE_TO_PYTHON,
            system_prompt=PINE_TO_PYTHON_SYSTEM,
            validate=validate
        )
    
    def python_to_pine(
        self,
        python_code: str,
        use_ai: bool = True,
        validate: bool = True
    ) -> ConversionResult:
        """
        Convert Python/Backtrader to PineScript v5.
        
        Args:
            python_code: Python source code
            use_ai: Use AI for conversion (True) or rule-based only (False)
            validate: Validate the converted code
            
        Returns:
            ConversionResult with converted code and metadata
        """
        if not python_code.strip():
            return ConversionResult(
                success=False,
                source_code=python_code,
                converted_code="",
                direction=ConversionDirection.PYTHON_TO_PINE,
                warnings=["Empty input code"]
            )
        
        if not use_ai or not self.client:
            return ConversionResult(
                success=False,
                source_code=python_code,
                converted_code="",
                direction=ConversionDirection.PYTHON_TO_PINE,
                warnings=["Python→Pine requires AI mode. Please enable AI."]
            )
        
        # AI-powered conversion
        return self._ai_convert(
            source_code=python_code,
            direction=ConversionDirection.PYTHON_TO_PINE,
            system_prompt=PYTHON_TO_PINE_SYSTEM,
            validate=validate
        )
    
    def _rule_based_pine_to_python(
        self, 
        pine_code: str,
        validate: bool = True
    ) -> ConversionResult:
        """Use rule-based converter (fallback)."""
        try:
            converted = self.rule_converter.convert(pine_code)
            
            validation = None
            if validate:
                validation = self.validate_python(converted)
            
            return ConversionResult(
                success=True,
                source_code=pine_code,
                converted_code=converted,
                direction=ConversionDirection.PINE_TO_PYTHON,
                validation=validation,
                warnings=["Converted using rule-based method. Manual review recommended."]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                source_code=pine_code,
                converted_code="",
                direction=ConversionDirection.PINE_TO_PYTHON,
                warnings=[f"Conversion failed: {str(e)}"]
            )
    
    def _ai_convert(
        self,
        source_code: str,
        direction: ConversionDirection,
        system_prompt: str,
        validate: bool = True
    ) -> ConversionResult:
        """Perform AI-powered conversion."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Convert this code:\n\n```\n{source_code}\n```"}
                ],
                temperature=0.2,  # Low temperature for deterministic output
                max_tokens=4000,
            )
            
            # Extract tokens and calculate cost
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            cost = (input_tokens / 1_000_000 * self.INPUT_PRICE) + \
                   (output_tokens / 1_000_000 * self.OUTPUT_PRICE)
            
            # Update tracking
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            self._total_cost += cost
            
            # Extract code from response
            content = response.choices[0].message.content
            converted_code = self._extract_code(content, direction)
            
            # Extract AI notes (any text outside code blocks)
            ai_notes = self._extract_notes(content)
            
            # Validate if requested
            validation = None
            if validate:
                if direction == ConversionDirection.PINE_TO_PYTHON:
                    validation = self.validate_python(converted_code)
                else:
                    validation = self.validate_pine(converted_code)
            
            return ConversionResult(
                success=True,
                source_code=source_code,
                converted_code=converted_code,
                direction=direction,
                tokens_used=input_tokens + output_tokens,
                cost_usd=cost,
                validation=validation,
                ai_notes=ai_notes
            )
            
        except Exception as e:
            logger.error(f"AI conversion failed: {e}")
            return ConversionResult(
                success=False,
                source_code=source_code,
                converted_code="",
                direction=direction,
                warnings=[f"AI conversion failed: {str(e)}"]
            )
    
    def _extract_code(self, content: str, direction: ConversionDirection) -> str:
        """Extract code from AI response."""
        # Try to find code block
        if direction == ConversionDirection.PINE_TO_PYTHON:
            pattern = r'```python\s*(.*?)```'
        else:
            pattern = r'```(?:pinescript|pine)?\s*(.*?)```'
        
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # If no code block, return the whole content (cleaned)
        return content.strip()
    
    def _extract_notes(self, content: str) -> str:
        """Extract notes/explanations from AI response."""
        # Remove code blocks
        cleaned = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        return cleaned.strip()
    
    def validate_python(self, code: str) -> ValidationResult:
        """Validate Python code syntax."""
        errors = []
        suggestions = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        
        # Check for common issues
        if 'bt.indicators' in code and 'import backtrader' not in code:
            suggestions.append("Missing 'import backtrader as bt'")
        
        if 'BaseStrategy' in code and 'from src.strategies.base' not in code:
            suggestions.append("Missing BaseStrategy import")
        
        if 'self.buy(' in code and 'def next(' not in code:
            suggestions.append("Missing next() method")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            suggestions=suggestions
        )
    
    def validate_pine(self, code: str) -> ValidationResult:
        """Validate PineScript code (basic checks)."""
        errors = []
        suggestions = []
        
        # Check version
        if '//@version=' not in code:
            errors.append("Missing //@version= declaration")
        
        # Check declaration
        if 'strategy(' not in code and 'indicator(' not in code:
            errors.append("Missing strategy() or indicator() declaration")
        
        # Check for common syntax issues
        if '==' in code.split('\n')[0]:  # Avoiding false positives
            pass  # OK
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            suggestions=suggestions
        )
    
    def fix_code(
        self,
        broken_code: str,
        error_message: str,
        original_pine: str = "",
        max_attempts: int = 3
    ) -> ConversionResult:
        """
        Attempt to fix broken Python code using AI.
        
        Args:
            broken_code: The code that has errors
            error_message: The error message from the failed attempt
            original_pine: Original PineScript code (for context)
            max_attempts: Maximum number of fix attempts
            
        Returns:
            ConversionResult with fixed code or failure info
        """
        if not self.client:
            return ConversionResult(
                success=False,
                source_code=broken_code,
                converted_code=broken_code,
                direction=ConversionDirection.PINE_TO_PYTHON,
                warnings=["AI not available for code fixing"]
            )
        
        fix_prompt = f"""You are fixing a Python/Backtrader strategy that has errors.

ORIGINAL PINE SCRIPT (for reference):
```pinescript
{original_pine if original_pine else 'Not provided'}
```

BROKEN PYTHON CODE:
```python
{broken_code}
```

ERROR MESSAGE:
{error_message}

Please fix the Python code to resolve this error. The code should:
1. Be valid Python syntax
2. Work with Backtrader framework
3. Inherit from BaseStrategy
4. Have proper __init__ and next methods

Return ONLY the fixed Python code wrapped in ```python``` markers."""

        total_tokens = 0
        total_cost = 0.0
        last_error = error_message
        current_code = broken_code
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert Python/Backtrader developer fixing trading strategy code."},
                        {"role": "user", "content": fix_prompt if attempt == 0 else f"""
The previous fix attempt still has errors.

CODE:
```python
{current_code}
```

NEW ERROR:
{last_error}

Please fix this error. Return ONLY the fixed Python code wrapped in ```python``` markers.
"""}
                    ],
                    temperature=0.2,
                    max_tokens=4000,
                )
                
                usage = response.usage
                tokens = usage.prompt_tokens + usage.completion_tokens
                cost = (usage.prompt_tokens / 1_000_000 * self.INPUT_PRICE) + \
                       (usage.completion_tokens / 1_000_000 * self.OUTPUT_PRICE)
                
                total_tokens += tokens
                total_cost += cost
                
                content = response.choices[0].message.content
                fixed_code = self._extract_code(content, ConversionDirection.PINE_TO_PYTHON)
                
                # Validate the fixed code
                validation = self.validate_python(fixed_code)
                
                if validation.valid:
                    # Try to compile it
                    try:
                        compile(fixed_code, '<string>', 'exec')
                        
                        return ConversionResult(
                            success=True,
                            source_code=broken_code,
                            converted_code=fixed_code,
                            direction=ConversionDirection.PINE_TO_PYTHON,
                            tokens_used=total_tokens,
                            cost_usd=total_cost,
                            validation=validation,
                            ai_notes=f"Fixed after {attempt + 1} attempt(s)"
                        )
                    except SyntaxError as e:
                        last_error = f"Syntax error: {e}"
                        current_code = fixed_code
                else:
                    last_error = "; ".join(validation.errors)
                    current_code = fixed_code
                    
            except Exception as e:
                last_error = str(e)
        
        # All attempts failed
        return ConversionResult(
            success=False,
            source_code=broken_code,
            converted_code=current_code,
            direction=ConversionDirection.PINE_TO_PYTHON,
            tokens_used=total_tokens,
            cost_usd=total_cost,
            warnings=[f"Could not fix code after {max_attempts} attempts. Last error: {last_error}"]
        )
    
    def get_stats(self) -> Dict:
        """Get usage statistics."""
        return {
            'total_input_tokens': self._total_input_tokens,
            'total_output_tokens': self._total_output_tokens,
            'total_tokens': self._total_input_tokens + self._total_output_tokens,
            'total_cost': self._total_cost,
        }
    
    def reset_stats(self):
        """Reset usage statistics."""
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0


# ============================================================
# DEMO
# ============================================================

def demo():
    """Demo the AI converter."""
    pine_sample = '''
//@version=5
strategy("RSI Mean Reversion", overlay=false)

// Inputs
rsi_length = input.int(14, "RSI Length")
oversold = input.int(30, "Oversold Level")
overbought = input.int(70, "Overbought Level")

// RSI calculation
rsi_value = ta.rsi(close, rsi_length)

// Entry conditions
long_condition = ta.crossover(rsi_value, oversold)
short_condition = ta.crossunder(rsi_value, overbought)

// Strategy entries
if long_condition
    strategy.entry("Long", strategy.long)
if short_condition
    strategy.entry("Short", strategy.short)

// Plot
plot(rsi_value, color=color.blue, linewidth=2)
hline(oversold, color=color.green)
hline(overbought, color=color.red)
'''
    
    print("=" * 60)
    print("AI PineScript Converter Demo")
    print("=" * 60)
    
    converter = AIPineConverter()
    
    if converter.client:
        print("\n🔄 Converting Pine Script → Python...")
        result = converter.pine_to_python(pine_sample)
        
        if result.success:
            print("\n✅ Conversion successful!")
            print(f"📊 Tokens used: {result.tokens_used}")
            print(f"💰 Cost: ${result.cost_usd:.4f}")
            print(f"✓ Valid: {result.validation.valid}")
            print("\n--- Converted Code ---")
            print(result.converted_code[:1500] + "..." if len(result.converted_code) > 1500 else result.converted_code)
        else:
            print(f"\n❌ Conversion failed: {result.warnings}")
    else:
        print("\n⚠️ OpenAI client not initialized. Using rule-based conversion...")
        result = converter.pine_to_python(pine_sample, use_ai=False)
        print(result.converted_code[:1000])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
