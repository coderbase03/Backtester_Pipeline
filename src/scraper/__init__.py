# -*- coding: utf-8 -*-
"""
Reddit Strategy Scraper Module

Components:
- RedditCollector: Reddit'ten post toplama
- TwoStageExtractor: 2 aşamalı AI strateji çıkarma
- StrategyStorage: Veritabanı yönetimi
- StrategyCodeGenerator: Python kod üretimi
"""

from .reddit_collector import RedditCollector

# Lazy imports for optional dependencies
def get_ai_extractor():
    """Get TwoStageExtractor class (requires openai)."""
    from .ai_extractor import TwoStageExtractor
    return TwoStageExtractor

def get_storage():
    """Get StrategyStorage class."""
    from .strategy_storage import StrategyStorage
    return StrategyStorage

def get_code_generator():
    """Get StrategyCodeGenerator class."""
    from .code_generator import StrategyCodeGenerator
    return StrategyCodeGenerator

__all__ = [
    'RedditCollector',
    'get_ai_extractor',
    'get_storage',
    'get_code_generator',
]
