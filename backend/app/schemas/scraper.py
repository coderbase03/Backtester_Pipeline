"""
Pydantic schemas for scraper endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RedditCollectRequest(BaseModel):
    subreddits: list[str] = ["algotrading"]
    limit: int = Field(default=25, ge=1, le=100)
    min_score: int = 0
    time_filter: str = "week"


class RedditAnalyzeRequest(BaseModel):
    batch_size: int = Field(default=10, ge=1, le=50)
    min_priority: int = 0


class GitHubSearchRequest(BaseModel):
    query: str = "backtrader strategy"
    language: Optional[str] = "python"
    min_stars: int = 5
    max_repos: int = 20


class CollectResult(BaseModel):
    total_collected: int
    new_posts: int
    duplicates: int
    subreddits: list[str]


class AnalyzeResult(BaseModel):
    total_analyzed: int
    actionable: int
    methodology: int
    noise: int
    total_cost_usd: float


class GitHubSearchResult(BaseModel):
    repos_found: int
    strategies_detected: int
    new_strategies: int


# --- Paginated posts ---

class RawPostResponse(BaseModel):
    hash_id: str
    reddit_id: Optional[str] = None
    subreddit: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    score: int = 0
    comments: int = 0
    author: Optional[str] = None
    post_created_at: Optional[str] = None
    collected_at: Optional[str] = None
    ai_processed: bool = False
    stage1_category: Optional[str] = None
    stage1_processed_at: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_name: Optional[str] = None
    entry_rules: Optional[str] = None
    exit_rules: Optional[str] = None
    strategy_indicators: Optional[list[str]] = None
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None
    ai_score: Optional[float] = None
    strategy_timeframe: Optional[str] = None
    strategy_summary: Optional[str] = None
    strategy_status: Optional[str] = None
    approval_status: Optional[str] = None
    execution_status: Optional[str] = None
    fix_category: Optional[str] = None
    strategy_category: Optional[str] = None
    rule_quality: Optional[str] = None


class PaginatedPostsResponse(BaseModel):
    posts: list[RawPostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AnalyzeSingleResult(BaseModel):
    hash_id: str
    category: str
    strategy_saved: bool = False
    insight_saved: bool = False
    strategy_name: Optional[str] = None
    ai_score: float = 0


class ActionableApproveRequest(BaseModel):
    strategy_id: int
    approved: bool = True


class ActionableApproveBulkRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=500)
    min_score: float = Field(default=0, ge=0, le=100)


class ActionableConvertTestRequest(BaseModel):
    strategy_ids: Optional[list[int]] = None
    first_n: int = Field(default=10, ge=1, le=500)
    only_approved: bool = True
    symbols: Optional[list[str]] = None
    intervals: Optional[list[str]] = None
    n_bars: int = Field(default=1000, ge=100, le=10000)
