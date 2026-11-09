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

CREATE TABLE IF NOT EXISTS research_insights (
    id SERIAL PRIMARY KEY,
    ts TEXT NOT NULL,
    category TEXT NOT NULL,
    insight TEXT NOT NULL,
    win_rate DOUBLE PRECISION,
    sample_size INTEGER
);
"""

def _connect():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is missing.")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url, connect_timeout=10)

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

# ... (Keep existing functions: get_pending_trades, close_trade, update_stop_loss, get_performance_stats, save_insight, get_all_insights, get_all_closed_signals) ...

# 🚨 NEW: GET HISTORICAL WIN RATE FOR SPECIFIC PAIR 🚨
def get_historical_win_rate(symbol, timeframe):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'WIN') as wins,
                    COUNT(*) FILTER (WHERE status IN ('WIN', 'LOSS')) as total
                FROM signals 
                WHERE symbol = %s AND timeframe = %s
            """, (symbol, timeframe))
            row = cur.fetchone()
            if row and row[1] > 0:
                return row[0] / row[1] # Return win rate as decimal
            return None # No data yet
    finally:
        conn.close()
