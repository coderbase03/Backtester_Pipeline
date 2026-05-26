# -*- coding: utf-8 -*-
"""
GitHub Collector Module

GitHub'dan trading stratejileri (Pine Script, Python/Backtrader) toplar.
- Repository arama (token gerekmez)
- Code arama (token gerekli)
- Dosya içeriği çekme
- Strateji tespit etme

Usage:
    from src.scraper.github_collector import GitHubCollector
    
    collector = GitHubCollector()
    repos = collector.search_repositories("backtrader strategy")
    strategies = collector.collect_strategies()
"""

import requests
import time
import json
import re
import yaml
import base64
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class GitHubCollector:
    """
    GitHub'dan trading stratejileri toplar.
    
    Features:
    - Repository search (unauthenticated: 60 req/hour, authenticated: 5000 req/hour)
    - Code search (authenticated only: 30 req/minute)
    - File content extraction
    - Pine Script and Python strategy detection
    """
    
    # API endpoints
    BASE_URL = "https://api.github.com"
    SEARCH_REPOS_URL = f"{BASE_URL}/search/repositories"
    SEARCH_CODE_URL = f"{BASE_URL}/search/code"
    CONTENTS_URL = f"{BASE_URL}/repos/{{owner}}/{{repo}}/contents/{{path}}"
    
    # Default search queries
    DEFAULT_QUERIES = {
        'pine_script': [
            "trading strategy language:pine",
            "pinescript indicator",
        ],
        'python': [
            "backtrader strategy",
            "trading bot python",
        ]
    }
    
    def __init__(
        self,
        token: str = None,
        rate_limit_seconds: float = 2.5,
        config_path: str = None
    ):
        """
        Initialize GitHub collector.
        
        Args:
            token: GitHub Personal Access Token (optional, increases rate limits)
            rate_limit_seconds: Seconds to wait between requests
            config_path: Path to github.yaml config file
        """
        self.token = token or self._load_token()
        self.rate_limit_seconds = rate_limit_seconds
        self.last_request_time = 0
        
        # Stats
        self.stats = {
            'requests_made': 0,
            'repos_found': 0,
            'files_found': 0,
            'strategies_detected': 0,
            'errors': 0,
        }
        
        # Load config
        self.config = self._load_config(config_path)
        
        # Session for connection reuse
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json',
            })
        else:
            self.session.headers.update({
                'Accept': 'application/vnd.github.v3+json',
            })
        
        logger.info(f"GitHubCollector initialized (token: {'✓' if self.token else '✗'})")
    
    def _load_token(self) -> Optional[str]:
        """Load GitHub token from secrets.yaml."""
        try:
            secrets_path = Path(__file__).parent.parent.parent / "config" / "secrets.yaml"
            if secrets_path.exists():
                with open(secrets_path, 'r', encoding='utf-8') as f:
                    secrets = yaml.safe_load(f) or {}
                return secrets.get('github_token') or secrets.get('github', {}).get('token')
        except Exception as e:
            logger.warning(f"Could not load GitHub token: {e}")
        return None
    
    def _load_config(self, config_path: str = None) -> Dict:
        """Load GitHub config from yaml file."""
        try:
            if config_path is None:
                config_path = Path(__file__).parent.parent.parent / "config" / "github.yaml"
            else:
                config_path = Path(config_path)
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load GitHub config: {e}")
        
        return {
            'settings': {
                'rate_limit_seconds': 2.5,
                'max_repos_per_query': 30,
                'min_stars': 3,
            }
        }
    
    def _wait_rate_limit(self):
        """Wait for rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with rate limiting and error handling."""
        self._wait_rate_limit()
        self.stats['requests_made'] += 1
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            
            # Check rate limit
            remaining = response.headers.get('X-RateLimit-Remaining', 'N/A')
            logger.debug(f"Rate limit remaining: {remaining}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                logger.warning("Rate limit exceeded or authentication required")
                self.stats['errors'] += 1
                return None
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {url}")
                return None
            else:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
                self.stats['errors'] += 1
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            self.stats['errors'] += 1
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            self.stats['errors'] += 1
            return None
    
    def search_repositories(
        self,
        query: str,
        min_stars: int = None,
        language: str = None,
        sort: str = 'stars',
        order: str = 'desc',
        per_page: int = 30
    ) -> List[Dict]:
        """
        Search GitHub repositories.
        
        Args:
            query: Search query string
            min_stars: Minimum star count filter
            language: Programming language filter
            sort: Sort by (stars, forks, updated)
            order: Sort order (asc, desc)
            per_page: Results per page (max 100)
            
        Returns:
            List of repository dicts
        """
        min_stars = min_stars or self.config.get('settings', {}).get('min_stars', 3)
        
        # Build query
        full_query = query
        if min_stars:
            full_query += f" stars:>={min_stars}"
        if language:
            full_query += f" language:{language}"
        
        params = {
            'q': full_query,
            'sort': sort,
            'order': order,
            'per_page': min(per_page, 100),
        }
        
        logger.info(f"Searching repositories: {full_query}")
        
        result = self._make_request(self.SEARCH_REPOS_URL, params)
        
        if result and 'items' in result:
            repos = result['items']
            self.stats['repos_found'] += len(repos)
            logger.info(f"Found {len(repos)} repositories (total: {result.get('total_count', 'N/A')})")
            return repos
        
        return []
    
    def search_code(
        self,
        query: str,
        language: str = None,
        extension: str = None,
        filename: str = None,
        per_page: int = 30
    ) -> List[Dict]:
        """
        Search code files (requires authentication).
        
        Args:
            query: Search query
            language: Programming language
            extension: File extension (e.g., 'py', 'pine')
            filename: Filename pattern
            per_page: Results per page
            
        Returns:
            List of code file dicts
        """
        if not self.token:
            logger.warning("Code search requires GitHub token")
            return []
        
        # Build query
        full_query = query
        if language:
            full_query += f" language:{language}"
        if extension:
            full_query += f" extension:{extension}"
        if filename:
            full_query += f" filename:{filename}"
        
        params = {
            'q': full_query,
            'per_page': min(per_page, 100),
        }
        
        logger.info(f"Searching code: {full_query}")
        
        result = self._make_request(self.SEARCH_CODE_URL, params)
        
        if result and 'items' in result:
            files = result['items']
            self.stats['files_found'] += len(files)
            logger.info(f"Found {len(files)} code files")
            return files
        
        return []
    
    def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        Get raw file content from repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path within repository
            
        Returns:
            File content as string, or None if failed
        """
        url = self.CONTENTS_URL.format(owner=owner, repo=repo, path=path)
        
        result = self._make_request(url)
        
        if result and 'content' in result:
            try:
                # GitHub returns base64 encoded content
                content = base64.b64decode(result['content']).decode('utf-8')
                return content
            except Exception as e:
                logger.error(f"Failed to decode file content: {e}")
        
        return None
    
    def get_repository_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
        recursive: bool = True,
        max_depth: int = 2,
        max_files: int = 100,
        _current_count: int = 0
    ) -> List[Dict]:
        """
        Get list of files in a repository directory.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Directory path (empty for root)
            recursive: Whether to recurse into subdirectories
            max_depth: Maximum recursion depth
            max_files: Maximum total files to return (prevents hanging)
            
        Returns:
            List of file info dicts
        """
        if max_depth <= 0 or _current_count >= max_files:
            return []
        
        url = self.CONTENTS_URL.format(owner=owner, repo=repo, path=path)
        result = self._make_request(url)
        
        if not result:
            return []
        
        # Handle single file response
        if isinstance(result, dict):
            return [result] if result.get('type') == 'file' else []
        
        files = []
        for item in result:
            if len(files) + _current_count >= max_files:
                break  # Stop if we've reached the limit
                
            if item['type'] == 'file':
                files.append(item)
            elif item['type'] == 'dir' and recursive:
                # Only recurse into promising directories
                dir_name = item['name'].lower()
                skip_dirs = ['test', 'tests', 'docs', 'doc', 'examples', 'sample', '.github', 'node_modules', '__pycache__', 'venv', 'env']
                if dir_name not in skip_dirs:
                    subfiles = self.get_repository_files(
                        owner, repo, item['path'], recursive, max_depth - 1,
                        max_files, _current_count + len(files)
                    )
                    files.extend(subfiles)
        
        return files
    
    def detect_pine_scripts(self, owner: str, repo: str, max_strategies: int = 10) -> List[Dict]:
        """
        Find Pine Script files in a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            max_strategies: Maximum strategies to find per repo
            
        Returns:
            List of Pine Script file info with content
        """
        pine_files = []
        
        # Get files with limit
        files = self.get_repository_files(owner, repo, max_files=100)
        
        for f in files:
            if len(pine_files) >= max_strategies:
                break
                
            name = f['name'].lower()
            # Check for Pine Script files
            if (name.endswith('.pine') or 
                name.endswith('.pinescript') or
                ('pine' in name and name.endswith('.txt')) or
                ('indicator' in name and name.endswith('.txt')) or
                ('strategy' in name and name.endswith('.txt'))):
                
                content = self.get_file_content(owner, repo, f['path'])
                if content and self._is_pine_script(content):
                    pine_files.append({
                        'name': f['name'],
                        'path': f['path'],
                        'url': f.get('html_url', ''),
                        'size': f.get('size', 0),
                        'content': content,
                        'type': 'pine_script',
                    })
                    self.stats['strategies_detected'] += 1
        
        return pine_files
    
    def detect_python_strategies(self, owner: str, repo: str, max_strategies: int = 10) -> List[Dict]:
        """
        Find Python strategy files in a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            max_strategies: Maximum strategies to find per repo
            
        Returns:
            List of Python strategy file info with content
        """
        python_files = []
        
        # Get files with limit
        files = self.get_repository_files(owner, repo, max_files=100)
        
        for f in files:
            if len(python_files) >= max_strategies:
                break
                
            name = f['name'].lower()
            # Check for Python strategy files
            if name.endswith('.py'):
                # Filter by filename patterns
                if any(pattern in name for pattern in ['strategy', 'signal', 'indicator', 'bot', 'algo', 'backtest', 'trading']):
                    content = self.get_file_content(owner, repo, f['path'])
                    if content and self._is_python_strategy(content):
                        python_files.append({
                            'name': f['name'],
                            'path': f['path'],
                            'url': f.get('html_url', ''),
                            'size': f.get('size', 0),
                            'content': content,
                            'type': 'python',
                        })
                        self.stats['strategies_detected'] += 1
        
        return python_files
    
    def _is_pine_script(self, content: str) -> bool:
        """Check if content is valid Pine Script."""
        indicators = [
            '//@version',
            'study(',
            'strategy(',
            'indicator(',
            'plot(',
            'ta.',
            'input.',
            'close',
            'open',
            'high',
            'low',
        ]
        content_lower = content.lower()
        return sum(1 for ind in indicators if ind.lower() in content_lower) >= 3
    
    def _is_python_strategy(self, content: str) -> bool:
        """Check if content is valid Python trading strategy."""
        indicators = [
            'import backtrader',
            'bt.Strategy',
            'bt.Cerebro',
            'def next(',
            'self.buy(',
            'self.sell(',
            'self.close(',
            'import pandas',
            'import numpy',
            'SMA',
            'RSI',
            'EMA',
        ]
        return sum(1 for ind in indicators if ind in content) >= 2
    
    def collect_strategies(
        self,
        queries: List[str] = None,
        max_repos: int = None,
        include_code_search: bool = True
    ) -> List[Dict]:
        """
        Main collection method - searches and extracts strategies.
        
        Args:
            queries: List of search queries (uses config if None)
            max_repos: Maximum repositories to process
            include_code_search: Whether to use code search (requires token)
            
        Returns:
            List of strategy dicts with metadata and content
        """
        max_repos = max_repos or self.config.get('settings', {}).get('max_repos_per_query', 30)
        
        # Get queries from config
        if queries is None:
            queries = []
            for category in self.config.get('search_queries', {}).values():
                if isinstance(category, list):
                    queries.extend(category)
        
        all_strategies = []
        seen_repos = set()
        
        for query in queries:
            logger.info(f"Processing query: {query}")
            
            # Search repositories
            repos = self.search_repositories(query, per_page=max_repos)
            
            for repo in repos[:max_repos]:
                repo_full_name = repo['full_name']
                if repo_full_name in seen_repos:
                    continue
                seen_repos.add(repo_full_name)
                
                owner, name = repo_full_name.split('/')
                
                # Detect strategies
                try:
                    # Pine Script
                    pine_files = self.detect_pine_scripts(owner, name)
                    for pf in pine_files:
                        pf['repo'] = repo_full_name
                        pf['repo_stars'] = repo.get('stargazers_count', 0)
                        pf['repo_url'] = repo.get('html_url', '')
                        pf['repo_description'] = repo.get('description', '')
                        all_strategies.append(pf)
                    
                    # Python
                    python_files = self.detect_python_strategies(owner, name)
                    for pf in python_files:
                        pf['repo'] = repo_full_name
                        pf['repo_stars'] = repo.get('stargazers_count', 0)
                        pf['repo_url'] = repo.get('html_url', '')
                        pf['repo_description'] = repo.get('description', '')
                        all_strategies.append(pf)
                        
                except Exception as e:
                    logger.warning(f"Error processing repo {repo_full_name}: {e}")
        
        logger.info(f"Collection complete: {len(all_strategies)} strategies from {len(seen_repos)} repos")
        return all_strategies
    
    def get_stats(self) -> Dict:
        """Get collection statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'requests_made': 0,
            'repos_found': 0,
            'files_found': 0,
            'strategies_detected': 0,
            'errors': 0,
        }
    
    def check_rate_limit(self) -> Dict:
        """Check current rate limit status."""
        result = self._make_request(f"{self.BASE_URL}/rate_limit")
        if result:
            return result.get('resources', {})
        return {}


# Utility functions
def quick_search(query: str, max_results: int = 10) -> List[Dict]:
    """Quick search for repositories."""
    collector = GitHubCollector()
    return collector.search_repositories(query, per_page=max_results)


# Demo
if __name__ == "__main__":
    print("GitHub Collector Demo")
    print("=" * 50)
    
    collector = GitHubCollector()
    
    # Check rate limit
    limits = collector.check_rate_limit()
    if limits:
        core = limits.get('core', {})
        print(f"Rate limit: {core.get('remaining', 'N/A')}/{core.get('limit', 'N/A')}")
    
    # Search repositories
    print("\nSearching for 'backtrader strategy'...")
    repos = collector.search_repositories("backtrader strategy", per_page=5)
    
    for repo in repos[:5]:
        print(f"  ⭐ {repo['stargazers_count']:4d} | {repo['full_name']}")
        print(f"       {repo.get('description', 'No description')[:60]}")
    
    print(f"\nStats: {collector.get_stats()}")
