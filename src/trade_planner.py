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
        
    tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}.get(timeframe, 15)
    now = datetime.now(tz=timezone.utc)
    
    # Start in 1 minute
    start_time = now + timedelta(minutes=1) 
    
    # Calculate total minutes based on the AI's horizon (h10) AND the timeframe
    total_minutes = tf_minutes * horizon
    
    end_time = start_time + timedelta(minutes=total_minutes)
    
    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "start_time": start_time,
        "end_time": end_time,
        "duration_min": total_minutes,
        "horizon": horizon,
        "chart_tf": timeframe
    }
