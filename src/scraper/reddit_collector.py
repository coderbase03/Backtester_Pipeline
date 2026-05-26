# -*- coding: utf-8 -*-
"""
Reddit Collector Module - Enhanced

Reddit'ten alım-satım stratejileri içeren postları toplar.
- Config dosyası ile dinamik subreddit yönetimi
- Genişletilmiş keyword listesi
- Esnek filtreleme (subreddit kalitesine göre)

Usage:
    from src.scraper import RedditCollector
    
    collector = RedditCollector()
    posts = collector.collect_posts()  # Config'den subredditleri yükler
    
    # Manuel subreddit
    posts = collector.collect_posts(['algotrading', 'quantfinance'])
"""

import requests
import time
import json
import re
import yaml
from typing import List, Dict, Optional, Set, Any
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RedditCollector:
    """Reddit'ten trading stratejisi postlarını toplar - Enhanced."""
    
    # Default subreddits (config yoksa kullanılır)
    DEFAULT_SUBREDDITS = [
        'algotrading',
        'quantfinance',
        'ai_trading',  # AI ve ML stratejileri
        'FuturesTrading',
        'Trading',
        'Daytrading',
        'RealDayTrading',
        'options',
        'thetagang',
        'stocks',
        'SecurityAnalysis',
        'forex',
        'CryptoCurrency',
    ]
    
    # ===== GENİŞLETİLMİŞ KEYWORD LİSTESİ =====
    STRATEGY_KEYWORDS = [
        # Core trading terms
        'strategy', 'backtest', 'indicator', 'signal', 'system',
        'buy', 'sell', 'entry', 'exit', 'long', 'short',
        'profit', 'loss', 'stop loss', 'take profit', 'tp', 'sl',
        'win rate', 'sharpe', 'drawdown', 'return', 'pnl',
        
        # Technical indicators
        'rsi', 'sma', 'ema', 'macd', 'bollinger', 'supertrend',
        'moving average', 'crossover', 'divergence', 'convergence',
        'atr', 'fibonacci', 'support', 'resistance',
        'ichimoku', 'vwap', 'poc', 'value area', 'tpo',
        'stochastic', 'cci', 'adx', 'obv', 'mfi', 'roc',
        'keltner', 'donchian', 'parabolic sar', 'pivot',
        
        # Smart Money / Order Flow
        'smart money', 'order flow', 'volume profile', 'footprint',
        'market structure', 'liquidity', 'fair value gap', 'fvg',
        'imbalance', 'order block', 'breaker block', 'mitigation',
        'inducement', 'sweep', 'grab', 'manipulation',
        'wyckoff', 'accumulation', 'distribution',
        
        # Price Action
        'price action', 'candlestick', 'pattern', 'formation',
        'breakout', 'breakdown', 'pullback', 'retracement',
        'trend', 'range', 'consolidation', 'reversal',
        'higher high', 'lower low', 'double top', 'double bottom',
        'head and shoulders', 'triangle', 'wedge', 'flag',
        
        # Quant / Algo
        'algorithm', 'systematic', 'quantitative', 'quant',
        'machine learning', 'neural network', 'ml', 'ai',
        'regression', 'optimization', 'parameter',
        'monte carlo', 'walk forward', 'out of sample',
        'overfitting', 'curve fitting', 'robustness',
        
        # Risk Management
        'position size', 'kelly criterion', 'risk reward', 'rr',
        'expectancy', 'var', 'cvar', 'max drawdown',
        'risk management', 'money management', 'portfolio',
        
        # Trading styles
        'momentum', 'mean reversion', 'scalp', 'scalping',
        'swing', 'intraday', 'day trade', 'position trade',
        'trend following', 'counter trend', 'range trading',
        
        # Platforms/Code
        'python', 'backtrader', 'pine script', 'tradingview',
        'metatrader', 'mt4', 'mt5', 'ninjatrader', 'amibroker',
        'quantconnect', 'zipline', 'freqtrade',
        
        # Markets
        'futures', 'options', 'forex', 'crypto', 'stocks',
        'es', 'nq', 'cl', 'gc', 'btc', 'eth', 'spy', 'qqq',
    ]
    
    def __init__(self, rate_limit_seconds: float = 3.5, config_path: str = None):
        """
        Initialize Reddit collector.
        
        Args:
            rate_limit_seconds: Seconds to wait between requests (default 3.5 to avoid 429 errors)
            config_path: Path to subreddits.yaml config file
        """
        self.rate_limit = rate_limit_seconds
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OpusBacktrader/2.0 (Enhanced Strategy Research Bot)'
        })
        self._seen_ids: Set[str] = set()
        self._last_request_time = 0
        self._stats = {'requests': 0, 'posts_fetched': 0, 'filtered_out': 0}
        
        # Progress tracking for estimated time
        self._start_time = None
        self._total_expected_requests = 0
        self._completed_requests = 0
        
        # Load config
        self.config = self._load_config(config_path)
        self.subreddit_settings = self._build_subreddit_settings()
        
    def _wait_rate_limit(self):
        """Rate limit bekle."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()
    
    def _load_config(self, config_path: str = None) -> Dict:
        """Config dosyasını yükle."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "subreddits.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"Config not found: {config_path}, using defaults")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded subreddit config from {config_path}")
            return config or {}
        except Exception as e:
            logger.error(f"Config load error: {e}")
            return {}
    
    def _build_subreddit_settings(self) -> Dict[str, Dict]:
        """Config'den subreddit ayarlarını oluştur."""
        settings = {}
        
        if not self.config or 'subreddits' not in self.config:
            # Defaults
            for sub in self.DEFAULT_SUBREDDITS:
                settings[sub] = {
                    'priority': 2,
                    'min_score': 5,
                    'min_length': 100,
                    'enabled': True,
                }
            return settings
        
        # Config'den yükle
        for tier, subs in self.config.get('subreddits', {}).items():
            if not isinstance(subs, list):
                continue
            for sub_config in subs:
                if not sub_config.get('enabled', True):
                    continue
                name = sub_config.get('name')
                if name:
                    settings[name] = {
                        'priority': sub_config.get('priority', 2),
                        'min_score': sub_config.get('min_score', 5),
                        'min_length': sub_config.get('min_length', 100),
                        'tags': sub_config.get('tags', []),
                    }
        
        logger.info(f"Built settings for {len(settings)} subreddits")
        return settings
    
    def get_enabled_subreddits(self) -> List[str]:
        """Aktif subredditleri döndür."""
        return list(self.subreddit_settings.keys())
    
    def add_subreddit(self, name: str, priority: int = 2, min_score: int = 5, min_length: int = 100):
        """Runtime'da subreddit ekle."""
        self.subreddit_settings[name] = {
            'priority': priority,
            'min_score': min_score,
            'min_length': min_length,
        }
        logger.info(f"Added subreddit: {name}")
    
    def get_quality_tiers(self) -> Dict[str, int]:
        return self.config.get('quality_tiers', {
            'high': 60,
            'medium': 40,
            'low': 20,
            'rejected': 0,
        })
    
    def _fetch_subreddit_page(
        self, 
        subreddit: str, 
        sort: str = 'hot',
        limit: int = 25,
        time_filter: str = 'week',
        after: str = None
    ) -> tuple:
        """
        Bir subreddit'ten tek sayfa post çek.
        
        Args:
            subreddit: Subreddit adı
            sort: Sıralama (hot, new, top)
            limit: Maximum post sayısı (max 100)
            time_filter: Zaman filtresi (hour, day, week, month, year, all)
            after: Pagination cursor
            
        Returns:
            (posts, next_after) tuple
        """
        self._wait_rate_limit()
        self._stats['requests'] += 1
        self._completed_requests += 1  # Track for progress estimation
        
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        params = {'limit': min(limit, 100)}  # Reddit max 100
        if sort == 'top':
            params['t'] = time_filter
        if after:
            params['after'] = after
            
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for child in data.get('data', {}).get('children', []):
                post_data = child.get('data', {})
                post_id = post_data.get('id', '')
                
                # Skip duplicates
                if post_id in self._seen_ids:
                    continue
                self._seen_ids.add(post_id)
                
                posts.append({
                    'id': post_id,
                    'subreddit': subreddit,
                    'title': post_data.get('title', ''),
                    'selftext': post_data.get('selftext', ''),
                    'url': f"https://reddit.com{post_data.get('permalink', '')}",
                    'score': post_data.get('score', 0),
                    'num_comments': post_data.get('num_comments', 0),
                    'created_utc': post_data.get('created_utc', 0),
                    'author': post_data.get('author', ''),
                    'is_self': post_data.get('is_self', True),
                })
                
            logger.info(f"r/{subreddit}/{sort}: {len(posts)} post toplandı")
            
            # Get next page cursor
            next_after = data.get('data', {}).get('after')
            self._stats['posts_fetched'] += len(posts)
            
            return posts, next_after
            
        except requests.RequestException as e:
            logger.error(f"r/{subreddit} fetch error: {e}")
            return [], None
        except json.JSONDecodeError as e:
            logger.error(f"r/{subreddit} JSON parse error: {e}")
            return [], None
    
    def _has_strategy_keywords(self, post: Dict) -> bool:
        """Post'ta strateji anahtar kelimeleri var mı kontrol et."""
        text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
        return any(keyword in text for keyword in self.STRATEGY_KEYWORDS)
    
    def _filter_quality_posts(self, posts: List[Dict], min_score: int = None, min_length: int = None) -> List[Dict]:
        """
        Esnek kalite filtreleme.
        
        Subreddit bazlı threshold kullanır.
        Yüksek upvote'lu postlar için daha düşük min_length kabul eder.
        
        Args:
            posts: Post listesi
            min_score: Override minimum upvote (None = subreddit config'den)
            min_length: Override minimum karakter (None = subreddit config'den)
            
        Returns:
            Filtrelenmiş postlar
        """
        filtered = []
        for post in posts:
            subreddit = post.get('subreddit', '')
            settings = self.subreddit_settings.get(subreddit, {})
            
            # Subreddit-specific thresholds veya defaults
            sub_min_score = min_score or settings.get('min_score', 5)
            sub_min_length = min_length or settings.get('min_length', 100)
            
            score = post.get('score', 0)
            content = post.get('selftext', '')
            
            # ESNEK RULE 1: Çok yüksek upvote = düşük karakter kabul
            if score >= 50:
                sub_min_length = max(30, sub_min_length // 3)
            elif score >= 25:
                sub_min_length = max(50, sub_min_length // 2)
            
            # ESNEK RULE 2: Kaliteli subreddit = düşük threshold
            if settings.get('priority', 3) == 1:
                sub_min_score = max(1, sub_min_score - 2)
            
            # Filter checks
            if score < sub_min_score:
                self._stats['filtered_out'] += 1
                continue
            
            if len(content) < sub_min_length:
                self._stats['filtered_out'] += 1
                continue
                
            # Strateji anahtar kelimeleri içermeli
            if not self._has_strategy_keywords(post):
                self._stats['filtered_out'] += 1
                continue
                
            filtered.append(post)
            
        return filtered
    
    def collect_posts(
        self,
        subreddits: List[str] = None,
        sort_types: List[str] = None,
        limit_per_sub: int = 25,
        min_score: int = 5,
        apply_keyword_filter: bool = True
    ) -> List[Dict]:
        """
        Birden fazla subreddit'ten post topla.
        
        Args:
            subreddits: Subreddit listesi (None = defaults)
            sort_types: Sıralama tipleri ['hot', 'new', 'top']
            limit_per_sub: Her subreddit için maksimum post
            min_score: Minimum upvote skoru
            apply_keyword_filter: Anahtar kelime filtresi uygula
            
        Returns:
            Toplanan postlar
        """
        if subreddits is None:
            subreddits = self.DEFAULT_SUBREDDITS
        if sort_types is None:
            sort_types = ['hot', 'top']
            
        all_posts = []
        
        for subreddit in subreddits:
            for sort_type in sort_types:
                posts, _ = self._fetch_subreddit_page(
                    subreddit=subreddit,
                    sort=sort_type,
                    limit=limit_per_sub
                )
                all_posts.extend(posts)
                
        logger.info(f"Toplam {len(all_posts)} raw post toplandı")
        
        # Kalite filtresi
        if apply_keyword_filter:
            filtered = self._filter_quality_posts(all_posts, min_score=min_score)
            logger.info(f"Filtreleme sonrası: {len(filtered)} kaliteli post")
            return filtered
            
        return all_posts
    
    def deep_collect(
        self,
        subreddits: List[str] = None,
        pages_per_sub: int = 3,
        posts_per_page: int = 100,
        min_score: int = 3,
        time_filter: str = 'month',
        sort_types: List[str] = None
    ) -> List[Dict]:
        """
        Çoklu sayfa ile derin tarama.
        
        Args:
            subreddits: Subreddit listesi
            pages_per_sub: Her subreddit'ten kaç sayfa çek
            posts_per_page: Sayfa başına post (max 100)
            min_score: Minimum upvote
            time_filter: Zaman filtresi (week, month, year, all)
            sort_types: Sıralama tipleri (default: ['top', 'new', 'hot'])
            
        Returns:
            Filtrelenmiş postlar
        """
        if subreddits is None:
            subreddits = self.DEFAULT_SUBREDDITS[:10]
        
        if sort_types is None:
            sort_types = ['top', 'new', 'hot']  # Tüm sıralama türleri
        
        # Initialize progress tracking
        estimated_requests = len(subreddits) * len(sort_types) * pages_per_sub
        self._start_progress_tracking(estimated_requests)
            
        all_posts = []
        
        for subreddit in subreddits:
            logger.info(f"Deep collecting from r/{subreddit}...")
            
            for sort_type in sort_types:
                after = None
                
                for page in range(pages_per_sub):
                    posts, after = self._fetch_subreddit_page(
                        subreddit=subreddit,
                        sort=sort_type,
                        limit=posts_per_page,
                        time_filter=time_filter if sort_type == 'top' else 'week',
                        after=after
                    )
                    all_posts.extend(posts)
                    
                    if not after:  # No more pages
                        break
                    
        logger.info(f"Deep collect: {len(all_posts)} raw post toplandı (sort: {sort_types})")
        
        filtered = self._filter_quality_posts(all_posts, min_score=min_score)
        logger.info(f"Deep collect filtreleme: {len(filtered)} kaliteli post")
        
        return filtered
    
    def collect_single_subreddit(
        self,
        subreddit: str,
        limit: int = 50,
        min_score: int = 3
    ) -> List[Dict]:
        """
        Tek bir subreddit'ten hızlı tarama.
        
        Args:
            subreddit: Subreddit adı
            limit: Maximum post sayısı
            min_score: Minimum upvote skoru
            
        Returns:
            Filtrelenmiş postlar
        """
        posts = []
        for sort_type in ['hot', 'new', 'top']:
            fetched, _ = self._fetch_subreddit_page(subreddit, sort_type, limit // 3)
            posts.extend(fetched)
            
        return self._filter_quality_posts(posts, min_score=min_score)
    
    def get_stats(self) -> Dict:
        """Toplama istatistiklerini döndür."""
        return {
            'requests': self._stats.get('requests', 0),
            'posts_fetched': self._stats.get('posts_fetched', 0),
            'unique_posts': len(self._seen_ids),
        }
    
    def reset_stats(self):
        """İstatistikleri sıfırla."""
        self._stats = {'requests': 0, 'posts_fetched': 0}
        self._seen_ids.clear()
    
    def _start_progress_tracking(self, total_expected_requests: int):
        """Start tracking progress for estimated time calculation."""
        import time
        self._start_time = time.time()
        self._total_expected_requests = total_expected_requests
        self._completed_requests = 0
    
    def get_progress_stats(self) -> Dict:
        """
        Get current progress statistics including estimated time remaining.
        
        Returns:
            Dict with progress, elapsed_time, estimated_total_time, estimated_remaining_time
        """
        import time
        
        if self._start_time is None or self._total_expected_requests == 0:
            return {
                'progress': 0.0,
                'elapsed_seconds': 0,
                'estimated_total_seconds': 0,
                'estimated_remaining_seconds': 0,
                'estimated_remaining_str': 'N/A'
            }
        
        elapsed = time.time() - self._start_time
        progress = self._completed_requests / max(self._total_expected_requests, 1)
        
        if progress > 0:
            estimated_total = elapsed / progress
            estimated_remaining = max(0, estimated_total - elapsed)
        else:
            estimated_total = 0
            estimated_remaining = 0
        
        # Format remaining time
        if estimated_remaining < 60:
            time_str = f"{int(estimated_remaining)} saniye"
        else:
            minutes = int(estimated_remaining // 60)
            seconds = int(estimated_remaining % 60)
            time_str = f"{minutes} dk {seconds} sn"
        
        return {
            'progress': progress,
            'elapsed_seconds': int(elapsed),
            'estimated_total_seconds': int(estimated_total),
            'estimated_remaining_seconds': int(estimated_remaining),
            'estimated_remaining_str': time_str,
            'completed': self._completed_requests,
            'total': self._total_expected_requests
        }


# Demo / Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Reddit Collector - Test")
    print("=" * 60)
    
    collector = RedditCollector()
    
    # Tek subreddit testi
    posts = collector.collect_single_subreddit('algotrading', limit=30, min_score=3)
    
    print(f"\n📥 Toplanan post sayısı: {len(posts)}")
    print("\n" + "-" * 60)
    
    for i, post in enumerate(posts[:5], 1):
        print(f"\n{i}. {post['title'][:70]}...")
        print(f"   Score: {post['score']} | Comments: {post['num_comments']}")
        print(f"   URL: {post['url']}")
