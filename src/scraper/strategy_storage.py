from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _pg_url() -> str:
    return os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or "postgresql://opus:opus@localhost:5432/opus_backtrader"


class StrategyStorage:
    """PostgreSQL-backed strategy storage."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path  # compatibility only
        self._sqlite = bool(db_path and str(db_path).endswith(".db"))
        if self._sqlite:
            self._sqlite_path = str(db_path)
            self._init_sqlite_for_tests()
            self.engine = None
            return
        self.engine: Engine = create_engine(_pg_url(), pool_pre_ping=True, future=True)
        self._init_database()

    def _init_sqlite_for_tests(self):
        conn = sqlite3.connect(self._sqlite_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_posts (
                hash_id TEXT PRIMARY KEY,
                reddit_id TEXT,
                subreddit TEXT,
                title TEXT,
                content TEXT,
                url TEXT UNIQUE,
                score INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                author TEXT,
                post_created_at TEXT,
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ai_processed INTEGER DEFAULT 0,
                stage1_category TEXT,
                stage1_processed_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS filtered_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_hash_id TEXT,
                category TEXT NOT NULL,
                strategy_name TEXT,
                summary TEXT,
                entry_rules TEXT,
                exit_rules TEXT,
                indicators TEXT,
                tp_pct REAL,
                sl_pct REAL,
                timeframe TEXT,
                markets TEXT,
                ai_score REAL DEFAULT 0,
                ai_notes TEXT,
                rule_quality TEXT DEFAULT 'weak',
                tested INTEGER DEFAULT 0,
                test_results TEXT,
                python_code TEXT,
                status TEXT DEFAULT 'pending',
                approval_status TEXT DEFAULT 'pending',
                execution_status TEXT DEFAULT 'idle',
                fix_category TEXT DEFAULT 'none',
                last_error TEXT,
                last_model TEXT,
                converted_at TEXT,
                tested_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_hash_id TEXT,
                title TEXT,
                summary TEXT,
                sentiment TEXT,
                confidence TEXT,
                key_points TEXT,
                actionable_takeaways TEXT,
                source_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                stage TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0
            )
            """
        )
        conn.commit()
        conn.close()

    def _init_database(self):
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS raw_posts (
                hash_id TEXT PRIMARY KEY,
                reddit_id TEXT,
                subreddit TEXT,
                title TEXT,
                content TEXT,
                url TEXT UNIQUE,
                score INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                author TEXT,
                post_created_at TIMESTAMP,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ai_processed BOOLEAN DEFAULT FALSE,
                stage1_category TEXT,
                stage1_processed_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS filtered_strategies (
                id BIGSERIAL PRIMARY KEY,
                raw_hash_id TEXT REFERENCES raw_posts(hash_id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                strategy_name TEXT,
                summary TEXT,
                entry_rules TEXT,
                exit_rules TEXT,
                indicators JSONB,
                tp_pct DOUBLE PRECISION,
                sl_pct DOUBLE PRECISION,
                timeframe TEXT,
                markets JSONB,
                ai_score DOUBLE PRECISION DEFAULT 0,
                ai_notes TEXT,
                rule_quality TEXT DEFAULT 'weak',
                tested BOOLEAN DEFAULT FALSE,
                test_results JSONB,
                python_code TEXT,
                status TEXT DEFAULT 'pending',
                approval_status TEXT DEFAULT 'pending',
                execution_status TEXT DEFAULT 'idle',
                fix_category TEXT DEFAULT 'none',
                last_error TEXT,
                last_model TEXT,
                converted_at TIMESTAMP,
                tested_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS insights (
                id BIGSERIAL PRIMARY KEY,
                raw_hash_id TEXT REFERENCES raw_posts(hash_id) ON DELETE CASCADE,
                title TEXT,
                summary TEXT,
                sentiment TEXT,
                confidence TEXT,
                key_points JSONB,
                actionable_takeaways JSONB,
                source_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                id BIGSERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stage TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd DOUBLE PRECISION DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS github_raw_strategies (
                id BIGSERIAL PRIMARY KEY,
                hash_id TEXT UNIQUE,
                repo_full_name TEXT,
                repo_stars INTEGER DEFAULT 0,
                repo_url TEXT,
                repo_description TEXT,
                file_path TEXT,
                file_name TEXT,
                file_url TEXT,
                file_content TEXT,
                language TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ai_processed BOOLEAN DEFAULT FALSE,
                ai_category TEXT,
                ai_score INTEGER DEFAULT 0,
                ai_summary TEXT,
                status TEXT DEFAULT 'pending'
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_raw_posts_hash_ai_created ON raw_posts(hash_id, ai_processed, post_created_at)",
            "CREATE INDEX IF NOT EXISTS ix_filtered_lookup ON filtered_strategies(raw_hash_id, category, approval_status, execution_status, ai_score)",
        ]
        with self.engine.begin() as conn:
            for stmt in ddl:
                conn.execute(text(stmt))

    @staticmethod
    def generate_hash(url: str) -> str:
        return hashlib.sha256((url or "").encode()).hexdigest()[:16]

    def is_duplicate(self, url: str) -> bool:
        h = self.generate_hash(url)
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM raw_posts WHERE hash_id=?", (h,))
            row = cur.fetchone()
            conn.close()
            return row is not None
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT 1 FROM raw_posts WHERE hash_id=:h"), {"h": h}).first()
            return row is not None

    def is_already_analyzed(self, hash_id: str) -> bool:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT ai_processed, stage1_category FROM raw_posts WHERE hash_id=:h"), {"h": hash_id}).first()
            return bool(row and row[0] and row[1] and row[1] != "PROCESSING_ERROR")

    def get_unprocessed_count(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM raw_posts WHERE ai_processed=FALSE")).scalar() or 0)

    def save_raw_post(self, post: Dict) -> str:
        url = post.get("url", "")
        hash_id = self.generate_hash(url)
        created_utc = post.get("created_utc", 0)
        post_created_at = datetime.fromtimestamp(created_utc) if created_utc else None
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO raw_posts (hash_id, reddit_id, subreddit, title, content, url, score, comments, author, post_created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (hash_id, post.get("id", ""), post.get("subreddit", ""), post.get("title", ""), post.get("selftext", ""), url, int(post.get("score", 0) or 0), int(post.get("num_comments", 0) or 0), str(post.get("author", "")), str(post_created_at) if post_created_at else None),
            )
            conn.commit()
            conn.close()
            return hash_id
        stmt = text(
            """
            INSERT INTO raw_posts (hash_id, reddit_id, subreddit, title, content, url, score, comments, author, post_created_at)
            VALUES (:hash_id, :reddit_id, :subreddit, :title, :content, :url, :score, :comments, :author, :post_created_at)
            ON CONFLICT (hash_id) DO NOTHING
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "hash_id": hash_id,
                    "reddit_id": post.get("id", ""),
                    "subreddit": post.get("subreddit", ""),
                    "title": post.get("title", ""),
                    "content": post.get("selftext", ""),
                    "url": url,
                    "score": int(post.get("score", 0) or 0),
                    "comments": int(post.get("num_comments", 0) or 0),
                    "author": str(post.get("author", "")),
                    "post_created_at": post_created_at,
                },
            )
        return hash_id

    def save_raw_posts_batch(self, posts: List[Dict]) -> Tuple[int, int]:
        saved = 0
        duplicates = 0
        for p in posts:
            if self.is_duplicate(p.get("url", "")):
                duplicates += 1
            else:
                self.save_raw_post(p)
                saved += 1
        return saved, duplicates

    def _json_safe(self, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v
        return v

    def get_raw_posts(self, processed: bool = None, limit: int = 100, order_by: str = "collected_at DESC") -> List[Dict]:
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if processed is None:
                cur.execute(f"SELECT * FROM raw_posts ORDER BY {order_by} LIMIT ?", (limit,))
            else:
                cur.execute(f"SELECT * FROM raw_posts WHERE ai_processed=? ORDER BY {order_by} LIMIT ?", (1 if processed else 0, limit))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        q = "SELECT * FROM raw_posts"
        params = {}
        if processed is not None:
            q += " WHERE ai_processed = :processed"
            params["processed"] = processed
        q += f" ORDER BY {order_by} LIMIT :limit"
        params["limit"] = limit
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).mappings().all()
        return [dict(r) for r in rows]

    def get_raw_posts_paginated(self, processed: bool = None, category: str = None, exclude_noise: bool = False, limit: int = 100, offset: int = 0, order_by: str = "collected_at DESC") -> List[Dict]:
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            q = "SELECT * FROM raw_posts WHERE 1=1"
            params: list[Any] = []
            if processed is not None:
                q += " AND ai_processed=?"
                params.append(1 if processed else 0)
            if category:
                q += " AND stage1_category=?"
                params.append(category)
            if exclude_noise:
                q += " AND (stage1_category IS NULL OR stage1_category!='NOISE')"
            q += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cur.execute(q, params)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        q = "SELECT * FROM raw_posts WHERE 1=1"
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if processed is not None:
            q += " AND ai_processed = :processed"
            params["processed"] = processed
        if category:
            q += " AND stage1_category = :category"
            params["category"] = category
        if exclude_noise:
            q += " AND (stage1_category IS NULL OR stage1_category != 'NOISE')"
        q += f" ORDER BY {order_by} LIMIT :limit OFFSET :offset"
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).mappings().all()
        return [dict(r) for r in rows]

    def get_raw_post_count(self, processed: bool = None, category: str = None, exclude_noise: bool = False) -> int:
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            cur = conn.cursor()
            q = "SELECT COUNT(*) FROM raw_posts WHERE 1=1"
            params = []
            if processed is not None:
                q += " AND ai_processed=?"
                params.append(1 if processed else 0)
            if category:
                q += " AND stage1_category=?"
                params.append(category)
            if exclude_noise:
                q += " AND (stage1_category IS NULL OR stage1_category!='NOISE')"
            cur.execute(q, params)
            c = int(cur.fetchone()[0] or 0)
            conn.close()
            return c
        q = "SELECT COUNT(*) FROM raw_posts WHERE 1=1"
        params = {}
        if processed is not None:
            q += " AND ai_processed = :processed"
            params["processed"] = processed
        if category:
            q += " AND stage1_category = :category"
            params["category"] = category
        if exclude_noise:
            q += " AND (stage1_category IS NULL OR stage1_category != 'NOISE')"
        with self.engine.connect() as conn:
            return int(conn.execute(text(q), params).scalar() or 0)

    def get_unprocessed_posts(self, limit: int = 50) -> List[Dict]:
        return self.get_raw_posts(processed=False, limit=limit)

    def mark_stage1_processed(self, hash_id: str, category: str):
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            cur = conn.cursor()
            cur.execute("UPDATE raw_posts SET ai_processed=1, stage1_category=?, stage1_processed_at=CURRENT_TIMESTAMP WHERE hash_id=?", (category, hash_id))
            conn.commit()
            conn.close()
            return
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE raw_posts SET ai_processed=TRUE, stage1_category=:c, stage1_processed_at=CURRENT_TIMESTAMP WHERE hash_id=:h"),
                {"c": category, "h": hash_id},
            )

    def save_filtered_strategy(self, raw_hash_id: str, strategy_data: Dict) -> int:
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO filtered_strategies (raw_hash_id, category, strategy_name, summary, entry_rules, exit_rules, indicators, tp_pct, sl_pct, timeframe, markets, ai_score, ai_notes, rule_quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_hash_id,
                    strategy_data.get("category", "STRATEGY"),
                    strategy_data.get("strategy_name", "Unknown Strategy"),
                    strategy_data.get("summary_tr") or strategy_data.get("summary", ""),
                    strategy_data.get("entry_rules", ""),
                    strategy_data.get("exit_rules", ""),
                    json.dumps(strategy_data.get("indicators", [])),
                    strategy_data.get("tp_pct", 3.0),
                    strategy_data.get("sl_pct", 1.5),
                    strategy_data.get("timeframe", "1d"),
                    json.dumps(strategy_data.get("markets", ["stocks"])),
                    strategy_data.get("quality_score") or strategy_data.get("ai_score", 50),
                    strategy_data.get("ai_notes_tr") or strategy_data.get("ai_notes", ""),
                    strategy_data.get("rule_quality", "weak"),
                ),
            )
            conn.commit()
            sid = int(cur.lastrowid)
            conn.close()
            return sid
        stmt = text(
            """
            INSERT INTO filtered_strategies
            (raw_hash_id, category, strategy_name, summary, entry_rules, exit_rules, indicators, tp_pct, sl_pct, timeframe, markets, ai_score, ai_notes, rule_quality)
            VALUES
            (:raw_hash_id, :category, :strategy_name, :summary, :entry_rules, :exit_rules, CAST(:indicators AS jsonb), :tp_pct, :sl_pct, :timeframe, CAST(:markets AS jsonb), :ai_score, :ai_notes, :rule_quality)
            RETURNING id
            """
        )
        with self.engine.begin() as conn:
            row = conn.execute(
                stmt,
                {
                    "raw_hash_id": raw_hash_id,
                    "category": strategy_data.get("category", "STRATEGY"),
                    "strategy_name": strategy_data.get("strategy_name", "Unknown Strategy"),
                    "summary": strategy_data.get("summary_tr") or strategy_data.get("summary", ""),
                    "entry_rules": strategy_data.get("entry_rules", ""),
                    "exit_rules": strategy_data.get("exit_rules", ""),
                    "indicators": json.dumps(strategy_data.get("indicators", [])),
                    "tp_pct": strategy_data.get("tp_pct", 3.0),
                    "sl_pct": strategy_data.get("sl_pct", 1.5),
                    "timeframe": strategy_data.get("timeframe", "1d"),
                    "markets": json.dumps(strategy_data.get("markets", ["stocks"])),
                    "ai_score": strategy_data.get("quality_score") or strategy_data.get("ai_score", 50),
                    "ai_notes": strategy_data.get("ai_notes_tr") or strategy_data.get("ai_notes", ""),
                    "rule_quality": strategy_data.get("rule_quality", "weak"),
                },
            ).first()
            return int(row[0]) if row else -1

    def save_insight(self, raw_hash_id: str, insight_data: Dict) -> int:
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO insights (raw_hash_id, title, summary, sentiment, confidence, key_points, actionable_takeaways, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_hash_id,
                    insight_data.get("title", ""),
                    insight_data.get("summary", ""),
                    insight_data.get("sentiment", ""),
                    insight_data.get("confidence", ""),
                    json.dumps(insight_data.get("key_points", [])),
                    json.dumps(insight_data.get("actionable_takeaways", [])),
                    insight_data.get("source_url", ""),
                ),
            )
            conn.commit()
            sid = int(cur.lastrowid)
            conn.close()
            return sid
        stmt = text(
            """
            INSERT INTO insights (raw_hash_id, title, summary, sentiment, confidence, key_points, actionable_takeaways, source_url)
            VALUES (:raw_hash_id, :title, :summary, :sentiment, :confidence, CAST(:key_points AS jsonb), CAST(:actionable AS jsonb), :source_url)
            RETURNING id
            """
        )
        with self.engine.begin() as conn:
            row = conn.execute(
                stmt,
                {
                    "raw_hash_id": raw_hash_id,
                    "title": insight_data.get("title", ""),
                    "summary": insight_data.get("summary", ""),
                    "sentiment": insight_data.get("sentiment", ""),
                    "confidence": insight_data.get("confidence", ""),
                    "key_points": json.dumps(insight_data.get("key_points", [])),
                    "actionable": json.dumps(insight_data.get("actionable_takeaways", [])),
                    "source_url": insight_data.get("source_url", ""),
                },
            ).first()
            return int(row[0]) if row else -1

    def get_filtered_strategies(self, min_score: int = 0, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        if self._sqlite:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            q = """
                SELECT fs.*, rp.title as post_title, rp.url as post_url, rp.subreddit, rp.score as upvotes, rp.post_created_at as post_date
                FROM filtered_strategies fs
                LEFT JOIN raw_posts rp ON rp.hash_id = fs.raw_hash_id
                WHERE fs.ai_score >= ?
            """
            params: list[Any] = [min_score]
            if status:
                q += " AND fs.status = ?"
                params.append(status)
            q += " ORDER BY fs.ai_score DESC, fs.created_at DESC LIMIT ?"
            params.append(limit)
            cur.execute(q, params)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            for d in rows:
                d["indicators"] = self._json_safe(d.get("indicators")) or []
                d["markets"] = self._json_safe(d.get("markets")) or []
                d["test_results"] = self._json_safe(d.get("test_results")) if d.get("test_results") else None
            return rows
        q = "SELECT fs.*, rp.title as post_title, rp.url as post_url, rp.subreddit, rp.score as upvotes, rp.post_created_at as post_date FROM filtered_strategies fs LEFT JOIN raw_posts rp ON rp.hash_id=fs.raw_hash_id WHERE fs.ai_score >= :min_score"
        params: Dict[str, Any] = {"min_score": min_score, "limit": limit}
        if status:
            q += " AND fs.status = :status"
            params["status"] = status
        q += " ORDER BY fs.ai_score DESC, fs.created_at DESC LIMIT :limit"
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["indicators"] = self._json_safe(d.get("indicators")) or []
            d["markets"] = self._json_safe(d.get("markets")) or []
            d["test_results"] = self._json_safe(d.get("test_results")) if d.get("test_results") else None
            out.append(d)
        return out

    def update_strategy_pipeline(self, strategy_id: int, *, status: Optional[str] = None, approval_status: Optional[str] = None, execution_status: Optional[str] = None, fix_category: Optional[str] = None, last_error: Optional[str] = None, last_model: Optional[str] = None, converted_at: bool = False, tested_at: bool = False, test_results: Optional[Dict] = None, tested: Optional[bool] = None, python_code: Optional[str] = None) -> bool:
        fields = []
        params: Dict[str, Any] = {"id": strategy_id}

        def add(name, val):
            fields.append(f"{name} = :{name}")
            params[name] = val

        if status is not None:
            add("status", status)
        if approval_status is not None:
            add("approval_status", approval_status)
        if execution_status is not None:
            add("execution_status", execution_status)
        if fix_category is not None:
            add("fix_category", fix_category)
        if last_error is not None:
            add("last_error", last_error)
        if last_model is not None:
            add("last_model", last_model)
        if test_results is not None:
            fields.append("test_results = CAST(:test_results AS jsonb)")
            params["test_results"] = json.dumps(test_results)
        if tested is not None:
            add("tested", bool(tested))
        if python_code is not None:
            add("python_code", python_code)
        if converted_at:
            fields.append("converted_at = CURRENT_TIMESTAMP")
        if tested_at:
            fields.append("tested_at = CURRENT_TIMESTAMP")
        if not fields:
            return True
        q = f"UPDATE filtered_strategies SET {', '.join(fields)} WHERE id = :id"
        with self.engine.begin() as conn:
            res = conn.execute(text(q), params)
            return res.rowcount > 0

    def get_actionable_strategies(self, *, status: Optional[str] = None, limit: int = 20, min_score: float = 0) -> List[Dict]:
        q = """
            SELECT fs.*, rp.url as post_url, rp.subreddit, rp.score as upvotes, rp.title as post_title
            FROM filtered_strategies fs
            LEFT JOIN raw_posts rp ON rp.hash_id = fs.raw_hash_id
            WHERE fs.category = 'ACTIONABLE_STRATEGY' AND fs.ai_score >= :min_score
        """
        params: Dict[str, Any] = {"min_score": min_score, "limit": limit}
        if status:
            q += " AND fs.status = :status"
            params["status"] = status
        q += " ORDER BY fs.ai_score DESC, fs.created_at DESC LIMIT :limit"
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).mappings().all()
        return [dict(r) for r in rows]

    def delete_strategy(self, strategy_id: int) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(text("DELETE FROM filtered_strategies WHERE id=:id"), {"id": strategy_id})
            return res.rowcount > 0

    def delete_all_strategies(self) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(text("DELETE FROM filtered_strategies"))
            return res.rowcount

    def delete_strategy_by_name(self, strategy_name: str) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(text("DELETE FROM filtered_strategies WHERE strategy_name=:name"), {"name": strategy_name})
            return res.rowcount > 0

    def reset_all_data(self) -> Dict:
        out = {}
        with self.engine.begin() as conn:
            for t in ["insights", "filtered_strategies", "raw_posts", "api_usage"]:
                count = int(conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() or 0)
                conn.execute(text(f"DELETE FROM {t}"))
                out[t] = count
        return out

    def get_data_summary(self) -> Dict:
        with self.engine.connect() as conn:
            total_raw = int(conn.execute(text("SELECT COUNT(*) FROM raw_posts")).scalar() or 0)
            total_processed = int(conn.execute(text("SELECT COUNT(*) FROM raw_posts WHERE ai_processed=TRUE")).scalar() or 0)
            total_strategies = int(conn.execute(text("SELECT COUNT(*) FROM filtered_strategies")).scalar() or 0)
            total_insights = int(conn.execute(text("SELECT COUNT(*) FROM insights")).scalar() or 0)
            cost = float(conn.execute(text("SELECT COALESCE(SUM(cost_usd),0) FROM api_usage")).scalar() or 0)
        return {
            "total_raw": total_raw,
            "total_processed": total_processed,
            "total_unprocessed": total_raw - total_processed,
            "total_strategies": total_strategies,
            "total_insights": total_insights,
            "by_subreddit": {},
            "by_category": {},
            "prefilter_skipped": 0,
            "api_cost_usd": cost,
        }

    def log_api_usage(self, stage: str, input_tokens: int, output_tokens: int, cost_usd: float):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO api_usage(stage, input_tokens, output_tokens, cost_usd) VALUES(:s,:i,:o,:c)"),
                {"s": stage, "i": input_tokens, "o": output_tokens, "c": cost_usd},
            )

    def get_total_api_cost(self) -> Dict:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(cost_usd),0) FROM api_usage")).first()
        return {"total_requests": row[0], "total_input_tokens": row[1], "total_output_tokens": row[2], "total_cost_usd": float(row[3])}

    def get_api_usage_by_stage(self) -> Dict:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT stage, COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(cost_usd),0) FROM api_usage GROUP BY stage")).all()
        return {r[0]: {"requests": r[1], "input_tokens": r[2], "output_tokens": r[3], "cost_usd": float(r[4])} for r in rows}

    def get_api_usage_log(self, limit: int = 100) -> List[Dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT timestamp, stage, input_tokens, output_tokens, cost_usd FROM api_usage ORDER BY timestamp DESC LIMIT :l"), {"l": limit}).all()
        return [{"timestamp": r[0], "stage": r[1], "input_tokens": r[2], "output_tokens": r[3], "cost_usd": float(r[4])} for r in rows]

    def get_stats(self) -> Dict:
        total = self.get_data_summary()
        api = self.get_total_api_cost()
        return {
            "raw_posts": total["total_raw"],
            "processed": total["total_processed"],
            "unprocessed": total["total_unprocessed"],
            "categories": {},
            "total_strategies": total["total_strategies"],
            "approved_strategies": 0,
            "total_insights": total["total_insights"],
            "api_requests": api["total_requests"],
            "api_cost_usd": api["total_cost_usd"],
        }

    def get_insights(self, limit: int = 50) -> List[Dict]:
        q = """
            SELECT i.*, rp.title as post_title, rp.url as post_url
            FROM insights i
            LEFT JOIN raw_posts rp ON i.raw_hash_id = rp.hash_id
            ORDER BY i.created_at DESC
            LIMIT :l
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), {"l": limit}).mappings().all()
        return [dict(r) for r in rows]

    def export_all_to_json(self, output_dir: str = None) -> str:
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "data" / "exports"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            "exported_at": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "raw_posts": self.get_raw_posts(limit=10000),
            "filtered_strategies": self.get_filtered_strategies(limit=1000),
            "insights": self.get_insights(limit=1000),
            "api_usage": self.get_total_api_cost(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return str(path)

    def close(self):
        if self.engine is not None:
            self.engine.dispose()


def get_test_config() -> Dict:
    return {
        "symbols": {
            "US Stocks": ["AAPL", "MSFT", "SPY", "QQQ"],
            "Crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "Forex": ["EURUSD", "GBPUSD", "USDJPY"],
            "Commodities": ["GOLD", "SILVER", "USOIL"],
        },
        "timeframes": ["1h", "4h", "1d"],
        "exchanges": {"US Stocks": "NASDAQ", "Crypto": "BINANCE", "Forex": "FX_IDC", "Commodities": "TVC"},
    }
