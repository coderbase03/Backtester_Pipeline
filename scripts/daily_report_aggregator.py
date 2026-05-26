import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.telegram_notifier import TelegramNotifier


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def _filter_today(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    out = []
    for r in rows:
        ts = r.get("timestamp")
        if not ts:
            continue
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            if d == today:
                out.append(r)
        except Exception:
            continue
    return out


def build_daily_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {"run_count": 0}

    ready = sum(1 for r in runs if r.get("execution_decision") == "READY_TO_USE")
    needs_fix = len(runs) - ready
    strategies = []
    for r in runs:
        s = (r.get("selected_strategy") or {}).get("strategy_name")
        if s:
            strategies.append(s)

    avg_sharpes = [
        (r.get("backtest_summary") or {}).get("avg_sharpe")
        for r in runs
        if (r.get("backtest_summary") or {}).get("avg_sharpe") is not None
    ]
    avg_returns = [
        (r.get("backtest_summary") or {}).get("avg_return")
        for r in runs
        if (r.get("backtest_summary") or {}).get("avg_return") is not None
    ]

    return {
        "run_count": len(runs),
        "ready_count": ready,
        "needs_fix_count": needs_fix,
        "strategies": list(dict.fromkeys(strategies))[:10],
        "avg_sharpe": round(sum(avg_sharpes) / len(avg_sharpes), 4) if avg_sharpes else None,
        "avg_return": round(sum(avg_returns) / len(avg_returns), 4) if avg_returns else None,
    }


def format_daily_text(summary: dict[str, Any]) -> str:
    if summary.get("run_count", 0) == 0:
        return "Opus Daily Report\nBugün run yok."
    return "\n".join(
        [
            "Opus Daily Report",
            f"Run: {summary.get('run_count')}",
            f"READY_TO_USE: {summary.get('ready_count')} | NEEDS_FIX: {summary.get('needs_fix_count')}",
            f"Avg Sharpe: {summary.get('avg_sharpe')} | Avg Return: {summary.get('avg_return')}",
            f"Strategies: {', '.join(summary.get('strategies', []))}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate daily pipeline runs")
    parser.add_argument("--history", default="reports/pipeline_runs_history.jsonl")
    parser.add_argument("--send-telegram", action="store_true")
    args = parser.parse_args()

    history_path = Path(args.history)
    runs = _filter_today(_load_history(history_path))
    summary = build_daily_summary(runs)

    out_path = Path("reports/daily_report_summary.json")
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"daily_runs={summary.get('run_count')}")
    print(f"summary={out_path}")

    if args.send_telegram:
        notifier = TelegramNotifier.from_secrets()
        if notifier.is_configured:
            notifier.send_message(format_daily_text(summary))
            notifier.send_document(out_path, caption="daily_report_summary.json")
            print("telegram_sent=true")
        else:
            print("telegram_sent=false (not configured)")


if __name__ == "__main__":
    main()
