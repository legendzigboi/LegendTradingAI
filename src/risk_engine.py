from datetime import datetime, timezone
from src.signal_db import get_daily_pnl

SYSTEM_PAUSED = False
MAX_DAILY_DRAWDOWN = -0.03 # -3%

def check_circuit_breaker():
    """Returns True if trading is allowed, False if halted."""
    global SYSTEM_PAUSED

    if SYSTEM_PAUSED:
        return False, "⛔ Risk Officer: System manually PAUSED."

    # 🚨 INDEPENDENT RISK ENGINE CHECK 🚨
    daily_pnl = get_daily_pnl()
    
    if daily_pnl <= MAX_DAILY_DRAWDOWN:
        SYSTEM_PAUSED = True
        return False, f"🔴 RISK OFFICER TRIGGERED: Daily drawdown hit {daily_pnl*100:.2f}%. Trading halted for the day to protect capital."

    return True, f"✅ Risk Check Passed. Today's PnL: {daily_pnl*100:.2f}%"

def set_pause(state: bool):
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = state
    return SYSTEM_PAUSED
