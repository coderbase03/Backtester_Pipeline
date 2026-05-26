"""
Pine Script to Python Converter

Converts TradingView Pine Script code to Python/Backtrader format.

Features:
- Parses Pine Script syntax
- Maps common functions to Python equivalents
- Generates Backtrader strategy/indicator templates
- Supports indicators and strategies

Usage:
    from src.converter import PineConverter
    
    pine_code = '''
    //@version=5
    indicator("My RSI", overlay=false)
    rsi_val = ta.rsi(close, 14)
    plot(rsi_val)
    '''
    
    converter = PineConverter()
    python_code = converter.convert(pine_code)
    print(python_code)

Note: Auto-conversion is approximate. Manual review is recommended.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class PineType(Enum):
    INDICATOR = "indicator"
    STRATEGY = "strategy"
    LIBRARY = "library"


@dataclass
class PineFunction:
    """Represents a Pine Script function call."""
    name: str
    args: List[str]
    pine_syntax: str
    python_equivalent: str


# Pine Script to Python/Backtrader function mapping
FUNCTION_MAP = {
    # Technical Indicators
    'ta.sma': 'bt.indicators.SMA({source}, period={period})',
    'ta.ema': 'bt.indicators.EMA({source}, period={period})',
    'ta.rsi': 'bt.indicators.RSI({source}, period={period})',
    'ta.macd': 'bt.indicators.MACD({source}, period_me1={fast}, period_me2={slow}, period_signal={signal})',
    'ta.atr': 'bt.indicators.ATR(self.data, period={period})',
    'ta.stoch': 'bt.indicators.Stochastic(self.data, period={period})',
    'ta.bb': 'bt.indicators.BollingerBands({source}, period={period}, devfactor={mult})',
    'ta.wma': 'bt.indicators.WMA({source}, period={period})',
    'ta.vwap': 'bt.indicators.VWAP(self.data)',
    'ta.supertrend': 'SupertrendIndicator(self.data, period={period}, multiplier={mult})',
    
    # Math functions
    'math.abs': 'abs({x})',
    'math.max': 'max({a}, {b})',
    'math.min': 'min({a}, {b})',
    'math.sqrt': 'math.sqrt({x})',
    'math.pow': 'pow({base}, {exp})',
    'math.log': 'math.log({x})',
    'math.round': 'round({x})',
    
    # Price data
    'close': 'self.data.close[0]',
    'open': 'self.data.open[0]',
    'high': 'self.data.high[0]',
    'low': 'self.data.low[0]',
    'volume': 'self.data.volume[0]',
    'close[1]': 'self.data.close[-1]',
    'high[1]': 'self.data.high[-1]',
    'low[1]': 'self.data.low[-1]',
    
    # Crossover functions
    'ta.crossover': 'bt.indicators.CrossOver({a}, {b})[0] > 0',
    'ta.crossunder': 'bt.indicators.CrossOver({a}, {b})[0] < 0',
    'ta.cross': 'bt.indicators.CrossOver({a}, {b})[0] != 0',
    
    # Comparison
    'ta.highest': 'bt.indicators.Highest(self.data.high, period={period})[0]',
    'ta.lowest': 'bt.indicators.Lowest(self.data.low, period={period})[0]',
    'ta.change': '({source}[0] - {source}[-1])',
    
    # Strategy functions
    'strategy.entry': 'self.buy() if {direction} == "long" else self.sell()',
    'strategy.close': 'self.close()',
    'strategy.exit': 'self.close()',
}

# Pine Script keywords to Python
KEYWORD_MAP = {
    'var': '',  # Variable declaration (not needed in Python)
    'varip': '',
    'true': 'True',
    'false': 'False',
    'na': 'float("nan")',
    'and': 'and',
    'or': 'or',
    'not': 'not',
    ':=': '=',  # Assignment
    '?': '# TERNARY: ',  # Ternary operator needs manual conversion
}


class PineParser:
    """Parses Pine Script code into structured components."""
    
    def __init__(self, code: str):
        self.code = code
        self.lines = code.strip().split('\n')
        self.version = self._detect_version()
        self.script_type = self._detect_type()
        self.title = self._extract_title()
        self.inputs = []
        self.variables = []
        self.indicators = []
        self.conditions = []
        self.plots = []
    
    def _detect_version(self) -> int:
        """Detect Pine Script version."""
        for line in self.lines[:5]:
            if '@version=' in line:
                match = re.search(r'@version=(\d+)', line)
                if match:
                    return int(match.group(1))
        return 5  # Default to v5
    
    def _detect_type(self) -> PineType:
        """Detect script type (indicator/strategy)."""
        for line in self.lines[:10]:
            if 'strategy(' in line:
                return PineType.STRATEGY
            elif 'indicator(' in line:
                return PineType.INDICATOR
            elif 'library(' in line:
                return PineType.LIBRARY
        return PineType.INDICATOR
    
    def _extract_title(self) -> str:
        """Extract script title."""
        pattern = r'(?:indicator|strategy)\s*\(\s*["\']([^"\']+)["\']'
        for line in self.lines:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
        return "ConvertedScript"
    
    def parse(self) -> Dict:
        """Parse the Pine Script code."""
        result = {
            'version': self.version,
            'type': self.script_type,
            'title': self.title,
            'inputs': [],
            'variables': [],
            'indicators': [],
            'conditions': [],
            'plots': [],
            'raw_lines': [],
        }
        
        for line in self.lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # Parse inputs
            if 'input.' in line or 'input(' in line:
                result['inputs'].append(self._parse_input(line))
            
            # Parse indicator calls
            elif 'ta.' in line:
                result['indicators'].append(line)
            
            # Parse conditions
            elif 'if ' in line or 'else' in line:
                result['conditions'].append(line)
            
            # Parse plots
            elif 'plot(' in line or 'plotshape(' in line:
                result['plots'].append(line)
            
            # Parse variable assignments
            elif '=' in line and not line.startswith('//@'):
                result['variables'].append(line)
            
            result['raw_lines'].append(line)
        
        return result
    
    def _parse_input(self, line: str) -> Dict:
        """Parse input declaration."""
        # Match: name = input.type(default, title="...")
        pattern = r'(\w+)\s*=\s*input\.?(\w*)\s*\(([^)]*)\)'
        match = re.search(pattern, line)
        
        if match:
            return {
                'name': match.group(1),
                'type': match.group(2) or 'float',
                'args': match.group(3),
                'raw': line,
            }
        return {'raw': line}


class PineConverter:
    """Converts Pine Script to Python/Backtrader code."""
    
    def __init__(self):
        self.function_map = FUNCTION_MAP
        self.keyword_map = KEYWORD_MAP
    
    def convert(self, pine_code: str) -> str:
        """
        Convert Pine Script to Python/Backtrader.
        
        Args:
            pine_code: Pine Script source code
            
        Returns:
            Python code as string
        """
        parser = PineParser(pine_code)
        parsed = parser.parse()
        
        if parsed['type'] == PineType.STRATEGY:
            return self._generate_strategy(parsed)
        else:
            return self._generate_indicator(parsed)
    
    def _convert_line(self, line: str) -> str:
        """Convert a single line of Pine Script."""
        result = line
        
        # Replace keywords
        for pine_kw, py_kw in self.keyword_map.items():
            result = result.replace(pine_kw, py_kw)
        
        # Replace function calls
        for pine_func, py_func in self.function_map.items():
            if pine_func in result:
                result = self._convert_function(result, pine_func, py_func)
        
        return result
    
    def _convert_function(self, line: str, pine_func: str, py_template: str) -> str:
        """Convert a Pine Script function to Python."""
        # Simple replacement for now
        # More complex parsing would be needed for full support
        
        # Handle ta.sma(close, 14) -> bt.indicators.SMA(self.data.close, period=14)
        pattern = rf'{re.escape(pine_func)}\s*\(([^)]+)\)'
        match = re.search(pattern, line)
        
        if match:
            args = [a.strip() for a in match.group(1).split(',')]
            
            # Build Python equivalent
            if 'period' in py_template and len(args) >= 2:
                py_code = py_template.replace('{source}', f'self.data.{args[0]}')
                py_code = py_code.replace('{period}', args[1])
            elif len(args) == 1:
                py_code = py_template.replace('{source}', f'self.data.{args[0]}')
            else:
                py_code = f"# {line}  # TODO: Convert manually"
            
            line = line.replace(match.group(0), py_code)
        
        return line
    
    def _generate_indicator(self, parsed: Dict) -> str:
        """Generate Backtrader indicator code."""
        title = self._to_class_name(parsed['title'])
        
        # Generate params from inputs
        params = []
        for inp in parsed['inputs']:
            if 'name' in inp:
                params.append(f"        ('{inp['name']}', 14),  # TODO: Set default")
        
        params_str = '\n'.join(params) if params else "        ('period', 14),"
        
        # Convert indicator lines
        indicator_lines = []
        for line in parsed['indicators']:
            converted = self._convert_line(line)
            indicator_lines.append(f"        {converted}")
        
        indicators_str = '\n'.join(indicator_lines) if indicator_lines else "        # TODO: Add indicator logic"
        
        # Generate template
        template = f'''"""
{parsed['title']} - Converted from Pine Script v{parsed['version']}

Auto-generated by PineConverter. Manual review recommended.
"""

import backtrader as bt
import math


class {title}(bt.Indicator):
    """
    {parsed['title']} Indicator
    
    Converted from TradingView Pine Script.
    """
    
    lines = ('signal',)  # TODO: Define output lines
    
    params = (
{params_str}
    )
    
    plotinfo = dict(subplot=True)
    
    def __init__(self):
        # TODO: Initialize indicators
{indicators_str}
    
    def next(self):
        # TODO: Calculate indicator values
        # Original Pine Script lines:
'''
        
        # Add original lines as comments
        for line in parsed['raw_lines']:
            template += f"        # {line}\n"
        
        template += '''        
        pass  # TODO: Implement logic
'''
        
        return template
    
    def _generate_strategy(self, parsed: Dict) -> str:
        """Generate Backtrader strategy code."""
        title = self._to_class_name(parsed['title'])
        
        # Generate params
        params = []
        for inp in parsed['inputs']:
            if 'name' in inp:
                params.append(f"        ('{inp['name']}', 14),  # TODO: Set default")
        
        params_str = '\n'.join(params) if params else "        ('period', 14),"
        
        # Convert indicator lines
        indicator_lines = []
        for line in parsed['indicators']:
            converted = self._convert_line(line)
            indicator_lines.append(f"        self.{converted}")
        
        indicators_str = '\n'.join(indicator_lines) if indicator_lines else "        # TODO: Add indicators"
        
        # Convert conditions
        condition_lines = []
        for line in parsed['conditions']:
            converted = self._convert_line(line)
            condition_lines.append(f"        {converted}")
        
        conditions_str = '\n'.join(condition_lines) if condition_lines else "        # TODO: Add entry/exit conditions"
        
        template = f'''"""
{parsed['title']} Strategy - Converted from Pine Script v{parsed['version']}

Auto-generated by PineConverter. Manual review recommended.
"""

import backtrader as bt
import math

from src.strategies.base import BaseStrategy


class {title}(BaseStrategy):
    """
    {parsed['title']} Strategy
    
    Converted from TradingView Pine Script.
    """
    
    params = (
{params_str}
        ('risk_pct', 0.02),
        ('tp_pct', 3.0),
        ('sl_pct', 1.5),
        ('trade_direction', 'both'),
        ('use_bracket', True),
    )
    
    def __init__(self):
        super().__init__()
        
        # Indicators
{indicators_str}
    
    def next(self):
        if self.order:
            return
        
        # Entry/Exit Logic
        # Original Pine Script:
'''
        
        # Add original lines as comments
        for line in parsed['raw_lines']:
            template += f"        # {line}\n"
        
        template += f'''
        # TODO: Implement entry/exit logic
{conditions_str}
        
        # Example entry:
        # if buy_condition:
        #     self.buy_with_bracket()
        # elif sell_condition:
        #     self.sell_with_bracket()
'''
        
        return template
    
    def _to_class_name(self, title: str) -> str:
        """Convert title to valid Python class name."""
        # Remove special characters, capitalize words
        words = re.sub(r'[^a-zA-Z0-9\s]', '', title).split()
        return ''.join(word.capitalize() for word in words)
    
    def convert_file(self, input_path: str, output_path: str = None) -> str:
        """
        Convert Pine Script file to Python file.
        
        Args:
            input_path: Path to .pine or .txt file
            output_path: Output path (auto-generated if None)
            
        Returns:
            Path to generated Python file
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            pine_code = f.read()
        
        python_code = self.convert(pine_code)
        
        if output_path is None:
            output_path = input_path.rsplit('.', 1)[0] + '_converted.py'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(python_code)
        
        return output_path


# Demo
def demo():
    """Demo Pine Script conversion."""
    
    pine_code = '''
//@version=5
strategy("Simple SMA Crossover", overlay=true)

// Inputs
fast_length = input.int(10, "Fast SMA Length")
slow_length = input.int(30, "Slow SMA Length")

// Calculate SMAs
fast_sma = ta.sma(close, fast_length)
slow_sma = ta.sma(close, slow_length)

// Entry conditions
long_condition = ta.crossover(fast_sma, slow_sma)
short_condition = ta.crossunder(fast_sma, slow_sma)

// Strategy entries
if long_condition
    strategy.entry("Long", strategy.long)
if short_condition
    strategy.entry("Short", strategy.short)

// Plot
plot(fast_sma, color=color.blue)
plot(slow_sma, color=color.red)
'''
    
    print("=" * 60)
    print("Pine Script to Python Converter Demo")
    print("=" * 60)
    print("\nOriginal Pine Script:")
    print("-" * 40)
    print(pine_code)
    
    converter = PineConverter()
    python_code = converter.convert(pine_code)
    
    print("\nConverted Python Code:")
    print("-" * 40)
    print(python_code)


if __name__ == "__main__":
    demo()
