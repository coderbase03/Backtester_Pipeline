import sqlite3

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_prefilter_priority_and_rule_quality():
    from src.scraper.ai_extractor import pre_filter_post

    rich_post = pre_filter_post(
        "Backtested breakout strategy with code",
        (
            "Entry: buy when price breaks 20-day high and ATR confirms. "
            "Exit: take profit at 4% or stop loss at 1.5%. "
            "Backtest Sharpe 1.4, max drawdown 8%, 320 trades. "
            "```python\nif signal: pass\n```"
        ),
    )
    assert rich_post["should_process"] is True
    assert rich_post["final_priority_score"] >= 60
    assert rich_post["rule_quality"] in {"medium", "strong"}

    weak_post = pre_filter_post(
        "Need advice",
        "Hi, beginner here. what should i buy today? thanks",
    )
    assert weak_post["should_process"] is False
    assert weak_post["final_priority_score"] < 30


def test_backtest_history_nan_summary_payload(monkeypatch):
    from app.services import backtest_service

    class _FakeDB:
        def get_backtest_history(self, limit=50):
            return pd.DataFrame(
                [
                    {
                        "run_id": "run_nan_1",
                        "strategy_name": "SMACrossover",
                        "symbol": "BTCUSDT",
                        "sharpe_ratio": float("nan"),
                        "sortino_ratio": float("inf"),
                        "total_return": 12.5,
                        "parameters": '{"fast": 10, "slow": 30}',
                        "equity_curve_json": '[{"datetime":"2026-01-01","value":100000}]',
                        "drawdown_curve_json": '[{"datetime":"2026-01-01","drawdown":0.0}]',
                    }
                ]
            )

        def close(self):
            return None

    monkeypatch.setattr(backtest_service, "_get_db", lambda: _FakeDB())

    response = client.get("/api/backtest/history?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list) and len(body) == 1
    row = body[0]

    assert "equity_curve_json" not in row
    assert "drawdown_curve_json" not in row
    assert row["sharpe_ratio"] is None
    assert row["sortino_ratio"] is None
    assert row["parameters"] == {"fast": 10, "slow": 30}


def test_scraper_posts_and_strategies_filters_smoke(tmp_path, monkeypatch):
    from src.scraper import strategy_storage as storage_module

    db_path = tmp_path / "scraper_filters_smoke.db"
    OriginalStorage = storage_module.StrategyStorage

    class TestStrategyStorage(OriginalStorage):
        def __init__(self, db_path_override=None):
            super().__init__(db_path=str(db_path))

    monkeypatch.setattr(storage_module, "StrategyStorage", TestStrategyStorage)

    storage = storage_module.StrategyStorage()

    hash_actionable = storage.save_raw_post(
        {
            "id": "t3_actionable",
            "subreddit": "algotrading",
            "title": "Breakout system with rules and backtest",
            "selftext": (
                "Entry uses breakout + ATR filter. Exit uses trailing stop and TP/SL. "
                "Backtest sharpe and drawdown metrics included."
            ),
            "url": "https://reddit.com/r/algotrading/comments/actionable_1",
            "score": 85,
            "num_comments": 12,
            "author": "user_a",
            "created_utc": 1704067200,
        }
    )
    storage.mark_stage1_processed(hash_actionable, "ACTIONABLE_STRATEGY")
    storage.save_filtered_strategy(
        hash_actionable,
        {
            "category": "ACTIONABLE_STRATEGY",
            "strategy_name": "Breakout Alpha",
            "summary": "Breakout + volatility filter strategy",
            "entry_rules": "Price breaks 20-bar high with ATR confirmation",
            "exit_rules": "ATR trailing stop or TP hit",
            "indicators": ["ATR", "Donchian"],
            "tp_pct": 4.0,
            "sl_pct": 1.5,
            "timeframe": "1h",
            "markets": ["crypto"],
            "quality_score": 82,
            "ai_notes": "Good clarity",
        },
    )

    hash_noise = storage.save_raw_post(
        {
            "id": "t3_noise",
            "subreddit": "stocks",
            "title": "Beginner question",
            "selftext": "What should I buy today?",
            "url": "https://reddit.com/r/stocks/comments/noise_1",
            "score": 3,
            "num_comments": 2,
            "author": "user_b",
            "created_utc": 1704153600,
        }
    )
    storage.mark_stage1_processed(hash_noise, "NOISE")

    conn = sqlite3.connect(storage.db_path)
    conn.execute(
        "UPDATE filtered_strategies SET status = 'approved' WHERE raw_hash_id = ?",
        (hash_actionable,),
    )
    conn.commit()
    conn.close()

    posts_response = client.get(
        "/api/scraper/posts",
        params={
            "page": 1,
            "page_size": 10,
            "category": "ACTIONABLE_STRATEGY",
            "subreddit": "algotrading",
            "min_post_score": 50,
            "max_post_score": 100,
            "min_ai_score": 70,
            "max_ai_score": 90,
            "has_strategy": True,
            "has_entry_rules": True,
            "has_exit_rules": True,
            "strategy_status": "approved",
            "strategy_category": "ACTIONABLE_STRATEGY",
            "timeframe": "1h",
            "sort_by": "ai_score",
            "sort_dir": "desc",
        },
    )
    assert posts_response.status_code == 200
    posts_body = posts_response.json()
    assert posts_body["total"] == 1
    assert len(posts_body["posts"]) == 1
    assert posts_body["posts"][0]["hash_id"] == hash_actionable
    assert posts_body["posts"][0]["strategy_name"] == "Breakout Alpha"

    strategies_response = client.get(
        "/api/scraper/strategies",
        params={
            "page": 1,
            "page_size": 10,
            "search": "Breakout",
            "category": "ACTIONABLE_STRATEGY",
            "status": "approved",
            "min_score": 70,
            "max_score": 90,
            "has_entry_rules": True,
            "has_exit_rules": True,
            "timeframe": "1h",
            "sort_by": "ai_score",
            "sort_dir": "desc",
        },
    )
    assert strategies_response.status_code == 200
    strategies_body = strategies_response.json()
    assert strategies_body["total"] == 1
    assert strategies_body["page"] == 1
    assert strategies_body["page_size"] == 10
    assert strategies_body["total_pages"] == 1
    assert len(strategies_body["strategies"]) == 1
    assert strategies_body["strategies"][0]["strategy_name"] == "Breakout Alpha"
