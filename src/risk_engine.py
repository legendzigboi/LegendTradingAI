"""
Risk Engine & Circuit Breaker
Prevents the bot from trading if daily drawdown exceeds 3%.
"""
import sqlite3
from datetime import datetime, timezone
from src.signal_db import _connect

SYSTEM_PAUSED = False

def check_circuit_breaker():
    """Returns True if trading is allowed, False if halted."""
    global SYSTEM_PAUSED
    
    if SYSTEM_PAUSED:
        return False, "⛔ Circuit Breaker is ACTIVE. Use /resume to override."

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    
    with _connect() as conn:
        # Sum the PnL of all closed trades today
        row = conn.execute("""
            SELECT SUM(actual_return), COUNT(*)
            FROM signals 
            WHERE status IN ('WIN', 'LOSS') 
            AND ts LIKE ?
        """, (f"{today}%",)).fetchone()
        
        # SQLite fetchone() returns a tuple. row[0] is the SUM, row[1] is the COUNT.
        daily_pnl = row[0] if row[0] is not None else 0.0
        
    if daily_pnl <= -0.03:
        SYSTEM_PAUSED = True
        return False, f"🔴 CIRCUIT BREAKER TRIPPED: Daily drawdown hit {daily_pnl*100:.2f}%. Trading halted."
        
    return True, f"✅ Risk Check Passed. Today's PnL: {daily_pnl*100:.2f}%"

def set_pause(state: bool):
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = state
    return SYSTEM_PAUSED
