"""
SQLite database for paper trader signals and outcomes.

Schema:
  signals   — every prediction made by the trader
  daily_summary — cached aggregates (optional, for fast reporting)
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
    horizon INTEGER NOT NULL,
    direction TEXT NOT NULL,
    role TEXT NOT NULL,
    model_version TEXT NOT NULL,
    confidence REAL NOT NULL,
    entry_price REAL NOT NULL,
    target_price REAL,
    stop_price REAL,
    signal_type TEXT NOT NULL,       -- STRONG | WEAK
    -- outcome fields (filled when the horizon passes)
    outcome_checked INTEGER DEFAULT 0,
    outcome_ts TEXT,
    outcome_price REAL,
    bars_elapsed INTEGER,
    actual_return REAL,
    win INTEGER
);

CREATE INDEX IF NOT EXISTS idx_signals_pending
    ON signals (outcome_checked, ts);

CREATE INDEX IF NOT EXISTS idx_signals_symbol
    ON signals (symbol, ts);
"""


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript(SCHEMA)
    return True


def log_signal(symbol, horizon, direction, role, model_version,
               confidence, entry_price, target_price, stop_price, signal_type):
    """Insert a new signal. Returns the new row id."""
    ts = datetime.now(tz=timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO signals (
                ts, symbol, horizon, direction, role, model_version,
                confidence, entry_price, target_price, stop_price, signal_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, symbol, horizon, direction, role, model_version,
              confidence, entry_price, target_price, stop_price, signal_type))
        return cur.lastrowid


def get_pending_signals():
    """Return signals where outcome hasn't been checked yet."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM signals
            WHERE outcome_checked = 0
            ORDER BY ts ASC
        """).fetchall()
        return [dict(r) for r in rows]


def record_outcome(signal_id, outcome_price, bars_elapsed):
    """Update a signal with its outcome."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT symbol, horizon, direction, entry_price FROM signals WHERE id = ?",
            (signal_id,)
        ).fetchone()
        if not row:
            return False
        symbol, horizon, direction, entry_price = row

        actual_return = (outcome_price - entry_price) / entry_price
        if direction == "short":
            actual_return = -actual_return
        win = 1 if actual_return > 0 else 0

        ts = datetime.now(tz=timezone.utc).isoformat()
        conn.execute("""
            UPDATE signals
            SET outcome_checked = 1,
                outcome_ts = ?,
                outcome_price = ?,
                bars_elapsed = ?,
                actual_return = ?,
                win = ?
            WHERE id = ?
        """, (ts, outcome_price, bars_elapsed, actual_return, win, signal_id))
        return True


def stats_last_n_days(days=30):
    """Summary stats over completed signals in the last N days."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"""
            SELECT symbol, horizon, direction,
                   COUNT(*)                    AS trades,
                   SUM(win)                    AS wins,
                   AVG(actual_return)          AS avg_return,
                   AVG(confidence)             AS avg_conf
            FROM signals
            WHERE outcome_checked = 1
              AND ts > datetime('now', '-{int(days)} days')
            GROUP BY symbol, horizon, direction
            ORDER BY AVG(actual_return) DESC
        """).fetchall()
        return [dict(r) for r in rows]


def total_count():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]


if __name__ == "__main__":
    init_db()
    print(f"✅ DB initialized at {DB_PATH.resolve()}")
    print(f"   Total signals: {total_count()}")
