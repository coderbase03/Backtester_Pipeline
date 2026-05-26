"""
Scraper service - wraps Reddit/GitHub collectors for API use.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Iterable
import tempfile
import importlib.util
import json as _json

ENGINE_ROOT = Path(__file__).resolve().parents[3]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

logger = logging.getLogger(__name__)


def _find_generated_strategy_class(code: str):
    """Load generated code into temp module and return first BaseStrategy subclass."""
    from src.strategies.base import BaseStrategy

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    module_name = f"generated_strategy_{Path(temp_path).stem}"
    spec = importlib.util.spec_from_file_location(module_name, temp_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to create module spec for generated strategy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
            return attr
    raise RuntimeError("No BaseStrategy subclass found in generated code")


def _is_needs_fix_result(result: dict) -> tuple[bool, str]:
    """Return (needs_fix, reason)."""
    if result is None:
        return True, "DATA_NULL"
    if result.get("error"):
        return True, "RUNTIME_ERROR"
    equity = result.get("equity_curve") or []
    if not equity:
        return True, "DATA_NULL"
    if result.get("total_trades") in (None,):
        return True, "NO_TRADES"
    if isinstance(result.get("total_trades"), (int, float)) and result.get("total_trades", 0) <= 0:
        return True, "NO_TRADES"
    return False, "OK"


def _select_posts_for_analysis(storage, batch_size: int, min_priority: int):
    """
    Select unprocessed posts based on regex pre-filter priority.

    Notes:
    - min_priority <= 0 keeps prior behavior (simple batch fetch).
    - For min_priority > 0, we inspect a larger candidate pool and keep only
      posts with prefilter priority_score >= min_priority.
    """
    from src.scraper.ai_extractor import pre_filter_post

    if min_priority <= 0:
        return storage.get_unprocessed_posts(limit=batch_size)

    candidate_limit = min(max(batch_size * 10, batch_size), 500)
    candidates = storage.get_unprocessed_posts(limit=candidate_limit)
    selected = []

    for post in candidates:
        title = post.get("title", "")
        content = post.get("selftext") or post.get("content", "")
        pf = pre_filter_post(title, content)
        score = int(pf.get("final_priority_score", pf.get("priority_score", 0)))
        if score >= min_priority:
            selected.append(post)
            if len(selected) >= batch_size:
                break

    return selected


def get_subreddit_presets() -> dict:
    """Read subreddit presets from config/subreddits.yaml."""
    import yaml

    config_path = ENGINE_ROOT / "config" / "subreddits.yaml"
    if not config_path.exists():
        return {"tiers": {}, "settings": {}}

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return {
        "tiers": config.get("subreddits", {}),
        "settings": config.get("settings", {}),
    }


def collect_reddit(
    subreddits: list[str],
    limit: int = 25,
    min_score: int = 0,
    time_filter: str = "week",
) -> dict:
    """Collect posts from Reddit and return summary."""
    from src.scraper.reddit_collector import RedditCollector
    from src.scraper.strategy_storage import StrategyStorage

    collector = RedditCollector()
    storage = StrategyStorage()

    total = 0
    new = 0
    dupes = 0

    for sub in subreddits:
        try:
            posts = collector.collect_posts(
                subreddits=[sub],
                limit_per_sub=limit,
                min_score=min_score,
            )
            saved_count, dup_count = storage.save_raw_posts_batch(posts)
            total += saved_count + dup_count
            new += saved_count
            dupes += dup_count
        except Exception as e:
            logger.warning("Reddit collect failed for r/%s: %s", sub, e)

    return {
        "total_collected": total,
        "new_posts": new,
        "duplicates": dupes,
        "subreddits": subreddits,
    }


def collect_reddit_stream(
    subreddits: list[str],
    limit: int = 25,
    min_score: int = 0,
    time_filter: str = "week",
):
    """Generator yielding per-subreddit collect progress for SSE streaming."""
    import json as _json
    from src.scraper.reddit_collector import RedditCollector
    from src.scraper.strategy_storage import StrategyStorage

    collector = RedditCollector()
    storage = StrategyStorage()

    total_subs = len(subreddits)
    agg_new = 0
    agg_dupes = 0
    agg_collected = 0

    if total_subs == 0:
        yield _json.dumps({"current": 0, "total": 0, "done": True, "total_collected": 0, "new_posts": 0, "duplicates": 0})
        return

    for i, sub in enumerate(subreddits, 1):
        error = None
        sub_new = 0
        sub_dupes = 0
        try:
            posts = collector.collect_posts(
                subreddits=[sub],
                limit_per_sub=limit,
                min_score=min_score,
            )
            saved_count, dup_count = storage.save_raw_posts_batch(posts)
            sub_new = saved_count
            sub_dupes = dup_count
            agg_new += saved_count
            agg_dupes += dup_count
            agg_collected += saved_count + dup_count
        except Exception as e:
            logger.warning("Reddit collect failed for r/%s: %s", sub, e)
            error = str(e)

        yield _json.dumps({
            "current": i,
            "total": total_subs,
            "subreddit": sub,
            "new_posts": sub_new,
            "duplicates": sub_dupes,
            "error": error,
            "done": False,
        })

    yield _json.dumps({
        "current": total_subs,
        "total": total_subs,
        "done": True,
        "total_collected": agg_collected,
        "new_posts": agg_new,
        "duplicates": agg_dupes,
    })


def analyze_posts(batch_size: int = 10, min_priority: int = 0) -> dict:
    """Run AI analysis on unprocessed posts."""
    from src.scraper.ai_extractor import SmartExtractor
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    extractor = SmartExtractor()

    unprocessed = _select_posts_for_analysis(
        storage=storage,
        batch_size=batch_size,
        min_priority=min_priority,
    )
    actionable = 0
    methodology = 0
    noise = 0
    total_cost = 0.0

    for post in unprocessed:
        try:
            result = extractor.process_post(post, skip_if_analyzed=True)
            if result:
                cat = result.get("category", "NOISE")
                storage.mark_stage1_processed(post["hash_id"], cat)
                if cat == "ACTIONABLE_STRATEGY":
                    actionable += 1
                elif cat == "METHODOLOGY":
                    methodology += 1
                else:
                    noise += 1
                if result.get("strategy"):
                    storage.save_filtered_strategy(post["hash_id"], result["strategy"])
                if result.get("insight"):
                    storage.save_insight(post["hash_id"], result["insight"])
        except Exception as e:
            logger.warning("Analysis failed for post %s: %s", post.get("hash_id"), e)
            noise += 1

    return {
        "total_analyzed": len(unprocessed),
        "actionable": actionable,
        "methodology": methodology,
        "noise": noise,
        "total_cost_usd": round(total_cost, 6),
    }


def analyze_posts_stream(batch_size: int = 10, min_priority: int = 0):
    """Generator that yields per-post analysis results for SSE streaming."""
    import json as _json
    from src.scraper.ai_extractor import SmartExtractor
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    extractor = SmartExtractor()

    unprocessed = _select_posts_for_analysis(
        storage=storage,
        batch_size=batch_size,
        min_priority=min_priority,
    )
    total = len(unprocessed)

    if total == 0:
        yield _json.dumps({"current": 0, "total": 0, "done": True})
        return

    actionable = 0
    methodology = 0
    noise = 0

    for i, post in enumerate(unprocessed, 1):
        hash_id = post.get("hash_id", "")
        title = (post.get("title") or "Untitled")[:80]
        cat = "NOISE"
        strategy_name = None
        error = None

        try:
            result = extractor.process_post(post, skip_if_analyzed=True)
            if result:
                cat = result.get("category", "NOISE")
                storage.mark_stage1_processed(hash_id, cat)
                if cat == "ACTIONABLE_STRATEGY":
                    actionable += 1
                elif cat == "METHODOLOGY":
                    methodology += 1
                else:
                    noise += 1
                if result.get("strategy"):
                    storage.save_filtered_strategy(hash_id, result["strategy"])
                    strategy_name = result["strategy"].get("strategy_name")
                if result.get("insight"):
                    storage.save_insight(hash_id, result["insight"])
            else:
                noise += 1
        except Exception as e:
            logger.warning("Analysis failed for post %s: %s", hash_id, e)
            noise += 1
            error = str(e)

        yield _json.dumps({
            "current": i,
            "total": total,
            "hash_id": hash_id,
            "title": title,
            "category": cat,
            "strategy_name": strategy_name,
            "priority_score": (result or {}).get("priority_score") if result else None,
            "final_priority_score": (result or {}).get("final_priority_score") if result else None,
            "rule_quality": (result or {}).get("rule_quality") if result else None,
            "error": error,
            "done": False,
        })

    yield _json.dumps({
        "current": total,
        "total": total,
        "done": True,
        "actionable": actionable,
        "methodology": methodology,
        "noise": noise,
    })


def analyze_single_post(hash_id: str) -> dict:
    """Run AI analysis on a single post by hash_id."""
    from src.scraper.ai_extractor import SmartExtractor
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    extractor = SmartExtractor()

    posts = storage.get_raw_posts(limit=5000)
    row = next((p for p in posts if p.get("hash_id") == hash_id), None)
    if not row:
        raise ValueError(f"Post not found: {hash_id}")
    result = extractor.process_post(row, skip_if_analyzed=False)

    if not result:
        raise RuntimeError("AI analysis returned no result")

    cat = result.get("category", "NOISE")
    storage.mark_stage1_processed(hash_id, cat)

    strategy_saved = False
    insight_saved = False

    if result.get("strategy"):
        storage.save_filtered_strategy(hash_id, result["strategy"])
        strategy_saved = True
    if result.get("insight"):
        storage.save_insight(hash_id, result["insight"])
        insight_saved = True

    return {
        "hash_id": hash_id,
        "category": cat,
        "strategy_saved": strategy_saved,
        "insight_saved": insight_saved,
        "strategy_name": result.get("strategy", {}).get("strategy_name") if strategy_saved else None,
        "ai_score": result.get("strategy", {}).get("quality_score", 0) if strategy_saved else 0,
    }


def get_raw_posts_paginated(
    page: int = 1,
    page_size: int = 25,
    filter_status: Optional[str] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    subreddit: Optional[str] = None,
    min_post_score: Optional[int] = None,
    max_post_score: Optional[int] = None,
    min_ai_score: Optional[float] = None,
    max_ai_score: Optional[float] = None,
    has_strategy: Optional[bool] = None,
    has_entry_rules: Optional[bool] = None,
    has_exit_rules: Optional[bool] = None,
    strategy_status: Optional[str] = None,
    strategy_category: Optional[str] = None,
    timeframe: Optional[str] = None,
    sort_by: str = "collected_at",
    sort_dir: str = "desc",
) -> dict:
    """Get paginated raw posts with optional strategy details and filters."""
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    processed = True if filter_status == "analyzed" else False if filter_status == "unanalyzed" else None
    posts = storage.get_raw_posts(processed=processed, limit=20000)
    strategies = storage.get_filtered_strategies(min_score=0, status=None, limit=20000)
    by_hash = {}
    for s in strategies:
        by_hash.setdefault(s.get("raw_hash_id"), []).append(s)

    merged = []
    for p in posts:
        rows = by_hash.get(p.get("hash_id")) or [None]
        for s in rows:
            d = dict(p)
            if s:
                d.update(
                    {
                        "strategy_id": s.get("id"),
                        "strategy_name": s.get("strategy_name"),
                        "entry_rules": s.get("entry_rules"),
                        "exit_rules": s.get("exit_rules"),
                        "strategy_indicators": s.get("indicators"),
                        "tp_pct": s.get("tp_pct"),
                        "sl_pct": s.get("sl_pct"),
                        "ai_score": s.get("ai_score"),
                        "strategy_timeframe": s.get("timeframe"),
                        "strategy_summary": s.get("summary"),
                        "strategy_status": s.get("status"),
                        "approval_status": s.get("approval_status"),
                        "execution_status": s.get("execution_status"),
                        "fix_category": s.get("fix_category"),
                        "strategy_category": s.get("category"),
                        "rule_quality": s.get("rule_quality"),
                    }
                )
            merged.append(d)

    def contains(val, q):
        return q.lower() in str(val or "").lower()

    rows = merged
    if search:
        rows = [r for r in rows if contains(r.get("title"), search) or contains(r.get("subreddit"), search) or contains(r.get("content"), search) or contains(r.get("strategy_name"), search)]
    if category:
        rows = [r for r in rows if r.get("stage1_category") == category]
    if subreddit:
        rows = [r for r in rows if str(r.get("subreddit", "")).lower() == subreddit.lower()]
    if min_post_score is not None:
        rows = [r for r in rows if float(r.get("score") or 0) >= min_post_score]
    if max_post_score is not None:
        rows = [r for r in rows if float(r.get("score") or 0) <= max_post_score]
    if min_ai_score is not None:
        rows = [r for r in rows if r.get("ai_score") is not None and float(r.get("ai_score") or 0) >= min_ai_score]
    if max_ai_score is not None:
        rows = [r for r in rows if r.get("ai_score") is not None and float(r.get("ai_score") or 0) <= max_ai_score]
    if has_strategy is True:
        rows = [r for r in rows if (r.get("strategy_name") or "").strip()]
    if has_strategy is False:
        rows = [r for r in rows if not (r.get("strategy_name") or "").strip()]
    if has_entry_rules is True:
        rows = [r for r in rows if (r.get("entry_rules") or "").strip()]
    if has_entry_rules is False:
        rows = [r for r in rows if not (r.get("entry_rules") or "").strip()]
    if has_exit_rules is True:
        rows = [r for r in rows if (r.get("exit_rules") or "").strip()]
    if has_exit_rules is False:
        rows = [r for r in rows if not (r.get("exit_rules") or "").strip()]
    if strategy_status:
        rows = [r for r in rows if r.get("strategy_status") == strategy_status]
    if strategy_category:
        rows = [r for r in rows if r.get("strategy_category") == strategy_category]
    if timeframe:
        rows = [r for r in rows if r.get("strategy_timeframe") == timeframe]

    reverse = str(sort_dir).lower() != "asc"
    key_map = {
        "collected_at": lambda r: r.get("collected_at") or "",
        "post_created_at": lambda r: r.get("post_created_at") or "",
        "score": lambda r: r.get("score") or 0,
        "comments": lambda r: r.get("comments") or 0,
        "subreddit": lambda r: r.get("subreddit") or "",
        "ai_score": lambda r: r.get("ai_score") or 0,
        "strategy_name": lambda r: r.get("strategy_name") or "",
        "timeframe": lambda r: r.get("strategy_timeframe") or "",
    }
    rows.sort(key=key_map.get(sort_by, key_map["collected_at"]), reverse=reverse)

    total = len(rows)
    offset = (page - 1) * page_size
    rows = rows[offset:offset + page_size]
    return {"posts": rows, "total": total, "page": page, "page_size": page_size, "total_pages": max(1, (total + page_size - 1) // page_size)}


def search_github(
    query: str = "backtrader strategy",
    language: Optional[str] = "python",
    min_stars: int = 5,
    max_repos: int = 20,
) -> dict:
    """Search GitHub for strategy repositories."""
    from src.scraper.github_collector import GitHubCollector

    collector = GitHubCollector()
    try:
        repos = collector.search_repositories(query=query, min_stars=min_stars, max_results=max_repos)
        strategies = 0
        new_strategies = 0

        for repo in repos:
            try:
                detected = collector.detect_strategies(repo)
                strategies += len(detected)
                for s in detected:
                    saved = collector.save_strategy(s)
                    if saved:
                        new_strategies += 1
            except Exception as e:
                logger.warning("Strategy detection failed for %s: %s", repo.get("full_name"), e)

        return {
            "repos_found": len(repos),
            "strategies_detected": strategies,
            "new_strategies": new_strategies,
        }
    except Exception as e:
        logger.error("GitHub search failed: %s", e)
        return {"repos_found": 0, "strategies_detected": 0, "new_strategies": 0}


def get_filtered_strategies_paginated(
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    has_entry_rules: Optional[bool] = None,
    has_exit_rules: Optional[bool] = None,
    timeframe: Optional[str] = None,
    sort_by: str = "ai_score",
    sort_dir: str = "desc",
) -> dict:
    """Get paginated strategies with filtering and sorting."""
    from src.scraper.strategy_storage import StrategyStorage
    storage = StrategyStorage()
    rows = storage.get_filtered_strategies(min_score=min_score or 0, status=status, limit=10000)
    if category:
        rows = [r for r in rows if r.get("category") == category]
    if timeframe:
        rows = [r for r in rows if r.get("timeframe") == timeframe]
    if search:
        s = search.lower()
        rows = [r for r in rows if s in (r.get("strategy_name") or "").lower() or s in (r.get("summary") or "").lower() or s in (r.get("entry_rules") or "").lower() or s in (r.get("exit_rules") or "").lower()]
    if max_score is not None:
        rows = [r for r in rows if float(r.get("ai_score") or 0) <= max_score]
    if has_entry_rules is True:
        rows = [r for r in rows if (r.get("entry_rules") or "").strip()]
    if has_entry_rules is False:
        rows = [r for r in rows if not (r.get("entry_rules") or "").strip()]
    if has_exit_rules is True:
        rows = [r for r in rows if (r.get("exit_rules") or "").strip()]
    if has_exit_rules is False:
        rows = [r for r in rows if not (r.get("exit_rules") or "").strip()]
    reverse = str(sort_dir).lower() != "asc"
    key_map = {
        "ai_score": lambda r: r.get("ai_score") or 0,
        "created_at": lambda r: r.get("created_at") or "",
        "strategy_name": lambda r: r.get("strategy_name") or "",
        "timeframe": lambda r: r.get("timeframe") or "",
        "status": lambda r: r.get("status") or "",
        "category": lambda r: r.get("category") or "",
        "upvotes": lambda r: r.get("upvotes") or 0,
    }
    rows.sort(key=key_map.get(sort_by, key_map["ai_score"]), reverse=reverse)
    total = len(rows)
    offset = (page - 1) * page_size
    page_rows = rows[offset:offset + page_size]
    return {"strategies": page_rows, "total": total, "page": page, "page_size": page_size, "total_pages": max(1, (total + page_size - 1) // page_size)}


def get_filtered_strategies(
    min_score: int = 0,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Backward-compatible non-paginated accessor.
    """
    res = get_filtered_strategies_paginated(
        page=1,
        page_size=limit,
        min_score=min_score,
        status=status,
        sort_by="ai_score",
        sort_dir="desc",
    )
    return res["strategies"]


def approve_actionable_strategy(strategy_id: int, approved: bool = True) -> dict:
    """Approve or reject a single actionable strategy."""
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    status = "approved" if approved else "rejected"
    ok = storage.update_strategy_pipeline(
        strategy_id,
        status=status,
        approval_status=status,
        execution_status="idle",
        fix_category="none" if approved else "needs_fix",
        last_error=None,
    )
    if not ok:
        raise ValueError(f"Strategy not found: {strategy_id}")
    return {"strategy_id": strategy_id, "status": status}


def approve_actionable_bulk(limit: int = 10, min_score: float = 0) -> dict:
    """Approve first N actionable strategies by score."""
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    rows = storage.get_actionable_strategies(status="pending", limit=limit, min_score=min_score)
    approved_ids = []
    for row in rows:
        strategy_id = int(row["id"])
        if storage.update_strategy_pipeline(
            strategy_id,
            status="approved",
            approval_status="approved",
            execution_status="idle",
            fix_category="none",
            last_error=None,
        ):
            approved_ids.append(strategy_id)
    return {"requested": limit, "approved_count": len(approved_ids), "strategy_ids": approved_ids}


def _resolve_test_symbols(symbols: Optional[list[str]]) -> list[str]:
    if symbols:
        return symbols
    return ["BTCUSDT", "ETHUSDT", "AAPL"]


def _resolve_test_intervals(intervals: Optional[list[str]]) -> list[str]:
    if intervals:
        return intervals
    return ["1h", "4h", "1d"]


def _iter_target_actionable_strategies(
    strategy_ids: Optional[list[int]],
    first_n: int,
    only_approved: bool,
) -> list[dict]:
    from src.scraper.strategy_storage import StrategyStorage

    storage = StrategyStorage()
    if strategy_ids:
        selected = []
        target_set = {int(x) for x in strategy_ids}
        status = "approved" if only_approved else None
        candidates = storage.get_actionable_strategies(status=status, limit=max(len(target_set) * 3, 100))
        for row in candidates:
            if int(row["id"]) in target_set:
                selected.append(row)
        return selected

    status = "approved" if only_approved else None
    return storage.get_actionable_strategies(status=status, limit=first_n)


def _convert_and_test_single_strategy(
    strategy_row: dict,
    symbols: list[str],
    intervals: list[str],
    n_bars: int,
) -> dict:
    from src.scraper.strategy_storage import StrategyStorage
    from src.scraper.code_generator import StrategyCodeGenerator
    from src.backtest.engine import BacktestEngine

    storage = StrategyStorage()
    strategy_id = int(strategy_row["id"])
    storage.update_strategy_pipeline(
        strategy_id,
        execution_status="code_generating",
        fix_category="none",
        last_error=None,
        last_model="rule-template-v1",
    )

    generator = StrategyCodeGenerator()
    gen = generator.generate_with_validation(strategy_row, strategy_row.get("post_url", ""))
    if not gen["valid"] or not gen["code"]:
        storage.update_strategy_pipeline(
            strategy_id,
            execution_status="failed",
            fix_category="needs_fix",
            status="needs_fix",
            last_error=gen.get("error") or "CODE_ERROR",
            tested=False,
            test_results={"stage": "code_generation", "error": gen.get("error")},
        )
        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy_row.get("strategy_name"),
            "status": "needs_fix",
            "reason": "CODE_ERROR",
            "tests": [],
        }

    storage.update_strategy_pipeline(
        strategy_id,
        python_code=gen["code"],
        converted_at=True,
        execution_status="code_ready",
    )

    tests = []
    needs_fix = False
    first_error = None

    try:
        strategy_cls = _find_generated_strategy_class(gen["code"])
    except Exception as e:
        err = f"CODE_ERROR: {e}"
        storage.update_strategy_pipeline(
            strategy_id,
            execution_status="failed",
            fix_category="needs_fix",
            status="needs_fix",
            last_error=err,
            tested=False,
            test_results={"stage": "class_load", "error": err},
        )
        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy_row.get("strategy_name"),
            "status": "needs_fix",
            "reason": "CODE_ERROR",
            "tests": [],
        }

    storage.update_strategy_pipeline(
        strategy_id,
        execution_status="auto_backtesting",
    )

    for sym in symbols:
        for tf in intervals:
            engine = BacktestEngine()
            try:
                result = engine.run(
                    strategy=strategy_cls,
                    symbol=sym,
                    source="tradingview",
                    exchange=None,
                    interval=tf,
                    n_bars=n_bars,
                    initial_cash=100_000,
                    commission=0.001,
                    strategy_params=None,
                    instant_execution=True,
                )
                is_fix, reason = _is_needs_fix_result(result)
                if is_fix:
                    needs_fix = True
                    first_error = first_error or reason
                tests.append({
                    "symbol": sym,
                    "interval": tf,
                    "status": "needs_fix" if is_fix else "ok",
                    "reason": reason,
                    "total_return": (result or {}).get("total_return") if isinstance(result, dict) else None,
                    "sharpe_ratio": (result or {}).get("sharpe_ratio") if isinstance(result, dict) else None,
                    "total_trades": (result or {}).get("total_trades") if isinstance(result, dict) else None,
                    "run_id": (result or {}).get("run_id") if isinstance(result, dict) else None,
                })
            except Exception as e:
                needs_fix = True
                first_error = first_error or str(e)
                tests.append({
                    "symbol": sym,
                    "interval": tf,
                    "status": "needs_fix",
                    "reason": "RUNTIME_ERROR",
                    "error_detail": str(e),
                    "total_return": None,
                    "sharpe_ratio": None,
                    "total_trades": None,
                    "run_id": None,
                })

    final_status = "needs_fix" if needs_fix else "ready_to_use"
    storage.update_strategy_pipeline(
        strategy_id,
        status=final_status,
        approval_status=strategy_row.get("approval_status") or "approved",
        execution_status="done" if not needs_fix else "failed",
        fix_category="needs_fix" if needs_fix else "none",
        last_error=first_error if needs_fix else None,
        tested=True,
        tested_at=True,
        test_results={"tests": tests, "summary": {"total": len(tests), "needs_fix": needs_fix}},
    )

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_row.get("strategy_name"),
        "status": final_status,
        "reason": first_error if needs_fix else "OK",
        "tests": tests,
    }


def convert_and_test_actionable(
    strategy_ids: Optional[list[int]] = None,
    first_n: int = 10,
    only_approved: bool = True,
    symbols: Optional[list[str]] = None,
    intervals: Optional[list[str]] = None,
    n_bars: int = 1000,
) -> dict:
    targets = _iter_target_actionable_strategies(strategy_ids, first_n, only_approved)
    test_symbols = _resolve_test_symbols(symbols)
    test_intervals = _resolve_test_intervals(intervals)

    results = []
    for row in targets:
        results.append(
            _convert_and_test_single_strategy(
                strategy_row=row,
                symbols=test_symbols,
                intervals=test_intervals,
                n_bars=n_bars,
            )
        )

    needs_fix = [r for r in results if r["status"] == "needs_fix"]
    ready = [r for r in results if r["status"] == "ready_to_use"]
    return {
        "total": len(results),
        "ready_to_use": len(ready),
        "needs_fix": len(needs_fix),
        "results": results,
    }


def convert_and_test_actionable_stream(
    strategy_ids: Optional[list[int]] = None,
    first_n: int = 10,
    only_approved: bool = True,
    symbols: Optional[list[str]] = None,
    intervals: Optional[list[str]] = None,
    n_bars: int = 1000,
):
    targets = _iter_target_actionable_strategies(strategy_ids, first_n, only_approved)
    test_symbols = _resolve_test_symbols(symbols)
    test_intervals = _resolve_test_intervals(intervals)
    total = len(targets)
    if total == 0:
        yield _json.dumps({"current": 0, "total": 0, "done": True, "ready_to_use": 0, "needs_fix": 0})
        return

    ready_cnt = 0
    fix_cnt = 0
    for idx, row in enumerate(targets, 1):
        out = _convert_and_test_single_strategy(
            strategy_row=row,
            symbols=test_symbols,
            intervals=test_intervals,
            n_bars=n_bars,
        )
        if out["status"] == "ready_to_use":
            ready_cnt += 1
        else:
            fix_cnt += 1
        yield _json.dumps({
            "current": idx,
            "total": total,
            "strategy_id": out["strategy_id"],
            "strategy_name": out["strategy_name"],
            "status": out["status"],
            "reason": out["reason"],
            "done": False,
        })

    yield _json.dumps({
        "current": total,
        "total": total,
        "done": True,
        "ready_to_use": ready_cnt,
        "needs_fix": fix_cnt,
    })


def get_pipeline_reports(limit: int = 100) -> list[dict]:
    """List pipeline runs for UI (newest first)."""
    history_path = ENGINE_ROOT / "reports" / "pipeline_runs_history.jsonl"
    if not history_path.exists():
        return []

    rows = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = _json.loads(line)
            sel = r.get("selected_strategy") or {}
            bs = r.get("backtest_summary") or {}
            rows.append({
                "timestamp": r.get("timestamp"),
                "subreddit": r.get("subreddit"),
                "ideas_count": r.get("ideas_count"),
                "decision": r.get("execution_decision"),
                "fix_category": r.get("fix_category"),
                "strategy_name": sel.get("strategy_name"),
                "backtest_mode": sel.get("backtest_mode"),
                "avg_sharpe": bs.get("avg_sharpe"),
                "avg_return": bs.get("avg_return"),
                "report_file": "reports/pipeline_run_report.json",
            })
        except Exception:
            continue

    rows = list(reversed(rows))
    return rows[:limit]
