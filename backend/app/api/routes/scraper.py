"""
Scraper API routes (Reddit + GitHub).
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from ...schemas.scraper import (
    RedditCollectRequest,
    RedditAnalyzeRequest,
    GitHubSearchRequest,
    CollectResult,
    AnalyzeResult,
    GitHubSearchResult,
    PaginatedPostsResponse,
    AnalyzeSingleResult,
    ActionableApproveRequest,
    ActionableApproveBulkRequest,
    ActionableConvertTestRequest,
)
from ...services import scraper_service

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.get("/subreddits")
async def get_subreddits():
    """Get subreddit presets from config/subreddits.yaml."""
    try:
        return scraper_service.get_subreddit_presets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reddit/collect", response_model=CollectResult)
async def collect_reddit(req: RedditCollectRequest):
    """Collect posts from Reddit."""
    try:
        result = scraper_service.collect_reddit(
            subreddits=req.subreddits,
            limit=req.limit,
            min_score=req.min_score,
            time_filter=req.time_filter,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Collection failed: {e}")


@router.post("/reddit/collect-stream")
async def collect_reddit_stream(req: RedditCollectRequest):
    """SSE stream: per-subreddit progress during collection."""

    def _event_generator():
        for chunk in scraper_service.collect_reddit_stream(
            subreddits=req.subreddits,
            limit=req.limit,
            min_score=req.min_score,
            time_filter=req.time_filter,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/reddit/analyze", response_model=AnalyzeResult)
async def analyze_posts(req: RedditAnalyzeRequest):
    """Run AI analysis on unprocessed posts."""
    try:
        result = scraper_service.analyze_posts(
            batch_size=req.batch_size,
            min_priority=req.min_priority,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.get("/posts", response_model=PaginatedPostsResponse)
async def get_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=100),
    filter: Optional[str] = Query(default=None, description="all, analyzed, unanalyzed"),
    search: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    subreddit: Optional[str] = Query(default=None),
    min_post_score: Optional[int] = Query(default=None),
    max_post_score: Optional[int] = Query(default=None),
    min_ai_score: Optional[float] = Query(default=None),
    max_ai_score: Optional[float] = Query(default=None),
    has_strategy: Optional[bool] = Query(default=None),
    has_entry_rules: Optional[bool] = Query(default=None),
    has_exit_rules: Optional[bool] = Query(default=None),
    strategy_status: Optional[str] = Query(default=None),
    strategy_category: Optional[str] = Query(default=None),
    timeframe: Optional[str] = Query(default=None),
    sort_by: str = Query(default="collected_at"),
    sort_dir: str = Query(default="desc"),
):
    """Get paginated raw posts from the database."""
    try:
        result = scraper_service.get_raw_posts_paginated(
            page=page,
            page_size=page_size,
            filter_status=filter,
            search=search,
            category=category,
            subreddit=subreddit,
            min_post_score=min_post_score,
            max_post_score=max_post_score,
            min_ai_score=min_ai_score,
            max_ai_score=max_ai_score,
            has_strategy=has_strategy,
            has_entry_rules=has_entry_rules,
            has_exit_rules=has_exit_rules,
            strategy_status=strategy_status,
            strategy_category=strategy_category,
            timeframe=timeframe,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/posts/{hash_id}/analyze", response_model=AnalyzeSingleResult)
async def analyze_single_post(hash_id: str):
    """Run AI analysis on a single post."""
    try:
        result = scraper_service.analyze_single_post(hash_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.post("/posts/analyze-batch", response_model=AnalyzeResult)
async def analyze_batch(req: RedditAnalyzeRequest):
    """Run AI analysis on a batch of unprocessed posts."""
    try:
        result = scraper_service.analyze_posts(
            batch_size=req.batch_size,
            min_priority=req.min_priority,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {e}")


@router.post("/posts/analyze-batch-stream")
async def analyze_batch_stream(req: RedditAnalyzeRequest):
    """SSE stream: per-post progress during batch analysis."""

    def _event_generator():
        for chunk in scraper_service.analyze_posts_stream(
            batch_size=req.batch_size,
            min_priority=req.min_priority,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/github/search", response_model=GitHubSearchResult)
async def search_github(req: GitHubSearchRequest):
    """Search GitHub for strategy repos."""
    try:
        result = scraper_service.search_github(
            query=req.query,
            language=req.language,
            min_stars=req.min_stars,
            max_repos=req.max_repos,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub search failed: {e}")


@router.get("/strategies")
async def get_strategies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=100),
    search: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    min_score: Optional[float] = Query(default=None, ge=0, le=100),
    max_score: Optional[float] = Query(default=None, ge=0, le=100),
    has_entry_rules: Optional[bool] = Query(default=None),
    has_exit_rules: Optional[bool] = Query(default=None),
    timeframe: Optional[str] = Query(default=None),
    sort_by: str = Query(default="ai_score"),
    sort_dir: str = Query(default="desc"),
):
    """Get paginated filtered strategies from the database."""
    try:
        return scraper_service.get_filtered_strategies_paginated(
            page=page,
            page_size=page_size,
            search=search,
            category=category,
            status=status,
            min_score=min_score,
            max_score=max_score,
            has_entry_rules=has_entry_rules,
            has_exit_rules=has_exit_rules,
            timeframe=timeframe,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actionable/approve")
async def approve_actionable(req: ActionableApproveRequest):
    """Approve/reject a single actionable strategy."""
    try:
        return scraper_service.approve_actionable_strategy(
            strategy_id=req.strategy_id,
            approved=req.approved,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actionable/approve-bulk")
async def approve_actionable_bulk(req: ActionableApproveBulkRequest):
    """Approve first N actionable strategies by score."""
    try:
        return scraper_service.approve_actionable_bulk(
            limit=req.limit,
            min_score=req.min_score,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actionable/convert-and-test")
async def convert_and_test_actionable(req: ActionableConvertTestRequest):
    """Convert actionable strategies to code and auto-backtest across symbol/TF matrix."""
    try:
        return scraper_service.convert_and_test_actionable(
            strategy_ids=req.strategy_ids,
            first_n=req.first_n,
            only_approved=req.only_approved,
            symbols=req.symbols,
            intervals=req.intervals,
            n_bars=req.n_bars,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actionable/convert-and-test-stream")
async def convert_and_test_actionable_stream(req: ActionableConvertTestRequest):
    """SSE stream for actionable convert+test pipeline progress."""

    def _event_generator():
        for chunk in scraper_service.convert_and_test_actionable_stream(
            strategy_ids=req.strategy_ids,
            first_n=req.first_n,
            only_approved=req.only_approved,
            symbols=req.symbols,
            intervals=req.intervals,
            n_bars=req.n_bars,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/reports/runs")
async def get_pipeline_report_runs(
    limit: int = Query(default=50, ge=1, le=500),
):
    """List pipeline run reports for UI table view."""
    try:
        return {"runs": scraper_service.get_pipeline_reports(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
