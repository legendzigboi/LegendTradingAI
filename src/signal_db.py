import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL,
    model_version TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    stop_loss DOUBLE PRECISION NOT NULL,
    tp1 DOUBLE PRECISION NOT NULL,
    tp2 DOUBLE PRECISION NOT NULL,
    tp3 DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'PENDING',
    outcome_price DOUBLE PRECISION,
    actual_return DOUBLE PRECISION,
    closed_at TEXT
);
"""

def _connect():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is missing from environment variables.")
    # Render sometimes gives postgres://, psycopg2 prefers postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url)

def init_db():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return True

def log_signal(symbol, timeframe, direction, model_version, confidence, entry_price, stop_loss, tp1, tp2, tp3):
    ts = datetime.now(tz=timezone.utc).isoformat()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO signals (
                    ts, symbol, timeframe, direction, model_version,
                    confidence, entry_price, stop_loss, tp1, tp2, tp3, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
                RETURNING id
            """, (ts, symbol, timeframe, direction, model_version, confidence, entry_price, stop_loss, tp1, tp2, tp3))
            sig_id = cur.fetchone()[0]
        conn.commit()
        return sig_id
    finally:
        conn.close()

def get_pending_trades():
    conn = _connect()
    try:
        # RealDictCursor returns rows as dictionaries, just like sqlite3.Row
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM signals WHERE status = 'PENDING' ORDER BY ts DESC")
            return cur.fetchall()
    finally:
        conn.close()

def close_trade(trade_id, status, outcome_price, actual_return, closed_at):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE signals SET status = %s, outcome_price = %s, actual_return = %s, closed_at = %s WHERE id = %s
            """, (status, outcome_price, actual_return, closed_at, trade_id))
        conn.commit()
    finally:
        conn.close()

def get_performance_stats():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM signals WHERE status = 'WIN'")
            wins = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM signals WHERE status = 'LOSS'")
            losses = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM signals WHERE status = 'EXPIRED'")
            expired = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM signals WHERE status = 'PENDING'")
            pending = cur.fetchone()[0]

        total_closed = wins + losses + expired
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

        return {
            "wins": wins, "losses": losses, "expired": expired,
            "pending": pending, "win_rate": win_rate, "total_closed": total_closed
        }
    finally:
        conn.close()

def total_count():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM signals")
            return cur.fetchone()[0]
    finally:
        conn.close()
