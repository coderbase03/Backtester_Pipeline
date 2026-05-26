"""
Strategy-related models.

Covers:
- Scraped Reddit posts (raw_posts)
- AI-filtered strategies (filtered_strategies)
- GitHub raw strategies (github_raw_strategies)
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean
from sqlalchemy.sql import func

from ..core.database import Base


class RawPost(Base):
    __tablename__ = "raw_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    subreddit = Column(String(100))
    title = Column(Text)
    content = Column(Text)
    author = Column(String(100))
    url = Column(Text)
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    created_utc = Column(DateTime)
    collected_at = Column(DateTime, server_default=func.now())
    ai_processed = Column(Boolean, default=False)
    ai_category = Column(String(50))


class FilteredStrategy(Base):
    __tablename__ = "filtered_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(50), index=True)
    strategy_name = Column(String(200))
    summary = Column(Text)
    entry_rules = Column(Text)
    exit_rules = Column(Text)
    indicators = Column(Text)  # JSON string
    timeframe = Column(String(20))
    markets = Column(Text)  # JSON string
    tp_pct = Column(Float)
    sl_pct = Column(Float)
    ai_score = Column(Integer, default=0)
    ai_notes = Column(Text)
    ai_category = Column(String(50))
    source_url = Column(Text)
    generated_code = Column(Text)
    code_valid = Column(Boolean, default=False)
    backtest_result = Column(Text)  # JSON string
    status = Column(String(20), default="pending")  # pending/approved/rejected/coded
    created_at = Column(DateTime, server_default=func.now())


class GitHubRawStrategy(Base):
    __tablename__ = "github_raw_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash_id = Column(String(64), unique=True, nullable=False, index=True)
    repo_full_name = Column(String(200))
    repo_stars = Column(Integer, default=0)
    repo_description = Column(Text)
    file_path = Column(Text)
    file_name = Column(String(200))
    file_content = Column(Text)
    language = Column(String(20))  # pine / python
    ai_processed = Column(Boolean, default=False)
    ai_category = Column(String(50))
    ai_score = Column(Integer, default=0)
    ai_summary = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())


class APIUsage(Base):
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50))  # openai / glm / github
    model = Column(String(100))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0)
    operation = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
