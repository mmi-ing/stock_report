"""뉴스 중복 방지 SQLite 저장소."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).parent / "data" / "news.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_news (
            id   TEXT PRIMARY KEY,
            ticker TEXT,
            title  TEXT,
            sent_at INTEGER
        )
    """)
    conn.commit()
    return conn


def is_sent(news_id: str) -> bool:
    with _conn() as conn:
        return conn.execute("SELECT 1 FROM sent_news WHERE id=?", (news_id,)).fetchone() is not None


def mark_sent(news_id: str, ticker: str, title: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sent_news (id, ticker, title, sent_at) VALUES (?,?,?,?)",
            (news_id, ticker, title, int(time.time())),
        )
        conn.commit()


def cleanup_old(days: int = 7) -> None:
    """days일 이상 된 기사 삭제."""
    cutoff = int(time.time()) - days * 86400
    with _conn() as conn:
        conn.execute("DELETE FROM sent_news WHERE sent_at < ?", (cutoff,))
        conn.commit()
