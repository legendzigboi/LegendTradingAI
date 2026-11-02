from datetime import datetime, timezone, timedelta

def build_trade_plan(entry_price, direction, atr_14, timeframe="15m", horizon=10):
    if atr_14 < 0.005:
        atr_14 = 0.005
        
    if direction.upper() == "LONG":
        stop_loss = entry_price * (1 - (atr_14 * 1.5))
        tp1 = entry_price * (1 + (atr_14 * 2.0))
    else: # SHORT
        stop_loss = entry_price * (1 + (atr_14 * 1.5))
        tp1 = entry_price * (1 - (atr_14 * 2.0))
        
    # Timeframe mapping for expiry
    tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}.get(timeframe, 15)
    now = datetime.now(tz=timezone.utc)
    
    # Start 1 minute from now, End exactly 1 candle later (like a binary option)
    start_time = now + timedelta(minutes=1) 
    end_time = start_time + timedelta(minutes=tf_minutes * horizon)
    
    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "start_time": start_time,
        "end_time": end_time,
        "duration_min": tf_minutes * horizon
    }
