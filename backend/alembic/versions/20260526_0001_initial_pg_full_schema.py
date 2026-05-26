"""initial_pg_full_schema

Revision ID: 20260526_0001
Revises: 
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260526_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "ohlcv",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text()),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Float()),
        sa.Column("high", sa.Float()),
        sa.Column("low", sa.Float()),
        sa.Column("close", sa.Float()),
        sa.Column("volume", sa.Float()),
        sa.UniqueConstraint("symbol", "exchange", "timeframe", "timestamp", name="uq_ohlcv_key"),
    )
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text(), unique=True),
        sa.Column("strategy_name", sa.Text()),
        sa.Column("symbol", sa.Text()),
        sa.Column("timeframe", sa.Text()),
        sa.Column("start_date", sa.Text()),
        sa.Column("end_date", sa.Text()),
        sa.Column("initial_cash", sa.Float()),
        sa.Column("final_value", sa.Float()),
        sa.Column("total_return", sa.Float()),
        sa.Column("sharpe_ratio", sa.Float()),
        sa.Column("sortino_ratio", sa.Float()),
        sa.Column("calmar_ratio", sa.Float()),
        sa.Column("max_drawdown", sa.Float()),
        sa.Column("avg_drawdown", sa.Float()),
        sa.Column("win_rate", sa.Float()),
        sa.Column("total_trades", sa.Integer()),
        sa.Column("won_trades", sa.Integer()),
        sa.Column("lost_trades", sa.Integer()),
        sa.Column("profit_factor", sa.Float()),
        sa.Column("avg_win", sa.Float()),
        sa.Column("avg_loss", sa.Float()),
        sa.Column("avg_trade", sa.Float()),
        sa.Column("sqn", sa.Float()),
        sa.Column("buy_hold_return", sa.Float()),
        sa.Column("parameters", sa.JSON()),
        sa.Column("equity_curve_json", sa.JSON()),
        sa.Column("drawdown_curve_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("backtest_results.run_id", ondelete="CASCADE")),
        sa.Column("trade_num", sa.Integer()),
        sa.Column("direction", sa.Text()),
        sa.Column("entry_time", sa.Text()),
        sa.Column("entry_price", sa.Float()),
        sa.Column("exit_time", sa.Text()),
        sa.Column("exit_price", sa.Float()),
        sa.Column("size", sa.Float()),
        sa.Column("pnl", sa.Float()),
        sa.Column("pnl_pct", sa.Float()),
    )
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text(), unique=True),
        sa.Column("strategy_name", sa.Text()),
        sa.Column("symbol", sa.Text()),
        sa.Column("exchange", sa.Text()),
        sa.Column("timeframe", sa.Text()),
        sa.Column("n_bars", sa.Integer()),
        sa.Column("metric", sa.Text()),
        sa.Column("trade_direction", sa.Text()),
        sa.Column("param_grid", sa.JSON()),
        sa.Column("total_combinations", sa.Integer()),
        sa.Column("best_params", sa.JSON()),
        sa.Column("best_metric_value", sa.Float()),
        sa.Column("best_return", sa.Float()),
        sa.Column("best_sharpe", sa.Float()),
        sa.Column("best_win_rate", sa.Float()),
        sa.Column("all_results_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "raw_posts",
        sa.Column("hash_id", sa.Text(), primary_key=True),
        sa.Column("reddit_id", sa.Text()),
        sa.Column("subreddit", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("url", sa.Text(), unique=True),
        sa.Column("score", sa.Integer(), server_default="0"),
        sa.Column("comments", sa.Integer(), server_default="0"),
        sa.Column("author", sa.Text()),
        sa.Column("post_created_at", sa.DateTime()),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ai_processed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("stage1_category", sa.Text()),
        sa.Column("stage1_processed_at", sa.DateTime()),
    )

    op.create_table(
        "filtered_strategies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("raw_hash_id", sa.Text(), sa.ForeignKey("raw_posts.hash_id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("strategy_name", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("entry_rules", sa.Text()),
        sa.Column("exit_rules", sa.Text()),
        sa.Column("indicators", sa.JSON()),
        sa.Column("tp_pct", sa.Float()),
        sa.Column("sl_pct", sa.Float()),
        sa.Column("timeframe", sa.Text()),
        sa.Column("markets", sa.JSON()),
        sa.Column("ai_score", sa.Float(), server_default="0"),
        sa.Column("ai_notes", sa.Text()),
        sa.Column("rule_quality", sa.Text(), server_default="weak"),
        sa.Column("tested", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("test_results", sa.JSON()),
        sa.Column("python_code", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending"),
        sa.Column("approval_status", sa.Text(), server_default="pending"),
        sa.Column("execution_status", sa.Text(), server_default="idle"),
        sa.Column("fix_category", sa.Text(), server_default="none"),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_model", sa.Text()),
        sa.Column("converted_at", sa.DateTime()),
        sa.Column("tested_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_check_constraint("ck_filtered_approval_status", "filtered_strategies", "approval_status in ('pending','approved','rejected')")
    op.create_check_constraint("ck_filtered_execution_status", "filtered_strategies", "execution_status in ('idle','code_generating','code_ready','auto_backtesting','done','failed')")
    op.create_check_constraint("ck_filtered_fix_category", "filtered_strategies", "fix_category in ('none','needs_fix','DATA_NULL','CODE_ERROR','RUNTIME_ERROR','NO_TRADES')")

    op.create_table(
        "insights",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("raw_hash_id", sa.Text(), sa.ForeignKey("raw_posts.hash_id", ondelete="CASCADE")),
        sa.Column("title", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("sentiment", sa.Text()),
        sa.Column("confidence", sa.Text()),
        sa.Column("key_points", sa.JSON()),
        sa.Column("actionable_takeaways", sa.JSON()),
        sa.Column("source_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "github_raw_strategies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("hash_id", sa.Text(), unique=True),
        sa.Column("repo_full_name", sa.Text()),
        sa.Column("repo_stars", sa.Integer(), server_default="0"),
        sa.Column("repo_url", sa.Text()),
        sa.Column("repo_description", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("file_name", sa.Text()),
        sa.Column("file_url", sa.Text()),
        sa.Column("file_content", sa.Text()),
        sa.Column("language", sa.Text()),
        sa.Column("collected_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ai_processed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("ai_category", sa.Text()),
        sa.Column("ai_score", sa.Integer(), server_default="0"),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending"),
    )

    op.create_table(
        "api_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("stage", sa.Text()),
        sa.Column("input_tokens", sa.Integer(), server_default="0"),
        sa.Column("output_tokens", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Float(), server_default="0"),
    )

    op.create_index("ix_raw_posts_hash_ai_created", "raw_posts", ["hash_id", "ai_processed", "post_created_at"])
    op.create_index("ix_filtered_strategies_lookup", "filtered_strategies", ["raw_hash_id", "category", "approval_status", "execution_status", "ai_score"])
    op.create_index("ix_ohlcv_composite", "ohlcv", ["symbol", "exchange", "timeframe", "timestamp"])
    op.create_index("ix_backtest_results_lookup", "backtest_results", ["run_id", "strategy_name", "symbol", "timeframe"])
    op.create_index("ix_trades_run_window", "trades", ["run_id", "entry_time", "exit_time"])


def downgrade() -> None:
    op.drop_index("ix_trades_run_window", table_name="trades")
    op.drop_index("ix_backtest_results_lookup", table_name="backtest_results")
    op.drop_index("ix_ohlcv_composite", table_name="ohlcv")
    op.drop_index("ix_filtered_strategies_lookup", table_name="filtered_strategies")
    op.drop_index("ix_raw_posts_hash_ai_created", table_name="raw_posts")
    op.drop_table("api_usage")
    op.drop_table("github_raw_strategies")
    op.drop_table("insights")
    op.drop_table("filtered_strategies")
    op.drop_table("raw_posts")
    op.drop_table("optimization_runs")
    op.drop_table("trades")
    op.drop_table("backtest_results")
    op.drop_table("ohlcv")
