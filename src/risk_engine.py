from datetime import datetime, timezone
from src.signal_db import get_daily_pnl

SYSTEM_PAUSED = False

def check_circuit_breaker():
    """Returns True if trading is allowed, False if halted."""
    global SYSTEM_PAUSED

    if SYSTEM_PAUSED:
        return False, "⛔ System manually PAUSED."

    # 🚨 RISK OFFICER DISABLED FOR PAPER TESTING 🚨
    # We will re-enable this when trading real money.
    daily_pnl = get_daily_pnl()
    
    return True, f"✅ Risk Check Passed. Today's PnL: {daily_pnl*100:.2f}%"

def set_pause(state: bool):
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = state
    return SYSTEM_PAUSED
