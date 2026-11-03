import sqlite3
from datetime import datetime, timezone
from src.signal_db import get_pending_trades, close_trade
from src.live_features import fetch_klines
from src.telegram_notify import send_message

async def check_trades(context=None):
    trades = get_pending_trades()
        
    if not trades:
        return

    print(f"🔍 [Tracker] Checking {len(trades)} pending trades...")
        
    for t in trades:
        symbol = t["symbol"]
        timeframe = t["timeframe"]
        
        tf_hours = {"1m": 0.016, "5m": 0.083, "15m": 0.25, "1h": 1, "4h": 4, "1d": 24}.get(timeframe, 1)
        horizon_hours = tf_hours 
        
        entry_time = datetime.fromisoformat(t["ts"].replace("Z", "+00:00"))
        now = datetime.now(tz=timezone.utc)
        hours_elapsed = (now - entry_time).total_seconds() / 3600
        
        try:
            candles = fetch_klines(symbol, timeframe, limit=200)
        except Exception as e:
            print(f"Error fetching candles for {symbol}: {e}")
            continue

        status = "PENDING"
        outcome_price = None
        actual_return = None
        
        for c in candles:
            candle_time = datetime.fromtimestamp(c[0]/1000, tz=timezone.utc)
            if candle_time <= entry_time: continue
                
            high = float(c[2]); low = float(c[3])
            
            if t["direction"] == "LONG":
                if low <= t["stop_loss"]: status, outcome_price = "LOSS", t["stop_loss"]; break
                elif high >= t["tp1"]: status, outcome_price = "WIN", t["tp1"]; break
            else:
                if high >= t["stop_loss"]: status, outcome_price = "LOSS", t["stop_loss"]; break
                elif low <= t["tp1"]: status, outcome_price = "WIN", t["tp1"]; break
                    
        # 🚨 NEW LOGIC: If time is up, classify as WIN or LOSS based on final price 🚨
        if status == "PENDING" and hours_elapsed >= horizon_hours:
            outcome_price = float(candles[-1][4])
            if t["direction"] == "LONG": 
                actual_return = (outcome_price - t["entry_price"]) / t["entry_price"]
            else: 
                actual_return = (t["entry_price"] - outcome_price) / t["entry_price"]
            
            if actual_return > 0.00005: # If it closed in profit
                status = "WIN"
            elif actual_return < -0.00005: # If it closed in loss
                status = "LOSS"
            else:
                status = "EXPIRED" # Exactly breakeven
            
        if status != "PENDING":
            if actual_return is None:
                if t["direction"] == "LONG": actual_return = (outcome_price - t["entry_price"]) / t["entry_price"]
                else: actual_return = (t["entry_price"] - outcome_price) / t["entry_price"]
                
            close_trade(t["id"], status, outcome_price, actual_return, now.isoformat())
                
            msg = f"🔔 TRADE CLOSED: {symbol} (ID: {t['id']})\nResult: {status}\nReturn: {actual_return*100:+.2f}%"
            send_message(msg)
            print(msg)
        else:
            print(f"⏳ [Tracker] ID: {t['id']} ({symbol}) is still PENDING.")
