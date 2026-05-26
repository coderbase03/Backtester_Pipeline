"""SQLite -> PostgreSQL migration (idempotent)."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SQLITE_SCRAPER = DATA_DIR / "scraped_strategies.db"
SQLITE_TRADING = DATA_DIR / "trading.db"
REPORT = ROOT / "reports" / "pg_migration_report.json"

PG_URL = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or "postgresql://opus:opus@localhost:5432/opus_backtrader"

TABLES = {
    "scraper": ["raw_posts", "filtered_strategies", "insights", "github_raw_strategies", "api_usage"],
    "trading": ["ohlcv", "backtest_results", "trades", "optimization_runs"],
}


def sqlite_count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    except Exception:
        return 0


def pg_count(engine, table: str) -> int:
    with engine.connect() as conn:
        try:
            return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
        except Exception:
            return 0


def migrate_table(sqlite_conn: sqlite3.Connection, engine, table: str, pkey: str | None = None) -> dict[str, Any]:
    cur = sqlite_conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    inserted = 0
    errors = []

    if not rows:
        return {"source_count": 0, "inserted": 0, "errors": []}

    col_csv = ", ".join(cols)
    val_csv = ", ".join([f":{c}" for c in cols])

    updates = []
    if pkey and pkey in cols:
        updates = [f"{c}=EXCLUDED.{c}" for c in cols if c != pkey]

    upsert = f"INSERT INTO {table} ({col_csv}) VALUES ({val_csv})"
    if pkey and updates:
        upsert += f" ON CONFLICT ({pkey}) DO UPDATE SET {', '.join(updates)}"

    stmt = text(upsert)

    batch = []
    for row in rows:
        item = {}
        for i, c in enumerate(cols):
            v = row[i]
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            item[c] = v
        batch.append(item)

    for i in range(0, len(batch), 500):
        chunk = batch[i:i+500]
        try:
            with engine.begin() as conn:
                conn.execute(stmt, chunk)
            inserted += len(chunk)
        except Exception as e:
            errors.append(str(e))

    return {"source_count": len(rows), "inserted": inserted, "errors": errors[:20]}


def main():
    started = time.time()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(PG_URL, future=True)

    scraper_conn = sqlite3.connect(str(SQLITE_SCRAPER)) if SQLITE_SCRAPER.exists() else None
    trading_conn = sqlite3.connect(str(SQLITE_TRADING)) if SQLITE_TRADING.exists() else None

    report: dict[str, Any] = {"started_at": started, "pg_url": PG_URL, "tables": {}, "errors": []}

    pkeys = {
        "raw_posts": "hash_id",
        "filtered_strategies": "id",
        "insights": "id",
        "github_raw_strategies": "id",
        "api_usage": "id",
        "ohlcv": "id",
        "backtest_results": "id",
        "trades": "id",
        "optimization_runs": "id",
    }

    if scraper_conn:
        for t in TABLES["scraper"]:
            source_count = sqlite_count(scraper_conn, t)
            result = migrate_table(scraper_conn, engine, t, pkeys.get(t)) if source_count else {"source_count": 0, "inserted": 0, "errors": []}
            target_count = pg_count(engine, t)
            report["tables"][t] = {**result, "target_count": target_count, "diff_count": target_count - source_count}

    if trading_conn:
        for t in TABLES["trading"]:
            source_count = sqlite_count(trading_conn, t)
            result = migrate_table(trading_conn, engine, t, pkeys.get(t)) if source_count else {"source_count": 0, "inserted": 0, "errors": []}
            target_count = pg_count(engine, t)
            report["tables"][t] = {**result, "target_count": target_count, "diff_count": target_count - source_count}

    report["duration_sec"] = round(time.time() - started, 2)
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Migration report written: {REPORT}")


if __name__ == "__main__":
    main()
