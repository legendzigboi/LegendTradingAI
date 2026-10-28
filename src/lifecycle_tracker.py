"""
Lifecycle Tracker
Runs in the background. Checks PENDING trades, determines if they hit SL or TP, 
updates the database, and alerts Telegram.
"""
import time
import sqlite3
from datetime import datetime, timezone
from src.signal_db import _connect
from src.live_features import fetch_klines
from src.telegram_notify import send_message

def check_trades():
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM signals WHERE status = 'PENDING'").fetchall()
        
    for t in trades:
        symbol = t["symbol"]
        timeframe = t["timeframe"]
        tf_hours = {"1h": 1, "4h": 4, "1d": 24, "15m": 0.25, "5m": 0.083}[timeframe]
        horizon_hours = tf_hours * 10 
        
        entry_time = datetime.fromisoformat(t["ts"].replace("Z", "+00:00"))
        now = datetime.now(tz=timezone.utc)
        hours_elapsed = (now - entry_time).total_seconds() / 3600
        
        try:
            candles = fetch_klines(symbol, timeframe, limit=20)
        except Exception as e:
            print(f"Error fetching candles for {symbol}: {e}")
            continue

        status = "PENDING"
        outcome_price = None
        actual_return = None
        
        for c in candles:
            candle_time = datetime.fromtimestamp(c[0]/1000, tz=timezone.utc)
            if candle_time <= entry_time:
                continue
                
            high = float(c[2])
            low = float(c[3])
            
            if t["direction"] == "LONG":
                if low <= t["stop_loss"]:
                    status = "LOSS"
                    outcome_price = t["stop_loss"]
                    break
                elif high >= t["tp1"]:
                    status = "WIN"
                    outcome_price = t["tp1"]
                    break
            else: # SHORT
                if high >= t["stop_loss"]:
                    status = "LOSS"
                    outcome_price = t["stop_loss"]
                    break
                elif low <= t["tp1"]:
                    status = "WIN"
                    outcome_price = t["tp1"]
                    break
                    
        if status == "PENDING" and hours_elapsed >= horizon_hours:
            status = "EXPIRED"
            outcome_price = float(candles[-1][4])
            
        if status != "PENDING":
            if t["direction"] == "LONG":
                actual_return = (outcome_price - t["entry_price"]) / t["entry_price"]
            else:
                actual_return = (t["entry_price"] - outcome_price) / t["entry_price"]
                
            with _connect() as conn:
                conn.execute("""
                    UPDATE signals 
                    SET status = ?, outcome_price = ?, actual_return = ?, closed_at = ?
                    WHERE id = ?
                """, (status, outcome_price, actual_return, now.isoformat(), t["id"]))
                conn.commit()
                
            msg = f"🔔 TRADE CLOSED: {symbol} (ID: {t['id']})\nResult: {status}\nReturn: {actual_return*100:+.2f}%"
            send_message(msg)
            print(msg)

def run_tracker():
    print("📡 Lifecycle Tracker running. Checking every 5 minutes...")
    while True:
        check_trades()
        time.sleep(300) 

if __name__ == "__main__":
    run_tracker()
