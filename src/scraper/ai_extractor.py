# -*- coding: utf-8 -*-
"""
Enhanced Two-Stage AI Extractor with Smart Filtering

Daha akıllı filtreleme:
- Gerçek strateji mi yoksa sadece pozisyon paylaşımı mı?
- Backtest sonucu var mı?
- Entry/exit kuralları tanımlı mı?
- Metodoloji açıklanmış mı?

Puanlama kriterleri:
- Backtest results: +25
- Entry/exit rules: +25
- Indicators defined: +15
- Methodology explained: +15
- Risk management: +10
- Reproducible: +10
"""

import json
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
import yaml
from pathlib import Path
from math import sqrt

logger = logging.getLogger(__name__)

# ===== Calibration knobs (v2) =====
PREFILTER_LOW_THRESHOLD = 35
PREFILTER_HIGH_THRESHOLD = 65
RULE_QUALITY_STRONG_MIN_SCORE = 70
RULE_QUALITY_MEDIUM_MIN_SCORE = 45

# OpenAI lazy import
OPENAI_AVAILABLE = None

def _check_openai():
    global OPENAI_AVAILABLE
    if OPENAI_AVAILABLE is None:
        try:
            from openai import OpenAI
            OPENAI_AVAILABLE = True
        except ImportError:
            OPENAI_AVAILABLE = False
    return OPENAI_AVAILABLE


class PostCategory(Enum):
    ACTIONABLE_STRATEGY = "ACTIONABLE_STRATEGY"  # Kodlanabilir, test edilebilir
    METHODOLOGY = "METHODOLOGY"  # Metodoloji/yaklaşım, ama tam kural yok
    INSIGHT = "INSIGHT"  # Değerli analiz/bilgi
    POSITION_SHARE = "POSITION_SHARE"  # Sadece pozisyon paylaşımı
    NOISE = "NOISE"  # Gürültü
    SKIP = "SKIP"  # Regex pre-filter tarafından elenmiş


# ========== REGEX PRE-FILTER (Zero-cost noise reduction) ==========
import re

# Keywords that indicate valuable content
VALUABLE_KEYWORDS = re.compile(
    r'\b(entry|exit|backtest|sharpe|drawdown|win.?rate|strategy|indicator|'
    r'sma|ema|rsi|macd|bollinger|atr|adx|cci|stochastic|ichimoku|fibonacci|'
    r'pivot|vwap|obv|momentum|breakout|reversal|mean.?reversion|trend|'
    r'tp|sl|take.?profit|stop.?loss|risk.?reward|position.?size|leverage|'
    r'python|pine|backtrader|code|algorithm|automated|quantitative|'
    r'buy.?signal|sell.?signal|long|short|trade.?setup)\b',
    re.IGNORECASE
)

# Keywords that indicate likely noise
NOISE_KEYWORDS = re.compile(
    r'\b(help|newbie|beginner|question|advice|opinion|recommend|suggest|'
    r'should.?i|what.?do.?you.?think|is.?this.?good|roast|critique|'
    r'congratulations|thanks|thank.?you|appreciate|update.?me)\b',
    re.IGNORECASE
)

# Code snippet patterns
CODE_PATTERNS = re.compile(
    r'(```|def\s+\w+\(|import\s+\w+|class\s+\w+|if\s+.*:|for\s+.*:|'
    r'strategy\s*\(|indicator\s*\(|ta\.\w+|bt\.Strategy|backtrader)',
    re.IGNORECASE
)

# Backtest metrics patterns
BACKTEST_METRICS = re.compile(
    r'(\d+\.?\d*\s*%.*(?:return|profit|win|loss|drawdown|sharpe)|'
    r'sharpe\s*(?:ratio)?\s*:?\s*\d+\.?\d*|'
    r'max\s*(?:draw)?down\s*:?\s*\d+\.?\d*\s*%|'
    r'win\s*rate\s*:?\s*\d+\.?\d*\s*%|'
    r'\d+\s*trades?\s*over\s*\d+)',
    re.IGNORECASE
)

# Explicit rule patterns (evidence extraction)
ENTRY_RULE_PATTERNS = re.compile(
    r'\b(entry|buy\s+when|long\s+when|go\s+long|open\s+long|trigger)\b',
    re.IGNORECASE
)

EXIT_RULE_PATTERNS = re.compile(
    r'\b(exit|sell\s+when|close\s+position|go\s+flat|take\s+profit|stop\s+loss|tp|sl)\b',
    re.IGNORECASE
)

RISK_RULE_PATTERNS = re.compile(
    r'\b(risk|position\s*size|risk.?reward|rr\b|stop.?loss|take.?profit|tp|sl|leverage)\b',
    re.IGNORECASE
)

STRUCTURE_PATTERNS = re.compile(
    r'(\bif\b.*\bthen\b|\bwhen\b.*\bthen\b|:|;|\n|\d+\)|- )',
    re.IGNORECASE
)


def _rule_quality_level(
    has_entry_rule: bool,
    has_exit_rule: bool,
    has_backtest: bool,
    has_risk_rule: bool,
    has_code: bool,
    quality_score: int
) -> str:
    evidence_count = sum([has_entry_rule, has_exit_rule, has_backtest, has_risk_rule, has_code])
    if evidence_count >= 4 and has_entry_rule and has_exit_rule and quality_score >= RULE_QUALITY_STRONG_MIN_SCORE:
        return "strong"
    if evidence_count >= 3 and (has_entry_rule or has_exit_rule) and quality_score >= RULE_QUALITY_MEDIUM_MIN_SCORE:
        return "medium"
    return "weak"


def _subreddit_weight(subreddit: str) -> float:
    s = (subreddit or "").lower()
    # More technical subs => community signal is more meaningful
    if s in {"algotrading", "quant", "quantfinance", "backtrader"}:
        return 1.1
    # More general subs => reduce upvote impact
    if s in {"stocks", "investing", "cryptocurrency", "wallstreetbets"}:
        return 0.65
    return 0.8


def _upvote_bonus(upvotes: int, subreddit: str) -> int:
    if upvotes >= 500:
        base = 9
    elif upvotes >= 100:
        base = 7
    elif upvotes >= 50:
        base = 5
    elif upvotes >= 20:
        base = 3
    else:
        base = 0
    return int(round(base * _subreddit_weight(subreddit)))


def _asset_weight_from_text(text: str) -> float:
    t = (text or "").lower()
    if any(k in t for k in ["btc", "eth", "crypto", "binance", "altcoin"]):
        return 0.8
    if any(k in t for k in ["eurusd", "gbpusd", "forex", "fx"]):
        return 0.9
    if any(k in t for k in ["aapl", "msft", "spy", "nasdaq", "stocks"]):
        return 1.0
    return 0.9


def pre_filter_post(title: str, content: str) -> dict:
    """
    Zero-cost regex pre-filter to skip obvious noise.
    
    Returns:
        {
            'should_process': bool,  # True = send to AI, False = skip
            'skip_reason': str or None,
            'priority_score': int,  # 0-100, higher = more valuable
            'has_code': bool,
            'has_backtest': bool,
            'has_entry_rule': bool,
            'has_exit_rule': bool,
            'has_risk_rule': bool,
            'rule_quality': str
        }
    """
    text = f"{title} {content}".lower()
    original_text = f"{title} {content}"  # Keep original for case-sensitive checks
    
    result = {
        'should_process': True,
        'skip_reason': None,
        'priority_score': 50,  # Base score (legacy compatibility)
        'final_priority_score': 50,  # New weighted score
        'prefilter_band': 'medium',
        'has_code': False,
        'has_backtest': False,
        'has_entry_rule': False,
        'has_exit_rule': False,
        'has_risk_rule': False,
        'valuable_matches': 0,
        'noise_matches': 0,
        'evidence_score': 0,
        'structure_score': 0,
        'regex_score': 50,
        'rule_quality': 'weak',
    }
    
    # ===== SPAM BLACKLIST (exact match, case-sensitive) =====
    # Known promotional/premium service spam patterns
    SPAM_BLACKLIST = [
        "QuantSignals",  # Premium signal service spam in ai_trading
    ]
    
    for spam_term in SPAM_BLACKLIST:
        if spam_term in original_text:
            result['should_process'] = False
            result['skip_reason'] = f'spam_blacklist:{spam_term}'
            result['priority_score'] = 0
            result['final_priority_score'] = 0
            result['prefilter_band'] = 'skip'
            logger.debug(f"Spam blacklist match: {spam_term}")
            return result
    
    # Check for code snippets (major priority boost)
    if CODE_PATTERNS.search(content):
        result['has_code'] = True
        result['priority_score'] += 30
        logger.debug(f"Code detected, priority boosted")
    
    # Check for backtest metrics (major priority boost)
    if BACKTEST_METRICS.search(text):
        result['has_backtest'] = True
        result['priority_score'] += 25
        logger.debug(f"Backtest metrics detected, priority boosted")

    # Explicit rule/risk evidence
    result['has_entry_rule'] = bool(ENTRY_RULE_PATTERNS.search(text))
    result['has_exit_rule'] = bool(EXIT_RULE_PATTERNS.search(text))
    result['has_risk_rule'] = bool(RISK_RULE_PATTERNS.search(text))
    if result['has_entry_rule']:
        result['priority_score'] += 10
    if result['has_exit_rule']:
        result['priority_score'] += 10
    if result['has_risk_rule']:
        result['priority_score'] += 8
    
    # Count valuable keywords
    valuable_matches = len(VALUABLE_KEYWORDS.findall(text))
    result['valuable_matches'] = valuable_matches
    if valuable_matches >= 3:
        result['priority_score'] += min(valuable_matches * 3, 20)
    
    # Check for noise indicators
    noise_matches = len(NOISE_KEYWORDS.findall(text))
    result['noise_matches'] = noise_matches
    
    # Decision logic
    if len(content) < 100:  # Too short
        result['should_process'] = False
        result['skip_reason'] = 'too_short'
        result['priority_score'] = 0
        result['final_priority_score'] = 0
        result['prefilter_band'] = 'skip'
    elif valuable_matches == 0 and noise_matches > 2:
        result['should_process'] = False
        result['skip_reason'] = 'likely_noise'
        result['priority_score'] = 0
        result['final_priority_score'] = 0
        result['prefilter_band'] = 'skip'
    elif noise_matches > valuable_matches * 2 and valuable_matches < 2:
        result['should_process'] = False
        result['skip_reason'] = 'noise_ratio_high'
        result['priority_score'] = 0
        result['final_priority_score'] = 0
        result['prefilter_band'] = 'skip'
    
    # Cap priority score
    result['priority_score'] = min(100, max(0, result['priority_score']))

    # New weighted priority model (keep legacy priority_score for compatibility)
    regex_score = result['priority_score']
    evidence_count = sum([
        result['has_code'],
        result['has_backtest'],
        result['has_entry_rule'],
        result['has_exit_rule'],
        result['has_risk_rule'],
    ])
    # non-linear lift to reward multi-signal evidence
    evidence_score = min(100, int(round((evidence_count / 5) * 100 + sqrt(evidence_count) * 10)))
    structure_hits = len(STRUCTURE_PATTERNS.findall(content))
    structure_score = min(100, structure_hits * 12)

    final_priority = int(round(regex_score * 0.45 + evidence_score * 0.35 + structure_score * 0.20))
    final_priority = max(0, min(100, final_priority))

    if final_priority < PREFILTER_LOW_THRESHOLD:
        result['prefilter_band'] = 'low'
        if result['should_process']:
            result['should_process'] = False
            result['skip_reason'] = result['skip_reason'] or 'low_priority'
    elif final_priority < PREFILTER_HIGH_THRESHOLD:
        result['prefilter_band'] = 'medium'
    else:
        result['prefilter_band'] = 'high'

    result['regex_score'] = regex_score
    result['evidence_score'] = evidence_score
    result['structure_score'] = structure_score
    result['final_priority_score'] = final_priority
    result['rule_quality'] = _rule_quality_level(
        has_entry_rule=result['has_entry_rule'],
        has_exit_rule=result['has_exit_rule'],
        has_backtest=result['has_backtest'],
        has_risk_rule=result['has_risk_rule'],
        has_code=result['has_code'],
        quality_score=final_priority
    )
    
    return result


class SmartExtractor:
    """Akıllı 2 aşamalı strateji çıkarıcı."""
    
    MODEL = "gpt-4o-mini"
    
    # Stage 1: Akıllı sınıflandırma (detaylı kriterler ile)
    STAGE1_SMART_PROMPT = """You are a trading strategy analyst. Analyze this Reddit post and classify it.

TITLE: {title}
CONTENT: {content}

=== HIGH VALUE SIGNALS (prioritize these) ===
- Backtest results with METRICS (return %, Sharpe, drawdown, win rate)
- Python/Pine code snippet or mentions "code available"
- Specific entry/exit rules with indicator parameters
- Session time rules (NY session, London, Asia)
- Risk management with TP/SL percentages
- Sample trade count (e.g., "435 trades over 2 years")
- Machine learning, statistical models, or advanced techniques
- Multiple confirmation signals (not just one indicator)

=== LOW VALUE / REJECT SIGNALS ===
- ONLY SMA/EMA crossover (e.g., SMA50/SMA200 golden cross alone)
- ONLY RSI overbought/oversold (e.g., just "buy when RSI < 30")
- ONLY MACD crossover without other filters
- Single indicator strategies without any edge
- No backtest, no risk management, no originality
- These are OUTDATED, OVERUSED patterns with no real edge

=== CLASSIFICATION CRITERIA ===

1. ACTIONABLE_STRATEGY - Must have ALL of these:
   - Specific entry condition with MULTIPLE factors (not just one indicator)
   - Specific exit condition
   - At least one ADVANCED or COMBINED indicator setup
   - Reproducible logic that can be coded
   - BONUS: Has backtest metrics or code
   - NOTE: Simple SMA crossover or RSI alone = NOISE, not strategy

2. METHODOLOGY - Has these but lacks complete rules:
   - Explains a trading approach or system
   - Has backtested results or performance data
   - Describes indicators or analysis method
   - Missing some entry/exit specifics

3. INSIGHT - Valuable but not tradeable:
   - Market analysis or prediction
   - Educational content about trading

4. POSITION_SHARE - Just showing a trade:
   - "I bought X at Y price", no rules

5. NOISE - Low value OR basic strategies:
   - Memes, jokes, simple questions
   - BASIC SMA crossover, RSI threshold alone
   - Single indicator "strategies" without edge

RESPOND WITH ONLY ONE: ACTIONABLE_STRATEGY, METHODOLOGY, INSIGHT, POSITION_SHARE, or NOISE"""

    # Stage 2: Detaylı strateji çıkarma (puanlama ile)
    STAGE2_STRATEGY_PROMPT = """Extract trading strategy details and score its quality.

TITLE: {title}
CONTENT: {content}

=== SCORING CRITERIA (0-100 total) ===
POSITIVE POINTS:
- Backtest results present: +25 points
- Clear entry rules with MULTIPLE factors: +20 points
- Clear exit rules: +15 points
- Advanced/combined indicators: +15 points
- Risk management (TP/SL): +10 points
- Reproducible/codeable: +10 points
- Author experience/credibility: +5 points

NEGATIVE POINTS (VERY IMPORTANT):
- ONLY SMA/EMA crossover (no other factors): -40 points
- ONLY RSI overbought/oversold (no other factors): -40 points  
- ONLY MACD crossover (no other factors): -30 points
- Single indicator without confirmation: -25 points
- No backtest and no risk management: -20 points
- Common/overused pattern without edge: -15 points

These basic patterns are OUTDATED and have NO EDGE in modern markets.
A "SMA50/SMA200 crossover" alone should score 15-25 maximum.
A "RSI < 30 buy, RSI > 70 sell" alone should score 15-25 maximum.

Return JSON:
{{
    "strategy_name": "descriptive name",
    "category": "ACTIONABLE_STRATEGY or METHODOLOGY",
    
    "summary_tr": "2-3 cümle Türkçe özet",
    
    "entry_rules": "EXACT entry condition",
    "exit_rules": "EXACT exit condition",
    
    "indicators": [
        {{"name": "indicator_name", "params": {{"period": 14}}, "usage": "how it's used"}}
    ],
    
    "tp_pct": 3.0,
    "sl_pct": 1.5,
    "risk_reward": 2.0,
    
    "timeframe": "recommended timeframe",
    "markets": ["suitable markets"],
    
    "backtest_results": {{
        "has_backtest": true/false,
        "win_rate": null or percentage,
        "profit_factor": null or number,
        "sample_size": null or number,
        "period": null or "description"
    }},
    
    "sophistication_level": "BASIC/INTERMEDIATE/ADVANCED",
    "is_basic_pattern": true/false,
    
    "quality_score": 0-100,
    "score_breakdown": {{
        "backtest_present": 0-25,
        "entry_rules_clear": 0-20,
        "exit_rules_clear": 0-15,
        "indicators_defined": 0-15,
        "risk_management": 0-10,
        "reproducible": 0-10,
        "credibility": 0-5,
        "basic_pattern_penalty": 0 to -40
    }},
    
    "ai_notes_tr": "Türkçe notlar - basit pattern ise bunu belirt",
    
    "is_codeable": true/false,
    "missing_info": ["list of missing info"]
}}

Be VERY STRICT. Basic SMA crossover or RSI alone should score < 30.
Return ONLY valid JSON."""

    # Stage 2: Insight çıkarma (link ve detay ile)
    STAGE2_INSIGHT_PROMPT = """Extract valuable insights from this financial post.

TITLE: {title}
CONTENT: {content}
URL: {url}

Return JSON:
{{
    "title": "concise insight title",
    "summary_tr": "2-3 cümle Türkçe özet",
    "category": "METHODOLOGY or INSIGHT",
    
    "key_points": [
        "key point 1",
        "key point 2"
    ],
    
    "sentiment": "bullish/bearish/neutral",
    "confidence": "high/medium/low",
    
    "relevant_assets": ["BTC", "SPY"],
    "relevant_timeframe": "short-term/medium-term/long-term",
    
    "actionable_takeaways": [
        "What can trader learn or do based on this"
    ],
    
    "source_url": "{url}",
    "author_credibility": "unknown/low/medium/high"
}}

Return ONLY valid JSON."""

    def __init__(self, api_key: str = None, config_path: str = None):
        if not _check_openai():
            raise ImportError("OpenAI package required. Run: pip install openai")
        
        from openai import OpenAI
        
        if api_key is None:
            api_key = self._load_api_key(config_path)
        
        self.client = OpenAI(api_key=api_key)
        self._token_stats = {
            'stage1': {'input': 0, 'output': 0, 'cost': 0.0, 'calls': 0},
            'stage2': {'input': 0, 'output': 0, 'cost': 0.0, 'calls': 0},
        }
    
    def _load_api_key(self, config_path: str = None) -> str:
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "secrets.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        api_key = (
            config.get('openai_api_key') or
            config.get('openai', {}).get('api_key') or
            config.get('OPENAI_API_KEY') or
            config.get('api_keys', {}).get('openai')
        )
        
        if not api_key:
            raise ValueError("OpenAI API key not found in secrets.yaml")
        
        return api_key
    
    def _call_gpt(self, prompt: str, stage: str, max_tokens: int = 500) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,  # Daha tutarlı sonuçlar için düşük
            )
            
            usage = response.usage
            if usage:
                self._track_tokens(stage, usage.prompt_tokens, usage.completion_tokens)
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"GPT API error: {e}")
            raise
    
    def _track_tokens(self, stage: str, input_tokens: int, output_tokens: int):
        stats = self._token_stats[stage]
        stats['input'] += input_tokens
        stats['output'] += output_tokens
        stats['calls'] += 1
        cost = (input_tokens / 1_000_000 * 0.15) + (output_tokens / 1_000_000 * 0.60)
        stats['cost'] += cost
        
        # Veritabanına da kaydet
        try:
            from src.scraper.strategy_storage import StrategyStorage
            storage = StrategyStorage()
            storage.log_api_usage(stage, input_tokens, output_tokens, cost)
        except Exception as e:
            logger.debug(f"API usage log error: {e}")
    
    # ========== STAGE 1 ==========
    
    def stage1_classify(self, post: Dict) -> str:
        """Stage 1: Akıllı sınıflandırma."""
        title = post.get('title', '')
        content = post.get('selftext', '') or post.get('content', '')
        content = content[:2000]  # Truncate
        
        prompt = self.STAGE1_SMART_PROMPT.format(title=title, content=content)
        result = self._call_gpt(prompt, stage='stage1', max_tokens=30)
        
        result = result.upper().strip()
        
        # Map to category
        if "ACTIONABLE" in result:
            return "ACTIONABLE_STRATEGY"
        elif "METHODOLOGY" in result:
            return "METHODOLOGY"
        elif "INSIGHT" in result:
            return "INSIGHT"
        elif "POSITION" in result:
            return "POSITION_SHARE"
        else:
            return "NOISE"
    
    # ========== STAGE 2 ==========
    
    def stage2_extract_strategy(self, post: Dict) -> Optional[Dict]:
        """Stage 2: Detaylı strateji çıkarma - Tier sistemi ile."""
        title = post.get('title', '')
        content = post.get('selftext', '') or post.get('content', '')
        content = content[:4000]
        
        prompt = self.STAGE2_STRATEGY_PROMPT.format(title=title, content=content)
        result = self._call_gpt(prompt, stage='stage2', max_tokens=1500)
        
        try:
            result = self._clean_json(result)
            data = json.loads(result)
            
            # Tier sistemine göre değerlendir (reject etme, sadece işaretle)
            score = data.get('quality_score', 0)
            if score >= 60:
                data['quality_tier'] = 'HIGH'
            elif score >= 40:
                data['quality_tier'] = 'MEDIUM'
            elif score >= 20:
                data['quality_tier'] = 'LOW'
            else:
                data['quality_tier'] = 'VERY_LOW'
                logger.info(f"Low quality strategy (score={score}), marked as VERY_LOW tier")
            
            return data
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Strategy extraction failed: {e}")
            return None
    
    def stage2_extract_insight(self, post: Dict) -> Optional[Dict]:
        """Stage 2: Insight çıkarma."""
        title = post.get('title', '')
        content = post.get('selftext', '') or post.get('content', '')
        url = post.get('url', '')
        content = content[:2500]
        
        prompt = self.STAGE2_INSIGHT_PROMPT.format(title=title, content=content, url=url)
        result = self._call_gpt(prompt, stage='stage2', max_tokens=600)
        
        try:
            result = self._clean_json(result)
            data = json.loads(result)
            data['source_url'] = url
            return data
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Insight extraction failed: {e}")
            return None
    
    def _clean_json(self, text: str) -> str:
        """JSON response'u temizle."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        if text.startswith("json"):
            text = text[4:]
        return text.strip()
    
    # ========== FULL PIPELINE ==========
    
    def process_post(self, post: Dict, use_prefilter: bool = True, skip_if_analyzed: bool = True) -> Dict:
        """
        Tam pipeline: Pre-filter + Stage 1 + Stage 2.
        
        Args:
            post: Reddit post dict
            use_prefilter: If True, skip obvious noise without AI call
            skip_if_analyzed: If True, skip posts that have already been analyzed (prevents duplicate AI calls)
        """
        from .strategy_storage import StrategyStorage
        storage = StrategyStorage()
        hash_id = StrategyStorage.generate_hash(post.get('url', ''))
        
        title = post.get('title', '')
        content = post.get('selftext', '') or post.get('content', '')
        
        result = {
            'hash_id': hash_id,
            'category': None,
            'strategy': None,
            'insight': None,
            'skipped_reason': None,
            'priority_score': 50,
            'final_priority_score': 50,
            'prefilter_band': 'medium',
            'has_code': False,
            'has_backtest': False,
            'has_entry_rule': False,
            'has_exit_rule': False,
            'has_risk_rule': False,
            'rule_quality': 'weak',
            'prefilter_skipped': False,
            'already_analyzed': False,
        }
        
        # ===== DUPLICATE ANALYSIS CHECK (zero cost) =====
        if skip_if_analyzed and storage.is_already_analyzed(hash_id):
            result['category'] = 'ALREADY_ANALYZED'
            result['skipped_reason'] = 'already_analyzed'
            result['already_analyzed'] = True
            logger.debug(f"Post already analyzed, skipping: {hash_id}")
            return result
        
        # ===== PRE-FILTER (zero cost) =====
        if use_prefilter:
            pf = pre_filter_post(title, content)
            result['priority_score'] = pf['priority_score']
            result['final_priority_score'] = pf.get('final_priority_score', pf['priority_score'])
            result['prefilter_band'] = pf.get('prefilter_band', 'medium')
            result['has_code'] = pf['has_code']
            result['has_backtest'] = pf['has_backtest']
            result['has_entry_rule'] = pf.get('has_entry_rule', False)
            result['has_exit_rule'] = pf.get('has_exit_rule', False)
            result['has_risk_rule'] = pf.get('has_risk_rule', False)
            result['rule_quality'] = pf.get('rule_quality', 'weak')
            
            if not pf['should_process']:
                result['category'] = 'SKIP'
                result['skipped_reason'] = pf['skip_reason']
                result['prefilter_skipped'] = True
                logger.debug(f"Pre-filter skipped: {pf['skip_reason']}")
                return result
        
        # ===== STAGE 1: AI Classify =====
        category = self.stage1_classify(post)
        result['category'] = category
        
        # ===== STAGE 2: Extract details =====
        if category == "ACTIONABLE_STRATEGY":
            strategy = self.stage2_extract_strategy(post)
            if strategy:
                # Boost score if pre-filter detected code/backtest
                if result['has_code']:
                    strategy['quality_score'] = min(100, strategy.get('quality_score', 50) + 10)
                if result['has_backtest']:
                    strategy['quality_score'] = min(100, strategy.get('quality_score', 50) + 10)
                
                # ===== UPVOTE BONUS =====
                # High upvotes = community validated = higher quality signal
                upvotes = post.get('score', 0) or 0
                subreddit = post.get('subreddit', '')
                asset_w = _asset_weight_from_text(f"{title} {content}")
                bonus = int(round(_upvote_bonus(int(upvotes), str(subreddit)) * asset_w))
                if bonus > 0:
                    strategy['quality_score'] = min(100, strategy.get('quality_score', 50) + bonus)
                    logger.debug(f"Upvote bonus +{bonus} ({upvotes} upvotes, subreddit={subreddit})")

                strategy['rule_quality'] = _rule_quality_level(
                    has_entry_rule=bool(strategy.get('entry_rules')),
                    has_exit_rule=bool(strategy.get('exit_rules')),
                    has_backtest=result['has_backtest'],
                    has_risk_rule=result['has_risk_rule'],
                    has_code=result['has_code'],
                    quality_score=int(strategy.get('quality_score', 0))
                )
                
                result['strategy'] = strategy
            else:
                result['skipped_reason'] = "quality_score_too_low"
                
        elif category == "METHODOLOGY":
            strategy = self.stage2_extract_strategy(post)
            if strategy:
                strategy['category'] = 'METHODOLOGY'
                
                # ===== UPVOTE BONUS FOR METHODOLOGY =====
                upvotes = post.get('score', 0) or 0
                subreddit = post.get('subreddit', '')
                asset_w = _asset_weight_from_text(f"{title} {content}")
                bonus = int(round(_upvote_bonus(int(upvotes), str(subreddit)) * asset_w))
                if bonus > 0:
                    strategy['quality_score'] = min(100, strategy.get('quality_score', 50) + bonus)

                strategy['rule_quality'] = _rule_quality_level(
                    has_entry_rule=bool(strategy.get('entry_rules')),
                    has_exit_rule=bool(strategy.get('exit_rules')),
                    has_backtest=result['has_backtest'],
                    has_risk_rule=result['has_risk_rule'],
                    has_code=result['has_code'],
                    quality_score=int(strategy.get('quality_score', 0))
                )
                
                result['strategy'] = strategy
                
        elif category == "INSIGHT":
            insight = self.stage2_extract_insight(post)
            if insight:
                result['insight'] = insight
                
        elif category == "POSITION_SHARE":
            result['skipped_reason'] = "position_share_only"
            
        else:  # NOISE
            result['skipped_reason'] = "noise"
        
        return result
    
    def get_token_stats(self) -> Dict:
        s1 = self._token_stats['stage1']
        s2 = self._token_stats['stage2']
        
        return {
            'stage1': s1.copy(),
            'stage2': s2.copy(),
            'total_tokens': s1['input'] + s1['output'] + s2['input'] + s2['output'],
            'total_cost': s1['cost'] + s2['cost'],
            'total_calls': s1['calls'] + s2['calls'],
        }
    
    def reset_token_stats(self):
        self._token_stats = {
            'stage1': {'input': 0, 'output': 0, 'cost': 0.0, 'calls': 0},
            'stage2': {'input': 0, 'output': 0, 'cost': 0.0, 'calls': 0},
        }


# Backward compatibility
TwoStageExtractor = SmartExtractor
AIExtractor = SmartExtractor


# Demo
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Smart Extractor ready")
    print("Categories: ACTIONABLE_STRATEGY, METHODOLOGY, INSIGHT, POSITION_SHARE, NOISE")
