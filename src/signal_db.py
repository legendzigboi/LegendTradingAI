"""
SQLite database for paper trader signals and outcomes.
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/paper_trader.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL,
    model_version TEXT NOT NULL,
    confidence REAL NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    tp1 REAL NOT NULL,
    tp2 REAL NOT NULL,
    tp3 REAL NOT NULL,
    status TEXT DEFAULT 'PENDING',   -- PENDING, WIN, LOSS, EXPIRED
    outcome_price REAL,
    actual_return REAL,
    closed_at TEXT
);
"""

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)
    return True

def log_signal(symbol, timeframe, direction, model_version, confidence, entry_price, stop_loss, tp1, tp2, tp3):
    ts = datetime.now(tz=timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO signals (
                ts, symbol, timeframe, direction, model_version,
                confidence, entry_price, stop_loss, tp1, tp2, tp3, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (ts, symbol, timeframe, direction, model_version, confidence, entry_price, stop_loss, tp1, tp2, tp3))
        return cur.lastrowid

def get_pending_trades():
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM signals WHERE status = 'PENDING' ORDER BY ts DESC").fetchall()
        return [dict(r) for r in rows]

def total_count():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

if __name__ == "__main__":
    init_db()
    print(f"✅ DB initialized. Total signals: {total_count()}")
