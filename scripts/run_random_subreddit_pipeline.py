import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services import backtest_service
from src.scraper.ai_extractor import SmartExtractor
from src.scraper.glm_strategy_coder import GLMStrategyCoder
from src.scraper.reddit_collector import RedditCollector
from src.utils.telegram_notifier import TelegramNotifier, build_pipeline_summary_text

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "AAPL"]
DEFAULT_TIMEFRAMES = ["1h", "4h", "1d"]


def _parse_csv(value: str | None, defaults: list[str]) -> list[str]:
    if not value:
        return defaults
    items = [x.strip() for x in value.split(",") if x.strip()]
    normalized = []
    for item in items:
        if item.lower() == "1":
            normalized.append("1d")
        else:
            normalized.append(item)
    return normalized or defaults


def _is_options_like(strategy_row: dict[str, Any]) -> tuple[bool, str | None]:
    text = " ".join(
        [
            str(strategy_row.get("strategy_name", "")),
            str(strategy_row.get("title", "")),
            str(strategy_row.get("entry_rules", "")),
            str(strategy_row.get("exit_rules", "")),
        ]
    ).lower()
    keywords = ["option", "iron condor", "straddle", "strangle", "delta", "dte", "put", "call"]
    if any(k in text for k in keywords):
        return True, "options strategy detected; using OHLCV proxy backtest"
    return False, None


def _resolve_proxy_strategy_name(strategy_row: dict[str, Any]) -> str:
    indicators = strategy_row.get("indicators") or []
    names = {str(i.get("name", "")).lower() for i in indicators if isinstance(i, dict)}
    rules = f"{strategy_row.get('entry_rules','')} {strategy_row.get('exit_rules','')}".lower()

    if "supertrend" in names:
        return "supertrend"
    if "rsi" in names or "mean reversion" in rules:
        return "rsi"
    if "sma" in names or "ema" in names or "crossover" in rules:
        return "sma"
    if any(k in rules for k in ["market structure", "order block", "fvg", "liquidity"]):
        return "smc"
    return "sma"


def _sanitize_metric(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _run_backtest_matrix(
    strategy_name: str,
    symbols: list[str],
    timeframes: list[str],
    source: str,
    n_bars: int,
    initial_cash: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        multi = backtest_service.run_multi_backtest(
            strategy_name=strategy_name,
            symbols=[symbol],
            source=source,
            intervals=timeframes,
            n_bars=n_bars,
            initial_cash=initial_cash,
            strategy_params=None,
        )
        for r in multi:
            rows.append(
                {
                    "symbol": r.get("symbol", symbol),
                    "timeframe": r.get("interval"),
                    "error": r.get("error"),
                    "total_return": _sanitize_metric(r.get("total_return")),
                    "sharpe_ratio": _sanitize_metric(r.get("sharpe_ratio")),
                    "max_drawdown_pct": _sanitize_metric(r.get("max_drawdown_pct")),
                    "win_rate": _sanitize_metric(r.get("win_rate")),
                    "profit_factor": _sanitize_metric(r.get("profit_factor")),
                    "total_trades": int(r.get("total_trades", 0) or 0),
                    "final_value": _sanitize_metric(r.get("final_value")),
                    "run_id": r.get("run_id"),
                }
            )
    return rows


def _summarize_backtests(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    ok_rows = [r for r in rows if not r.get("error")]
    success_count = len(ok_rows)
    error_count = total - success_count

    by_sharpe = [r for r in ok_rows if r.get("sharpe_ratio") is not None]
    best = max(by_sharpe, key=lambda x: x.get("sharpe_ratio", -999), default=None)
    worst = min(by_sharpe, key=lambda x: x.get("sharpe_ratio", 999), default=None)

    avg_sharpe = None
    avg_return = None
    if ok_rows:
        sharpe_vals = [r["sharpe_ratio"] for r in ok_rows if r.get("sharpe_ratio") is not None]
        return_vals = [r["total_return"] for r in ok_rows if r.get("total_return") is not None]
        avg_sharpe = round(sum(sharpe_vals) / len(sharpe_vals), 4) if sharpe_vals else None
        avg_return = round(sum(return_vals) / len(return_vals), 4) if return_vals else None

    return {
        "total_tests": total,
        "success_count": success_count,
        "error_count": error_count,
        "avg_sharpe": avg_sharpe,
        "avg_return": avg_return,
        "best_combo": None if not best else f"{best['symbol']}@{best['timeframe']}",
        "worst_combo": None if not worst else f"{worst['symbol']}@{worst['timeframe']}",
    }


def _decide_execution(result: dict[str, Any]) -> tuple[str, str]:
    if not result.get("code_valid", False):
        return "NEEDS_FIX", "CODE_ERROR"

    rows = result.get("backtest_results") or []
    ok_rows = [r for r in rows if not r.get("error")]
    if not ok_rows:
        return "NEEDS_FIX", "DATA_NULL"

    no_trade_ratio = sum(1 for r in ok_rows if int(r.get("total_trades", 0) or 0) == 0) / max(len(ok_rows), 1)
    metric_ok = any(
        (r.get("total_trades", 0) >= 5 and (r.get("sharpe_ratio") or 0) > 0 and (r.get("profit_factor") or 0) >= 1.05)
        for r in ok_rows
    )

    if no_trade_ratio >= 0.7:
        return "NEEDS_FIX", "NO_TRADES"
    if metric_ok:
        return "READY_TO_USE", "none"
    return "NEEDS_FIX", "RUNTIME_ERROR"


def _write_markdown_report(out_dir: Path, result: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Pipeline Run Report v2")
    lines.append(f"- Subreddit: r/{result.get('subreddit')}")
    lines.append(f"- Ideas: {result.get('ideas_count')}")
    lines.append(f"- Decision: {result.get('execution_decision')}")
    lines.append(f"- Fix Category: {result.get('fix_category')}")

    sel = result.get("selected_strategy") or {}
    if sel:
        lines.append(f"- Selected Strategy: {sel.get('strategy_name')} (score={sel.get('quality_score')})")
        lines.append(f"- Backtest Mode: {sel.get('backtest_mode')}")

    summary = result.get("backtest_summary") or {}
    lines.append("\n## Backtest Summary")
    for k in ["total_tests", "success_count", "error_count", "avg_sharpe", "avg_return", "best_combo", "worst_combo"]:
        lines.append(f"- {k}: {summary.get(k)}")

    lines.append("\n## Backtest Rows")
    for r in result.get("backtest_results", []):
        lines.append(
            f"- {r.get('symbol')}@{r.get('timeframe')} | ret={r.get('total_return')} | sharpe={r.get('sharpe_ratio')} | pf={r.get('profit_factor')} | trades={r.get('total_trades')} | err={r.get('error')}"
        )

    (out_dir / "pipeline_run_report.md").write_text("\n".join(lines), encoding="utf-8")


def _append_history(result: dict[str, Any], out_dir: Path) -> None:
    history_file = out_dir / "pipeline_runs_history.jsonl"
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def run_pipeline(
    max_attempts: int = 5,
    ideas_target: int = 10,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    n_bars: int = 600,
    initial_cash: float = 100_000,
    source: str = "tradingview",
    send_telegram: bool = False,
) -> dict:
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)

    symbols = symbols or DEFAULT_SYMBOLS
    timeframes = timeframes or DEFAULT_TIMEFRAMES

    secrets = yaml.safe_load(Path("config/secrets.yaml").read_text(encoding="utf-8"))
    api_key = secrets.get("openai", {}).get("api_key")
    extractor = SmartExtractor(api_key=api_key)

    subs = RedditCollector.DEFAULT_SUBREDDITS.copy()
    random.shuffle(subs)

    final_result = None

    for attempt, sub in enumerate(subs[:max_attempts], 1):
        collector = RedditCollector(rate_limit_seconds=0.6)

        raw_posts = []
        for sort in ["hot", "new", "top"]:
            posts, _ = collector._fetch_subreddit_page(subreddit=sub, sort=sort, limit=25)
            raw_posts.extend(posts)

        seen = set()
        ideas = []
        for post in raw_posts:
            url = post.get("url", "")
            if url and url not in seen:
                seen.add(url)
                ideas.append(post)
            if len(ideas) >= ideas_target:
                break

        result: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt": attempt,
            "subreddit": sub,
            "ideas_count": len(ideas),
            "ideas": [],
            "analysis": [],
            "selected_strategy": None,
            "generated_file": None,
            "errors": [],
            "backtest_config": {
                "symbols": symbols,
                "timeframes": timeframes,
                "n_bars": n_bars,
                "initial_cash": initial_cash,
                "source": source,
            },
            "backtest_results": [],
            "backtest_summary": {},
            "execution_decision": "NEEDS_FIX",
            "fix_category": "RUNTIME_ERROR",
        }

        for p in ideas:
            result["ideas"].append(
                {
                    "title": p.get("title", ""),
                    "score": p.get("score", 0),
                    "comments": p.get("num_comments", 0),
                    "url": p.get("url", ""),
                }
            )

        for p in ideas:
            r = extractor.process_post(p, use_prefilter=True, skip_if_analyzed=False)
            row = {
                "title": p.get("title", ""),
                "url": p.get("url", ""),
                "category": r.get("category"),
                "prefilter_band": r.get("prefilter_band"),
                "final_priority_score": r.get("final_priority_score"),
                "rule_quality": r.get("rule_quality"),
                "skipped_reason": r.get("skipped_reason"),
            }
            if r.get("strategy"):
                st = r["strategy"]
                row.update(
                    {
                        "strategy_name": st.get("strategy_name"),
                        "quality_score": st.get("quality_score"),
                        "entry_rules": st.get("entry_rules"),
                        "exit_rules": st.get("exit_rules"),
                        "indicators": st.get("indicators"),
                    }
                )
            result["analysis"].append(row)

        candidates = [a for a in result["analysis"] if a.get("strategy_name") and isinstance(a.get("quality_score"), (int, float))]
        candidates.sort(key=lambda x: x.get("quality_score", 0), reverse=True)

        if not candidates:
            final_result = result
            continue

        best = candidates[0]
        is_options, proxy_reason = _is_options_like(best)
        backtest_mode = "proxy" if is_options else "native"
        proxy_engine_strategy = _resolve_proxy_strategy_name(best)

        result["selected_strategy"] = {
            "strategy_name": best.get("strategy_name"),
            "quality_score": best.get("quality_score"),
            "source_url": best.get("url"),
            "title": best.get("title"),
            "backtest_mode": backtest_mode,
            "proxy_reason": proxy_reason,
            "proxy_engine_strategy": proxy_engine_strategy,
        }

        strategy_data = {
            "strategy_name": best.get("strategy_name"),
            "summary": f"Extracted from r/{sub}: {best.get('title', '')}",
            "entry_rules": best.get("entry_rules") or "",
            "exit_rules": best.get("exit_rules") or "",
            "indicators": best.get("indicators") or [],
            "tp_pct": 3.0,
            "sl_pct": 1.5,
            "ai_notes": "Auto-generated pipeline output",
        }

        generated = GLMStrategyCoder().generate_with_validation(strategy_data, best.get("url", ""))

        safe_name = "".join(ch if ch.isalnum() else "_" for ch in best.get("strategy_name", "strategy")).strip("_").lower()
        output_file = out_dir / f"pipeline_generated_{safe_name}.py"
        output_file.write_text(generated.code, encoding="utf-8")

        result["generated_file"] = str(output_file)
        result["code_valid"] = generated.valid
        result["code_error"] = generated.error
        result["code_model_used"] = generated.model_used
        result["code_tokens_used"] = generated.tokens_used
        result["code_cost_usd"] = round(generated.cost_usd, 6)

        try:
            result["backtest_results"] = _run_backtest_matrix(
                strategy_name=proxy_engine_strategy,
                symbols=symbols,
                timeframes=timeframes,
                source=source,
                n_bars=n_bars,
                initial_cash=initial_cash,
            )
            result["backtest_summary"] = _summarize_backtests(result["backtest_results"])
        except Exception as e:
            result["errors"].append(f"BACKTEST_ERROR: {e}")

        decision, fix_category = _decide_execution(result)
        result["execution_decision"] = decision
        result["fix_category"] = fix_category

        final_result = result
        break

    if final_result is None:
        final_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "errors": ["No attempts executed"],
            "execution_decision": "NEEDS_FIX",
            "fix_category": "RUNTIME_ERROR",
        }

    report_file = out_dir / "pipeline_run_report.json"
    report_file.write_text(json.dumps(final_result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_report(out_dir, final_result)
    _append_history(final_result, out_dir)

    if send_telegram:
        notifier = TelegramNotifier.from_secrets()
        if notifier.is_configured:
            caption = build_pipeline_summary_text(final_result)
            notifier.send_message(caption)
            notifier.send_document(report_file, caption="pipeline_run_report.json")
        else:
            final_result.setdefault("errors", []).append("Telegram not configured")

    return final_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Random subreddit pipeline v2")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES), help="Comma-separated timeframes")
    parser.add_argument("--n-bars", type=int, default=600)
    parser.add_argument("--initial-cash", type=float, default=100000)
    parser.add_argument("--source", default="tradingview")
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--ideas-target", type=int, default=10)
    parser.add_argument("--telegram", action="store_true", help="Send report to Telegram")
    args = parser.parse_args()

    result = run_pipeline(
        max_attempts=args.max_attempts,
        ideas_target=args.ideas_target,
        symbols=_parse_csv(args.symbols, DEFAULT_SYMBOLS),
        timeframes=_parse_csv(args.timeframes, DEFAULT_TIMEFRAMES),
        n_bars=args.n_bars,
        initial_cash=args.initial_cash,
        source=args.source,
        send_telegram=args.telegram,
    )

    print(f"subreddit=r/{result.get('subreddit')} ideas={result.get('ideas_count')} selected={bool(result.get('selected_strategy'))}")
    print(f"decision={result.get('execution_decision')} fix={result.get('fix_category')}")
    print("report=reports/pipeline_run_report.json")
    if result.get("generated_file"):
        print(f"generated={result['generated_file']}")


if __name__ == "__main__":
    main()

