# -*- coding: utf-8 -*-
"""
Strategy Code Generator

AI'dan çıkarılan stratejileri Backtrader Python koduna çevirir.

Usage:
    from src.scraper.code_generator import StrategyCodeGenerator
    
    generator = StrategyCodeGenerator()
    code = generator.generate(strategy_data)
"""

import re
import logging
from typing import Dict, List, Optional, Any
from string import Template

logger = logging.getLogger(__name__)


# Desteklenen indikatörler ve Backtrader karşılıkları
INDICATOR_MAP = {
    'sma': ('bt.indicators.SMA', 'period'),
    'ema': ('bt.indicators.EMA', 'period'),
    'rsi': ('bt.indicators.RSI', 'period'),
    'macd': ('bt.indicators.MACD', 'period_me1,period_me2,period_signal'),
    'bollinger': ('bt.indicators.BollingerBands', 'period,devfactor'),
    'atr': ('bt.indicators.ATR', 'period'),
    'supertrend': ('SupertrendIndicator', 'period,multiplier'),
    'stochastic': ('bt.indicators.Stochastic', 'period,period_dfast'),
    'adx': ('bt.indicators.ADX', 'period'),
    'cci': ('bt.indicators.CCI', 'period'),
}


# Jenerik test konfigürasyonu
TEST_CONFIG = {
    'symbols': {
        'US Stocks': [('AAPL', 'NASDAQ'), ('MSFT', 'NASDAQ'), ('SPY', 'AMEX')],
        'Crypto': [('BTCUSDT', 'BINANCE'), ('ETHUSDT', 'BINANCE'), ('SOLUSDT', 'BINANCE')],
        'Forex': [('EURUSD', 'FX_IDC'), ('GBPUSD', 'FX_IDC'), ('USDJPY', 'FX_IDC')],
        'Commodities': [('GOLD', 'TVC'), ('SILVER', 'TVC'), ('USOIL', 'TVC')],
    },
    'timeframes': ['1h', '4h', '1d'],
}


# Strateji şablonu
STRATEGY_TEMPLATE = '''# -*- coding: utf-8 -*-
"""
${strategy_name}

Auto-generated from Reddit post analysis.
Source: ${source_url}

Summary:
${summary}

Entry Rules: ${entry_rules}
Exit Rules: ${exit_rules}
TP/SL: ${tp_pct}% / ${sl_pct}%
"""

import backtrader as bt
from src.strategies.base import BaseStrategy


class ${class_name}(BaseStrategy):
    """
    ${strategy_name}
    
    ${summary}
    
    AI Notes:
    ${ai_notes}
    """
    
    params = (
${params_section}
    )
    
    def __init__(self):
        super().__init__()
        
        # Indicators
${indicators_section}
        
        # Entry/Exit signals
        self.entry_signal = None
        self.exit_signal = None
    
    def next(self):
        # Skip if order pending
        if self.order:
            return
        
        # Calculate signals
        self._update_signals()
        
        # Position management
        if not self.position:
            # Entry logic
            if self.entry_signal:
                self.buy_bracket()
        else:
            # Exit logic
            if self.exit_signal:
                self.close()
    
    def _update_signals(self):
        """Update entry and exit signals based on strategy rules."""
        try:
${signal_logic}
        except Exception as e:
            self.entry_signal = False
            self.exit_signal = False


# Test configuration
TEST_SYMBOLS = ${test_symbols}
TEST_TIMEFRAMES = ${test_timeframes}
'''


class StrategyCodeGenerator:
    """Strateji Python kodu üreteci."""
    
    def __init__(self):
        self.template = Template(STRATEGY_TEMPLATE)
    
    def generate(self, strategy_data: Dict, source_url: str = "") -> str:
        """
        Strateji verisinden Python kodu üret.
        
        Args:
            strategy_data: AI'dan çıkarılan strateji verisi
            source_url: Kaynak Reddit URL
            
        Returns:
            Python kod string
        """
        # Class name oluştur
        strategy_name = strategy_data.get('strategy_name', 'CustomStrategy')
        class_name = self._to_class_name(strategy_name)
        
        # İndikatörleri işle
        indicators = strategy_data.get('indicators', [])
        if isinstance(indicators, str):
            indicators = []  # JSON parse hatası durumunda
        params_section = self._generate_params(strategy_data, indicators)
        indicators_section = self._generate_indicators(indicators)
        
        # Signal logic
        entry_rules = strategy_data.get('entry_rules', '') or ''
        exit_rules = strategy_data.get('exit_rules', '') or ''
        signal_logic = self._generate_signal_logic(entry_rules, exit_rules, indicators)
        
        # Clean text fields for docstring compatibility
        summary = self._clean_docstring(strategy_data.get('summary', 'No description'))
        ai_notes = self._clean_docstring(strategy_data.get('ai_notes', ''))
        
        # Template doldur
        code = self.template.substitute(
            strategy_name=strategy_name,
            class_name=class_name,
            source_url=source_url or "N/A",
            summary=summary,
            entry_rules=entry_rules or "Manual",
            exit_rules=exit_rules or "Manual/TP/SL",
            tp_pct=strategy_data.get('tp_pct', 3.0),
            sl_pct=strategy_data.get('sl_pct', 1.5),
            ai_notes=ai_notes,
            params_section=params_section,
            indicators_section=indicators_section,
            signal_logic=signal_logic,
            test_symbols=repr(TEST_CONFIG['symbols']),
            test_timeframes=repr(TEST_CONFIG['timeframes']),
        )
        
        return code
    
    def _clean_docstring(self, text: str) -> str:
        """Docstring için metin temizle - özel karakterleri kaldır."""
        if not text:
            return ""
        # Newlines'ı single space'e çevir
        text = ' '.join(text.split())
        # Triple quotes'u escape et
        text = text.replace('"""', "'''")
        text = text.replace("'''", "")
        return text
    
    def _to_class_name(self, name: str) -> str:
        """String'i geçerli Python class adına çevir."""
        # Özel karakterleri kaldır
        name = re.sub(r'[^\w\s]', '', name)
        # CamelCase yap
        words = name.split()
        class_name = ''.join(word.capitalize() for word in words)
        # Sayı ile başlıyorsa prefix ekle
        if class_name and class_name[0].isdigit():
            class_name = 'Strategy' + class_name
        return class_name or 'CustomStrategy'
    
    def _generate_params(self, strategy_data: Dict, indicators: List[Dict]) -> str:
        """Strateji parametrelerini üret."""
        params = []
        
        # TP/SL parametreleri
        params.append(f"        ('tp_pct', {strategy_data.get('tp_pct', 3.0)}),")
        params.append(f"        ('sl_pct', {strategy_data.get('sl_pct', 1.5)}),")
        params.append(f"        ('risk_pct', 0.02),")
        params.append(f"        ('use_bracket', True),")
        
        # İndikatör parametreleri
        for ind in indicators:
            ind_name = ind.get('name', '').lower()
            ind_params = ind.get('params', {})
            
            for key, value in ind_params.items():
                param_name = f"{ind_name}_{key}"
                params.append(f"        ('{param_name}', {value}),")
        
        return '\n'.join(params)
    
    def _generate_indicators(self, indicators: List[Dict]) -> str:
        """İndikatör tanımlamalarını üret."""
        lines = []
        
        for ind in indicators:
            ind_name = ind.get('name', '').lower()
            ind_params = ind.get('params', {})
            
            if ind_name in INDICATOR_MAP:
                bt_class, param_names = INDICATOR_MAP[ind_name]
                
                # Parametre string'i oluştur
                param_strs = []
                for param in param_names.split(','):
                    param = param.strip()
                    if param in ind_params:
                        param_strs.append(f"{param}={ind_params[param]}")
                    elif param == 'period' and 'period' in ind_params:
                        param_strs.append(f"period=self.p.{ind_name}_period")
                
                param_str = ', '.join(param_strs) if param_strs else ''
                
                lines.append(f"        self.{ind_name} = {bt_class}(self.data.close{', ' + param_str if param_str else ''})")
            else:
                # Bilinmeyen indikatör - basit SMA fallback
                period = ind_params.get('period', 14)
                lines.append(f"        # Unknown indicator: {ind_name}")
                lines.append(f"        self.{ind_name} = bt.indicators.SMA(self.data.close, period={period})")
        
        if not lines:
            lines.append("        # No indicators defined")
            lines.append("        self.sma = bt.indicators.SMA(self.data.close, period=20)")
        
        return '\n'.join(lines)
    
    def _generate_signal_logic(
        self, 
        entry_rules: str, 
        exit_rules: str, 
        indicators: List[Dict]
    ) -> str:
        """Entry/exit signal logic üret."""
        lines = []
        
        # Entry signal
        entry_code = self._parse_rules_to_code(entry_rules, indicators)
        lines.append(f"            # Entry condition: {entry_rules}")
        lines.append(f"            self.entry_signal = {entry_code}")
        lines.append("")
        
        # Exit signal
        exit_code = self._parse_rules_to_code(exit_rules, indicators)
        lines.append(f"            # Exit condition: {exit_rules}")
        lines.append(f"            self.exit_signal = {exit_code}")
        
        return '\n'.join(lines)
    
    def _parse_rules_to_code(self, rules: str, indicators: List[Dict]) -> str:
        """Kural string'ini Python koduna çevir."""
        if not rules:
            return "False"
        
        code = rules.lower()
        
        # İndikatör referanslarını düzelt
        for ind in indicators:
            ind_name = ind.get('name', '').lower()
            
            # RSI < 30 -> self.rsi[0] < 30
            code = re.sub(
                rf'\b{ind_name}\s*([<>=!]+)\s*(\d+)',
                rf'self.{ind_name}[0] \1 \2',
                code
            )
            
            # RSI crosses above -> crossover logic
            code = re.sub(
                rf'{ind_name}\s+crosses?\s+above',
                f'self.{ind_name}[0] > self.{ind_name}[-1] and self.{ind_name}[-1] <= ',
                code
            )
            code = re.sub(
                rf'{ind_name}\s+crosses?\s+below',
                f'self.{ind_name}[0] < self.{ind_name}[-1] and self.{ind_name}[-1] >= ',
                code
            )
        
        # Boolean operatörleri
        code = code.replace(' and ', ' and ')
        code = code.replace(' or ', ' or ')
        
        # Price references
        code = re.sub(r'\bprice\b', 'self.data.close[0]', code)
        code = re.sub(r'\bclose\b', 'self.data.close[0]', code)
        code = re.sub(r'\bhigh\b', 'self.data.high[0]', code)
        code = re.sub(r'\blow\b', 'self.data.low[0]', code)
        
        # SMA crossovers
        code = re.sub(
            r'sma\s*\((\d+)\)\s*>\s*sma\s*\((\d+)\)',
            r'self.sma_fast[0] > self.sma_slow[0]',
            code
        )
        
        # Validate - temel kontrol
        if not any(c in code for c in ['self.', 'True', 'False']):
            code = "True  # Manual entry required: " + rules[:50]
        
        return code
    
    def validate_code(self, code: str) -> bool:
        """Üretilen kodun syntax olarak geçerli olup olmadığını kontrol et."""
        try:
            compile(code, '<string>', 'exec')
            return True
        except SyntaxError as e:
            logger.warning(f"Syntax error in generated code: {e}")
            return False
    
    def generate_with_validation(self, strategy_data: Dict, source_url: str = "") -> Dict:
        """
        Kod üret ve validate et.
        
        Returns:
            {'code': str, 'valid': bool, 'error': str or None}
        """
        try:
            code = self.generate(strategy_data, source_url)
            valid = self.validate_code(code)
            
            return {
                'code': code,
                'valid': valid,
                'error': None if valid else "Syntax error",
            }
        except Exception as e:
            return {
                'code': '',
                'valid': False,
                'error': str(e),
            }


def get_test_config() -> Dict:
    """Jenerik test konfigürasyonu."""
    return TEST_CONFIG


# Demo
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test verisi
    test_strategy = {
        'strategy_name': 'RSI Mean Reversion',
        'summary': 'RSI 30 altına düştüğünde al, 70 üstüne çıktığında sat.',
        'entry_rules': 'RSI < 30 AND price > SMA(20)',
        'exit_rules': 'RSI > 70 OR price < SMA(20)',
        'indicators': [
            {'name': 'rsi', 'params': {'period': 14}},
            {'name': 'sma', 'params': {'period': 20}},
        ],
        'tp_pct': 3.0,
        'sl_pct': 1.5,
        'ai_notes': 'Mean reversion stratejisi, range piyasalarda iyi çalışır.',
    }
    
    generator = StrategyCodeGenerator()
    result = generator.generate_with_validation(test_strategy, "https://reddit.com/test")
    
    print("Generated Code:")
    print("=" * 60)
    print(result['code'][:2000])
    print(f"\nValid: {result['valid']}")
