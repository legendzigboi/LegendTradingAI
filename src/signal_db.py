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
    status TEXT DEFAULT 'PENDING',
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

def get_performance_stats():
    with _connect() as conn:
        wins = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'WIN'").fetchone()[0]
        losses = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'LOSS'").fetchone()[0]
        expired = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'EXPIRED'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'PENDING'").fetchone()[0]
        
        # FIX: Include expired trades in the total!
        total_closed = wins + losses + expired
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        return {
            "wins": wins, "losses": losses, "expired": expired, 
            "pending": pending, "win_rate": win_rate, "total_closed": total_closed
        }

def total_count():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
