from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml


@dataclass
class TelegramNotifier:
    bot_token: str | None = None
    chat_id: str | None = None
    timeout: int = 20

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    @classmethod
    def from_secrets(cls, secrets_path: str = "config/secrets.yaml") -> "TelegramNotifier":
        p = Path(secrets_path)
        if not p.exists():
            return cls()
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        tg = cfg.get("telegram", {}) if isinstance(cfg, dict) else {}
        return cls(
            bot_token=tg.get("bot_token"),
            chat_id=str(tg.get("chat_id")) if tg.get("chat_id") is not None else None,
        )

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def send_message(self, text: str, parse_mode: str | None = None) -> dict[str, Any]:
        if not self.is_configured:
            return {"ok": False, "error": "telegram_not_configured"}
        payload = {"chat_id": self.chat_id, "text": text[:4096]}
        if parse_mode:
            payload["parse_mode"] = parse_mode
            payload["disable_web_page_preview"] = True
        r = requests.post(self._url("sendMessage"), json=payload, timeout=self.timeout)
        return r.json()

    def send_document(self, file_path: str | Path, caption: str | None = None) -> dict[str, Any]:
        if not self.is_configured:
            return {"ok": False, "error": "telegram_not_configured"}
        path = Path(file_path)
        with path.open("rb") as f:
            r = requests.post(
                self._url("sendDocument"),
                data={"chat_id": self.chat_id, "caption": (caption or "")[:1024]},
                files={"document": f},
                timeout=self.timeout,
            )
        return r.json()


def _icon(decision: str) -> str:
    return "🟢" if decision == "READY_TO_USE" else "🔴"


def build_pipeline_summary_text(report: dict[str, Any]) -> str:
    sel = report.get("selected_strategy") or {}
    s = report.get("backtest_summary") or {}

    header = [
        "📌 <b>Opus Pipeline Run</b>",
        f"Subreddit: <b>r/{report.get('subreddit')}</b>",
        f"Karar: {_icon(report.get('execution_decision'))} <b>{report.get('execution_decision')}</b> ({report.get('fix_category')})",
        f"Strateji: <b>{sel.get('strategy_name') or '-'}</b>",
        f"Kod Modeli: <b>{report.get('code_model_used') or '-'}</b>",
        f"Backtest: {s.get('success_count',0)}/{s.get('total_tests',0)} | Avg Sharpe: {s.get('avg_sharpe')} | Avg Return: {s.get('avg_return')}",
    ]

    actionable = []
    if sel.get("strategy_name"):
        actionable.append("")
        actionable.append("<b>Actionable Özet</b>")
        # rules from analysis
        entry = exit_ = "-"
        for a in report.get("analysis", []):
            if a.get("strategy_name") == sel.get("strategy_name"):
                entry = (a.get("entry_rules") or "-")[:180]
                exit_ = (a.get("exit_rules") or "-")[:180]
                break
        actionable.append(f"• Entry: {entry}")
        actionable.append(f"• Exit: {exit_}")

    rows = [r for r in (report.get("backtest_results") or []) if not r.get("error")]
    rows = sorted(rows, key=lambda x: (x.get("sharpe_ratio") or -999), reverse=True)[:5]

    table = []
    if rows:
        table.append("")
        table.append("<b>Top Backtest Sonuçları</b>")
        table.append("<pre>SYM/TF      RET%   SHRP   PF   TRD</pre>")
        for r in rows:
            symtf = f"{r.get('symbol')}@{r.get('timeframe')}"
            line = f"{symtf[:10]:10} {r.get('total_return',0):>6.2f} {r.get('sharpe_ratio',0):>6.2f} {r.get('profit_factor',0):>4.2f} {int(r.get('total_trades',0)):>4}"
            table.append(f"<pre>{line}</pre>")

    return "\n".join(header + actionable + table)


def build_multi_run_table_text(batch_report: dict[str, Any]) -> str:
    runs = batch_report.get("runs", [])
    ready = sum(1 for r in runs if r.get("execution_decision") == "READY_TO_USE")
    needs = len(runs) - ready

    lines = [
        "📊 <b>Opus Multi-Subreddit Rapor</b>",
        f"Run: <b>{len(runs)}</b> | READY: <b>{ready}</b> | NEEDS_FIX: <b>{needs}</b>",
        "",
        "<pre>SUBREDDIT      DECISION      STRATEGY               SHARPE</pre>",
    ]
    for r in runs:
        sub = (r.get("subreddit") or "-")[:13]
        dec = (r.get("execution_decision") or "-")[:12]
        strat = ((r.get("selected_strategy") or {}).get("strategy_name") or "-")[:22]
        sh = (r.get("backtest_summary") or {}).get("avg_sharpe")
        shs = "-" if sh is None else f"{float(sh):.2f}"
        lines.append(f"<pre>{sub:13} {dec:12} {strat:22} {shs:>6}</pre>")
    return "\n".join(lines)


def build_compact_digest_text(report: dict[str, Any], total_scan_target: int = 15) -> str:
    """
    Requested compact format:
    1) Toplam tarama
    2) Kategori adetleri
    3) Actionable stratejiler + backtest özeti
    Supports both single-run and multi-run payloads.
    """
    runs = report.get("runs")
    if not isinstance(runs, list):
        runs = [report]

    # Aggregate category counts from analysis rows
    cat_counts: dict[str, int] = {}
    actionable_rows: list[dict[str, Any]] = []

    for r in runs:
        analysis = r.get("analysis") or []
        for row in analysis:
            cat = str(row.get("category") or "UNKNOWN")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            if cat == "ACTIONABLE_STRATEGY":
                actionable_rows.append({"run": r, "row": row})

    lines = [
        "📌 <b>Opus Kısa Rapor</b>",
        f"Toplam Tarama: <b>{total_scan_target}</b> post",
        "",
        "<b>Kategori Dağılımı</b>",
    ]

    for k in ["ACTIONABLE_STRATEGY", "METHODOLOGY", "INSIGHT", "NOISE", "SKIP"]:
        lines.append(f"• {k}: <b>{cat_counts.get(k, 0)}</b>")

    lines.append("")
    lines.append("<b>Actionable Stratejiler</b>")

    if not actionable_rows:
        lines.append("• Actionable strateji bulunamadı.")
        return "\n".join(lines)

    for item in actionable_rows[:5]:
        r = item["run"]
        row = item["row"]
        sel_name = row.get("strategy_name") or "-"

        bt = r.get("backtest_summary") or {}
        lines.append(f"• <b>{sel_name}</b>")
        lines.append(f"  - Entry: {(row.get('entry_rules') or '-')[:140]}")
        lines.append(f"  - Exit: {(row.get('exit_rules') or '-')[:140]}")
        lines.append(
            f"  - Backtest: tests={bt.get('success_count',0)}/{bt.get('total_tests',0)}, "
            f"avg_sharpe={bt.get('avg_sharpe')}, avg_return={bt.get('avg_return')}, "
            f"best={bt.get('best_combo')}"
        )
        lines.append(
            f"  - Karar: {_icon(r.get('execution_decision'))} {r.get('execution_decision')} ({r.get('fix_category')})"
        )

    return "\n".join(lines)


def build_actionable_table_text(report: dict[str, Any], total_scan_target: int = 15) -> str:
    """
    Visual, table-heavy Telegram message:
    - Total scan + category counts
    - For actionable strategies: Entry/Exit rules
    - Backtest table: Pair, TF, Return, DD, Sharpe, PF, Trades
    """
    runs = report.get("runs")
    if not isinstance(runs, list):
        runs = [report]

    cat_counts: dict[str, int] = {}
    actionable_items: list[dict[str, Any]] = []

    for r in runs:
        analysis = r.get("analysis") or []
        for row in analysis:
            cat = str(row.get("category") or "UNKNOWN")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            if cat == "ACTIONABLE_STRATEGY":
                actionable_items.append({"run": r, "row": row})

    ts = report.get("timestamp")
    ts_text = ts or datetime.utcnow().isoformat() + "Z"

    lines = [
        "📊 <b>Opus Actionable Rapor</b>",
        f"Tarih/Saat: <b>{ts_text}</b>",
        f"Toplam Tarama: <b>{total_scan_target}</b> post",
        "",
        "<b>Kategori Adetleri</b>",
        f"• ACTIONABLE: <b>{cat_counts.get('ACTIONABLE_STRATEGY',0)}</b>",
        f"• METHODOLOGY: <b>{cat_counts.get('METHODOLOGY',0)}</b>",
        f"• INSIGHT: <b>{cat_counts.get('INSIGHT',0)}</b>",
        f"• NOISE: <b>{cat_counts.get('NOISE',0)}</b>",
        f"• SKIP: <b>{cat_counts.get('SKIP',0)}</b>",
        "",
    ]

    if not actionable_items:
        lines.append("⚠️ Actionable strateji bulunamadı.")
        return "\n".join(lines)

    for idx, item in enumerate(actionable_items[:5], 1):
        run = item["run"]
        row = item["row"]
        strat = row.get("strategy_name") or f"Actionable-{idx}"
        entry = (row.get("entry_rules") or "-").replace("\n", " ")[:260]
        exit_ = (row.get("exit_rules") or "-").replace("\n", " ")[:260]

        lines.append(f"🧠 <b>{strat}</b>")
        lines.append(f"Rule[Entry]: <code>{entry}</code>")
        lines.append(f"Rule[Exit]: <code>{exit_}</code>")
        lines.append("<pre>PAIR/TF      RET%    DD%   SHRP    PF  TRD</pre>")

        bt_rows = run.get("backtest_results") or []
        ok_rows = [r for r in bt_rows if not r.get("error")]
        ok_rows = sorted(ok_rows, key=lambda x: (x.get("sharpe_ratio") or -999), reverse=True)[:6]
        if not ok_rows:
            lines.append("<pre>- no backtest rows -</pre>")
        else:
            for i, r in enumerate(ok_rows):
                pair_tf = f"{r.get('symbol','-')}@{r.get('timeframe','-')}"[:12]
                ret = float(r.get("total_return") or 0.0)
                dd = float(r.get("max_drawdown_pct") or 0.0)
                sh = float(r.get("sharpe_ratio") or 0.0)
                pf = float(r.get("profit_factor") or 0.0)
                trd = int(r.get("total_trades") or 0)
                prefix = "🟢" if i == 0 else "  "
                lines.append(f"{prefix}<pre>{pair_tf:12} {ret:>6.2f} {dd:>6.2f} {sh:>6.2f} {pf:>5.2f} {trd:>4}</pre>")

        lines.append(
            f"Karar: {_icon(run.get('execution_decision'))} <b>{run.get('execution_decision')}</b> ({run.get('fix_category')})"
        )
        lines.append("")

    return "\n".join(lines[:3900])  # Telegram safety


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
