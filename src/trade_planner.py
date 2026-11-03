from datetime import datetime, timezone, timedelta

def build_trade_plan(entry_price, direction, atr_14, timeframe="15m", expiry_minutes=None):
    if atr_14 < 0.005:
        atr_14 = 0.005
        
    # Map timeframe to minutes if expiry is not explicitly provided
    tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}.get(timeframe, 15)
    duration = expiry_minutes if expiry_minutes else tf_minutes
    
    # Scale ATR targets based on the length of the trade. Shorter trade = tighter targets.
    # We use a smaller multiplier for short expiries to make the R:R realistic.
    multiplier = 1.0
    if duration <= 5:
        multiplier = 0.4
    elif duration <= 15:
        multiplier = 0.7
        
    if direction.upper() == "LONG":
        stop_loss = entry_price * (1 - (atr_14 * 1.5 * multiplier))
        tp1 = entry_price * (1 + (atr_14 * 2.0 * multiplier))
    else: # SHORT
        stop_loss = entry_price * (1 + (atr_14 * 1.5 * multiplier))
        tp1 = entry_price * (1 - (atr_14 * 2.0 * multiplier))
        
    now = datetime.now(tz=timezone.utc)
    start_time = now + timedelta(minutes=1) 
    
    # EXACT EXPIRY
    end_time = start_time + timedelta(minutes=duration)
    
    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "start_time": start_time,
        "end_time": end_time,
        "duration_min": duration
    }
